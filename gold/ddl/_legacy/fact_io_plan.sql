-- gold.fact_io_plan
-- VIEW diária de plano de investimento por estratégia × cliente.
-- Grain: 1 linha por (plan_line_id × dia).
--
-- Fonte: stg.io_plan_drive (novo pipeline Drive → RAW → STG → Gold)
-- Substitui: abordagem anterior via core.io_plan_manual (seed manual, descontinuada)
--
-- Distribuição: linear — planned_spend / flight_days por dia.
-- Justificativa: padrão de mercado para planejamento.
--
-- JOIN com gold.fact_delivery:
--   ON p.client_id = d.client_id AND p.report_date = d.day
--   Filtro adicional por category/platform para pacing por canal.
--
-- Uso no Power BI:
--   SUM(planned_spend_daily) sobre filtro de data = investimento projetado para o período.
--   Pacing % = SUM(actual_spend) / SUM(planned_spend_daily) × 100
--   Funciona para qualquer corte: dia, semana, mês, flight, categoria, cliente.
--
-- Nota sobre flights Cora (ciclo 11→10):
--   "Junho 2026" soma dias 01-10 Jun (tail do flight Mai→Jun) + dias 11-30 Jun (head do flight Jun→Jul).
--   O pro-rata é matematicamente correto mas pode surpreender o comercial.
--
-- Limitações conhecidas:
--   planned_impressions = NULL quando nem impressions_cpm nem impressions_est preenchidos no xlsx.
--   planned_clicks = NULL quando coluna de cliques não existe no xlsx.
--   category = 'OTHER' para estratégias com nome não mapeado — revisar com comercial.

CREATE OR REPLACE VIEW `adframework.gold.fact_io_plan` AS

SELECT
  s.client_id,
  d                                                                    AS report_date,
  s.plan_line_id,
  s.drive_folder,
  s.strategy_name,
  s.category,
  s.platform,
  s.spend_type,
  s.buy_model,
  s.flight_start,
  s.flight_end,
  s.flight_days,

  -- ── Valores diários (base para filtros de período no Power BI) ────────────
  ROUND(SAFE_DIVIDE(CAST(s.planned_spend AS FLOAT64),
    s.flight_days), 2)                                                 AS planned_spend_daily,

  ROUND(SAFE_DIVIDE(CAST(s.planned_impressions AS FLOAT64),
    s.flight_days))                                                    AS planned_impressions_daily,

  ROUND(SAFE_DIVIDE(CAST(s.planned_clicks AS FLOAT64),
    s.flight_days))                                                    AS planned_clicks_daily,

  -- ── Totais do flight (para comparação full-flight ou auditoria) ───────────
  s.planned_spend                                                      AS planned_spend_flight,
  s.planned_impressions                                                AS planned_impressions_flight,
  s.planned_clicks                                                     AS planned_clicks_flight,

  s.unit_price,
  s.source_file,
  s.snapshot_at

FROM `adframework.stg.io_plan_drive` s
CROSS JOIN UNNEST(GENERATE_DATE_ARRAY(s.flight_start, s.flight_end)) AS d;
