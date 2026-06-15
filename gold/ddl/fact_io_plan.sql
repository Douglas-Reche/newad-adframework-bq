-- gold.fact_io_plan
-- VIEW que expande core.io_plan_manual (grain: flight × cliente)
-- para grain diário (1 linha por dia × cliente) — alinhado com gold.fact_delivery.
--
-- Distribuição: linear (valor_flight ÷ dias_flight por dia).
-- Justificativa: padrão de mercado para planejamento. Versão futura pode ponderar
-- por dia da semana se a equipe de operações fornecer histórico de distribuição.
--
-- JOIN com fact_delivery:
--   ON p.client_id = d.client_id AND p.report_date = d.day
--
-- Uso no Power BI:
--   SUM(planned_impressions_daily) sobre filtro de data = total projetado para o período.
--   Pacing % = SUM(impressions) / SUM(planned_impressions_daily) × 100
--   Funciona para qualquer corte: dia, semana, mês, flight, customizado.
--
-- Flights Cora cruzam meses calendário (ciclo 11→10):
--   Para "Junho 2026" o Power BI vai somar:
--     dias 01-10 Jun → tail do flight "11 Mai→10 Jun"
--     dias 11-30 Jun → head do flight "11 Jun→10 Jul"
--   O resultado pro-rateado é matematicamente correto mas pode surpreender o comercial.
--   ⚠️ COMERCIAL [FLIGHTS]: revisar se o dashboard deve mostrar por flight ou por mês calendário.
--
-- Limitações conhecidas:
--   planned_spend_net  = NULL para TecPar e Cora Jan-Abr (sem arquivo líquido disponível)
--   planned_impressions = NULL para Cora Jan-Mar (impressões não extraídas do arquivo)
--
-- Fonte da verdade: core.io_plan_manual
-- Ver pendências completas: core/ddl/io_plan_manual.sql

CREATE OR REPLACE VIEW `adframework.gold.fact_io_plan` AS

SELECT
  m.client_id,
  d                                                                    AS report_date,
  m.flight_start,
  m.flight_end,
  DATE_DIFF(m.flight_end, m.flight_start, DAY) + 1                    AS flight_days,

  -- ── Valores diários (base para filtros de período no Power BI) ────────────
  ROUND(SAFE_DIVIDE(m.planned_impressions,
    DATE_DIFF(m.flight_end, m.flight_start, DAY) + 1))                AS planned_impressions_daily,

  ROUND(SAFE_DIVIDE(m.planned_clicks,
    DATE_DIFF(m.flight_end, m.flight_start, DAY) + 1))                AS planned_clicks_daily,

  ROUND(SAFE_DIVIDE(CAST(m.planned_spend_gross AS FLOAT64),
    DATE_DIFF(m.flight_end, m.flight_start, DAY) + 1), 2)             AS planned_spend_gross_daily,

  ROUND(SAFE_DIVIDE(CAST(m.planned_spend_net AS FLOAT64),
    DATE_DIFF(m.flight_end, m.flight_start, DAY) + 1), 2)             AS planned_spend_net_daily,

  -- ── Totais do flight (para comparação full-flight ou auditoria) ───────────
  m.planned_impressions                                                AS planned_impressions_flight,
  m.planned_clicks                                                     AS planned_clicks_flight,
  m.planned_spend_gross                                                AS planned_spend_gross_flight,
  m.planned_spend_net                                                  AS planned_spend_net_flight,

  m.plan_version,
  m.source_file

FROM `adframework.core.io_plan_manual` m
CROSS JOIN UNNEST(GENERATE_DATE_ARRAY(m.flight_start, m.flight_end)) AS d;
