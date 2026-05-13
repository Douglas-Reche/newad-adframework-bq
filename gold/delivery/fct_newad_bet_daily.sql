-- MVP Demo: gold.fct_newad_bet_daily
-- Dados Luckbet com identificadores de cliente removidos para uso comercial
-- Vertical: Bet | Nomes de campanha mascarados (usa line_item do IO, não nome da plataforma)
CREATE OR REPLACE VIEW `adframework.gold.fct_newad_bet_daily` AS
WITH delivery_ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY date, platform_campaign_id
      ORDER BY proposal_month DESC
    ) AS _rn
  FROM `adframework.share.io_calc_daily_v4`
  WHERE newad_client_id = 'nwd_luckbet_a485d6bc'
    AND binding_scope = 'campaign'
    AND platform_campaign_id IS NOT NULL
)
SELECT
  'Bet'                                                        AS vertical,
  d.date,
  FORMAT_DATE('%Y-%m', d.date)                                 AS mes,
  FORMAT_DATE('%Y', d.date)                                    AS ano,
  d.platform,
  d.buying_model                                               AS modelo_compra,
  d.line_item                                                  AS estrategia,
  d.creative_type                                              AS formato,
  d.target_device                                              AS device,
  -- Planejamento
  d.start_date                                                 AS inicio_previsto,
  d.end_date                                                   AS fim_previsto,
  CAST(d.budget_total AS NUMERIC)                              AS investimento_previsto,
  CAST(d.planned_budget_daily AS NUMERIC)                      AS budget_diario_previsto,
  CAST(d.planned_budget_to_date AS NUMERIC)                    AS budget_acumulado_previsto,
  CAST(d.deliverable_volume AS NUMERIC)                        AS volume_previsto,
  -- Entrega
  d.impressions                                                AS impressoes,
  d.clicks,
  d.video_start                                                AS video_inicio,
  d.video_completed                                            AS video_conclusao,
  -- Conversões (semântica Bet confirmada por Shiro 29/04/2026)
  d.conversions1                                               AS pageviews,
  d.conversions2                                               AS cadastros,
  d.conversions3                                               AS ftds,
  d.conversions4                                               AS depositos_recorrentes,
  d.conversions5                                               AS inicio_cadastro,
  -- Custo
  CAST(d.realized_revenue_estimated AS NUMERIC)                AS custo_estimado,
  CAST(r.client_revenue AS FLOAT64)                            AS receita_dsp,
  -- KPIs calculados
  ROUND(SAFE_DIVIDE(d.clicks, NULLIF(d.impressions, 0)) * 100, 4)                          AS ctr_pct,
  ROUND(SAFE_DIVIDE(CAST(d.realized_revenue_estimated AS FLOAT64), NULLIF(d.impressions, 0)) * 1000, 2) AS cpm_realizado,
  ROUND(SAFE_DIVIDE(CAST(d.realized_revenue_estimated AS FLOAT64), NULLIF(d.clicks, 0)), 2) AS cpc_realizado,
  ROUND(SAFE_DIVIDE(d.video_completed, NULLIF(d.video_start, 0)) * 100, 2)                 AS taxa_conclusao_video_pct,
  ROUND(SAFE_DIVIDE(d.conversions3, NULLIF(d.conversions2, 0)) * 100, 2)                   AS tx_ftd_cadastro_pct,
  ROUND(SAFE_DIVIDE(d.conversions3, NULLIF(d.clicks, 0)) * 100, 4)                         AS tx_ftd_click_pct,
  ROUND(SAFE_DIVIDE(d.conversions4, NULLIF(d.conversions3, 0)) * 100, 2)                   AS tx_deposito_ftd_pct,
  ROUND(CAST(d.pacing_ratio AS FLOAT64) * 100, 1)                                          AS pacing_pct,
  -- Referências internas (opacas ao usuário final)
  d.io_id,
  d.line_id,
  d.line_number,
  d.proposal_month                                             AS io_mes_referencia,
  CURRENT_TIMESTAMP()                                          AS gold_updated_at
FROM delivery_ranked d
LEFT JOIN `adframework.share.newad_revenue_daily` r
  ON r.date = d.date
  AND LOWER(r.platform) = LOWER(d.platform)
  AND r.platform_campaign_id = d.platform_campaign_id
  AND r.platform_strategy_id = d.platform_strategy_id
WHERE d._rn = 1
