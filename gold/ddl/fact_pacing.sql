-- gold.fact_pacing
-- Grain: client_id + day + formato + platform.
-- Junta planejado (gold.fact_io_plan) com realizado (gold.fact_delivery) por
-- client_id+dia+formato+platform -- NUNCA por campaign_id (o plano nao
-- especifica campanha). FULL OUTER JOIN preserva dias com so plano (futuro)
-- ou so entrega (formato fora do plano).
--
-- client_id NAO remapeado aqui (TecPar/Amigo) -- diferente da versao
-- anterior. Decisao 2026-06-24: esse rollup fica para a hierarquia
-- pai-filho do Power BI (gold.dim_advertiser.parent_client_id), nao em SQL,
-- pra nao hardcodear regra de negocio que pode mudar (TecPar pode ganhar
-- outras sub-marcas no futuro).
--
-- investimento_realizado: calculado aqui porque precisa cruzar unit_price/
-- goal_type (atributos do PLANO) com impressions/clicks (atributos da
-- ENTREGA) linha a linha, na mesma granularidade -- impossivel via
-- relacionamento simples no Power BI (duas fact tables nao se relacionam
-- direto). Formula confirmada pelo usuario 2026-07-08:
--   CPC: clicks realizadas x unit_price
--   CPM: impressions realizadas x unit_price x 1000
-- CPI (AppInstall) e outros goal_type sem formula confirmada -- fica NULL.
--
-- Principio de negocio confirmado (2026-06-16, mantido): cliente nunca ve
-- spend real da plataforma -- "investimento_realizado" aqui e uma metrica
-- nova (estimativa via preco do plano x volume real), nao o spend nativo
-- da API (que nao existe no pipeline -- fora de escopo do rebuild RAW).
--
-- CTE io_agg: pre-agrega fact_io_plan removendo unit_price do grain antes
-- do JOIN. Necessario porque o IO pode ter 2 linhas com mesmo
-- client+dia+formato+platform mas unit_prices diferentes (ex: Cora
-- AppInstall CPA+CPI no mesmo mes). Sem isso o FULL OUTER JOIN gera linhas
-- duplicadas. unit_price: NULL quando ha conflito (goal_type CPI nao tem
-- formula de investimento_realizado de qualquer forma).

CREATE OR REPLACE VIEW `adframework.gold.fact_pacing` AS
WITH io_agg AS (
  SELECT
    client_id,
    report_date,
    formato,
    platform,
    goal_type,
    IF(COUNT(DISTINCT unit_price) = 1, ANY_VALUE(unit_price), NULL) AS unit_price,
    SUM(planned_spend_daily)       AS planned_spend_daily,
    SUM(planned_impressions_daily) AS planned_impressions_daily,
    SUM(planned_clicks_daily)      AS planned_clicks_daily
  FROM `adframework.gold.fact_io_plan`
  GROUP BY client_id, report_date, formato, platform, goal_type
)
SELECT
  COALESCE(p.client_id, d.client_id) AS client_id,
  COALESCE(p.report_date, d.day) AS day,
  COALESCE(p.formato, d.formato) AS formato,
  COALESCE(p.platform, d.platform) AS platform,
  p.planned_spend_daily,
  p.planned_impressions_daily,
  p.planned_clicks_daily,
  p.unit_price,
  COALESCE(p.goal_type, d.goal_type) AS goal_type,
  d.impressions AS realized_impressions,
  d.clicks AS realized_clicks,
  d.conversions AS realized_conversions,
  CASE COALESCE(p.goal_type, d.goal_type)
    WHEN 'CPC' THEN d.clicks * p.unit_price
    WHEN 'CPM' THEN SAFE_DIVIDE(d.impressions * p.unit_price, 1000)
    ELSE NULL
  END AS investimento_realizado
FROM io_agg p
FULL OUTER JOIN `adframework.gold.fact_delivery` d
  ON p.client_id = d.client_id
  AND p.report_date = d.day
  AND UPPER(p.formato) = UPPER(d.formato)
  AND p.platform = d.platform;
