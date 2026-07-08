-- stg.mg_delivery_by_hour
-- T7 STG MGID -- grain: 1 linha por (date, hour, creative_id).
-- Mesma cadeia de joins de stg.mg_delivery_by_geo. Testado: 1346/1346 (100%).

CREATE OR REPLACE VIEW `adframework.stg.mg_delivery_by_hour` AS
SELECT
  d.date,
  d.hour,
  t.campaign_id,
  d.creative_id,
  c.client_id,
  c.formato,
  c.goal_type,
  d.impressions,
  d.clicks,
  d.conversions_interest,
  d.conversions_decision,
  d.conversions_buy,
  SAFE_DIVIDE(d.clicks, d.impressions) AS ctr
FROM `adframework.raw.mg_delivery_by_hour` d
LEFT JOIN `adframework.stg.mg_teasers` t ON t.creative_id = d.creative_id
LEFT JOIN `adframework.stg.mg_campaigns` c ON c.campaign_id = t.campaign_id;
