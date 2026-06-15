-- stg.mgid_revenue (T8 MGID)
-- Métricas financeiras MGID por campanha com mgid_client_id resolvido.
-- Grain: day + mgid_campaign_id
-- Fonte: raw.mgid_stats_daily (Job A) — 2025-10-01 → hoje
-- Dedup: ROW_NUMBER por raw_ingested_at DESC (backfill rodou 2x)
-- Depende de: core.platform_client_links
--
-- spent/cpc/revenue/profit chegam como Python dict: {'amount': '190.2', 'currency': 'BRL'}
-- Parser: REPLACE("'", '"') + REPLACE('None', 'null') → JSON_VALUE($.amount)
-- roas chega como inteiro direto (STRING '0') — não é dict.
-- revenue e profit são 0 para clientes sem pixel com valor configurado (esperado).

CREATE OR REPLACE VIEW `adframework.stg.mgid_revenue` AS

WITH stats_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY day, campaignid ORDER BY raw_ingested_at DESC) AS rn
  FROM `adframework.raw.mgid_stats_daily`
  WHERE day IS NOT NULL
    AND campaignid IS NOT NULL
),

parsed AS (
  SELECT
    day,
    campaignid,
    REPLACE(REPLACE(spent,   "'", '"'), 'None', 'null') AS spent_json,
    REPLACE(REPLACE(cpc,     "'", '"'), 'None', 'null') AS cpc_json,
    REPLACE(REPLACE(revenue, "'", '"'), 'None', 'null') AS revenue_json,
    REPLACE(REPLACE(profit,  "'", '"'), 'None', 'null') AS profit_json,
    roas,
    raw_ingested_at,
    rn
  FROM stats_deduped
)

SELECT
  SAFE_CAST(p.day AS DATE)                              AS day,
  pcl.client_id                                         AS mgid_client_id,
  p.campaignid                                          AS mgid_campaign_id,
  SAFE_CAST(JSON_VALUE(p.spent_json,   '$.amount') AS FLOAT64) AS spent,
  SAFE_CAST(JSON_VALUE(p.cpc_json,     '$.amount') AS FLOAT64) AS cpc,
  SAFE_CAST(JSON_VALUE(p.revenue_json, '$.amount') AS FLOAT64) AS revenue,
  SAFE_CAST(JSON_VALUE(p.profit_json,  '$.amount') AS FLOAT64) AS profit,
  SAFE_CAST(p.roas AS FLOAT64)                          AS roas,
  JSON_VALUE(p.spent_json, '$.currency')                AS currency,
  'stats_daily'                                         AS source_table
FROM parsed p
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = p.campaignid
WHERE p.rn = 1;
