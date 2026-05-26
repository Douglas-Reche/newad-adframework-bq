-- raw.mediasmart_campaigns
-- Metadata de campanhas da MediaSmart (estrutura JSON da API, armazenada como STRING).
-- Grain: id (controlid da campanha)
-- Fonte: API MediaSmart /api/campaign — carga periódica
-- Chave de join com raw.mediasmart_delivery: id = controlid

CREATE OR REPLACE TABLE `adframework.raw.mediasmart_campaigns`
(
  id                    STRING,    -- controlid da campanha
  name                  STRING,    -- nome da campanha
  type                  STRING,    -- tipo (display, video, native, etc.)
  state                 STRING,    -- estado (active, paused, etc.)
  active                STRING,    -- flag de ativo
  goal                  STRING,    -- objetivo da campanha
  tags                  STRING,    -- tags (JSON serializado)
  strategies            STRING,    -- estratégias vinculadas (JSON serializado)
  schedule              STRING,    -- agendamento (JSON serializado)
  pricing               STRING,    -- modelo de precificação (JSON serializado)
  deals_and_pricing     STRING,    -- deals e precificação (JSON serializado)
  creatives             STRING,    -- criativos vinculados (JSON serializado)
  description           STRING,
  created_at            STRING,
  updated_at            STRING,

  -- Metadados de ingestão
  raw_ingested_at       TIMESTAMP
)
OPTIONS (
  description = 'Metadata de campanhas MediaSmart. id = controlid. Campos complexos armazenados como STRING (JSON).'
);
