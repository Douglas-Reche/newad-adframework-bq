#!/usr/bin/env bash
# Deploy do AdFramework Data Hub -- servico Cloud Run PROPRIO do Douglas,
# separado dos 4 servicos do Shiro (aat-console, advanced-adtracking,
# adframework-admin-ui, adframework-etl). Nao mexe em nada deles.
#
# Nota: este script roda `gcloud run deploy --source` propositalmente.
# A regra "nunca deploy local com --source, sempre via Actions" e do
# repo do Shiro (rshiro-newad/adframework) -- nao se aplica aqui, esse
# hub nao tem CI proprio ainda (deploy manual e aceitavel pro uso pessoal).
#
# Uso:
#   HUB_PASSWORD="sua-senha-aqui" ./deploy.sh
set -euo pipefail

PROJECT_ID="adframework"
REGION="southamerica-east1"
SERVICE_NAME="douglas-data-hub"
SA_NAME="douglas-data-hub-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Writer SA -- usada pelas abas "Overrides Historicos (Cora)" e "Propostas de
# Mudanca", via impersonation (sem chave JSON). Escopo de escrita restrito
# DATASET A DATASET (`core`, `raw`), nunca projeto inteiro. A SA principal
# acima (SA_EMAIL) continua 100% read-only -- nao ganha nenhuma role de
# escrita; ela so recebe permissao de IMPERSONAR a writer SA.
WRITER_SA_NAME="douglas-data-hub-writer-sa"
WRITER_SA_EMAIL="${WRITER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if [[ -z "${HUB_PASSWORD:-}" ]]; then
  echo "Defina HUB_PASSWORD antes de rodar: HUB_PASSWORD='...' ./deploy.sh"
  exit 1
fi

# 1) Service account dedicada, so leitura de BQ (roda pela primeira vez apenas)
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" \
    --project "$PROJECT_ID" \
    --display-name="Douglas Data Hub (read-only BQ)"

  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/bigquery.dataViewer"

  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/bigquery.jobUser"

  # Necessario pra aba de Custos ler INFORMATION_SCHEMA.JOBS do projeto inteiro
  # (nao so os proprios jobs do hub) -- ainda assim so leitura de metadado, sem escrita.
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/bigquery.resourceViewer"
fi

# 1b) Writer SA dedicada -- dataEditor SO no dataset `core` (nunca projeto inteiro).
# Roda pela primeira vez apenas.
if ! gcloud iam service-accounts describe "$WRITER_SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$WRITER_SA_NAME" \
    --project "$PROJECT_ID" \
    --display-name="Douglas Data Hub Writer (dataEditor escopado a core)"
fi

# Bindings a nivel de DATASET (nao de projeto) -- so os datasets abaixo ganham
# permissao de escrita para essa SA. Idempotente: pode rodar de novo sem duplicar.
#   core -- Propostas de Mudanca (core.change_proposals)
#   raw  -- Propostas de Mudanca (aprovacao de source='siprocal_diff' insere em raw.sp_delivery)
# Nota: Overrides Historicos (Cora) e Config de Overrides por Cliente
# (stg.historical_overrides_delivery / core.client_reporting_source_config)
# NAO usam estes bindings -- vivem em douglas-bq-staging, ver bloco abaixo.
bq add-iam-policy-binding \
  --member="serviceAccount:${WRITER_SA_EMAIL}" \
  --role="roles/bigquery.dataEditor" \
  "${PROJECT_ID}:core" >/dev/null 2>&1 || echo "  (binding core ja aplicado ou bloqueado por allowlisting -- ver docs/known_issues.md S6, nao bloqueia deploy)"

bq add-iam-policy-binding \
  --member="serviceAccount:${WRITER_SA_EMAIL}" \
  --role="roles/bigquery.dataEditor" \
  "${PROJECT_ID}:raw" >/dev/null 2>&1 || echo "  (binding raw ja aplicado ou bloqueado por allowlisting -- ver docs/known_issues.md S6, nao bloqueia deploy)"

# Bindings em douglas-bq-staging (projeto SEPARADO de $PROJECT_ID) -- necessarios
# porque, a partir de 2026-08-06, douglas-bq-staging virou o ambiente completo
# onde roda TODO o fluxo de override historico antes de promover para producao:
#   raw  -- landing da planilha crua (historical_uploads/_meta, ver
#           stage_raw_historical_upload() em app.py)
#   stg  -- historical_overrides_delivery (dado normalizado, override em si)
#   core -- client_reporting_source_config (liga/desliga do override, SCD2)
# Confirmado NAO rodado ainda (verificado 2026-08-06 via python bigquery client:
# nenhum access_entry para writer-sa em nenhum dos 3 datasets, so o
# projectWriters padrao) -- o app trata a falta disso com erro de permissao
# claro em vez de estourar (ver stage_raw_historical_upload/commit_override/
# set_client_override_active em app.py), mas sem este binding as escritas
# reais falham. Rodar so apos confirmar com o Douglas (regra de IAM do hub).
STAGING_PROJECT_ID="douglas-bq-staging"

bq add-iam-policy-binding \
  --member="serviceAccount:${WRITER_SA_EMAIL}" \
  --role="roles/bigquery.dataEditor" \
  "${STAGING_PROJECT_ID}:raw" >/dev/null 2>&1 || echo "  (binding staging raw ja aplicado ou bloqueado por allowlisting -- ver docs/known_issues.md S6, nao bloqueia deploy)"

bq add-iam-policy-binding \
  --member="serviceAccount:${WRITER_SA_EMAIL}" \
  --role="roles/bigquery.dataEditor" \
  "${STAGING_PROJECT_ID}:stg" >/dev/null 2>&1 || echo "  (binding staging stg ja aplicado ou bloqueado por allowlisting -- ver docs/known_issues.md S6, nao bloqueia deploy)"

bq add-iam-policy-binding \
  --member="serviceAccount:${WRITER_SA_EMAIL}" \
  --role="roles/bigquery.dataEditor" \
  "${STAGING_PROJECT_ID}:core" >/dev/null 2>&1 || echo "  (binding staging core ja aplicado ou bloqueado por allowlisting -- ver docs/known_issues.md S6, nao bloqueia deploy)"

# A writer SA tambem precisa poder RODAR jobs de load/query contra as tabelas
# de staging acima. O hub agora fatura essas 3 escritas direto em
# douglas-bq-staging (get_staging_writer_bq_client() em app.py, 2026-08-06) --
# NAO em $PROJECT_ID/adframework -- entao o jobUser correspondente e escopado
# so ao projeto de staging (isolado, so o Douglas tem acesso la), nunca a
# producao. dataEditor no dataset staging sozinho nao basta sem isto.
gcloud projects add-iam-policy-binding "$STAGING_PROJECT_ID" \
  --member="serviceAccount:${WRITER_SA_EMAIL}" \
  --role="roles/bigquery.jobUser" >/dev/null

# SA PRINCIPAL (read-only) tambem precisa de leitura em douglas-bq-staging --
# achado real em producao (2026-08-06, primeiro teste ao vivo): a secao
# "Comparar Snapshot: Planilha vs. Dado Real" e as leituras de
# historical_uploads/_meta usam get_bq_client() (a SA principal), nao a writer
# SA, mas a SA principal so tinha permissao no projeto $PROJECT_ID/adframework
# -- 403 Access Denied real ao tentar ler douglas-bq-staging.raw.*. dataViewer
# (leitura) + jobUser (rodar a query, mesma logica do bloco da writer SA acima)
# escopados so ao projeto de staging, isolado, sem tocar producao.
gcloud projects add-iam-policy-binding "$STAGING_PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.dataViewer" >/dev/null

# Writer SA tambem precisa de LEITURA em douglas-bq-staging (nao so escrita) --
# achado real 2026-08-12: refresh_fact_pacing_base() em app.py (chamada pelo
# toggle de override_active) le gold.fact_delivery/gold.fact_io_plan via
# get_staging_writer_bq_client() antes de escrever stg.fact_pacing_base -- 403
# Access Denied sem isto. Binding a nivel de DATASET (bq add-iam-policy-binding
# "${STAGING_PROJECT_ID}:gold") bloqueado por allowlisting (mesmo padrao ja
# documentado em docs/known_issues.md S6) -- projeto inteiro via
# gcloud projects add-iam-policy-binding e o fallback que funciona (mesmo
# escopo ja usado para a SA principal acima).
gcloud projects add-iam-policy-binding "$STAGING_PROJECT_ID" \
  --member="serviceAccount:${WRITER_SA_EMAIL}" \
  --role="roles/bigquery.dataViewer" >/dev/null

gcloud projects add-iam-policy-binding "$STAGING_PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.jobUser" >/dev/null

# SA principal (read-only) ganha permissao de IMPERSONAR a writer SA -- nenhuma
# chave JSON e criada/baixada. So a aba de Overrides usa essa impersonation.
gcloud iam service-accounts add-iam-policy-binding "$WRITER_SA_EMAIL" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountTokenCreator" >/dev/null

# 2) Build + deploy
gcloud run deploy "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --source . \
  --service-account "$SA_EMAIL" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=1 \
  --memory=512Mi \
  --set-env-vars="HUB_PASSWORD=${HUB_PASSWORD},WRITER_SA_EMAIL=${WRITER_SA_EMAIL}"

echo "Pronto. URL do servico:"
gcloud run services describe "$SERVICE_NAME" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)'
