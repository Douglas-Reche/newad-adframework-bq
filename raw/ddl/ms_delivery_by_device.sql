-- raw.ms_delivery_by_device
-- Fato de entrega diaria por device/OS da MediaSmart (T6).
-- Grain: dia + client + campanha + creative + device_type + operating_system
-- Fonte: GET /api/analytics/custom-report
--   drilldown = day,eventid,controlid,creativeid,devicetype,os
--   kpis = impressions,clicks,events1..5
-- Ingestao: diaria incremental
--
-- Sem limite de dimensoes na MediaSmart (diferente da MGID) -- device_type e os
-- couberam juntos numa unica chamada, sem problema.

CREATE OR REPLACE TABLE `adframework.raw.ms_delivery_by_device`
(
  date               DATE,
  client_id          STRING,
  campaign_id        STRING,
  creative_id        STRING,
  device_type        STRING,    -- ex: Tablet, Desktop, Smartphone
  operating_system   STRING,    -- ex: android, ipad, chrome os, unknown
  impressions        FLOAT64,
  clicks             FLOAT64,
  conversions_1      FLOAT64,
  conversions_2      FLOAT64,
  conversions_3      FLOAT64,
  conversions_4      FLOAT64,
  conversions_5      FLOAT64,
  platform           STRING,
  raw_ingested_at    TIMESTAMP
)
PARTITION BY date
OPTIONS (
  description = 'T6 MS — entrega por device/OS. Particionado por date, incremental.'
);
