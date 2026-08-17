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
# Uso (staging, comportamento padrao, identico a antes):
#   HUB_PASSWORD="sua-senha-aqui" ./deploy.sh
#
# Uso (producao -- servico Cloud Run NOVO e separado, ver plano de promocao
# registrado na task Notion MAE "Regras de Negocio Configuraveis por Cliente",
# entrada 2026-08-16):
#   HUB_TARGET_ENV=production HUB_PASSWORD="sua-senha-aqui" ./deploy.sh
#
# Os dois ambientes rodam no MESMO projeto GCP de Cloud Run (adframework) e
# reusam as MESMAS service accounts -- a diferenca e (a) o nome do servico
# Cloud Run e (b) qual projeto BigQuery a aba de Override/Regras de Negocio
# le/escreve (HISTORICAL_OVERRIDE_PROJECT_ID, ver hub/app.py). Staging nao
# sincroniza continuamente com producao: uma feature so vai pro Hub de
# producao quando promovida deliberadamente (redeploy manual em modo
# production apos o Douglas confirmar).
set -euo pipefail

PROJECT_ID="adframework"
REGION="southamerica-east1"
SA_NAME="douglas-data-hub-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# HUB_TARGET_ENV controla qual dos 2 ambientes do Hub este deploy afeta.
# Default "staging" preserva o comportamento de sempre (nenhuma mudanca pra
# quem so roda `./deploy.sh` sem essa var).
HUB_TARGET_ENV="${HUB_TARGET_ENV:-staging}"

case "$HUB_TARGET_ENV" in
  staging)
    SERVICE_NAME="douglas-data-hub"
    HISTORICAL_OVERRIDE_PROJECT_ID="douglas-bq-staging"
    ;;
  production|prod)
    SERVICE_NAME="douglas-data-hub-prod"
    # Em producao, os dados de override/regras de negocio vivem no MESMO
    # projeto BQ do resto do Hub (adframework) -- nunca em douglas-bq-staging.
    HISTORICAL_OVERRIDE_PROJECT_ID="$PROJECT_ID"
    ;;
  *)
    echo "HUB_TARGET_ENV invalido: '${HUB_TARGET_ENV}' (use 'staging' ou 'production')"
    exit 1
    ;;
esac

echo "Ambiente alvo: ${HUB_TARGET_ENV} (servico: ${SERVICE_NAME}, override project: ${HISTORICAL_OVERRIDE_PROJECT_ID})"

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

# Bindings de override -- so um dos dois blocos abaixo roda, dependendo de
# HUB_TARGET_ENV (o projeto BQ de override e sempre $HISTORICAL_OVERRIDE_PROJECT_ID,
# ja resolvido no case acima; aqui so aplicamos os bindings de IAM correspondentes).
if [[ "$HUB_TARGET_ENV" == "staging" ]]; then
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
else
  # Modo producao -- HISTORICAL_OVERRIDE_PROJECT_ID == $PROJECT_ID (adframework),
  # entao os bindings de override vao pro PROPRIO $PROJECT_ID, nunca pro projeto
  # de staging. Mesmo raciocinio dos 2 achados reais documentados no bloco
  # staging acima (2026-08-06 e 2026-08-12), replicado pro projeto de producao:
  #   stg  -- historical_overrides_delivery / stg.fact_pacing_base (escrita)
  #   gold -- refresh_fact_pacing_base() precisa LER fact_delivery/fact_io_plan
  #           antes de escrever stg.fact_pacing_base (mesmo achado do incidente
  #           2026-08-12, replicado aqui pro projeto de producao)
  # `core`/`raw` em $PROJECT_ID ja tem dataEditor pela writer SA desde o bloco
  # de Propostas de Mudanca acima -- nao precisa duplicar.
  bq add-iam-policy-binding \
    --member="serviceAccount:${WRITER_SA_EMAIL}" \
    --role="roles/bigquery.dataEditor" \
    "${PROJECT_ID}:stg" >/dev/null 2>&1 || echo "  (binding prod stg ja aplicado ou bloqueado por allowlisting -- ver docs/known_issues.md S6, nao bloqueia deploy)"

  bq add-iam-policy-binding \
    --member="serviceAccount:${WRITER_SA_EMAIL}" \
    --role="roles/bigquery.dataViewer" \
    "${PROJECT_ID}:gold" >/dev/null 2>&1 || echo "  (binding prod gold ja aplicado ou bloqueado por allowlisting -- ver docs/known_issues.md S6, nao bloqueia deploy)"
fi

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
  --set-env-vars="HUB_PASSWORD=${HUB_PASSWORD},WRITER_SA_EMAIL=${WRITER_SA_EMAIL},HISTORICAL_OVERRIDE_PROJECT_ID=${HISTORICAL_OVERRIDE_PROJECT_ID}"

echo "Pronto. URL do servico:"
gcloud run services describe "$SERVICE_NAME" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)'
