-- stg.ms_delivery_by_hour
-- T7 STG MediaSmart -- grain: 1 linha por (date, hour, campaign_id, creative_id).
-- Mesma logica de stg.ms_delivery + dimensao extra (hour) passthrough.

CREATE OR REPLACE VIEW `adframework.stg.ms_delivery_by_hour` AS
SELECT
  d.date,
  d.hour,
  d.client_id AS event_id,
  d.campaign_id,
  d.creative_id,
  c.client_id,
  c.formato,
  c.goal_type,
  d.impressions,
  d.clicks,
  d.conversions_1,
  d.conversions_2,
  d.conversions_3,
  d.conversions_4,
  d.conversions_5,
  SAFE_DIVIDE(d.clicks, d.impressions) AS ctr
FROM `adframework.raw.ms_delivery_by_hour` d
LEFT JOIN `adframework.stg.ms_campaigns` c ON c.campaign_id = d.campaign_id;
