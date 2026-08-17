"""Cloud Function (2a geracao, HTTP trigger via Cloud Scheduler) -- refresh
automatico diario de stg.fact_pacing_base em producao (adframework).

Por que isso NAO passa por scripts/deploy/apply_ddl.py: fact_pacing_base_refresh.sql
e um `CREATE OR REPLACE TABLE ... AS SELECT`, e apply_ddl.py exige confirmacao
humana interativa (input() ou --confirmed-via-chat) pra qualquer aplicacao
--env=prod, por desenho -- correto para MUDANCA DE SCHEMA/DEFINICAO, mas
inviabiliza um refresh de DADO recorrente e automatico (Cloud Scheduler nao
tem terminal humano nem sabe responder confirmacao). Este mecanismo e
deliberadamente separado: roda so o REFRESH (recalcula os dados da MESMA
definicao ja aprovada), nunca muda a definicao/schema da tabela -- se o
SCHEMA precisar mudar, isso continua exigindo apply_ddl.py com confirmacao
humana normal, nao este job.

SQL mantido em sincronia manual com stg/ddl/fact_pacing_base_refresh.sql
(fonte de verdade da definicao) -- se aquele arquivo mudar a logica de
negocio (novos campos, novo JOIN), atualizar aqui tambem. Mesma duplicacao
deliberada ja usada em hub/app.py::refresh_fact_pacing_base() (motivo
identico: nenhum dos dois ambientes tem o resto do repo disponivel em
runtime, so este arquivo/modulo).

Autorizado pelo Douglas em 2026-08-16 (task Notion MAE "Regras de Negocio
Configuraveis por Cliente", entrada "Registro do plano de promocao") --
"vamos construir isso no staging e testar" + confirmacao explicita de
promover pra producao junto com o resto do mecanismo de override.

Deploy (rodar do terminal, projeto adframework -- ver PRODUCTION_RUNBOOK.md
secao B pro passo a passo completo):
    gcloud functions deploy fact-pacing-base-refresh \
        --gen2 \
        --project=adframework \
        --region=southamerica-east1 \
        --runtime=python312 \
        --source=scripts/deploy/fact_pacing_base_scheduler \
        --entry-point=refresh_fact_pacing_base \
        --trigger-http \
        --no-allow-unauthenticated \
        --service-account=fact-pacing-base-refresh-sa@adframework.iam.gserviceaccount.com \
        --memory=256Mi \
        --timeout=300s
"""

import functions_framework
from google.cloud import bigquery

PROJECT_ID = "adframework"

REFRESH_SQL = f"""
CREATE OR REPLACE TABLE `{PROJECT_ID}.stg.fact_pacing_base` AS
WITH io_agg AS (
  SELECT
    client_id, report_date, formato, platform, goal_type,
    IF(COUNT(DISTINCT unit_price) = 1, ANY_VALUE(unit_price), NULL) AS unit_price,
    SUM(planned_spend_daily)       AS planned_spend_daily,
    SUM(planned_impressions_daily) AS planned_impressions_daily,
    SUM(planned_clicks_daily)      AS planned_clicks_daily
  FROM `{PROJECT_ID}.gold.fact_io_plan`
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
  FULL OUTER JOIN `{PROJECT_ID}.gold.fact_delivery` d
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
  `{PROJECT_ID}.core.resolve_reporting_source`(j.client_id, j.day, CURRENT_DATE()) = 'override' AS is_override
FROM joined j
LEFT JOIN `{PROJECT_ID}.stg.historical_overrides_delivery` ov
  ON ov.client_id = j.client_id AND ov.day = j.day
  AND UPPER(ov.formato) = UPPER(j.formato) AND UPPER(ov.platform) = UPPER(j.platform)
"""


@functions_framework.http
def refresh_fact_pacing_base(request):
    """Entry point HTTP -- chamado pelo Cloud Scheduler (OIDC) ou manualmente
    via `gcloud functions call` / curl autenticado. Sem parametros de request
    -- sempre roda o refresh completo, idempotente (CREATE OR REPLACE)."""
    client = bigquery.Client(project=PROJECT_ID)
    query_job = client.query(REFRESH_SQL)
    query_job.result()  # espera terminar, propaga erro se falhar (-> Cloud Scheduler marca como falha, alertavel)

    count_job = client.query(f"SELECT COUNT(*) AS n FROM `{PROJECT_ID}.stg.fact_pacing_base`")
    n_rows = list(count_job.result())[0]["n"]

    return {"status": "ok", "table": f"{PROJECT_ID}.stg.fact_pacing_base", "row_count": n_rows}, 200
