-- raw.mg_delivery_by_hour
-- Fato de entrega diaria por hora da MGID (T7).
-- Grain: dia + hora + creative
-- Fonte: GET /v1/goodhits/clients/{MGID_CLIENT_ID}/statistics-reports
--   dimensions[] = day, teaserId, hour (3 dimensoes -- dentro do limite, sem gap)
--   metrics[] = impressions, clicks, conversionsInterest, conversionsDecision, conversionsBuy
-- Ingestao: diaria incremental
--
-- SEM campaign_id (mesmo padrao do T5/T6) -- resolvido via JOIN com
-- raw.mg_teasers.creative_id -> campaign_id na STG.
-- "hour" ja vem como inteiro 0-23 da API, sem necessidade de parse.

CREATE OR REPLACE TABLE `adframework.raw.mg_delivery_by_hour`
(
  date                  DATE,
  hour                  INT64,
  creative_id           STRING,     -- teaserId -- FK para raw.mg_teasers.creative_id
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
  description = 'T7 MGID — entrega por hora, nivel creative. Sem campaign_id (resolvido na STG). Particionado por date, incremental.'
);
