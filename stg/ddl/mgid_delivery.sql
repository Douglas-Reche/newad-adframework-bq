-- stg.mgid_delivery
-- Typing e normalização sobre raw.mgid_delivery.
-- Grain: day + campaignid + teaserid

CREATE OR REPLACE VIEW `adframework.stg.mgid_delivery` AS
SELECT
  SAFE_CAST(day AS DATE)                        AS day,
  campaignid,
  teaserid,
  SAFE_CAST(impressions          AS INT64)      AS impressions,
  SAFE_CAST(clicks               AS INT64)      AS clicks,
  SAFE_CAST(conversionsinterest  AS INT64)      AS conversionsinterest,
  SAFE_CAST(conversionsdecision  AS INT64)      AS conversionsdecision,
  SAFE_CAST(conversionsbuy       AS INT64)      AS conversionsbuy,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.mgid_delivery`
WHERE day IS NOT NULL;
