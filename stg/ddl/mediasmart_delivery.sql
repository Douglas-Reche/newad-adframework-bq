-- stg.mediasmart_delivery
-- Typing e normalização sobre raw.mediasmart_delivery.
-- Grain: day + eventid + controlid + strategyid + conversion_source

CREATE OR REPLACE VIEW `adframework.stg.mediasmart_delivery` AS
SELECT
  SAFE_CAST(day AS DATE)              AS day,
  eventid,
  controlid,
  strategyid,
  strategyname,
  conversion_source,
  SAFE_CAST(impressions       AS INT64) AS impressions,
  SAFE_CAST(clicks            AS INT64) AS clicks,
  SAFE_CAST(video_start       AS INT64) AS video_start,
  SAFE_CAST(video_25_viewed   AS INT64) AS video_25_viewed,
  SAFE_CAST(video_50_viewed   AS INT64) AS video_50_viewed,
  SAFE_CAST(video_75_viewed   AS INT64) AS video_75_viewed,
  SAFE_CAST(video_completion  AS INT64) AS video_completion,
  SAFE_CAST(conversions_1     AS INT64) AS conversions_1,
  SAFE_CAST(conversions_2     AS INT64) AS conversions_2,
  SAFE_CAST(conversions_3     AS INT64) AS conversions_3,
  SAFE_CAST(conversions_4     AS INT64) AS conversions_4,
  SAFE_CAST(conversions_5     AS INT64) AS conversions_5,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.mediasmart_delivery`
WHERE day IS NOT NULL;
