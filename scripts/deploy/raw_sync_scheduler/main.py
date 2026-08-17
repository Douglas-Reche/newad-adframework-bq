"""Cloud Function (2a geracao, HTTP trigger via Cloud Scheduler) -- sync diario
de `raw` de producao (adframework) para staging (douglas-bq-staging).

Por que isso existe
--------------------
Staging (douglas-bq-staging) tem `raw` fisicamente replicado desde 2026-08-06
(ver core/ddl/schema_change_log.sql e o header de scripts/deploy/apply_ddl.py,
ALT_PROJECT_MIRRORED_DATASETS) -- mas o sync diario planejado nessa data NUNCA
foi implementado de fato, so desenhado. Achado em 2026-08-17: a API do Cloud
Scheduler nunca tinha sido habilitada em `douglas-bq-staging`, deixando o raw
de staging 11+ dias atrasado em relacao a producao sem que ninguem percebesse
(nao ha alerta de staleness). Esta function fecha esse gap.

O que faz: `bq cp -f` (BigQuery table copy job, so metadado + dado fisico via
job nativo do BQ -- nao um scan/leitura linha a linha) de cada uma das 18
tabelas de `adframework.raw.*` para `douglas-bq-staging.raw.*`. Roda como job
CROSS-PROJECT (source_project != destination_project), exige que a service
account tenha `bigquery.dataViewer`+`bigquery.jobUser` em `adframework` E
`bigquery.dataEditor`+`bigquery.jobUser` em `douglas-bq-staging`.

Tabelas deliberadamente EXCLUIDAS da lista (existem em staging mas NAO em
producao -- sao dado subido manualmente via Hub, nunca vieram de sync):
`historical_uploads`, `historical_uploads_meta`. Syncar essas sobrescreveria/
apagaria override de cliente carregado direto em staging (ex: Cora).

TABLES abaixo e a fonte de verdade real (confirmada via `bq ls` ao vivo em
2026-08-17) -- diverge da contagem aproximada "mg_* (7), ms_* (7)" registrada
no CHANGELOG.md/task Notion daquele dia (a contagem real e mg_*=6, ms_*=8;
total de 18 bate, mas a composicao exata so foi confirmada agora).

Deploy (rodar do terminal, projeto douglas-bq-staging):
    gcloud functions deploy raw-sync-staging \
        --gen2 \
        --project=douglas-bq-staging \
        --region=southamerica-east1 \
        --runtime=python312 \
        --source=scripts/deploy/raw_sync_scheduler \
        --entry-point=sync_raw_staging \
        --trigger-http \
        --no-allow-unauthenticated \
        --service-account=raw-sync-staging-sa@douglas-bq-staging.iam.gserviceaccount.com \
        --memory=256Mi \
        --timeout=300s
"""

import functions_framework
from google.cloud import bigquery
from google.cloud.bigquery.job import CopyJobConfig, WriteDisposition

SOURCE_PROJECT = "adframework"
DEST_PROJECT = "douglas-bq-staging"
DATASET = "raw"

TABLES = [
    "io_plan_drive_snapshot",
    "mg_campaigns",
    "mg_delivery",
    "mg_delivery_by_device",
    "mg_delivery_by_geo",
    "mg_delivery_by_hour",
    "mg_teasers",
    "mgid_stats_creative",
    "mgid_stats_daily",
    "ms_advertisers",
    "ms_campaigns",
    "ms_creative_daily",
    "ms_creatives",
    "ms_delivery",
    "ms_delivery_by_device",
    "ms_delivery_by_geo",
    "ms_delivery_by_hour",
    "sp_delivery",
]


@functions_framework.http
def sync_raw_staging(request):
    """Entry point HTTP -- chamado pelo Cloud Scheduler (OIDC) ou manualmente
    via `gcloud functions call` / curl autenticado. Copia as 18 tabelas de
    `raw`, uma por uma, sobrescrevendo o destino (WRITE_TRUNCATE, mesmo
    comportamento de `bq cp -f`). Falha rapido e retorna erro por tabela --
    nao tenta ser transacional entre tabelas (cada `bq cp` ja e atomico por
    tabela individualmente, que e a mesma garantia que o fluxo manual tinha)."""
    client = bigquery.Client(project=DEST_PROJECT)
    results = []
    for table in TABLES:
        source_ref = f"{SOURCE_PROJECT}.{DATASET}.{table}"
        dest_ref = f"{DEST_PROJECT}.{DATASET}.{table}"
        try:
            job = client.copy_table(
                source_ref,
                dest_ref,
                job_config=CopyJobConfig(write_disposition=WriteDisposition.WRITE_TRUNCATE),
            )
            job.result()  # espera terminar, propaga erro se falhar
            results.append({"table": table, "status": "ok"})
        except Exception as e:
            results.append({"table": table, "status": "error", "error": str(e)})

    failed = [r for r in results if r["status"] == "error"]
    status_code = 500 if failed else 200
    return {
        "status": "error" if failed else "ok",
        "synced": len(results) - len(failed),
        "failed": len(failed),
        "details": results,
    }, status_code
