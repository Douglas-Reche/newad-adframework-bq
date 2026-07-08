-- raw.ms_delivery_by_geo
-- Fato de entrega diaria por geografia da MediaSmart (T5).
-- Grain: dia + client + campanha + creative + country + city
-- Fonte: GET /api/analytics/custom-report
--   drilldown = day,eventid,controlid,creativeid,countrycode,city
--   kpis = impressions,clicks,events1..5
-- Ingestao: diaria incremental
--
-- NOTA: "region" (estado) NAO existe como dimensao de drilldown na API da
-- MediaSmart (confirmado em 2026-06-22, testado e rejeitado pela API: "Provided
-- drilldown variable is wrong: regioncode"). O design original assumia region
-- disponivel ("BR-SP") sem ter testado -- nao existe. Apenas country (codigo
-- ISO3, ex: "BRA") e city (nome em minusculas, sem acentuacao) estao disponiveis.
--
-- creative_id: mesmo formato/gap-resolvido de raw.ms_delivery (prefixo "cr-",
-- joinable com raw.ms_creatives apos o fix de 2026-06-22).
--
-- Alta cardinalidade -- MS pode exigir timeout maior (REQUEST_TIMEOUT_SECONDS=60
-- ja configurado no connector).

CREATE OR REPLACE TABLE `adframework.raw.ms_delivery_by_geo`
(
  date              DATE,
  client_id         STRING,
  campaign_id       STRING,
  creative_id       STRING,
  country           STRING,    -- codigo ISO3, ex: "BRA"
  city              STRING,    -- nome da cidade, minusculas
  impressions       FLOAT64,
  clicks            FLOAT64,
  conversions_1     FLOAT64,
  conversions_2     FLOAT64,
  conversions_3     FLOAT64,
  conversions_4     FLOAT64,
  conversions_5     FLOAT64,
  platform          STRING,
  raw_ingested_at   TIMESTAMP
)
PARTITION BY date
OPTIONS (
  description = 'T5 MS — entrega por geografia. Sem region (nao existe na API). Particionado por date, incremental.'
);

