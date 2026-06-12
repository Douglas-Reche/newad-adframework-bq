-- raw.mediasmart_advertisers
-- Cadastro de anunciantes/contas da MediaSmart.
-- Grain: id (event_id da conta)
-- Fonte: API MediaSmart /api/advertiser — carga periódica (não diária)
-- Chave de join com raw.mediasmart_delivery: id = eventid

-- Schema verificado em produção 2026-06-12. Diferente do esperado:
--   event_id = 'newad_brazil-{32chars}'  — chave de JOIN com delivery.eventid
--   id       = '{32chars}'               — sufixo do event_id, usado em stg.ms_clients.ms_client_id
--   SEM raw_ingested_at (não injetado pelo ETL nesta tabela)
--   WRITE_TRUNCATE desde 2026-06-11: 21 linhas únicas, sem duplicatas

CREATE OR REPLACE TABLE `adframework.raw.mediasmart_advertisers`
(
  event_id            STRING,    -- 'newad_brazil-{id}' — JOIN com delivery.eventid
  id                  STRING,    -- sufixo puro do event_id (32 chars)
  name                STRING,    -- nome do anunciante
  iab_category        STRING,    -- categoria IAB
  domain              STRING,    -- domínio do anunciante
  sensitive_content   STRING     -- flag de conteúdo sensível ('true'/'false')
)
OPTIONS (
  description = 'Cadastro de anunciantes MediaSmart. event_id = eventid nas tabelas de delivery. WRITE_TRUNCATE — sem duplicatas.'
);
