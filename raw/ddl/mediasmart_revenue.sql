-- raw.mediasmart_revenue
-- Receita diária da MediaSmart — separada da entrega por ter grain diferente.
-- Grain: day + controlid + strategyid + revenuesource
-- Nota: sem eventid — a API de revenue não retorna o campo de conta.
-- Fonte: job mediasmart_revenue_daily (orchestrator), rules=revenuesource=[event1..5,2..5]
-- Atualização: diária ~03:25 UTC

CREATE OR REPLACE TABLE `adframework.raw.mediasmart_revenue`
(
  -- Dimensões
  day             STRING    NOT NULL,  -- YYYY-MM-DD
  controlid       STRING,              -- ID da campanha
  strategyid      STRING,              -- ID da estratégia
  revenuesource   STRING,              -- Fonte de receita (event1..5, 2..5)

  -- Métrica
  clientrevenue   STRING,              -- Receita cobrada ao cliente (moeda nativa)

  -- Metadados de ingestão
  platform        STRING,              -- sempre 'mediasmart'
  report_name     STRING,
  raw_ingested_at TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (
  description = 'Receita diária MediaSmart. Grain: day+controlid+strategyid+revenuesource. Separado de mediasmart_delivery por grain e semântica distintos.'
);
