-- =============================================================================
-- RAW LAYER — MIGRAÇÃO: Passo 2 — Drop de tabelas legacy, backups e orphans
-- =============================================================================
-- PRÉ-REQUISITO: 01_create_canonical_tables.sql executado e validado.
-- PRÉ-REQUISITO: Orchestrator (repo Shiro) atualizado para escrever nos novos nomes.
-- ATENÇÃO: Operação irreversível. Confirmar row counts antes de executar.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- VALIDAÇÃO antes do drop (rodar e confirmar que tudo está OK)
-- -----------------------------------------------------------------------------
-- SELECT 'mediasmart_delivery' AS tabela, COUNT(*) AS rows FROM `adframework.raw.mediasmart_delivery`
-- UNION ALL SELECT 'mediasmart_daily_OLD',       COUNT(*) FROM `adframework.raw.mediasmart_daily`
-- UNION ALL SELECT 'mediasmart_revenue',          COUNT(*) FROM `adframework.raw.mediasmart_revenue`
-- UNION ALL SELECT 'mediasmart_revenue_daily_OLD',COUNT(*) FROM `adframework.raw.mediasmart_revenue_daily`
-- UNION ALL SELECT 'mediasmart_bid_supply',        COUNT(*) FROM `adframework.raw.mediasmart_bid_supply`
-- UNION ALL SELECT 'mediasmart_bid_supply_daily_OLD',COUNT(*) FROM `adframework.raw.mediasmart_bid_supply_daily`
-- UNION ALL SELECT 'mgid_delivery',               COUNT(*) FROM `adframework.raw.mgid_delivery`
-- UNION ALL SELECT 'mgid_daily_OLD',              COUNT(*) FROM `adframework.raw.mgid_daily`
-- UNION ALL SELECT 'siprocal_delivery',           COUNT(*) FROM `adframework.raw.siprocal_delivery`
-- UNION ALL SELECT 'siprocal_daily_mat_OLD',      COUNT(*) FROM `adframework.raw.siprocal_daily_materialized`;


-- =============================================================================
-- BLOCO A — Tabelas antigas substituídas pelas canônicas
-- =============================================================================

DROP TABLE IF EXISTS `adframework.raw.mediasmart_daily`;
DROP TABLE IF EXISTS `adframework.raw.mediasmart_revenue_daily`;
DROP TABLE IF EXISTS `adframework.raw.mediasmart_bid_supply_daily`;
DROP TABLE IF EXISTS `adframework.raw.mgid_daily`;
DROP TABLE IF EXISTS `adframework.raw.siprocal_daily_materialized`;


-- =============================================================================
-- BLOCO B — Tabelas vazias (0 rows, nunca usadas)
-- =============================================================================

DROP TABLE IF EXISTS `adframework.raw.siprocal_daily`;
DROP TABLE IF EXISTS `adframework.raw.mediasmart_daily_creative`;
DROP TABLE IF EXISTS `adframework.raw.mediasmart_daily_operational`;


-- =============================================================================
-- BLOCO C — Duplicatas e tabelas descontinuadas
-- =============================================================================

DROP TABLE IF EXISTS `adframework.raw.siprocal_daily_native`;       -- duplicata exata de siprocal_delivery
DROP TABLE IF EXISTS `adframework.raw.mgid_daily_device`;           -- disabled no daily_jobs_target.yaml


-- =============================================================================
-- BLOCO D — Backups e legados de fevereiro/2026 (dados preservados nas canônicas)
-- =============================================================================

DROP TABLE IF EXISTS `adframework.raw.mediasmart_daily_backup_20260227_111821`;
DROP TABLE IF EXISTS `adframework.raw.mediasmart_daily_legacy_20260227_061441`;
DROP TABLE IF EXISTS `adframework.raw.mediasmart_daily_legacy_20260227_065635`;
DROP TABLE IF EXISTS `adframework.raw.mgid_daily_legacy_20260227_061627`;
DROP TABLE IF EXISTS `adframework.raw.mgid_daily_legacy_20260227_065913`;


-- =============================================================================
-- BLOCO E — Datasets orphan completos
-- Estes datasets são espelhos parados em 2026-04-21 sem atualização.
-- raw_newadframework: todas as tabelas com 0 rows (core vive em `core`, não aqui).
-- EXECUTAR VIA gcloud CLI ou console BQ — BigQuery SQL não tem DROP SCHEMA.
-- =============================================================================

-- bq rm -r -f --dataset adframework:raw_mediasmart
-- bq rm -r -f --dataset adframework:raw_mgid
-- bq rm -r -f --dataset adframework:raw_siprocal
-- bq rm -r -f --dataset adframework:raw_newadframework
