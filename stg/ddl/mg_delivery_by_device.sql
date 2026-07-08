-- stg.mg_delivery_by_device
-- T6 STG MGID -- grain: 1 linha por (date, creative_id, device_type).
-- Mesma cadeia de joins de stg.mg_delivery_by_geo. Testado: 251/251 (100%).
-- Sem operating_system (nao existe nesse grain na raw).

CREATE OR REPLACE VIEW `adframework.stg.mg_delivery_by_device` AS
SELECT
  d.date,
  t.campaign_id,
  d.creative_id,
  c.client_id,
  c.formato,
  c.goal_type,
  d.device_type,
  d.impressions,
  d.clicks,
  d.conversions_interest,
  d.conversions_decision,
  d.conversions_buy,
  SAFE_DIVIDE(d.clicks, d.impressions) AS ctr
FROM `adframework.raw.mg_delivery_by_device` d
LEFT JOIN `adframework.stg.mg_teasers` t ON t.creative_id = d.creative_id
LEFT JOIN `adframework.stg.mg_campaigns` c ON c.campaign_id = t.campaign_id;
