-- raw.mediasmart_advertisers
-- Cadastro de anunciantes/contas da MediaSmart.
-- Grain: id (event_id da conta)
-- Fonte: API MediaSmart /api/advertiser — carga periódica (não diária)
-- Chave de join com raw.mediasmart_delivery: id = eventid

CREATE OR REPLACE TABLE `adframework.raw.mediasmart_advertisers`
(
  id                  STRING,    -- event_id da conta na MediaSmart
  name                STRING,    -- nome do anunciante
  iab_category        STRING,    -- categoria IAB
  domain              STRING,    -- domínio do anunciante
  sensitive_content   STRING,    -- flag de conteúdo sensível

  -- Metadados de ingestão
  raw_ingested_at     TIMESTAMP
)
OPTIONS (
  description = 'Cadastro de anunciantes MediaSmart. id = eventid usado na mediasmart_delivery para identificar a conta.'
);
