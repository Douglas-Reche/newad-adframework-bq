-- gold.dim_campaign
-- Dimensão de campanhas unificada das 3 plataformas.
-- PK: (platform, platform_campaign_id) — IDs não são únicos entre plataformas.
-- campaign_name: nome da campanha da tabela de referência quando disponível.
-- client_id: FK para dim_client — permite RLS diretamente na dimensão.

CREATE OR REPLACE TABLE `adframework.gold.dim_campaign`
(
  platform               STRING NOT NULL,
  platform_campaign_id   STRING NOT NULL,
  platform_campaign_name STRING,
  platform_advertiser_id STRING,
  client_id              STRING
)
OPTIONS (description = 'Dimensao de campanhas unificada — mediasmart/mgid/siprocal');

INSERT INTO `adframework.gold.dim_campaign`
  (platform, platform_campaign_id, platform_campaign_name, platform_advertiser_id, client_id)

-- MediaSmart — grain: strategyid (campanha individual); strategyname é 1:1 com strategyid
SELECT DISTINCT
  'mediasmart'        AS platform,
  d.strategyid        AS platform_campaign_id,
  d.strategyname      AS platform_campaign_name,
  d.eventid           AS platform_advertiser_id,
  pcl.client_id
FROM `adframework.stg.mediasmart_delivery` d
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mediasmart'
  AND pcl.link_type  = 'eventid'
  AND pcl.link_value = d.eventid
WHERE d.strategyid IS NOT NULL

UNION ALL

-- MGID — campaign name da tabela de referência
SELECT DISTINCT
  'mgid'              AS platform,
  d.campaignid        AS platform_campaign_id,
  c.name              AS platform_campaign_name,
  CAST(NULL AS STRING) AS platform_advertiser_id,
  pcl.client_id
FROM `adframework.stg.mgid_delivery` d
LEFT JOIN `adframework.raw.mgid_campaigns` c ON c.id = d.campaignid
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = d.campaignid
WHERE d.campaignid IS NOT NULL

UNION ALL

-- Siprocal — sem tabela de campanhas; usa campaign_id + advertiser
SELECT DISTINCT
  'siprocal'                    AS platform,
  d.campaign_id                 AS platform_campaign_id,
  CAST(NULL AS STRING)          AS platform_campaign_name,
  d.advertiser                  AS platform_advertiser_id,
  pcl.client_id
FROM `adframework.stg.siprocal_delivery` d
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'siprocal'
  AND pcl.link_type  = 'advertiser'
  AND pcl.link_value = d.advertiser
WHERE d.campaign_id IS NOT NULL;
