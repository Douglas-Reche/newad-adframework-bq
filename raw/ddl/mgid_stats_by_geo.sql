-- raw.mgid_stats_by_geo
-- Estatísticas diárias MGID por campanha + região geográfica.
-- Grain: day + campaignid + region
-- Fonte: job mgid_stats_by_geo (orchestrator) via /goodhits/clients/{client_id}/statistics-reports
-- Dimensões API: day, campaignId, region (3 dims — limite máximo da API)
-- NOTA: country não é dimensão aqui — enriquecido via JOIN com raw.mgid_geo_regions na STG.
-- NOTA: spent retorna como objeto {'amount': '...', 'currency': 'USD'} — armazenado como string.
-- Alimenta: stg.mgid_delivery_by_geo (T10)

CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_geo`
(
  -- Dimensões
  day                   STRING    NOT NULL,  -- YYYY-MM-DD
  campaignid            STRING,              -- ID da campanha MGID
  region                STRING,              -- ID da região (city_ID do /dictionaries/geo)

  -- Métricas de entrega
  impressions           STRING,
  clicks                STRING,

  -- Métricas de custo e receita (objeto JSON: {'amount': '...', 'currency': 'USD'})
  spent                 STRING,
  revenue               STRING,
  profit                STRING,
  roas                  STRING,

  -- Métricas de conversão (funil MGID)
  conversionsinterest   STRING,
  conversionsdecision   STRING,
  conversionsbuy        STRING,

  -- Metadados de ingestão
  platform              STRING,             -- sempre 'mgid'
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (
  description = 'Estatísticas diárias MGID por região. Grain: day+campaignid+region. country enriquecido via JOIN com raw.mgid_geo_regions na STG T10.'
);
