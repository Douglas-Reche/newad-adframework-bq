-- core.schema_change_log — ALTER (adiciona previous_definition e commit_hash)
-- ---------------------------------------------------------------------------
-- Tabela criada originalmente sem estas 2 colunas (ver histórico completo
-- e semântica de `status`/`tested_env`/etc. no header do CREATE TABLE
-- abaixo, mantido para referência — a fonte de verdade do schema atual é
-- a soma do CREATE + este ALTER). Este arquivo só adiciona as colunas
-- novas necessárias para o rollback do MVP de staging x produção (task
-- "Ambientes Staging x Produção", 2026-08-05) — não recria a tabela (já
-- tem histórico real de execuções do apply_ddl.py).
--
-- previous_definition: a definição (DDL/view_definition/routine_definition)
-- do objeto exatamente como estava ANTES desta execução sobrescrevê-lo —
-- capturada via INFORMATION_SCHEMA logo antes de aplicar. NULL quando o
-- objeto não existia ainda (primeira criação — não há "antes" para
-- restaurar) ou quando a captura falhou silenciosamente (não deve
-- bloquear a aplicação da mudança em si). É o que `--rollback <change_id>`
-- reaplica para desfazer a mudança.
--
-- commit_hash: `git rev-parse HEAD` do repo `newad-adframework-bq` no
-- momento da execução — amarra a linha de auditoria ao commit exato do
-- arquivo .sql aplicado. NULL se o script não estiver rodando dentro de
-- um repo git (erro do `git rev-parse` é ignorado silenciosamente — não é
-- motivo para abortar o deploy).
--
-- ADD COLUMN IF NOT EXISTS é idempotente e não-destrutivo.

ALTER TABLE `adframework.core.schema_change_log`
  ADD COLUMN IF NOT EXISTS previous_definition STRING;

ALTER TABLE `adframework.core.schema_change_log`
  ADD COLUMN IF NOT EXISTS commit_hash STRING;

-- confirmation_method: só relevante quando tested_env='prod' (NULL em test).
-- 'terminal' = humano digitou ao vivo no input() interativo do apply_ddl.py
-- (mecanismo original). 'chat' = confirmado via --confirmed-via-chat, usado
-- só quando o Douglas está sem acesso a terminal (ex: operando por
-- celular/chat) — decisão consciente dele, 2026-08-16, registrada na task
-- Notion MÃE "Regras de Negócio Configuráveis por Cliente". A validação de
-- nome exato do objeto é idêntica nos dois casos — esta coluna só distingue
-- QUEM confirmou fisicamente, não afrouxa a validação em si.
ALTER TABLE `adframework.core.schema_change_log`
  ADD COLUMN IF NOT EXISTS confirmation_method STRING;

-- ============================================================================
-- Referência: CREATE TABLE original (NÃO re-executar — ver core/ddl/
-- schema_change_log.sql no histórico do git para o arquivo completo com o
-- header de contexto original). Mantido aqui só como lembrete do schema
-- base sobre o qual este ALTER incide:
--
-- CREATE TABLE IF NOT EXISTS `adframework.core.schema_change_log` (
--   change_id       STRING    NOT NULL,
--   object_dataset  STRING    NOT NULL,
--   object_name     STRING    NOT NULL,
--   change_summary  STRING,
--   reason          STRING,
--   requested_by    STRING,
--   tested_at       TIMESTAMP NOT NULL,
--   tested_env      STRING    NOT NULL,
--   approved_by     STRING,
--   promoted_at     TIMESTAMP,
--   status          STRING    NOT NULL
-- );
-- ============================================================================
