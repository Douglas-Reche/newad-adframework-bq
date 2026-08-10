"""
AdFramework Data Hub -- painel local, read-only, do pipeline BQ de Douglas.

Roda 100% local (nao ha deploy). Le direto do projeto GCP `adframework`
via credenciais ADC (gcloud auth application-default login).

Nunca ESCREVE nos datasets intocaveis (pixel, adtracking, analytics,
finops_billing) nem em tabelas do Admin UI do Shiro (io_manager_v2 etc).
finops_billing e lido (read-only) na aba de Custos -- e o billing export
real da GCP, ja habilitado por outra pessoa; este hub so consulta.

Uso:
    cd hub
    pip install -r requirements.txt
    streamlit run app.py
"""

import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import google.auth
import pandas as pd
import streamlit as st
import yaml
from google.api_core.exceptions import Forbidden, NotFound
from google.auth import impersonated_credentials
from google.cloud import bigquery

PROJECT_ID = "adframework"
HUB_PASSWORD = os.environ.get("HUB_PASSWORD")  # se ausente (rodando local), nao pede senha

# Escrita isolada: so as abas de Overrides Historicos e Propostas de Mudanca usam
# essa SA, via impersonation (sem chave JSON). A SA principal do hub
# (douglas-data-hub-sa) continua 100% read-only -- nao muda em nada para as
# outras abas. dataEditor escopado por dataset: `core` + `raw` em $PROJECT_ID
# (Propostas de Mudanca) e `raw`/`stg`/`core` em douglas-bq-staging (Overrides
# Historicos + Config de Overrides, ambiente de teste) -- ver hub/deploy.sh.
WRITER_SA_EMAIL = os.environ.get(
    "WRITER_SA_EMAIL", f"douglas-data-hub-writer-sa@{PROJECT_ID}.iam.gserviceaccount.com"
)

# Ambiente de teste do fluxo de override historico -- 2026-08-06 douglas-bq-staging
# virou um ambiente standalone completo (raw copiado fisicamente, stg/core/gold
# 100% locais, paridade validada com producao). O fluxo inteiro (landing RAW,
# normalizacao, carga, toggle) roda AQUI primeiro, nunca em `adframework`
# (producao) -- essas duas tabelas nunca foram aplicadas em producao de proposito.
# Mesma constante de projeto usada pela landing RAW (RAW_LANDING_PROJECT_ID,
# definida mais abaixo) -- redeclarada aqui em cima porque e usada antes.
HISTORICAL_OVERRIDE_PROJECT_ID = "douglas-bq-staging"

# Escopo fechado do override historico -- decisao explicita: isso NAO generaliza
# para outros clientes/periodos. So Cora, so Jan-Jun/2026. Ver docs/PROCESS.md
# e memoria project_gold_layer_state para o contexto completo.
CORA_CLIENT_ID = "banco_cora_fe13d78a"
CORA_OVERRIDE_START = date(2026, 1, 1)
CORA_OVERRIDE_END = date(2026, 6, 30)
OVERRIDE_TABLE = f"{HISTORICAL_OVERRIDE_PROJECT_ID}.stg.historical_overrides_delivery"
OVERRIDE_TARGET_FIELDS = ["day", "platform", "formato", "goal_type", "impressions", "clicks", "investimento"]

# Desenho fechado com o Douglas em 2026-08-05: generaliza o override historico
# para qualquer cliente (nao mais so Cora). O range de cada cliente (MIN/MAX day)
# vem SEMPRE ao vivo de OVERRIDE_TABLE, nunca de config digitada. O liga/desliga
# (`override_active`) fica em core.client_reporting_source_config -- tabela SCD2
# nova, construida pelo backend em paralelo (client_id, override_active,
# effective_from, effective_to, reason, confirmed_by, confirmed_at). Pode ainda
# nao existir em producao -- a secao abaixo trata isso sem quebrar.
# Vive em douglas-bq-staging (mesmo motivo de OVERRIDE_TABLE acima) -- NUNCA
# em `adframework` (producao), nunca existiu la de proposito.
CLIENT_REPORTING_SOURCE_CONFIG_TABLE = f"{HISTORICAL_OVERRIDE_PROJECT_ID}.core.client_reporting_source_config"

# Upload de Planilha Historica (landing RAW) -- peca (a) do desenho fechado em
# 2026-08-05/06 para generalizar overrides historicos alem da Cora (ver
# docs/known_issues.md item S4, repo newad-adframework-bq). Sobe a planilha
# crua do comercial SEM NENHUM tratamento, pousa como RAW literal dentro do
# projeto de STAGING (nao producao -- e trabalho de descoberta antes de decidir
# como normalizar).
# Contrato confirmado com o backend (repassado pelo orquestrador, 2026-08-06):
# duas tabelas em douglas-bq-staging.raw --
#   historical_uploads: upload_id, client_id, source_filename, row_number,
#     raw_row (JSON-text STRING), uploaded_at, uploaded_by
#   historical_uploads_meta: upload_id, client_id, source_filename,
#     column_names (ARRAY<STRING>), row_count, uploaded_at, uploaded_by
# DDL em raw/ddl/historical_uploads.sql + historical_uploads_meta.sql. Script
# CLI irmao (uso fora do Hub) em scripts/deploy/load_historical_raw.py -- o
# Hub NAO chama esse script, escreve direto via BQ client (mesmo padrao de
# commit_override), ver stage_raw_historical_upload().
RAW_LANDING_PROJECT_ID = HISTORICAL_OVERRIDE_PROJECT_ID
RAW_LANDING_DATASET = "raw"
RAW_UPLOADS_TABLE = f"{RAW_LANDING_PROJECT_ID}.{RAW_LANDING_DATASET}.historical_uploads"
RAW_UPLOADS_META_TABLE = f"{RAW_LANDING_PROJECT_ID}.{RAW_LANDING_DATASET}.historical_uploads_meta"

# Fila generica de propostas de mudanca pendentes de aprovacao humana. Tabela
# desenhada pelo backend para servir qualquer fonte futura (hoje so
# source='siprocal_diff', da reconciliacao incremental de raw.sp_delivery).
# So a aba "Propostas de Mudanca" le/escreve aqui -- ver commit_proposal_decision abaixo.
PROPOSALS_TABLE = f"{PROJECT_ID}.core.change_proposals"

# Regras de negocio configuraveis por cliente (ex: teto de impressao diaria) --
# sub-etapa "b" (listagem) da task "Desenhar UX/fluxo do formulario de regras de
# negocio no Hub". A tabela SO existe em douglas-bq-staging ate agora (nunca
# aplicada em producao -- ver CHANGELOG.md 2026-08-09 e docs/core_layer_design.md),
# entao a leitura fica qualificada com HISTORICAL_OVERRIDE_PROJECT_ID de proposito,
# nao PROJECT_ID. dim_client de staging (copia com paridade validada, ver comentario
# de HISTORICAL_OVERRIDE_PROJECT_ID acima) e usada so para o lookup de nome de
# cliente nos cards -- client_id de teste (test_client_fake_*) nao existe la, tratado
# como "nao encontrado" na UI, nao como erro. So leitura nesta sub-etapa: formulario
# de criacao/pausa e escrita ficam para sub-etapas seguintes.
BUSINESS_RULES_TABLE = f"{HISTORICAL_OVERRIDE_PROJECT_ID}.core.client_business_rules"
BUSINESS_RULES_DIM_CLIENT_TABLE = f"{HISTORICAL_OVERRIDE_PROJECT_ID}.core.dim_client"

# Rotulo amigavel por rule_type -- fallback: mostra o rule_type cru se nao mapeado
# aqui (a listagem nunca deve quebrar so porque um rule_type novo apareceu).
RULE_TYPE_LABELS = {
    "impression_cap_pct": "Teto de Impressao Diaria (%)",
}

# status da linha HISTORICA (effective_to preenchido) -> (rotulo, cor do st.badge).
# Ver comentario de design em core/ddl/client_business_rules.sql: 'active' numa linha
# fechada significa "substituida por versao nova" (SCD2 natural), 'paused' significa
# "fechada sem substituto" (pausa deliberada) -- badges diferentes de proposito.
HISTORY_STATUS_STYLE = {
    "active": ("substituida", "blue"),
    "paused": ("pausada", "orange"),
}

# Datasets que este hub tem permissao de listar, na ORDEM real do pipeline.
# NUNCA adicionar aqui: pixel, adtracking, analytics, finops_billing (intocaveis)
# ou datasets exclusivos do Admin UI do Shiro.
LAYERS = [
    {"id": "raw", "label": "RAW", "icon": ":material/download:", "desc": "Dados brutos, direto da fonte (MediaSmart, MGID, Siprocal)"},
    {"id": "raw_siprocal", "label": "RAW · Siprocal", "icon": ":material/download:", "desc": "Dump completo da planilha a cada run"},
    {"id": "stg", "label": "STG", "icon": ":material/filter_alt:", "desc": "Dados padronizados e limpos"},
    {"id": "core", "label": "CORE", "icon": ":material/hub:", "desc": "Modelos centrais reutilizaveis"},
    {"id": "marts", "label": "MARTS", "icon": ":material/store:", "desc": "Modelos por dominio/area"},
    {"id": "share", "label": "SHARE", "icon": ":material/share:", "desc": "Compartilhado com Admin UI / consumo externo"},
    {"id": "gold", "label": "GOLD", "icon": ":material/verified:", "desc": "Camada final -- alimenta o Power BI"},
]
DATASETS = [layer["id"] for layer in LAYERS]

HUB_DIR = Path(__file__).parent

# status -> (label, cor do st.badge, icone material)
STATUS_STYLE = {
    "fresco": ("fresco", "green", ":material/check_circle:"),
    "atencao": ("atencao", "orange", ":material/warning:"),
    "atrasado": ("atrasado", "red", ":material/error:"),
    "sem_dado": ("sem dado", "gray", ":material/help:"),
    "tabela_nao_encontrada": ("nao encontrada", "gray", ":material/search_off:"),
    "view": ("view (ver tabela base)", "blue", ":material/visibility:"),
}
# ordem de severidade -- usado pra achar o "pior" status de um grupo de tabelas.
# "view" fica abaixo de "fresco" de proposito: nao deve nunca ser o "pior" status
# de um grupo so por ser view -- quem importa e a tabela real por tras dela.
STATUS_SEVERITY = {"atrasado": 3, "sem_dado": 2, "atencao": 1, "fresco": 0, "view": -1}

POWERBI_STATUS_STYLE = {
    "planejado": ("planejado", "gray"),
    "em_build": ("em build", "blue"),
    "revisao": ("em revisao", "orange"),
    "publicado": ("publicado", "green"),
}

# Pricing on-demand BigQuery, US multi-regiao (2026) -- so usado como fallback quando
# o billing export real (abaixo) nao estiver disponivel.
BQ_BYTES_PER_TIB = 1024 ** 4
BQ_FREE_TIB_PER_MONTH = 1
BQ_PRICE_PER_TIB = 6.25
BQ_FREE_STORAGE_GB = 10

# Billing export real (leitura apenas -- finops_billing e intocavel, nunca escrever aqui).
# Existe porque alguem (Shiro) ja habilitou o export da conta de faturamento pra BQ.
FINOPS_DATASET = "finops_billing"
BILLING_EXPORT_TABLE = "gcp_billing_export_v1_015F92_E18CAF_B39F18"
BILLING_EXPORT_RESOURCE_TABLE = "gcp_billing_export_resource_v1_015F92_E18CAF_B39F18"

st.set_page_config(page_title="AdFramework Data Hub", layout="wide", page_icon=":material/dashboard:")

# Identidade visual Newad (paleta dark, estilo dev-tool). Cores base em .streamlit/config.toml;
# aqui so o que o theme do Streamlit nao cobre (surface dos cards, tipografia).
st.markdown(
    """
    <style>
    [data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
        background-color: #161b22;
        border-radius: 10px;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 10px;
    }
    html, body, [class*="css"] {
        font-family: -apple-system, system-ui, "Segoe UI", sans-serif;
    }
    code, pre, [data-testid="stCode"] {
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace !important;
    }
    small, .stCaption, [data-testid="stCaptionContainer"] {
        font-size: 0.72rem !important;
        opacity: 0.75;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_bq_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


@st.cache_data(ttl=300)
def load_table_metadata() -> pd.DataFrame:
    """Metadado nativo via __TABLES__ -- nao processa dados, nao cobra bytes."""
    client = get_bq_client()
    # __TABLES__ ja tem sua propria coluna dataset_id -- nao redeclarar, so unir.
    unions = "\n  UNION ALL\n  ".join(
        f"SELECT * FROM `{PROJECT_ID}.{ds}.__TABLES__`" for ds in DATASETS
    )
    query = f"""
    SELECT
      dataset_id AS dataset,
      table_id AS tabela,
      CASE type WHEN 1 THEN 'tabela' WHEN 2 THEN 'view' WHEN 3 THEN 'externa' END AS tipo,
      row_count AS linhas,
      ROUND(size_bytes / 1024 / 1024, 1) AS tamanho_mb,
      TIMESTAMP_MILLIS(last_modified_time) AS ultima_modificacao
    FROM (
      {unions}
    )
    ORDER BY dataset, linhas DESC
    """
    df = client.query(query).to_dataframe()
    # Views: last_modified_time e da DEFINICAO (ultimo ALTER/CREATE OR REPLACE),
    # nao dos dados por tras dela -- aplicar freshness de tabela aqui da falso
    # alarme (view "atrasada" com dado fresco no raw por baixo). Badge proprio.
    df["freshness"] = df.apply(
        lambda r: "view" if r["tipo"] == "view" else freshness_status(r["ultima_modificacao"]),
        axis=1,
    )
    return df


def owner_of_service(name: str) -> str:
    """adframework-etl e o unico Cloud Run/service account do pipeline do Douglas -- todo o
    resto (aat-console, advanced-adtracking, admin-ui) e do Shiro."""
    return "Douglas" if "adframework-etl" in (name or "").lower() else "Shiro"


@st.cache_data(ttl=600)
def load_cloud_run_costs(days: int = 30):
    """Custo real de Cloud Run por servico, via view curada finops_billing.vw_cloud_run_daily."""
    client = get_bq_client()
    query = f"""
    SELECT
      resource_name AS service,
      SUM(gross_cost) AS gross_30d,
      SUM(net_cost) AS net_30d
    FROM `{PROJECT_ID}.{FINOPS_DATASET}.vw_cloud_run_daily`
    WHERE usage_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
    GROUP BY 1
    ORDER BY gross_30d DESC
    """
    df = client.query(query).to_dataframe()
    df["owner"] = df["service"].apply(owner_of_service)
    return df


@st.cache_data(ttl=600)
def load_min_instance_costs(days: int = 30):
    """Detecta gasto com min-instances (instancia sempre ligada) -- maior driver de custo oculto."""
    client = get_bq_client()
    query = f"""
    SELECT
      resource.name AS service,
      sku.description AS sku,
      SUM(cost) AS cost_30d
    FROM `{PROJECT_ID}.{FINOPS_DATASET}.{BILLING_EXPORT_RESOURCE_TABLE}`
    WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      AND sku.description LIKE '%Min Instance%'
      AND cost > 0
    GROUP BY 1, 2
    ORDER BY cost_30d DESC
    """
    return client.query(query).to_dataframe()


def _cost_by_service_since(date_expr: str) -> pd.DataFrame:
    """Query compartilhada: soma gross/net por servico GCP desde `date_expr` (expressao SQL
    de data, ex. `DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)` ou `DATE_TRUNC(CURRENT_DATE(), MONTH)`).
    Usada tanto pela aba Custos (janela de 30 dias) quanto pelo resumo do mes corrente no
    farol da tela principal -- evita duplicar a mesma query com janelas diferentes."""
    client = get_bq_client()
    query = f"""
    SELECT
      service_name,
      SUM(gross_cost) AS gross,
      SUM(net_cost) AS net
    FROM `{PROJECT_ID}.{FINOPS_DATASET}.vw_cost_daily_service`
    WHERE usage_date >= {date_expr}
    GROUP BY 1
    ORDER BY gross DESC
    """
    return client.query(query).to_dataframe()


@st.cache_data(ttl=600)
def load_cost_by_service(days: int = 30):
    """Custo total por servico GCP (SKU agregado), via view curada finops_billing.vw_cost_daily_service."""
    df = _cost_by_service_since(f"DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)")
    return df.rename(columns={"gross": "gross_30d", "net": "net_30d"})


@st.cache_data(ttl=600)
def load_cost_current_month():
    """Resumo gross/net do mes corrente (calendario), pro farol da tela principal.
    Reusa _cost_by_service_since -- so muda a janela de data, mesma view curada."""
    df = _cost_by_service_since("DATE_TRUNC(CURRENT_DATE(), MONTH)")
    gross = df["gross"].sum() if not df.empty else 0.0
    net = df["net"].sum() if not df.empty else 0.0
    return gross, net


@st.cache_data(ttl=600)
def load_cost_by_project(days: int = 30):
    """Todos os projetos cobrados na mesma conta de faturamento -- confere se so adframework/nwd-aat aparecem."""
    client = get_bq_client()
    query = f"""
    SELECT
      project_id,
      SUM(gross_cost) AS gross_30d,
      SUM(net_cost) AS net_30d
    FROM `{PROJECT_ID}.{FINOPS_DATASET}.vw_cost_daily_service`
    WHERE usage_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
    GROUP BY 1
    ORDER BY gross_30d DESC
    """
    return client.query(query).to_dataframe()


@st.cache_data(ttl=600)
def load_bq_query_volume(days: int = 30):
    """Volume de queries BQ por usuario/service account, via INFORMATION_SCHEMA.JOBS (location=US)."""
    client = get_bq_client()
    query = f"""
    SELECT
      SPLIT(user_email, '@')[SAFE_OFFSET(0)] AS user,
      COUNT(*) AS n_queries,
      ROUND(SUM(total_bytes_processed) / 1e12, 6) AS tb_processed,
      ROUND(SUM(total_bytes_billed) / 1e12, 6) AS tb_billed
    FROM `region-US`.INFORMATION_SCHEMA.JOBS
    WHERE DATE(creation_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      AND job_type = 'QUERY' AND state = 'DONE'
    GROUP BY 1
    ORDER BY tb_processed DESC
    """
    df = client.query(query, location="US").to_dataframe()
    df["owner"] = df["user"].apply(lambda u: "Douglas" if "adframework-etl" in u.lower() or u.lower().startswith("douglas") else "Shiro / outro")
    return df


@st.cache_data(ttl=600)
def load_bq_storage_via_api():
    """Tamanho real das tabelas via API Python (bq.get_table) -- evita o erro de location do
    INFORMATION_SCHEMA.TABLE_STORAGE. Views sempre retornam num_bytes=0, e normal."""
    client = get_bq_client()
    rows = []
    for ds_id in DATASETS:
        try:
            tables = list(client.list_tables(f"{PROJECT_ID}.{ds_id}"))
        except Exception:
            continue
        for t in tables:
            tbl = client.get_table(t)
            rows.append(
                {
                    "dataset": ds_id,
                    "tabela": tbl.table_id,
                    "tipo": tbl.table_type,
                    "gb": (tbl.num_bytes or 0) / (1024 ** 3),
                }
            )
    return pd.DataFrame(rows)


def freshness_status(last_modified) -> str:
    if pd.isna(last_modified):
        return "sem_dado"
    age_hours = (datetime.now(timezone.utc) - last_modified.to_pydatetime().replace(tzinfo=timezone.utc)).total_seconds() / 3600
    if age_hours <= 30:
        return "fresco"
    if age_hours <= 72:
        return "atencao"
    return "atrasado"


def status_badge(status: str):
    label, color, icon = STATUS_STYLE.get(status, STATUS_STYLE["sem_dado"])
    st.badge(label, icon=icon, color=color)


def worst_status(statuses: list[str]) -> str:
    if not statuses:
        return "sem_dado"
    return max(statuses, key=lambda s: STATUS_SEVERITY.get(s, 2))


def load_yaml(filename: str) -> dict:
    with open(HUB_DIR / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


@st.cache_resource
def get_writer_bq_client() -> bigquery.Client:
    """Client com credencial IMPERSONADA da writer SA (dataEditor so no dataset
    `core`). E o UNICO ponto de escrita do hub inteiro -- todo o resto do app
    usa get_bq_client() (ambient, read-only). So chamar isso de dentro da acao
    de commit do override, nunca em funcao cacheada/chamada automaticamente."""
    source_credentials, _ = google.auth.default()
    target_credentials = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=WRITER_SA_EMAIL,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        lifetime=300,
    )
    return bigquery.Client(project=PROJECT_ID, credentials=target_credentials)


@st.cache_resource
def get_staging_writer_bq_client() -> bigquery.Client:
    """Mesma credencial impersonada da writer SA, mas faturada/rodando jobs
    direto em `douglas-bq-staging` (nao em PROJECT_ID/adframework). Existe
    para as 3 escritas que vivem 100% em staging (stage_raw_historical_upload,
    commit_override, set_client_override_active) -- usar get_writer_bq_client()
    para elas exigiria conceder roles/bigquery.jobUser para a writer SA em
    PRODUCAO so pra rodar jobs contra tabelas de staging, o que viola o
    isolamento total de staging (decisao do Douglas, 2026-08-06). O dataEditor
    dataset-scoped em douglas-bq-staging (raw/stg/core) continua sendo o unico
    binding de escrita necessario; o jobUser correspondente tambem passa a ser
    escopado a douglas-bq-staging (ver hub/deploy.sh)."""
    source_credentials, _ = google.auth.default()
    target_credentials = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=WRITER_SA_EMAIL,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        lifetime=300,
    )
    return bigquery.Client(project=HISTORICAL_OVERRIDE_PROJECT_ID, credentials=target_credentials)


def dry_run_bytes(sql: str) -> int:
    client = get_bq_client()
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = client.query(sql, job_config=job_config)
    return job.total_bytes_processed


def read_uploaded_spreadsheet(uploaded_file) -> pd.DataFrame:
    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file)
    return pd.read_excel(uploaded_file)


def read_uploaded_spreadsheet_raw(uploaded_file) -> pd.DataFrame:
    """Le TODAS as colunas como STRING, sem inferencia de tipo do pandas --
    mesmo principio 'RAW = dump literal' de scripts/deploy/load_historical_raw.py
    (a contraparte CLI que fixa este mesmo contrato). Usada so pela landing RAW
    generica (nao pelo fluxo de override normalizado da Cora acima, que continua
    usando read_uploaded_spreadsheet com inferencia de tipo -- ali o schema alvo
    ja e conhecido e tipado)."""
    uploaded_file.seek(0)
    read_kwargs = {"dtype": str, "keep_default_na": False, "na_values": [""]}
    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file, **read_kwargs)
    return pd.read_excel(uploaded_file, **read_kwargs)


def build_override_dataframe(raw_df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Aplica o mapeamento de colunas (arquivo -> schema alvo) escolhido na UI.
    Colunas alvo sem mapeamento (ex. arquivo nao tem `investimento`) viram NULL."""
    out = pd.DataFrame()
    for field in OVERRIDE_TARGET_FIELDS:
        source_col = mapping.get(field)
        out[field] = raw_df[source_col] if source_col else None
    out["day"] = pd.to_datetime(out["day"]).dt.date
    for col in ["impressions", "clicks", "investimento"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def validate_override_scope(df: pd.DataFrame) -> list[str]:
    """Guarda-corpo: essa carga e fechada -- so Cora, so Jan-Jun/2026. Nunca deixar
    passar outro periodo/cliente por engano (nao existe campo de cliente na UI
    de proposito: o escopo inteiro so serve para Cora)."""
    errors = []
    out_of_range = df[(df["day"] < CORA_OVERRIDE_START) | (df["day"] > CORA_OVERRIDE_END)]
    if not out_of_range.empty:
        errors.append(
            f"{len(out_of_range)} linha(s) fora da janela permitida "
            f"({CORA_OVERRIDE_START} a {CORA_OVERRIDE_END}) -- este fluxo e exclusivo "
            "para o historico Jan-Jun/2026 da Cora."
        )
    if df["day"].isna().any():
        errors.append("Existem linhas com data invalida/vazia apos o mapeamento.")
    return errors


def commit_override(df: pd.DataFrame, source_file: str, notes: str) -> int:
    """Escreve stg.historical_overrides_delivery em douglas-bq-staging. Usa a
    writer SA impersonada, faturada direto em staging (get_staging_writer_bq_client)
    -- nunca em PROJECT_ID/adframework."""
    client = get_staging_writer_bq_client()
    load_df = df.copy()
    load_df["client_id"] = CORA_CLIENT_ID
    load_df["source_file"] = source_file
    load_df["loaded_by"] = "Douglas"
    load_df["loaded_at"] = datetime.now(timezone.utc)
    load_df["notes"] = notes
    job = client.load_table_from_dataframe(load_df, OVERRIDE_TABLE)
    job.result()
    return len(load_df)


@st.cache_data(ttl=300)
def load_client_options() -> pd.DataFrame:
    """Lista de clientes ativos para popular dropdowns do hub -- fonte unica
    core.dim_client (nunca lista hardcoded, mesmo padrao usado no resto do
    hub para client_id). So leitura, SA principal."""
    client = get_bq_client()
    query = f"""
    SELECT client_id, name
    FROM `{PROJECT_ID}.core.dim_client`
    WHERE status = 'active'
    ORDER BY name
    """
    return client.query(query).to_dataframe()


def stage_raw_historical_upload(raw_df: pd.DataFrame, client_id: str, source_filename: str) -> dict:
    """Landing RAW literal em douglas-bq-staging.raw -- contrato confirmado com o
    backend (repassado pelo orquestrador, 2026-08-06, ver docs/known_issues.md
    item S4): duas tabelas, `historical_uploads` (uma linha por linha do
    arquivo, `raw_row` como JSON-text STRING) e `historical_uploads_meta` (uma
    linha por upload, com column_names + row_count) -- ver RAW_UPLOADS_TABLE /
    RAW_UPLOADS_META_TABLE. Contrato validado contra raw/ddl/historical_uploads.sql
    + raw/ddl/historical_uploads_meta.sql + scripts/deploy/load_historical_raw.py
    (script CLI irmao, mesmo schema) -- todos entregues pelo backend em paralelo
    nesta mesma janela de trabalho.

    Escreve com a writer SA impersonada, faturada direto em douglas-bq-staging
    (get_staging_writer_bq_client) -- nunca em PROJECT_ID/adframework. IMPORTANTE:
    essa SA precisa de dataEditor em `douglas-bq-staging.raw` (ver WRITER_SA_EMAIL
    e hub/deploy.sh, bindings dataset-scoped em douglas-bq-staging). Se o binding
    ainda nao tiver sido aplicado, esta chamada deve falhar com erro de permissao
    -- tratado abaixo com uma mensagem clara em vez de deixar a excecao estourar
    na UI."""
    upload_id = str(uuid.uuid4())
    uploaded_at = datetime.now(timezone.utc)
    uploaded_by = "Douglas"

    meta_row = pd.DataFrame([{
        "upload_id": upload_id,
        "client_id": client_id,
        "source_filename": source_filename,
        "column_names": [str(c) for c in raw_df.columns],
        "row_count": len(raw_df),
        "uploaded_at": uploaded_at,
        "uploaded_by": uploaded_by,
    }])
    def _row_to_json(row: pd.Series) -> str:
        # NaN (celula vazia) nao serializa em JSON valido -- vira None/null,
        # mesmo tratamento do script CLI irmao (load_historical_raw.py).
        record = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        return json.dumps(record, ensure_ascii=False, default=str)

    rows_df = pd.DataFrame({
        "upload_id": upload_id,
        "client_id": client_id,
        "source_filename": source_filename,
        "row_number": range(1, len(raw_df) + 1),
        "raw_row": [_row_to_json(row) for _, row in raw_df.iterrows()],
        "uploaded_at": uploaded_at,
        "uploaded_by": uploaded_by,
    })

    try:
        client = get_staging_writer_bq_client()
        client.load_table_from_dataframe(rows_df, RAW_UPLOADS_TABLE).result()
        client.load_table_from_dataframe(meta_row, RAW_UPLOADS_META_TABLE).result()
    except Exception as exc:
        return {
            "staged": False,
            "reason": (
                f"Nao consegui gravar em `{RAW_UPLOADS_TABLE}` -- causa provavel: falta "
                f"binding de IAM (dataEditor) para `{WRITER_SA_EMAIL}` no dataset "
                f"`{RAW_LANDING_PROJECT_ID}.{RAW_LANDING_DATASET}`, ou as tabelas ainda nao "
                f"foram criadas la. Erro original: {exc}"
            ),
            "upload_id": upload_id,
            "would_be_table": RAW_UPLOADS_TABLE,
            "n_rows": len(raw_df),
            "columns": list(raw_df.columns),
        }

    return {
        "staged": True,
        "upload_id": upload_id,
        "would_be_table": RAW_UPLOADS_TABLE,
        "n_rows": len(raw_df),
        "columns": list(raw_df.columns),
    }


def _parse_json_field(value):
    """Normaliza um campo que pode vir do BQ como str JSON, dict ja parseado ou
    list -- pura, sem I/O. Usada para reidratar `raw_row` (STRING JSON-text) de
    historical_uploads de volta em dict Python para exibicao."""
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {"_raw": value}
    return value


def load_landed_historical_upload(upload_id: str) -> tuple[dict, pd.DataFrame]:
    """Le de volta o que pousou em douglas-bq-staging.raw para um upload_id --
    meta (nomes de coluna reais + row_count, direto de historical_uploads_meta)
    + amostra de ate 10 linhas parseadas de raw_row. Le com get_bq_client() (SA
    principal, read-only) -- se ela nao tiver leitura no projeto de staging
    ainda, a excecao propaga para quem chama tratar (mesmo padrao do resto do
    hub: nao mascarar erro de permissao/tabela ausente)."""
    client = get_bq_client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("upload_id", "STRING", upload_id)]
    )

    meta_df = client.query(
        f"""
        SELECT client_id, source_filename, column_names, row_count, uploaded_at, uploaded_by
        FROM `{RAW_UPLOADS_META_TABLE}`
        WHERE upload_id = @upload_id
        """,
        job_config=job_config,
    ).to_dataframe()

    sample_df = client.query(
        f"""
        SELECT row_number, raw_row
        FROM `{RAW_UPLOADS_TABLE}`
        WHERE upload_id = @upload_id
        ORDER BY row_number
        LIMIT 10
        """,
        job_config=job_config,
    ).to_dataframe()

    if not sample_df.empty:
        sample_df = pd.json_normalize(sample_df["raw_row"].map(_parse_json_field))

    meta = meta_df.iloc[0].to_dict() if not meta_df.empty else {}
    return meta, sample_df


@st.cache_data(ttl=120)
def load_historical_uploads_for_client(client_id: str) -> pd.DataFrame:
    """Lista de uploads ja pousados em historical_uploads_meta para um client_id --
    popula o dropdown da secao 'Comparar Snapshot: Planilha vs. Dado Real'. So
    cabecalho de cada upload (nao le historical_uploads inteira aqui). Le com
    get_bq_client() (SA principal, read-only), mesmo padrao de
    load_landed_historical_upload."""
    client = get_bq_client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("client_id", "STRING", client_id)]
    )
    query = f"""
    SELECT upload_id, source_filename, row_count, uploaded_at
    FROM `{RAW_UPLOADS_META_TABLE}`
    WHERE client_id = @client_id
    ORDER BY uploaded_at DESC
    """
    return client.query(query, job_config=job_config).to_dataframe()


def load_full_landed_historical_upload(upload_id: str) -> pd.DataFrame:
    """Le TODAS as linhas (nao so a amostra de 10 de load_landed_historical_upload)
    de historical_uploads para um upload_id -- usada so para inferir o range de
    datas da planilha crua (MIN/MAX precisam da planilha inteira, nao de uma
    amostra). Mesma leitura SA principal, mesmo parse de raw_row via
    _parse_json_field."""
    client = get_bq_client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("upload_id", "STRING", upload_id)]
    )
    df = client.query(
        f"""
        SELECT raw_row
        FROM `{RAW_UPLOADS_TABLE}`
        WHERE upload_id = @upload_id
        ORDER BY row_number
        """,
        job_config=job_config,
    ).to_dataframe()
    if df.empty:
        return pd.DataFrame()
    return pd.json_normalize(df["raw_row"].map(_parse_json_field))


# Pistas de nome de coluna para tentar inferir automaticamente qual coluna da
# planilha crua (ainda sem mapeamento) representa data -- so um palpite pra
# poupar digitacao manual, nunca a fonte de verdade (ver infer_date_range_from_raw).
DATE_COLUMN_NAME_HINTS = ("data", "date", "dia", "day")


def infer_date_range_from_raw(raw_df: pd.DataFrame) -> tuple:
    """Pura -- tenta achar, por nome de coluna, uma coluna de data na planilha
    crua (ainda nao normalizada/mapeada) e inferir o range MIN/MAX a partir
    dela. Exige pelo menos 80% das linhas da coluna candidata parseando como
    data para aceitar (evita inferir de uma coluna que so parece data por
    acaso). Retorna (min_date, max_date, nome_da_coluna) ou (None, None, None)
    se nao achar nada confiavel -- quem chama cai no fallback manual (range
    digitado pelo usuario)."""
    if raw_df is None or raw_df.empty:
        return None, None, None
    candidates = [c for c in raw_df.columns if any(hint in str(c).lower() for hint in DATE_COLUMN_NAME_HINTS)]
    for col in candidates:
        parsed = pd.to_datetime(raw_df[col], errors="coerce", dayfirst=True)
        if parsed.notna().mean() >= 0.8:
            return parsed.min().date(), parsed.max().date(), col
    return None, None, None


def load_gold_sample_for_range(client_id: str, start_day: date, end_day: date, limit: int = 15) -> pd.DataFrame:
    """Amostra de douglas-bq-staging.gold.fact_delivery pro client_id e range de
    datas informado -- SA principal (read-only), fully-qualified table name
    (mesmo padrao de load_landed_historical_upload -- nao precisa trocar de
    projeto no client, so qualificar a tabela). So leitura, sem nenhuma logica
    de comparacao/diff -- essa e so a coluna direita da tela lado a lado."""
    client = get_bq_client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
            bigquery.ScalarQueryParameter("start_day", "DATE", start_day),
            bigquery.ScalarQueryParameter("end_day", "DATE", end_day),
        ]
    )
    query = f"""
    SELECT day, platform, formato, goal_type, impressions, clicks, conversions
    FROM `{HISTORICAL_OVERRIDE_PROJECT_ID}.gold.fact_delivery`
    WHERE client_id = @client_id
      AND day BETWEEN @start_day AND @end_day
    ORDER BY day
    LIMIT {limit}
    """
    return client.query(query, job_config=job_config).to_dataframe()


def load_gold_coverage_for_client(client_id: str):
    """MIN/MAX day existente em douglas-bq-staging.gold.fact_delivery pro
    client_id, independente do range da planilha -- usada so para dar contexto
    quando a amostra do range da planilha vem vazia (dizer o que a plataforma
    real TEM, em vez de so mostrar uma tabela vazia sem explicacao)."""
    client = get_bq_client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("client_id", "STRING", client_id)]
    )
    query = f"""
    SELECT MIN(day) AS min_day, MAX(day) AS max_day
    FROM `{HISTORICAL_OVERRIDE_PROJECT_ID}.gold.fact_delivery`
    WHERE client_id = @client_id
    """
    df = client.query(query, job_config=job_config).to_dataframe()
    if df.empty or pd.isna(df.iloc[0]["min_day"]):
        return None, None
    return df.iloc[0]["min_day"], df.iloc[0]["max_day"]


@st.cache_data(ttl=60)
def load_override_delivery_summary() -> pd.DataFrame:
    """Um cliente por linha: quantas linhas e o range real (MIN/MAX day) de
    stg.historical_overrides_delivery (movida de core para stg em
    2026-08-06 -- dado normalizado pertence a STG) -- calculado AO VIVO,
    nunca digitado manualmente (decisao fechada 2026-08-05). So leitura, SA
    principal."""
    client = get_bq_client()
    query = f"""
    SELECT
      client_id,
      COUNT(*) AS n_linhas,
      MIN(day) AS min_day,
      MAX(day) AS max_day
    FROM `{OVERRIDE_TABLE}`
    GROUP BY client_id
    ORDER BY client_id
    """
    return client.query(query).to_dataframe()


@st.cache_data(ttl=60)
def load_override_active_config() -> pd.DataFrame:
    """Versao SCD2-vigente hoje (effective_to IS NULL) de
    core.client_reporting_source_config -- um cliente por linha com o estado
    atual do liga/desliga. NAO captura NotFound aqui de proposito -- a tabela
    e nova (backend constroi em paralelo) e pode ainda nao existir; quem chama
    trata esse caso explicitamente em vez de mascarar num df vazio sempre."""
    client = get_bq_client()
    query = f"""
    SELECT client_id, override_active, effective_from, reason, confirmed_by, confirmed_at
    FROM `{CLIENT_REPORTING_SOURCE_CONFIG_TABLE}`
    WHERE effective_to IS NULL
    """
    return client.query(query).to_dataframe()


def build_client_override_status(summary_df: pd.DataFrame, config_df: pd.DataFrame) -> pd.DataFrame:
    """Junta o range real (historical_overrides_delivery) com o estado vigente
    do liga/desliga (client_reporting_source_config). Pura -- sem I/O -- so
    para poder testar o merge independente do BQ. Cliente sem linha de config
    ainda (tabela nova / cliente nunca configurado) vira override_active=False."""
    merged = summary_df.merge(config_df, on="client_id", how="left")
    merged["override_active"] = merged["override_active"].fillna(False).astype(bool)
    return merged


def set_client_override_active(client_id: str, new_active: bool, reason: str) -> None:
    """Grava o novo estado do liga/desliga como uma linha SCD2 NOVA em
    core.client_reporting_source_config -- nunca UPDATE do valor em si: fecha
    effective_to da linha vigente (se existir) e insere uma linha nova com
    effective_from = hoje. Mesmo padrao SCD2 ja usado no resto do pipeline.
    Usa a writer SA impersonada, faturada direto em douglas-bq-staging
    (get_staging_writer_bq_client) -- CLIENT_REPORTING_SOURCE_CONFIG_TABLE vive
    em douglas-bq-staging.core, nao em PROJECT_ID/adframework."""
    client = get_staging_writer_bq_client()

    close_sql = f"""
        UPDATE `{CLIENT_REPORTING_SOURCE_CONFIG_TABLE}`
        SET effective_to = CURRENT_DATE()
        WHERE client_id = @client_id AND effective_to IS NULL
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("client_id", "STRING", client_id)]
    )
    client.query(close_sql, job_config=job_config).result()

    new_row = pd.DataFrame([{
        "client_id": client_id,
        "override_active": new_active,
        "effective_from": date.today(),
        "effective_to": None,
        "reason": reason,
        "confirmed_by": "Douglas",
        "confirmed_at": datetime.now(timezone.utc),
    }])
    job = client.load_table_from_dataframe(
        new_row,
        CLIENT_REPORTING_SOURCE_CONFIG_TABLE,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND"),
    )
    job.result()


def _parse_json_field(value):
    """Colunas JSON do BQ podem chegar como str (comum) ou ja como dict/list
    dependendo da versao do client -- normaliza para objeto Python em todos os casos."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


@st.cache_data(ttl=60)
def count_pending_proposals() -> int:
    """Contador leve (so COUNT, sem os campos JSON pesados) -- usado no farol da tela
    principal. A aba Propostas de Mudanca usa load_pending_proposals() pro detalhe completo."""
    client = get_bq_client()
    query = f"SELECT COUNT(*) AS n FROM `{PROPOSALS_TABLE}` WHERE status = 'pending'"
    return int(client.query(query).to_dataframe()["n"].iloc[0])


@st.cache_data(ttl=60)
def load_pending_proposals() -> pd.DataFrame:
    """core.change_proposals WHERE status='pending' -- fila generica de aprovacao.
    So leitura, usa a SA principal (read-only)."""
    client = get_bq_client()
    query = f"""
    SELECT
      proposal_id, target_dataset, target_table, operation,
      TO_JSON_STRING(key_fields) AS key_fields,
      TO_JSON_STRING(old_values) AS old_values,
      TO_JSON_STRING(new_values) AS new_values,
      source, status, detected_at, proposed_by, notes
    FROM `{PROPOSALS_TABLE}`
    WHERE status = 'pending'
    ORDER BY detected_at DESC
    """
    df = client.query(query).to_dataframe()
    for col in ["key_fields", "old_values", "new_values"]:
        df[col] = df[col].apply(_parse_json_field)
    return df


def is_ambiguous_proposal(new_values: dict) -> bool:
    """Chave ambigua: new_values traz `sheet_rows` (lista de linhas) em vez de um
    dict simples campo->valor. O hub nunca aprova esse tipo sozinho -- so rejeitar
    ou revisar fora do fluxo automatico."""
    return isinstance(new_values, dict) and "sheet_rows" in new_values


def approve_proposal(proposal_id: str, target_dataset: str, target_table: str,
                      key_fields: dict, new_values: dict) -> None:
    """UNICA acao de escrita fora do dataset `core`. Sempre INSERT (nunca
    UPDATE/DELETE) na tabela alvo, com raw_ingested_at novo -- a linha antiga
    (se existir) fica intacta como historico nativo, append-only. So os campos
    presentes em key_fields+new_values sao preenchidos; o resto fica NULL nessa
    nova linha. Usa a writer SA impersonada -- nunca a SA principal read-only."""
    client = get_writer_bq_client()
    row = {**key_fields, **new_values, "raw_ingested_at": datetime.now(timezone.utc)}
    load_df = pd.DataFrame([row])
    job = client.load_table_from_dataframe(
        load_df,
        f"{PROJECT_ID}.{target_dataset}.{target_table}",
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND"),
    )
    job.result()

    update_sql = f"""
        UPDATE `{PROPOSALS_TABLE}`
        SET status = 'applied', resolved_by = 'Douglas',
            resolved_at = CURRENT_TIMESTAMP(), applied_at = CURRENT_TIMESTAMP()
        WHERE proposal_id = @proposal_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("proposal_id", "STRING", proposal_id)]
    )
    client.query(update_sql, job_config=job_config).result()


def reject_proposal(proposal_id: str) -> None:
    """So marca status='rejected' -- nunca escreve na tabela alvo."""
    client = get_writer_bq_client()
    update_sql = f"""
        UPDATE `{PROPOSALS_TABLE}`
        SET status = 'rejected', resolved_by = 'Douglas', resolved_at = CURRENT_TIMESTAMP()
        WHERE proposal_id = @proposal_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("proposal_id", "STRING", proposal_id)]
    )
    client.query(update_sql, job_config=job_config).result()


@st.cache_data(ttl=180)
def load_business_rules() -> pd.DataFrame:
    """Le TODAS as linhas (vigentes + historico fechado) de core.client_business_rules
    em douglas-bq-staging -- staging, fase de teste, tabela ainda NAO existe em
    producao (ver comentario de BUSINESS_RULES_TABLE acima). Volume esperado e
    pequeno (config de regra de negocio, nao dado de evento) -- agrupamento
    vigente/historico e feito em pandas na UI, nao em SQL. So leitura, SA principal."""
    client = get_bq_client()
    query = f"""
    SELECT
      rule_id, rule_type, client_id, TO_JSON_STRING(rule_params) AS rule_params_json,
      confirmed_at, confirmed_by, notes, effective_from, effective_to, status
    FROM `{BUSINESS_RULES_TABLE}`
    ORDER BY rule_type, client_id, effective_from DESC
    """
    df = client.query(query).to_dataframe()
    df["rule_params"] = df["rule_params_json"].apply(_parse_json_field)
    return df


@st.cache_data(ttl=300)
def load_business_rules_client_names() -> pd.DataFrame:
    """client_id -> name para os cards de override, lido do dim_client de
    STAGING (mesmo projeto de BUSINESS_RULES_TABLE, nao PROJECT_ID/producao) --
    client_business_rules so existe em staging por enquanto, entao o lookup
    precisa vir do dim_client que tem paridade com esses client_id (incluindo os
    fake de teste, que nao existem em nenhum dos dois de verdade)."""
    client = get_bq_client()
    query = f"SELECT client_id, name FROM `{BUSINESS_RULES_DIM_CLIENT_TABLE}`"
    return client.query(query).to_dataframe()


@st.cache_data(ttl=300)
def load_pacing_for_simulation(client_id: str, strategies: tuple[str, ...]) -> pd.DataFrame:
    """Dado real de entrega (gold.fact_pacing, PRODUCAO) para o simulador mock da aba
    Regras de Negocio -- so leitura, SA principal, mesmo padrao das demais queries do
    hub. `strategies` e tuple (nao list) para ser hashable e caber no cache_data.
    O calculo do teto em si acontece em pandas na UI, nunca aqui -- esta funcao so
    busca o dado bruto (planned vs realized por dia/formato)."""
    if not strategies:
        return pd.DataFrame()
    client = get_bq_client()
    query = f"""
    SELECT day, formato, platform, planned_impressions_daily, realized_impressions
    FROM `{PROJECT_ID}.gold.fact_pacing`
    WHERE client_id = @client_id AND UPPER(formato) IN UNNEST(@strategies)
    ORDER BY day
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
        bigquery.ArrayQueryParameter("strategies", "STRING", [s.upper() for s in strategies]),
    ])
    return client.query(query, job_config=job_config).to_dataframe()


def business_rule_exists_active(rule_type: str, client_id: str | None) -> bool:
    """SELECT antes de INSERT (guarda-corpo pedido explicitamente) -- confirma que
    nao ha versao vigente (effective_to IS NULL) para este (rule_type, client_id)
    antes de deixar criar uma regra nova. So leitura, SA principal -- nao precisa
    da writer so para checar. client_id NULL usa `IS NULL` (comparacao `= NULL`
    nunca e verdadeira em SQL, por isso o branch separado)."""
    client = get_bq_client()
    if client_id is None:
        query = f"""
        SELECT COUNT(*) AS n FROM `{BUSINESS_RULES_TABLE}`
        WHERE rule_type = @rule_type AND client_id IS NULL AND effective_to IS NULL
        """
        params = [bigquery.ScalarQueryParameter("rule_type", "STRING", rule_type)]
    else:
        query = f"""
        SELECT COUNT(*) AS n FROM `{BUSINESS_RULES_TABLE}`
        WHERE rule_type = @rule_type AND client_id = @client_id AND effective_to IS NULL
        """
        params = [
            bigquery.ScalarQueryParameter("rule_type", "STRING", rule_type),
            bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
        ]
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    return int(client.query(query, job_config=job_config).to_dataframe()["n"].iloc[0]) > 0


def create_business_rule(rule_type: str, client_id: str | None, rule_params: dict,
                          confirmed_by: str, notes: str, effective_from: date) -> None:
    """INSERT simples de uma regra nova -- so chamado depois que
    business_rule_exists_active ja confirmou que nao ha versao vigente para esse
    (rule_type, client_id). Nao implementa 'nova versao substituindo uma
    existente' (fechar a antiga + abrir a nova) -- simplificacao explicita desta
    entrega, sinalizada no relato; ver procedimento completo em
    core/ddl/client_business_rules.sql. rule_id e status ficam fora da lista de
    colunas para os DEFAULTs do BQ (GENERATE_UUID() / 'active') preencherem
    sozinhos, como o DDL manda. Escreve com a writer SA impersonada, faturada em
    staging (get_staging_writer_bq_client) -- BUSINESS_RULES_TABLE ja aponta pra
    douglas-bq-staging."""
    client = get_staging_writer_bq_client()
    insert_sql = f"""
        INSERT INTO `{BUSINESS_RULES_TABLE}`
          (rule_type, client_id, rule_params, confirmed_at, confirmed_by, notes, effective_from, effective_to)
        VALUES (
          @rule_type, @client_id, PARSE_JSON(@rule_params), CURRENT_DATE(), @confirmed_by,
          @notes, @effective_from, NULL
        )
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("rule_type", "STRING", rule_type),
        bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
        bigquery.ScalarQueryParameter("rule_params", "STRING", json.dumps(rule_params)),
        bigquery.ScalarQueryParameter("confirmed_by", "STRING", confirmed_by),
        bigquery.ScalarQueryParameter("notes", "STRING", notes),
        bigquery.ScalarQueryParameter("effective_from", "DATE", effective_from),
    ])
    client.query(insert_sql, job_config=job_config).result()


def pause_business_rule(rule_id: str, notes: str) -> None:
    """Fecha a linha vigente SEM substituto (status='paused'), a partir de hoje --
    ver procedimento de PAUSA documentado em core/ddl/client_business_rules.sql.
    O WHERE inclui `effective_to IS NULL` como guarda-corpo -- nunca reabre/toca
    uma linha ja fechada, mesmo que o rule_id passado seja de uma linha antiga.
    Escreve com a writer SA impersonada, faturada em staging."""
    client = get_staging_writer_bq_client()
    update_sql = f"""
        UPDATE `{BUSINESS_RULES_TABLE}`
        SET effective_to = CURRENT_DATE(), status = 'paused', notes = @notes
        WHERE rule_id = @rule_id AND effective_to IS NULL
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("rule_id", "STRING", rule_id),
        bigquery.ScalarQueryParameter("notes", "STRING", notes),
    ])
    client.query(update_sql, job_config=job_config).result()


def summarize_rule_params(rule_type: str, params: dict) -> str:
    """Resumo legivel de rule_params para exibicao em card (ex: 'Teto 20% --
    Native, Push') -- pura, sem I/O. Conhece o formato de qualquer rule_type que
    comece com 'impression_cap_pct' (cobre tambem os rule_type de teste reais em
    staging, ex: impression_cap_pct_test) explicitamente; qualquer rule_type sem
    esse formato cai no fallback generico (par chave=valor), nunca quebra a UI."""
    params = params or {}
    if (rule_type or "").startswith("impression_cap_pct") and "threshold_pct" in params:
        strategies = params.get("strategies") or []
        strategies_label = ", ".join(s.title() for s in strategies) if strategies else "todas as estrategias"
        return f"Teto {params['threshold_pct']}% -- {strategies_label}"
    if not params:
        return "(sem parametros)"
    return ", ".join(f"{k}={v}" for k, v in params.items())


def history_status_badge(status: str) -> None:
    label, color = HISTORY_STATUS_STYLE.get(status, (status or "desconhecido", "gray"))
    st.badge(label, color=color)


def _render_business_rule_card(rule_type: str, scope_label: str, is_general: bool,
                                current_row, history_df: pd.DataFrame) -> None:
    """Um card por escopo (Geral ou 1 cliente) dentro de um rule_type: badge de
    escopo + resumo legivel da versao vigente + expander de historico. Nao pura
    (chama st.*) -- so agrupa a repeticao de UI entre a regra geral e cada
    override de cliente. `current_row` pode ser None quando o escopo so tem
    historico fechado (ex: override pausado sem substituto, sem nenhuma versao
    vigente hoje) -- a listagem ainda mostra o card, so sem o resumo vigente,
    para nunca esconder um historico so porque nao ha versao ativa agora."""
    with st.container(border=True):
        c1, c2 = st.columns([1, 4])
        with c1:
            if is_general:
                st.badge("Geral", icon=":material/public:", color="blue")
            else:
                st.badge(scope_label, icon=":material/person:", color="gray")
        with c2:
            if current_row is not None:
                st.markdown(f"**{summarize_rule_params(rule_type, current_row['rule_params'])}**")
                st.caption(
                    f"vigente desde {current_row['effective_from']} -- confirmado por "
                    f"{current_row['confirmed_by']} em {current_row['confirmed_at']}"
                )
                if current_row.get("notes"):
                    st.caption(f"nota: {current_row['notes']}")

                rule_id = current_row["rule_id"]
                pause_open_key = f"pause_open_{rule_id}"
                if st.button("Pausar", key=f"pause_btn_{rule_id}"):
                    st.session_state[pause_open_key] = True

                if st.session_state.get(pause_open_key):
                    with st.container(border=True):
                        pause_notes = st.text_area(
                            "Motivo da pausa (obrigatorio)", key=f"pause_notes_{rule_id}",
                        )
                        pause_confirm = st.checkbox(
                            "Confirmo que quero pausar esta regra a partir de hoje",
                            key=f"pause_confirm_{rule_id}",
                        )
                        commit_col, cancel_col = st.columns([1, 1])
                        with commit_col:
                            if st.button(
                                "Confirmar pausa", key=f"pause_commit_{rule_id}",
                                disabled=not (pause_notes.strip() and pause_confirm),
                            ):
                                try:
                                    with st.spinner("Pausando regra..."):
                                        pause_business_rule(rule_id, pause_notes.strip())
                                    st.success("Regra pausada.")
                                    load_business_rules.clear()
                                    st.session_state[pause_open_key] = False
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Erro ao pausar: {exc}")
                        with cancel_col:
                            if st.button("Cancelar", key=f"pause_cancel_{rule_id}"):
                                st.session_state[pause_open_key] = False
                                st.rerun()
            else:
                st.badge("sem versao vigente -- pausada", icon=":material/pause_circle:", color="orange")

        if not history_df.empty:
            with st.expander(f"Ver historico ({len(history_df)} versao(oes))"):
                header = st.columns([3, 2.5, 1.3])
                for h, txt in zip(header, ["Resumo / vigencia", "Confirmado por / notas", "Status"]):
                    h.markdown(f"<span style='color:gray;font-size:0.8em'>{txt}</span>", unsafe_allow_html=True)
                for _, h in history_df.iterrows():
                    hc1, hc2, hc3 = st.columns([3, 2.5, 1.3])
                    with hc1:
                        st.write(summarize_rule_params(rule_type, h["rule_params"]))
                        st.caption(f"{h['effective_from']} a {h['effective_to']}")
                    with hc2:
                        st.caption(f"{h['confirmed_by']} -- {h['notes'] or 'sem notas'}")
                    with hc3:
                        history_status_badge(h["status"])


def check_password() -> bool:
    """Gate simples por senha compartilhada, so ativo quando HUB_PASSWORD esta setada
    (ou seja, so em Cloud Run -- rodando local ninguem mais tem acesso, entao nao pede senha)."""
    if not HUB_PASSWORD:
        return True
    if st.session_state.get("authenticated"):
        return True
    st.title("AdFramework Data Hub")
    pwd = st.text_input("Senha", type="password")
    if pwd:
        if pwd == HUB_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Senha incorreta")
    return False


if not check_password():
    st.stop()

st.title("AdFramework Data Hub")
st.caption(
    "Painel do pipeline BQ (projeto `adframework`). As abas de leitura nao disparam "
    "nada. Propostas de Mudanca e Overrides Historicos sao as UNICAS abas que escrevem, "
    "sempre via a writer SA impersonada (nunca a SA principal) -- ver hub/README.md."
)

# ─────────────────────────────────────────────────────────────────────────
# Farol permanente -- visivel ao abrir o hub, sem clicar em nenhuma aba.
# Reusa as mesmas funcoes/queries das abas de detalhe (nao duplica logica):
# saude do pipeline (Visao Geral BQ), fila de propostas (Propostas de Mudanca)
# e custo do mes corrente (Custos). Notion fica de fora por decisao do Douglas.
# ─────────────────────────────────────────────────────────────────────────
with st.expander(":material/visibility_off: Farol operacional (saude, propostas, custo)", expanded=False):
    with st.spinner("Carregando farol..."):
        _farol_meta = load_table_metadata()
        _pipeline_status = worst_status(_farol_meta["freshness"].tolist()) if not _farol_meta.empty else "sem_dado"
        _pending_count = count_pending_proposals()
        _month_gross, _month_net = load_cost_current_month()

    farol1, farol2, farol3 = st.columns(3)
    with farol1:
        with st.container(border=True):
            st.markdown("**Saude do pipeline**")
            status_badge(_pipeline_status)
            st.caption("pior status entre todas as camadas -- detalhe na aba Visao Geral BQ")
    with farol2:
        with st.container(border=True):
            st.markdown("**Propostas de mudanca pendentes**")
            st.metric("pendentes", _pending_count, label_visibility="collapsed")
            st.caption("fila vazia" if not _pending_count else "revisar na aba Propostas de Mudanca")
    with farol3:
        with st.container(border=True):
            st.markdown(f"**Custo do mes -- {date.today().strftime('%m/%Y')}**")
            st.metric("gross", f"US$ {_month_gross:,.2f}", label_visibility="collapsed")
            st.caption(f"net US$ {_month_net:,.2f} -- detalhe na aba Custos")

st.divider()

tab_freshness, tab_jobs, tab_powerbi, tab_costs, tab_browser, tab_query, tab_proposals, tab_overrides, tab_business_rules = st.tabs([
    ":material/database: Visao Geral BQ",
    ":material/sync: Status dos Jobs",
    ":material/bar_chart: Power BI em Construcao",
    ":material/payments: Custos",
    ":material/table_view: Navegador de Tabelas",
    ":material/terminal: Query Runner",
    ":material/fact_check: Propostas de Mudanca",
    ":material/history: Ajustes de Dados Historicos",
    ":material/gavel: Regras de Negocio",
])

# ─────────────────────────────────────────────────────────────────────────
# Aba 1 -- Visao Geral BQ: cards por camada, na ordem do pipeline
# ─────────────────────────────────────────────────────────────────────────
with tab_freshness:
    with st.spinner("Consultando __TABLES__ (metadado, sem custo de bytes)..."):
        df = load_table_metadata()

    st.subheader("Camadas do pipeline")
    st.caption("RAW -> STG -> CORE -> MARTS -> SHARE -> GOLD. Cada card resume uma camada; clique para ver o detalhe.")

    summary_cols = st.columns(len(LAYERS))
    layer_counts = {}
    for col, layer in zip(summary_cols, LAYERS):
        subset = df[df["dataset"] == layer["id"]]
        layer_counts[layer["id"]] = subset
        with col:
            with st.container(border=True):
                st.markdown(f"**{layer['label']}**")
                st.metric("Tabelas", len(subset), label_visibility="collapsed")
                if subset.empty:
                    st.badge("vazio", icon=":material/help:", color="gray")
                else:
                    status_badge(worst_status(subset["freshness"].tolist()))

    st.divider()

    for layer in LAYERS:
        subset = layer_counts[layer["id"]]
        if subset.empty:
            continue
        n_issues = (~subset["freshness"].isin(["fresco", "view"])).sum()
        title = f"{layer['icon']} **{layer['label']}** -- {len(subset)} tabelas"
        if n_issues:
            title += f" · {n_issues} para revisar"
        with st.expander(title, expanded=(worst_status(subset["freshness"].tolist()) in ("atrasado", "sem_dado"))):
            st.caption(layer["desc"])
            header = st.columns([3, 1, 1, 1, 2, 1.5])
            for h, txt in zip(header, ["Tabela", "Tipo", "Linhas", "MB", "Ultima atualizacao", "Status"]):
                h.markdown(f"<span style='color:gray;font-size:0.8em'>{txt}</span>", unsafe_allow_html=True)
            for _, row in subset.iterrows():
                c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 1, 1, 2, 1.5])
                c1.code(row["tabela"], language=None)
                c2.write(row["tipo"])
                c3.write(f"{row['linhas']:,}" if row["tipo"] != "view" else "-")
                c4.write(f"{row['tamanho_mb']:,}" if row["tipo"] != "view" else "-")
                c5.write(row["ultima_modificacao"].strftime("%d/%m/%Y %H:%M") if pd.notna(row["ultima_modificacao"]) else "-")
                with c6:
                    status_badge(row["freshness"])

    st.caption("`view`s sempre mostram 0 linhas/0 MB (nao armazenam dados) -- freshness delas reflete a definicao, nao os dados.")

# ─────────────────────────────────────────────────────────────────────────
# Aba 2 -- Status dos Jobs: cards por job de ingestao
# ─────────────────────────────────────────────────────────────────────────
with tab_jobs:
    st.subheader("Jobs de ingestao diaria")
    st.caption("Mapa mantido manualmente em `jobs_config.yaml`. Cruza com o freshness real da tabela associada.")
    jobs_cfg = load_yaml("jobs_config.yaml")["jobs"]
    meta = load_table_metadata()

    for job in jobs_cfg:
        dataset, table = job["table"].split(".")
        match = meta[(meta["dataset"] == dataset) & (meta["tabela"] == table)]
        if match.empty:
            status, last_mod = "tabela_nao_encontrada", None
        else:
            status, last_mod = match["freshness"].iloc[0], match["ultima_modificacao"].iloc[0]

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 1.5, 2, 1.5])
            with c1:
                st.markdown(f"**{job['label']}**")
                st.caption(f"`{job['table']}`")
            with c2:
                st.write(job["schedule"])
            with c3:
                st.write(last_mod.strftime("%d/%m/%Y %H:%M") if pd.notna(last_mod) else "sem dado ainda")
            with c4:
                status_badge(status)

# ─────────────────────────────────────────────────────────────────────────
# Aba 3 -- Power BI em construcao: tracker manual
# ─────────────────────────────────────────────────────────────────────────
with tab_powerbi:
    st.subheader("Power BI em desenvolvimento")
    st.caption("Tracker manual -- nao conecta na API do Power BI. Editar `powerbi_status.yaml` para atualizar.")
    dashboards = load_yaml("powerbi_status.yaml")["dashboards"]

    for dash in dashboards:
        label, color = POWERBI_STATUS_STYLE.get(dash["status"], ("desconhecido", "gray"))
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1.5, 2])
            with c1:
                st.markdown(f"**{dash['nome']}**")
                st.caption(dash.get("notas", ""))
            with c2:
                st.badge(label, color=color)
            with c3:
                st.write(f"{dash['owner']} · atualizado {dash['ultima_atualizacao']}")

# ─────────────────────────────────────────────────────────────────────────
# Aba 4 -- Custos: dado real do billing export (finops_billing), separado por dono
# ─────────────────────────────────────────────────────────────────────────
with tab_costs:
    st.subheader("Custo real do projeto (ultimos 30 dias)")
    st.caption(
        "Dado real do billing export da GCP (`finops_billing`, leitura apenas). "
        "Gross = preco de lista; Net = o que realmente sai do bolso depois de creditos/descontos."
    )

    with st.spinner("Consultando finops_billing..."):
        cloud_run_df = load_cloud_run_costs(days=30)
        min_instance_df = load_min_instance_costs(days=30)
        service_df = load_cost_by_service(days=30)
        project_df = load_cost_by_project(days=30)
        jobs_df = load_bq_query_volume(days=30)
        storage_api_df = load_bq_storage_via_api()

    gross_total = service_df["gross_30d"].sum() if not service_df.empty else 0
    net_total = service_df["net_30d"].sum() if not service_df.empty else 0
    douglas_gross = cloud_run_df.loc[cloud_run_df["owner"] == "Douglas", "gross_30d"].sum() if not cloud_run_df.empty else 0
    shiro_gross = cloud_run_df.loc[cloud_run_df["owner"] == "Shiro", "gross_30d"].sum() if not cloud_run_df.empty else 0

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        with st.container(border=True):
            st.markdown("**Total (gross)**")
            st.metric("30 dias", f"US$ {gross_total:,.2f}", label_visibility="collapsed")
            st.caption(f"US$ {gross_total/30:,.2f}/dia · preco de lista")
    with m2:
        with st.container(border=True):
            st.markdown("**Total (net)**")
            st.metric("30 dias", f"US$ {net_total:,.2f}", label_visibility="collapsed")
            st.caption(f"US$ {net_total/30:,.2f}/dia · o que sai do bolso de fato")
    with m3:
        with st.container(border=True):
            st.markdown("**Cloud Run -- seu (Douglas)**")
            st.metric("gross 30d", f"US$ {douglas_gross:,.2f}", label_visibility="collapsed")
            st.caption("adframework-etl (pipeline)")
    with m4:
        with st.container(border=True):
            st.markdown("**Cloud Run -- Shiro**")
            st.metric("gross 30d", f"US$ {shiro_gross:,.2f}", label_visibility="collapsed")
            st.caption("aat-console, advanced-adtracking, admin-ui")

    if not min_instance_df.empty:
        st.warning(
            f":material/warning: **{len(min_instance_df)} servico(s) com custo de Min Instance** "
            "(instancia sempre ligada mesmo sem trafego) -- normalmente o maior gasto oculto de Cloud Run.",
            icon=":material/warning:",
        )
        st.dataframe(min_instance_df.round(2), use_container_width=True, hide_index=True)
    else:
        st.badge("nenhum min-instance gerando custo detectado", icon=":material/check_circle:", color="green")

    st.divider()

    col_run, col_svc = st.columns(2)
    with col_run:
        st.markdown("**Cloud Run por servico -- de quem e**")
        if not cloud_run_df.empty:
            display = cloud_run_df.copy()
            display["gross_30d"] = display["gross_30d"].round(2)
            display["net_30d"] = display["net_30d"].round(2)
            st.dataframe(display[["service", "owner", "gross_30d", "net_30d"]], use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados de Cloud Run no periodo.")
    with col_svc:
        st.markdown("**Custo total por servico GCP**")
        if not service_df.empty:
            display = service_df.copy()
            display["gross_30d"] = display["gross_30d"].round(2)
            display["net_30d"] = display["net_30d"].round(2)
            st.dataframe(display, use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados de custo por servico no periodo.")

    st.markdown("**Projetos cobrados nessa conta de faturamento**")
    st.caption("Sanidade: confirma que so `adframework` (e eventualmente `nwd-aat`) aparecem aqui -- se surgir outro projeto, vale investigar.")
    if not project_df.empty:
        display = project_df.copy()
        display["gross_30d"] = display["gross_30d"].round(2)
        display["net_30d"] = display["net_30d"].round(2)
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("BigQuery -- a parte que voce controla direto")

    total_storage_gb = storage_api_df.loc[storage_api_df["tipo"] == "TABLE", "gb"].sum() if not storage_api_df.empty else 0
    total_tb_processed = jobs_df["tb_processed"].sum() if not jobs_df.empty else 0

    fm1, fm2 = st.columns(2)
    with fm1:
        with st.container(border=True):
            st.markdown("**Storage BQ**")
            st.metric("GB usados", f"{total_storage_gb:,.2f} / {BQ_FREE_STORAGE_GB} GB gratis", label_visibility="collapsed")
            if total_storage_gb < BQ_FREE_STORAGE_GB:
                st.badge("dentro do free tier", icon=":material/check_circle:", color="green")
            else:
                st.badge("acima do free tier", icon=":material/warning:", color="orange")
    with fm2:
        with st.container(border=True):
            st.markdown("**Queries BQ (30 dias)**")
            st.metric("TB processados", f"{total_tb_processed:.4f} / {BQ_FREE_TIB_PER_MONTH} TB gratis/mes", label_visibility="collapsed")
            if total_tb_processed < BQ_FREE_TIB_PER_MONTH:
                st.badge("dentro do free tier", icon=":material/check_circle:", color="green")
            else:
                st.badge("acima do free tier", icon=":material/warning:", color="orange")

    st.markdown("**Volume de queries por usuario/service account**")
    if not jobs_df.empty:
        display = jobs_df.copy()
        st.dataframe(display[["user", "owner", "n_queries", "tb_processed", "tb_billed"]], use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma query registrada nos ultimos 30 dias.")

    st.caption(
        "Carga de dados (LOAD jobs dos ETLs) e gratis no BigQuery -- so QUERY (leitura/processamento) e armazenamento acima do free tier geram custo. "
        "Storage via API (`bq.get_table`), nao via INFORMATION_SCHEMA -- evita erro de location. Views sempre mostram 0 GB, e normal."
    )

# ─────────────────────────────────────────────────────────────────────────
# Aba 5 -- Navegador de Tabelas: schema + preview, so leitura
# ─────────────────────────────────────────────────────────────────────────
with tab_browser:
    st.subheader("Navegador de Tabelas")
    st.caption("Schema e preview de qualquer tabela/view das camadas do pipeline. Read-only.")

    meta_df = load_table_metadata()
    ds_choice = st.selectbox("Dataset", DATASETS, key="browser_dataset")
    tables_in_ds = sorted(meta_df.loc[meta_df["dataset"] == ds_choice, "tabela"].tolist())
    if not tables_in_ds:
        st.info("Nenhuma tabela encontrada nesse dataset.")
    else:
        table_choice = st.selectbox("Tabela", tables_in_ds, key="browser_table")
        client = get_bq_client()
        table_ref = client.get_table(f"{PROJECT_ID}.{ds_choice}.{table_choice}")

        row_meta = meta_df[(meta_df["dataset"] == ds_choice) & (meta_df["tabela"] == table_choice)].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Tipo", row_meta["tipo"])
        c2.metric("Linhas", f"{row_meta['linhas']:,}" if row_meta["tipo"] != "view" else "-")
        c3.metric("Tamanho (MB)", f"{row_meta['tamanho_mb']:,}" if row_meta["tipo"] != "view" else "-")

        st.markdown("**Schema**")
        schema_rows = [
            {"coluna": f.name, "tipo": f.field_type, "modo": f.mode, "descricao": f.description or ""}
            for f in table_ref.schema
        ]
        st.dataframe(pd.DataFrame(schema_rows), use_container_width=True, hide_index=True)

        st.markdown("**Preview (50 linhas)**")
        if st.button("Carregar preview", key="browser_preview_btn"):
            preview_sql = f"SELECT * FROM `{PROJECT_ID}.{ds_choice}.{table_choice}` LIMIT 50"
            with st.spinner("Consultando..."):
                preview_df = client.query(preview_sql).to_dataframe()
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────
# Aba 6 -- Query Runner: SQL livre, protegido por IAM read-only (nao por
# validacao de texto -- a SA do hub nao tem permissao de escrita em nada).
# ─────────────────────────────────────────────────────────────────────────
with tab_query:
    st.subheader("Query Runner")
    st.caption(
        "SQL livre contra o projeto `adframework`. Protegido por permissao, nao por "
        "validacao de texto: a service account deste hub so tem `bigquery.dataViewer` -- "
        "qualquer INSERT/UPDATE/DELETE/DROP falha por falta de acesso, nao e bloqueado no app."
    )

    sql_text = st.text_area(
        "SQL", height=160, placeholder="SELECT * FROM gold.fact_delivery LIMIT 10",
        key="query_runner_sql",
    )

    DRY_RUN_WARN_BYTES = 1024 ** 3  # 1 GB

    if st.button("Rodar", key="query_runner_run_btn", disabled=not sql_text.strip()):
        try:
            with st.spinner("Estimando custo (dry run)..."):
                estimated_bytes = dry_run_bytes(sql_text)
            estimated_gb = estimated_bytes / (1024 ** 3)
            st.caption(f"Estimativa: {estimated_gb:.4f} GB processados.")

            proceed = True
            if estimated_bytes > DRY_RUN_WARN_BYTES:
                proceed = st.checkbox(
                    f"Essa query processa {estimated_gb:.2f} GB (> 1 GB) -- confirmar execucao mesmo assim",
                    key="query_runner_confirm_big",
                )

            if proceed:
                with st.spinner("Rodando..."):
                    result_df = get_bq_client().query(sql_text).to_dataframe()
                st.success(f"{len(result_df)} linha(s) retornada(s).")
                st.dataframe(result_df, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Erro ao rodar a query: {exc}")

# ─────────────────────────────────────────────────────────────────────────
# Aba 7 -- Propostas de Mudanca: fila generica de aprovacao humana sobre
# core.change_proposals. Hoje so source='siprocal_diff' (reconciliacao
# incremental de raw.sp_delivery), mas a tabela e generica de proposito --
# esta aba tambem, para servir qualquer fonte futura sem redesenho.
# ─────────────────────────────────────────────────────────────────────────
with tab_proposals:
    st.subheader("Propostas de Mudanca")
    st.caption(
        "Fila generica de propostas pendentes em `core.change_proposals`. Aprovar sempre "
        "gera um INSERT na tabela alvo (nunca UPDATE/DELETE) -- o historico antigo nunca "
        "e apagado, so ganha uma linha nova com `raw_ingested_at` mais recente."
    )

    proposals_df = load_pending_proposals()

    if proposals_df.empty:
        st.badge("nenhuma proposta pendente", icon=":material/check_circle:", color="green")
    else:
        st.caption(f"{len(proposals_df)} proposta(s) pendente(s).")
        for _, prop in proposals_df.iterrows():
            key_fields = prop["key_fields"] or {}
            old_values = prop["old_values"] or {}
            new_values = prop["new_values"] or {}
            ambiguous = is_ambiguous_proposal(new_values)

            key_desc = " / ".join(f"{k}={v}" for k, v in key_fields.items())
            title = (
                f"CHAVE AMBIGUA -- `{prop['target_dataset']}.{prop['target_table']}`"
                if ambiguous
                else f"`{prop['target_dataset']}.{prop['target_table']}` -- {key_desc}"
            )

            with st.container(border=True):
                c1, c2 = st.columns([4, 1.3])
                with c1:
                    st.markdown(f"**{title}**")
                    st.caption(
                        f"fonte: `{prop['source']}` -- detectado "
                        f"{prop['detected_at'].strftime('%d/%m/%Y %H:%M') if pd.notna(prop['detected_at']) else '-'}"
                    )
                with c2:
                    st.badge(prop["operation"], color="blue")

                if prop["notes"]:
                    st.info(prop["notes"], icon=":material/info:")

                if ambiguous:
                    col_old, col_new = st.columns(2)
                    with col_old:
                        st.markdown("**Linhas ja no BQ**")
                        st.dataframe(
                            pd.DataFrame(old_values.get("bq_rows", [])),
                            use_container_width=True, hide_index=True,
                        )
                    with col_new:
                        st.markdown("**Linhas na planilha**")
                        st.dataframe(
                            pd.DataFrame(new_values.get("sheet_rows", [])),
                            use_container_width=True, hide_index=True,
                        )
                    st.warning(
                        "Chave ambigua -- o hub nao insere dado sozinho nesse caso. So da pra "
                        "Rejeitar por aqui; qualquer correcao precisa de revisao manual fora do fluxo automatico.",
                        icon=":material/warning:",
                    )
                else:
                    st.markdown("**Chave:** " + ", ".join(f"`{k}`={v}" for k, v in key_fields.items()))
                    col_old, col_new = st.columns(2)
                    with col_old:
                        st.markdown("**Valor atual (BQ)**")
                        for k, v in old_values.items():
                            st.write(f"`{k}`: {v}")
                    with col_new:
                        st.markdown("**Valor novo (planilha)**")
                        for k, v in new_values.items():
                            marker = " 🔴" if old_values.get(k) != v else ""
                            st.write(f"`{k}`: {v}{marker}")

                confirmed = False
                if not ambiguous:
                    confirmed = st.checkbox(
                        "Confirmo que revisei o valor atual vs o novo acima e aprovo esta insercao",
                        key=f"proposal_confirm_{prop['proposal_id']}",
                    )

                b1, b2, _ = st.columns([1, 1, 4])
                with b1:
                    if st.button(
                        "Aprovar", key=f"proposal_approve_{prop['proposal_id']}",
                        disabled=ambiguous or not confirmed,
                    ):
                        try:
                            with st.spinner("Inserindo na tabela alvo (writer SA impersonada)..."):
                                approve_proposal(
                                    prop["proposal_id"], prop["target_dataset"], prop["target_table"],
                                    key_fields, new_values,
                                )
                            st.success("Aprovado -- linha inserida e proposta marcada como `applied`.")
                            load_pending_proposals.clear()
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Erro ao aprovar: {exc}")
                with b2:
                    if st.button("Rejeitar", key=f"proposal_reject_{prop['proposal_id']}"):
                        try:
                            reject_proposal(prop["proposal_id"])
                            st.success("Rejeitado.")
                            load_pending_proposals.clear()
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Erro ao rejeitar: {exc}")

# ─────────────────────────────────────────────────────────────────────────
# Aba 8 -- Overrides Historicos. Duas secoes:
#   1) Upload da Cora (Jan-Jun/2026) -- fluxo original, escopo fechado, NAO
#      generaliza (guarda-corpo em validate_override_scope).
#   2) Config por cliente (2026-08-05) -- generaliza o liga/desliga do
#      override para qualquer cliente que ja tenha dado carregado em
#      stg.historical_overrides_delivery (movida de core em 2026-08-06),
#      com range real calculado ao vivo
#      e status em core.client_reporting_source_config (SCD2).
# ─────────────────────────────────────────────────────────────────────────
with tab_overrides:
    st.subheader("Ajuste Manual de Dados -- Banco Cora (Jan-Jun/2026)")
    st.warning(
        ":material/warning: Fluxo fechado e pontual -- carrega a planilha legada da Cora "
        "para o periodo Jan-Jun/2026 apenas. Nao e uma pratica recorrente para outros "
        "clientes/periodos (guarda-corpo de escopo aplicado abaixo).",
        icon=":material/warning:",
    )

    st.markdown("**1. Upload da planilha**")
    uploaded = st.file_uploader("Arquivo (.xlsx ou .csv)", type=["xlsx", "csv"], key="override_upload")

    if uploaded is not None:
        raw_df = read_uploaded_spreadsheet(uploaded)
        st.caption("Preview bruto do arquivo:")
        st.dataframe(raw_df.head(20), use_container_width=True, hide_index=True)

        st.markdown("**2. Mapeamento de colunas**")
        st.caption("Para cada campo do schema alvo, escolha a coluna correspondente no arquivo.")
        source_columns = ["(nenhuma)"] + list(raw_df.columns)
        mapping = {}
        map_cols = st.columns(len(OVERRIDE_TARGET_FIELDS))
        for col, field in zip(map_cols, OVERRIDE_TARGET_FIELDS):
            with col:
                choice = st.selectbox(field, source_columns, key=f"override_map_{field}")
                mapping[field] = None if choice == "(nenhuma)" else choice

        if mapping.get("day") is None:
            st.info("Mapeie ao menos a coluna `day` para continuar.")
        else:
            try:
                normalized_df = build_override_dataframe(raw_df, mapping)
            except Exception as exc:
                st.error(f"Erro ao normalizar com esse mapeamento: {exc}")
                normalized_df = None

            if normalized_df is not None:
                st.markdown("**3. Preview normalizado + validacao de escopo**")
                st.dataframe(normalized_df, use_container_width=True, hide_index=True)

                scope_errors = validate_override_scope(normalized_df)
                for err in scope_errors:
                    st.error(err)

                if not scope_errors:
                    st.markdown("**4. Comparacao com o gold atual (mesmo cliente/periodo)**")
                    if st.button("Comparar com gold.fact_delivery", key="override_compare_btn"):
                        compare_sql = f"""
                        SELECT
                          ROUND(SUM(impressions)) AS impressions_gold_atual,
                          ROUND(SUM(clicks)) AS clicks_gold_atual
                        FROM `{PROJECT_ID}.gold.fact_delivery`
                        WHERE client_id = '{CORA_CLIENT_ID}'
                          AND day BETWEEN '{CORA_OVERRIDE_START}' AND '{CORA_OVERRIDE_END}'
                        """
                        gold_totals = get_bq_client().query(compare_sql).to_dataframe()
                        file_totals = pd.DataFrame([{
                            "impressions_arquivo": normalized_df["impressions"].sum(),
                            "clicks_arquivo": normalized_df["clicks"].sum(),
                        }])
                        st.dataframe(pd.concat([gold_totals, file_totals], axis=1), use_container_width=True, hide_index=True)

                    st.markdown("**5. Confirmar carga**")
                    notes = st.text_input("Notas (opcional)", key="override_notes")
                    confirm = st.checkbox(
                        "Confirmo que revisei o preview e a comparacao acima antes de commitar",
                        key="override_confirm_checkbox",
                    )
                    if st.button("Confirmar carga em stg.historical_overrides_delivery", disabled=not confirm, key="override_commit_btn"):
                        try:
                            with st.spinner("Escrevendo (writer SA impersonada)..."):
                                n_rows = commit_override(normalized_df, uploaded.name, notes)
                            st.success(f"{n_rows} linha(s) inserida(s) em `stg.historical_overrides_delivery`.")
                        except Exception as exc:
                            st.error(f"Erro ao commitar: {exc}")

    st.divider()
    st.subheader("Upload de Planilha Historica")
    st.caption(
        "Peca (a) do desenho fechado em 2026-08-05/06 para generalizar overrides "
        "historicos alem da Cora (ver docs/known_issues.md item S4): sobe a planilha "
        "crua do comercial, SEM NENHUM tratamento -- nem validacao de coluna, nem "
        "parsing -- como landing RAW literal dentro do projeto de STAGING "
        "(`douglas-bq-staging`, nunca producao). Douglas + IA analisam a estrutura real "
        "mostrada abaixo antes de construir o mapeamento de normalizacao (a peca 'b' -- "
        "carrega dado ja normalizado -- ja existe em "
        "`scripts/deploy/load_historical_override.py`, mas exige entrada ja mapeada 1:1 "
        "para o schema final; esta secao aqui e o passo ANTES disso)."
    )
    st.warning(
        ":material/warning: Contrato de tabelas confirmado com o backend "
        f"(`{RAW_UPLOADS_TABLE}` + `{RAW_UPLOADS_META_TABLE}`), mas a writer SA do hub "
        "ainda nao tem `dataEditor` no dataset `raw` de `douglas-bq-staging` (hoje ela so "
        "escreve em `adframework.core`/`adframework.raw`) -- e possivel que as tabelas em "
        "si ainda nao existam la tambem. O botao de confirmar abaixo TENTA gravar de "
        "verdade e mostra o erro exato se faltar permissao/tabela, em vez de simular. "
        "Selecao de cliente, upload e preview local ja funcionam de verdade independente disso.",
        icon=":material/warning:",
    )

    client_options = load_client_options()
    if client_options.empty:
        st.error("`core.dim_client` nao retornou nenhum cliente ativo -- nada para selecionar.")
    else:
        client_options = client_options.copy()
        client_options["display"] = client_options["name"] + " (" + client_options["client_id"] + ")"
        landing_client_display = st.selectbox(
            "Cliente", client_options["display"].tolist(), key="landing_client_select"
        )
        landing_client_row = client_options[client_options["display"] == landing_client_display].iloc[0]
        landing_client_id = landing_client_row["client_id"]

        landing_upload = st.file_uploader(
            "Planilha crua (.csv ou .xlsx) -- sobe exatamente como o comercial mandou, sem tratamento",
            type=["csv", "xlsx"],
            key="landing_upload",
        )

        if landing_upload is not None:
            landing_raw_df = None
            try:
                landing_raw_df = read_uploaded_spreadsheet_raw(landing_upload)
            except Exception as exc:
                st.error(f"Nao consegui ler o arquivo (formato invalido?): {exc}")

            if landing_raw_df is not None:
                if landing_raw_df.empty:
                    st.error("Arquivo lido, mas esta vazio -- nada para subir.")
                else:
                    st.markdown("**Estrutura real do arquivo (sem nenhum tratamento)**")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("Total de linhas", len(landing_raw_df))
                    with col_b:
                        st.metric("Total de colunas", len(landing_raw_df.columns))
                    st.caption("Colunas encontradas, na ordem do arquivo:")
                    st.code(", ".join(str(c) for c in landing_raw_df.columns), language=None)
                    st.caption("Amostra (10 primeiras linhas):")
                    st.dataframe(landing_raw_df.head(10), use_container_width=True, hide_index=True)

                    landing_confirm = st.checkbox(
                        f"Confirmo que este arquivo e o historico cru de "
                        f"**{landing_client_row['name']}** (`{landing_client_id}`) e deve subir "
                        "como landing RAW literal, sem tratamento",
                        key="landing_confirm_checkbox",
                    )
                    if st.button(
                        "Confirmar upload para landing RAW",
                        key="landing_commit_btn",
                        disabled=not landing_confirm,
                    ):
                        with st.spinner("Escrevendo (writer SA impersonada)..."):
                            result = stage_raw_historical_upload(landing_raw_df, landing_client_id, landing_upload.name)
                        if result["staged"]:
                            st.success(
                                f"Landing gravado em `{result['would_be_table']}` "
                                f"(upload_id `{result['upload_id']}`)."
                            )
                            st.session_state["landing_last_upload_id"] = result["upload_id"]
                        else:
                            st.warning(
                                f"Preview validado ({result['n_rows']} linha(s), "
                                f"{len(result['columns'])} coluna(s) para `{landing_client_id}`) mas "
                                f"AINDA NAO gravado no BigQuery -- {result['reason']}",
                                icon=":material/warning:",
                            )

                    last_upload_id = st.session_state.get("landing_last_upload_id")
                    if last_upload_id:
                        st.markdown("**Estrutura real do que pousou em `douglas-bq-staging.raw`**")
                        st.caption(
                            "Lido de volta de historical_uploads_meta + historical_uploads (nao do "
                            "arquivo local) -- confirma o que de fato ficou gravado, base para a "
                            "analise humana/IA que decide como normalizar depois."
                        )
                        try:
                            landed_meta, landed_sample = load_landed_historical_upload(last_upload_id)
                        except (NotFound, Forbidden) as exc:
                            landed_meta, landed_sample = None, None
                            st.error(
                                "Nao consegui ler de volta o que pousou -- provavelmente falta leitura "
                                f"da SA principal (`douglas-data-hub-sa`) no projeto `{RAW_LANDING_PROJECT_ID}` "
                                f"ainda (identificar/reportar, nao aplicar agora). Erro: {exc}"
                            )
                        except Exception as exc:
                            landed_meta, landed_sample = None, None
                            st.error(f"Erro ao ler o landing gravado: {exc}")

                        if landed_meta:
                            col_c, col_d = st.columns(2)
                            with col_c:
                                st.metric("Total de linhas (BQ)", int(landed_meta.get("row_count", 0)))
                            with col_d:
                                st.metric("Total de colunas (BQ)", len(landed_meta.get("column_names") or []))
                            st.caption("Colunas (de historical_uploads_meta.column_names):")
                            st.code(", ".join(str(c) for c in (landed_meta.get("column_names") or [])), language=None)
                            if landed_sample is not None and not landed_sample.empty:
                                st.caption("Amostra (de historical_uploads.raw_row, parseado):")
                                st.dataframe(landed_sample, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Comparacao: Planilha vs. Dado Real")
    st.caption(
        "Apoio visual para a analise humana ANTES de construir o mapeamento de "
        "normalizacao (decisao fechada com o Douglas em 2026-08-06): mostra a "
        "planilha crua que ja pousou em `raw.historical_uploads` lado a lado com "
        "uma amostra real do mesmo periodo em `gold.fact_delivery` de "
        "`douglas-bq-staging`. So leitura -- sem nenhum diff automatico "
        "(determinístico ou por IA); a interpretacao fica com o Douglas + a "
        "sessao do Claude Code (ou o agente `historical-data-analyst`)."
    )

    if client_options.empty:
        st.info("`core.dim_client` nao retornou nenhum cliente ativo -- nada para comparar.")
    else:
        compare_client_display = st.selectbox(
            "Cliente", client_options["display"].tolist(), key="compare_client_select"
        )
        compare_client_row = client_options[client_options["display"] == compare_client_display].iloc[0]
        compare_client_id = compare_client_row["client_id"]

        uploads_for_client = load_historical_uploads_for_client(compare_client_id)
        if uploads_for_client.empty:
            st.info(
                f"Nenhum upload em `historical_uploads_meta` ainda para **{compare_client_row['name']}** "
                f"(`{compare_client_id}`) -- suba uma planilha na secao acima primeiro."
            )
        else:
            uploads_for_client = uploads_for_client.copy()
            uploads_for_client["display"] = (
                uploads_for_client["source_filename"] + " -- "
                + uploads_for_client["uploaded_at"].astype(str)
                + f" ({uploads_for_client['row_count']} linhas)"
            )
            compare_upload_display = st.selectbox(
                "Upload", uploads_for_client["display"].tolist(), key="compare_upload_select"
            )
            compare_upload_id = uploads_for_client[
                uploads_for_client["display"] == compare_upload_display
            ].iloc[0]["upload_id"]

            with st.spinner("Lendo planilha pousada e inferindo periodo..."):
                _, landing_sample_df = load_landed_historical_upload(compare_upload_id)
                full_raw_df = load_full_landed_historical_upload(compare_upload_id)
                inferred_min, inferred_max, inferred_col = infer_date_range_from_raw(full_raw_df)

            if inferred_col:
                st.caption(
                    f"Periodo inferido automaticamente da coluna `{inferred_col}` da planilha "
                    f"crua: **{inferred_min}** a **{inferred_max}**. Ajuste abaixo se necessario."
                )
            else:
                st.warning(
                    ":material/warning: Nao consegui inferir automaticamente uma coluna de data "
                    "nessa planilha crua (nenhuma coluna com nome parecido com data/dia bateu com "
                    "confianca suficiente) -- selecione o periodo manualmente abaixo.",
                    icon=":material/warning:",
                )

            range_col1, range_col2 = st.columns(2)
            with range_col1:
                compare_start = st.date_input(
                    "Inicio do periodo", value=inferred_min or date.today(), key="compare_range_start"
                )
            with range_col2:
                compare_end = st.date_input(
                    "Fim do periodo", value=inferred_max or date.today(), key="compare_range_end"
                )

            if compare_start > compare_end:
                st.error("Inicio do periodo esta depois do fim -- ajuste o range acima.")
            else:
                st.markdown("**Snapshot lado a lado (mesmo periodo)**")
                left_col, right_col = st.columns(2)
                with left_col:
                    st.markdown(f"*Planilha crua -- `{compare_upload_display}`*")
                    if landing_sample_df is not None and not landing_sample_df.empty:
                        st.dataframe(landing_sample_df.head(15), use_container_width=True, hide_index=True)
                    else:
                        st.info("Amostra da planilha veio vazia.")
                with right_col:
                    st.markdown(
                        f"*Dado real -- `gold.fact_delivery` ({HISTORICAL_OVERRIDE_PROJECT_ID}), "
                        f"{compare_start} a {compare_end}*"
                    )
                    try:
                        gold_sample_df = load_gold_sample_for_range(compare_client_id, compare_start, compare_end)
                    except (NotFound, Forbidden) as exc:
                        gold_sample_df = None
                        st.error(f"Nao consegui ler `gold.fact_delivery` em `{HISTORICAL_OVERRIDE_PROJECT_ID}`: {exc}")
                    except Exception as exc:
                        gold_sample_df = None
                        st.error(f"Erro ao ler `gold.fact_delivery`: {exc}")

                    if gold_sample_df is not None:
                        if gold_sample_df.empty:
                            coverage_min, coverage_max = load_gold_coverage_for_client(compare_client_id)
                            if coverage_min is None:
                                st.warning(
                                    f":material/warning: `gold.fact_delivery` em "
                                    f"`{HISTORICAL_OVERRIDE_PROJECT_ID}` nao tem NENHUM dado para "
                                    f"`{compare_client_id}` -- nao ha o que comparar ainda (achado "
                                    "relevante, nao um erro de tela).",
                                    icon=":material/warning:",
                                )
                            else:
                                st.warning(
                                    f":material/warning: Sem sobreposicao de periodo -- a planilha "
                                    f"cobre {compare_start} a {compare_end}, mas o dado real de "
                                    f"`{compare_client_id}` em `gold.fact_delivery` so existe de "
                                    f"**{coverage_min}** a **{coverage_max}**. Achado relevante para a "
                                    "analise, nao um erro de tela.",
                                    icon=":material/warning:",
                                )
                        else:
                            st.dataframe(gold_sample_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Configuracao de Ajustes por Cliente")
    st.caption(
        "Desenho fechado com o Douglas em 2026-08-05: generaliza o override historico para "
        "qualquer cliente que ja tenha dado carregado em `stg.historical_overrides_delivery` "
        "(hoje so a Cora, via o fluxo de upload acima -- mas essa secao ja funciona para "
        "qualquer client_id que aparecer ali no futuro, sem mudanca de codigo). O range "
        "(MIN/MAX day) e sempre calculado AO VIVO -- nunca digitado. O liga/desliga fica em "
        "`core.client_reporting_source_config` (SCD2), tabela nova que o backend esta "
        "construindo em paralelo."
    )

    delivery_summary = load_override_delivery_summary()

    if delivery_summary.empty:
        st.info("Nenhum cliente com dado carregado em `stg.historical_overrides_delivery` ainda.")
    else:
        config_table_missing = False
        try:
            active_config = load_override_active_config()
        except NotFound:
            active_config = pd.DataFrame(
                columns=["client_id", "override_active", "effective_from", "reason", "confirmed_by", "confirmed_at"]
            )
            config_table_missing = True

        if config_table_missing:
            st.warning(
                ":material/warning: `core.client_reporting_source_config` ainda nao existe no "
                "BigQuery (o backend esta construindo o DDL em paralelo) -- o range real abaixo "
                "funciona normalmente, mas o status de liga/desliga aparece como 'inativo' para "
                "todo mundo ate a tabela existir, e o botao de gravar vai falhar com erro claro.",
                icon=":material/warning:",
            )

        status_df = build_client_override_status(delivery_summary, active_config)

        st.markdown("**Status atual por cliente**")
        display_status = status_df.copy()
        display_status["override_active"] = display_status["override_active"].map(
            lambda v: "ativo" if v else "inativo"
        )
        st.dataframe(
            display_status[
                ["client_id", "n_linhas", "min_day", "max_day", "override_active", "effective_from", "reason"]
            ],
            use_container_width=True, hide_index=True,
        )

        st.markdown("**Alterar liga/desliga de um cliente**")
        client_choice = st.selectbox(
            "Cliente", sorted(status_df["client_id"].unique().tolist()), key="override_toggle_client"
        )
        current_row = status_df[status_df["client_id"] == client_choice].iloc[0]
        current_active = bool(current_row["override_active"])
        st.caption(
            f"Estado atual: **{'ativo' if current_active else 'inativo'}** -- "
            f"{current_row['n_linhas']} linha(s) carregada(s), {current_row['min_day']} a {current_row['max_day']}."
        )
        new_active = st.toggle("override_active", value=current_active, key="override_toggle_value")
        reason = st.text_input("Motivo da mudanca", key="override_toggle_reason")
        toggle_changed = new_active != current_active
        if not toggle_changed:
            st.caption("Nenhuma mudanca de estado selecionada -- mude o toggle acima para habilitar a gravacao.")
        toggle_confirm = st.checkbox(
            "Confirmo que revisei o estado atual e quero gravar esta mudanca (nova linha SCD2 em "
            "`core.client_reporting_source_config`, fechando a linha vigente)",
            key="override_toggle_confirm",
            disabled=not toggle_changed,
        )
        if st.button(
            "Gravar novo estado",
            key="override_toggle_commit_btn",
            disabled=not (toggle_changed and toggle_confirm),
        ):
            try:
                with st.spinner("Escrevendo (writer SA impersonada)..."):
                    set_client_override_active(client_choice, new_active, reason)
                st.success(f"`{client_choice}` -> override_active={new_active}.")
                load_override_active_config.clear()
                st.rerun()
            except NotFound:
                st.error(
                    "`core.client_reporting_source_config` ainda nao existe no BigQuery -- o "
                    "backend precisa aplicar o DDL antes desse botao funcionar."
                )
            except Exception as exc:
                st.error(f"Erro ao gravar: {exc}")

# ─────────────────────────────────────────────────────────────────────────
# Aba 9 -- Regras de Negocio: listagem de core.client_business_rules (staging,
# ver comentario de BUSINESS_RULES_TABLE) + criacao de regra nova + Pausar
# (dentro de cada card, ver _render_business_rule_card). Sem preview/simulacao
# de impacto -- decisao explicita do Douglas 2026-08-10 para nao atrasar;
# fica para uma iteracao seguinte. Fluxo de "nova versao substituindo uma
# vigente" tambem NAO esta implementado nesta entrega -- se ja existe versao
# vigente para o (tipo, escopo) escolhido, a criacao e bloqueada com aviso
# (ver business_rule_exists_active); so cobre criar quando nao ha vigente e
# pausar. Escrita via get_staging_writer_bq_client() -- nunca a writer de
# producao.
# ─────────────────────────────────────────────────────────────────────────
with tab_business_rules:
    st.subheader("Regras de Negocio")
    st.caption(
        "Regras configuraveis por cliente (ex: teto de impressao diaria), com historico "
        "completo de alteracoes. Ainda em ambiente de testes, fora do pipeline oficial."
    )

    try:
        with st.spinner("Consultando regras cadastradas..."):
            rules_df = load_business_rules()
        client_names_df = load_business_rules_client_names()
    except NotFound:
        st.info(
            "`core.client_business_rules` ainda nao existe no BigQuery -- o backend precisa "
            "aplicar o DDL antes desta aba ter o que listar.",
            icon=":material/info:",
        )
        rules_df = pd.DataFrame()
        client_names_df = pd.DataFrame()

    # Linhas de teste sintetico (rule_type terminado em "_test") usadas pra validar
    # o schema em staging (4 casos: geral, override cliente, pausa, substituicao de
    # versao) -- ficam no banco como registro do teste, mas nunca devem aparecer na
    # listagem nem no seletor de tipo do formulario (visivel a stakeholders externos
    # ao abrir o Hub, ex: apresentacao a chefes).
    rules_df = rules_df[~rules_df["rule_type"].str.endswith("_test", na=False)] if not rules_df.empty else rules_df

    if rules_df.empty:
        st.info("Nenhuma regra de negocio cadastrada ainda.")
    else:
        client_name_map = (
            dict(zip(client_names_df["client_id"], client_names_df["name"]))
            if not client_names_df.empty else {}
        )

        for rule_type, type_df in rules_df.groupby("rule_type", sort=False):
            st.markdown(f"### {RULE_TYPE_LABELS.get(rule_type, rule_type)}")

            current_df = type_df[type_df["effective_to"].isna()]
            history_df = type_df[type_df["effective_to"].notna()]

            # Regra geral (client_id nulo) -- card sempre primeiro, se existir.
            general_current = current_df[current_df["client_id"].isna()]
            general_history = history_df[history_df["client_id"].isna()]
            if not general_current.empty or not general_history.empty:
                _render_business_rule_card(
                    rule_type=rule_type,
                    scope_label="Geral",
                    is_general=True,
                    current_row=general_current.iloc[0] if not general_current.empty else None,
                    history_df=general_history,
                )

            # Overrides por cliente -- um card por client_id, incluindo os que so
            # tem historico fechado (sem versao vigente hoje).
            client_ids = sorted(
                set(current_df.loc[current_df["client_id"].notna(), "client_id"])
                | set(history_df.loc[history_df["client_id"].notna(), "client_id"])
            )
            for client_id in client_ids:
                scope_label = client_name_map.get(client_id, f"{client_id} (cliente nao encontrado)")
                client_current = current_df[current_df["client_id"] == client_id]
                client_history = history_df[history_df["client_id"] == client_id]
                _render_business_rule_card(
                    rule_type=rule_type,
                    scope_label=scope_label,
                    is_general=False,
                    current_row=client_current.iloc[0] if not client_current.empty else None,
                    history_df=client_history,
                )

            st.divider()

    with st.expander("+ Nova regra", expanded=False):
        st.caption(
            "Cria uma regra nova. So funciona quando ainda NAO ha uma versao vigente "
            "para o tipo/escopo escolhido; se ja houver, pause a regra atual na "
            "listagem acima antes de criar outra."
        )

        # "impression_cap_pct" sempre disponivel como opcao pronta (nao so quando ja
        # existe pelo menos uma linha real em core.client_business_rules) -- e o unico
        # rule_type com formulario dedicado (threshold_pct + strategies) hoje, entao
        # nao faz sentido obrigar "+ novo tipo..." so porque nenhuma regra real de
        # producao foi criada ainda (a primeira criacao seria justamente essa).
        existing_types = sorted(
            set(rules_df["rule_type"].dropna().unique().tolist()) | {"impression_cap_pct"}
        )
        new_type_option = "➕ novo tipo..."
        selected_type_option = st.selectbox(
            "Tipo de regra", options=existing_types + [new_type_option], key="new_rule_type_select",
            format_func=lambda rt: RULE_TYPE_LABELS.get(rt, rt) if rt != new_type_option else rt,
        )
        rule_type_input = (
            st.text_input("Novo rule_type (ex: meu_novo_tipo)", key="new_rule_type_text")
            if selected_type_option == new_type_option
            else selected_type_option
        )

        scope_choice = st.radio(
            "Escopo", options=["Regra geral (todos os clientes)", "Cliente especifico"],
            key="new_rule_scope",
        )
        client_id_input = None
        client_scope_ready = scope_choice == "Regra geral (todos os clientes)"
        if scope_choice == "Cliente especifico":
            try:
                client_options_df = load_client_options()
            except Exception as exc:
                client_options_df = pd.DataFrame()
                st.error(f"Erro ao carregar lista de clientes: {exc}")
            if not client_options_df.empty:
                client_label_map = dict(zip(client_options_df["name"], client_options_df["client_id"]))
                client_label = st.selectbox(
                    "Cliente", options=list(client_label_map.keys()), key="new_rule_client",
                )
                client_id_input = client_label_map.get(client_label)
                client_scope_ready = client_id_input is not None
            else:
                st.warning("Nenhum cliente ativo encontrado em core.dim_client.")

        is_known_type = bool(rule_type_input) and rule_type_input.startswith("impression_cap_pct")
        rule_params = None
        params_valid = False

        if is_known_type:
            threshold_pct = st.number_input(
                "Teto de impressao (%)", min_value=1, max_value=100, value=20, step=1,
                key="new_rule_threshold",
            )
            strategies = st.multiselect(
                "Estrategias", options=["native", "push", "video", "display", "retargeting"],
                key="new_rule_strategies",
            )
            params_valid = bool(strategies)
            rule_params = {"threshold_pct": int(threshold_pct), "strategies": strategies}
        elif rule_type_input:
            raw_json_text = st.text_area(
                "Parametros (JSON bruto)", key="new_rule_json",
                help="Formato livre por rule_type -- validado como JSON antes de habilitar salvar.",
            )
            try:
                rule_params = json.loads(raw_json_text) if raw_json_text.strip() else None
                params_valid = rule_params is not None
            except (ValueError, AttributeError):
                params_valid = False
                if raw_json_text.strip():
                    st.error("JSON invalido.")

        effective_from_input = st.date_input(
            "Vigente a partir de", value=date.today(), min_value=date.today(),
            key="new_rule_effective_from",
        )
        confirmed_by_input = st.text_input("Confirmado por", key="new_rule_confirmed_by")
        notes_input = st.text_area("Notas (contexto/evidencia da decisao)", key="new_rule_notes")

        already_active = False
        if rule_type_input and client_scope_ready:
            try:
                already_active = business_rule_exists_active(rule_type_input, client_id_input)
            except Exception as exc:
                st.error(f"Erro ao checar regra vigente: {exc}")
                already_active = True  # nao deixa salvar se a checagem falhou -- guarda-corpo do lado seguro

        if already_active:
            st.warning(
                "Ja existe uma versao vigente para esse tipo/escopo -- criacao bloqueada "
                "nesta entrega. Pause a versao atual (na listagem acima) antes de criar outra.",
                icon=":material/warning:",
            )

        can_save = (
            bool(rule_type_input)
            and client_scope_ready
            and params_valid
            and bool(confirmed_by_input.strip())
            and bool(notes_input.strip())
            and effective_from_input >= date.today()
            and not already_active
        )

        if st.button("Salvar regra", disabled=not can_save, key="new_rule_save"):
            try:
                with st.spinner("Gravando nova regra (writer SA impersonada, staging)..."):
                    create_business_rule(
                        rule_type=rule_type_input,
                        client_id=client_id_input,
                        rule_params=rule_params,
                        confirmed_by=confirmed_by_input.strip(),
                        notes=notes_input.strip(),
                        effective_from=effective_from_input,
                    )
                st.success("Regra criada.")
                load_business_rules.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"Erro ao criar regra: {exc}")

    st.divider()
    st.subheader("Simulador de Impacto")
    st.caption(
        "Usa dado real de entrega para calcular, na hora, o que aconteceria se essa "
        "regra estivesse ativa. E so uma visualizacao -- nao salva nada, nao altera "
        "nenhum dado do cliente."
    )

    try:
        sim_client_options_df = load_client_options()
    except Exception as exc:
        sim_client_options_df = pd.DataFrame()
        st.error(f"Erro ao carregar lista de clientes: {exc}")

    if sim_client_options_df.empty:
        st.warning("Nenhum cliente ativo encontrado.")
    else:
        sim_client_label_map = dict(zip(sim_client_options_df["name"], sim_client_options_df["client_id"]))
        sim_col1, sim_col2, sim_col3 = st.columns([2, 1, 2])
        with sim_col1:
            sim_client_label = st.selectbox(
                "Cliente", options=list(sim_client_label_map.keys()), key="sim_client",
            )
        with sim_col2:
            sim_threshold_pct = st.number_input(
                "Teto (%)", min_value=1, max_value=100, value=20, step=1, key="sim_threshold",
            )
        with sim_col3:
            sim_strategies = st.multiselect(
                "Estrategias", options=["native", "push", "video", "display", "retargeting"],
                default=["native", "push"], key="sim_strategies",
            )

        if st.button("Rodar simulacao", key="sim_run", disabled=not sim_strategies):
            sim_client_id = sim_client_label_map[sim_client_label]
            with st.spinner("Calculando..."):
                pacing_df = load_pacing_for_simulation(sim_client_id, tuple(sim_strategies))

            if pacing_df.empty:
                st.info("Sem dado de entrega para esse cliente/estrategia no periodo disponivel.")
            else:
                has_plan = pacing_df["planned_impressions_daily"].notna()
                cap = pacing_df["planned_impressions_daily"] * (1 + sim_threshold_pct / 100)
                simulated = pacing_df["realized_impressions"].where(
                    ~has_plan, pacing_df["realized_impressions"].clip(upper=cap)
                )
                pacing_df["teto_impressoes"] = cap
                pacing_df["impressoes_simuladas"] = simulated
                pacing_df["impressoes_cortadas"] = (
                    pacing_df["realized_impressions"] - pacing_df["impressoes_simuladas"]
                ).clip(lower=0)

                total_real = pacing_df["realized_impressions"].sum()
                total_sim = pacing_df["impressoes_simuladas"].sum()
                total_cortado = pacing_df["impressoes_cortadas"].sum()
                dias_sem_plano = int((~has_plan).sum())
                dias_afetados = int((pacing_df["impressoes_cortadas"] > 0).sum())

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Impressoes entregues", f"{total_real:,.0f}")
                m2.metric("Impressoes com o teto ativo", f"{total_sim:,.0f}")
                m3.metric(
                    "Reducao",
                    f"{total_cortado:,.0f}",
                    delta=f"-{(total_cortado / total_real * 100):.1f}%" if total_real else None,
                    delta_color="inverse",
                )
                m4.metric("Dias afetados", dias_afetados)
                if dias_sem_plano:
                    st.caption(
                        f":material/info: {dias_sem_plano} dia(s) sem planejamento cadastrado -- "
                        "nao entram no calculo do teto (nao ha o que comparar)."
                    )

                display_df = pacing_df.sort_values("impressoes_cortadas", ascending=False)[
                    ["day", "formato", "platform", "planned_impressions_daily",
                     "realized_impressions", "teto_impressoes", "impressoes_simuladas",
                     "impressoes_cortadas"]
                ].rename(columns={
                    "day": "Data",
                    "formato": "Formato",
                    "platform": "Plataforma",
                    "planned_impressions_daily": "Planejado",
                    "realized_impressions": "Entregue",
                    "teto_impressoes": "Teto",
                    "impressoes_simuladas": "Entregue (com teto)",
                    "impressoes_cortadas": "Diferenca",
                })
                st.dataframe(display_df, use_container_width=True, hide_index=True)
