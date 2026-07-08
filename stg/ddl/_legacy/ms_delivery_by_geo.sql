-- stg.ms_delivery_by_geo (T10)
-- Entrega MediaSmart segmentada por geografia (país + estado/região + cidade).
-- Grain: day + ms_client_id + ms_campaign_id + ms_strategy_id + country + area_name + city + conversion_source
-- Fonte: raw.mediasmart_delivery_by_geo (operacional desde 2026-06-11, backfill jan–jun/2026)
--   8.417.374 linhas | 2026-01-01 → hoje | cron 03:40 UTC
--   Tabela deduplicada em 2026-06-12 via SELECT DISTINCT após duplicação acidental no backfill.
--
-- Mapeamento de nomes (drilldown API → BQ após normalize_data):
--   countrycode           → country
--   georegion_areaname    → area_name
--   city                  → city
--
-- Schema novo (normalize_data puro): event_id, campaign_id, strategy_id.
-- Depende de: stg.ms_clients (T1)
-- NÃO substitui nenhuma view existente — view nova.

CREATE OR REPLACE VIEW `adframework.stg.ms_delivery_by_geo` AS
SELECT
  SAFE_CAST(d.day AS DATE)               AS day,
  cl.ms_client_id,
  d.campaign_id                          AS ms_campaign_id,
  d.strategy_id                          AS ms_strategy_id,
  d.country,
  d.area_name,
  d.city,
  d.conversion_source,
  SAFE_CAST(d.impressions      AS INT64) AS impressions,
  SAFE_CAST(d.clicks           AS INT64) AS clicks,
  SAFE_CAST(d.video_start      AS INT64) AS video_start,
  SAFE_CAST(d.video_25_viewed  AS INT64) AS video_25,
  SAFE_CAST(d.video_50_viewed  AS INT64) AS video_50,
  SAFE_CAST(d.video_75_viewed  AS INT64) AS video_75,
  SAFE_CAST(d.video_completion AS INT64) AS video_complete,
  SAFE_CAST(d.conversions_1    AS INT64) AS conversions_1,
  SAFE_CAST(d.conversions_2    AS INT64) AS conversions_2,
  SAFE_CAST(d.conversions_3    AS INT64) AS conversions_3,
  SAFE_CAST(d.conversions_4    AS INT64) AS conversions_4,
  SAFE_CAST(d.conversions_5    AS INT64) AS conversions_5,
  SAFE_CAST(d.final_price      AS FLOAT64) AS final_price,
  SAFE_CAST(d.media_cost__brl  AS FLOAT64) AS media_cost_brl
FROM `adframework.raw.mediasmart_delivery_by_geo` d
LEFT JOIN `adframework.stg.ms_clients` cl ON cl.ms_event_id = d.event_id
WHERE d.day IS NOT NULL;
