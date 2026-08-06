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
# outras abas. dataEditor escopado por dataset (hoje: `core` + `raw`) -- ver hub/deploy.sh.
WRITER_SA_EMAIL = os.environ.get(
    "WRITER_SA_EMAIL", f"douglas-data-hub-writer-sa@{PROJECT_ID}.iam.gserviceaccount.com"
)

# Escopo fechado do override historico -- decisao explicita: isso NAO generaliza
# para outros clientes/periodos. So Cora, so Jan-Jun/2026. Ver docs/PROCESS.md
# e memoria project_gold_layer_state para o contexto completo.
CORA_CLIENT_ID = "banco_cora_fe13d78a"
CORA_OVERRIDE_START = date(2026, 1, 1)
CORA_OVERRIDE_END = date(2026, 6, 30)
OVERRIDE_TABLE = f"{PROJECT_ID}.stg.historical_overrides_delivery"
OVERRIDE_TARGET_FIELDS = ["day", "platform", "formato", "goal_type", "impressions", "clicks", "investimento"]

# Desenho fechado com o Douglas em 2026-08-05: generaliza o override historico
# para qualquer cliente (nao mais so Cora). O range de cada cliente (MIN/MAX day)
# vem SEMPRE ao vivo de OVERRIDE_TABLE, nunca de config digitada. O liga/desliga
# (`override_active`) fica em core.client_reporting_source_config -- tabela SCD2
# nova, construida pelo backend em paralelo (client_id, override_active,
# effective_from, effective_to, reason, confirmed_by, confirmed_at). Pode ainda
# nao existir em producao -- a secao abaixo trata isso sem quebrar.
CLIENT_REPORTING_SOURCE_CONFIG_TABLE = f"{PROJECT_ID}.core.client_reporting_source_config"

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
RAW_LANDING_PROJECT_ID = "douglas-bq-staging"
RAW_LANDING_DATASET = "raw"
RAW_UPLOADS_TABLE = f"{RAW_LANDING_PROJECT_ID}.{RAW_LANDING_DATASET}.historical_uploads"
RAW_UPLOADS_META_TABLE = f"{RAW_LANDING_PROJECT_ID}.{RAW_LANDING_DATASET}.historical_uploads_meta"

# Fila generica de propostas de mudanca pendentes de aprovacao humana. Tabela
# desenhada pelo backend para servir qualquer fonte futura (hoje so
# source='siprocal_diff', da reconciliacao incremental de raw.sp_delivery).
# So a aba "Propostas de Mudanca" le/escreve aqui -- ver commit_proposal_decision abaixo.
PROPOSALS_TABLE = f"{PROJECT_ID}.core.change_proposals"

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
    """Unico ponto de escrita do hub. Usa a writer SA impersonada."""
    client = get_writer_bq_client()
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

    Escreve com a writer SA impersonada. IMPORTANTE: essa SA hoje so tem
    dataEditor em `adframework.core` e `adframework.raw` (ver WRITER_SA_EMAIL) --
    projeto DIFERENTE de douglas-bq-staging. Ate um binding de IAM novo ser
    criado (dataset-scoped, mesmo padrao das demais, ver hub/deploy.sh -- NAO
    rodar gcloud/IAM sem confirmar com o Douglas antes), esta chamada deve
    falhar com erro de permissao -- tratado abaixo com uma mensagem clara em vez
    de deixar a excecao estourar na UI."""
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
        client = get_writer_bq_client()
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
    Usa a writer SA impersonada -- `core` ja esta no escopo dela (mesma usada
    pelo override da Cora), nenhum binding de IAM novo necessario."""
    client = get_writer_bq_client()

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

tab_freshness, tab_jobs, tab_powerbi, tab_costs, tab_browser, tab_query, tab_proposals, tab_overrides = st.tabs([
    ":material/database: Visao Geral BQ",
    ":material/sync: Status dos Jobs",
    ":material/bar_chart: Power BI em Construcao",
    ":material/payments: Custos",
    ":material/table_view: Navegador de Tabelas",
    ":material/terminal: Query Runner",
    ":material/fact_check: Propostas de Mudanca",
    ":material/history: Overrides Historicos",
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
    st.subheader("Overrides Historicos -- Banco Cora (Jan-Jun/2026)")
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
    st.subheader("Upload de Planilha Historica (Landing RAW)")
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
    st.subheader("Configuracao de Overrides por Cliente")
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
