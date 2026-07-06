-- stg.ms_delivery
-- T4 STG MediaSmart -- grain: 1 linha por (date, campaign_id, creative_id).
--
-- event_id: raw.ms_delivery.client_id na verdade e o Event ID da MS (nome
-- ambiguo escolhido na RAW, ver raw/ddl/ms_delivery.sql linha 24) -- renomeado
-- aqui pra nao confundir com o client_id real (core.dim_client).
--
-- client_id: COALESCE(campanha, advertiser) -- fallback duplo introduzido em
-- 2026-07-06 para corrigir 81.8% NULL causado por raw.ms_campaigns conter
-- apenas campanhas ativas (WRITE_TRUNCATE diario). raw.ms_delivery acumula
-- historico de 121 campanhas; raw.ms_campaigns so tem as 13 ativas hoje.
-- Solucao: se campaign_id nao esta em stg.ms_campaigns (campanha historica),
-- pega client_id via join direto com stg.ms_advertisers pelo event_id que JA
-- existe em raw.ms_delivery.client_id. Preserva formato/goal_type quando
-- a campanha esta no catalogo; fica NULL apenas para campanhas que sairao do
-- catalogo E cujo nome nao contem keyword de formato -- gap residual aceitavel.
--
-- formato/goal_type: herdados de stg.ms_campaigns quando disponivel, NULL
-- para campanhas historicas sem entry no catalogo. gold.fact_delivery agrupa
-- NULL formato separado (nao filtra) -- visivel como "formato desconhecido".
--
-- 6/938 (0,6%) creative_id nao batem com stg.ms_creatives -- gap aceitavel,
-- LEFT JOIN preserva a linha mesmo sem match.

CREATE OR REPLACE VIEW `adframework.stg.ms_delivery` AS
SELECT
  d.date,
  d.client_id AS event_id,
  d.campaign_id,
  d.creative_id,
  COALESCE(c.client_id, a.client_id) AS client_id,
  c.formato,
  c.goal_type,
  d.impressions,
  d.clicks,
  d.conversions_1,
  d.conversions_2,
  d.conversions_3,
  d.conversions_4,
  d.conversions_5,
  d.video_start,
  d.video_25,
  d.video_50,
  d.video_75,
  d.video_complete,
  SAFE_DIVIDE(d.clicks, d.impressions) AS ctr
FROM `adframework.raw.ms_delivery` d
LEFT JOIN `adframework.stg.ms_campaigns` c ON c.campaign_id = d.campaign_id
LEFT JOIN `adframework.stg.ms_advertisers` a ON a.event_id = d.client_id;
