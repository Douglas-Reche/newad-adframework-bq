-- stg.ms_clients (T1)
-- Cadastro de contas/anunciantes MediaSmart com IDs legíveis.
-- Grain: 1 linha por conta (ms_client_id único).
-- Fonte: raw.mediasmart_advertisers (WRITE_TRUNCATE desde 2026-06-11)
--
-- ms_client_id: ID legível gerado por nós — slug(name) + primeiros 8 chars de id.
-- ms_event_id:  ID técnico da plataforma — chave de JOIN com delivery.eventid.
--
-- Schema real da tabela (verificado 2026-06-12):
--   event_id = 'newad_brazil-{32chars}'  → ms_event_id (JOIN com delivery)
--   id       = '{32chars}'               → sufixo para gerar ms_client_id
--   Sem raw_ingested_at (WRITE_TRUNCATE garante 21 linhas únicas — sem dedup necessário)
--
-- DEPENDÊNCIAS ABAIXO (todas usam ms_event_id como FK):
--   T3 stg.ms_campaigns, T6 stg.ms_delivery, T7 stg.ms_creative_delivery,
--   T8 stg.ms_revenue, T9-T13 stg.ms_delivery_by_*
--
-- NÃO substitui nenhuma view existente — view nova.

CREATE OR REPLACE VIEW `adframework.stg.ms_clients` AS
SELECT
  CONCAT(
    LOWER(REGEXP_REPLACE(name, r'[^a-zA-Z0-9]', '_')),
    '_',
    LEFT(id, 8)
  )                                          AS ms_client_id,
  event_id                                   AS ms_event_id,
  name                                       AS ms_client_name,
  domain,
  iab_category,
  SAFE_CAST(sensitive_content AS BOOL)       AS sensitive_content
FROM `adframework.raw.mediasmart_advertisers`
WHERE event_id IS NOT NULL;
