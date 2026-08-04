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
#   core -- Overrides Historicos (Cora)
#   raw  -- Propostas de Mudanca (aprovacao de source='siprocal_diff' insere em raw.sp_delivery)
bq add-iam-policy-binding \
  --member="serviceAccount:${WRITER_SA_EMAIL}" \
  --role="roles/bigquery.dataEditor" \
  "${PROJECT_ID}:core" >/dev/null

bq add-iam-policy-binding \
  --member="serviceAccount:${WRITER_SA_EMAIL}" \
  --role="roles/bigquery.dataEditor" \
  "${PROJECT_ID}:raw" >/dev/null

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
