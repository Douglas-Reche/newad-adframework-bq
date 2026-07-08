-- gold.fact_delivery
-- Fact de entrega unificada. Grain: day + client_id + platform + platform_campaign_id + category.
-- Particionada por day, clusterizada por client_id + platform.
--
-- v3 2026-06-16: adicionado campo category via JOIN gold.dim_campaign; spend removido.
--   Principio: spend vem do IO Plan (gold.fact_io_plan), nao da plataforma.
--   category: DISPLAY/VIDEO/RETARGETING para MS; NATIVE para MGID; PUSH para Siprocal.
--   video_completions: MS apenas (nulo nos demais).
--   conversions_1..5: MS apenas; mgid_conv_*: MGID apenas; Siprocal sem conversoes.
--
-- client_id: MS usa double-join (ms_clients + platform_client_links) para ID canonico.
--   stg.ms_delivery.ms_client_id = ID intermediario (nao casa com fact_io_plan.client_id).
--   pcl.client_id = ID canonico (casa com fact_io_plan.client_id).
--   MGID e Siprocal: client_id ja canonico no STG via platform_client_links.

CREATE OR REPLACE TABLE `adframework.gold.fact_delivery`
PARTITION BY day
CLUSTER BY client_id, platform
OPTIONS (description = 'Fact de entrega unificada v3 — grain: day + client + platform + campaign + category')
AS

-- ─── MEDIASMART ───────────────────────────────────────────────────────────────
-- Double-join obrigatorio: ms_delivery.ms_client_id (intermediario)
--   → ms_clients.ms_event_id → platform_client_links.client_id (canonico)
WITH ms_del AS (
  SELECT
    d.day,
    COALESCE(pcl.client_id, 'unattributed')  AS client_id,
    d.ms_strategy_id                          AS platform_campaign_id,
    SUM(d.impressions)    AS impressions,
    SUM(d.clicks)         AS clicks,
    SUM(d.video_complete) AS video_completions,
    SUM(d.conversions_1)  AS conversions_1,
    SUM(d.conversions_2)  AS conversions_2,
    SUM(d.conversions_3)  AS conversions_3,
    SUM(d.conversions_4)  AS conversions_4,
    SUM(d.conversions_5)  AS conversions_5
  FROM `adframework.stg.ms_delivery` d
  LEFT JOIN `adframework.stg.ms_clients` c
    ON c.ms_client_id = d.ms_client_id
  LEFT JOIN `adframework.core.platform_client_links` pcl
    ON  pcl.platform   = 'mediasmart'
    AND pcl.link_type  = 'eventid'
    AND pcl.link_value = c.ms_event_id
  GROUP BY 1, 2, 3
)
SELECT
  d.day,
  d.client_id,
  'mediasmart'          AS platform,
  d.platform_campaign_id,
  dc.category,
  d.impressions,
  d.clicks,
  d.video_completions,
  d.conversions_1,
  d.conversions_2,
  d.conversions_3,
  d.conversions_4,
  d.conversions_5,
  CAST(NULL AS INT64)   AS mgid_conv_interest,
  CAST(NULL AS INT64)   AS mgid_conv_decision,
  CAST(NULL AS INT64)   AS mgid_conv_buy
FROM ms_del d
LEFT JOIN `adframework.gold.dim_campaign` dc
  ON  dc.platform             = 'mediasmart'
  AND dc.platform_campaign_id = d.platform_campaign_id

UNION ALL

-- ─── MGID ─────────────────────────────────────────────────────────────────────
-- client_id: ja canonico em stg.mgid_delivery via platform_client_links
SELECT
  d.day,
  COALESCE(d.mgid_client_id, 'unattributed')  AS client_id,
  'mgid'                                        AS platform,
  d.mgid_campaign_id                            AS platform_campaign_id,
  dc.category,
  SUM(d.impressions)                            AS impressions,
  SUM(d.clicks)                                 AS clicks,
  CAST(NULL AS INT64)                           AS video_completions,
  CAST(NULL AS INT64)                           AS conversions_1,
  CAST(NULL AS INT64)                           AS conversions_2,
  CAST(NULL AS INT64)                           AS conversions_3,
  CAST(NULL AS INT64)                           AS conversions_4,
  CAST(NULL AS INT64)                           AS conversions_5,
  SUM(d.conversions_interest)                   AS mgid_conv_interest,
  SUM(d.conversions_decision)                   AS mgid_conv_decision,
  SUM(d.conversions_buy)                        AS mgid_conv_buy
FROM `adframework.stg.mgid_delivery` d
LEFT JOIN `adframework.gold.dim_campaign` dc
  ON  dc.platform             = 'mgid'
  AND dc.platform_campaign_id = d.mgid_campaign_id
GROUP BY d.day, COALESCE(d.mgid_client_id, 'unattributed'), d.mgid_campaign_id, dc.category

UNION ALL

-- ─── SIPROCAL ─────────────────────────────────────────────────────────────────
-- client_id: ja canonico em stg.siprocal_delivery via platform_client_links
-- sem video_completions, sem conversions (dados nao disponiveis na fonte)
SELECT
  d.day,
  COALESCE(d.siprocal_client_id, 'unattributed')  AS client_id,
  'siprocal'                                         AS platform,
  d.campaign_name                                    AS platform_campaign_id,
  dc.category,
  SUM(d.impressions)                                 AS impressions,
  SUM(d.clicks)                                      AS clicks,
  CAST(NULL AS INT64)                                AS video_completions,
  CAST(NULL AS INT64)                                AS conversions_1,
  CAST(NULL AS INT64)                                AS conversions_2,
  CAST(NULL AS INT64)                                AS conversions_3,
  CAST(NULL AS INT64)                                AS conversions_4,
  CAST(NULL AS INT64)                                AS conversions_5,
  CAST(NULL AS INT64)                                AS mgid_conv_interest,
  CAST(NULL AS INT64)                                AS mgid_conv_decision,
  CAST(NULL AS INT64)                                AS mgid_conv_buy
FROM `adframework.stg.siprocal_delivery` d
LEFT JOIN `adframework.gold.dim_campaign` dc
  ON  dc.platform             = 'siprocal'
  AND dc.platform_campaign_id = d.campaign_name
GROUP BY d.day, COALESCE(d.siprocal_client_id, 'unattributed'), d.campaign_name, dc.category;
