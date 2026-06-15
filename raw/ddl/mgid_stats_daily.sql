-- raw.mgid_stats_daily
-- Estatísticas diárias MGID por campanha — dados exatos da API, sem transformações.
-- Grain: day + campaignid
-- Fonte: job mgid_stats_daily (orchestrator) via /goodhits/clients/{client_id}/statistics-reports
-- Dimensões API: day, campaignId
-- Métricas API: impressions, clicks, spent, cpc, ctr, revenue, profit, roas, conversions*
-- NOTA: spent, cpc, revenue, profit, roas retornam como objeto {'amount': '...', 'currency': 'USD'} — armazenados como string.
-- Alimenta: stg.mgid_delivery (T3) — delivery; stg.mgid_revenue (T8) — financeiro

CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_daily`
(
  -- Dimensões
  day                   STRING    NOT NULL,  -- YYYY-MM-DD
  campaignid            STRING,              -- ID da campanha MGID

  -- Métricas de entrega
  impressions           STRING,
  clicks                STRING,
  ctr                   STRING,              -- click-through rate

  -- Métricas de custo e receita (objeto JSON: {'amount': '...', 'currency': 'USD'})
  spent                 STRING,              -- custo de mídia
  cpc                   STRING,              -- custo por clique
  revenue               STRING,              -- valor das conversões (performance financeira)
  profit                STRING,              -- revenue - spent
  roas                  STRING,              -- revenue / spent

  -- Métricas de conversão (funil MGID)
  conversionsinterest   STRING,             -- topo de funil
  conversionsdecision   STRING,             -- meio de funil
  conversionsbuy        STRING,             -- fundo de funil

  -- Metadados de ingestão
  platform              STRING,             -- sempre 'mgid'
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (
  description = 'Estatísticas diárias MGID por campanha. Grain: day+campaignid. Inclui delivery + financeiro (spent, revenue, profit, roas). Alimenta T3 (delivery) e T8 (revenue).'
);
