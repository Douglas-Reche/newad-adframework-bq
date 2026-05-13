-- DQ: Para cada campaign com entrega real, identifica o client ID via IO binding
-- Detecta campanhas órfãs (sem IO) e campanhas vinculadas a múltiplos clientes
-- Resultado esperado limpo: uma linha por campaign, um único cliente, sem "SEM IO"

WITH campaigns_com_entrega AS (
  SELECT
    platform,
    CAST(platform_campaign_id AS STRING) AS platform_campaign_id,
    SUM(impressions)  AS impressoes,
    SUM(clicks)       AS clicks,
    MIN(date)         AS inicio,
    MAX(date)         AS fim
  FROM `adframework.share.newad_operational_daily`
  WHERE impressions > 0
  GROUP BY platform, platform_campaign_id
),
ownership_via_io AS (
  SELECT
    platform,
    platform_campaign_id,
    STRING_AGG(DISTINCT newad_client_id ORDER BY newad_client_id) AS clientes_vinculados,
    STRING_AGG(DISTINCT io_id           ORDER BY io_id)           AS ios_vinculados,
    COUNT(DISTINCT newad_client_id)                               AS qtd_clientes
  FROM `adframework.raw_newadframework.io_line_bindings_v2`
  WHERE platform_campaign_id IS NOT NULL
  GROUP BY platform, platform_campaign_id
)
SELECT
  c.platform,
  c.platform_campaign_id,
  COALESCE(o.clientes_vinculados, '** SEM IO **')     AS cliente_no_sistema,
  COALESCE(o.ios_vinculados,      'nenhum')            AS ios,
  CASE
    WHEN o.platform_campaign_id IS NULL THEN 'orfao'
    WHEN o.qtd_clientes > 1            THEN 'duplicado'
    ELSE 'ok'
  END AS status_dq,
  FORMAT('%\'d', c.impressoes) AS impressoes,
  c.inicio,
  c.fim
FROM campaigns_com_entrega c
LEFT JOIN ownership_via_io o
  ON  o.platform              = c.platform
  AND o.platform_campaign_id  = c.platform_campaign_id
ORDER BY
  status_dq DESC,   -- orfao e duplicado no topo
  c.impressoes DESC
