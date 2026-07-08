-- stg.mgid_delivery_by_browser (T11b MGID)
-- Entrega MGID segmentada por browser.
-- Grain: day + mgid_campaign_id + browser
-- Fonte: raw.mgid_stats_by_browser (Job E2) — 2025-10-01 → hoje
-- Dedup: ROW_NUMBER por raw_ingested_at DESC (backfill rodou 2x)
-- Depende de: core.platform_client_links
--
-- browser: 18 valores limpos da API ("Google Chrome", "Microsoft Edge", "Safari", etc.)
-- Sem normalização necessária (nomes já legíveis).
-- Sem equivalente na MediaSmart — não entra no gold unificado.
-- Consultado diretamente pelo Power BI/dashboard para análise browser-específica (Cenário B).
-- Financeiro incluído (mesmo padrão T9-T11).

CREATE OR REPLACE VIEW `adframework.stg.mgid_delivery_by_browser` AS

WITH stats_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY day, campaignid, browser ORDER BY raw_ingested_at DESC) AS rn
  FROM `adframework.raw.mgid_stats_by_browser`
  WHERE day IS NOT NULL
    AND campaignid IS NOT NULL
    AND browser IS NOT NULL
),

parsed AS (
  SELECT
    day,
    campaignid,
    browser,
    impressions,
    clicks,
    conversionsinterest,
    conversionsdecision,
    conversionsbuy,
    REPLACE(REPLACE(spent,   "'", '"'), 'None', 'null') AS spent_json,
    REPLACE(REPLACE(revenue, "'", '"'), 'None', 'null') AS revenue_json,
    REPLACE(REPLACE(profit,  "'", '"'), 'None', 'null') AS profit_json,
    roas,
    rn
  FROM stats_deduped
)

SELECT
  SAFE_CAST(p.day AS DATE)                                          AS day,
  pcl.client_id                                                     AS mgid_client_id,
  p.campaignid                                                      AS mgid_campaign_id,
  p.browser,
  SAFE_CAST(p.impressions         AS INT64)                        AS impressions,
  SAFE_CAST(p.clicks              AS INT64)                        AS clicks,
  SAFE_CAST(p.conversionsinterest AS INT64)                        AS conversions_interest,
  SAFE_CAST(p.conversionsdecision AS INT64)                        AS conversions_decision,
  SAFE_CAST(p.conversionsbuy      AS INT64)                        AS conversions_buy,
  SAFE_CAST(JSON_VALUE(p.spent_json,   '$.amount') AS FLOAT64)    AS spent,
  SAFE_CAST(JSON_VALUE(p.revenue_json, '$.amount') AS FLOAT64)    AS revenue,
  SAFE_CAST(JSON_VALUE(p.profit_json,  '$.amount') AS FLOAT64)    AS profit,
  SAFE_CAST(p.roas AS FLOAT64)                                     AS roas,
  'stats_by_browser'                                               AS source_table
FROM parsed p
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = p.campaignid
WHERE p.rn = 1;
