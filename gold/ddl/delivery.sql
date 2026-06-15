-- gold.delivery
-- Fact unificada de entrega das 3 plataformas com client_id canônico.
-- Grain: day + platform + platform_campaign_id + granularidade original da STG
-- client_id NULL = entrega não atribuída (eventid/campaignid sem mapeamento confirmado)
-- Conversões não unificadas aqui — definição varia por plataforma e por cliente.

CREATE OR REPLACE VIEW `adframework.gold.delivery` AS

-- ─── MEDIASMART ───────────────────────────────────────────────────────────────
SELECT
  d.day,
  pcl.client_id,
  dc.name                AS client_name,
  'mediasmart'           AS platform,
  d.eventid              AS platform_advertiser_id,
  d.controlid            AS platform_campaign_id,
  d.strategyname         AS platform_campaign_name,
  d.impressions,
  d.clicks,
  d.report_name,
  d.raw_ingested_at
FROM `adframework.stg.mediasmart_delivery` d
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mediasmart'
  AND pcl.link_type  = 'eventid'
  AND pcl.link_value = d.eventid
LEFT JOIN `adframework.core.dim_client` dc
  ON dc.client_id = pcl.client_id

UNION ALL

-- ─── MGID ─────────────────────────────────────────────────────────────────────
SELECT
  d.day,
  pcl.client_id,
  dc.name                AS client_name,
  'mgid'                 AS platform,
  NULL                   AS platform_advertiser_id,
  d.campaignid           AS platform_campaign_id,
  c.name                 AS platform_campaign_name,
  d.impressions,
  d.clicks,
  d.report_name,
  d.raw_ingested_at
FROM `adframework.stg.mgid_delivery` d
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = d.campaignid
LEFT JOIN `adframework.core.dim_client` dc
  ON dc.client_id = pcl.client_id
LEFT JOIN `adframework.raw.mgid_campaigns` c
  ON c.id = d.campaignid

UNION ALL

-- ─── SIPROCAL ─────────────────────────────────────────────────────────────────
SELECT
  d.day,
  pcl.client_id,
  dc.name                AS client_name,
  'siprocal'             AS platform,
  d.advertiser           AS platform_advertiser_id,
  d.campaign_id          AS platform_campaign_id,
  NULL                   AS platform_campaign_name,
  d.impressions,
  d.clicks,
  d.report_name,
  d.raw_ingested_at
FROM `adframework.stg.siprocal_delivery` d
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'siprocal'
  AND pcl.link_type  = 'advertiser'
  AND pcl.link_value = d.advertiser
LEFT JOIN `adframework.core.dim_client` dc
  ON dc.client_id = pcl.client_id;
