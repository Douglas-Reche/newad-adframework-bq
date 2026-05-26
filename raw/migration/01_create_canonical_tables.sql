-- =============================================================================
-- RAW LAYER — MIGRAÇÃO: Passo 1 — Criar tabelas canônicas com dados existentes
-- =============================================================================
-- Execução: uma vez, coordenada com o Shiro antes de atualizar o orchestrator.
-- Cada bloco cria a nova tabela canônica copiando dados da tabela atual.
-- Após validação de row counts, executar 02_drop_legacy_and_orphans.sql.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. mediasmart_delivery  (substitui mediasmart_daily)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `adframework.raw.mediasmart_delivery`
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Entrega diária MediaSmart. Grain: day+eventid+controlid+strategyid+conversion_source.')
AS
SELECT
  day,
  eventid,
  controlid,
  strategyid,
  strategyname,
  conversion_source,
  impressions,
  clicks,
  video_start,
  video_25_viewed,
  video_50_viewed,
  video_75_viewed,
  video_completion,
  conversions_1,
  conversions_2,
  conversions_3,
  conversions_4,
  conversions_5,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.mediasmart_daily`;

-- Validação: deve retornar 0 diferença
-- SELECT
--   (SELECT COUNT(*) FROM `adframework.raw.mediasmart_delivery`) AS novo,
--   (SELECT COUNT(*) FROM `adframework.raw.mediasmart_daily`)    AS antigo;


-- -----------------------------------------------------------------------------
-- 2. mediasmart_revenue  (substitui mediasmart_revenue_daily)
-- Normaliza nomes duplicados de colunas para a forma canônica.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `adframework.raw.mediasmart_revenue`
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Receita diária MediaSmart. Grain: day+controlid+strategyid+revenuesource.')
AS
SELECT
  day,
  COALESCE(NULLIF(controlid, ''), NULLIF(campaign_id, ''), NULLIF(campaignid, '')) AS controlid,
  COALESCE(NULLIF(strategyid, ''), NULLIF(strategy_id, ''))                         AS strategyid,
  COALESCE(NULLIF(revenuesource, ''), NULLIF(revenue_source, ''),
           NULLIF(conversion_source, ''), NULLIF(convsource, ''))                   AS revenuesource,
  COALESCE(NULLIF(clientrevenue, ''), NULLIF(client_revenue, ''),
           NULLIF(event_revenue, ''))                                               AS clientrevenue,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.mediasmart_revenue_daily`;


-- -----------------------------------------------------------------------------
-- 3. mediasmart_bid_supply  (substitui mediasmart_bid_supply_daily)
-- Normaliza nomes duplicados de colunas para a forma canônica.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `adframework.raw.mediasmart_bid_supply`
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Supply e leilão horário MediaSmart.')
AS
SELECT
  day,
  COALESCE(NULLIF(hour, ''), NULLIF(hour_of_day, ''), NULLIF(hourofday, '')) AS hour,
  COALESCE(NULLIF(eventid, ''), NULLIF(event_id, ''))                        AS eventid,
  COALESCE(NULLIF(controlid, ''), NULLIF(campaign_id, ''))                   AS controlid,
  COALESCE(NULLIF(strategyid, ''), NULLIF(strategy_id, ''))                  AS strategyid,
  COALESCE(NULLIF(auction_type, ''), NULLIF(auctiontype, ''))                AS auction_type,
  COALESCE(NULLIF(ad_exchange, ''), NULLIF(exchange, ''))                    AS ad_exchange,
  COALESCE(NULLIF(publisher_id, ''), NULLIF(publisherid, ''))                AS publisher_id,
  COALESCE(NULLIF(publisher_name, ''), NULLIF(publishername, ''))            AS publisher_name,
  COALESCE(NULLIF(publisher_domain, ''), NULLIF(domain, ''))                 AS publisher_domain,
  COALESCE(NULLIF(publisher_url, ''), NULLIF(publisherurl, ''))              AS publisher_url,
  COALESCE(NULLIF(iab_category, ''), NULLIF(iabcategory, ''))                AS iab_category,
  COALESCE(NULLIF(iab_subcategory, ''), NULLIF(iabsubcategory, ''))          AS iab_subcategory,
  COALESCE(NULLIF(bid_offers, ''), NULLIF(offers, ''))                       AS bid_offers,
  bids,
  won,
  COALESCE(NULLIF(media_cost, ''), NULLIF(wonprice, ''))                     AS media_cost,
  COALESCE(NULLIF(total_bids_cost, ''), NULLIF(bidprice, ''))                AS total_bids_cost,
  impressions,
  clicks,
  COALESCE(NULLIF(conversions_1, ''), NULLIF(conversions1, ''), NULLIF(events1, '')) AS conversions_1,
  COALESCE(NULLIF(conversions_2, ''), NULLIF(conversions2, ''), NULLIF(events2, '')) AS conversions_2,
  COALESCE(NULLIF(conversions_3, ''), NULLIF(conversions3, ''), NULLIF(events3, '')) AS conversions_3,
  COALESCE(NULLIF(conversions_4, ''), NULLIF(conversions4, ''), NULLIF(events4, '')) AS conversions_4,
  COALESCE(NULLIF(conversions_5, ''), NULLIF(conversions5, ''), NULLIF(events5, '')) AS conversions_5,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.mediasmart_bid_supply_daily`;


-- -----------------------------------------------------------------------------
-- 4. mgid_delivery  (substitui mgid_daily)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `adframework.raw.mgid_delivery`
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Entrega diária MGID. Grain: day+campaignid. Atribuição via core.io_line_bindings.')
AS
SELECT
  day,
  campaignid,
  teaserid,
  impressions,
  clicks,
  conversionsinterest,
  conversionsdecision,
  conversionsbuy,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.mgid_daily`;


-- -----------------------------------------------------------------------------
-- 5. siprocal_delivery  (substitui siprocal_daily_materialized)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `adframework.raw.siprocal_delivery`
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Entrega diária Siprocal. advertiser é texto livre — atribuição via core.platform_client_links.')
AS
SELECT
  day,
  advertiser,
  campaign_id,
  creative_type,
  creative,
  impressions,
  clicks,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.siprocal_daily_materialized`;


-- -----------------------------------------------------------------------------
-- 6. Tabelas de metadata — copiar sem transformações
-- -----------------------------------------------------------------------------

CREATE OR REPLACE TABLE `adframework.raw.mediasmart_advertisers`
OPTIONS (description = 'Cadastro de anunciantes MediaSmart. id = eventid em mediasmart_delivery.')
AS SELECT id, name, iab_category, domain, sensitive_content,
          CURRENT_TIMESTAMP() AS raw_ingested_at
FROM `adframework.raw.mediasmart_advertisers`
WHERE FALSE;  -- estrutura apenas; dados já estão na tabela atual com mesmo nome

-- NOTA: mediasmart_campaigns, mediasmart_creatives, mgid_campaigns, mgid_creatives
-- já têm os nomes corretos — não precisam de rename, apenas de limpeza de colunas duplicadas
-- via rebuild_raw_daily_canonical.py (repo Shiro). Manter como estão por ora.
