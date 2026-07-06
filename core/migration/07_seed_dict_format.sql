-- core — Migração: Passo 7 — Criar e popular core.dict_format
-- Executar após: core/ddl/dict_format.sql
--
-- Protocolo de mercado (goal_type por formato, confirmado comercial 2026-06-18):
--   Display / Video / Retargeting → CPM  (compra por 1000 impressões)
--   Native / Push                 → CPC  (compra por clique)
--   AppInstall                    → CPI  (compra por instalação — sem fórmula em fact_pacing ainda)
--
-- goal_type é consistente por formato independente de platform (confirmado em gold.fact_io_plan:
-- "Fallback: se não achar match exato platform+formato, tenta só por formato"). Mesmo assim,
-- a tabela tem grain (platform, formato) para permitir exceções futuras por plataforma.
--
-- Formatos por plataforma (o que cada plataforma efetivamente serve):
--   mediasmart : Display, Video, Retargeting, Native
--   mgid       : Push, Native
--   siprocal   : Push
--
-- AppInstall: exclusivo do IO Plan (ainda sem plataforma de entrega ativa). Inserido em
-- mediasmart para garantir resolução via fallback df2 em gold.fact_io_plan.

INSERT INTO `adframework.core.dict_format` (platform, formato, goal_type)
SELECT 'mediasmart', 'Display',     'CPM' UNION ALL
SELECT 'mediasmart', 'Video',       'CPM' UNION ALL
SELECT 'mediasmart', 'Retargeting', 'CPM' UNION ALL
SELECT 'mediasmart', 'Native',      'CPC' UNION ALL
SELECT 'mgid',       'Push',        'CPC' UNION ALL
SELECT 'mgid',       'Native',      'CPC' UNION ALL
SELECT 'siprocal',   'Push',        'CPC' UNION ALL
SELECT 'io_plan',    'AppInstall',  'CPI';
