-- raw.mgid_campaigns
-- Metadata de campanhas do MGID.
-- Grain: id (campaignid)
-- Fonte: API MGID /goodhits/clients/{client_id}/campaigns — carga periódica
-- Chave de join com raw.mgid_delivery: id = campaignid

CREATE OR REPLACE TABLE `adframework.raw.mgid_campaigns`
(
  id                    STRING,    -- campaignid
  name                  STRING,    -- nome da campanha
  status                STRING,    -- status (active, paused, etc.)
  language              STRING,
  campaign_type         STRING,    -- tipo de campanha
  category              STRING,    -- categoria IAB
  start_date            STRING,
  end_date              STRING,
  targets               STRING,    -- configurações de targeting (JSON serializado)
  limits_filter         STRING,    -- limites de frequência (JSON serializado)
  sources_optimization  STRING,    -- otimização de fontes (JSON serializado)
  source_filters        STRING,    -- filtros de fonte (JSON serializado)
  statistics            STRING,    -- estatísticas agregadas (JSON serializado)
  tracking_options      STRING,    -- opções de tracking (JSON serializado)
  when_add              STRING,    -- data de criação

  -- Metadados de ingestão
  raw_ingested_at       TIMESTAMP
)
OPTIONS (
  description = 'Metadata de campanhas MGID. id = campaignid. Chave de join com mgid_delivery e core.io_line_bindings.'
);
