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
from datetime import date, datetime, timezone
from pathlib import Path

import google.auth
import pandas as pd
import streamlit as st
import yaml
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
OVERRIDE_TABLE = f"{PROJECT_ID}.core.historical_overrides_delivery"
OVERRIDE_TARGET_FIELDS = ["day", "platform", "formato", "goal_type", "impressions", "clicks", "investimento"]

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
    ":material/history: Overrides Historicos (Cora)",
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
# Aba 8 -- Overrides Historicos (Cora): UNICO fluxo de escrita do hub que
# ja existia antes desta aba. Escopo fechado por decisao explicita -- so
# Cora, so Jan-Jun/2026, nunca vira pratica recorrente para outros clientes
# (ver hub/README.md).
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
                    if st.button("Confirmar carga em core.historical_overrides_delivery", disabled=not confirm, key="override_commit_btn"):
                        try:
                            with st.spinner("Escrevendo (writer SA impersonada)..."):
                                n_rows = commit_override(normalized_df, uploaded.name, notes)
                            st.success(f"{n_rows} linha(s) inserida(s) em `core.historical_overrides_delivery`.")
                        except Exception as exc:
                            st.error(f"Erro ao commitar: {exc}")
