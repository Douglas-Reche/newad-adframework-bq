-- core.advertiser_platform_rules — Migração: relaxar client_id para NULLABLE
-- ----------------------------------------------------------------------------
-- Contexto: Douglas confirmou que quer os dois modos de regra de remapeamento
-- de plataforma — regra GERAL (vale para todos os clientes que não tiverem
-- override específico) e regra POR CLIENTE (tem prioridade sobre a geral
-- quando existir para a mesma data), mesmo padrão que core.client_business_rules
-- já resolve via core.resolve_client_business_rule() (ver core/ddl/resolve_client_business_rule.sql).
--
-- client_id era STRING NOT NULL desde a criação da tabela (core/ddl/advertiser_platform_rules.sql).
-- Esta migração relaxa a coluna para NULLABLE, preservando as 2 linhas já
-- existentes (Cora/Push→Siprocal, Casa do Construtor/Áudio→MiQ) intactas —
-- ALTER COLUMN DROP NOT NULL não reescreve dado, só a constraint de schema.
--
-- client_id NULL passa a significar "regra geral" (mesma convenção adotada
-- em core.client_business_rules) — ver core/ddl/resolve_platform_rule.sql
-- para a lógica de prioridade (client_id específico vence sobre NULL).
--
-- Executar UMA vez por ambiente (staging, depois prod). Idempotente: reexecutar
-- contra uma coluna já NULLABLE falha com erro do BigQuery (não é destrutivo,
-- só precisa não ser repetido às cegas).
--
-- Testado em douglas-bq-staging em 2026-09-07: OK, mode passou de REQUIRED
-- para NULLABLE, as 2 linhas existentes preservadas sem alteração de valor.
--
-- Comando de produção (NÃO EXECUTADO — aguardando aprovação do Douglas):
--   bq query --use_legacy_sql=false \
--     "ALTER TABLE \`adframework.core.advertiser_platform_rules\` ALTER COLUMN client_id DROP NOT NULL"

ALTER TABLE `adframework.core.advertiser_platform_rules`
  ALTER COLUMN client_id DROP NOT NULL;
