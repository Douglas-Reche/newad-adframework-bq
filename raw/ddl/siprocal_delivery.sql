-- raw.siprocal_delivery
-- Entrega diária da Siprocal — materialização do export BQ-para-BQ da plataforma.
-- Grain: day + advertiser + campaign_id + creative_type + creative
-- IMPORTANTE: O campo `advertiser` é texto livre enviado pela Siprocal.
--   A atribuição de cliente é feita por LOWER(advertiser) = LOWER(link_value) em core.platform_client_links.
--   Qualquer variação de escrita pelo lado da Siprocal quebra a atribuição silenciosamente.
-- Fonte: job siprocal_daily_external (orchestrator) — materialização de tabela BQ externa da Siprocal
-- Atualização: conforme disponibilidade da Siprocal (não controlada pela Newad)

CREATE OR REPLACE TABLE `adframework.raw.siprocal_delivery`
(
  -- Dimensões
  day             STRING    NOT NULL,  -- YYYY-MM-DD
  advertiser      STRING,              -- nome do anunciante (texto livre da Siprocal)
  campaign_id     STRING,              -- ID da campanha na Siprocal
  creative_type   STRING,              -- tipo de criativo (Push, Native, Display, etc.)
  creative        STRING,              -- nome/ID do criativo

  -- Métricas de entrega
  impressions     STRING,
  clicks          STRING,

  -- Metadados de ingestão
  platform        STRING,             -- sempre 'siprocal'
  report_name     STRING,
  raw_ingested_at TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (
  description = 'Entrega diária Siprocal. Grain: day+advertiser+campaign_id+creative_type+creative. advertiser é texto livre — join frágil. Atribuição via core.platform_client_links.'
);
