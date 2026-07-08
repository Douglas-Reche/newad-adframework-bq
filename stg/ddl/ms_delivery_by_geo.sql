-- stg.ms_delivery_by_geo
-- T5 STG MediaSmart -- grain: 1 linha por (date, campaign_id, creative_id, country, city).
-- Mesma logica de stg.ms_delivery + dimensao extra (country, city) passthrough.

CREATE OR REPLACE VIEW `adframework.stg.ms_delivery_by_geo` AS
SELECT
  d.date,
  d.client_id AS event_id,
  d.campaign_id,
  d.creative_id,
  c.client_id,
  c.formato,
  c.goal_type,
  d.country,
  d.city,
  d.impressions,
  d.clicks,
  d.conversions_1,
  d.conversions_2,
  d.conversions_3,
  d.conversions_4,
  d.conversions_5,
  SAFE_DIVIDE(d.clicks, d.impressions) AS ctr
FROM `adframework.raw.ms_delivery_by_geo` d
LEFT JOIN `adframework.stg.ms_campaigns` c ON c.campaign_id = d.campaign_id;
