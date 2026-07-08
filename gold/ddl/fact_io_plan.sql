-- gold.fact_io_plan
-- Grain: client_id + report_date + formato + platform.
-- Expande cada linha de stg.io_plan (grain = voo) em 1 linha por dia de
-- calendario dentro do voo, distribuindo planned_spend/impressions/clicks
-- linearmente (/ flight_days).
--
-- platform entra na granularidade (alem de formato) -- CONFIRMADO contra
-- dado real 2026-06-24: client_id+formato+dia sozinho tem 212 dias com 2
-- unit_price/buy_model diferentes coexistindo (ex: TecPar "Push - MGID"
-- R$0,35 vs "Push - App Targeting SIPROCAL" R$0,80, rodando juntos em
-- jan-mar/2026 -- nao e erro, sao 2 estrategias/plataformas genuinamente
-- diferentes).
--
-- platform_resolved: PLATFORM_RULES do sync_drive mapeia Push como 'unknown'
-- por padrao (seguro globalmente). Para clientes onde confirmamos que o Push
-- roda em uma plataforma especifica, a regra fica em
-- core.advertiser_platform_rules (nao hardcoded aqui). Adicionar novas regras
-- naquela tabela + re-executar o DDL dela.
--
-- unit_price: trazido de volta (passthrough) -- usado em gold.fact_pacing
-- pra calcular investimento_realizado (impressions/clicks reais x preco).
--
-- goal_type: regra platform+formato via core.dict_format (igual ao pipeline
-- de entrega). NAO via buy_model da planilha (pouco confiavel).
-- Fallback dict_fallback: quando platform='unknown', busca goal_type so por
-- formato -- mas apenas se o resultado for inequivoco (MIN=MAX, ou seja, o
-- mesmo formato tem o mesmo goal_type em todas as plataformas cadastradas).
-- Se ambiguo, fica NULL. CTE pre-computado para evitar subquery correlacionada.

CREATE OR REPLACE VIEW `adframework.gold.fact_io_plan` AS
WITH expanded AS (
  SELECT
    p.client_id,
    p.formato,
    COALESCE(r.platform_to, p.platform) AS platform,
    p.unit_price,
    day AS report_date,
    p.planned_spend / p.flight_days AS planned_spend_daily,
    SAFE_DIVIDE(p.planned_impressions, p.flight_days) AS planned_impressions_daily,
    SAFE_DIVIDE(p.planned_clicks, p.flight_days) AS planned_clicks_daily
  FROM `adframework.stg.io_plan` p,
  UNNEST(GENERATE_DATE_ARRAY(p.flight_start, p.flight_end)) AS day
  LEFT JOIN `adframework.core.advertiser_platform_rules` r
    ON r.client_id = p.client_id
    AND r.platform_from = p.platform
    AND r.formato = UPPER(p.formato)
  WHERE p.client_id IS NOT NULL
),
dict_fallback AS (
  -- goal_type por formato apenas quando inequivoco entre plataformas.
  -- Window function evita o problema de "aggregation of aggregation" do BQ.
  SELECT DISTINCT formato,
    IF(COUNT(DISTINCT goal_type) OVER (PARTITION BY formato) = 1, goal_type, NULL) AS goal_type
  FROM `adframework.core.dict_format`
),
with_goal AS (
  SELECT
    e.client_id,
    e.report_date,
    e.formato,
    e.platform,
    e.unit_price,
    e.planned_spend_daily,
    e.planned_impressions_daily,
    e.planned_clicks_daily,
    COALESCE(df1.goal_type, df_fb.goal_type) AS goal_type
  FROM expanded e
  LEFT JOIN `adframework.core.dict_format` df1
    ON df1.platform = e.platform AND UPPER(df1.formato) = UPPER(e.formato)
  LEFT JOIN dict_fallback df_fb
    ON UPPER(df_fb.formato) = UPPER(e.formato)
)
SELECT
  client_id,
  report_date,
  formato,
  platform,
  unit_price,
  goal_type,
  SUM(planned_spend_daily)       AS planned_spend_daily,
  SUM(planned_impressions_daily) AS planned_impressions_daily,
  SUM(planned_clicks_daily)      AS planned_clicks_daily
FROM with_goal
GROUP BY client_id, report_date, formato, platform, unit_price, goal_type;
