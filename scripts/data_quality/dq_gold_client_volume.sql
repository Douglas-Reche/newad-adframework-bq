-- DQ: Volume de entrega por newad_client_id na gold layer
-- Use para verificar se há clientes com volume inesperadamente alto (duplicação)
-- ou clientes com entrega na raw que não aparecem na gold (IO faltando)

-- 1. Volume na gold (via fct_delivery_daily que já está deduplicada)
SELECT
  'gold.fct_delivery_daily'    AS fonte,
  newad_client_id,
  platform,
  FORMAT_DATE('%Y-%m', date)   AS mes,
  SUM(impressoes)              AS impressoes,
  SUM(clicks)                  AS clicks,
  COUNT(DISTINCT date)         AS dias_com_entrega
FROM `adframework.gold.fct_delivery_daily`
GROUP BY newad_client_id, platform, mes
ORDER BY newad_client_id, mes, platform

-- 2. Para comparar com a raw (roda separadamente):
/*
SELECT
  'share.newad_operational_daily' AS fonte,
  -- newad_client_id não existe na raw; precisa do JOIN com platform_client_links
  l.newad_client_id,
  l.client_name,
  o.platform,
  FORMAT_DATE('%Y-%m', o.date)    AS mes,
  SUM(o.impressions)              AS impressoes,
  SUM(o.clicks)                   AS clicks
FROM `adframework.share.newad_operational_daily` o
JOIN `adframework.raw_newadframework.platform_client_links` l
  ON  LOWER(o.platform)              = LOWER(l.platform)
  AND CAST(o.advertiser_platform_id AS STRING) = CAST(l.link_value AS STRING)
WHERE l.status = 'active'
GROUP BY l.newad_client_id, l.client_name, o.platform, mes
ORDER BY l.newad_client_id, mes, o.platform
*/
