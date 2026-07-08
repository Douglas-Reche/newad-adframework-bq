-- raw.mg_delivery
-- Fato de entrega diaria da MGID (T4), conforme raw_layer_design.md.
-- Grain: dia + campanha + creative (sem client_id -- ver nota)
-- Fonte: GET /v1/goodhits/clients/{MGID_CLIENT_ID}/statistics-reports
--   dimensions[] = day, campaignId, teaserId
--   metrics[] = impressions, clicks, conversionsInterest, conversionsDecision, conversionsBuy
-- Ingestao: diaria incremental
--
-- client_id: NAO existe nesta tabela. Mesma decisao do T1/T2 MGID -- a API nao
-- expoe identidade de advertiser. Resolvido na STG via:
--   campaign_id -> core.platform_client_links.link_value -> .client_id
--
-- creative_id: testado e CONFIRMADO em 2026-06-22 -- teaserId da entrega bate
-- exatamente com raw.mg_teasers.creative_id (mesmo namespace numerico). Join
-- funciona, diferente do gap encontrado na MediaSmart.
--
-- ctr: NAO gravado aqui -- derivado, recalculado no STG.

CREATE OR REPLACE TABLE `adframework.raw.mg_delivery`
(
  date                  DATE,       -- "day"
  campaign_id           STRING,     -- "campaignId" -- FK para raw.mg_campaigns.campaign_id
  creative_id           STRING,     -- "teaserId" -- FK para raw.mg_teasers.creative_id (confirmado)
  impressions           FLOAT64,
  clicks                FLOAT64,
  conversions_interest  FLOAT64,
  conversions_decision  FLOAT64,
  conversions_buy       FLOAT64,
  platform              STRING,     -- 'mgid' (injetado)
  raw_ingested_at       TIMESTAMP   -- timestamp da ingestao (injetado)
)
PARTITION BY date
OPTIONS (
  description = 'T4 MGID — fato de entrega diaria. creative_id confirmado joinable com mg_teasers. Particionado por date, incremental.'
);
