-- core.dim_client — Migração: adiciona coluna `import_io_plan`
-- ----------------------------------------------------------------------------
-- Contexto: task Notion "Tela de Gerenciamento de Clientes no Hub" (escopo
-- fechado 2026-09-06/07) — campo NOVO, separado de `status` (ativo/inativo
-- comercial). Controla se `scripts/io_plan/sync_drive.py` deve processar
-- aquele cliente no sync automático do Drive. Motivação: cliente pode estar
-- comercialmente ativo mas não precisar de import automático (ex: sem dado
-- estruturado ainda, ou processo manual por algum motivo) — ou o inverso.
-- São decisões independentes, por isso 2 campos separados, não um só.
--
-- NOTA TÉCNICA IMPORTANTE (não resolvida nesta migração, registrada aqui pro
-- backend decidir quando for a hora): hoje `sync_drive.py` decide quem
-- processar via `CLIENT_MAP`/`PARENT_FOLDER_CLIENTS` HARDCODED no próprio
-- arquivo Python — esta coluna nova é só o CAMPO em dim_client que a tela do
-- Hub agora edita; ela NÃO substitui sozinha essas listas hardcoded no sync.
-- Isso é mudança de arquitetura do lado do pipeline (fora do escopo do
-- hub-frontend) — sinalizado para o backend decidir separadamente.
--
-- DEFAULT TRUE: todo cliente existente continua sendo processado pelo sync
-- exatamente como hoje (comportamento hardcoded atual) até que alguém marque
-- explicitamente `import_io_plan = FALSE` na tela — nenhum cliente para de
-- ser importado só por esta migração ter rodado.
--
-- Idempotente: `ADD COLUMN IF NOT EXISTS` não falha se já existir.
--
-- Testado em douglas-bq-staging em 2026-09-07: OK — coluna adicionada,
-- 36 linhas existentes, backfill de import_io_plan=TRUE aplicado em seguida
-- (UPDATE ... SET import_io_plan = TRUE WHERE import_io_plan IS NULL).
--
-- Comando de produção (NÃO EXECUTADO — aguardando aprovação do Douglas):
--   bq query --use_legacy_sql=false \
--     "ALTER TABLE \`adframework.core.dim_client\` ADD COLUMN IF NOT EXISTS import_io_plan BOOL"
--   bq query --use_legacy_sql=false \
--     "UPDATE \`adframework.core.dim_client\` SET import_io_plan = TRUE WHERE import_io_plan IS NULL"

ALTER TABLE `adframework.core.dim_client`
  ADD COLUMN IF NOT EXISTS import_io_plan BOOL;

UPDATE `adframework.core.dim_client`
  SET import_io_plan = TRUE
  WHERE import_io_plan IS NULL;
