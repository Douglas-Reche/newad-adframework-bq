-- core — Migração: Passo 10 — Popular core.strategy_format_map
-- Executar após: core/ddl/strategy_format_map.sql
--
-- Migração 1:1 do CASE WHEN hardcoded que existia em stg/ddl/io_plan.sql
-- (linhas 42-50 antes desta mudança) — os mesmos 6 formatos, na mesma
-- ordem de prioridade implícita (ver comentário de ordem no DDL da tabela e
-- em core/ddl/resolve_strategy_format.sql). effective_from = 2025-01-01
-- (mesma data retroativa usada em core.dict_format/core.advertiser_platform_rules
-- — anterior a raw.ms_delivery, que começa em 2025-01-29).

INSERT INTO `adframework.core.strategy_format_map`
  (keyword, formato, notes, confirmed_by, created_at, effective_from, effective_to)
SELECT 'native',      'Native',      'Migrado do CASE WHEN hardcoded em stg.io_plan.', 'migracao_hardcode', DATE '2026-09-07', DATE '2025-01-01', CAST(NULL AS DATE) UNION ALL
SELECT 'video',       'Video',       'Migrado do CASE WHEN hardcoded em stg.io_plan.', 'migracao_hardcode', DATE '2026-09-07', DATE '2025-01-01', CAST(NULL AS DATE) UNION ALL
SELECT 'vídeo',       'Video',       'Migrado do CASE WHEN hardcoded em stg.io_plan (variante acentuada).', 'migracao_hardcode', DATE '2026-09-07', DATE '2025-01-01', CAST(NULL AS DATE) UNION ALL
SELECT 'retargeting', 'Retargeting', 'Migrado do CASE WHEN hardcoded em stg.io_plan.', 'migracao_hardcode', DATE '2026-09-07', DATE '2025-01-01', CAST(NULL AS DATE) UNION ALL
SELECT 'display',     'Display',     'Migrado do CASE WHEN hardcoded em stg.io_plan.', 'migracao_hardcode', DATE '2026-09-07', DATE '2025-01-01', CAST(NULL AS DATE) UNION ALL
SELECT 'push',        'Push',        'Migrado do CASE WHEN hardcoded em stg.io_plan.', 'migracao_hardcode', DATE '2026-09-07', DATE '2025-01-01', CAST(NULL AS DATE) UNION ALL
SELECT 'appinstall',  'AppInstall',  'Migrado do CASE WHEN hardcoded em stg.io_plan.', 'migracao_hardcode', DATE '2026-09-07', DATE '2025-01-01', CAST(NULL AS DATE) UNION ALL
SELECT 'app install', 'AppInstall',  'Migrado do CASE WHEN hardcoded em stg.io_plan (variante com espaço).', 'migracao_hardcode', DATE '2026-09-07', DATE '2025-01-01', CAST(NULL AS DATE);

-- Pendente de propósito (NÃO incluído neste seed): keyword 'audio'/'áudio' ->
-- 'Áudio'. A estratégia "Áudio Ads" da Casa do Construtor
-- (client_id=casa_construtor_adf15c2c) continua caindo em formato=NULL após
-- esta migração — é o comportamento esperado, vira o primeiro caso real da
-- fila de pendências que o Hub vai mostrar (task separada, hub-frontend).
