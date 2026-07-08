-- gold.pipeline_health
-- View de monitoramento da saúde do pipeline ETL.
-- Atualizada a cada query — sem dados em cache.
-- Uso: Power BI (refresh diário) ou consulta direta no BQ Console.
--
-- Colunas chave:
--   status_ingestao    — ✓/⚠/✗ com texto explicativo
--   dias_sem_dado      — dias desde o último dado na RAW
--   status_linhagem    — ✓/⚠/✗ delta RAW → GOLD (deve ser 0)
--   pct_null_spend     — % de linhas sem dado de custo
--   pct_imp_unattributed — % de impressões sem cliente vinculado
--   links_pendentes    — platform_client_links aguardando confirmação

CREATE OR REPLACE VIEW `adframework.gold.pipeline_health`
OPTIONS (description = 'Monitoramento da saude do pipeline ETL — atualizado a cada query.')
AS

WITH raw_status AS (
  SELECT
    'mediasmart' AS platform,
    'raw.mediasmart_delivery' AS raw_table,
    COUNT(*) AS raw_rows,
    MAX(SAFE_CAST(day AS DATE)) AS raw_max_day,
    DATE_DIFF(CURRENT_DATE('America/Sao_Paulo'), MAX(SAFE_CAST(day AS DATE)), DAY) AS dias_sem_dado,
    COUNTIF(strategyid IS NULL OR strategyid = '') AS raw_null_id_campo,
    COUNTIF(clientrevenue IS NULL OR clientrevenue = '') AS raw_null_spend_campo,
    SUM(SAFE_CAST(impressions AS INT64)) AS raw_impressions,
    SUM(SAFE_CAST(clicks AS INT64)) AS raw_clicks
  FROM `adframework.raw.mediasmart_delivery`

  UNION ALL

  SELECT
    'mgid', 'raw.mgid_delivery',
    COUNT(*),
    MAX(SAFE_CAST(day AS DATE)),
    DATE_DIFF(CURRENT_DATE('America/Sao_Paulo'), MAX(SAFE_CAST(day AS DATE)), DAY),
    COUNTIF(teaserid IS NULL OR teaserid = ''),
    COUNTIF(spent IS NULL OR spent = ''),
    SUM(SAFE_CAST(impressions AS INT64)),
    SUM(SAFE_CAST(clicks AS INT64))
  FROM `adframework.raw.mgid_delivery`

  UNION ALL

  SELECT
    'siprocal', 'raw.siprocal_delivery',
    COUNT(*),
    MAX(SAFE_CAST(day AS DATE)),
    DATE_DIFF(CURRENT_DATE('America/Sao_Paulo'), MAX(SAFE_CAST(day AS DATE)), DAY),
    COUNTIF(campaign_id IS NULL OR campaign_id = ''),
    COUNTIF(creative_type IS NULL OR creative_type = ''),
    SUM(SAFE_CAST(impressions AS INT64)),
    SUM(SAFE_CAST(clicks AS INT64))
  FROM `adframework.raw.siprocal_delivery`
),

gold_status AS (
  SELECT
    platform,
    COUNT(*) AS gold_rows,
    MAX(day) AS gold_max_day,
    DATE_DIFF(CURRENT_DATE('America/Sao_Paulo'), MAX(day), DAY) AS gold_dias_atrasado,
    SUM(impressions) AS gold_impressions,
    SUM(clicks) AS gold_clicks,
    SUM(spend) AS gold_spend,
    COUNTIF(client_id = 'unattributed') AS linhas_unattributed,
    SUM(CASE WHEN client_id = 'unattributed' THEN impressions ELSE 0 END) AS imp_unattributed,
    COUNTIF(spend IS NOT NULL AND spend > 0) AS linhas_com_spend
  FROM `adframework.gold.fact_delivery`
  GROUP BY platform
),

revenue_status AS (
  SELECT
    COUNT(*) AS revenue_rows,
    MAX(SAFE_CAST(day AS DATE)) AS revenue_max_day,
    DATE_DIFF(CURRENT_DATE('America/Sao_Paulo'), MAX(SAFE_CAST(day AS DATE)), DAY) AS revenue_dias_atrasado,
    SUM(SAFE_CAST(clientrevenue AS FLOAT64)) AS revenue_total,
    COUNTIF(eventid IS NULL OR eventid = '') AS null_eventid,
    COUNTIF(revenue_source IS NULL OR revenue_source = '') AS null_revenue_source
  FROM `adframework.raw.mediasmart_revenue`
),

links_status AS (
  SELECT
    platform,
    COUNT(*) AS total_links,
    COUNTIF(status = 'active') AS links_ativos,
    COUNTIF(status = 'pending_confirmation') AS links_pendentes,
    COUNTIF(status = 'unresolved') AS links_unresolved,
    COUNTIF(client_id IS NULL) AS links_sem_cliente
  FROM `adframework.core.platform_client_links`
  GROUP BY platform
)

SELECT
  r.platform,
  r.raw_table,
  r.raw_rows,
  r.raw_max_day,
  r.dias_sem_dado,
  CASE
    WHEN r.dias_sem_dado = 0 THEN '✓ Atualizado hoje'
    WHEN r.dias_sem_dado <= 1 THEN '✓ Atualizado ontem'
    WHEN r.dias_sem_dado <= 3 THEN '⚠ ' || CAST(r.dias_sem_dado AS STRING) || ' dias sem dado'
    ELSE '✗ ' || CAST(r.dias_sem_dado AS STRING) || ' dias sem dado — VERIFICAR'
  END AS status_ingestao,
  r.raw_null_id_campo,
  r.raw_null_spend_campo,
  ROUND(r.raw_null_spend_campo / NULLIF(r.raw_rows, 0) * 100, 1) AS pct_null_spend,
  r.raw_impressions,
  r.raw_clicks,
  g.gold_rows,
  g.gold_max_day,
  g.gold_dias_atrasado,
  g.gold_impressions,
  g.gold_clicks,
  g.gold_spend,
  g.linhas_com_spend,
  g.linhas_unattributed,
  g.imp_unattributed,
  ROUND(g.imp_unattributed / NULLIF(g.gold_impressions, 0) * 100, 2) AS pct_imp_unattributed,
  g.gold_impressions - r.raw_impressions AS delta_impressions_raw_gold,
  g.gold_clicks - r.raw_clicks AS delta_clicks_raw_gold,
  CASE
    WHEN g.gold_impressions = r.raw_impressions THEN '✓ Linhagem OK'
    WHEN ABS(g.gold_impressions - r.raw_impressions) < 1000 THEN '⚠ Diferenca pequena'
    ELSE '✗ DIVERGENCIA: ' || FORMAT('%+d', g.gold_impressions - r.raw_impressions) || ' imp'
  END AS status_linhagem,
  l.total_links,
  l.links_ativos,
  l.links_pendentes,
  l.links_unresolved,
  l.links_sem_cliente,
  CURRENT_TIMESTAMP() AS verificado_em

FROM raw_status r
LEFT JOIN gold_status g ON g.platform = r.platform
LEFT JOIN links_status l ON l.platform = r.platform

UNION ALL

SELECT
  'mediasmart_revenue', 'raw.mediasmart_revenue',
  rev.revenue_rows, rev.revenue_max_day, rev.revenue_dias_atrasado,
  CASE
    WHEN rev.revenue_dias_atrasado <= 1 THEN '✓ Atualizado'
    WHEN rev.revenue_dias_atrasado <= 3 THEN '⚠ ' || CAST(rev.revenue_dias_atrasado AS STRING) || ' dias'
    ELSE '✗ ' || CAST(rev.revenue_dias_atrasado AS STRING) || ' dias — VERIFICAR'
  END,
  rev.null_eventid, rev.null_revenue_source,
  ROUND(rev.null_revenue_source / NULLIF(rev.revenue_rows, 0) * 100, 1),
  CAST(rev.revenue_total AS INT64), 0,
  NULL, NULL, NULL, NULL, NULL, rev.revenue_total, rev.revenue_rows,
  0, 0, 0.0, 0, 0,
  CASE WHEN rev.revenue_total > 0
    THEN '✓ Revenue OK — R$' || CAST(CAST(rev.revenue_total AS INT64) AS STRING)
    ELSE '✗ Sem revenue' END,
  NULL, NULL, NULL, NULL, NULL,
  CURRENT_TIMESTAMP()
FROM revenue_status rev;
