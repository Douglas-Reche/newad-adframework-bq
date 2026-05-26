-- stg.siprocal_delivery
-- Typing e normalização sobre raw.siprocal_delivery.
-- Grain: day + advertiser + campaign_id + creative_type + creative
-- NOTA: advertiser normalizado para UPPER+TRIM para consistência no join com platform_client_links.

CREATE OR REPLACE VIEW `adframework.stg.siprocal_delivery` AS
SELECT
  SAFE_CAST(day AS DATE)              AS day,
  UPPER(TRIM(advertiser))             AS advertiser,
  campaign_id,
  creative_type,
  creative,
  SAFE_CAST(impressions AS INT64)     AS impressions,
  SAFE_CAST(clicks      AS INT64)     AS clicks,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.siprocal_delivery`
WHERE day IS NOT NULL;
