-- stg.mgid_creative_delivery (T4 MGID)
-- Fato de entrega MGID no nível de criativo com mgid_client_id resolvido.
-- Grain: day + mgid_campaign_id + mgid_creative_id
-- Fonte: raw.mgid_stats_creative (Job B) — 2025-10-01 → hoje
-- Dedup: ROW_NUMBER por raw_ingested_at DESC (backfill rodou 2x)
-- Depende de: core.platform_client_links
--
-- Sem ctr (calculado no gold), sem spent/cpc/revenue/profit/roas (vão para T8 stg.mgid_revenue).
-- Nomes de conversão preservados conforme API MGID (interest/decision/buy).
-- Equivalente ao T7 stg.ms_creative_delivery da MediaSmart.

CREATE OR REPLACE VIEW `adframework.stg.mgid_creative_delivery` AS

WITH stats_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY day, campaignid, teaserid ORDER BY raw_ingested_at DESC) AS rn
  FROM `adframework.raw.mgid_stats_creative`
  WHERE day IS NOT NULL
    AND campaignid IS NOT NULL
    AND teaserid IS NOT NULL
)

SELECT
  SAFE_CAST(s.day AS DATE)                       AS day,
  pcl.client_id                                  AS mgid_client_id,
  s.campaignid                                   AS mgid_campaign_id,
  s.teaserid                                     AS mgid_creative_id,
  SAFE_CAST(s.impressions          AS INT64)     AS impressions,
  SAFE_CAST(s.clicks               AS INT64)     AS clicks,
  SAFE_CAST(s.conversionsinterest  AS INT64)     AS conversions_interest,
  SAFE_CAST(s.conversionsdecision  AS INT64)     AS conversions_decision,
  SAFE_CAST(s.conversionsbuy       AS INT64)     AS conversions_buy,
  'stats_creative'                               AS source_table
FROM stats_deduped s
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = s.campaignid
WHERE s.rn = 1;
