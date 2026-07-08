-- gold.fact_delivery_creative
-- Grain: day + platform + client_id + formato + goal_type + creative_id
-- View separada de fact_delivery para análise por criativo.
-- NAO alimenta fact_pacing (evita multiplicacao do planned_spend por criativo).
-- Siprocal nao tem creative_id estruturado — usa campo 'criativo' (nome string).

CREATE OR REPLACE VIEW `adframework.gold.fact_delivery_creative` AS

SELECT
  date                                        AS day,
  'mediasmart'                                AS platform,
  client_id,
  formato,
  goal_type,
  creative_id,
  CAST(NULL AS STRING)                        AS creative_name,
  SUM(impressions)                            AS impressions,
  SUM(clicks)                                 AS clicks,
  SUM(conversions_1 + conversions_2 + conversions_3 + conversions_4 + conversions_5) AS conversions
FROM `adframework.stg.ms_delivery`
WHERE client_id IS NOT NULL AND creative_id IS NOT NULL
GROUP BY date, client_id, formato, goal_type, creative_id

UNION ALL

SELECT
  date                                        AS day,
  'mgid'                                      AS platform,
  client_id,
  formato,
  goal_type,
  creative_id,
  CAST(NULL AS STRING)                        AS creative_name,
  SUM(impressions)                            AS impressions,
  SUM(clicks)                                 AS clicks,
  SUM(conversions_interest + conversions_decision + conversions_buy) AS conversions
FROM `adframework.stg.mg_delivery`
WHERE client_id IS NOT NULL AND creative_id IS NOT NULL
GROUP BY date, client_id, formato, goal_type, creative_id

UNION ALL

SELECT
  date                                        AS day,
  'siprocal'                                  AS platform,
  client_id,
  formato,
  goal_type,
  CAST(NULL AS STRING)                        AS creative_id,
  criativo                                    AS creative_name,
  SUM(impressions)                            AS impressions,
  SUM(clicks)                                 AS clicks,
  CAST(0 AS FLOAT64)                          AS conversions
FROM `adframework.stg.sp_delivery`
WHERE client_id IS NOT NULL
GROUP BY date, client_id, formato, goal_type, criativo;
