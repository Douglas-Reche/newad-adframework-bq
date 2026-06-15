-- raw.mgid_stats_creative
-- Estatísticas diárias MGID por campanha + criativo — dados exatos da API, sem transformações.
-- Grain: day + campaignid + teaserid
-- Fonte: job mgid_stats_creative (orchestrator) via /goodhits/clients/{client_id}/statistics-reports
-- Dimensões API: day, campaignId, teaserId
-- Métricas API: impressions, clicks, spent, cpc, ctr, conversions*
-- NOTA: spent e cpc retornam como objeto {'amount': '...', 'currency': 'USD'} — armazenados como string.
-- Alimenta: stg.mgid_creative_delivery (T4)

CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_creative`
(
  -- Dimensões
  day                   STRING    NOT NULL,
  campaignid            STRING,
  teaserid              STRING,

  -- Métricas de entrega
  impressions           STRING,
  clicks                STRING,
  ctr                   STRING,

  -- Métricas de custo e receita (objeto JSON: {'amount': '...', 'currency': 'USD'})
  spent                 STRING,
  cpc                   STRING,
  revenue               STRING,
  profit                STRING,
  roas                  STRING,

  -- Métricas de conversão (funil MGID)
  conversionsinterest   STRING,
  conversionsdecision   STRING,
  conversionsbuy        STRING,

  -- Metadados de ingestão
  platform              STRING,
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (
  description = 'Estatísticas diárias MGID por campanha + criativo. Grain: day+campaignid+teaserid. Alimenta stg.mgid_creative_delivery (T4).'
);
