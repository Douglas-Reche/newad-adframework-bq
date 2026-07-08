-- raw.ms_delivery_by_hour
-- Fato de entrega diaria por hora da MediaSmart (T7).
-- Grain: dia + hora + client + campanha + creative
-- Fonte: GET /api/analytics/custom-report
--   drilldown = day,eventid,controlid,creativeid,hour
--   kpis = impressions,clicks,events1..5
-- Ingestao: diaria incremental
--
-- "Hour" vem da API como string "HH:00" (ex: "00:00", "23:00"), nao como
-- inteiro 0-23 como o design original assumia. Extraido para INT64 na ingestao
-- (connector parseia os 2 primeiros caracteres).
--
-- Sem dados antes de 2026-05-28 (limitacao da API, sem backfill possivel para
-- periodo anterior) -- confirmado no design original, nao testado novamente aqui.

CREATE OR REPLACE TABLE `adframework.raw.ms_delivery_by_hour`
(
  date              DATE,
  hour              INT64,      -- 0-23, extraido de "HH:00"
  client_id         STRING,
  campaign_id       STRING,
  creative_id       STRING,
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
  description = 'T7 MS — entrega por hora. Sem dados antes de 2026-05-28. Particionado por date, incremental.'
);
