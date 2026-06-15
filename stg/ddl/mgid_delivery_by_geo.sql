-- stg.mgid_delivery_by_geo (T10 MGID)
-- Entrega MGID segmentada por região geográfica.
-- Grain: day + mgid_campaign_id + region
-- Fonte: raw.mgid_stats_by_geo (Job D) — 2025-10-01 → hoje
-- Dedup: ROW_NUMBER por raw_ingested_at DESC (backfill rodou 2x)
-- Depende de: core.platform_client_links
--
-- region: texto bruto da API ("Belo Horizonte City", "Bahia", "Bahia Region Other cities")
-- geo_level: derivado do sufixo do texto — city / state / region_aggregate / other
-- Sem country_code: raw.mgid_geo_regions tem 0 linhas (job one-time nunca executado);
--   JOIN por nome de texto é frágil. Resolver na próxima fase se necessário.
-- Financeiro incluído (mesmo raciocínio do T9 — necessário para análise geo x spend).

CREATE OR REPLACE VIEW `adframework.stg.mgid_delivery_by_geo` AS

WITH stats_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY day, campaignid, region ORDER BY raw_ingested_at DESC) AS rn
  FROM `adframework.raw.mgid_stats_by_geo`
  WHERE day IS NOT NULL
    AND campaignid IS NOT NULL
    AND region IS NOT NULL
),

parsed AS (
  SELECT
    day,
    campaignid,
    region,
    CASE
      WHEN region LIKE '%City%'    THEN 'city'
      WHEN region LIKE '%Region%'  THEN 'region_aggregate'
      WHEN region = 'Other regions' THEN 'other'
      ELSE 'state'
    END                                                             AS geo_level,
    impressions,
    clicks,
    conversionsinterest,
    conversionsdecision,
    conversionsbuy,
    REPLACE(REPLACE(spent,   "'", '"'), 'None', 'null')            AS spent_json,
    REPLACE(REPLACE(revenue, "'", '"'), 'None', 'null')            AS revenue_json,
    REPLACE(REPLACE(profit,  "'", '"'), 'None', 'null')            AS profit_json,
    roas,
    rn
  FROM stats_deduped
)

SELECT
  SAFE_CAST(p.day AS DATE)                                          AS day,
  pcl.client_id                                                     AS mgid_client_id,
  p.campaignid                                                      AS mgid_campaign_id,
  p.region,
  p.geo_level,
  SAFE_CAST(p.impressions         AS INT64)                        AS impressions,
  SAFE_CAST(p.clicks              AS INT64)                        AS clicks,
  SAFE_CAST(p.conversionsinterest AS INT64)                        AS conversions_interest,
  SAFE_CAST(p.conversionsdecision AS INT64)                        AS conversions_decision,
  SAFE_CAST(p.conversionsbuy      AS INT64)                        AS conversions_buy,
  SAFE_CAST(JSON_VALUE(p.spent_json,   '$.amount') AS FLOAT64)    AS spent,
  SAFE_CAST(JSON_VALUE(p.revenue_json, '$.amount') AS FLOAT64)    AS revenue,
  SAFE_CAST(JSON_VALUE(p.profit_json,  '$.amount') AS FLOAT64)    AS profit,
  SAFE_CAST(p.roas AS FLOAT64)                                     AS roas,
  'stats_by_geo'                                                   AS source_table
FROM parsed p
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = p.campaignid
WHERE p.rn = 1;
