-- gold.fact_pacing
-- VIEW principal do dashboard — une planejado (IO Plan) com realizado (entrega das plataformas).
-- Grain: client_id + report_date + category
--
-- Lado planejado: gold.fact_io_plan agregado a (client_id, report_date, category)
--   buy_model: MAX por grupo → CPM vence NULL; 1 linha por (client, date, category), sem duplicar entrega
--   unit_price: MAX por grupo → CPM Projetado e CPC Projetado diretamente desta VIEW
-- Lado realizado: gold.fact_delivery agregado a (client_id, day, category)
-- JOIN: FULL OUTER ON client_id + report_date + category
--
-- Medidas DAX derivadas no Power BI (todas as 28 medidas da auditoria Cora):
--   Investimento Realizado = CALCULATE(SUM(planned_spend_daily), report_date <= TODAY())
--   Investimento Projetado = SUM(planned_spend_daily)
--   Investimento CPM       = CALCULATE(SUM(planned_spend_daily), buy_model = "CPM")
--   Investimento CPC       = CALCULATE(SUM(planned_spend_daily), buy_model = "CPC")
--   Pacing Invest %        = Invest Realizado / Invest Projetado
--   Pacing CPM %           = Impr CPM Realizado / Impr CPM Projetado
--   Pacing CPC %           = Cliques CPC Realizado / Cliques CPC Projetado
--   CTR Realizado          = SUM(actual_clicks) / SUM(actual_impressions)
--   CPM CTR Realizado      = CALCULATE(CTR, buy_model = "CPM")
--   CPM Realizado          = MEDIANX(rows, planned_spend_daily / actual_impressions * 1000) filtrado CPM
--   CPC Realizado          = MEDIANX(rows, planned_spend_daily / actual_clicks) filtrado CPC
--   CPM Projetado          = MAX(unit_price) filtrado buy_model = "CPM"
--   CPC Projetado          = MAX(unit_price) filtrado buy_model = "CPC"

CREATE OR REPLACE VIEW `adframework.gold.fact_pacing` AS

WITH plan AS (
  SELECT
    client_id,
    report_date,
    category,
    -- MAX garante 1 linha por (client, date, category) sem duplicar a delivery.
    -- Quando há linhas CPM + NULL no mesmo dia/categoria, CPM vence (CPM > NULL no MAX).
    MAX(buy_model)                  AS buy_model,
    MAX(unit_price)                 AS unit_price,
    SUM(planned_spend_daily)        AS planned_spend_daily,
    SUM(planned_impressions_daily)  AS planned_impressions_daily,
    SUM(planned_clicks_daily)       AS planned_clicks_daily,
    MIN(flight_start)               AS flight_start,
    MAX(flight_end)                 AS flight_end
  FROM `adframework.gold.fact_io_plan`
  GROUP BY client_id, report_date, category
),

delivery AS (
  SELECT
    client_id,
    day,
    category,
    SUM(impressions)  AS actual_impressions,
    SUM(clicks)       AS actual_clicks
  FROM `adframework.gold.fact_delivery`
  WHERE category IS NOT NULL
  GROUP BY client_id, day, category
)

SELECT
  COALESCE(p.client_id,    d.client_id)   AS client_id,
  COALESCE(p.report_date,  d.day)         AS report_date,
  COALESCE(p.category,     d.category)    AS category,
  -- fallback: quando delivery não tem plano correspondente, derivar buy_model da category
  COALESCE(p.buy_model, CASE COALESCE(p.category, d.category)
    WHEN 'DISPLAY'     THEN 'CPM'
    WHEN 'RETARGETING' THEN 'CPM'
    WHEN 'VIDEO'       THEN 'CPM'
    WHEN 'NATIVE'      THEN 'CPC'
    WHEN 'PUSH'        THEN 'CPC'
    ELSE NULL
  END) AS buy_model,
  p.unit_price,
  p.planned_spend_daily,
  p.planned_impressions_daily,
  p.planned_clicks_daily,
  p.flight_start,
  p.flight_end,
  d.actual_impressions,
  d.actual_clicks
FROM plan p
FULL OUTER JOIN delivery d
  ON  d.client_id  = p.client_id
  AND d.day        = p.report_date
  AND d.category   = p.category;
