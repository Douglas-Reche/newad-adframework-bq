-- core.client_reporting_source_config
-- Regra de negócio: por client_id, decide se o reporting deve usar o
-- histórico manual (`core.historical_overrides_delivery`) ou o dado real
-- da plataforma (`stg.*_delivery`) — versionada (SCD2), consumida por
-- `core.resolve_reporting_source()` em vez de JOIN inline em cada view
-- (mesmo padrão de core.dict_format / core.advertiser_platform_rules —
-- ver core/OWNERSHIP.yaml para a lista completa coberta por este
-- procedimento).
--
-- Criada em 2026-08-05 (task "Ambientes Staging x Produção", desenhada com
-- o usuário) para generalizar o caso hoje hardcoded em
-- `gold.vw_fact_delivery_reporting` (Cora, client_id = 'banco_cora_fe13d78a',
-- day < '2026-07-01' cravado no SQL da view) — a mesma decisão vai ser
-- necessária para outros clientes/períodos no futuro, e cravar
-- client_id+data no SQL de uma view compartilhada por todos os clientes é
-- exatamente o tipo de risco que o Nível 2 de teste (apply_ddl.py
-- --env=test) existe para mitigar.
--
-- Não tem coluna de "data de corte" (ex: override_until) de propósito —
-- o RANGE real (MIN(day)/MAX(day)) vem calculado ao vivo em
-- `core.historical_overrides_delivery` para aquele client_id, dentro de
-- `core.resolve_reporting_source()`. Guardar a data de corte aqui
-- duplicaria uma informação que já existe nos dados carregados e que
-- pode mudar (novo lote de override estende o range) sem precisar de um
-- UPDATE nesta tabela toda vez.
--
-- override_active = false é a saída padrão segura: sem linha vigente para
-- um client_id (cliente nunca teve override) OU com a linha vigente
-- desligada explicitamente, `resolve_reporting_source()` sempre retorna
-- 'platform' — nenhum client_id passa a usar histórico sem uma linha
-- SCD2 explícita dizendo isso.
--
-- Como adicionar/trocar uma regra (procedimento SCD2 — mesmo padrão de
-- dict_format/advertiser_platform_rules):
--   1. UPDATE ... SET effective_to = <data da mudança> WHERE client_id = ... AND effective_to IS NULL;
--   2. INSERT INTO ... a nova linha com effective_from = <data da mudança>, effective_to = NULL.
--   NUNCA fazer UPDATE do override_active de uma linha existente — isso
--   reinterpretaria retroativamente qualquer relatório já servido com a
--   versão antiga da regra (mesmo bug documentado no ADR 0001 que motivou
--   o padrão SCD2 nas outras 3 tabelas).
--   Sempre confirmar (SELECT antes de INSERT) que não existe linha
--   vigente ambígua/conflitante para o mesmo client_id antes de inserir.

CREATE TABLE IF NOT EXISTS `adframework.core.client_reporting_source_config`
(
  client_id         STRING    NOT NULL,  -- FK lógica para gold.dim_client / dim_advertiser
  override_active   BOOLEAN   NOT NULL,  -- true = usa historical_overrides_delivery dentro do range real; false = sempre dado real da plataforma
  effective_from    DATE      NOT NULL,  -- desde quando esta versão da regra vale para fins de reprocessamento retroativo
  effective_to      DATE,                -- até quando valeu; NULL = versão ainda ativa
  reason            STRING,              -- por que este client_id precisa de override (contexto de negócio)
  confirmed_by      STRING,              -- quem confirmou a decisão (ex: 'douglas')
  confirmed_at      TIMESTAMP            -- quando a decisão foi registrada (trilha de auditoria, != effective_from)
)
OPTIONS (
  description = 'Regra de negocio: por client_id, usa historico manual (override) ou dado real da plataforma para reporting. Versionada (SCD2) por effective_from/effective_to. Consumida via core.resolve_reporting_source().'
);

-- Seed inicial proposto (NÃO aplicado por este arquivo — INSERT INTO
-- explícito, revisar client_id/datas antes de rodar):
--
-- INSERT INTO `adframework.core.client_reporting_source_config` VALUES
--   ('banco_cora_fe13d78a', TRUE, DATE '2025-01-01', NULL,
--    'Migração do hardcode em gold.vw_fact_delivery_reporting (Jan-Jun/2026) para a regra genérica.',
--    'douglas', CURRENT_TIMESTAMP());
