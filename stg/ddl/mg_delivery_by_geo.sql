-- stg.mg_delivery_by_geo
-- T5 STG MGID -- grain: 1 linha por (date, creative_id, region).
-- raw.mg_delivery_by_geo SO TEM creative_id (sem campaign_id) -- precisa do
-- join em cadeia via mg_teasers pra resolver campaign_id, diferente do T4
-- (que ja tem campaign_id nativo). Testado contra dado real 2026-06-24:
-- 800/800 (100%) resolvido.

CREATE OR REPLACE VIEW `adframework.stg.mg_delivery_by_geo` AS
SELECT
  d.date,
  t.campaign_id,
  d.creative_id,
  c.client_id,
  c.formato,
  c.goal_type,
  d.region,
  d.impressions,
  d.clicks,
  d.conversions_interest,
  d.conversions_decision,
  d.conversions_buy,
  SAFE_DIVIDE(d.clicks, d.impressions) AS ctr
FROM `adframework.raw.mg_delivery_by_geo` d
LEFT JOIN `adframework.stg.mg_teasers` t ON t.creative_id = d.creative_id
LEFT JOIN `adframework.stg.mg_campaigns` c ON c.campaign_id = t.campaign_id;
