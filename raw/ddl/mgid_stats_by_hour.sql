-- raw.mgid_stats_by_hour
-- Estatísticas diárias MGID por campanha + hora do dia.
-- Grain: day + campaignid + hour
-- Fonte: job mgid_stats_by_hour (orchestrator) via /goodhits/clients/{client_id}/statistics-reports
-- Dimensões API: day, campaignId, hour — Métricas API: impressions, clicks, spent, conversions*
-- NOTA: spent retorna como objeto {'amount': '...', 'currency': 'USD'} — armazenado como string.
-- Alimenta: stg.mgid_delivery_by_hour (T12)

CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_hour`
(
  -- Dimensões
  day                   STRING    NOT NULL,  -- YYYY-MM-DD
  campaignid            STRING,              -- ID da campanha MGID
  hour                  STRING,              -- hora do dia (0-23)

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
  description = 'Estatísticas diárias MGID por hora. Grain: day+campaignid+hour. Alimenta stg.mgid_delivery_by_hour (T12).'
);
