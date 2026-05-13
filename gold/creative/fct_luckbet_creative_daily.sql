-- MVP: gold.fct_luckbet_creative_daily
-- Source: gold.fct_creative_daily (já existente) filtrado para conta canônica Luckbet
-- Adiciona mes/ano para slicer Power BI + KPIs calculados
CREATE OR REPLACE VIEW `adframework.gold.fct_luckbet_creative_daily` AS
SELECT
  date,
  FORMAT_DATE('%Y-%m', date) AS mes,
  FORMAT_DATE('%Y', date)    AS ano,
  platform,
  platform_campaign_id,
  strategy_id,
  strategy_name              AS estrategia,
  creative_id,
  creative_type              AS formato_criativo,
  native_size                AS tamanho,
  format                     AS formato,
  device_type                AS device,
  impressions                AS impressoes,
  clicks,
  video_start                AS video_inicio,
  video_25                   AS video_25pct,
  video_50                   AS video_50pct,
  video_75                   AS video_75pct,
  video_completed            AS video_conclusao,
  pageviews,
  cadastros,
  ftds,
  depositos_recorrentes,
  inicio_cadastro,
  ROUND(SAFE_DIVIDE(clicks, NULLIF(impressions, 0)) * 100, 4)                        AS ctr_pct,
  ROUND(SAFE_DIVIDE(video_completed, NULLIF(video_start, 0)) * 100, 2)               AS taxa_conclusao_video_pct,
  ROUND(SAFE_DIVIDE(ftds, NULLIF(cadastros, 0)) * 100, 2)                            AS tx_ftd_cadastro_pct,
  io_id,
  newad_client_id
FROM `adframework.gold.fct_creative_daily`
WHERE newad_client_id = 'nwd_luckbet_a485d6bc'
  AND NOT (
    impressions = 0
    AND clicks = 0
    AND COALESCE(video_start, 0) = 0
    AND COALESCE(video_completed, 0) = 0
    AND COALESCE(pageviews, 0) = 0
  )
