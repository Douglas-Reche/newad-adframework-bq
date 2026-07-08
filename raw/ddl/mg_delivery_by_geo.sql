-- raw.mg_delivery_by_geo
-- Fato de entrega diaria por geografia da MGID (T5).
-- Grain: dia + creative + region
-- Fonte: GET /v1/goodhits/clients/{MGID_CLIENT_ID}/statistics-reports
--   dimensions[] = day, teaserId, region
--   metrics[] = impressions, clicks, conversionsInterest, conversionsDecision, conversionsBuy
-- Ingestao: diaria incremental
--
-- SEM campaign_id e SEM country nesta tabela -- decisoes deliberadas:
--
-- 1. campaign_id removido: a MGID aceita NO MAXIMO 3 dimensoes por chamada
--    (erro confirmado: "This collection should contain 3 elements or less.").
--    day+campaignId+teaserId+region = 4, excede o limite. Como teaserId ja e
--    FK para raw.mg_teasers (que tem campaign_id), resolvido via JOIN na STG:
--      raw.mg_delivery_by_geo.creative_id -> raw.mg_teasers.creative_id -> .campaign_id
--
-- 2. country nao gravado: a dimensao "region" da MGID retorna texto livre
--    (ex: "Sao Paulo City", "Texas State") -- mistura nivel de cidade e estado,
--    nao e so estado como o design original assumia ("SP"). Confirmado em 2026-06-22:
--    a maioria e Brasil, mas ja observamos trafego de fora (ex: "Texas State") --
--    pode ser trafego residual/VPN, baixo volume. country fica como pendencia de
--    resolucao na STG (parse de texto ou lookup), nao foi possivel trazer junto
--    devido ao limite de 3 dimensoes.

CREATE OR REPLACE TABLE `adframework.raw.mg_delivery_by_geo`
(
  date                  DATE,
  creative_id           STRING,     -- teaserId -- FK para raw.mg_teasers.creative_id
  region                STRING,     -- texto livre da MGID, mistura cidade/estado
  impressions           FLOAT64,
  clicks                FLOAT64,
  conversions_interest  FLOAT64,
  conversions_decision  FLOAT64,
  conversions_buy       FLOAT64,
  platform              STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY date
OPTIONS (
  description = 'T5 MGID — entrega por geografia, nivel creative. Sem campaign_id (resolvido via join com mg_teasers na STG) e sem country (region e texto livre, ver nota). Particionado por date, incremental.'
);
