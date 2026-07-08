-- stg.mg_delivery
-- T4 STG MGID -- grain: 1 linha por (date, campaign_id, creative_id).
--
-- raw.mg_delivery JA TEM campaign_id nativo -- nao precisa do join com
-- mg_teasers pra resolver isso (esse join so e necessario no T5-T7, onde o
-- raw so tem creative_id). Corrigido aqui em relacao ao design original.
--
-- client_id/formato/goal_type: herdados via join com stg.mg_campaigns (ja
-- resolvidos no T1/T2 -- aqui e so denormalizacao de conveniencia, a pedido
-- do usuario 2026-06-24, nao reabre a resolucao).

CREATE OR REPLACE VIEW `adframework.stg.mg_delivery` AS
SELECT
  d.date,
  d.campaign_id,
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
FROM `adframework.raw.mg_delivery` d
LEFT JOIN `adframework.stg.mg_campaigns` c ON c.campaign_id = d.campaign_id;
