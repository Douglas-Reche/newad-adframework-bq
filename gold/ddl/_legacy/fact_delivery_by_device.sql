-- gold.fact_delivery_by_device
-- Entrega segmentada por dispositivo. Grain: day + client_id + platform + platform_campaign_id + category + device_type + app_vs_web
-- Particionada por day, clusterizada por client_id.
--
-- Fontes por plataforma:
--   MediaSmart: stg.ms_delivery_by_device (T9) — backfill jan-jun/2026
--   MGID: nao disponivel (T13 e por widget, nao por device — sem mapeamento de device_type)
--   Siprocal: nao disponivel (fonte nao reporta breakdown por device)
--
-- client_id: double-join obrigatorio igual a fact_delivery
--   ms_delivery_by_device.ms_client_id (intermediario) → ms_clients → platform_client_links (canonico)
--
-- category: via JOIN gold.dim_campaign ON (platform, ms_strategy_id)

CREATE OR REPLACE TABLE `adframework.gold.fact_delivery_by_device`
PARTITION BY day
CLUSTER BY client_id
OPTIONS (description = 'Entrega por dispositivo — MediaSmart apenas; grain: day+client+campaign+category+device+app_vs_web')
AS

WITH ms_dev AS (
  SELECT
    d.day,
    COALESCE(pcl.client_id, 'unattributed')  AS client_id,
    d.ms_strategy_id                          AS platform_campaign_id,
    d.device_type,
    d.app_vs_web,
    SUM(d.impressions)    AS impressions,
    SUM(d.clicks)         AS clicks,
    SUM(d.video_complete) AS video_completions
  FROM `adframework.stg.ms_delivery_by_device` d
  LEFT JOIN `adframework.stg.ms_clients` c
    ON c.ms_client_id = d.ms_client_id
  LEFT JOIN `adframework.core.platform_client_links` pcl
    ON  pcl.platform   = 'mediasmart'
    AND pcl.link_type  = 'eventid'
    AND pcl.link_value = c.ms_event_id
  GROUP BY 1, 2, 3, 4, 5
)

SELECT
  d.day,
  d.client_id,
  'mediasmart'            AS platform,
  d.platform_campaign_id,
  dc.category,
  d.device_type,
  d.app_vs_web,
  d.impressions,
  d.clicks,
  d.video_completions
FROM ms_dev d
LEFT JOIN `adframework.gold.dim_campaign` dc
  ON  dc.platform             = 'mediasmart'
  AND dc.platform_campaign_id = d.platform_campaign_id;
