-- stg.siprocal_delivery
-- Typing, normalização e extração de advertiser sobre raw.siprocal_delivery.
-- Grain: day + campaign_name + campaign_id + creative
--
-- IMPORTANTE — formato da coluna `advertiser` na raw:
--   raw.siprocal_delivery.advertiser = nome completo da campanha (ex: NEWAD_AMIGOTECPAR_BR_ABR26).
--   Esta view extrai o advertiser key via REGEXP_EXTRACT('NEWAD_{ADVERTISER}_BR_{MES}{ANO}').
--   O campo `campaign_name` preserva o nome completo da campanha (rastreabilidade).
--   O JOIN com core.platform_client_links usa link_type='advertiser' e link_value = advertiser (ex: AMIGOTECPAR).
--
-- Fonte: raw.siprocal_delivery (Google Sheets raw_daily via ETL siprocal_daily_external)
-- Atualização: diária via ETL (Firestore: siprocal_daily_external)

CREATE OR REPLACE VIEW `adframework.stg.siprocal_delivery` AS
SELECT
  SAFE_CAST(day AS DATE)                                                   AS day,
  advertiser                                                               AS campaign_name,
  COALESCE(
    REGEXP_EXTRACT(UPPER(TRIM(advertiser)), r'^NEWAD_(.+)_BR_\w+$'),
    UPPER(TRIM(advertiser))
  )                                                                        AS advertiser,
  campaign_id,
  creative_type,
  creative,
  SAFE_CAST(impressions AS INT64)                                          AS impressions,
  SAFE_CAST(clicks      AS INT64)                                          AS clicks,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.siprocal_delivery`
WHERE day IS NOT NULL;
