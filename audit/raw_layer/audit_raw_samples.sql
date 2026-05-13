-- Amostras de IDs das tabelas raw principais

-- 1. MediaSmart daily: quais IDs são controlid vs eventid vs strategyid?
SELECT 'mediasmart_daily' AS tabela,
  controlid, eventid, strategyid,
  CAST(impressions AS INT64) AS impressions,
  day
FROM `adframework.raw.mediasmart_daily`
WHERE CAST(impressions AS INT64) > 0
LIMIT 5;

-- 2. MediaSmart operational (sem creative)
SELECT 'mediasmart_operational' AS tabela,
  controlid, eventid, strategyid,
  CAST(impressions AS INT64) AS impressions,
  day
FROM `adframework.raw.mediasmart_daily_operational`
WHERE CAST(impressions AS INT64) > 0
LIMIT 5;

-- 3. MediaSmart revenue: como os IDs aparecem aqui?
SELECT 'mediasmart_revenue' AS tabela,
  controlid, campaign_id, campaignid, eventid, event_id, strategyid, strategy_id,
  clientrevenue, client_revenue, day
FROM `adframework.raw.mediasmart_revenue_daily`
WHERE COALESCE(clientrevenue, client_revenue) IS NOT NULL
LIMIT 5;

-- 4. MGID daily
SELECT 'mgid_daily' AS tabela, campaignid, teaserid,
  CAST(impressions AS INT64) AS impressions, day
FROM `adframework.raw.mgid_daily`
WHERE CAST(impressions AS INT64) > 0
LIMIT 5;

-- 5. Siprocal
SELECT 'siprocal_materialized' AS tabela, campaign_id, advertiser,
  CAST(impressions AS INT64) AS impressions, day
FROM `adframework.raw.siprocal_daily_materialized`
WHERE CAST(impressions AS INT64) > 0
LIMIT 5;
