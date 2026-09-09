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

import difflib
import io
import json
import os
import random
import re
import unicodedata
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import google.auth
import google.auth.transport.requests
import gspread
import pandas as pd
import requests
import streamlit as st
import yaml
from google.api_core.exceptions import Forbidden, NotFound
from google.auth import impersonated_credentials
from google.cloud import bigquery

PROJECT_ID = "adframework"
HUB_PASSWORD = os.environ.get("HUB_PASSWORD")  # se ausente (rodando local), nao pede senha

# Fase 2 autorizada pelo Douglas em 2026-09-07 (via AskUserQuestion, escolha
# explicita "Escrita completa em prod tambem") -- producao deixou de ser
# sempre-read-only por ambiente. O gate real agora e a PRESENCA da writer SA:
# HUB_READ_ONLY so e True quando WRITER_SA_EMAIL nao foi passada como env var
# (deploy sem SETUP_WRITER_SA=true, ou rodando local sem a var setada) --
# independente de HUB_TARGET_ENV ser staging ou production. HUB_TARGET_ENV
# continua controlando SERVICE_NAME/HISTORICAL_OVERRIDE_PROJECT_ID (ver
# hub/deploy.sh), so nao decide mais sozinho se escreve ou nao. HUB_READ_ONLY
# nao desliga NENHUMA permissao de IAM por si so -- e so o gate de UI; a
# garantia real continua sendo a ausencia da writer SA/bindings quando
# SETUP_WRITER_SA=false no deploy.
HUB_TARGET_ENV = os.environ.get("HUB_TARGET_ENV", "staging").lower()
HUB_READ_ONLY = not bool(os.environ.get("WRITER_SA_EMAIL"))

# Escrita isolada: so as abas de Overrides Historicos e Propostas de Mudanca usam
# essa SA, via impersonation (sem chave JSON). A SA principal do hub
# (douglas-data-hub-sa) continua 100% read-only -- nao muda em nada para as
# outras abas. dataEditor escopado por dataset: `core` + `raw` em $PROJECT_ID
# (Propostas de Mudanca) e `raw`/`stg`/`core` em douglas-bq-staging (Overrides
# Historicos + Config de Overrides, ambiente de teste) -- ver hub/deploy.sh.
WRITER_SA_EMAIL = os.environ.get(
    "WRITER_SA_EMAIL", f"douglas-data-hub-writer-sa@{PROJECT_ID}.iam.gserviceaccount.com"
)

# Gatilho on-demand "corrigir e reprocessar" na aba Saude do IO Plan (pedido
# do Douglas, 2026-09-06: "se achar problema ali, ja vou la corrigir a
# planilha e rodo on demand"). ATENCAO -- ESTA E A PRIMEIRA ACAO DO HUB QUE
# ESCREVE EM PRODUCAO DE VERDADE, SEM VERSAO DE STAGING: `scripts/io_plan/
# sync_drive.py` tem BQ_PROJECT="adframework" hardcoded (confirmado ao vivo,
# nao ha equivalente em douglas-bq-staging) -- diferente do resto do hub,
# este botao NAO respeita o seletor de ambiente (staging/producao) da aba,
# porque a fonte que ele aciona so existe em producao. Por isso fica atras do
# MESMO gate HUB_READ_ONLY que already protege Propostas de Mudanca/Overrides/
# Regras de Negocio -- nao habilitar aqui sem decisao explicita, mesmo que o
# resto da aba (leitura) va pro servico de producao.
#
# Reusa DOIS servicos Cloud Run que o backend ja mantem e ja rodam contra
# producao via Cloud Scheduler (confirmado ao vivo via `gcloud run services
# list`/`gcloud scheduler jobs list`, 2026-09-06):
#   1. io-plan-admin (services/io-plan-admin/main.py) -- roda sync_drive.py
#      por cliente. Ja e PUBLICO (roles/run.invoker = allUsers), protegido so
#      por token estatico na URL/form (SYNC_TOKEN) -- ver _check_token() la.
#      O HUB NAO PRECISA DE NENHUM IAM NOVO pra chamar este -- so precisa do
#      valor do token, que o Douglas define como secret/env var do Hub
#      (IO_PLAN_ADMIN_SYNC_TOKEN). Sem o valor, o botao fica desabilitado com
#      mensagem clara (nunca falha silenciosamente/finge sucesso).
#   2. fact-pacing-base-refresh -- Cloud Run que reaplica stg.fact_pacing_base
#      (fonte de gold.fact_pacing) em producao. GAP CONFIRMADO (2026-09-06):
#      o IAM dele (`gcloud run services get-iam-policy`) so autoriza
#      `fact-pacing-refresh-invoker@adframework.iam.gserviceaccount.com` --
#      NENHUMA service account do Hub (nem a principal douglas-data-hub-sa,
#      nem a writer douglas-data-hub-writer-sa) tem roles/run.invoker nele
#      hoje. Este modulo NAO concede esse binding sozinho -- fica documentado
#      aqui e reportado pro orquestrador/Douglas para decisao explicita (ver
#      protocolo de IAM do CLAUDE.md deste repo). Ate a concessao acontecer,
#      a etapa 2 do botao falha com 403 de proposito, com mensagem clara --
#      nao mascarar como sucesso.
IO_PLAN_ADMIN_URL = os.environ.get("IO_PLAN_ADMIN_URL", "https://io-plan-admin-kgv2ewhm3a-uc.a.run.app")
IO_PLAN_ADMIN_SYNC_TOKEN = os.environ.get("IO_PLAN_ADMIN_SYNC_TOKEN", "")
FACT_PACING_REFRESH_URL = os.environ.get("FACT_PACING_REFRESH_URL", "https://fact-pacing-base-refresh-kgv2ewhm3a-rj.a.run.app")
FACT_PACING_REFRESH_INVOKER_SA = "fact-pacing-refresh-invoker@adframework.iam.gserviceaccount.com"

# Ambiente de teste do fluxo de override historico -- 2026-08-06 douglas-bq-staging
# virou um ambiente standalone completo (raw copiado fisicamente, stg/core/gold
# 100% locais, paridade validada com producao). O fluxo inteiro (landing RAW,
# normalizacao, carga, toggle) roda AQUI primeiro, nunca em `adframework`
# (producao) -- essas duas tabelas nunca foram aplicadas em producao de proposito.
# Mesma constante de projeto usada pela landing RAW (RAW_LANDING_PROJECT_ID,
# definida mais abaixo) -- redeclarada aqui em cima porque e usada antes.
#
# 2026-08-16: parametrizado via env var pra suportar o segundo ambiente do Hub
# (Cloud Run de producao, servico separado `douglas-data-hub-prod`, ver
# hub/deploy.sh HUB_TARGET_ENV). Default continua "douglas-bq-staging" -- sem
# a env var setada, o comportamento do servico de staging existente nao muda
# em nada. O servico de producao roda com HISTORICAL_OVERRIDE_PROJECT_ID=adframework.
HISTORICAL_OVERRIDE_PROJECT_ID = os.environ.get(
    "HISTORICAL_OVERRIDE_PROJECT_ID", "douglas-bq-staging"
)

OVERRIDE_TABLE = f"{HISTORICAL_OVERRIDE_PROJECT_ID}.stg.historical_overrides_delivery"

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
# Hub NAO chama esse script, escreve direto via BQ client, ver
# stage_raw_historical_upload().
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

# Campos numericos de gold.fact_pacing disponiveis para o construtor de regra
# (aba Regras de Negocio) e para o Simulador de Impacto -- pedido explicito do
# Douglas (2026-08-10): "gostaria de selecionar os campos de referencia e
# escrever a regra", em vez do form anterior que assumia Impressoes/threshold_pct
# implicitamente sem deixar claro qual campo era comparado com qual. Escopo
# inicial e sempre fact_pacing (e onde a regra do Rafael se aplica); outras
# tabelas/campos podem entrar aqui no futuro conforme o Douglas evoluir o
# desenho em staging -- rotulo amigavel, chave = nome real da coluna.
FACT_PACING_FIELDS = {
    "realized_impressions": "Impressoes Entregues",
    "planned_impressions_daily": "Impressoes Planejadas",
    "realized_clicks": "Cliques Entregues",
    "planned_clicks_daily": "Cliques Planejados",
    "realized_conversions": "Conversoes Entregues",
    "investimento_realizado": "Investimento Realizado",
    "planned_spend_daily": "Investimento Planejado",
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

# Ambientes que o Farol/Navegador/Status dos Jobs sabem escanear -- SEMPRE os
# dois, lado a lado, independente de HISTORICAL_OVERRIDE_PROJECT_ID (aquela
# variavel controla so ONDE o fluxo de Override/Regras de Negocio escreve
# neste deploy especifico; esta lista aqui e sobre visibilidade de leitura,
# nao muda por deploy). Adicionado 2026-08-31 -- causa raiz do incidente
# `stg.fact_pacing_base` (staging) ficar 15 dias atrasada sem o hub acusar:
# load_table_metadata() so escaneava PROJECT_ID (adframework/producao),
# nunca douglas-bq-staging, entao qualquer tabela que so existisse ali era
# invisivel pro Farol/Navegador por completo. A SA principal (read-only) ja
# tem bigquery.dataViewer+jobUser em douglas-bq-staging desde 2026-08-06 (ver
# hub/deploy.sh, bloco de staging) -- nenhum IAM novo necessario pra isto.
STAGING_PROJECT_ID = "douglas-bq-staging"
ENVIRONMENTS = [
    {"id": "producao", "label": "Producao", "project_id": PROJECT_ID},
    {"id": "staging", "label": "Staging", "project_id": STAGING_PROJECT_ID},
]

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

# Billing export real (leitura apenas -- finops_billing e intocavel, nunca escrever aqui).
# Existe porque alguem (Shiro) ja habilitou o export da conta de faturamento pra BQ.
# So o dataset em si continua em uso (farol da tela principal, via
# _cost_by_service_since/load_cost_current_month/load_cost_previous_month) --
# a aba Custos dedicada (e as constantes/funcoes so dela) foi removida
# 2026-09-07 a pedido do Douglas (nao mais usada).
FINOPS_DATASET = "finops_billing"

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
def load_table_metadata(project_id: str = PROJECT_ID) -> pd.DataFrame:
    """Metadado nativo via __TABLES__ -- nao processa dados, nao cobra bytes.
    project_id permite escanear qualquer ambiente de ENVIRONMENTS (producao
    OU staging) -- a SA principal (read-only) ja tem dataViewer+jobUser nos
    dois projetos, ver comentario de ENVIRONMENTS acima. Datasets que nao
    existem no projeto pedido (ex: staging hoje nao tem marts/share/
    raw_siprocal) sao pulados individualmente em vez de quebrar a query
    inteira."""
    client = get_bq_client()
    existing_datasets = []
    for ds in DATASETS:
        try:
            client.get_dataset(f"{project_id}.{ds}")
            existing_datasets.append(ds)
        except NotFound:
            continue
    if not existing_datasets:
        return pd.DataFrame(
            columns=["dataset", "tabela", "tipo", "linhas", "tamanho_mb", "ultima_modificacao", "freshness"]
        )
    # __TABLES__ ja tem sua propria coluna dataset_id -- nao redeclarar, so unir.
    unions = "\n  UNION ALL\n  ".join(
        f"SELECT * FROM `{project_id}.{ds}.__TABLES__`" for ds in existing_datasets
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
def load_cost_current_month():
    """Resumo gross/net do mes corrente (calendario), pro farol da tela principal.
    Reusa _cost_by_service_since -- so muda a janela de data, mesma view curada."""
    df = _cost_by_service_since("DATE_TRUNC(CURRENT_DATE(), MONTH)")
    gross = df["gross"].sum() if not df.empty else 0.0
    net = df["net"].sum() if not df.empty else 0.0
    return gross, net


@st.cache_data(ttl=600)
def load_cost_previous_month():
    """Resumo gross/net do mes calendario anterior (janela fechada), so pra comparacao de
    variacao no farol -- mesma view curada finops_billing.vw_cost_daily_service, leitura apenas."""
    client = get_bq_client()
    query = f"""
    SELECT
      SUM(gross_cost) AS gross,
      SUM(net_cost) AS net
    FROM `{PROJECT_ID}.{FINOPS_DATASET}.vw_cost_daily_service`
    WHERE usage_date >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH)
      AND usage_date < DATE_TRUNC(CURRENT_DATE(), MONTH)
    """
    df = client.query(query).to_dataframe()
    if df.empty or pd.isna(df["gross"].iloc[0]):
        return 0.0, 0.0
    return float(df["gross"].iloc[0]), float(df["net"].iloc[0] if pd.notna(df["net"].iloc[0]) else 0.0)


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
def get_scheduler_client():
    from google.cloud import scheduler_v1
    return scheduler_v1.CloudSchedulerClient()


@st.cache_data(ttl=120)
def load_scheduler_job_status(project_id: str, location: str, job_id: str) -> dict:
    """Status REAL da ultima execucao de um Cloud Scheduler job -- sucesso/falha e
    quando, nao so 'a tabela alvo parece fresca' (heuristica indireta que e o que
    a aba Status dos Jobs usava ate 2026-08-31; ver causa raiz documentada em
    ENVIRONMENTS acima). Precisa de roles/cloudscheduler.viewer (leitura pura) pra
    SA principal no projeto -- se o binding ainda nao tiver sido aplicado (ver
    hub/deploy.sh), cai aqui num erro claro em vez de quebrar a aba inteira,
    mesmo padrao de tratamento de permissao ausente usado no resto do hub."""
    from google.api_core.exceptions import PermissionDenied
    from google.cloud import scheduler_v1

    try:
        client = get_scheduler_client()
        name = f"projects/{project_id}/locations/{location}/jobs/{job_id}"
        job = client.get_job(name=name)
        status_code = job.status.code if job.status else 0
        last_attempt = job.last_attempt_time
        return {
            "found": True,
            "state": scheduler_v1.Job.State(job.state).name,
            "last_attempt_time": last_attempt,
            "ok": status_code == 0,
            "error_message": job.status.message if status_code else None,
        }
    except PermissionDenied:
        return {
            "found": False,
            "error": "sem_permissao",
            "detail": (
                f"SA principal sem roles/cloudscheduler.viewer em `{project_id}` -- "
                "binding pendente, ver hub/deploy.sh (precisa confirmacao do Douglas antes de rodar)."
            ),
        }
    except NotFound:
        return {"found": False, "error": "job_nao_encontrado", "detail": f"Job `{job_id}` nao existe em `{project_id}/{location}`."}
    except Exception as exc:
        return {"found": False, "error": "erro", "detail": str(exc)}


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
    para as escritas que vivem 100% em staging (stage_raw_historical_upload,
    set_client_override_active) -- usar get_writer_bq_client()
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


@st.cache_resource
def get_writer_bq_client_for_project(project_id: str) -> bigquery.Client:
    """Mesma credencial impersonada da writer SA, faturando jobs no
    `project_id` PASSADO (nao um fixo como as duas funcoes irmas acima) --
    existe especificamente para a aba Saude do IO Plan (status de
    tratamento por achado, `core.io_plan_finding_status`), que precisa
    escrever no MESMO projeto que o seletor Staging/Producao daquela aba
    esta mostrando no momento, ao contrario do resto do hub que tem sempre
    um lado fixo (sempre staging, ou sempre producao).

    GAP DE IAM CONHECIDO (2026-09-06, confirmado ao vivo via `gcloud projects
    get-iam-policy adframework`): a writer SA tem dataEditor no DATASET
    `core` em AMBOS os projetos (staging e producao, dataset-level ACL via
    `bq add-iam-policy-binding`) mas so tem `roles/bigquery.jobUser`
    (permissao de RODAR jobs/queries, escopo sempre de PROJETO, nao de
    dataset) em `douglas-bq-staging` -- NENHUM binding de jobUser existe pra
    ela em `adframework` (producao) hoje. Isso significa: MERGE/UPDATE via
    esta funcao FUNCIONA contra staging, mas falha com 403 contra producao
    ate esse binding ser concedido -- mesmo padrao de gap ja documentado em
    get_staging_writer_bq_client() acima (que resolveu o mesmo problema
    restringindo por design a staging). Nao concedido automaticamente aqui
    -- decisao de IAM em producao passa pelo Douglas."""
    source_credentials, _ = google.auth.default()
    target_credentials = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=WRITER_SA_EMAIL,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        lifetime=300,
    )
    return bigquery.Client(project=project_id, credentials=target_credentials)


def _read_excel_resilient(uploaded_file, **kwargs) -> pd.DataFrame:
    """pd.read_excel com fallback para .xlsx com stylesheet corrompido -- erro real
    encontrado em producao (2026-08-10): 'could not read stylesheet from ... this
    is most probably because the workbook source files contain some invalid XML'.
    Causa comum: arquivo .xlsx gerado/re-salvo por ferramenta que produz
    xl/styles.xml fora do padrao que o openpyxl aceita (ex: alguns exports do
    Google Sheets, versoes antigas de LibreOffice). So lemos VALOR de celula aqui
    (nunca formatacao/estilo), entao o fallback remove xl/styles.xml do zip do
    xlsx antes de reler -- openpyxl usa estilo default e le o dado normalmente,
    sem perder nenhuma linha/coluna."""
    uploaded_file.seek(0)
    try:
        return pd.read_excel(uploaded_file, **kwargs)
    except ValueError as exc:
        if "stylesheet" not in str(exc).lower():
            raise
        uploaded_file.seek(0)
        raw_bytes = uploaded_file.read()
        buffer = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zin, zipfile.ZipFile(buffer, "w") as zout:
            for item in zin.infolist():
                if item.filename == "xl/styles.xml":
                    continue
                zout.writestr(item, zin.read(item.filename))
        buffer.seek(0)
        return pd.read_excel(buffer, **kwargs)


def read_uploaded_spreadsheet_raw(uploaded_file) -> pd.DataFrame:
    """Le TODAS as colunas como STRING, sem inferencia de tipo do pandas --
    mesmo principio 'RAW = dump literal' de scripts/deploy/load_historical_raw.py
    (a contraparte CLI que fixa este mesmo contrato)."""
    uploaded_file.seek(0)
    read_kwargs = {"dtype": str, "keep_default_na": False, "na_values": [""]}
    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file, **read_kwargs)
    return _read_excel_resilient(uploaded_file, **read_kwargs)


# Upload via link do Google Sheets -- alternativa ao file_uploader acima, mesmo
# fluxo de preview/mapeamento a partir daqui (task Notion 3b99d0f6, filha de
# "Desenhar override historico por cliente"). Mesmo padrao de credencial/scopes
# de scripts/etl/cora_sheets_sync.py (leitura pontual de UI aqui, nao job
# agendado). Nao passamos value_render_option -- comportamento padrao da API
# ja retorna valor calculado, nunca formula.
GSHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


@st.cache_resource
def get_gspread_client():
    creds, _ = google.auth.default(scopes=GSHEETS_SCOPES)
    return gspread.authorize(creds)


def extract_gsheet_id(link_or_id: str) -> str:
    """Aceita tanto o link completo (https://docs.google.com/spreadsheets/d/<ID>/edit...)
    quanto o ID puro colado direto."""
    link_or_id = (link_or_id or "").strip()
    m = re.search(r"/d/([a-zA-Z0-9-_]+)", link_or_id)
    return m.group(1) if m else link_or_id


@st.cache_data(ttl=120, show_spinner=False)
def list_gsheet_worksheets(spreadsheet_id: str) -> list:
    """Lista os titulos de todas as abas da planilha, para o usuario escolher
    qual e a correta antes de seguir pro fluxo de mapeamento."""
    gc = get_gspread_client()
    ss = gc.open_by_key(spreadsheet_id)
    return [ws.title for ws in ss.worksheets()]


@st.cache_data(ttl=120, show_spinner=False)
def read_gsheet_worksheet_raw(spreadsheet_id: str, worksheet_title: str) -> pd.DataFrame:
    """Le uma aba do Google Sheets como RAW literal -- mesmo contrato 'tudo
    string, sem tratamento' de read_uploaded_spreadsheet_raw acima.
    ws.get_all_values() ja retorna tudo como string por padrao (valor
    calculado, nao formula), entao o dtype ja bate sem conversao extra."""
    gc = get_gspread_client()
    ss = gc.open_by_key(spreadsheet_id)
    ws = ss.worksheet(worksheet_title)
    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame()
    headers = rows[0]
    data_rows = [r + [""] * max(0, len(headers) - len(r)) for r in rows[1:] if any(c.strip() for c in r)]
    data_rows = [r[: len(headers)] for r in data_rows]
    return pd.DataFrame(data_rows, columns=headers)


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


# ─────────────────────────────────────────────────────────────────────────
# Gerenciamento de Clientes -- CRUD real de core.dim_client (status
# ativo/inativo comercial, hierarquia parent_client_id, nome fantasia,
# toggle "Importar IO Plan"), + deteccao/reconciliacao de duplicatas. Task
# Notion 3b99d0f6219e81868244cfc5e472ec91, escopo fechado 2026-09-06/07.
# Motivador real: Casa do Construtor reiniciou relacionamento comercial e
# precisa "zerar" o historico sem apagar dado (so desativar pra frente);
# achado real do mesmo dia: Casa do Construtor e Dr. Consulta tem
# parent_client_id apontando pra DAXX (dax_agency_00000001) corretamente, mas
# Caloi/Efi Bank/Fox Lux/Mastercard (tambem sub-clientes da DAXX) nao tem esse
# campo preenchido -- inconsistencia real, nao hipotetica.
#
# "Ativo" NAO e calculado por freshness -- e o campo core.dim_client.status,
# editavel na tela. Freshness (gold.fact_delivery) e plataformas com dado
# aparecem so como CONTEXTO DE APOIO pra decisao humana (Douglas pergunta pro
# comercial "esse cliente ainda esta ativo?" e marca aqui), nunca como
# criterio automatico -- ver comentario de STATUS_OPTIONS abaixo.
#
# "Importar IO Plan" (import_io_plan, coluna nova, ver core/migration/
# 12_dim_client_add_import_io_plan.sql) e um campo SEPARADO de `status` --
# controla se scripts/io_plan/sync_drive.py deve processar aquele cliente,
# decisao independente de estar comercialmente ativo. NOTA (nao implementada
# aqui, fora do escopo do hub-frontend): sync_drive.py hoje decide quem
# processar via CLIENT_MAP/PARENT_FOLDER_CLIENTS hardcoded no proprio
# arquivo Python -- esta coluna e so o CAMPO que a tela edita, a migracao do
# sync pra ler daqui e trabalho de backend, sinalizado no relato final.
# ─────────────────────────────────────────────────────────────────────────
CLIENT_MGMT_TABLE = "core.dim_client"
CLIENT_MGMT_RECONCILIATION_TABLE = "core.dim_client_reconciliation"

# Valores aceitos de core.dim_client.status -- sem CHECK constraint (BigQuery
# nao suporta), validado no codigo que escreve. Vistos ao vivo em producao
# (2026-09-07): active, pending_confirmation, legacy (ver core/seeds/clients.csv);
# "inactive" adicionado aqui porque e o valor que o caso Casa do Construtor
# (e a desativacao de duplicata, ver deactivate_duplicate_client()) precisa
# gravar, mesmo sem nenhuma linha usando ainda.
CLIENT_STATUS_OPTIONS = ["active", "inactive", "pending_confirmation", "legacy"]
CLIENT_STATUS_LABELS = {
    "active": "Ativo", "inactive": "Inativo",
    "pending_confirmation": "Aguardando confirmacao comercial", "legacy": "Legado",
}

# Limiares da heuristica de duplicata (detect_duplicate_candidates) -- ajustaveis
# sem mudar a logica. score = similaridade de nome normalizado (0-1, ver
# normalize_client_name_for_match/similarity_score). Par com o MESMO
# parent_client_id (nao-nulo) pede uma similaridade menor pra ser sinalizado --
# sub-clientes do mesmo guarda-chuva com nomes parecidos sao o caso real (DR
# CONSULTA vs DR CONSULTA RJ, ambos sob DAXX) que motivou esta tela.
CLIENT_DUP_SCORE_THRESHOLD = 0.72
CLIENT_DUP_SCORE_THRESHOLD_SAME_PARENT = 0.55


def normalize_client_name_for_match(name) -> str:
    """Pura -- normaliza nome de cliente para comparacao de duplicata:
    lowercase, remove acentos (unicodedata), remove pontuacao, colapsa
    espacos multiplos. Nao remove sufixos regionais (ex: 'RJ', 'SP') de
    proposito -- e exatamente a diferenca que precisa aparecer no score de
    similaridade pra um humano decidir (removê-la faria 'Dr Consulta' e
    'Dr Consulta RJ' virarem identicos e o par nunca apareceria como
    candidato -- o oposto do que a tela precisa fazer)."""
    if not name or not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def similarity_score(a: str, b: str) -> float:
    """Pura -- razao de similaridade (0-1) entre duas strings ja normalizadas,
    via difflib.SequenceMatcher (biblioteca padrao, sem dependencia nova)."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def detect_duplicate_candidates(dim_client_df: pd.DataFrame) -> pd.DataFrame:
    """Pura -- gera todos os pares (client_id_a, client_id_b) de
    core.dim_client (client_id_a sempre o lexicograficamente menor, mesma
    normalizacao de chave usada por CLIENT_MGMT_RECONCILIATION_TABLE) cujo
    nome normalizado e "parecido o suficiente" (CLIENT_DUP_SCORE_THRESHOLD),
    OU parecido com um limiar mais baixo quando os dois compartilham o MESMO
    parent_client_id nao-nulo (caso DR CONSULTA / DR CONSULTA RJ, ambos sob
    DAXX -- ver comentario de CLIENT_DUP_SCORE_THRESHOLD_SAME_PARENT acima).
    Clientes ja num relacionamento pai-filho direto entre si (um e o
    parent_client_id do outro) NUNCA sao candidatos -- isso e hierarquia
    valida, nao duplicata. Retorna DataFrame vazio (mesmas colunas) se
    dim_client_df tiver menos de 2 linhas. Nao consulta BigQuery -- so
    dataframe em memoria, testavel sem mock de BQ."""
    cols = ["client_id_a", "name_a", "client_id_b", "name_b", "score", "same_parent"]
    if dim_client_df.shape[0] < 2:
        return pd.DataFrame(columns=cols)

    rows = dim_client_df.to_dict("records")
    normalized = [(r, normalize_client_name_for_match(r.get("name"))) for r in rows]
    candidates = []
    for i in range(len(normalized)):
        r_a, norm_a = normalized[i]
        for j in range(i + 1, len(normalized)):
            r_b, norm_b = normalized[j]
            # hierarquia direta (um e pai do outro) nunca e "duplicata"
            if r_a["client_id"] == r_b.get("parent_client_id") or r_b["client_id"] == r_a.get("parent_client_id"):
                continue
            same_parent = (
                pd.notna(r_a.get("parent_client_id")) and pd.notna(r_b.get("parent_client_id"))
                and r_a.get("parent_client_id") == r_b.get("parent_client_id")
            )
            score = similarity_score(norm_a, norm_b)
            threshold = CLIENT_DUP_SCORE_THRESHOLD_SAME_PARENT if same_parent else CLIENT_DUP_SCORE_THRESHOLD
            if score >= threshold:
                id_a, id_b = sorted([r_a["client_id"], r_b["client_id"]])
                name_by_id = {r_a["client_id"]: r_a.get("name"), r_b["client_id"]: r_b.get("name")}
                candidates.append({
                    "client_id_a": id_a, "name_a": name_by_id[id_a],
                    "client_id_b": id_b, "name_b": name_by_id[id_b],
                    "score": round(score, 3), "same_parent": same_parent,
                })
    if not candidates:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(candidates).sort_values(["same_parent", "score"], ascending=[False, False]).reset_index(drop=True)


def filter_undismissed_candidates(candidates_df: pd.DataFrame, decisions_df: pd.DataFrame) -> pd.DataFrame:
    """Pura -- remove da lista de candidatos qualquer par ja com decisao
    registrada em CLIENT_MGMT_RECONCILIATION_TABLE (seja 'same' ou
    'different'; uma vez decidido -- inclusive quando a decisao foi
    desativar um dos dois -- o par nao precisa incomodar de novo)."""
    if candidates_df.empty or decisions_df.empty:
        return candidates_df
    decided_pairs = {(r.client_id_a, r.client_id_b) for r in decisions_df.itertuples()}
    mask = ~candidates_df.apply(lambda r: (r["client_id_a"], r["client_id_b"]) in decided_pairs, axis=1)
    return candidates_df[mask].reset_index(drop=True)


@st.cache_data(ttl=120)
def check_dim_client_supports_import_io_plan(project_id: str) -> bool:
    """True se core.dim_client ja tem a coluna import_io_plan neste projeto
    especifico (ver core/migration/12_dim_client_add_import_io_plan.sql) --
    checado ao vivo via metadado de schema (nao um valor fixo), mesmo padrao
    de check_advertiser_rules_supports_global: staging e producao podem estar
    em estagios diferentes da migracao (aplicado em douglas-bq-staging
    2026-09-07; producao pendente de aprovacao do Douglas). So leitura de
    metadado, SA principal."""
    client = get_bq_client()
    table = client.get_table(f"{project_id}.{CLIENT_MGMT_TABLE}")
    return any(f.name == "import_io_plan" for f in table.schema)


@st.cache_data(ttl=120)
def load_client_management_data(project_id: str) -> pd.DataFrame:
    """Todas as colunas de core.dim_client + contexto de apoio (SUPORTE, nao
    fonte da verdade de ativo/inativo -- ver comentario no topo da secao):
    ultima entrega (MAX(day)) e lista de plataformas com dado, agregados de
    gold.fact_delivery via LEFT JOIN correlacionado -- cliente sem nenhuma
    linha de fact_delivery aparece com last_delivery/platforms NULL (nunca
    quebra a query). So leitura, SA principal."""
    client = get_bq_client()
    query = f"""
    SELECT
      c.*,
      d.last_delivery,
      d.platforms_with_data
    FROM `{project_id}.{CLIENT_MGMT_TABLE}` c
    LEFT JOIN (
      SELECT
        client_id,
        MAX(day) AS last_delivery,
        STRING_AGG(DISTINCT platform, ', ' ORDER BY platform) AS platforms_with_data
      FROM `{project_id}.gold.fact_delivery`
      GROUP BY client_id
    ) d USING (client_id)
    ORDER BY c.name
    """
    return client.query(query).to_dataframe()


@st.cache_data(ttl=60)
def load_client_reconciliation_decisions(project_id: str) -> pd.DataFrame:
    """Decisoes ja registradas em CLIENT_MGMT_RECONCILIATION_TABLE -- NotFound
    tratado explicitamente (df vazio, nao erro), mesmo padrao de
    load_io_plan_finding_status: a tabela so existe em douglas-bq-staging ate
    agora (ver core/OWNERSHIP.yaml), producao ainda nao tem nenhum par
    decidido -- e correto aparecer vazio la, nao quebrar a tela."""
    client = get_bq_client()
    cols = ["client_id_a", "client_id_b", "decision", "decided_by", "decided_at", "notes"]
    try:
        query = f"SELECT {', '.join(cols)} FROM `{project_id}.{CLIENT_MGMT_RECONCILIATION_TABLE}`"
        return client.query(query).to_dataframe()
    except NotFound:
        return pd.DataFrame(columns=cols)


def update_dim_client_fields(project_id: str, client_id: str, updates: dict) -> dict:
    """UPDATE real em core.dim_client, WHERE client_id=@client_id -- escrita
    real pedida explicitamente pela task (status/nome/hierarquia/import_io_plan
    sao UPDATE direto, dim_client nao segue SCD2 aqui, ver core/ddl/dim_client.sql).
    `updates` = dict coluna->valor ja no tipo Python certo (str/bool/int/None);
    o tipo BQ do parametro e inferido pelo tipo Python (STRING para str,
    BOOL para bool, INT64 para int) -- client_id NUNCA deve estar em updates
    (e a chave do WHERE, imutavel por design, ver core/ddl/dim_client.sql).
    Usa a writer SA impersonada, faturando no projeto selecionado na tela
    (mesmo padrao de get_writer_bq_client_for_project). Nunca lanca excecao
    pra UI -- retorna dict com 'ok' explicito."""
    if not updates:
        return {"ok": False, "detail": "Nenhum campo para atualizar."}
    _bq_type = {str: "STRING", bool: "BOOL", int: "INT64", type(None): "STRING"}
    try:
        client = get_writer_bq_client_for_project(project_id)
        set_clause = ", ".join(f"{col} = @{col}" for col in updates)
        sql = f"UPDATE `{project_id}.{CLIENT_MGMT_TABLE}` SET {set_clause} WHERE client_id = @client_id"
        params = [
            bigquery.ScalarQueryParameter(col, _bq_type.get(type(val), "STRING"), val)
            for col, val in updates.items()
        ]
        params.append(bigquery.ScalarQueryParameter("client_id", "STRING", client_id))
        client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
        return {"ok": True, "detail": "Cliente atualizado."}
    except Exception as exc:
        detail = f"Erro ao atualizar cliente: {exc}"
        if "403" in str(exc) or "Forbidden" in str(exc):
            detail += f" -- possivel falta de roles/bigquery.jobUser para `{WRITER_SA_EMAIL}` em `{project_id}`."
        return {"ok": False, "detail": detail}


def save_client_reconciliation_decision(
    project_id: str, client_id_a: str, client_id_b: str, decision: str, decided_by: str, notes: str,
) -> dict:
    """UPSERT (MERGE) em core.dim_client_reconciliation -- mesmo padrao de
    save_io_plan_finding_status. `client_id_a`/`client_id_b` devem chegar ja
    ordenados (menor primeiro, ver detect_duplicate_candidates) -- esta
    funcao nao reordena sozinha, quem chama e responsavel (evita reordenar 2x
    por engano). Nunca lanca excecao pra UI -- sempre retorna dict com 'ok'
    explicito (mesmo padrao de erro claro em vez de sucesso fingido)."""
    try:
        client = get_writer_bq_client_for_project(project_id)
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("client_id_a", "STRING", client_id_a),
            bigquery.ScalarQueryParameter("client_id_b", "STRING", client_id_b),
            bigquery.ScalarQueryParameter("decision", "STRING", decision),
            bigquery.ScalarQueryParameter("decided_by", "STRING", decided_by),
            bigquery.ScalarQueryParameter("notes", "STRING", notes or None),
        ])
        sql = f"""
        MERGE `{project_id}.{CLIENT_MGMT_RECONCILIATION_TABLE}` T
        USING (SELECT @client_id_a AS client_id_a, @client_id_b AS client_id_b) S
        ON T.client_id_a = S.client_id_a AND T.client_id_b = S.client_id_b
        WHEN MATCHED THEN UPDATE SET
          decision = @decision, decided_by = @decided_by, notes = @notes, decided_at = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (client_id_a, client_id_b, decision, decided_by, notes, decided_at)
          VALUES (@client_id_a, @client_id_b, @decision, @decided_by, @notes, CURRENT_TIMESTAMP())
        """
        client.query(sql, job_config=job_config).result()
        return {"ok": True, "detail": "Decisao salva."}
    except NotFound:
        return {
            "ok": False,
            "detail": (
                f"Tabela `{project_id}.{CLIENT_MGMT_RECONCILIATION_TABLE}` ainda nao existe neste projeto -- "
                "aplicar core/ddl/dim_client_reconciliation.sql antes de decidir aqui."
            ),
        }
    except Exception as exc:
        detail = f"Erro ao salvar decisao: {exc}"
        if "403" in str(exc) or "Forbidden" in str(exc):
            detail += f" -- possivel falta de roles/bigquery.jobUser para `{WRITER_SA_EMAIL}` em `{project_id}`."
        return {"ok": False, "detail": detail}


def deactivate_duplicate_client(
    project_id: str, duplicate_client_id: str, duplicate_name: str,
    survivor_client_id: str, survivor_name: str, decided_by: str,
) -> dict:
    """Confirma 'mesmo cliente' -- desativa o client_id duplicado
    (status='inactive') com nota apontando pro sobrevivente, e registra a
    decisao 'same' em CLIENT_MGMT_RECONCILIATION_TABLE. NAO mescla dado
    historico de fact_delivery/io_plan/platform_client_links -- isso seria
    mudar o pipeline (fora do escopo do hub-frontend); fica registrado como
    proximo passo se o Douglas decidir que precisa. As duas escritas
    (dim_client + reconciliation) sao sequenciais, nao atomicas -- se a
    segunda falhar, o UPDATE de dim_client ja aconteceu (reportado
    explicitamente pra UI, nunca escondido)."""
    note = (
        f"Desativado em {date.today().isoformat()} -- confirmado como duplicata de "
        f"'{survivor_name}' ({survivor_client_id}) por {decided_by} via Hub."
    )
    update_result = update_dim_client_fields(project_id, duplicate_client_id, {"status": "inactive", "notes": note})
    if not update_result["ok"]:
        return update_result
    id_a, id_b = sorted([duplicate_client_id, survivor_client_id])
    decision_result = save_client_reconciliation_decision(
        project_id, id_a, id_b, "same", decided_by,
        f"'{duplicate_name}' ({duplicate_client_id}) desativado como duplicata de '{survivor_name}' ({survivor_client_id}).",
    )
    if not decision_result["ok"]:
        return {
            "ok": False,
            "detail": (
                f"Cliente '{duplicate_name}' foi desativado com sucesso, mas a decisao NAO foi "
                f"registrada em {CLIENT_MGMT_RECONCILIATION_TABLE} ({decision_result['detail']}) -- "
                "o par pode voltar a aparecer como candidato a duplicata na proxima carga."
            ),
        }
    return {"ok": True, "detail": f"'{duplicate_name}' desativado como duplicata de '{survivor_name}'."}


# ─────────────────────────────────────────────────────────────────────────
# Saude do IO Plan -- deteccao proativa de incongruencia mensal por cliente
# (task Notion pendente de anexar, pedido do Douglas 2026-09-06). Motivada por
# 2 incidentes reais confirmados no mesmo dia em core.io_plan_manual:
#   Caso 1 -- Cora, flight 2026-08-11/31: planned_impressions=886444,
#     planned_spend_gross=12500, IDENTICOS a um flight de Maio (2026-05-01/10)
#     completamente diferente. Causa raiz confirmada via source_file: o arquivo
#     e "Plano_NEWAD_CORA_MAIO_JUNHO_JULHO_V3_08_05_26 (1) (1).xlsx" -- sufixo
#     "(1) (1)" e o padrao classico de arquivo duplicado do Google Drive,
#     pousado na pasta errada (Agosto em vez de Maio/Junho/Julho).
#   Caso 2 -- Cora, flight de Setembro: campo "Periodo" da planilha preenchido
#     como "Julho" por engano (usaram como referencia um arquivo do Rafael,
#     descartado, e nao ajustaram o periodo). Nao aparece como coluna own no
#     schema atual (nem raw.io_plan_drive_snapshot.flight_label carrega esse
#     texto para o Sept -- vem NULL) -- por isso a heuristica de "nome de
#     arquivo parecido -> multiplos flights" e a defesa principal aqui,
#     complementar a comparacao de valores.
#
# Fonte escolhida apos auditoria do schema real (2026-09-06): core.io_plan_manual
# -- e a tabela ja agregada por client_id+flight (grain que casa com "um card
# por flight, um flight por linha"), enquanto raw.io_plan_drive_snapshot e
# grain de linha de estrategia (formato/plataforma), mais granular do que o
# necessario para esta tela. gold.fact_io_plan e VIEW derivada de
# core.io_plan_manual -- ler a fonte, nao a view.
# IMPORTANTE: core.io_plan_manual pode ter MAIS DE UMA LINHA para o mesmo
# client_id+flight_start+flight_end (plan_version diferente, ex. um plano
# manual antigo "PLANO-JAN-MAR" sendo substituido depois por "DRIVE-SYNC") --
# ver dedupe_latest_per_flight() abaixo, que sempre reduz para 1 linha por
# flight antes de qualquer deteccao de duplicata/salto.
IO_PLAN_DUPLICATE_VALUE_FIELDS = ["planned_impressions", "planned_clicks", "planned_spend_gross"]
IO_PLAN_BIG_JUMP_PCT_THRESHOLD = 60  # % -- limiar de "salto grande" para revisao humana, nao bloqueio
IO_PLAN_ADJACENT_GAP_DAYS = 2  # tolerancia entre flight_end de um flight e flight_start do proximo para considerar "consecutivo"

# rotulo amigavel + severidade (usada so pra ordenar a exibicao, nao pra badge de cor --
# ver IO_PLAN_SEVERITY_STYLE) por tipo de achado.
IO_PLAN_ISSUE_SEVERITY_STYLE = {
    "duplicata_valores": ("Valores identicos entre flights diferentes", "red"),
    "arquivo_duplicado": ("Mesmo arquivo (ou variante) em mais de um periodo", "red"),
    "salto_grande": ("Salto grande vs. mes anterior", "orange"),
    "gap_cobertura": ("Mes sem nenhum flight (gap de cobertura)", "gray"),
    "multiplas_versoes": ("Mais de uma versao carregada para o mesmo flight", "blue"),
}


@st.cache_data(ttl=300)
def load_io_plan_manual(project_id: str) -> pd.DataFrame:
    """core.io_plan_manual + nome do cliente (LEFT JOIN dim_client -- cliente
    sem match ainda aparece com o client_id cru, nunca quebra a query). So
    leitura, SA principal (mesmo client de load_table_metadata)."""
    client = get_bq_client()
    query = f"""
    SELECT
      p.client_id,
      COALESCE(c.name, p.client_id) AS client_name,
      p.flight_start,
      p.flight_end,
      p.planned_impressions,
      p.planned_clicks,
      p.planned_spend_gross,
      p.planned_spend_net,
      p.plan_version,
      p.source_file,
      p.loaded_at
    FROM `{project_id}.core.io_plan_manual` p
    LEFT JOIN `{project_id}.core.dim_client` c USING (client_id)
    ORDER BY p.client_id, p.flight_start
    """
    return client.query(query).to_dataframe()


@st.cache_data(ttl=300)
def load_io_plan_raw_detail(project_id: str) -> pd.DataFrame:
    """Detalhe linha-item de raw.io_plan_drive_snapshot -- descartada como
    fonte do agregado principal (grain errado pra 'um card por mes'), mas
    pedida de volta pelo Douglas (2026-09-06) como DRILL-DOWN dentro do card
    do mes: quando um alerta aparece, ele precisa ver o 'raio-x' (quantos
    arquivos alimentaram aquele flight, quebra por estrategia/plataforma,
    impressions_cpm VS impressions_est lado a lado -- o bug real do
    COALESCE vs SOMA que ele mesmo achou e corrigiu em sync_drive.py so da
    pra auditar visualmente vendo os dois campos junto) sem abrir o BigQuery
    manualmente toda vez.

    Carrega TODOS os clientes de uma vez (nao 1 query por flight/card) --
    a UI filtra em memoria por client_id+flight_start+flight_end. QUALIFY
    ROW_NUMBER() dedupe pra manter so a snapshot mais recente de cada
    (client_id, flight_start, flight_end, strategy_name, source_file) --
    mesmo raciocinio de stg/ddl (ver stg.io_plan, que dedupa por snapshot_at
    DESC), so que aqui MANTEMOS source_file no grain do dedupe (a view
    stg.io_plan nao inclui) porque o 1o pedido do drill-down e exatamente
    'quantos arquivos alimentaram este periodo' -- colapsar por source_file
    perderia esse sinal."""
    client = get_bq_client()
    query = f"""
    SELECT * EXCEPT(_rn) FROM (
      SELECT
        client_id, flight_start, flight_end, flight_label, drive_folder,
        source_file, strategy_name, platform, format, buy_model,
        impressions_cpm, impressions_est, monthly_spend, unit_price,
        clicks, snapshot_at,
        ROW_NUMBER() OVER (
          PARTITION BY client_id, flight_start, flight_end, strategy_name, source_file
          ORDER BY snapshot_at DESC
        ) AS _rn
      FROM `{project_id}.raw.io_plan_drive_snapshot`
      WHERE flight_start IS NOT NULL AND flight_end IS NOT NULL
    )
    WHERE _rn = 1
    ORDER BY client_id, flight_start, strategy_name
    """
    return client.query(query).to_dataframe()


# Nomes de heuristica -- MESMAS chaves usadas em build_io_plan_health_report()
# (duplicata_valores, arquivo_duplicado, salto_grande, gap_cobertura,
# multiplas_versoes). io_plan_finding_status.heuristic_name usa exatamente
# esses valores -- nunca reinventar um rotulo novo aqui, ou o JOIN de status
# persistido com o achado ao vivo (join_finding_status) quebra silenciosamente.
IO_PLAN_FINDING_STATUS_TABLE = "core.io_plan_finding_status"
IO_PLAN_STATUS_LABELS = {
    "pendente": ("Pendente", "gray", ":material/hourglass_empty:"),
    "resolvido": ("Resolvido", "green", ":material/check_circle:"),
    "esperado": ("Esperado/Correto assim", "blue", ":material/verified:"),
}


@st.cache_data(ttl=60)
def load_io_plan_finding_status(project_id: str) -> pd.DataFrame:
    """Estado de tratamento humano persistido em `core.io_plan_finding_status`
    (ver DDL em core/ddl/io_plan_finding_status.sql) -- NAO existe em todo
    ambiente ainda (aplicado em douglas-bq-staging 2026-09-06; producao
    pendente de decisao do Douglas, ver comentario de
    get_writer_bq_client_for_project). Trata NotFound explicitamente (df
    vazio, nao erro) -- a tela toda deve continuar funcionando (todo achado
    aparece 'pendente' por default) mesmo antes da tabela existir naquele
    projeto."""
    client = get_bq_client()
    try:
        query = f"""
        SELECT client_id, flight_start, flight_end, heuristic_name, status, comment, updated_by, updated_at
        FROM `{project_id}.{IO_PLAN_FINDING_STATUS_TABLE}`
        """
        return client.query(query).to_dataframe()
    except NotFound:
        return pd.DataFrame(columns=["client_id", "flight_start", "flight_end", "heuristic_name", "status", "comment", "updated_by", "updated_at"])


def join_finding_status(flight_issues: dict, status_df: pd.DataFrame) -> dict:
    """Pura -- funde o indice ao vivo flight->achados (build_flight_issue_index)
    com o status persistido (load_io_plan_finding_status), por
    (client_id, flight_start, flight_end, heuristic_name). Achado sem linha
    de status ainda vira 'pendente' (default implicito, ver DDL -- nunca
    precisa INSERT automatico quando o achado nasce). Cada dict de achado
    ganha 3 chaves novas: status, comment, status_updated_at -- sem alterar
    as chaves originais (severity/label/detail) que o resto da UI ja usa."""
    status_lookup = {
        (r.client_id, r.flight_start, r.flight_end, r.heuristic_name): r
        for r in status_df.itertuples()
    } if not status_df.empty else {}

    merged = {}
    for key, issues in flight_issues.items():
        client_id, flight_start, flight_end = key
        merged_issues = []
        for issue in issues:
            status_row = status_lookup.get((client_id, flight_start, flight_end, issue["heuristic_name"]))
            merged_issue = dict(issue)
            merged_issue["status"] = status_row.status if status_row is not None else "pendente"
            merged_issue["comment"] = status_row.comment if status_row is not None else None
            merged_issue["status_updated_at"] = status_row.updated_at if status_row is not None else None
            merged_issues.append(merged_issue)
        merged[key] = merged_issues
    return merged


def save_io_plan_finding_status(
    project_id: str, client_id: str, flight_start, flight_end,
    heuristic_name: str, status: str, comment: str, updated_by: str = "Douglas",
) -> dict:
    """UPSERT (MERGE) em core.io_plan_finding_status via writer SA impersonada,
    faturando no MESMO projeto que a aba esta olhando no momento (ver
    get_writer_bq_client_for_project). Nunca lanca excecao pra UI -- sempre
    retorna dict com 'ok' explicito (mesmo padrao de call_io_plan_admin_sync/
    call_fact_pacing_refresh), pra tela poder mostrar erro real (ex: 403 por
    falta de jobUser em producao) em vez de fingir sucesso."""
    try:
        client = get_writer_bq_client_for_project(project_id)
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
                bigquery.ScalarQueryParameter("flight_start", "DATE", flight_start),
                bigquery.ScalarQueryParameter("flight_end", "DATE", flight_end),
                bigquery.ScalarQueryParameter("heuristic_name", "STRING", heuristic_name),
                bigquery.ScalarQueryParameter("status", "STRING", status),
                bigquery.ScalarQueryParameter("comment", "STRING", comment or None),
                bigquery.ScalarQueryParameter("updated_by", "STRING", updated_by),
            ]
        )
        sql = f"""
        MERGE `{project_id}.{IO_PLAN_FINDING_STATUS_TABLE}` T
        USING (SELECT @client_id AS client_id, @flight_start AS flight_start,
                      @flight_end AS flight_end, @heuristic_name AS heuristic_name) S
        ON T.client_id = S.client_id AND T.flight_start = S.flight_start
           AND T.flight_end = S.flight_end AND T.heuristic_name = S.heuristic_name
        WHEN MATCHED THEN UPDATE SET
          status = @status, comment = @comment, updated_by = @updated_by, updated_at = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (client_id, flight_start, flight_end, heuristic_name, status, comment, updated_by, updated_at)
          VALUES (@client_id, @flight_start, @flight_end, @heuristic_name, @status, @comment, @updated_by, CURRENT_TIMESTAMP())
        """
        client.query(sql, job_config=job_config).result()
        return {"ok": True, "detail": "Status salvo."}
    except NotFound:
        return {
            "ok": False,
            "detail": (
                f"Tabela `{project_id}.{IO_PLAN_FINDING_STATUS_TABLE}` ainda nao existe neste projeto -- "
                "aplicar core/ddl/io_plan_finding_status.sql via apply_ddl.py antes de salvar status aqui."
            ),
        }
    except Exception as exc:
        detail = f"Erro ao salvar status: {exc}"
        if "403" in str(exc) or "Forbidden" in str(exc):
            detail += (
                f" -- possivel falta de roles/bigquery.jobUser para `{WRITER_SA_EMAIL}` em `{project_id}` "
                "(gap conhecido em producao, ver get_writer_bq_client_for_project)."
            )
        return {"ok": False, "detail": detail}


# ─────────────────────────────────────────────────────────────────────────
# Gerenciamento de Formatos/Regras -- core.dict_format (platform+formato ->
# goal_type) e core.strategy_format_map (keyword -> formato), mais a fila de
# "estrategias nao classificadas". Task Notion 3d49d0f6219e81a4bc8cea05bd3fdd72
# (2026-09-07) -- motivador real: "Audio Ads" da Casa do Construtor cai como
# formato=NULL em stg.io_plan porque nenhuma keyword de core.strategy_format_map
# bate com o texto. As duas tabelas ja existem em staging E producao (backend
# ja aplicou, ja fez seed das 6 keywords antigas do CASE WHEN hardcoded, ja
# reescreveu stg/ddl/io_plan.sql pra chamar core.resolve_strategy_format() nos
# dois ambientes -- confirmado ao vivo, 2026-09-07) -- este modulo so cobre a
# TELA (CRUD + fila), nada de DDL/pipeline aqui.
# Mesmo padrao SCD2 do resto do repo (client_business_rules, campaign_format_map,
# advertiser_platform_rules): NUNCA UPDATE do valor de uma linha vigente --
# fechar (effective_to = data) + INSERT nova linha. Nenhuma das duas tabelas
# tem coluna de id proprio -- a "chave natural" pra fechar uma versao vigente
# e (platform, formato) em dict_format e (keyword) em strategy_format_map,
# sempre combinada com `effective_to IS NULL` como guarda-corpo.
FORMAT_DICT_TABLE = "core.dict_format"
STRATEGY_FORMAT_MAP_TABLE = "core.strategy_format_map"
FORMAT_PLATFORM_OPTIONS = ["mediasmart", "mgid", "siprocal", "io_plan"]
FORMAT_GOAL_TYPE_OPTIONS = ["CPM", "CPC", "CPI"]


@st.cache_data(ttl=60)
def load_dict_format(project_id: str) -> pd.DataFrame:
    """Todas as linhas (historico incluido) de core.dict_format -- a UI separa
    vigente (effective_to IS NULL) de historico na exibicao, nao aqui. So
    leitura, SA principal."""
    client = get_bq_client()
    query = f"""
    SELECT platform, formato, goal_type, notes, confirmed_by, created_at, effective_from, effective_to
    FROM `{project_id}.{FORMAT_DICT_TABLE}`
    ORDER BY formato, effective_from DESC
    """
    return client.query(query).to_dataframe()


@st.cache_data(ttl=60)
def load_strategy_format_map(project_id: str) -> pd.DataFrame:
    """Todas as linhas (historico incluido) de core.strategy_format_map. So
    leitura, SA principal."""
    client = get_bq_client()
    query = f"""
    SELECT keyword, formato, notes, confirmed_by, created_at, effective_from, effective_to
    FROM `{project_id}.{STRATEGY_FORMAT_MAP_TABLE}`
    ORDER BY keyword
    """
    return client.query(query).to_dataframe()


# ─────────────────────────────────────────────────────────────────────────
# 4a secao da aba Formatos/Regras -- core.advertiser_platform_rules (remapeia
# platform_from='unknown' -> platform_to real, por formato, opcionalmente por
# cliente). Pedido do orquestrador 2026-09-07, MESMO DIA em que o backend
# estendeu client_id pra aceitar NULL (regra GLOBAL, vale pra todo cliente sem
# override especifico) -- ver core/ddl/advertiser_platform_rules.sql,
# core/ddl/resolve_platform_rule.sql, core/migration/11_advertiser_platform_rules_
# allow_global.sql. Mesmo padrao SCD2 das outras 2 secoes (dict_format,
# strategy_format_map) -- nunca UPDATE do valor, so fechar effective_to + INSERT.
#
# ATENCAO -- GAP DE PROMOCAO CONFIRMADO AO VIVO (2026-09-07): a migracao pra
# NULLABLE + o resolve_platform_rule() novo (com prioridade especifico >
# geral) SO foram aplicados em douglas-bq-staging ate agora -- `adframework`
# (producao) ainda tem client_id STRING REQUIRED e a versao ANTIGA da funcao
# (sem suporte a NULL). Rodar INSERT com client_id=NULL em producao quebraria
# com erro de NOT NULL constraint. Por isso check_advertiser_rules_supports_global()
# checa o modo real da coluna ANTES de oferecer a opcao "Global" na UI --
# nunca assumido fixo, sempre perguntado ao BigQuery ao vivo (schema pode ser
# promovido pra producao a qualquer momento sem eu saber com antecedencia).
ADVERTISER_PLATFORM_RULES_TABLE = "core.advertiser_platform_rules"


@st.cache_data(ttl=300)
def check_advertiser_rules_supports_global(project_id: str) -> bool:
    """True se client_id em core.advertiser_platform_rules ja aceita NULL
    (migracao 11_advertiser_platform_rules_allow_global.sql aplicada) neste
    projeto especifico -- checado ao vivo via metadado de schema (nao um
    valor fixo), porque staging e producao podem estar em estagios diferentes
    da migracao (confirmado ao vivo 2026-09-07: staging sim, producao ainda
    nao). So leitura de metadado, SA principal."""
    client = get_bq_client()
    table = client.get_table(f"{project_id}.{ADVERTISER_PLATFORM_RULES_TABLE}")
    field = next((f for f in table.schema if f.name == "client_id"), None)
    return field is not None and field.mode == "NULLABLE"


@st.cache_data(ttl=60)
def load_advertiser_platform_rules(project_id: str) -> pd.DataFrame:
    """Todas as linhas (historico incluido) de core.advertiser_platform_rules
    + nome do cliente (LEFT JOIN dim_client -- client_id NULL/regra global
    fica com client_name NULL de proposito, a UI trata isso como 'TODOS OS
    CLIENTES', nao como cliente nao encontrado). So leitura, SA principal."""
    client = get_bq_client()
    query = f"""
    SELECT
      r.client_id, c.name AS client_name, r.platform_from, r.formato, r.platform_to,
      r.confirmed_at, r.confirmed_by, r.notes, r.effective_from, r.effective_to
    FROM `{project_id}.{ADVERTISER_PLATFORM_RULES_TABLE}` r
    LEFT JOIN `{project_id}.core.dim_client` c ON c.client_id = r.client_id
    ORDER BY r.platform_from, r.formato, r.effective_from DESC
    """
    return client.query(query).to_dataframe()


def _platform_rule_active_count(project_id: str, client_id: str | None, platform_from: str, formato: str) -> int:
    """Guarda-corpo antes de INSERT -- checa se ja existe versao vigente pra
    essa chave natural (client_id, platform_from, formato). Comparacao de
    client_id e NULL-safe (client_id pode ser NULL = regra global) --
    `col = @param` nunca e verdadeiro quando ambos os lados sao NULL em SQL
    padrao, por isso o OR explicito. So leitura, SA principal."""
    client = get_bq_client()
    query = f"""
    SELECT COUNT(*) AS n FROM `{project_id}.{ADVERTISER_PLATFORM_RULES_TABLE}`
    WHERE platform_from = @platform_from AND formato = @formato
      AND (client_id = @client_id OR (client_id IS NULL AND @client_id IS NULL))
      AND effective_to IS NULL
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
        bigquery.ScalarQueryParameter("platform_from", "STRING", platform_from),
        bigquery.ScalarQueryParameter("formato", "STRING", formato),
    ])
    return int(client.query(query, job_config=job_config).to_dataframe()["n"].iloc[0])


def close_advertiser_platform_rule(project_id: str, client_id: str | None, platform_from: str, formato: str) -> dict:
    """Fecha (effective_to = CURRENT_DATE()) a linha vigente que casa com a
    chave natural (client_id NULL-safe, ver _platform_rule_active_count).
    Escreve com a writer SA impersonada, mesmo projeto selecionado na tela.
    Nunca lanca excecao pra UI -- retorna dict com 'ok' explicito."""
    try:
        client = get_writer_bq_client_for_project(project_id)
        sql = f"""
        UPDATE `{project_id}.{ADVERTISER_PLATFORM_RULES_TABLE}`
        SET effective_to = CURRENT_DATE()
        WHERE platform_from = @platform_from AND formato = @formato
          AND (client_id = @client_id OR (client_id IS NULL AND @client_id IS NULL))
          AND effective_to IS NULL
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
            bigquery.ScalarQueryParameter("platform_from", "STRING", platform_from),
            bigquery.ScalarQueryParameter("formato", "STRING", formato),
        ])
        client.query(sql, job_config=job_config).result()
        return {"ok": True, "detail": "Vigencia encerrada."}
    except Exception as exc:
        detail = f"Erro ao encerrar vigencia: {exc}"
        if "403" in str(exc) or "Forbidden" in str(exc):
            detail += f" -- possivel falta de roles/bigquery.jobUser para `{WRITER_SA_EMAIL}` em `{project_id}`."
        return {"ok": False, "detail": detail}


def add_advertiser_platform_rule(
    project_id: str, client_id: str | None, platform_from: str, formato: str,
    platform_to: str, confirmed_by: str, notes: str,
) -> dict:
    """INSERT de uma nova versao vigente, seguindo o procedimento SCD2
    documentado em core/ddl/advertiser_platform_rules.sql: fecha qualquer
    versao vigente da MESMA chave natural (no-op se nao houver nenhuma) +
    insere a linha nova (confirmed_at/effective_from=CURRENT_DATE(),
    effective_to=NULL). `formato` sempre normalizado pra UPPER aqui --
    core.resolve_platform_rule() compara com UPPER(p_formato), e os dados
    existentes ja seguem essa convencao (ex: 'PUSH', 'ÁUDIO'). Escreve com a
    writer SA impersonada. Nunca lanca excecao pra UI."""
    try:
        formato_upper = formato.strip().upper()
        client = get_writer_bq_client_for_project(project_id)
        if _platform_rule_active_count(project_id, client_id, platform_from, formato_upper):
            close_result = close_advertiser_platform_rule(project_id, client_id, platform_from, formato_upper)
            if not close_result["ok"]:
                return close_result
        sql = f"""
        INSERT INTO `{project_id}.{ADVERTISER_PLATFORM_RULES_TABLE}`
          (client_id, platform_from, formato, platform_to, confirmed_at, confirmed_by, notes, effective_from, effective_to)
        VALUES (@client_id, @platform_from, @formato, @platform_to, CURRENT_DATE(), @confirmed_by, @notes, CURRENT_DATE(), NULL)
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
            bigquery.ScalarQueryParameter("platform_from", "STRING", platform_from),
            bigquery.ScalarQueryParameter("formato", "STRING", formato_upper),
            bigquery.ScalarQueryParameter("platform_to", "STRING", platform_to),
            bigquery.ScalarQueryParameter("confirmed_by", "STRING", confirmed_by),
            bigquery.ScalarQueryParameter("notes", "STRING", notes),
        ])
        client.query(sql, job_config=job_config).result()
        return {"ok": True, "detail": "Regra criada."}
    except Exception as exc:
        detail = f"Erro ao criar regra: {exc}"
        if "403" in str(exc) or "Forbidden" in str(exc):
            detail += f" -- possivel falta de roles/bigquery.jobUser para `{WRITER_SA_EMAIL}` em `{project_id}`."
        return {"ok": False, "detail": detail}


@st.cache_data(ttl=300)
def load_dim_client_options(project_id: str) -> pd.DataFrame:
    """client_id+name de core.dim_client, escopado ao `project_id` selecionado
    na tela (staging e producao podem ter conjuntos de clientes diferentes --
    diferente de load_client_options(), fixa em PROJECT_ID/producao, usada em
    outras abas que nao tem seletor dual). So leitura, SA principal."""
    client = get_bq_client()
    query = f"SELECT client_id, name FROM `{project_id}.core.dim_client` WHERE status = 'active' ORDER BY name"
    return client.query(query).to_dataframe()


@st.cache_data(ttl=60)
def load_unclassified_strategies(project_id: str) -> pd.DataFrame:
    """strategy_name distintos de stg.io_plan que resolvem formato=NULL hoje --
    core.resolve_strategy_format() ja roda dentro da propria view (backend ja
    migrou stg/ddl/io_plan.sql, 2026-09-07), entao esta query so precisa ler o
    resultado, nao reimplementar a logica de match de keyword aqui. Uma linha
    por strategy_name, com contexto (linhas/clientes/flights afetados) pra
    ajudar a decisao -- sem isso a fila e so uma lista de texto sem prioridade
    visivel. So leitura, SA principal -- funciona em qualquer ambiente onde
    stg.io_plan exista, mesmo antes de core.strategy_format_map ganhar
    qualquer linha nova."""
    client = get_bq_client()
    query = f"""
    SELECT
      p.strategy_name,
      COUNT(*) AS n_linhas,
      COUNT(DISTINCT p.client_id) AS n_clientes,
      COUNT(DISTINCT CONCAT(CAST(p.flight_start AS STRING), '|', CAST(p.flight_end AS STRING))) AS n_flights,
      STRING_AGG(DISTINCT COALESCE(c.name, p.client_id), ', ' ORDER BY COALESCE(c.name, p.client_id) LIMIT 5) AS clientes_exemplo
    FROM `{project_id}.stg.io_plan` p
    LEFT JOIN `{project_id}.core.dim_client` c USING (client_id)
    WHERE p.formato IS NULL
    GROUP BY p.strategy_name
    ORDER BY n_linhas DESC
    """
    return client.query(query).to_dataframe()


def _scd2_active_count(project_id: str, table: str, filters: dict) -> int:
    """Pura o suficiente (so um SELECT COUNT) -- guarda-corpo generico pra
    checar se ja existe versao vigente (effective_to IS NULL) pra uma chave
    natural antes de deixar inserir uma linha nova, mesmo raciocinio ja usado
    em business_rule_exists_active. `filters` = dict coluna->valor (STRING),
    combinados com AND. So leitura, SA principal."""
    client = get_bq_client()
    where = " AND ".join(f"{k} = @{k}" for k in filters)
    query = f"SELECT COUNT(*) AS n FROM `{project_id}.{table}` WHERE {where} AND effective_to IS NULL"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter(k, "STRING", v) for k, v in filters.items()]
    )
    return int(client.query(query, job_config=job_config).to_dataframe()["n"].iloc[0])


def _scd2_close_active(project_id: str, table: str, filters: dict) -> dict:
    """UPDATE generico pra fechar a(s) linha(s) vigente(s) (effective_to =
    CURRENT_DATE()) que casam com `filters` (chave natural) -- NUNCA toca o
    valor de negocio da linha (formato/goal_type), so a vigencia. Escreve com
    a writer SA impersonada, faturando no MESMO projeto selecionado na tela
    (get_writer_bq_client_for_project -- mesmo padrao/gap de IAM ja documentado
    la: funciona em staging, pode faltar jobUser em producao). Nunca lanca
    excecao pra UI -- retorna dict com 'ok' explicito."""
    try:
        client = get_writer_bq_client_for_project(project_id)
        where = " AND ".join(f"{k} = @{k}" for k in filters)
        sql = f"UPDATE `{project_id}.{table}` SET effective_to = CURRENT_DATE() WHERE {where} AND effective_to IS NULL"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter(k, "STRING", v) for k, v in filters.items()]
        )
        client.query(sql, job_config=job_config).result()
        return {"ok": True, "detail": "Vigencia encerrada."}
    except Exception as exc:
        detail = f"Erro ao encerrar vigencia: {exc}"
        if "403" in str(exc) or "Forbidden" in str(exc):
            detail += f" -- possivel falta de roles/bigquery.jobUser para `{WRITER_SA_EMAIL}` em `{project_id}`."
        return {"ok": False, "detail": detail}


def _scd2_insert_new_version(project_id: str, table: str, values: dict, close_filters: dict | None = None) -> dict:
    """INSERT generico de uma nova versao vigente, seguindo o procedimento SCD2
    documentado em core/ddl/dict_format.sql e core/ddl/strategy_format_map.sql:
    1) fecha qualquer versao vigente da MESMA chave natural (close_filters,
    se houver -- no-op se nao houver nenhuma, caso comum de formato/keyword
    genuinamente novo), 2) insere a linha nova com effective_from=CURRENT_DATE(),
    effective_to=NULL, created_at=CURRENT_DATE(). `values` = dict coluna->valor
    (STRING) das colunas de negocio (ex: platform/formato/goal_type/notes/
    confirmed_by ou keyword/formato/notes/confirmed_by). Escreve com a writer
    SA impersonada, mesmo projeto selecionado na tela. Nunca lanca excecao pra
    UI -- retorna dict com 'ok' explicito."""
    try:
        client = get_writer_bq_client_for_project(project_id)
        if close_filters:
            close_result = _scd2_close_active(project_id, table, close_filters)
            if not close_result["ok"]:
                return close_result
        cols = list(values.keys())
        col_list = ", ".join(cols + ["created_at", "effective_from", "effective_to"])
        val_list = ", ".join(f"@{c}" for c in cols) + ", CURRENT_DATE(), CURRENT_DATE(), NULL"
        sql = f"INSERT INTO `{project_id}.{table}` ({col_list}) VALUES ({val_list})"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter(c, "STRING", v) for c, v in values.items()]
        )
        client.query(sql, job_config=job_config).result()
        return {"ok": True, "detail": "Regra criada."}
    except Exception as exc:
        detail = f"Erro ao criar regra: {exc}"
        if "403" in str(exc) or "Forbidden" in str(exc):
            detail += f" -- possivel falta de roles/bigquery.jobUser para `{WRITER_SA_EMAIL}` em `{project_id}`."
        return {"ok": False, "detail": detail}


def normalize_source_file(name) -> str:
    """Pura -- normaliza nome de arquivo pra comparacao de 'mesmo arquivo ou
    variante duplicada do Drive': lowercase, underscore vira espaco (Drive as
    vezes salva a mesma copia com um caractere trocado), colapsa espacos
    multiplos, remove extensao e remove QUALQUER numero de sufixo
    ' (N)' repetido no fim (padrao de duplicata do Google Drive/Windows --
    'arquivo (1) (1).xlsx', 'arquivo (2).xlsx' etc. viram todos 'arquivo').
    Retorna '' para valor vazio/None -- quem chama trata '' como 'sem
    comparacao possivel', nunca como match entre dois arquivos sem nome."""
    if not name or not isinstance(name, str):
        return ""
    s = name.strip().lower().replace("_", " ")
    s = re.sub(r"\.(xlsx|xls|csv)$", "", s)
    while True:
        new_s = re.sub(r"\s*\(\d+\)\s*$", "", s).strip()
        if new_s == s:
            break
        s = new_s
    s = re.sub(r"\s+", " ", s).strip()
    return s


def dedupe_latest_per_flight(df: pd.DataFrame) -> pd.DataFrame:
    """Pura -- reduz core.io_plan_manual para 1 linha por
    client_id+flight_start+flight_end (a de loaded_at mais recente). Existe
    porque a tabela pode ter mais de uma versao carregada pro mesmo flight
    (ex: plan_version 'PLANO-JAN-MAR' substituido depois por 'DRIVE-SYNC') --
    sem isso, qualquer deteccao de duplicata/salto compararia versoes velhas
    contra novas do MESMO periodo, gerando falso positivo. df vazio ou sem as
    colunas esperadas volta como veio (funcao nao deve quebrar em df vazio)."""
    if df.empty:
        return df
    return (
        df.sort_values("loaded_at")
        .groupby(["client_id", "flight_start", "flight_end"], as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )


def detect_multiple_versions(df: pd.DataFrame) -> pd.DataFrame:
    """Pura -- lista flights (client_id+flight_start+flight_end) com mais de
    uma linha em core.io_plan_manual (antes do dedupe), so informativo -- nao
    e por si so um erro (substituicao de plano e esperada), mas vale visibilidade
    de quantas versoes um flight acumulou."""
    if df.empty:
        return pd.DataFrame(columns=["client_id", "client_name", "flight_start", "flight_end", "n_versoes", "versoes"])
    grouped = (
        df.groupby(["client_id", "client_name", "flight_start", "flight_end"])
        .agg(n_versoes=("plan_version", "count"), versoes=("plan_version", lambda s: sorted(set(s.dropna()))))
        .reset_index()
    )
    grouped = grouped[grouped["n_versoes"] > 1].sort_values(["client_id", "flight_start"])
    grouped["flight_key"] = list(zip(grouped["flight_start"], grouped["flight_end"]))
    return grouped


def detect_value_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Pura -- opera sobre o df JA deduplicado (dedupe_latest_per_flight).
    Agrupa por client_id + a combinacao exata de
    IO_PLAN_DUPLICATE_VALUE_FIELDS; qualquer grupo com >1 flight distinto e
    suspeito (mesmo numero planejado em 2 periodos diferentes -- e exatamente
    o Caso 1 real: 886444 impressoes / 12500 de spend em Maio E em Agosto).
    Ignora linhas com todos os campos de comparacao nulos/zero (nao ha o que
    comparar) para nao gerar ruido de 'ambos vazios'."""
    if df.empty:
        return pd.DataFrame(columns=["client_id", "client_name", "flights", "planned_impressions", "planned_clicks", "planned_spend_gross"])
    comparable = df.dropna(subset=IO_PLAN_DUPLICATE_VALUE_FIELDS, how="all").copy()
    comparable = comparable[(comparable[IO_PLAN_DUPLICATE_VALUE_FIELDS].fillna(0) != 0).any(axis=1)]
    if comparable.empty:
        return pd.DataFrame(columns=["client_id", "client_name", "flights", "planned_impressions", "planned_clicks", "planned_spend_gross"])

    rows = []
    group_cols = ["client_id"] + IO_PLAN_DUPLICATE_VALUE_FIELDS
    for key, group in comparable.groupby(group_cols, dropna=False):
        if len(group) < 2:
            continue
        client_id = key[0]
        flight_keys = sorted((r.flight_start, r.flight_end) for r in group.itertuples())
        rows.append({
            "client_id": client_id,
            "client_name": group["client_name"].iloc[0],
            "flight_keys": flight_keys,
            "flights": [f"{s} a {e}" for s, e in flight_keys],
            "planned_impressions": key[1],
            "planned_clicks": key[2],
            "planned_spend_gross": key[3],
        })
    return pd.DataFrame(rows)


def detect_source_file_reuse(df: pd.DataFrame) -> pd.DataFrame:
    """Pura -- opera sobre o df JA deduplicado. Normaliza source_file
    (normalize_source_file) e agrupa por client_id + nome normalizado; se o
    MESMO arquivo (ou uma variante '(1)', '(1) (1)' etc. do Drive) aparece
    associado a mais de um flight_start distinto, e sinal direto de arquivo
    duplicado/mal posicionado -- exatamente a causa raiz confirmada do Caso 1."""
    if df.empty:
        return pd.DataFrame(columns=["client_id", "client_name", "arquivo_normalizado", "flights", "arquivos_originais"])
    work = df.copy()
    work["_norm_file"] = work["source_file"].apply(normalize_source_file)
    work = work[work["_norm_file"] != ""]

    rows = []
    for (client_id, norm_file), group in work.groupby(["client_id", "_norm_file"]):
        distinct_flights = group[["flight_start", "flight_end"]].drop_duplicates()
        if len(distinct_flights) < 2:
            continue
        flight_keys = sorted((r.flight_start, r.flight_end) for r in distinct_flights.itertuples())
        rows.append({
            "client_id": client_id,
            "client_name": group["client_name"].iloc[0],
            "arquivo_normalizado": norm_file,
            "flight_keys": flight_keys,
            "flights": [f"{s} a {e}" for s, e in flight_keys],
            "arquivos_originais": sorted(set(group["source_file"].dropna())),
        })
    return pd.DataFrame(rows)


def detect_big_jumps(df: pd.DataFrame, pct_threshold: float = IO_PLAN_BIG_JUMP_PCT_THRESHOLD) -> pd.DataFrame:
    """Pura -- opera sobre o df JA deduplicado. So compara flights
    CONSECUTIVOS de verdade (flight_start de um comeca ate
    IO_PLAN_ADJACENT_GAP_DAYS dias depois do flight_end do anterior, mesmo
    client_id) -- evita falso positivo de comparar periodos com gap real no
    meio (ex: cliente pausado 2 meses e depois retoma com orcamento maior,
    isso e esperado, nao e o mesmo salto que preocupa aqui). Sinaliza so pra
    revisao humana (nao classifica como erro) -- cliente pode genuinamente
    ter mudado de escala."""
    if df.empty:
        return pd.DataFrame(columns=["client_id", "client_name", "flight_anterior", "flight_atual", "campo", "valor_anterior", "valor_atual", "variacao_pct"])
    rows = []
    for client_id, group in df.sort_values("flight_start").groupby("client_id"):
        group = group.reset_index(drop=True)
        for i in range(1, len(group)):
            prev, curr = group.iloc[i - 1], group.iloc[i]
            gap_days = (curr["flight_start"] - prev["flight_end"]).days
            if gap_days > IO_PLAN_ADJACENT_GAP_DAYS or gap_days < 0:
                continue  # nao sao consecutivos -- nao compara
            for field in ("planned_spend_gross", "planned_impressions"):
                prev_val, curr_val = prev[field], curr[field]
                if pd.isna(prev_val) or pd.isna(curr_val) or prev_val == 0:
                    continue
                pct_change = (curr_val - prev_val) / prev_val * 100
                if abs(pct_change) >= pct_threshold:
                    rows.append({
                        "client_id": client_id,
                        "client_name": curr["client_name"],
                        "flight_key": (curr["flight_start"], curr["flight_end"]),
                        "flight_anterior": f"{prev['flight_start']} a {prev['flight_end']}",
                        "flight_atual": f"{curr['flight_start']} a {curr['flight_end']}",
                        "campo": field,
                        "valor_anterior": prev_val,
                        "valor_atual": curr_val,
                        "variacao_pct": round(pct_change, 1),
                    })
    return pd.DataFrame(rows)


def detect_coverage_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Pura -- opera sobre o df JA deduplicado. Para cada cliente, calcula os
    dias cobertos por pelo menos 1 flight entre o menor flight_start e o maior
    flight_end, e reporta os MESES (competencia calendario) onde nenhum dia
    caiu dentro de um flight -- sinal de mes esquecido no meio de uma sequencia
    que normalmente tem plano. So informativo (gray) -- pode ser cliente
    pausado de proposito, nao e por si so um erro."""
    if df.empty:
        return pd.DataFrame(columns=["client_id", "client_name", "mes_sem_flight"])
    rows = []
    for client_id, group in df.groupby("client_id"):
        client_name = group["client_name"].iloc[0]
        overall_start, overall_end = group["flight_start"].min(), group["flight_end"].max()
        covered_days = set()
        for r in group.itertuples():
            covered_days.update(pd.date_range(r.flight_start, r.flight_end, freq="D").date)
        months = pd.period_range(overall_start, overall_end, freq="M")
        for month in months:
            month_days = set(pd.date_range(month.start_time, month.end_time, freq="D").date)
            if not (month_days & covered_days):
                rows.append({"client_id": client_id, "client_name": client_name, "mes_sem_flight": str(month)})
    return pd.DataFrame(rows)


# severidade -> peso pra achar "o pior status" de um flight/cliente com varios
# achados simultaneos. Maior peso vence -- mesmo raciocinio de STATUS_SEVERITY,
# tabela separada porque o dominio de severidade aqui e proprio desta aba.
IO_PLAN_ISSUE_WEIGHT = {"critico": 3, "atencao": 2, "informativo": 1}


def build_flight_issue_index(report_without_index: dict) -> dict:
    """Pura -- vira o relatorio 'uma tabela por tipo de achado' (formato bom
    pra auditoria plana) em 'um flight -> lista de achados' (formato que a UI
    hierarquica cliente->mes precisa pra colorir cada card de mes). Chave =
    (client_id, flight_start, flight_end). Cada achado carrega (severidade,
    rotulo curto, detalhe longo, heuristic_name) -- severidade em
    {'critico','atencao','informativo'}, ver IO_PLAN_ISSUE_WEIGHT para a ordem
    de "pior vence". `heuristic_name` (adicionado 2026-09-06) e a chave estavel
    usada pra casar este achado com o status de tratamento persistido em
    core.io_plan_finding_status (ver join_finding_status/save_io_plan_finding_status)
    -- SEMPRE um dos nomes de categoria do proprio report (duplicata_valores,
    arquivo_duplicado, salto_grande, multiplas_versoes), nunca um texto livre."""
    index: dict = {}

    def _add(client_id, flight_key, severity, label, detail, heuristic_name):
        key = (client_id, flight_key[0], flight_key[1])
        index.setdefault(key, []).append({
            "severity": severity, "label": label, "detail": detail, "heuristic_name": heuristic_name,
        })

    for _, row in report_without_index["duplicata_valores"].iterrows():
        others_by_flight = {fk: [f for f in row["flight_keys"] if f != fk] for fk in row["flight_keys"]}
        for fk in row["flight_keys"]:
            other_periods = ", ".join(f"{s} a {e}" for s, e in others_by_flight[fk])
            _add(
                row["client_id"], fk, "critico",
                "Valores identicos a outro periodo",
                f"impressoes={row['planned_impressions']}, cliques={row['planned_clicks']}, "
                f"spend_gross={row['planned_spend_gross']} -- igual a: {other_periods}",
                "duplicata_valores",
            )

    for _, row in report_without_index["arquivo_duplicado"].iterrows():
        for fk in row["flight_keys"]:
            _add(
                row["client_id"], fk, "critico",
                "Arquivo duplicado/reusado do Drive",
                "Mesma familia de arquivo em " + ", ".join(f"{s} a {e}" for s, e in row["flight_keys"])
                + " -- arquivos: " + " | ".join(row["arquivos_originais"]),
                "arquivo_duplicado",
            )

    # salto_grande pode disparar 2x pro MESMO flight (investimento E
    # impressoes saltando juntos, caso comum -- ver detect_big_jumps) --
    # agrupado por flight ANTES de _add() de proposito: core.io_plan_finding_status
    # so guarda 1 status por (client_id, flight, heuristic_name), entao 2
    # achados "salto_grande" separados no mesmo flight colidiriam tanto na key
    # do widget Streamlit quanto no grain da tabela de persistencia. Um saldo
    # combinado (1 achado, detalhe com os 2 campos) resolve os dois problemas.
    for (client_id, flight_key), group in report_without_index["salto_grande"].groupby(["client_id", "flight_key"]):
        partes = []
        for row in group.itertuples():
            campo_label = "investimento" if row.campo == "planned_spend_gross" else "impressoes"
            seta = "salto" if row.variacao_pct > 0 else "queda"
            partes.append(
                f"{seta} de {abs(row.variacao_pct):.0f}% em {campo_label} "
                f"({row.flight_anterior}: {row.valor_anterior:,.0f} -> {row.flight_atual}: {row.valor_atual:,.0f})"
            )
        _add(
            client_id, flight_key, "atencao",
            "Salto grande vs. mes anterior",
            " · ".join(partes),
            "salto_grande",
        )

    for _, row in report_without_index["multiplas_versoes"].iterrows():
        _add(
            row["client_id"], row["flight_key"], "informativo",
            f"{row['n_versoes']} versoes carregadas para este periodo",
            "plan_version: " + ", ".join(row["versoes"]),
            "multiplas_versoes",
        )

    return index


def build_io_plan_health_report(raw_df: pd.DataFrame) -> dict:
    """Pura (orquestra as detect_* acima, todas puras) -- monta o relatorio
    completo a partir do df cru de load_io_plan_manual (ainda com possiveis
    versoes duplicadas por flight). Retorna um dict com cada categoria de
    achado + o df ja deduplicado (para a UI poder mostrar a tabela completa
    tambem) + `flight_issues` (indice flight->achados, ver
    build_flight_issue_index) para a UI hierarquica cliente->mes. Ponto unico
    de composicao -- a UI so chama esta funcao e itera o resultado, nao
    reimplementa logica de deteccao."""
    deduped = dedupe_latest_per_flight(raw_df)
    report = {
        "deduped": deduped,
        "multiplas_versoes": detect_multiple_versions(raw_df),
        "duplicata_valores": detect_value_duplicates(deduped),
        "arquivo_duplicado": detect_source_file_reuse(deduped),
        "salto_grande": detect_big_jumps(deduped),
        "gap_cobertura": detect_coverage_gaps(deduped),
    }
    report["flight_issues"] = build_flight_issue_index(report)
    return report


def call_io_plan_admin_sync(client_slug: str | None, timeout: int = 180) -> dict:
    """Chama o servico Cloud Run `io-plan-admin` (services/io-plan-admin/main.py,
    ja deployado e publico -- ver comentario grande de IO_PLAN_ADMIN_URL acima)
    para rodar sync_drive.py contra producao. client_slug=None (ou "") ==
    'Sync All' (todos os clientes do CLIENT_MAP, mesmo botao que o proprio
    /main.py ja oferece) -- nao reimplementa a lista de clientes aqui, so
    repassa a chamada. NAO precisa de IAM novo (servico e allUsers +
    token) -- so do valor de IO_PLAN_ADMIN_SYNC_TOKEN configurado no Hub.
    Nunca lanca excecao pra UI -- sempre retorna um dict com 'ok' explicito,
    mesmo em erro de rede/permissao, pra tela poder mostrar resultado claro
    (nunca fingir sucesso)."""
    if not IO_PLAN_ADMIN_SYNC_TOKEN:
        return {
            "ok": False, "stage": "sync_drive",
            "detail": (
                "IO_PLAN_ADMIN_SYNC_TOKEN nao configurado neste ambiente do Hub -- "
                "pedir o valor ao Douglas (token do servico io-plan-admin) e setar como "
                "env var/secret antes deste botao funcionar de verdade."
            ),
        }
    try:
        resp = requests.post(
            f"{IO_PLAN_ADMIN_URL}/sync",
            data={"token": IO_PLAN_ADMIN_SYNC_TOKEN, "client": client_slug or ""},
            timeout=timeout,
            allow_redirects=False,
        )
        # /sync responde com 303 redirect em sucesso (ver main.py) -- 200 tambem aceitavel.
        if resp.status_code in (200, 303):
            return {"ok": True, "stage": "sync_drive", "detail": f"HTTP {resp.status_code} -- disparado com sucesso."}
        return {"ok": False, "stage": "sync_drive", "detail": f"HTTP {resp.status_code}: {resp.text[:500]}"}
    except requests.RequestException as exc:
        return {"ok": False, "stage": "sync_drive", "detail": f"Erro de rede chamando io-plan-admin: {exc}"}


def call_fact_pacing_refresh(timeout: int = 180) -> dict:
    """Invoca o Cloud Run `fact-pacing-base-refresh` (producao) via ID token,
    impersonando a writer SA do Hub (nunca a principal, que fica estritamente
    read-only por design). O binding roles/run.invoker ja foi concedido a
    `{WRITER_SA_EMAIL}` em 2026-09-07 (gap de IAM antigo, resolvido) -- o 403
    tratado abaixo fica so como fallback defensivo caso o binding seja
    revogado no futuro, nao e mais o caminho esperado.

    BUG REAL corrigido em 2026-09-07: IDTokenCredentials nao aceita
    `target_principal` diretamente (esse kwarg e de impersonated_credentials
    .Credentials, nao de IDTokenCredentials) -- precisa do passo intermediario
    de criar as credenciais impersonadas primeiro, mesmo padrao ja usado em
    get_writer_bq_client() acima, e SO ENTAO pedir o ID token sobre elas."""
    try:
        source_credentials, _ = google.auth.default()
        target_credentials = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=WRITER_SA_EMAIL,
            target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
            lifetime=300,
        )
        id_creds = impersonated_credentials.IDTokenCredentials(
            target_credentials, target_audience=FACT_PACING_REFRESH_URL, include_email=True,
        )
        id_creds.refresh(google.auth.transport.requests.Request())
        resp = requests.post(
            FACT_PACING_REFRESH_URL, headers={"Authorization": f"Bearer {id_creds.token}"}, timeout=timeout,
        )
        if resp.status_code == 200:
            return {"ok": True, "stage": "fact_pacing_refresh", "detail": f"HTTP {resp.status_code} -- refresh disparado."}
        detail = f"HTTP {resp.status_code}: {resp.text[:500]}"
        if resp.status_code == 403:
            detail += (
                f" -- esperado ate `{WRITER_SA_EMAIL}` ganhar roles/run.invoker em "
                f"`fact-pacing-base-refresh` (hoje so `{FACT_PACING_REFRESH_INVOKER_SA}` tem). "
                "Pendente de decisao do Douglas, nao aplicado automaticamente."
            )
        return {"ok": False, "stage": "fact_pacing_refresh", "detail": detail}
    except Exception as exc:
        return {"ok": False, "stage": "fact_pacing_refresh", "detail": f"Erro ao chamar fact-pacing-base-refresh: {exc}"}


def trigger_io_plan_resync(client_slug: str | None) -> list[dict]:
    """Orquestra o ciclo completo 'corrigir na fonte -> reprocessar' pedido
    pelo Douglas: 1) sync_drive (um cliente ou todos, client_slug=None),
    2) UMA chamada de fact-pacing-base-refresh no final (o refresh recalcula
    geral, nao por cliente -- nao precisa rodar 14x pra 'rodar todos"").
    Roda a etapa 2 mesmo se a 1 falhar parcialmente (sync_drive resolve por
    cliente internamente) -- quem le o resultado decide o que fazer. Retorna
    a lista de resultados na ordem de execucao, cada um com 'ok' explicito."""
    results = [call_io_plan_admin_sync(client_slug)]
    results.append(call_fact_pacing_refresh())
    return results


def stage_raw_historical_upload(raw_df: pd.DataFrame, client_id: str, source_filename: str, notes: str = "") -> dict:
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
        "notes": notes.strip() if notes else None,
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
    SELECT upload_id, source_filename, row_count, uploaded_at, notes, promoted_at
    FROM `{RAW_UPLOADS_META_TABLE}`
    WHERE client_id = @client_id
    ORDER BY uploaded_at DESC
    """
    return client.query(query, job_config=job_config).to_dataframe()


def delete_historical_upload(upload_id: str) -> None:
    """DELETE PROVISORIO de um upload inteiro (historical_uploads +
    historical_uploads_meta) -- pedido explicito do Douglas durante o teste ao
    vivo, ambiente de staging: precisava poder limpar upload de teste/engano
    sem esperar o processo formal de expurgo. Foge do principio 'raw so
    INSERT, nunca DELETE' documentado no cabecalho deste arquivo -- por isso
    fica marcado como provisorio na UI (aviso explicito), nao um botao
    permanente do fluxo formal. Escreve com a writer SA impersonada, staging."""
    client = get_staging_writer_bq_client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("upload_id", "STRING", upload_id)]
    )
    client.query(
        f"DELETE FROM `{RAW_UPLOADS_TABLE}` WHERE upload_id = @upload_id", job_config=job_config,
    ).result()
    client.query(
        f"DELETE FROM `{RAW_UPLOADS_META_TABLE}` WHERE upload_id = @upload_id", job_config=job_config,
    ).result()


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
    """Amostra de douglas-bq-staging.gold.fact_pacing pro client_id e range de
    datas informado -- SA principal (read-only), fully-qualified table name
    (mesmo padrao de load_landed_historical_upload -- nao precisa trocar de
    projeto no client, so qualificar a tabela). So leitura, sem nenhuma logica
    de comparacao/diff -- essa e so a coluna direita da tela lado a lado.
    Usa fact_pacing (nao fact_delivery, corrigido 2026-08-11 a pedido do
    Douglas): e fact_pacing quem de fato consome
    stg.historical_overrides_delivery como 4a fonte do UNION ALL (ver
    core/ddl/resolve_reporting_source.sql) -- fact_delivery nao tem nenhuma
    logica de override, comparar contra ela nunca refletiria o efeito real do
    override. Todas as colunas de fact_pacing incluidas (nao so
    impressions/clicks/conversions -- ampliado 2026-08-11 a pedido do Douglas,
    ver task 'Ampliar Comparacao...'), planejado+realizado+investimento, pra
    dar visao completa do que a planilha historica precisaria cobrir.
    Colunas realized_* aliadas para impressions/clicks/conversions pra manter
    compatibilidade com o preview do arquivo upado (que usa esses nomes)."""
    client = get_bq_client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
            bigquery.ScalarQueryParameter("start_day", "DATE", start_day),
            bigquery.ScalarQueryParameter("end_day", "DATE", end_day),
        ]
    )
    query = f"""
    SELECT day, platform, formato, goal_type,
      planned_impressions_daily, planned_clicks_daily, planned_spend_daily,
      unit_price, investimento_realizado,
      realized_impressions AS impressions, realized_clicks AS clicks,
      realized_conversions AS conversions
    FROM `{HISTORICAL_OVERRIDE_PROJECT_ID}.gold.fact_pacing`
    WHERE client_id = @client_id
      AND day BETWEEN @start_day AND @end_day
    ORDER BY day
    LIMIT {limit}
    """
    return client.query(query, job_config=job_config).to_dataframe()


def load_gold_coverage_for_client(client_id: str):
    """MIN/MAX day existente em douglas-bq-staging.gold.fact_pacing pro
    client_id, independente do range da planilha -- usada so para dar contexto
    quando a amostra do range da planilha vem vazia (dizer o que a plataforma
    real TEM, em vez de so mostrar uma tabela vazia sem explicacao). Ver nota
    em load_gold_sample_for_range sobre por que fact_pacing (nao fact_delivery)."""
    client = get_bq_client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("client_id", "STRING", client_id)]
    )
    query = f"""
    SELECT MIN(day) AS min_day, MAX(day) AS max_day
    FROM `{HISTORICAL_OVERRIDE_PROJECT_ID}.gold.fact_pacing`
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


def refresh_fact_pacing_base() -> None:
    """Reaplica o refresh de stg.fact_pacing_base direto via BQ client (sem
    subprocess/apply_ddl.py -- o container do Hub so tem hub/, nao o resto do
    repo). SQL inline deve ficar em sincronia com
    stg/ddl/fact_pacing_base_refresh.sql (fonte de verdade); se aquele
    arquivo mudar, atualizar aqui tambem -- 2026-08-12, pedido do Douglas pra
    o toggle de override_active ja disparar o refresh, sem precisar rodar o
    apply_ddl.py manualmente no terminal depois. Usa a mesma writer SA de
    set_client_override_active."""
    client = get_staging_writer_bq_client()
    sql = f"""
        CREATE OR REPLACE TABLE `{HISTORICAL_OVERRIDE_PROJECT_ID}.stg.fact_pacing_base` AS
        WITH io_agg AS (
          SELECT
            client_id, report_date, formato, platform, goal_type,
            IF(COUNT(DISTINCT unit_price) = 1, ANY_VALUE(unit_price), NULL) AS unit_price,
            SUM(planned_spend_daily)       AS planned_spend_daily,
            SUM(planned_impressions_daily) AS planned_impressions_daily,
            SUM(planned_clicks_daily)      AS planned_clicks_daily
          FROM `{HISTORICAL_OVERRIDE_PROJECT_ID}.gold.fact_io_plan`
          GROUP BY client_id, report_date, formato, platform, goal_type
        ),
        joined AS (
          SELECT
            COALESCE(p.client_id, d.client_id) AS client_id,
            COALESCE(p.report_date, d.day) AS day,
            COALESCE(p.formato, d.formato) AS formato,
            COALESCE(p.platform, d.platform) AS platform,
            p.planned_spend_daily, p.planned_impressions_daily, p.planned_clicks_daily, p.unit_price,
            COALESCE(p.goal_type, d.goal_type) AS goal_type,
            d.impressions AS realized_impressions,
            d.clicks AS realized_clicks,
            d.conversions AS realized_conversions,
            CASE COALESCE(p.goal_type, d.goal_type)
              WHEN 'CPC' THEN d.clicks * p.unit_price
              WHEN 'CPM' THEN SAFE_DIVIDE(d.impressions * p.unit_price, 1000)
              ELSE NULL
            END AS investimento_realizado_formula
          FROM io_agg p
          FULL OUTER JOIN `{HISTORICAL_OVERRIDE_PROJECT_ID}.gold.fact_delivery` d
            ON p.client_id = d.client_id AND p.report_date = d.day
            AND UPPER(p.formato) = UPPER(d.formato) AND p.platform = d.platform
          WHERE COALESCE(p.client_id, d.client_id) IS NOT NULL
            AND COALESCE(p.report_date, d.day) IS NOT NULL
        )
        SELECT
          j.client_id, j.day, j.formato, j.platform,
          COALESCE(ov.planned_spend_daily, j.planned_spend_daily) AS planned_spend_daily,
          COALESCE(ov.planned_impressions_daily, j.planned_impressions_daily) AS planned_impressions_daily,
          COALESCE(ov.planned_clicks_daily, j.planned_clicks_daily) AS planned_clicks_daily,
          COALESCE(ov.unit_price, j.unit_price) AS unit_price,
          j.goal_type, j.realized_impressions, j.realized_clicks, j.realized_conversions,
          COALESCE(ov.investimento, j.investimento_realizado_formula) AS investimento_realizado,
          `{HISTORICAL_OVERRIDE_PROJECT_ID}.core.resolve_reporting_source`(j.client_id, j.day, CURRENT_DATE()) = 'override' AS is_override
        FROM joined j
        LEFT JOIN `{HISTORICAL_OVERRIDE_PROJECT_ID}.stg.historical_overrides_delivery` ov
          ON ov.client_id = j.client_id AND ov.day = j.day
          AND UPPER(ov.formato) = UPPER(j.formato) AND UPPER(ov.platform) = UPPER(j.platform)
    """
    client.query(sql).result()


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
    fields_select = ", ".join(FACT_PACING_FIELDS)
    query = f"""
    SELECT day, formato, platform, {fields_select}
    FROM `{PROJECT_ID}.gold.fact_pacing`
    WHERE client_id = @client_id AND UPPER(formato) IN UNNEST(@strategies)
    ORDER BY day
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
        bigquery.ArrayQueryParameter("strategies", "STRING", [s.upper() for s in strategies]),
    ])
    return client.query(query, job_config=job_config).to_dataframe()


def mock_pacing_demo_data(strategies: tuple[str, ...]) -> pd.DataFrame:
    """Dado de EXEMPLO (fabricado, nao vem do BigQuery) para o modo demonstracao do
    simulador -- rede de seguranca para apresentacao ao vivo, caso a consulta real
    (load_pacing_for_simulation) falhe por qualquer motivo (rede, permissao, etc).
    Perfil de volume/variacao inspirado no cliente Cora real (Native/Push, ~90
    dias com IO Plan continuo), mas os numeros aqui sao gerados com seed fixa --
    NUNCA sao dado real de nenhum cliente. Sempre exibido com aviso explicito na UI."""
    rnd = random.Random(42)
    base_by_strategy = {
        "native": 11000, "push": 2300, "video": 8000, "display": 15000, "retargeting": 6000,
    }
    platform_by_strategy = {
        "native": "MediaSmart", "display": "MediaSmart", "retargeting": "MediaSmart",
        "push": "MGID", "video": "MediaSmart",
    }
    ctr = 0.02  # cliques / impressao, fixo -- so para o dado de exemplo ter proporcao plausivel
    cvr = 0.03  # conversoes / clique
    cpm = 8.0   # investimento por 1000 impressoes (BRL)
    rows = []
    for strategy in strategies:
        base = base_by_strategy.get(strategy, 5000)
        for i in range(90):
            day = date(2026, 1, 1) + timedelta(days=i)
            planned_impr = base * rnd.uniform(0.92, 1.08)
            spike = rnd.choices([1.0, 1.3, 1.6], weights=[75, 18, 7])[0]
            realized_impr = max(planned_impr * spike * rnd.uniform(0.9, 1.1), 0)
            rows.append({
                "day": day,
                "formato": strategy.title(),
                "platform": platform_by_strategy.get(strategy, "MediaSmart"),
                "planned_impressions_daily": round(planned_impr),
                "realized_impressions": round(realized_impr),
                "planned_clicks_daily": round(planned_impr * ctr),
                "realized_clicks": round(realized_impr * ctr),
                "realized_conversions": round(realized_impr * ctr * cvr),
                "planned_spend_daily": round(planned_impr / 1000 * cpm, 2),
                "investimento_realizado": round(realized_impr / 1000 * cpm, 2),
            })
    return pd.DataFrame(rows)


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


def edit_business_rule_dates(rule_id: str, effective_from: date, effective_to: date | None) -> None:
    """UPDATE direto de effective_from/effective_to numa linha existente -- foge do
    padrao SCD2 (fechar+abrir nova linha) usado no resto do pipeline, decisao
    explicita do Douglas (2026-08-11): como admin/unico usuario de escrita hoje,
    ele precisa poder corrigir range de vigencia sem passar pelo fluxo de
    pausa+recriacao. Restringir isso a usuarios nao-admin fica para quando o Hub
    tiver controle de acesso por papel (nao existe ainda). Sem guarda-corpo de
    'so linha vigente' de proposito -- serve tambem para corrigir historico
    fechado por engano. Escreve com a writer SA impersonada, staging."""
    client = get_staging_writer_bq_client()
    update_sql = f"""
        UPDATE `{BUSINESS_RULES_TABLE}`
        SET effective_from = @effective_from, effective_to = @effective_to
        WHERE rule_id = @rule_id
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("rule_id", "STRING", rule_id),
        bigquery.ScalarQueryParameter("effective_from", "DATE", effective_from),
        bigquery.ScalarQueryParameter("effective_to", "DATE", effective_to),
    ])
    client.query(update_sql, job_config=job_config).result()


def delete_business_rule(rule_id: str) -> None:
    """DELETE definitivo de uma linha de core.client_business_rules -- nao e
    'pausar' (que preserva a linha como historico fechado), apaga o registro por
    completo. Decisao explicita do Douglas (2026-08-11): admin precisa poder
    apagar regra criada por engano/teste, sem deixar rastro de historico se nao
    quiser. Restringir isso a usuarios nao-admin fica para quando o Hub tiver
    controle de acesso por papel (nao existe ainda). Escreve com a writer SA
    impersonada, staging."""
    client = get_staging_writer_bq_client()
    delete_sql = f"DELETE FROM `{BUSINESS_RULES_TABLE}` WHERE rule_id = @rule_id"
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("rule_id", "STRING", rule_id),
    ])
    client.query(delete_sql, job_config=job_config).result()


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
        # base_field/reference_field so existem em regras criadas apos o construtor
        # de campos (2026-08-10) -- regras antigas (ex: dado de teste em staging)
        # nao tem essas chaves, cai no rotulo generico "Teto X%" de antes.
        if "base_field" in params and "reference_field" in params:
            base_label = FACT_PACING_FIELDS.get(params["base_field"], params["base_field"])
            ref_label = FACT_PACING_FIELDS.get(params["reference_field"], params["reference_field"])
            return (
                f"{base_label} nao pode superar {ref_label} em mais de "
                f"{params['threshold_pct']}% -- {strategies_label}"
            )
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
                edit_open_key = f"edit_open_{rule_id}"
                delete_open_key = f"delete_open_{rule_id}"
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    if st.button("Pausar", key=f"pause_btn_{rule_id}"):
                        st.session_state[pause_open_key] = True
                with btn_col2:
                    if st.button("Editar datas", key=f"edit_btn_{rule_id}"):
                        st.session_state[edit_open_key] = True
                with btn_col3:
                    if st.button("Deletar", key=f"delete_btn_{rule_id}"):
                        st.session_state[delete_open_key] = True

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

                if st.session_state.get(edit_open_key):
                    with st.container(border=True):
                        st.caption(
                            "Ajuste direto de vigencia -- foge do fluxo normal de "
                            "pausa/criacao, uso admin. Nao gera historico novo, altera "
                            "a linha existente."
                        )
                        new_effective_from = st.date_input(
                            "Vigente a partir de", value=current_row["effective_from"],
                            key=f"edit_from_{rule_id}",
                        )
                        current_eff_to = current_row.get("effective_to")
                        has_end_date = st.checkbox(
                            "Tem data fim", value=current_eff_to is not None,
                            key=f"edit_has_end_{rule_id}",
                        )
                        new_effective_to = None
                        if has_end_date:
                            new_effective_to = st.date_input(
                                "Vigente ate",
                                value=current_eff_to if current_eff_to is not None else date.today(),
                                key=f"edit_to_{rule_id}",
                            )
                        edit_confirm = st.checkbox(
                            "Confirmo o ajuste manual de datas desta regra",
                            key=f"edit_confirm_{rule_id}",
                        )
                        edit_commit_col, edit_cancel_col = st.columns([1, 1])
                        with edit_commit_col:
                            if st.button(
                                "Salvar datas", key=f"edit_commit_{rule_id}",
                                disabled=not edit_confirm,
                            ):
                                try:
                                    with st.spinner("Atualizando vigencia..."):
                                        edit_business_rule_dates(
                                            rule_id, new_effective_from, new_effective_to,
                                        )
                                    st.success("Datas atualizadas.")
                                    load_business_rules.clear()
                                    st.session_state[edit_open_key] = False
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Erro ao editar datas: {exc}")
                        with edit_cancel_col:
                            if st.button("Cancelar", key=f"edit_cancel_{rule_id}"):
                                st.session_state[edit_open_key] = False
                                st.rerun()

                if st.session_state.get(delete_open_key):
                    with st.container(border=True):
                        st.warning(
                            ":material/warning: Apaga a linha por completo -- diferente de "
                            "Pausar, nao deixa rastro de historico.",
                            icon=":material/warning:",
                        )
                        delete_confirm = st.checkbox(
                            "Confirmo que quero deletar esta regra definitivamente",
                            key=f"delete_confirm_{rule_id}",
                        )
                        del_commit_col, del_cancel_col = st.columns([1, 1])
                        with del_commit_col:
                            if st.button(
                                "Confirmar delete", key=f"delete_commit_{rule_id}",
                                disabled=not delete_confirm,
                            ):
                                try:
                                    with st.spinner("Deletando regra..."):
                                        delete_business_rule(rule_id)
                                    st.success("Regra deletada.")
                                    load_business_rules.clear()
                                    st.session_state[delete_open_key] = False
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Erro ao deletar: {exc}")
                        with del_cancel_col:
                            if st.button("Cancelar", key=f"delete_cancel_{rule_id}"):
                                st.session_state[delete_open_key] = False
                                st.rerun()
            else:
                st.badge("sem versao vigente -- pausada", icon=":material/pause_circle:", color="orange")

        if not history_df.empty:
            with st.expander(f"Ver historico ({len(history_df)} versao(oes))"):
                header = st.columns([3, 2.5, 1.3, 1])
                for h, txt in zip(header, ["Resumo / vigencia", "Confirmado por / notas", "Status", ""]):
                    h.markdown(f"<span style='color:gray;font-size:0.8em'>{txt}</span>", unsafe_allow_html=True)
                for _, h in history_df.iterrows():
                    hist_rule_id = h["rule_id"]
                    hc1, hc2, hc3, hc4 = st.columns([3, 2.5, 1.3, 1])
                    with hc1:
                        st.write(summarize_rule_params(rule_type, h["rule_params"]))
                        st.caption(f"{h['effective_from']} a {h['effective_to']}")
                    with hc2:
                        st.caption(f"{h['confirmed_by']} -- {h['notes'] or 'sem notas'}")
                    with hc3:
                        history_status_badge(h["status"])
                    with hc4:
                        hist_delete_key = f"hist_delete_open_{hist_rule_id}"
                        if st.button("Deletar", key=f"hist_delete_btn_{hist_rule_id}"):
                            st.session_state[hist_delete_key] = True
                        if st.session_state.get(hist_delete_key):
                            hist_confirm = st.checkbox(
                                "Confirmo", key=f"hist_delete_confirm_{hist_rule_id}",
                            )
                            if st.button(
                                "Confirmar", key=f"hist_delete_commit_{hist_rule_id}",
                                disabled=not hist_confirm,
                            ):
                                try:
                                    delete_business_rule(hist_rule_id)
                                    st.success("Deletada.")
                                    load_business_rules.clear()
                                    st.session_state[hist_delete_key] = False
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Erro: {exc}")


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
        # Checa OS DOIS ambientes -- ate 2026-08-31 o farol so olhava producao
        # (PROJECT_ID), entao um problema so-em-staging (caso real:
        # stg.fact_pacing_base 15 dias atrasada) nunca acendia aqui. Ver
        # comentario de ENVIRONMENTS em cima.
        _farol_status_by_env = {}
        for _env in ENVIRONMENTS:
            _env_meta = load_table_metadata(_env["project_id"])
            _farol_status_by_env[_env["label"]] = (
                worst_status(_env_meta["freshness"].tolist()) if not _env_meta.empty else "sem_dado"
            )
        _pipeline_status = worst_status(list(_farol_status_by_env.values()))
        _pending_count = count_pending_proposals()
        _month_gross, _month_net = load_cost_current_month()
        _prev_month_gross, _prev_month_net = load_cost_previous_month()

    farol1, farol2, farol3 = st.columns(3)
    with farol1:
        with st.container(border=True):
            st.markdown("**Saude do pipeline**")
            for _env_label, _env_status in _farol_status_by_env.items():
                _col_label, _col_badge = st.columns([1.2, 1])
                _col_label.caption(_env_label)
                with _col_badge:
                    status_badge(_env_status)
            st.caption("pior status por camada em cada ambiente -- detalhe na aba Visao Geral BQ")
    with farol2:
        with st.container(border=True):
            st.markdown("**Propostas de mudanca pendentes**")
            st.metric("pendentes", _pending_count, label_visibility="collapsed")
            st.caption("fila vazia" if not _pending_count else "revisar na aba Propostas de Mudanca")
    with farol3:
        with st.container(border=True):
            st.markdown(f"**Custo do mes -- {date.today().strftime('%m/%Y')}**")
            _cost_delta = None
            if _prev_month_gross:
                _cost_delta = f"{((_month_gross - _prev_month_gross) / _prev_month_gross * 100):+.1f}% vs mes anterior"
            st.metric(
                "gross", f"US$ {_month_gross:,.2f}", delta=_cost_delta,
                delta_color="inverse", label_visibility="collapsed",
            )
            st.caption(
                f"net US$ {_month_net:,.2f} -- mes em andamento (nao comparavel 1:1 com "
                "mes anterior fechado)"
            )

st.divider()

tab_freshness, tab_jobs, tab_browser, tab_io_health, tab_formats, tab_proposals, tab_overrides, tab_business_rules, tab_clients = st.tabs([
    ":material/database: Visao Geral BQ",
    ":material/sync: Status dos Jobs",
    ":material/table_view: Navegador de Tabelas",
    ":material/health_and_safety: Saude do IO Plan",
    ":material/category: Formatos/Regras",
    ":material/fact_check: Propostas de Mudanca",
    ":material/history: Ajustes de Dados Historicos",
    ":material/gavel: Regras de Negocio",
    ":material/groups: Gerenciamento de Clientes",
])

# ─────────────────────────────────────────────────────────────────────────
# Aba 1 -- Visao Geral BQ: cards por camada, na ordem do pipeline
# ─────────────────────────────────────────────────────────────────────────
with tab_freshness:
    _env_choice = st.radio(
        "Ambiente", [e["label"] for e in ENVIRONMENTS], horizontal=True, key="freshness_env",
    )
    _env_project = next(e["project_id"] for e in ENVIRONMENTS if e["label"] == _env_choice)
    st.caption(f"Projeto GCP: `{_env_project}`")

    with st.spinner("Consultando __TABLES__ (metadado, sem custo de bytes)..."):
        df = load_table_metadata(_env_project)

    st.subheader("Camadas do pipeline")
    st.caption("RAW -> STG -> CORE -> MARTS -> SHARE -> GOLD. Cada card resume uma camada; clique para ver o detalhe.")
    if df.empty:
        st.info(f"Nenhum dataset das camadas do pipeline encontrado em `{_env_project}`.")

    # Larguras relativas -- CORE e GOLD ganham mais peso visual (mais proximas do
    # cliente final na jornada do dado), resto das camadas fica no padrao (1.0).
    _LAYER_WEIGHT = {"core": 1.35, "gold": 1.35}
    summary_cols = st.columns([_LAYER_WEIGHT.get(layer["id"], 1.0) for layer in LAYERS])
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
    st.subheader("Jobs de ingestao/refresh")
    st.caption(
        "Mapa mantido manualmente em `jobs_config.yaml` (producao + staging, lado a lado). "
        "Cruza freshness real da tabela associada com, quando disponivel, a execucao REAL "
        "do Cloud Scheduler (sucesso/falha da ultima tentativa, nao so heuristica indireta)."
    )
    jobs_cfg = load_yaml("jobs_config.yaml")["jobs"]
    # Carrega metadado uma vez por projeto distinto usado nos jobs (evita repetir
    # a mesma query __TABLES__ para cada job do mesmo ambiente).
    _job_projects = sorted({job.get("project", PROJECT_ID) for job in jobs_cfg})
    meta_by_project = {proj: load_table_metadata(proj) for proj in _job_projects}

    def _render_scheduler_status(job):
        """Se o job tiver scheduler_job configurado, mostra a execucao REAL da
        ultima tentativa (sucesso/falha + horario) via Cloud Scheduler API --
        None quando o job nao e um Cloud Scheduler proprio (ex: jobs do
        orchestrator do Shiro, disparados via Firestore)."""
        if not job.get("scheduler_job"):
            return
        sched = load_scheduler_job_status(
            job.get("project", PROJECT_ID), job.get("scheduler_location", "southamerica-east1"), job["scheduler_job"],
        )
        if not sched["found"]:
            st.caption(f":material/error: Cloud Scheduler: {sched['detail']}")
            return
        when = sched["last_attempt_time"].strftime("%d/%m/%Y %H:%M") if sched["last_attempt_time"] else "nunca rodou"
        if sched["ok"]:
            st.caption(f":material/check_circle: Cloud Scheduler ({sched['state']}): ultima execucao OK em {when}")
        else:
            st.caption(f":material/error: Cloud Scheduler ({sched['state']}): ULTIMA EXECUCAO FALHOU em {when} -- {sched['error_message']}")

    def _render_job_card(job, status, last_mod):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 1.5, 2, 1.5])
            with c1:
                st.markdown(f"**{job['label']}**")
                st.caption(f"`{job.get('project', PROJECT_ID)}.{job['table']}`")
            with c2:
                st.write(job["schedule"])
            with c3:
                st.write(last_mod.strftime("%d/%m/%Y %H:%M") if pd.notna(last_mod) else "sem dado ainda")
            with c4:
                status_badge(status)
            _render_scheduler_status(job)

    # Divulgacao progressiva: por padrao so mostra jobs com problema real
    # (severidade >= 1, ver STATUS_SEVERITY, OU falha real no Cloud Scheduler) --
    # jobs saudaveis ficam atras de um expander, reduzindo carga cognitiva pra
    # checagem rapida do dia a dia.
    problem_jobs, healthy_jobs = [], []
    for job in jobs_cfg:
        project = job.get("project", PROJECT_ID)
        dataset, table = job["table"].split(".")
        meta = meta_by_project.get(project, pd.DataFrame())
        match = meta[(meta["dataset"] == dataset) & (meta["tabela"] == table)] if not meta.empty else meta
        if match.empty:
            status, last_mod = "tabela_nao_encontrada", None
        else:
            status, last_mod = match["freshness"].iloc[0], match["ultima_modificacao"].iloc[0]
        has_scheduler_failure = False
        if job.get("scheduler_job"):
            sched = load_scheduler_job_status(project, job.get("scheduler_location", "southamerica-east1"), job["scheduler_job"])
            has_scheduler_failure = sched["found"] and not sched["ok"]
        entry = (job, status, last_mod)
        is_problem = STATUS_SEVERITY.get(status, 0) >= 1 or has_scheduler_failure
        (problem_jobs if is_problem else healthy_jobs).append(entry)

    if not problem_jobs:
        st.success(f"Todos os {len(healthy_jobs)} jobs saudaveis.", icon=":material/check_circle:")
    else:
        for job, status, last_mod in problem_jobs:
            _render_job_card(job, status, last_mod)

    if healthy_jobs:
        with st.expander(f"Ver historico completo ({len(healthy_jobs)} job(s) saudavel(is))"):
            for job, status, last_mod in healthy_jobs:
                _render_job_card(job, status, last_mod)


# ─────────────────────────────────────────────────────────────────────────
# Aba 3 -- Navegador de Tabelas: schema + preview, so leitura
# ─────────────────────────────────────────────────────────────────────────
with tab_browser:
    st.subheader("Navegador de Tabelas")
    st.caption("Schema e preview de qualquer tabela/view das camadas do pipeline, em producao OU staging. Read-only.")

    _browser_env_choice = st.radio(
        "Ambiente", [e["label"] for e in ENVIRONMENTS], horizontal=True, key="browser_env",
    )
    _browser_project = next(e["project_id"] for e in ENVIRONMENTS if e["label"] == _browser_env_choice)

    meta_df = load_table_metadata(_browser_project)
    ds_choice = st.selectbox("Dataset", DATASETS, key="browser_dataset")
    tables_in_ds = sorted(meta_df.loc[meta_df["dataset"] == ds_choice, "tabela"].tolist())
    if not tables_in_ds:
        st.info(f"Nenhuma tabela encontrada em `{_browser_project}.{ds_choice}`.")
    else:
        table_choice = st.selectbox("Tabela", tables_in_ds, key="browser_table")
        client = get_bq_client()
        table_ref = client.get_table(f"{_browser_project}.{ds_choice}.{table_choice}")

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
        st.dataframe(
            pd.DataFrame(schema_rows), use_container_width=True, hide_index=True,
            column_config={
                "coluna": st.column_config.TextColumn("Coluna", width="medium"),
                "tipo": st.column_config.TextColumn("Tipo"),
                "modo": st.column_config.TextColumn("Modo"),
                "descricao": st.column_config.TextColumn("Descricao", width="large"),
            },
        )

        st.markdown("**Preview (50 linhas)**")
        if st.button("Carregar preview", key="browser_preview_btn"):
            preview_sql = f"SELECT * FROM `{_browser_project}.{ds_choice}.{table_choice}` LIMIT 50"
            with st.spinner("Consultando..."):
                preview_df = client.query(preview_sql).to_dataframe()
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────
# Aba -- Saude do IO Plan: deteccao proativa de incongruencia mensal por
# cliente em core.io_plan_manual. 100% read-only -- so alerta, nao corrige
# nada aqui (correcao e sempre no arquivo fonte/Drive, fora do hub). Ver bloco
# de comentario grande em build_io_plan_health_report() e funcoes irmas acima
# para o desenho completo e os 2 casos reais que motivaram isto (2026-09-06).
# ─────────────────────────────────────────────────────────────────────────
with tab_io_health:
    st.subheader("Saude do IO Plan")
    st.caption(
        "Deteccao proativa de incongruencia mensal por cliente em `core.io_plan_manual` -- "
        "arquivo duplicado do Drive, periodo preenchido errado na planilha, salto de "
        "orcamento sem contexto. Read-only: so alerta, a correcao e sempre no arquivo "
        "fonte/Drive."
    )

    _io_env_choice = st.radio(
        "Ambiente", [e["label"] for e in ENVIRONMENTS], horizontal=True, key="io_health_env",
    )
    _io_project = next(e["project_id"] for e in ENVIRONMENTS if e["label"] == _io_env_choice)
    st.caption(f"Projeto GCP: `{_io_project}`")

    with st.spinner("Consultando core.io_plan_manual..."):
        _io_raw_df = load_io_plan_manual(_io_project)
    with st.spinner("Consultando raw.io_plan_drive_snapshot (detalhe linha-item)..."):
        _io_raw_detail_df = load_io_plan_raw_detail(_io_project)

    if _io_raw_df.empty:
        st.info(f"`{_io_project}.core.io_plan_manual` esta vazia ou nao encontrada.")
    else:
        _io_report = build_io_plan_health_report(_io_raw_df)
        _n_dup_values = len(_io_report["duplicata_valores"])
        _n_dup_files = len(_io_report["arquivo_duplicado"])
        _n_jumps = len(_io_report["salto_grande"])
        _n_gaps = len(_io_report["gap_cobertura"])
        _n_versions = len(_io_report["multiplas_versoes"])
        _n_flights = len(_io_report["deduped"])
        _n_clients = _io_report["deduped"]["client_id"].nunique()

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Clientes", _n_clients)
        m2.metric("Flights (deduplicados)", _n_flights)
        m3.metric("Valores duplicados", _n_dup_values, delta_color="inverse")
        m4.metric("Arquivo reusado", _n_dup_files, delta_color="inverse")
        m5.metric("Saltos grandes", _n_jumps, delta_color="inverse")
        m6.metric("Gaps de cobertura", _n_gaps, delta_color="inverse")

        _total_critical = _n_dup_values + _n_dup_files
        if _total_critical:
            st.error(f":material/error: {_total_critical} achado(s) de alta severidade -- valores ou arquivo idênticos entre periodos diferentes. Revisar antes de confiar no numero do dashboard do cliente.")
        elif _n_jumps:
            st.warning(f":material/warning: {_n_jumps} salto(s) grande(s) de orcamento/impressao entre meses consecutivos -- pode ser mudanca real do cliente, vale conferir.")
        else:
            st.success(":material/check_circle: Nenhuma incongruencia de alta severidade encontrada nos flights atuais.")

        st.divider()

        # ─────────────────────────────────────────────────────────────────
        # Hierarquia Cliente -> Mes (flight), colapsavel -- pedido explicito
        # do Douglas (2026-09-06, "front-end vendavel", task marcada "Mostrar
        # Chefes: yes"). st.expander nao pode ser aninhado dentro de outro
        # st.expander (limitacao do Streamlit) -- por isso o nivel Cliente usa
        # st.expander (colapsa/expande a lista inteira de meses) e o nivel
        # Mes usa um cartao colorido (st.error/warning/info/container) que ja
        # concentra o essencial na propria linha, sem precisar de um segundo
        # clique -- o efeito de "abrir o cliente e ver os meses organizados"
        # e o mesmo que ele pediu, so sem 2 niveis literais do MESMO widget.
        # Cor do cartao = pior achado daquele mes (critico=vermelho,
        # atencao=laranja, informativo=azul, nenhum=verde compacto).
        # ─────────────────────────────────────────────────────────────────
        st.markdown("#### :material/apartment: Por cliente")
        st.caption("Clique no cliente para abrir os meses. Ordenado pelos casos mais graves primeiro.")

        # Funde a deteccao ao vivo com o status de tratamento persistido
        # (core.io_plan_finding_status) -- pedido do Douglas (2026-09-06)
        # apos testar o conceito: sem isso, um achado ja resolvido volta a
        # aparecer "critico" pra sempre toda vez que a pagina recarrega.
        with st.spinner("Consultando status de tratamento (core.io_plan_finding_status)..."):
            _io_status_df = load_io_plan_finding_status(_io_project)
        _flight_issues = join_finding_status(_io_report["flight_issues"], _io_status_df)
        _gaps_by_client = _io_report["gap_cobertura"].groupby("client_id")["mes_sem_flight"].apply(list).to_dict() if not _io_report["gap_cobertura"].empty else {}

        _SEVERITY_EMOJI = {"critico": "\U0001F534", "atencao": "\U0001F7E0", "informativo": "\U0001F535", None: "\U0001F7E2"}
        _SEVERITY_ICON = {"critico": ":material/error:", "atencao": ":material/warning:", "informativo": ":material/info:"}
        _STATUS_ICON = {"pendente": "\U0001F553", "resolvido": "✅", "esperado": "\U0001F535"}

        def _flight_worst_severity(issues: list):
            """So achados ainda 'pendente' contam pra severidade do card/cliente --
            um achado marcado 'resolvido' ou 'esperado' pelo Douglas nao deve mais
            pintar o card de vermelho/laranja (mesmo que a heuristica continue
            detectando o padrao nos dados ao vivo), mas continua listado no corpo
            do card com seu status visivel -- nunca desaparece silenciosamente."""
            pendentes = [i for i in issues if i.get("status", "pendente") == "pendente"]
            if not pendentes:
                return None
            return max(pendentes, key=lambda i: IO_PLAN_ISSUE_WEIGHT[i["severity"]])["severity"]

        _client_blocks = []
        for _client_id, _client_group in _io_report["deduped"].groupby("client_id"):
            _client_group = _client_group.sort_values("flight_start").reset_index(drop=True)
            _client_name = _client_group["client_name"].iloc[0]
            _flight_severities = [
                _flight_worst_severity(_flight_issues.get((_client_id, r.flight_start, r.flight_end), []))
                for r in _client_group.itertuples()
            ]
            _has_gap = _client_id in _gaps_by_client
            _worst = max(
                [s for s in _flight_severities if s] + (["informativo"] if _has_gap else []),
                key=lambda s: IO_PLAN_ISSUE_WEIGHT[s],
                default=None,
            )
            _n_issue_flights = sum(1 for s in _flight_severities if s)
            _client_blocks.append({
                "client_id": _client_id, "client_name": _client_name, "group": _client_group,
                "worst": _worst, "n_issue_flights": _n_issue_flights,
            })

        _client_blocks.sort(key=lambda b: (-IO_PLAN_ISSUE_WEIGHT.get(b["worst"], 0), b["client_name"]))

        for _block in _client_blocks:
            _emoji = _SEVERITY_EMOJI[_block["worst"]]
            _label = (
                f"{_emoji} **{_block['client_name']}** -- {len(_block['group'])} periodo(s)"
                + (f" · {_block['n_issue_flights']} com achado" if _block["n_issue_flights"] else " · sem incongruencia")
            )
            with st.expander(_label, expanded=(_block["worst"] == "critico")):
                for _r in _block["group"].itertuples():
                    _issues = _flight_issues.get((_block["client_id"], _r.flight_start, _r.flight_end), [])
                    _severity = _flight_worst_severity(_issues)
                    _period_label = f"**{_r.flight_start:%d/%m/%Y} – {_r.flight_end:%d/%m/%Y}**"
                    _metrics_line = (
                        f"Impressoes: `{_r.planned_impressions:,.0f}`" if pd.notna(_r.planned_impressions) else "Impressoes: `-`"
                    ) + "  ·  " + (
                        f"Cliques: `{_r.planned_clicks:,.0f}`" if pd.notna(_r.planned_clicks) else "Cliques: `-`"
                    ) + "  ·  " + (
                        f"Investimento: `R$ {_r.planned_spend_gross:,.0f}`" if pd.notna(_r.planned_spend_gross) else "Investimento: `-`"
                    )
                    _issue_lines = "\n".join(
                        f"- {_SEVERITY_ICON[i['severity']]} **{i['label']}** -- {i['detail']} "
                        f"({_STATUS_ICON[i.get('status', 'pendente')]} {IO_PLAN_STATUS_LABELS[i.get('status', 'pendente')][0]})"
                        for i in _issues
                    )
                    _body = f"{_period_label}  \n{_metrics_line}" + (f"\n\n{_issue_lines}" if _issue_lines else "")
                    _caption_line = f"`{_r.source_file}` · versao `{_r.plan_version}` · carregado em {pd.Timestamp(_r.loaded_at):%d/%m/%Y %H:%M}"

                    if _severity == "critico":
                        st.error(_body, icon=":material/error:")
                        st.caption(_caption_line)
                    elif _severity == "atencao":
                        st.warning(_body, icon=":material/warning:")
                        st.caption(_caption_line)
                    elif _severity == "informativo":
                        st.info(_body, icon=":material/info:")
                        st.caption(_caption_line)
                    else:
                        with st.container(border=True):
                            st.markdown(f":material/check_circle: {_period_label}  \n{_metrics_line}")
                            st.caption(_caption_line)

                    # ─────────────────────────────────────────────────────
                    # Drill-down opcional "raio-x" do import -- pedido do
                    # Douglas apos testar o conceito (2026-09-06): sem isso
                    # ele precisava abrir o BigQuery manualmente toda vez que
                    # um alerta aparecia aqui. Fonte: raw.io_plan_drive_snapshot
                    # (linha-item, descartada como agregado principal mas
                    # reaproveitada aqui como detalhe). st.popover (nao
                    # st.expander) de proposito -- o nivel Cliente ja usa
                    # st.expander, e Streamlit nao permite expander aninhado
                    # dentro de expander; popover nao tem essa restricao.
                    # Dados ja carregados uma unica vez pra TODOS os clientes/
                    # flights (load_io_plan_raw_detail) -- aqui e so um
                    # filtro em memoria, nao dispara query nova por card.
                    # ─────────────────────────────────────────────────────
                    _flight_detail = _io_raw_detail_df[
                        (_io_raw_detail_df["client_id"] == _block["client_id"])
                        & (_io_raw_detail_df["flight_start"] == _r.flight_start)
                        & (_io_raw_detail_df["flight_end"] == _r.flight_end)
                    ] if not _io_raw_detail_df.empty else _io_raw_detail_df

                    with st.popover(":material/manage_search: Ver detalhe do import (raw)", use_container_width=False):
                        if _flight_detail.empty:
                            st.caption(
                                "Sem linha-item em `raw.io_plan_drive_snapshot` para este periodo "
                                "(pode ser plano carregado por outra via, ex. upload manual antigo)."
                            )
                        else:
                            _distinct_files = sorted(_flight_detail["source_file"].dropna().unique().tolist())
                            st.markdown(f"**{len(_distinct_files)} arquivo(s) alimentando este periodo:**")
                            for _f in _distinct_files:
                                st.caption(f"`{_f}`")
                            if len(_distinct_files) > 1:
                                st.warning(
                                    ":material/warning: Mais de um arquivo fonte no mesmo periodo -- "
                                    "conferir se e esperado (split de planilha) ou se e sinal de import duplicado."
                                )

                            _flight_labels = sorted(_flight_detail["flight_label"].dropna().unique().tolist())
                            if _flight_labels:
                                st.caption("Periodo/label literal da planilha (`flight_label`): " + ", ".join(_flight_labels))
                            else:
                                st.caption("`flight_label` vazio para este periodo (comum -- nem toda planilha preenche esse campo).")

                            st.markdown("**Quebra por estrategia:**")
                            st.dataframe(
                                _flight_detail[[
                                    "strategy_name", "platform", "format", "buy_model",
                                    "impressions_cpm", "impressions_est", "monthly_spend",
                                    "unit_price", "clicks", "source_file",
                                ]].sort_values("strategy_name"),
                                use_container_width=True, hide_index=True,
                                column_config={
                                    "strategy_name": "Estrategia", "platform": "Plataforma", "format": "Formato",
                                    "buy_model": "Modelo de compra",
                                    "impressions_cpm": st.column_config.NumberColumn("Impr. (CPM)", format="%d"),
                                    "impressions_est": st.column_config.NumberColumn("Impr. (estimado)", format="%d"),
                                    "monthly_spend": st.column_config.NumberColumn("Spend mensal", format="R$ %.2f"),
                                    "unit_price": "Preco unitario", "clicks": "Cliques", "source_file": "Arquivo",
                                },
                            )
                            st.caption(
                                "Impressoes planejadas final = COALESCE(impressions_cpm, impressions_est) -- "
                                "os dois campos aparecem lado a lado aqui de proposito pra auditar visualmente "
                                "qual foi usado (ver fix de 2026-09-06 em sync_drive.py: era SOMA, virou COALESCE)."
                            )

                    # ─────────────────────────────────────────────────────
                    # Status de tratamento por achado -- pedido do Douglas
                    # (2026-09-06): sem isso o mesmo achado volta "critico"
                    # pra sempre a cada reload. Persistido em
                    # core.io_plan_finding_status (ver DDL, join_finding_status,
                    # save_io_plan_finding_status). Um achado por bloco dentro
                    # do popover (um flight pode ter mais de 1 achado
                    # simultaneo -- cada um rastreado/resolvido independente).
                    # HUB_READ_ONLY tambem gate esta escrita (mesmo padrao das
                    # outras abas que escrevem) -- em prod Fase 1, so mostra
                    # o status leia-apenas, sem os controles de edicao.
                    # ─────────────────────────────────────────────────────
                    if _issues:
                        with st.popover(":material/task_alt: Gerenciar status dos achados", use_container_width=False):
                            for _idx, _issue in enumerate(_issues):
                                st.markdown(f"**{_issue['label']}**")
                                _status_key = (
                                    f"io_status_{_block['client_id']}_{_r.flight_start}_{_r.flight_end}"
                                    f"_{_issue['heuristic_name']}"
                                )
                                if HUB_READ_ONLY:
                                    _cur_label, _cur_color, _cur_icon = IO_PLAN_STATUS_LABELS[_issue.get("status", "pendente")]
                                    st.badge(_cur_label, icon=_cur_icon, color=_cur_color)
                                    if _issue.get("comment"):
                                        st.caption(f"Comentario: {_issue['comment']}")
                                else:
                                    _status_options = list(IO_PLAN_STATUS_LABELS.keys())
                                    _new_status = st.selectbox(
                                        "Status", options=_status_options,
                                        format_func=lambda s: IO_PLAN_STATUS_LABELS[s][0],
                                        index=_status_options.index(_issue.get("status", "pendente")),
                                        key=f"{_status_key}_select",
                                    )
                                    _comment_val = _issue.get("comment") or ""
                                    if _new_status == "resolvido":
                                        _comment_val = st.text_area(
                                            "O que foi corrigido na fonte? (obrigatorio)",
                                            value=_comment_val, key=f"{_status_key}_comment_resolvido",
                                        )
                                    elif _new_status == "esperado":
                                        _comment_val = st.text_input(
                                            "Motivo (opcional)", value=_comment_val, key=f"{_status_key}_comment_esperado",
                                        )
                                    if _issue.get("status_updated_at") is not None:
                                        st.caption(f"Ultima atualizacao: {pd.Timestamp(_issue['status_updated_at']):%d/%m/%Y %H:%M}")
                                    _save_disabled = _new_status == "resolvido" and not _comment_val.strip()
                                    if st.button("Salvar status", key=f"{_status_key}_save", disabled=_save_disabled):
                                        _save_result = save_io_plan_finding_status(
                                            _io_project, _block["client_id"], _r.flight_start, _r.flight_end,
                                            _issue["heuristic_name"], _new_status, _comment_val,
                                        )
                                        if _save_result["ok"]:
                                            st.success(_save_result["detail"])
                                            load_io_plan_finding_status.clear()
                                            st.rerun()
                                        else:
                                            st.error(_save_result["detail"])
                                if _idx < len(_issues) - 1:
                                    st.divider()

                if _block["client_id"] in _gaps_by_client:
                    st.markdown(
                        ":material/calendar_month: **Meses sem nenhum flight cadastrado:** "
                        + ", ".join(_gaps_by_client[_block["client_id"]])
                    )

        st.divider()

        # ─────────────────────────────────────────────────────────────────
        # Gatilho on-demand "corrigir na fonte -> reprocessar" -- pedido do
        # Douglas (2026-09-06): achou um problema aqui, corrige a planilha no
        # Drive, dispara sem abrir terminal. Ver comentario grande em
        # IO_PLAN_ADMIN_URL/trigger_io_plan_resync() (topo do arquivo) para o
        # desenho completo de seguranca. ATENCAO -- ESTE BOTAO SEMPRE ESCREVE
        # EM PRODUCAO (adframework), independente do radio "Ambiente" acima
        # (sync_drive.py so existe contra producao) -- por isso fica atras do
        # mesmo HUB_READ_ONLY que protege as outras abas de escrita do hub.
        # ─────────────────────────────────────────────────────────────────
        st.markdown("#### :material/bolt: Corrigiu a planilha? Reprocessar agora")
        if HUB_READ_ONLY:
            st.info(
                "Reprocessamento on-demand desabilitado neste deploy -- Fase 1 do Hub de producao e "
                "read-only. Use o Hub de staging (ou local) para disparar isso."
            )
        else:
            st.warning(
                ":material/warning: Este botao SEMPRE escreve em `adframework` (producao) -- "
                "`sync_drive.py` nao tem versao de staging. Isso vale mesmo se voce estiver olhando "
                "'Staging' no seletor de ambiente acima (aquele seletor so afeta a LEITURA desta tela)."
            )
            if not IO_PLAN_ADMIN_SYNC_TOKEN:
                st.error(
                    ":material/lock: `IO_PLAN_ADMIN_SYNC_TOKEN` nao configurado neste ambiente do Hub -- "
                    "os botoes abaixo ficam desabilitados ate o token do servico `io-plan-admin` ser "
                    "definido (pedir ao Douglas, nunca adivinhar/hardcodear)."
                )

            _resync_log_key = "io_plan_resync_log"
            if _resync_log_key not in st.session_state:
                st.session_state[_resync_log_key] = []  # lista de dicts: {quando, modo, alvo, resultados}

            _trigger_disabled = not IO_PLAN_ADMIN_SYNC_TOKEN
            _client_names_sorted = sorted(_io_report["deduped"]["client_name"].unique().tolist())

            col_single, col_all = st.columns(2)

            with col_single:
                with st.container(border=True):
                    st.markdown("**Um cliente especifico**")
                    _target_client = st.selectbox(
                        "Cliente", _client_names_sorted, key="io_resync_client_select",
                        disabled=_trigger_disabled,
                    )
                    _confirm_single = st.text_input(
                        f"Digite exatamente `{_target_client}` para habilitar",
                        key="io_resync_confirm_single", disabled=_trigger_disabled,
                    )
                    _single_ready = bool(_target_client) and _confirm_single.strip() == _target_client
                    if st.button(
                        "Rodar sync + refresh (este cliente)", key="io_resync_run_single",
                        disabled=_trigger_disabled or not _single_ready, type="primary",
                    ):
                        with st.spinner(f"Sincronizando {_target_client} e reprocessando gold..."):
                            _slug = _target_client.lower()
                            _results = trigger_io_plan_resync(_slug)
                        st.session_state[_resync_log_key].insert(0, {
                            "quando": datetime.now(timezone.utc), "modo": "individual",
                            "alvo": _target_client, "resultados": _results,
                        })
                        st.rerun()

            with col_all:
                with st.container(border=True):
                    st.markdown("**Todos os clientes**")
                    st.caption("Roda sync_drive sem filtro (todo o CLIENT_MAP) + 1 refresh unico no final.")
                    _confirm_all = st.text_input(
                        "Digite `CONFIRMAR TODOS` para habilitar", key="io_resync_confirm_all",
                        disabled=_trigger_disabled,
                    )
                    _all_ready = _confirm_all.strip() == "CONFIRMAR TODOS"
                    if st.button(
                        "Rodar sync + refresh (TODOS)", key="io_resync_run_all",
                        disabled=_trigger_disabled or not _all_ready, type="primary",
                    ):
                        with st.spinner("Sincronizando todos os clientes e reprocessando gold..."):
                            _results = trigger_io_plan_resync(None)
                        st.session_state[_resync_log_key].insert(0, {
                            "quando": datetime.now(timezone.utc), "modo": "todos",
                            "alvo": "todos os clientes", "resultados": _results,
                        })
                        st.rerun()

            if st.session_state[_resync_log_key]:
                st.markdown("**Log desta sessao**")
                for _entry in st.session_state[_resync_log_key][:10]:
                    _all_ok = all(r["ok"] for r in _entry["resultados"])
                    _icon = ":material/check_circle:" if _all_ok else ":material/error:"
                    with st.container(border=True):
                        st.markdown(f"{_icon} **{_entry['quando']:%d/%m/%Y %H:%M UTC}** -- {_entry['modo']} -- `{_entry['alvo']}`")
                        for _r in _entry["resultados"]:
                            _r_icon = ":material/check_circle:" if _r["ok"] else ":material/error:"
                            st.caption(f"{_r_icon} {_r['stage']}: {_r['detail']}")
            else:
                st.caption("Nenhum disparo nesta sessao ainda -- o log e local a sessao (nao persiste entre reinicios do container).")

        st.divider()
        st.markdown("#### :material/table_view: Visao plana (auditoria/export)")
        st.caption("Mesmos dados acima, em formato de tabela -- util pra exportar ou conferir tudo de uma vez.")

        with st.expander(f":material/calendar_month: Gaps de cobertura ({_n_gaps} mes(es) sem flight)"):
            st.caption("Mes de competencia, dentro do range ativo do cliente, sem nenhum dia coberto por um flight. Informativo -- pode ser pausa intencional.")
            if _io_report["gap_cobertura"].empty:
                st.badge("nenhum gap encontrado", icon=":material/check_circle:", color="green")
            else:
                st.dataframe(
                    _io_report["gap_cobertura"], use_container_width=True, hide_index=True,
                    column_config={"client_name": "Cliente", "client_id": "client_id", "mes_sem_flight": "Mes sem flight"},
                )

        with st.expander(f":material/layers: Flights com mais de uma versao carregada ({_n_versions})"):
            st.caption(
                "Mesmo client_id+flight_start+flight_end com mais de uma linha em core.io_plan_manual "
                "(plan_version diferente) -- informativo, substituicao de plano e esperada; a deteccao "
                "acima ja usa so a versao mais recente (loaded_at) de cada flight."
            )
            if _io_report["multiplas_versoes"].empty:
                st.badge("nenhum flight com mais de 1 versao", icon=":material/check_circle:", color="green")
            else:
                st.dataframe(
                    _io_report["multiplas_versoes"], use_container_width=True, hide_index=True,
                    column_config={
                        "client_name": "Cliente", "client_id": "client_id",
                        "flight_start": "Inicio", "flight_end": "Fim",
                        "n_versoes": "N. versoes", "versoes": "Versoes",
                    },
                )

        with st.expander(":material/table_view: Todos os flights (deduplicados, mais recente por periodo)"):
            _display_cols = [
                "client_name", "client_id", "flight_start", "flight_end",
                "planned_impressions", "planned_clicks", "planned_spend_gross",
                "planned_spend_net", "plan_version", "source_file", "loaded_at",
            ]
            st.dataframe(
                _io_report["deduped"][_display_cols].sort_values(["client_id", "flight_start"]),
                use_container_width=True, hide_index=True,
            )


# ─────────────────────────────────────────────────────────────────────────
# Aba 4 -- Formatos/Regras: CRUD de core.dict_format + core.strategy_format_map
# + fila de "estrategias nao classificadas". Task Notion
# 3d49d0f6219e81a4bc8cea05bd3fdd72 (2026-09-07). Ver bloco de comentario
# grande junto das funcoes (load_dict_format e vizinhas, acima) para o
# desenho completo -- aqui so a UI.
# ─────────────────────────────────────────────────────────────────────────
with tab_formats:
    st.subheader("Gerenciamento de Formatos/Regras")
    st.caption(
        "CRUD de `core.dict_format` (platform+formato -> goal_type) e "
        "`core.strategy_format_map` (keyword -> formato), mais a fila de estrategias "
        "que ainda nao tem formato reconhecido. Mesmo padrao SCD2 do resto do repo -- "
        "nunca sobrescreve o valor de uma regra, so encerra vigencia (effective_to) + "
        "cria uma linha nova."
    )

    _fmt_env_choice = st.radio(
        "Ambiente", [e["label"] for e in ENVIRONMENTS], horizontal=True, key="formats_env",
    )
    _fmt_project = next(e["project_id"] for e in ENVIRONMENTS if e["label"] == _fmt_env_choice)
    st.caption(f"Projeto GCP: `{_fmt_project}`")
    if HUB_READ_ONLY:
        st.info("Escrita (adicionar/encerrar regra, classificar estrategia) desabilitada em producao -- Fase 1 e read-only. Use o Hub de staging para essas acoes.")

    st.divider()

    # ── Secao 1: fila de estrategias nao classificadas (a mais importante --
    # resolve o caso real do Audio Ads) ─────────────────────────────────────
    st.markdown("#### :material/pending_actions: Estrategias nao classificadas")
    st.caption(
        "`strategy_name` distintos que hoje resolvem `formato = NULL` em `stg.io_plan` -- "
        "nenhuma keyword de `strategy_format_map` bate com o texto. Classificar aqui "
        "escreve em `core.strategy_format_map` e a estrategia some desta fila na proxima "
        "carga da tela (a view `stg.io_plan` ja resolve ao vivo via `core.resolve_strategy_format()`)."
    )
    with st.spinner("Consultando stg.io_plan..."):
        _unclassified_df = load_unclassified_strategies(_fmt_project)

    if _unclassified_df.empty:
        st.badge("nenhuma estrategia pendente", icon=":material/check_circle:", color="green")
    else:
        st.warning(f":material/warning: {len(_unclassified_df)} estrategia(s) sem formato reconhecido.")
        for _row in _unclassified_df.itertuples():
            with st.container(border=True):
                st.markdown(f"**{_row.strategy_name}**")
                st.caption(
                    f"{_row.n_linhas} linha(s) · {_row.n_clientes} cliente(s) · {_row.n_flights} flight(s) "
                    f"-- ex: {_row.clientes_exemplo}"
                )
                if not HUB_READ_ONLY:
                    _key_base = f"unclassified_{_row.strategy_name}"
                    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 1.3])
                    _kw = fc1.text_input(
                        "Keyword", value=_row.strategy_name.lower().strip(),
                        key=f"{_key_base}_kw", help="substring procurada em LOWER(strategy_name)",
                    )
                    _fmt = fc2.text_input("Formato", key=f"{_key_base}_fmt", placeholder="ex: Audio")
                    _confirmed_by = fc3.text_input("Confirmado por", key=f"{_key_base}_by", placeholder="ex: comercial")
                    with fc4:
                        st.write("")
                        st.write("")
                        if st.button("Classificar", key=f"{_key_base}_btn", disabled=not (_kw.strip() and _fmt.strip() and _confirmed_by.strip())):
                            _notes = f"Classificado via fila de pendencias do Hub -- strategy_name original: '{_row.strategy_name}'."
                            _active_n = _scd2_active_count(_fmt_project, STRATEGY_FORMAT_MAP_TABLE, {"keyword": _kw.strip().lower()})
                            _result = _scd2_insert_new_version(
                                _fmt_project, STRATEGY_FORMAT_MAP_TABLE,
                                {"keyword": _kw.strip().lower(), "formato": _fmt.strip(), "notes": _notes, "confirmed_by": _confirmed_by.strip()},
                                close_filters={"keyword": _kw.strip().lower()} if _active_n else None,
                            )
                            if _result["ok"]:
                                st.success(_result["detail"])
                                load_strategy_format_map.clear()
                                load_unclassified_strategies.clear()
                                st.rerun()
                            else:
                                st.error(_result["detail"])

    st.divider()

    # ── Secao 2: CRUD core.dict_format ──────────────────────────────────────
    st.markdown("#### :material/tune: Formatos (`core.dict_format`)")
    st.caption("Mapeia (platform, formato) -> goal_type. Usado em gold.fact_io_plan/fact_pacing pra calcular investimento_realizado.")

    with st.spinner("Consultando core.dict_format..."):
        _dict_format_df = load_dict_format(_fmt_project)
    _dict_format_active = _dict_format_df[_dict_format_df["effective_to"].isna()].sort_values(["platform", "formato"])

    st.dataframe(
        _dict_format_active[["platform", "formato", "goal_type", "confirmed_by", "effective_from", "notes"]],
        use_container_width=True, hide_index=True,
        column_config={
            "platform": "Platform", "formato": "Formato", "goal_type": "Goal type",
            "confirmed_by": "Confirmado por", "effective_from": "Vigente desde", "notes": "Notas",
        },
    )
    with st.expander(f"Ver historico completo ({len(_dict_format_df)} linha(s), incluindo encerradas)"):
        st.dataframe(_dict_format_df, use_container_width=True, hide_index=True)

    if not HUB_READ_ONLY:
        with st.expander(":material/add_circle: Adicionar novo formato"):
            dc1, dc2, dc3 = st.columns(3)
            _new_platform = dc1.selectbox("Platform", FORMAT_PLATFORM_OPTIONS, key="dict_format_new_platform")
            _new_formato = dc2.text_input("Formato", key="dict_format_new_formato", placeholder="ex: Audio")
            _new_goal_type = dc3.selectbox("Goal type", FORMAT_GOAL_TYPE_OPTIONS, key="dict_format_new_goal_type")
            _new_confirmed_by = st.text_input("Confirmado por (obrigatorio)", key="dict_format_new_confirmed_by", placeholder="ex: comercial")
            _new_notes = st.text_area("Notas", key="dict_format_new_notes")
            if st.button("Adicionar regra", key="dict_format_add_btn", disabled=not (_new_formato.strip() and _new_confirmed_by.strip())):
                _active_n = _scd2_active_count(_fmt_project, FORMAT_DICT_TABLE, {"platform": _new_platform, "formato": _new_formato.strip()})
                _result = _scd2_insert_new_version(
                    _fmt_project, FORMAT_DICT_TABLE,
                    {"platform": _new_platform, "formato": _new_formato.strip(), "goal_type": _new_goal_type,
                     "notes": _new_notes, "confirmed_by": _new_confirmed_by.strip()},
                    close_filters={"platform": _new_platform, "formato": _new_formato.strip()} if _active_n else None,
                )
                if _result["ok"]:
                    st.success(_result["detail"])
                    load_dict_format.clear()
                    st.rerun()
                else:
                    st.error(_result["detail"])

        if not _dict_format_active.empty:
            with st.expander(":material/block: Encerrar vigencia de um formato"):
                _dict_format_labels = [f"{r.platform} / {r.formato} ({r.goal_type})" for r in _dict_format_active.itertuples()]
                _close_choice = st.selectbox("Regra vigente", _dict_format_labels, key="dict_format_close_select")
                _close_row = _dict_format_active.iloc[_dict_format_labels.index(_close_choice)]
                if st.button("Encerrar vigencia (nao apaga historico)", key="dict_format_close_btn"):
                    _result = _scd2_close_active(_fmt_project, FORMAT_DICT_TABLE, {"platform": _close_row["platform"], "formato": _close_row["formato"]})
                    if _result["ok"]:
                        st.success(_result["detail"])
                        load_dict_format.clear()
                        st.rerun()
                    else:
                        st.error(_result["detail"])

    st.divider()

    # ── Secao 3: CRUD core.strategy_format_map ──────────────────────────────
    st.markdown("#### :material/label: Palavras-chave (`core.strategy_format_map`)")
    st.caption("Mapeia keyword (substring de strategy_name, case-insensitive) -> formato. Resolvido via core.resolve_strategy_format() dentro de stg.io_plan.")

    with st.spinner("Consultando core.strategy_format_map..."):
        _strategy_map_df = load_strategy_format_map(_fmt_project)
    _strategy_map_active = _strategy_map_df[_strategy_map_df["effective_to"].isna()].sort_values("keyword")

    st.dataframe(
        _strategy_map_active[["keyword", "formato", "confirmed_by", "effective_from", "notes"]],
        use_container_width=True, hide_index=True,
        column_config={
            "keyword": "Keyword", "formato": "Formato",
            "confirmed_by": "Confirmado por", "effective_from": "Vigente desde", "notes": "Notas",
        },
    )
    with st.expander(f"Ver historico completo ({len(_strategy_map_df)} linha(s), incluindo encerradas)"):
        st.dataframe(_strategy_map_df, use_container_width=True, hide_index=True)

    if not HUB_READ_ONLY:
        with st.expander(":material/add_circle: Adicionar nova keyword"):
            kc1, kc2 = st.columns(2)
            _new_keyword = kc1.text_input("Keyword", key="strategy_map_new_keyword", placeholder="ex: audio")
            _new_kw_formato = kc2.text_input("Formato", key="strategy_map_new_formato", placeholder="ex: Audio")
            _new_kw_confirmed_by = st.text_input("Confirmado por (obrigatorio)", key="strategy_map_new_confirmed_by", placeholder="ex: comercial")
            _new_kw_notes = st.text_area("Notas", key="strategy_map_new_notes")
            if st.button("Adicionar keyword", key="strategy_map_add_btn", disabled=not (_new_keyword.strip() and _new_kw_formato.strip() and _new_kw_confirmed_by.strip())):
                _kw_norm = _new_keyword.strip().lower()
                _active_n = _scd2_active_count(_fmt_project, STRATEGY_FORMAT_MAP_TABLE, {"keyword": _kw_norm})
                _result = _scd2_insert_new_version(
                    _fmt_project, STRATEGY_FORMAT_MAP_TABLE,
                    {"keyword": _kw_norm, "formato": _new_kw_formato.strip(), "notes": _new_kw_notes, "confirmed_by": _new_kw_confirmed_by.strip()},
                    close_filters={"keyword": _kw_norm} if _active_n else None,
                )
                if _result["ok"]:
                    st.success(_result["detail"])
                    load_strategy_format_map.clear()
                    load_unclassified_strategies.clear()
                    st.rerun()
                else:
                    st.error(_result["detail"])

        if not _strategy_map_active.empty:
            with st.expander(":material/block: Encerrar vigencia de uma keyword"):
                _strategy_map_labels = [f"{r.keyword} -> {r.formato}" for r in _strategy_map_active.itertuples()]
                _close_kw_choice = st.selectbox("Regra vigente", _strategy_map_labels, key="strategy_map_close_select")
                _close_kw_row = _strategy_map_active.iloc[_strategy_map_labels.index(_close_kw_choice)]
                if st.button("Encerrar vigencia (nao apaga historico)", key="strategy_map_close_btn"):
                    _result = _scd2_close_active(_fmt_project, STRATEGY_FORMAT_MAP_TABLE, {"keyword": _close_kw_row["keyword"]})
                    if _result["ok"]:
                        st.success(_result["detail"])
                        load_strategy_format_map.clear()
                        load_unclassified_strategies.clear()
                        st.rerun()
                    else:
                        st.error(_result["detail"])

    st.divider()

    # ── Secao 4: CRUD core.advertiser_platform_rules (regra GLOBAL ou por
    # cliente) ───────────────────────────────────────────────────────────────
    st.markdown("#### :material/hub: Regras de Plataforma por Anunciante (`core.advertiser_platform_rules`)")
    st.caption(
        "Remapeia `platform_from` (ex: 'unknown') -> `platform_to` real, por formato -- "
        "opcionalmente restrito a um cliente. Regra GLOBAL (sem cliente) vale pra todos; "
        "uma regra especifica de cliente sempre vence sobre a global pro mesmo periodo."
    )

    _fmt_supports_global = check_advertiser_rules_supports_global(_fmt_project)
    if not _fmt_supports_global:
        st.info(
            ":material/info: Este projeto (`" + _fmt_project + "`) ainda nao teve a migracao de regra "
            "GLOBAL aplicada (`client_id` continua obrigatorio) -- so da pra criar regra por cliente "
            "especifico aqui. Confirmado ao vivo via schema, nao e um valor fixo -- assim que a migracao "
            "for promovida pra este projeto, a opcao \"Global\" aparece sozinha, sem precisar mexer no codigo."
        )

    with st.spinner("Consultando core.advertiser_platform_rules..."):
        _platform_rules_df = load_advertiser_platform_rules(_fmt_project)
    _platform_rules_df = _platform_rules_df.copy()
    _platform_rules_df["escopo"] = _platform_rules_df.apply(
        lambda r: "TODOS OS CLIENTES" if pd.isna(r["client_id"]) else (r["client_name"] or r["client_id"]), axis=1,
    )
    _platform_rules_active = _platform_rules_df[_platform_rules_df["effective_to"].isna()].sort_values(["platform_from", "formato"])

    st.dataframe(
        _platform_rules_active[["escopo", "platform_from", "formato", "platform_to", "confirmed_by", "effective_from", "notes"]],
        use_container_width=True, hide_index=True,
        column_config={
            "escopo": "Escopo", "platform_from": "Platform (de)", "formato": "Formato",
            "platform_to": "Platform (para)", "confirmed_by": "Confirmado por",
            "effective_from": "Vigente desde", "notes": "Notas",
        },
    )
    with st.expander(f"Ver historico completo ({len(_platform_rules_df)} linha(s), incluindo encerradas)"):
        st.dataframe(
            _platform_rules_df[["escopo", "platform_from", "formato", "platform_to", "confirmed_by", "effective_from", "effective_to", "notes"]],
            use_container_width=True, hide_index=True,
        )

    if not HUB_READ_ONLY:
        with st.expander(":material/add_circle: Adicionar nova regra"):
            _scope_options = ["Cliente especifico"] + (["Global (todos os clientes)"] if _fmt_supports_global else [])
            _scope_choice = st.radio("Escopo", _scope_options, key="platform_rule_new_scope", horizontal=True)
            _new_rule_client_id = None
            if _scope_choice == "Cliente especifico":
                _dim_client_df = load_dim_client_options(_fmt_project)
                if _dim_client_df.empty:
                    st.warning("Nenhum cliente ativo encontrado em `core.dim_client` neste projeto.")
                else:
                    _client_labels = [f"{r.name} ({r.client_id})" for r in _dim_client_df.itertuples()]
                    _client_choice = st.selectbox("Cliente", _client_labels, key="platform_rule_new_client")
                    _new_rule_client_id = _dim_client_df.iloc[_client_labels.index(_client_choice)]["client_id"]

            pc1, pc2, pc3 = st.columns(3)
            _new_platform_from = pc1.text_input("Platform (de)", value="unknown", key="platform_rule_new_from")
            _new_rule_formato = pc2.text_input("Formato", key="platform_rule_new_formato", placeholder="ex: PUSH")
            _new_platform_to = pc3.text_input("Platform (para)", key="platform_rule_new_to", placeholder="ex: siprocal")
            _new_rule_confirmed_by = st.text_input("Confirmado por (obrigatorio)", key="platform_rule_new_confirmed_by", placeholder="ex: douglas")
            _new_rule_notes = st.text_area("Notas / evidencia", key="platform_rule_new_notes")

            _rule_ready = (
                _new_platform_from.strip() and _new_rule_formato.strip() and _new_platform_to.strip()
                and _new_rule_confirmed_by.strip()
                and (_scope_choice == "Global (todos os clientes)" or _new_rule_client_id is not None)
            )
            if st.button("Adicionar regra", key="platform_rule_add_btn", disabled=not _rule_ready):
                _result = add_advertiser_platform_rule(
                    _fmt_project, _new_rule_client_id, _new_platform_from.strip(), _new_rule_formato.strip(),
                    _new_platform_to.strip(), _new_rule_confirmed_by.strip(), _new_rule_notes,
                )
                if _result["ok"]:
                    st.success(_result["detail"])
                    load_advertiser_platform_rules.clear()
                    st.rerun()
                else:
                    st.error(_result["detail"])

        if not _platform_rules_active.empty:
            with st.expander(":material/block: Encerrar vigencia de uma regra"):
                _platform_rule_labels = [
                    f"{r.escopo} -- {r.platform_from}/{r.formato} -> {r.platform_to}" for r in _platform_rules_active.itertuples()
                ]
                _platform_rule_choice = st.selectbox("Regra vigente", _platform_rule_labels, key="platform_rule_close_select")
                _platform_rule_row = _platform_rules_active.iloc[_platform_rule_labels.index(_platform_rule_choice)]
                if st.button("Encerrar vigencia (nao apaga historico)", key="platform_rule_close_btn"):
                    _close_client_id = None if pd.isna(_platform_rule_row["client_id"]) else _platform_rule_row["client_id"]
                    _result = close_advertiser_platform_rule(
                        _fmt_project, _close_client_id, _platform_rule_row["platform_from"], _platform_rule_row["formato"],
                    )
                    if _result["ok"]:
                        st.success(_result["detail"])
                        load_advertiser_platform_rules.clear()
                        st.rerun()
                    else:
                        st.error(_result["detail"])

# ─────────────────────────────────────────────────────────────────────────
# Aba 5 -- Propostas de Mudanca: fila generica de aprovacao humana sobre
# core.change_proposals. Hoje so source='siprocal_diff' (reconciliacao
# incremental de raw.sp_delivery), mas a tabela e generica de proposito --
# esta aba tambem, para servir qualquer fonte futura sem redesenho.
# ─────────────────────────────────────────────────────────────────────────
with tab_proposals:
    if HUB_READ_ONLY:
        st.info("Propostas de Mudanca (aprovar/rejeitar) desabilitado em producao -- Fase 1 e read-only. Use o Hub de staging para esta acao.")
    else:
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
                            disabled=ambiguous or not confirmed, type="primary",
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
# Aba 6 -- Ajustes de Dados Historicos. Fluxo generico (2026-08-05/06,
# generaliza overrides historicos alem da Cora, ver docs/known_issues.md item
# S4 -- o fluxo antigo hardcoded so-Cora foi removido em 2026-08-11 a pedido
# do Douglas, ver CHANGELOG.md):
#   1) Upload -- sobe a planilha crua do comercial como landing RAW literal em
#      douglas-bq-staging (raw.historical_uploads/_meta).
#   2) Comparacao -- planilha pousada vs. amostra real de gold.fact_pacing.
#   3) Config por cliente -- liga/desliga do override para qualquer cliente
#      que ja tenha dado carregado em stg.historical_overrides_delivery
#      (movida de core em 2026-08-06), range real calculado ao vivo e status
#      em core.client_reporting_source_config (SCD2).
# ─────────────────────────────────────────────────────────────────────────
with tab_overrides:
    if HUB_READ_ONLY:
        st.info("Ajustes de Dados Historicos (upload/toggle de override) desabilitado em producao -- Fase 1 e read-only. Use o Hub de staging para esta acao.")
    else:
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

            st.markdown("**ou** cole o link de uma planilha do Google Sheets")
            landing_gsheet_link = st.text_input(
                "Link do Google Sheets",
                key="landing_gsheet_link",
                placeholder="https://docs.google.com/spreadsheets/d/...",
                help=(
                    "A planilha precisa estar compartilhada (permissao de visualizacao) com a "
                    "service account de leitura do hub -- se a leitura falhar por permissao, a "
                    "mensagem de erro abaixo vai indicar isso."
                ),
            )

            landing_raw_df = None
            landing_source_name = None

            if landing_gsheet_link.strip():
                gsheet_id = extract_gsheet_id(landing_gsheet_link)
                worksheet_titles = None
                try:
                    worksheet_titles = list_gsheet_worksheets(gsheet_id)
                except Exception as exc:
                    st.error(
                        "Nao consegui abrir essa planilha -- confirme que o link/ID esta correto e "
                        "que a planilha foi compartilhada (permissao de visualizacao) com a service "
                        f"account de leitura do hub. Erro: {exc}"
                    )

                if worksheet_titles:
                    landing_gsheet_tab = st.selectbox(
                        "Aba da planilha", worksheet_titles, key="landing_gsheet_tab"
                    )
                    try:
                        landing_raw_df = read_gsheet_worksheet_raw(gsheet_id, landing_gsheet_tab)
                        landing_source_name = f"gsheet:{gsheet_id}:{landing_gsheet_tab}"
                    except Exception as exc:
                        landing_raw_df = None
                        st.error(f"Nao consegui ler a aba '{landing_gsheet_tab}' dessa planilha: {exc}")
            elif landing_upload is not None:
                try:
                    landing_raw_df = read_uploaded_spreadsheet_raw(landing_upload)
                    landing_source_name = landing_upload.name
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

                    landing_notes = st.text_area(
                        "Comentario / contexto (opcional)",
                        key="landing_notes",
                        placeholder=(
                            "Ex: planilha cobre Jan-Ago, mas so usar ate Jul (ago em diante "
                            "vem da plataforma real); formato mudou a partir de Mar; coluna X "
                            "esta em outra unidade..."
                        ),
                        help="Fica salvo junto com o upload -- ajuda a lembrar contexto na hora de normalizar depois.",
                    )
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
                            result = stage_raw_historical_upload(
                                landing_raw_df, landing_client_id, landing_source_name, landing_notes,
                            )
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
            "uma amostra real do mesmo periodo em `gold.fact_pacing` de "
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
                uploads_for_client["_status_label"] = uploads_for_client["promoted_at"].apply(
                    lambda v: "promovido" if pd.notna(v) else "aguardando normalizacao"
                )
                uploads_for_client["display"] = (
                    uploads_for_client["source_filename"] + " -- "
                    + uploads_for_client["uploaded_at"].astype(str)
                    + f" ({uploads_for_client['row_count']} linhas) -- "
                    + uploads_for_client["_status_label"]
                )
                compare_upload_display = st.selectbox(
                    "Upload", uploads_for_client["display"].tolist(), key="compare_upload_select"
                )
                compare_upload_row = uploads_for_client[
                    uploads_for_client["display"] == compare_upload_display
                ].iloc[0]
                compare_upload_id = compare_upload_row["upload_id"]
                if pd.notna(compare_upload_row.get("promoted_at")):
                    st.success(
                        f":material/check_circle: Promovido para `stg.historical_overrides_delivery` em "
                        f"{compare_upload_row['promoted_at']}. Dado deste upload ja pode ser ativado/"
                        "desativado na secao de liga-desliga abaixo.",
                        icon=":material/check_circle:",
                    )
                else:
                    st.warning(
                        ":material/hourglass_empty: Aguardando normalizacao -- este upload ainda NAO foi "
                        "promovido para `stg.historical_overrides_delivery`. O toggle de ativar/desativar "
                        "override abaixo, se existir dado para este cliente, reflete um upload ANTERIOR ja "
                        "aprovado -- nao este. Rode `historical_mappings/<client_id>.py` + "
                        "`load_historical_override.py --upload-id` antes de considerar este upload pronto.",
                        icon=":material/hourglass_empty:",
                    )
                if compare_upload_row.get("notes"):
                    st.caption(f":material/sticky_note_2: {compare_upload_row['notes']}")

                with st.expander(":material/science: Deletar este upload (provisorio -- staging)"):
                    st.warning(
                        ":material/warning: Apaga o upload por completo (raw + meta) -- foge do "
                        "principio 'RAW so INSERT' de proposito, so pra limpar teste/engano em "
                        "staging. Nao existe em producao.",
                        icon=":material/warning:",
                    )
                    del_upload_confirm = st.checkbox(
                        "Confirmo que quero deletar este upload definitivamente",
                        key=f"del_upload_confirm_{compare_upload_id}",
                    )
                    if st.button(
                        "Deletar upload", key=f"del_upload_btn_{compare_upload_id}",
                        disabled=not del_upload_confirm,
                    ):
                        try:
                            with st.spinner("Deletando..."):
                                delete_historical_upload(compare_upload_id)
                            st.success("Upload deletado.")
                            load_historical_uploads_for_client.clear()
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Erro ao deletar: {exc}")

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
                            f"*Dado real -- `gold.fact_pacing` ({HISTORICAL_OVERRIDE_PROJECT_ID}), "
                            f"{compare_start} a {compare_end}*"
                        )
                        try:
                            gold_sample_df = load_gold_sample_for_range(compare_client_id, compare_start, compare_end)
                        except (NotFound, Forbidden) as exc:
                            gold_sample_df = None
                            st.error(f"Nao consegui ler `gold.fact_pacing` em `{HISTORICAL_OVERRIDE_PROJECT_ID}`: {exc}")
                        except Exception as exc:
                            gold_sample_df = None
                            st.error(f"Erro ao ler `gold.fact_pacing`: {exc}")

                        if gold_sample_df is not None:
                            if gold_sample_df.empty:
                                coverage_min, coverage_max = load_gold_coverage_for_client(compare_client_id)
                                if coverage_min is None:
                                    st.warning(
                                        f":material/warning: `gold.fact_pacing` em "
                                        f"`{HISTORICAL_OVERRIDE_PROJECT_ID}` nao tem NENHUM dado para "
                                        f"`{compare_client_id}` -- nao ha o que comparar ainda (achado "
                                        "relevante, nao um erro de tela).",
                                        icon=":material/warning:",
                                    )
                                else:
                                    st.warning(
                                        f":material/warning: Sem sobreposicao de periodo -- a planilha "
                                        f"cobre {compare_start} a {compare_end}, mas o dado real de "
                                        f"`{compare_client_id}` em `gold.fact_pacing` so existe de "
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
            except Exception as exc:
                st.error(f"Erro ao consultar configuracao de overrides: {exc}")
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
                    with st.spinner("Atualizando stg.fact_pacing_base (refresh automatico)..."):
                        refresh_fact_pacing_base()
                    st.success("`stg.fact_pacing_base` atualizado -- fact_pacing/fact_delivery ja refletem.")
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
# Aba 7 -- Regras de Negocio: listagem de core.client_business_rules (staging,
# ver comentario de BUSINESS_RULES_TABLE) + criacao de regra nova + Pausar
# (dentro de cada card, ver _render_business_rule_card) + Simulador de Impacto
# (dado real ou modo demonstracao, ver mock_pacing_demo_data). Fluxo de "nova
# versao substituindo uma
# vigente" tambem NAO esta implementado nesta entrega -- se ja existe versao
# vigente para o (tipo, escopo) escolhido, a criacao e bloqueada com aviso
# (ver business_rule_exists_active); so cobre criar quando nao ha vigente e
# pausar. Escrita via get_staging_writer_bq_client() -- nunca a writer de
# producao.
# ─────────────────────────────────────────────────────────────────────────
with tab_business_rules:
    if HUB_READ_ONLY:
        st.info("Regras de Negocio (criar/pausar) desabilitado em producao -- Fase 1 e read-only. Use o Hub de staging para esta acao.")
    else:
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
        except Exception as exc:
            st.error(f"Erro ao consultar regras de negocio: {exc}")
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
                st.caption(
                    "Baseado nos campos reais de `gold.fact_pacing` -- e onde essa regra "
                    "sera aplicada. A regra diz: o campo abaixo nao pode superar o campo "
                    "de referencia em mais de X%."
                )
                field_col1, field_col2 = st.columns(2)
                with field_col1:
                    base_field = st.selectbox(
                        "Campo a limitar", options=list(FACT_PACING_FIELDS),
                        format_func=lambda f: FACT_PACING_FIELDS[f],
                        index=list(FACT_PACING_FIELDS).index("realized_impressions"),
                        key="new_rule_base_field",
                    )
                with field_col2:
                    reference_field = st.selectbox(
                        "Campo de referencia (limite)", options=list(FACT_PACING_FIELDS),
                        format_func=lambda f: FACT_PACING_FIELDS[f],
                        index=list(FACT_PACING_FIELDS).index("planned_impressions_daily"),
                        key="new_rule_reference_field",
                    )
                threshold_pct = st.number_input(
                    "Nao pode superar a referencia em mais de (%)", min_value=1, max_value=100,
                    value=20, step=1, key="new_rule_threshold",
                )
                strategies = st.multiselect(
                    "Estrategias (formato)", options=["native", "push", "video", "display", "retargeting"],
                    key="new_rule_strategies",
                )
                if base_field == reference_field:
                    st.warning("Campo a limitar e campo de referencia nao podem ser o mesmo.")
                params_valid = bool(strategies) and base_field != reference_field
                rule_params = {
                    "base_field": base_field,
                    "reference_field": reference_field,
                    "threshold_pct": int(threshold_pct),
                    "strategies": strategies,
                }
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

            if st.button("Salvar regra", disabled=not can_save, key="new_rule_save", type="primary"):
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

        sim_demo_mode = st.checkbox(
            "Modo demonstracao (dado de exemplo, nao consulta o BigQuery)",
            key="sim_demo_mode",
            help="Use se a consulta ao dado real falhar durante uma apresentacao -- os "
                 "numeros aqui sao fabricados (mesmo padrao de volume da Cora), nunca "
                 "dado real de nenhum cliente.",
        )
        if sim_demo_mode:
            st.info(
                ":material/theaters: Modo demonstracao ativo -- os numeros abaixo sao "
                "de exemplo, nao vem de nenhum cliente real.",
                icon=":material/theaters:",
            )

        if sim_demo_mode:
            sim_client_options_df = pd.DataFrame()
        else:
            try:
                sim_client_options_df = load_client_options()
            except Exception as exc:
                sim_client_options_df = pd.DataFrame()
                st.error(f"Erro ao carregar lista de clientes: {exc}")

        if not sim_demo_mode and sim_client_options_df.empty:
            st.warning("Nenhum cliente ativo encontrado.")
        else:
            sim_client_label_map = (
                dict(zip(sim_client_options_df["name"], sim_client_options_df["client_id"]))
                if not sim_demo_mode else {}
            )
            sim_col1, sim_col2 = st.columns(2)
            with sim_col1:
                if not sim_demo_mode:
                    sim_client_label = st.selectbox(
                        "Cliente", options=list(sim_client_label_map.keys()), key="sim_client",
                    )
                else:
                    st.text_input("Cliente", value="Exemplo (dado fabricado)", disabled=True)
            with sim_col2:
                sim_strategies = st.multiselect(
                    "Estrategias (formato)", options=["native", "push", "video", "display", "retargeting"],
                    default=["native", "push"], key="sim_strategies",
                )

            st.caption("Mesma logica do construtor de regra acima: campo a limitar vs. campo de referencia.")
            field_sim_col1, field_sim_col2, field_sim_col3 = st.columns([2, 2, 1])
            with field_sim_col1:
                sim_base_field = st.selectbox(
                    "Campo a limitar", options=list(FACT_PACING_FIELDS),
                    format_func=lambda f: FACT_PACING_FIELDS[f],
                    index=list(FACT_PACING_FIELDS).index("realized_impressions"),
                    key="sim_base_field",
                )
            with field_sim_col2:
                sim_reference_field = st.selectbox(
                    "Campo de referencia (limite)", options=list(FACT_PACING_FIELDS),
                    format_func=lambda f: FACT_PACING_FIELDS[f],
                    index=list(FACT_PACING_FIELDS).index("planned_impressions_daily"),
                    key="sim_reference_field",
                )
            with field_sim_col3:
                sim_threshold_pct = st.number_input(
                    "Teto (%)", min_value=1, max_value=100, value=20, step=1, key="sim_threshold",
                )
            sim_fields_ready = sim_base_field != sim_reference_field
            if not sim_fields_ready:
                st.warning("Campo a limitar e campo de referencia nao podem ser o mesmo.")

            if st.button("Rodar simulacao", key="sim_run", disabled=not (sim_strategies and sim_fields_ready)):
                with st.spinner("Calculando..."):
                    if sim_demo_mode:
                        pacing_df = mock_pacing_demo_data(tuple(sim_strategies))
                    else:
                        try:
                            sim_client_id = sim_client_label_map[sim_client_label]
                            pacing_df = load_pacing_for_simulation(sim_client_id, tuple(sim_strategies))
                        except Exception as exc:
                            st.error(
                                f"Erro ao consultar dado real: {exc}. Marque 'Modo "
                                "demonstracao' acima e rode de novo para usar dado de exemplo."
                            )
                            pacing_df = pd.DataFrame()

                if pacing_df.empty:
                    st.info("Sem dado de entrega para esse cliente/estrategia no periodo disponivel.")
                else:
                    base_label = FACT_PACING_FIELDS[sim_base_field]
                    reference_label = FACT_PACING_FIELDS[sim_reference_field]

                    has_reference = pacing_df[sim_reference_field].notna()
                    cap = pacing_df[sim_reference_field] * (1 + sim_threshold_pct / 100)
                    simulated = pacing_df[sim_base_field].where(
                        ~has_reference, pacing_df[sim_base_field].clip(upper=cap)
                    )
                    pacing_df["teto_calculado"] = cap
                    pacing_df["valor_simulado"] = simulated
                    pacing_df["diferenca"] = (
                        pacing_df[sim_base_field] - pacing_df["valor_simulado"]
                    ).clip(lower=0)

                    total_real = pacing_df[sim_base_field].sum()
                    total_sim = pacing_df["valor_simulado"].sum()
                    total_cortado = pacing_df["diferenca"].sum()
                    dias_sem_referencia = int((~has_reference).sum())
                    dias_afetados = int((pacing_df["diferenca"] > 0).sum())

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric(base_label, f"{total_real:,.0f}")
                    m2.metric(f"{base_label} com o teto ativo", f"{total_sim:,.0f}")
                    m3.metric(
                        "Reducao",
                        f"{total_cortado:,.0f}",
                        delta=f"-{(total_cortado / total_real * 100):.1f}%" if total_real else None,
                        delta_color="inverse",
                    )
                    m4.metric("Dias afetados", dias_afetados)
                    if dias_sem_referencia:
                        st.caption(
                            f":material/info: {dias_sem_referencia} dia(s) sem "
                            f"'{reference_label}' cadastrado -- nao entram no calculo do "
                            "teto (nao ha o que comparar)."
                        )

                    display_df = pacing_df.sort_values("diferenca", ascending=False)[
                        ["day", "formato", "platform", sim_reference_field, sim_base_field,
                         "teto_calculado", "valor_simulado", "diferenca"]
                    ].rename(columns={
                        "day": "Data",
                        "formato": "Formato",
                        "platform": "Plataforma",
                        sim_reference_field: reference_label,
                        sim_base_field: base_label,
                        "teto_calculado": "Teto",
                        "valor_simulado": f"{base_label} (com teto)",
                        "diferenca": "Diferenca",
                    })
                    st.dataframe(display_df, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────
# Aba 9 -- Gerenciamento de Clientes: CRUD real de core.dim_client + deteccao
# e reconciliacao manual de duplicatas. Ver bloco de constantes/funcoes
# (CLIENT_MGMT_*, detect_duplicate_candidates etc.) definido acima, junto de
# load_client_options().
# ─────────────────────────────────────────────────────────────────────────
with tab_clients:
    st.subheader("Gerenciamento de Clientes")
    st.caption(
        "CRUD real de `core.dim_client` -- status ativo/inativo (comercial, editavel aqui, NAO "
        "calculado por freshness), hierarquia guarda-chuva (`parent_client_id`), nome fantasia e "
        "toggle \"Importar IO Plan\", mais deteccao/reconciliacao manual de possiveis duplicatas. "
        "Freshness e plataformas com dado (abaixo) sao so contexto de apoio -- quem decide "
        "ativo/inativo e o Douglas, escrevendo aqui."
    )

    _cli_env_choice = st.radio("Ambiente", [e["label"] for e in ENVIRONMENTS], horizontal=True, key="clients_env")
    _cli_project = next(e["project_id"] for e in ENVIRONMENTS if e["label"] == _cli_env_choice)
    st.caption(f"Projeto GCP: `{_cli_project}`")
    if HUB_READ_ONLY:
        st.info(
            "Escrita (editar cliente, reconciliar duplicata) desabilitada neste deploy -- writer SA "
            "nao configurada (variavel WRITER_SA_EMAIL ausente). Use o Hub de staging, ou o de "
            "producao apos a writer SA ser provisionada, para essas acoes."
        )

    with st.spinner("Consultando core.dim_client + gold.fact_delivery..."):
        _cli_df = load_client_management_data(_cli_project)

    if _cli_df.empty:
        st.info(f"`{_cli_project}.core.dim_client` esta vazia ou nao encontrada.")
    else:
        _cli_supports_import_io_plan = check_dim_client_supports_import_io_plan(_cli_project)
        if not _cli_supports_import_io_plan:
            st.info(
                ":material/info: Este projeto (`" + _cli_project + "`) ainda nao tem a coluna "
                "`import_io_plan` em `core.dim_client` -- o seletor \"Importar IO Plan\" fica oculto "
                "ate a migracao rodar aqui (ver `core/migration/12_dim_client_add_import_io_plan.sql`). "
                "Confirmado ao vivo via schema, nao e um valor fixo."
            )

        _cli_by_id = {r.client_id: r for r in _cli_df.itertuples()}
        _cli_name_by_id = {r.client_id: r.name for r in _cli_df.itertuples()}

        m1, m2, m3 = st.columns(3)
        m1.metric("Clientes", len(_cli_df))
        m2.metric("Ativos", int((_cli_df["status"] == "active").sum()))
        m3.metric("Sem hierarquia definida", int(_cli_df["parent_client_id"].isna().sum()))

        st.divider()

        # ── Deteccao de duplicatas ──────────────────────────────────────────
        st.markdown("#### :material/content_copy: Possiveis duplicatas")
        st.caption(
            "Heuristica de nome parecido (e/ou mesmo `parent_client_id`) -- sinaliza, nunca decide "
            "sozinha. Um par so some desta lista apos decisao explicita abaixo (fica registrado em "
            "`core.dim_client_reconciliation`, nao volta a perguntar de novo)."
        )
        with st.spinner("Consultando core.dim_client_reconciliation..."):
            _cli_decisions_df = load_client_reconciliation_decisions(_cli_project)
        _cli_candidates_df = filter_undismissed_candidates(detect_duplicate_candidates(_cli_df), _cli_decisions_df)

        if _cli_candidates_df.empty:
            st.badge("nenhum candidato pendente", icon=":material/check_circle:", color="green")
        else:
            st.warning(f":material/warning: {len(_cli_candidates_df)} par(es) de possivel duplicata pendente(s) de revisao.")
            for _pair in _cli_candidates_df.itertuples():
                _pair_label = (
                    f"**{_pair.name_a}** ({_pair.client_id_a}) <-> **{_pair.name_b}** ({_pair.client_id_b}) "
                    f"-- similaridade {_pair.score:.0%}"
                )
                if _pair.same_parent:
                    _pair_label += " · mesmo guarda-chuva"
                with st.container(border=True):
                    st.markdown(_pair_label)
                    if HUB_READ_ONLY:
                        continue
                    _key_base = f"dup_{_pair.client_id_a}_{_pair.client_id_b}"
                    _survivor_options = {
                        f"{_pair.name_a} ({_pair.client_id_a})": (_pair.client_id_a, _pair.name_a),
                        f"{_pair.name_b} ({_pair.client_id_b})": (_pair.client_id_b, _pair.name_b),
                    }
                    _decided_by = st.text_input("Decidido por", value="douglas", key=f"{_key_base}_by")
                    dc1, dc2, dc3 = st.columns([2, 1.3, 1.3])
                    with dc1:
                        _survivor_choice = st.radio(
                            "Se forem o mesmo cliente, qual client_id e o correto (o outro sera desativado)?",
                            list(_survivor_options.keys()), key=f"{_key_base}_survivor",
                        )
                    with dc2:
                        st.write("")
                        st.write("")
                        if st.button("Confirmar: mesmo cliente", key=f"{_key_base}_same"):
                            _survivor_id, _survivor_name = _survivor_options[_survivor_choice]
                            _dup_id, _dup_name = (
                                (_pair.client_id_b, _pair.name_b) if _survivor_id == _pair.client_id_a
                                else (_pair.client_id_a, _pair.name_a)
                            )
                            _result = deactivate_duplicate_client(
                                _cli_project, _dup_id, _dup_name, _survivor_id, _survivor_name,
                                _decided_by.strip() or "douglas",
                            )
                            if _result["ok"]:
                                st.success(_result["detail"])
                                load_client_management_data.clear()
                                load_client_reconciliation_decisions.clear()
                                st.rerun()
                            else:
                                st.error(_result["detail"])
                    with dc3:
                        st.write("")
                        st.write("")
                        if st.button("Confirmar: clientes diferentes", key=f"{_key_base}_diff"):
                            _result = save_client_reconciliation_decision(
                                _cli_project, _pair.client_id_a, _pair.client_id_b, "different",
                                _decided_by.strip() or "douglas", "Confirmado como clientes diferentes via Hub.",
                            )
                            if _result["ok"]:
                                st.success(_result["detail"])
                                load_client_reconciliation_decisions.clear()
                                st.rerun()
                            else:
                                st.error(_result["detail"])

        if not _cli_decisions_df.empty:
            with st.expander(f"Ver decisoes ja registradas ({len(_cli_decisions_df)})"):
                st.dataframe(_cli_decisions_df, use_container_width=True, hide_index=True)

        st.divider()

        # ── Lista de clientes / edicao ───────────────────────────────────────
        st.markdown("#### :material/edit: Clientes")
        _cli_search = st.text_input(
            "Filtrar por nome ou client_id", key="clients_search", placeholder="ex: dr consulta",
        )
        _cli_missing_hierarchy_only = st.checkbox(
            "So sem hierarquia definida (parent_client_id nulo)", key="clients_missing_hierarchy_only",
        )

        _cli_filtered = _cli_df.copy()
        if _cli_search.strip():
            _needle = _cli_search.strip().lower()
            _cli_filtered = _cli_filtered[
                _cli_filtered["name"].str.lower().str.contains(_needle, na=False)
                | _cli_filtered["client_id"].str.lower().str.contains(_needle, na=False)
            ]
        if _cli_missing_hierarchy_only:
            _cli_filtered = _cli_filtered[_cli_filtered["parent_client_id"].isna()]

        st.caption(f"{len(_cli_filtered)} de {len(_cli_df)} cliente(s) exibido(s).")

        for _row in _cli_filtered.sort_values("name").itertuples():
            _last_delivery_str = (
                _row.last_delivery.strftime("%d/%m/%Y") if pd.notna(_row.last_delivery) else "sem dado em gold.fact_delivery"
            )
            _platforms_str = _row.platforms_with_data if pd.notna(_row.platforms_with_data) else "nenhuma"
            _status_label = CLIENT_STATUS_LABELS.get(_row.status, _row.status or "?")
            _title = f"**{_row.name}** ({_row.client_id}) -- {_status_label}"
            with st.expander(_title):
                st.caption(
                    f":material/info: Contexto de apoio (nao altera nada sozinho): ultima entrega em "
                    f"`gold.fact_delivery` = {_last_delivery_str} · plataformas com dado = {_platforms_str}"
                )
                if HUB_READ_ONLY:
                    st.dataframe(
                        pd.DataFrame([{
                            "status": _row.status, "parent_client_id": _row.parent_client_id,
                            "sector": _row.sector, "notes": _row.notes,
                        }]),
                        use_container_width=True, hide_index=True,
                    )
                    continue

                _key_base = f"client_{_row.client_id}"
                ec1, ec2 = st.columns(2)
                _new_name = ec1.text_input("Nome fantasia", value=_row.name, key=f"{_key_base}_name")
                _new_status = ec2.selectbox(
                    "Status", CLIENT_STATUS_OPTIONS,
                    index=CLIENT_STATUS_OPTIONS.index(_row.status) if _row.status in CLIENT_STATUS_OPTIONS else 0,
                    format_func=lambda s: CLIENT_STATUS_LABELS.get(s, s),
                    key=f"{_key_base}_status",
                )

                # Guarda-chuva -- exclui o proprio cliente da lista (nunca pode ser
                # pai de si mesmo). So grava parent_client_id/client_level quando a
                # ESCOLHA muda em relacao ao rotulo atual -- evita limpar sozinho um
                # parent_client_id "orfao" (aponta pra um client_id inexistente) so
                # porque o usuario abriu o expander e salvou sem mexer neste campo.
                _parent_label_to_id = {
                    f"{name} ({cid})": cid for cid, name in _cli_name_by_id.items() if cid != _row.client_id
                }
                _parent_choices = ["(nenhum -- cliente raiz)"] + sorted(_parent_label_to_id.keys())
                _current_parent_label = "(nenhum -- cliente raiz)"
                if pd.notna(_row.parent_client_id):
                    _current_parent_label = next(
                        (lbl for lbl, cid in _parent_label_to_id.items() if cid == _row.parent_client_id),
                        f"(client_id nao encontrado: {_row.parent_client_id})",
                    )
                    if _current_parent_label not in _parent_choices:
                        _parent_choices = _parent_choices + [_current_parent_label]
                _parent_choice = st.selectbox(
                    "Guarda-chuva (cliente pai)", _parent_choices,
                    index=_parent_choices.index(_current_parent_label), key=f"{_key_base}_parent",
                )

                _new_import_io_plan = None
                if _cli_supports_import_io_plan and hasattr(_row, "import_io_plan"):
                    _current_import_io_plan = bool(_row.import_io_plan) if pd.notna(_row.import_io_plan) else True
                    _new_import_io_plan = st.toggle(
                        "Importar IO Plan (sync_drive.py processa este cliente)",
                        value=_current_import_io_plan, key=f"{_key_base}_import_io_plan",
                    )

                _new_notes = st.text_area("Notas internas", value=_row.notes or "", key=f"{_key_base}_notes")

                if st.button("Salvar", key=f"{_key_base}_save"):
                    _updates = {}
                    if _new_name.strip() and _new_name.strip() != _row.name:
                        _updates["name"] = _new_name.strip()
                    if _new_status != _row.status:
                        _updates["status"] = _new_status
                    if _parent_choice != _current_parent_label:
                        _new_parent_id = (
                            None if _parent_choice == "(nenhum -- cliente raiz)"
                            else _parent_label_to_id[_parent_choice]
                        )
                        _updates["parent_client_id"] = _new_parent_id
                        _updates["client_level"] = 2 if _new_parent_id else 1
                    if _new_import_io_plan is not None:
                        _current_import_io_plan = bool(_row.import_io_plan) if pd.notna(_row.import_io_plan) else True
                        if _new_import_io_plan != _current_import_io_plan:
                            _updates["import_io_plan"] = _new_import_io_plan
                    if (_new_notes or "") != (_row.notes or ""):
                        _updates["notes"] = _new_notes or None

                    if not _updates:
                        st.info("Nenhuma mudanca para salvar.")
                    else:
                        _result = update_dim_client_fields(_cli_project, _row.client_id, _updates)
                        if _result["ok"]:
                            st.success(_result["detail"])
                            load_client_management_data.clear()
                            load_dim_client_options.clear()
                            load_client_options.clear()
                            st.rerun()
                        else:
                            st.error(_result["detail"])
