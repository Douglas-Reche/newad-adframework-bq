-- Intervalo real de datas de cada tabela de fato (raw + share + gold)
-- Rode para saber "qual período existe no BQ" sem abrir dashboard nenhum
-- ATENÇÃO: este script processa dados reais — vai cobrar bytes no BQ

SELECT 'raw.mediasmart_daily'                AS tabela, MIN(CAST(day AS DATE)) AS inicio, MAX(CAST(day AS DATE)) AS fim, COUNT(*) AS linhas FROM `adframework.raw.mediasmart_daily`
UNION ALL
SELECT 'raw.mgid_daily',                                 MIN(CAST(day AS DATE)), MAX(CAST(day AS DATE)), COUNT(*) FROM `adframework.raw.mgid_daily`
UNION ALL
SELECT 'raw.siprocal_daily_materialized',                MIN(CAST(day AS DATE)), MAX(CAST(day AS DATE)), COUNT(*) FROM `adframework.raw.siprocal_daily_materialized`
UNION ALL
SELECT 'share.newad_operational_daily',                  MIN(date), MAX(date), COUNT(*) FROM `adframework.share.newad_operational_daily`
UNION ALL
SELECT 'share.platform_daily_detail',                    MIN(date), MAX(date), COUNT(*) FROM `adframework.share.platform_daily_detail`
UNION ALL
SELECT 'share.io_calc_daily_v4',                         MIN(date), MAX(date), COUNT(*) FROM `adframework.share.io_calc_daily_v4`
UNION ALL
SELECT 'gold.fct_delivery_daily',                        MIN(date), MAX(date), COUNT(*) FROM `adframework.gold.fct_delivery_daily`
UNION ALL
SELECT 'gold.fct_newad_bet_daily',                       MIN(date), MAX(date), COUNT(*) FROM `adframework.gold.fct_newad_bet_daily`
UNION ALL
SELECT 'gold.fct_newad_fintech_daily',                   MIN(date), MAX(date), COUNT(*) FROM `adframework.gold.fct_newad_fintech_daily`
UNION ALL
SELECT 'gold.fct_luckbet_delivery_daily',                MIN(date), MAX(date), COUNT(*) FROM `adframework.gold.fct_luckbet_delivery_daily`
ORDER BY tabela
