-- Para cada platform_campaign_id com entrega real na conta MediaSmart compartilhada,
-- identifica a qual newad_client_id esse campaign está vinculado via IO bindings
-- e qual o volume de entrega

WITH campaigns_in_account AS (
  SELECT DISTINCT
    CAST(platform_campaign_id AS STRING) AS platform_campaign_id,
    SUM(impressions) AS impressoes,
    SUM(clicks) AS clicks,
    MIN(date) AS inicio,
    MAX(date) AS fim
  FROM `adframework.share.newad_operational_daily`
  WHERE advertiser_platform_id = 'newad_brazil-dzynxhmnrdg2ec0czgdiabqmwvy0qhgj'
    AND platform = 'mediasmart'
    AND impressions > 0
  GROUP BY platform_campaign_id
),
io_ownership AS (
  SELECT
    platform_campaign_id,
    STRING_AGG(DISTINCT newad_client_id ORDER BY newad_client_id) AS clientes_vinculados,
    STRING_AGG(DISTINCT io_id ORDER BY io_id) AS ios_vinculados
  FROM `adframework.raw_newadframework.io_line_bindings_v2`
  WHERE platform = 'mediasmart'
    AND platform_campaign_id IS NOT NULL
  GROUP BY platform_campaign_id
)
SELECT
  c.platform_campaign_id,
  COALESCE(io.clientes_vinculados, '** SEM IO **') AS cliente_no_sistema,
  COALESCE(io.ios_vinculados, 'nenhum') AS ios,
  FORMAT('%\'d', c.impressoes) AS impressoes,
  c.inicio,
  c.fim
FROM campaigns_in_account c
LEFT JOIN io_ownership io ON io.platform_campaign_id = c.platform_campaign_id
ORDER BY c.impressoes DESC
