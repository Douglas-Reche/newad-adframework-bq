-- MVP Demo: gold.fct_newad_fintech_daily
-- Estrutura idêntica à fct_newad_bet_daily, com dados da Cora
-- Colunas de planejamento (budget_diario, pacing) = NULL para meses sem IO formal (pré-mar/26)
CREATE OR REPLACE VIEW `adframework.gold.fct_newad_fintech_daily` AS
WITH cora_campaigns AS (
  SELECT DISTINCT platform_campaign_id, platform
  FROM `adframework.stg.io_lines_v4`
  WHERE newad_client_id = 'nwd_banco-cora_acfae3ab'
    AND platform_campaign_id IS NOT NULL
),
io_context AS (
  SELECT
    platform_campaign_id,
    platform,
    ANY_VALUE(io_id)                     AS io_id,
    ANY_VALUE(line_id)                   AS line_id,
    ANY_VALUE(line_number)               AS line_number,
    ANY_VALUE(proposal_month)            AS io_mes_referencia,
    ANY_VALUE(line_item)                 AS estrategia,
    ANY_VALUE(buying_model)              AS modelo_compra,
    ANY_VALUE(buying_value)              AS buying_value,
    ANY_VALUE(creative_type)             AS formato,
    ANY_VALUE(target_device)             AS device,
    ANY_VALUE(start_date)                AS inicio_previsto,
    ANY_VALUE(end_date)                  AS fim_previsto,
    ANY_VALUE(CAST(budget_total AS NUMERIC))       AS investimento_previsto,
    ANY_VALUE(CAST(deliverable_volume AS NUMERIC)) AS volume_previsto
  FROM `adframework.stg.io_lines_v4`
  WHERE newad_client_id = 'nwd_banco-cora_acfae3ab'
    AND platform_campaign_id IS NOT NULL
  GROUP BY platform_campaign_id, platform
)
SELECT
  'Fintech'                                                    AS vertical,
  p.date,
  FORMAT_DATE('%Y-%m', p.date)                                 AS mes,
  FORMAT_DATE('%Y', p.date)                                    AS ano,
  p.platform,
  COALESCE(io.modelo_compra, 'CPM')                            AS modelo_compra,
  COALESCE(io.estrategia, p.platform_campaign_id)              AS estrategia,
  COALESCE(io.formato, p.creative_type)                        AS formato,
  COALESCE(io.device, p.device_type)                           AS device,
  -- Planejamento (disponível apenas para meses com IO)
  io.inicio_previsto,
  io.fim_previsto,
  io.investimento_previsto,
  CAST(NULL AS NUMERIC)                                        AS budget_diario_previsto,
  CAST(NULL AS NUMERIC)                                        AS budget_acumulado_previsto,
  io.volume_previsto,
  -- Entrega real
  p.impressions                                                AS impressoes,
  p.clicks,
  p.video_start                                                AS video_inicio,
  p.video_completed                                            AS video_conclusao,
  -- Conversões (semântica Fintech — mapeamento comercial pendente)
  p.conversions1                                               AS pageviews,
  p.conversions2                                               AS leads,
  p.conversions3                                               AS contas_abertas,
  p.conversions4                                               AS ativacoes,
  p.conversions5                                               AS inicio_cadastro,
  -- Custo estimado (calculado onde buying_value disponível)
  CASE
    WHEN UPPER(TRIM(COALESCE(io.modelo_compra, ''))) = 'CPM'
      THEN CAST(SAFE_DIVIDE(p.impressions, 1000) * io.buying_value AS NUMERIC)
    WHEN UPPER(TRIM(COALESCE(io.modelo_compra, ''))) = 'CPC'
      THEN CAST(p.clicks * io.buying_value AS NUMERIC)
    ELSE CAST(NULL AS NUMERIC)
  END                                                          AS custo_estimado,
  CAST(r.client_revenue AS FLOAT64)                            AS receita_dsp,
  -- KPIs calculados
  ROUND(SAFE_DIVIDE(p.clicks, NULLIF(p.impressions, 0)) * 100, 4)                              AS ctr_pct,
  ROUND(SAFE_DIVIDE(CAST(r.client_revenue AS FLOAT64), NULLIF(p.impressions, 0)) * 1000, 2)   AS cpm_realizado,
  ROUND(SAFE_DIVIDE(CAST(r.client_revenue AS FLOAT64), NULLIF(p.clicks, 0)), 2)                AS cpc_realizado,
  ROUND(SAFE_DIVIDE(p.video_completed, NULLIF(p.video_start, 0)) * 100, 2)                     AS taxa_conclusao_video_pct,
  ROUND(SAFE_DIVIDE(p.conversions3, NULLIF(p.conversions2, 0)) * 100, 2)                       AS tx_ftd_cadastro_pct,
  ROUND(SAFE_DIVIDE(p.conversions3, NULLIF(p.clicks, 0)) * 100, 4)                             AS tx_ftd_click_pct,
  ROUND(SAFE_DIVIDE(p.conversions4, NULLIF(p.conversions3, 0)) * 100, 2)                       AS tx_deposito_ftd_pct,
  CAST(NULL AS FLOAT64)                                        AS pacing_pct,
  -- Referências IO
  io.io_id,
  io.line_id,
  io.line_number,
  io.io_mes_referencia,
  CURRENT_TIMESTAMP()                                          AS gold_updated_at
FROM `adframework.share.platform_daily_detail` p
INNER JOIN cora_campaigns c
  ON c.platform_campaign_id = p.platform_campaign_id
  AND LOWER(c.platform) = LOWER(p.platform)
LEFT JOIN io_context io
  ON io.platform_campaign_id = p.platform_campaign_id
  AND LOWER(io.platform) = LOWER(p.platform)
LEFT JOIN `adframework.share.newad_revenue_daily` r
  ON r.date = p.date
  AND LOWER(r.platform) = LOWER(p.platform)
  AND r.platform_campaign_id = p.platform_campaign_id
