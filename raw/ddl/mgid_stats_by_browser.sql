-- raw.mgid_stats_by_browser
-- Estatísticas diárias MGID por campanha + browser.
-- Grain: day + campaignid + browser
-- Fonte: job mgid_stats_by_browser (orchestrator) via /goodhits/clients/{client_id}/statistics-reports
-- Dimensões API: day, campaignId, browser (3 dims — limite máximo da API)
-- NOTA: os é job separado (mgid_stats_by_os) — os e browser são atributos independentes,
--   sem hierarquia entre si, não é possível combinar em um único job dentro do limite de 3 dims.
-- NOTA: spent retorna como objeto {'amount': '...', 'currency': 'USD'} — armazenado como string.
-- Alimenta: stg.mgid_delivery_by_browser (T11b)

CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_browser`
(
  -- Dimensões
  day                   STRING    NOT NULL,  -- YYYY-MM-DD
  campaignid            STRING,              -- ID da campanha MGID
  browser               STRING,              -- código do browser (ex: chrome, firefox, operamobile)

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
  description = 'Estatísticas diárias MGID por browser. Grain: day+campaignid+browser. OS em tabela separada (raw.mgid_stats_by_os). Alimenta stg.mgid_delivery_by_browser (T11b).'
);
