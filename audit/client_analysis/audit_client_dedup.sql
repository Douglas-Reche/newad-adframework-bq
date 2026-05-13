-- 1. Detecta clientes que compartilham a mesma conta de plataforma (link_value)
-- Se dois newad_client_id têm o mesmo link_value na mesma plataforma = provável duplicata
SELECT
  platform,
  link_value,
  STRING_AGG(newad_client_id ORDER BY newad_client_id) AS clientes_compartilham,
  STRING_AGG(client_name ORDER BY newad_client_id) AS nomes,
  COUNT(*) AS qtd_clientes
FROM `adframework.raw_newadframework.platform_client_links`
WHERE status = 'active'
  AND link_value IS NOT NULL
  AND link_value != ''
GROUP BY platform, link_value
HAVING COUNT(*) > 1
ORDER BY platform, link_value;

-- 2. Volume de entrega real por newad_client_id em todas as plataformas
-- (fonte: newad_operational_daily que é o consolidado de plataformas)
SELECT
  l.newad_client_id,
  l.client_name,
  l.platform,
  l.link_value AS account_plataforma,
  COUNT(DISTINCT o.platform_campaign_id) AS campanhas_com_entrega,
  SUM(o.impressions) AS impressoes_total,
  MIN(o.date) AS primeira_entrega,
  MAX(o.date) AS ultima_entrega
FROM `adframework.raw_newadframework.platform_client_links` l
LEFT JOIN `adframework.share.newad_operational_daily` o
  ON LOWER(o.platform) = LOWER(l.platform)
  AND CAST(o.advertiser_platform_id AS STRING) = CAST(l.link_value AS STRING)
WHERE l.status = 'active'
  AND l.link_value IS NOT NULL
GROUP BY l.newad_client_id, l.client_name, l.platform, l.link_value
ORDER BY l.newad_client_id, l.platform;
