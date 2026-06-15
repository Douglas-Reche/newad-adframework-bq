-- gold.fact_delivery
-- Fact principal de entrega. Grain: day + client_id + platform + platform_campaign_id.
-- Particionada por day, clusterizada por client_id + platform para queries de BI.
-- spend:         MediaSmart (stg.mediasmart_revenue) e MGID (raw.mgid_delivery.spent).
-- conversions_1..5: MediaSmart apenas — mapeamento por cliente em project_conversion_mapping.md.
-- mgid_conv_*:   MGID apenas — funnel interest → decision → buy.
-- client_id = 'unattributed' quando entrega não possui mapeamento confirmado.
--
-- CORRECAO (2026-06-03): revenue MediaSmart agora é joinado DEPOIS da agregacao
-- da delivery, evitando multiplicacao pelo numero de eventids por strategyid+day.

CREATE OR REPLACE TABLE `adframework.gold.fact_delivery`
PARTITION BY day
CLUSTER BY client_id, platform
OPTIONS (description = 'Fact de entrega unificada — grain: day + client + platform + campaign')
AS

-- ─── MEDIASMART ───────────────────────────────────────────────────────────────
-- Passo 1: agregar delivery ao grain final (day + client + strategy)
-- Passo 2: joinar revenue JA no grain agregado — sem multiplicacao
WITH ms_delivery AS (
  SELECT
    d.day,
    COALESCE(pcl.client_id, 'unattributed')  AS client_id,
    d.strategyid                              AS platform_campaign_id,
    SUM(d.impressions)                        AS impressions,
    SUM(d.clicks)                             AS clicks,
    SUM(d.conversions_1)                      AS conversions_1,
    SUM(d.conversions_2)                      AS conversions_2,
    SUM(d.conversions_3)                      AS conversions_3,
    SUM(d.conversions_4)                      AS conversions_4,
    SUM(d.conversions_5)                      AS conversions_5
  FROM `adframework.stg.mediasmart_delivery` d
  LEFT JOIN `adframework.core.platform_client_links` pcl
    ON  pcl.platform   = 'mediasmart'
    AND pcl.link_type  = 'eventid'
    AND pcl.link_value = d.eventid
  GROUP BY 1, 2, 3
),
ms_revenue AS (
  SELECT day, strategyid, SUM(clientrevenue) AS spend
  FROM `adframework.stg.mediasmart_revenue`
  GROUP BY 1, 2
)
SELECT
  d.day,
  d.client_id,
  'mediasmart'                               AS platform,
  d.platform_campaign_id,
  d.impressions,
  d.clicks,
  rev.spend,
  d.conversions_1,
  d.conversions_2,
  d.conversions_3,
  d.conversions_4,
  d.conversions_5,
  CAST(NULL AS INT64)                        AS mgid_conv_interest,
  CAST(NULL AS INT64)                        AS mgid_conv_decision,
  CAST(NULL AS INT64)                        AS mgid_conv_buy
FROM ms_delivery d
LEFT JOIN ms_revenue rev
  ON rev.day = d.day AND rev.strategyid = d.platform_campaign_id

UNION ALL

-- ─── MGID ─────────────────────────────────────────────────────────────────────
SELECT
  d.day,
  COALESCE(pcl.client_id, 'unattributed')  AS client_id,
  'mgid'                                    AS platform,
  d.campaignid                              AS platform_campaign_id,
  SUM(d.impressions)                        AS impressions,
  SUM(d.clicks)                             AS clicks,
  SUM(d.spent)                              AS spend,
  CAST(NULL AS INT64)                       AS conversions_1,
  CAST(NULL AS INT64)                       AS conversions_2,
  CAST(NULL AS INT64)                       AS conversions_3,
  CAST(NULL AS INT64)                       AS conversions_4,
  CAST(NULL AS INT64)                       AS conversions_5,
  SUM(d.conversionsinterest)                AS mgid_conv_interest,
  SUM(d.conversionsdecision)                AS mgid_conv_decision,
  SUM(d.conversionsbuy)                     AS mgid_conv_buy
FROM `adframework.stg.mgid_delivery` d
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = d.campaignid
GROUP BY 1, 2, 3, 4

UNION ALL

-- ─── SIPROCAL ─────────────────────────────────────────────────────────────────
SELECT
  d.day,
  COALESCE(pcl.client_id, 'unattributed')  AS client_id,
  'siprocal'                                AS platform,
  d.campaign_id                             AS platform_campaign_id,
  SUM(d.impressions)                        AS impressions,
  SUM(d.clicks)                             AS clicks,
  CAST(NULL AS FLOAT64)                     AS spend,
  CAST(NULL AS INT64)                       AS conversions_1,
  CAST(NULL AS INT64)                       AS conversions_2,
  CAST(NULL AS INT64)                       AS conversions_3,
  CAST(NULL AS INT64)                       AS conversions_4,
  CAST(NULL AS INT64)                       AS conversions_5,
  CAST(NULL AS INT64)                       AS mgid_conv_interest,
  CAST(NULL AS INT64)                       AS mgid_conv_decision,
  CAST(NULL AS INT64)                       AS mgid_conv_buy
FROM `adframework.stg.siprocal_delivery` d
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'siprocal'
  AND pcl.link_type  = 'advertiser'
  AND pcl.link_value = d.advertiser
GROUP BY 1, 2, 3, 4;
