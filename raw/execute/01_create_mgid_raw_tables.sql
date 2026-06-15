-- =============================================================================
-- EXECUÇÃO: Criar todas as raw tables MGID de statistics-reports
-- Projeto: adframework
-- Dataset: raw
-- Data: 2026-06-14
-- Ordem: executar em sequência no BigQuery console
-- =============================================================================

-- ─── Job A — Campaign daily ───────────────────────────────────────────────────
CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_daily`
(
  day                   STRING    NOT NULL,
  campaignid            STRING,
  impressions           STRING,
  clicks                STRING,
  ctr                   STRING,
  spent                 STRING,
  cpc                   STRING,
  revenue               STRING,
  profit                STRING,
  roas                  STRING,
  conversionsinterest   STRING,
  conversionsdecision   STRING,
  conversionsbuy        STRING,
  platform              STRING,
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Estatísticas diárias MGID por campanha. Grain: day+campaignid. Alimenta T3 (delivery) e T8 (revenue).');

-- ─── Job B — Creative daily ───────────────────────────────────────────────────
CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_creative`
(
  day                   STRING    NOT NULL,
  campaignid            STRING,
  teaserid              STRING,
  impressions           STRING,
  clicks                STRING,
  ctr                   STRING,
  spent                 STRING,
  cpc                   STRING,
  revenue               STRING,
  profit                STRING,
  roas                  STRING,
  conversionsinterest   STRING,
  conversionsdecision   STRING,
  conversionsbuy        STRING,
  platform              STRING,
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Estatísticas diárias MGID por campanha + criativo. Grain: day+campaignid+teaserid. Alimenta T4.');

-- ─── Job C — By device ────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_device`
(
  day                   STRING    NOT NULL,
  campaignid            STRING,
  devicetype            STRING,
  impressions           STRING,
  clicks                STRING,
  spent                 STRING,
  conversionsinterest   STRING,
  conversionsdecision   STRING,
  conversionsbuy        STRING,
  platform              STRING,
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Estatísticas diárias MGID por dispositivo. Grain: day+campaignid+devicetype. Alimenta T9.');

-- ─── Job D — By geo (region) ──────────────────────────────────────────────────
CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_geo`
(
  day                   STRING    NOT NULL,
  campaignid            STRING,
  region                STRING,
  impressions           STRING,
  clicks                STRING,
  spent                 STRING,
  conversionsinterest   STRING,
  conversionsdecision   STRING,
  conversionsbuy        STRING,
  platform              STRING,
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Estatísticas diárias MGID por região. Grain: day+campaignid+region. country enriquecido via JOIN com raw.mgid_geo_regions na STG T10.');

-- ─── Job D-lookup — Geo regions (one-time) ────────────────────────────────────
CREATE OR REPLACE TABLE `adframework.raw.mgid_geo_regions`
(
  region_id             STRING    NOT NULL,
  region_name           STRING,
  region_name_latin     STRING,
  country_code          STRING,
  country_name          STRING,
  raw_ingested_at       TIMESTAMP
)
OPTIONS (description = 'Lookup global de regiões MGID. Grain: region_id único. Fonte: /dictionaries/geo. Usado no JOIN do stg.mgid_delivery_by_geo (T10).');

-- ─── Job E1 — By OS ───────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_os`
(
  day                   STRING    NOT NULL,
  campaignid            STRING,
  os                    STRING,
  impressions           STRING,
  clicks                STRING,
  spent                 STRING,
  conversionsinterest   STRING,
  conversionsdecision   STRING,
  conversionsbuy        STRING,
  platform              STRING,
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Estatísticas diárias MGID por OS. Grain: day+campaignid+os. Alimenta T11.');

-- ─── Job E2 — By browser ──────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_browser`
(
  day                   STRING    NOT NULL,
  campaignid            STRING,
  browser               STRING,
  impressions           STRING,
  clicks                STRING,
  spent                 STRING,
  conversionsinterest   STRING,
  conversionsdecision   STRING,
  conversionsbuy        STRING,
  platform              STRING,
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Estatísticas diárias MGID por browser. Grain: day+campaignid+browser. Alimenta T11b.');

-- ─── Job F — By hour ──────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_hour`
(
  day                   STRING    NOT NULL,
  campaignid            STRING,
  hour                  STRING,
  impressions           STRING,
  clicks                STRING,
  spent                 STRING,
  conversionsinterest   STRING,
  conversionsdecision   STRING,
  conversionsbuy        STRING,
  platform              STRING,
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Estatísticas diárias MGID por hora. Grain: day+campaignid+hour. Alimenta T12.');

-- ─── Job G — By widget ────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_widget`
(
  day                   STRING    NOT NULL,
  campaignid            STRING,
  widgetid              STRING,
  impressions           STRING,
  clicks                STRING,
  spent                 STRING,
  platform              STRING,
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (description = 'Estatísticas diárias MGID por widget/publisher. Grain: day+campaignid+widgetid. Alimenta T13.');
