-- stg.siprocal_delivery (T1 Siprocal)
-- Fato de entrega Siprocal com siprocal_client_id resolvido.
-- Grain: day + advertiser_key + creative
--
-- Fonte: raw.siprocal_delivery (Google Sheet raw_daily via SiproCalConnector)
-- Atualização: diária WRITE_TRUNCATE (schedule 03:20 UTC)
--
-- Atribuição: raw.advertiser (NEWAD_LUCKBET_BR_SET25)
--   → regex extrai advertiser_key (LUCKBET)
--   → JOIN core.platform_client_links (platform='siprocal', link_type='advertiser')
--   → siprocal_client_id resolvido
--
-- Nota: pi_externo (campaign_id na raw) é referência comercial interna da Siprocal.
--   Não é único por cliente — não usar como chave de campanha.
--   campaign_name (NEWAD_{CLIENTE}_BR_{MES}{ANO}) é o identificador natural de campanha.

CREATE OR REPLACE VIEW `adframework.stg.siprocal_delivery` AS

WITH base AS (
  SELECT
    SAFE_CAST(day AS DATE)                                          AS day,
    advertiser                                                      AS campaign_name,
    COALESCE(
      REGEXP_EXTRACT(UPPER(TRIM(advertiser)), r'^NEWAD_(.+)_BR_\w+$'),
      UPPER(TRIM(advertiser))
    )                                                               AS advertiser_key,
    campaign_id                                                     AS pi_externo,
    creative,
    SAFE_CAST(impressions AS INT64)                                 AS impressions,
    SAFE_CAST(clicks      AS INT64)                                 AS clicks,
    platform,
    raw_ingested_at
  FROM `adframework.raw.siprocal_delivery`
  WHERE day IS NOT NULL
    AND day != ''
    AND advertiser IS NOT NULL
    AND advertiser != ''
)

SELECT
  b.day,
  pcl.client_id                                                     AS siprocal_client_id,
  b.campaign_name,
  b.advertiser_key,
  b.pi_externo,
  b.creative,
  b.impressions,
  b.clicks,
  SAFE_DIVIDE(b.clicks, b.impressions)                              AS ctr,
  b.platform,
  b.raw_ingested_at
FROM base b
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'siprocal'
  AND pcl.link_type  = 'advertiser'
  AND pcl.link_value = b.advertiser_key;
