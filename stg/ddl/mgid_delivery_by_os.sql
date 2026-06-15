-- stg.mgid_delivery_by_os (T11 MGID)
-- Entrega MGID segmentada por sistema operacional.
-- Grain: day + mgid_campaign_id + os
-- Fonte: raw.mgid_stats_by_os (Job E1) — 2025-10-01 → hoje
-- Dedup: ROW_NUMBER por raw_ingested_at DESC (backfill rodou 2x)
-- Depende de: core.platform_client_links
--
-- os: valor bruto da API ("Android mobile 14.02", "Mac OS desktop 10.15")
-- operating_system: família normalizada — alinhado com stg.ms_delivery_by_os
--   MS usa lowercase ("android"), MGID usa capitalizado ("Android") — normalizar no gold com LOWER()
-- Sem strategy_id, conversion_source, video quartis (exclusivos MediaSmart).
-- Financeiro incluído (mesmo padrão T9/T10).

CREATE OR REPLACE VIEW `adframework.stg.mgid_delivery_by_os` AS

WITH stats_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY day, campaignid, os ORDER BY raw_ingested_at DESC) AS rn
  FROM `adframework.raw.mgid_stats_by_os`
  WHERE day IS NOT NULL
    AND campaignid IS NOT NULL
    AND os IS NOT NULL
),

parsed AS (
  SELECT
    day,
    campaignid,
    os,
    CASE
      WHEN os LIKE 'Android%' THEN 'Android'
      WHEN os LIKE 'iOS%'     THEN 'iOS'
      WHEN os LIKE 'Mac OS%'  THEN 'macOS'
      WHEN os LIKE 'Windows%' THEN 'Windows'
      WHEN os LIKE 'Tizen%'   THEN 'Tizen'
      WHEN os LIKE 'Fire%'    THEN 'Fire OS'
      ELSE 'Other'
    END                                                             AS operating_system,
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
  p.os,
  p.operating_system,
  SAFE_CAST(p.impressions         AS INT64)                        AS impressions,
  SAFE_CAST(p.clicks              AS INT64)                        AS clicks,
  SAFE_CAST(p.conversionsinterest AS INT64)                        AS conversions_interest,
  SAFE_CAST(p.conversionsdecision AS INT64)                        AS conversions_decision,
  SAFE_CAST(p.conversionsbuy      AS INT64)                        AS conversions_buy,
  SAFE_CAST(JSON_VALUE(p.spent_json,   '$.amount') AS FLOAT64)    AS spent,
  SAFE_CAST(JSON_VALUE(p.revenue_json, '$.amount') AS FLOAT64)    AS revenue,
  SAFE_CAST(JSON_VALUE(p.profit_json,  '$.amount') AS FLOAT64)    AS profit,
  SAFE_CAST(p.roas AS FLOAT64)                                     AS roas,
  'stats_by_os'                                                    AS source_table
FROM parsed p
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = p.campaignid
WHERE p.rn = 1;
