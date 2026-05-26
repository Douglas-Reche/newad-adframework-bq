-- raw.mediasmart_delivery
-- Entrega diária da MediaSmart — dados exatos da API, sem transformações.
-- Grain: day + eventid + controlid + strategyid + conversion_source
-- Fonte: job mediasmart_daily_daily (orchestrator) via /analytics/custom-report
-- Atualização: diária ~03:20 UTC

CREATE OR REPLACE TABLE `adframework.raw.mediasmart_delivery`
(
  -- Dimensões de tempo e hierarquia
  day                 STRING    NOT NULL,  -- YYYY-MM-DD
  eventid             STRING,              -- ID da conta (account/event identifier)
  controlid           STRING,              -- ID da campanha
  strategyid          STRING,              -- ID da estratégia
  strategyname        STRING,              -- Nome da estratégia
  conversion_source   STRING,              -- Fonte de conversão (convsource na API)

  -- Métricas de entrega
  impressions         STRING,
  clicks              STRING,

  -- Métricas de vídeo
  video_start         STRING,
  video_25_viewed     STRING,
  video_50_viewed     STRING,
  video_75_viewed     STRING,
  video_completion    STRING,

  -- Conversões (conv1-5 = eventos customizados configurados na plataforma)
  conversions_1       STRING,
  conversions_2       STRING,
  conversions_3       STRING,
  conversions_4       STRING,
  conversions_5       STRING,

  -- Metadados de ingestão
  platform            STRING,              -- sempre 'mediasmart'
  report_name         STRING,              -- nome do job que originou o registro
  raw_ingested_at     TIMESTAMP            -- momento da ingestão no BQ
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (
  description = 'Entrega diária MediaSmart. Grain: day+eventid+controlid+strategyid+conversion_source. Fonte: API /analytics/custom-report via orchestrator.'
);
