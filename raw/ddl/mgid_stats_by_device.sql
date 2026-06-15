-- raw.mgid_stats_by_device
-- Estatísticas diárias MGID por campanha + tipo de dispositivo.
-- Grain: day + campaignid + devicetype
-- Fonte: job mgid_stats_by_device (orchestrator) via /goodhits/clients/{client_id}/statistics-reports
-- Dimensões API: day, campaignId, deviceType — Métricas API: impressions, clicks, spent, conversions*
-- NOTA: spent retorna como objeto {'amount': '...', 'currency': 'USD'} — armazenado como string.
-- Alimenta: stg.mgid_delivery_by_device (T9)

CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_device`
(
  -- Dimensões
  day                   STRING    NOT NULL,  -- YYYY-MM-DD
  campaignid            STRING,              -- ID da campanha MGID
  devicetype            STRING,              -- desktop | mobile | tablet | smarttv

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
  description = 'Estatísticas diárias MGID por dispositivo. Grain: day+campaignid+devicetype. Alimenta stg.mgid_delivery_by_device (T9).'
);
