-- stg.ms_delivery (T6)
-- Fato de entrega MediaSmart unificado com ms_client_id resolvido.
-- Grain: day + event_id + campaign_id + strategy_id + conversion_source
-- Fontes:
--   raw.mediasmart_delivery → histórico ago/2025–mai/24/2026 (job morto)
--   raw.mediasmart_daily    → ativo mai/25/2026–hoje (31 cols, nomes antigos)
--
-- Ambas as fontes usam colunas com nomes antigos (eventid, controlid, strategyid)
-- porque o aat-console do Shiro aplica mapeamento inverso antes de carregar.
-- O vínculo ms_client_id vem de JOIN com stg.ms_clients via eventid = ms_event_id.
--
-- SUBSTITUI: stg.mediasmart_delivery (legado, sem ms_client_id)
-- DROP stg.mediasmart_delivery SOMENTE após gold.fact_delivery migrar para esta view.
-- Depende de: stg.ms_clients (T1)

CREATE OR REPLACE VIEW `adframework.stg.ms_delivery` AS

WITH delivery_union AS (
  -- histórico: ago/2025 → mai/24/2026
  SELECT
    SAFE_CAST(day AS DATE)              AS day,
    eventid                             AS event_id,
    controlid                           AS campaign_id,
    strategyid                          AS strategy_id,
    strategyname                        AS strategy_name,
    conversion_source,
    SAFE_CAST(impressions      AS INT64) AS impressions,
    SAFE_CAST(clicks           AS INT64) AS clicks,
    SAFE_CAST(video_start      AS INT64) AS video_start,
    SAFE_CAST(video_25_viewed  AS INT64) AS video_25,
    SAFE_CAST(video_50_viewed  AS INT64) AS video_50,
    SAFE_CAST(video_75_viewed  AS INT64) AS video_75,
    SAFE_CAST(video_completion AS INT64) AS video_complete,
    SAFE_CAST(conversions_1    AS INT64) AS conversions_1,
    SAFE_CAST(conversions_2    AS INT64) AS conversions_2,
    SAFE_CAST(conversions_3    AS INT64) AS conversions_3,
    SAFE_CAST(conversions_4    AS INT64) AS conversions_4,
    SAFE_CAST(conversions_5    AS INT64) AS conversions_5,
    'delivery'                          AS source_table
  FROM `adframework.raw.mediasmart_delivery`
  WHERE day IS NOT NULL

  UNION ALL

  -- ativo: mai/25/2026 → hoje
  SELECT
    SAFE_CAST(day AS DATE)              AS day,
    eventid                             AS event_id,
    controlid                           AS campaign_id,
    strategyid                          AS strategy_id,
    strategyname                        AS strategy_name,
    conversion_source,
    SAFE_CAST(impressions      AS INT64) AS impressions,
    SAFE_CAST(clicks           AS INT64) AS clicks,
    SAFE_CAST(video_start      AS INT64) AS video_start,
    SAFE_CAST(video_25_viewed  AS INT64) AS video_25,
    SAFE_CAST(video_50_viewed  AS INT64) AS video_50,
    SAFE_CAST(video_75_viewed  AS INT64) AS video_75,
    SAFE_CAST(video_completion AS INT64) AS video_complete,
    SAFE_CAST(conversions_1    AS INT64) AS conversions_1,
    SAFE_CAST(conversions_2    AS INT64) AS conversions_2,
    SAFE_CAST(conversions_3    AS INT64) AS conversions_3,
    SAFE_CAST(conversions_4    AS INT64) AS conversions_4,
    SAFE_CAST(conversions_5    AS INT64) AS conversions_5,
    'daily'                             AS source_table
  FROM `adframework.raw.mediasmart_daily`
  WHERE day IS NOT NULL
    AND SAFE_CAST(day AS DATE) > DATE('2026-05-24')
)

SELECT
  d.day,
  cl.ms_client_id,
  d.campaign_id   AS ms_campaign_id,
  d.strategy_id   AS ms_strategy_id,
  d.strategy_name AS ms_strategy_name,
  d.conversion_source,
  d.impressions,
  d.clicks,
  d.video_start,
  d.video_25,
  d.video_50,
  d.video_75,
  d.video_complete,
  d.conversions_1,
  d.conversions_2,
  d.conversions_3,
  d.conversions_4,
  d.conversions_5,
  d.source_table
FROM delivery_union d
LEFT JOIN `adframework.stg.ms_clients` cl ON cl.ms_event_id = d.event_id;
