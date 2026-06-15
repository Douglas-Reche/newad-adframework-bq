-- raw.mgid_stats_by_widget
-- Estatísticas diárias MGID por campanha + widget (publisher/fonte de tráfego).
-- Grain: day + campaignid + widgetid
-- Fonte: job mgid_stats_by_widget (orchestrator) via /goodhits/clients/{client_id}/statistics-reports
-- Dimensões API: day, campaignId, widgetId — Métricas API: impressions, clicks, spent
-- NOTA: spent retorna como objeto {'amount': '...', 'currency': 'USD'} — armazenado como string.
-- Sem conversions — volume muito granular, conversão por widget tem baixo valor analítico.
-- Alimenta: stg.mgid_delivery_by_widget (T13)

CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_widget`
(
  -- Dimensões
  day                   STRING    NOT NULL,  -- YYYY-MM-DD
  campaignid            STRING,              -- ID da campanha MGID
  widgetid              STRING,              -- ID do widget/publisher

  -- Métricas de entrega
  impressions           STRING,
  clicks                STRING,

  -- Métricas de custo e receita (objeto JSON: {'amount': '...', 'currency': 'USD'})
  spent                 STRING,
  revenue               STRING,
  profit                STRING,
  roas                  STRING,

  -- Metadados de ingestão
  platform              STRING,             -- sempre 'mgid'
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (
  description = 'Estatísticas diárias MGID por widget/publisher. Grain: day+campaignid+widgetid. Alimenta stg.mgid_delivery_by_widget (T13).'
);
