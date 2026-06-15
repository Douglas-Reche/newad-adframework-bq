-- raw.mgid_stats_by_os
-- Estatísticas diárias MGID por campanha + sistema operacional.
-- Grain: day + campaignid + os
-- Fonte: job mgid_stats_by_os (orchestrator) via /goodhits/clients/{client_id}/statistics-reports
-- Dimensões API: day, campaignId, os (3 dims — limite máximo da API)
-- NOTA: browser é job separado (mgid_stats_by_browser) — os e browser são atributos independentes,
--   sem hierarquia entre si, não é possível combinar em um único job dentro do limite de 3 dims.
-- NOTA: spent retorna como objeto {'amount': '...', 'currency': 'USD'} — armazenado como string.
-- Alimenta: stg.mgid_delivery_by_os (T11)

CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_by_os`
(
  -- Dimensões
  day                   STRING    NOT NULL,  -- YYYY-MM-DD
  campaignid            STRING,              -- ID da campanha MGID
  os                    STRING,              -- código do OS (ex: android10mobile, windows10)

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
  description = 'Estatísticas diárias MGID por OS. Grain: day+campaignid+os. Browser em tabela separada (raw.mgid_stats_by_browser). Alimenta stg.mgid_delivery_by_os (T11).'
);
