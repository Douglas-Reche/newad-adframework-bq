-- raw.mgid_delivery
-- Entrega diária do MGID — dados exatos da API, sem transformações.
-- Grain: day + campaignid (+ teaserid quando disponível)
-- IMPORTANTE: A API do MGID não expõe campo de anunciante/cliente.
--   Toda atribuição de cliente para MGID ocorre via core.io_line_bindings (campaignid → cliente).
-- Fonte: job mgid_daily_daily (orchestrator) via /goodhits/clients/{client_id}/statistics-reports
-- Atualização: diária ~03:20 UTC

CREATE OR REPLACE TABLE `adframework.raw.mgid_delivery`
(
  -- Dimensões
  day                   STRING    NOT NULL,  -- YYYY-MM-DD
  campaignid            STRING,              -- ID da campanha (único identificador disponível na API)
  teaserid              STRING,              -- ID do teaser/criativo (opcional, quando include_teaser_dimension=true)

  -- Métricas de entrega
  impressions           STRING,
  clicks                STRING,

  -- Métricas de conversão (funil MGID)
  conversionsinterest   STRING,             -- conversão de interesse (topo de funil)
  conversionsdecision   STRING,             -- conversão de decisão (meio de funil)
  conversionsbuy        STRING,             -- conversão de compra (fundo de funil)

  -- Metadados de ingestão
  platform              STRING,             -- sempre 'mgid'
  report_name           STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (
  description = 'Entrega diária MGID. Grain: day+campaignid. Sem campo de anunciante na API — atribuição via core.io_line_bindings.'
);
