-- stg.ms_delivery_by_publisher (T13)
-- Entrega MediaSmart segmentada por publisher (empresa + URL + exchange).
-- Grain: day + ms_client_id + ms_campaign_id + ms_strategy_id + publisher_company + publisher_url + ad_exchange + conversion_source
-- Fonte: raw.mediasmart_delivery_by_publisher (operacional desde 2026-06-11, backfill jan–jun/2026)
--   9.804.184 linhas | 2026-01-01 → hoje | cron 03:45 UTC
--   2ª maior tabela RAW do pipeline (após delivery_by_geo).
--
-- Nota: sem KPIs de vídeo — este drilldown retorna apenas impressions + clicks
-- (video não foi solicitado no job; publisher analysis raramente precisa de vídeo).
--
-- Schema novo (normalize_data puro): event_id, campaign_id, strategy_id.
-- Depende de: stg.ms_clients (T1)
-- NÃO substitui nenhuma view existente — view nova.

CREATE OR REPLACE VIEW `adframework.stg.ms_delivery_by_publisher` AS
SELECT
  SAFE_CAST(d.day AS DATE)                 AS day,
  cl.ms_client_id,
  d.campaign_id                            AS ms_campaign_id,
  d.strategy_id                            AS ms_strategy_id,
  d.publisher_company,
  d.publisher_url,
  d.ad_exchange,
  d.conversion_source,
  SAFE_CAST(d.impressions  AS INT64)       AS impressions,
  SAFE_CAST(d.clicks       AS INT64)       AS clicks,
  SAFE_CAST(d.final_price  AS FLOAT64)     AS final_price,
  SAFE_CAST(d.media_cost__brl AS FLOAT64)  AS media_cost_brl
FROM `adframework.raw.mediasmart_delivery_by_publisher` d
LEFT JOIN `adframework.stg.ms_clients` cl ON cl.ms_event_id = d.event_id
WHERE d.day IS NOT NULL;
