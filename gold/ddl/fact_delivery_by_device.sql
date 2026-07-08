-- gold.fact_delivery_by_device
-- Grain: day + platform + client_id + formato + goal_type + device_type + operating_system
-- Somente dados realizados (sem planejado).
-- Fonte: stg.ms_delivery_by_device (MS) + stg.mg_delivery_by_device (MGID).
-- Siprocal nao tem breakdown por device na raw — omitido.
-- operating_system: MGID nao tem esse campo; fica NULL para harmonizar o schema.

CREATE OR REPLACE VIEW `adframework.gold.fact_delivery_by_device` AS

SELECT
  date                                        AS day,
  'mediasmart'                                AS platform,
  client_id,
  formato,
  goal_type,
  device_type,
  operating_system,
  SUM(impressions)                            AS impressions,
  SUM(clicks)                                 AS clicks,
  SUM(conversions_1 + conversions_2 + conversions_3 + conversions_4 + conversions_5) AS conversions
FROM `adframework.stg.ms_delivery_by_device`
WHERE client_id IS NOT NULL
GROUP BY date, client_id, formato, goal_type, device_type, operating_system

UNION ALL

SELECT
  date                                        AS day,
  'mgid'                                      AS platform,
  client_id,
  formato,
  goal_type,
  device_type,
  CAST(NULL AS STRING)                        AS operating_system,
  SUM(impressions)                            AS impressions,
  SUM(clicks)                                 AS clicks,
  SUM(conversions_interest + conversions_decision + conversions_buy) AS conversions
FROM `adframework.stg.mg_delivery_by_device`
WHERE client_id IS NOT NULL
GROUP BY date, client_id, formato, goal_type, device_type;
