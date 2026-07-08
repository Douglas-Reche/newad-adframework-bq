-- gold.fact_delivery_by_size
-- Grain: day + platform + client_id + formato + goal_type + size
-- Entrega realizada segmentada pela dimensão física do criativo.
--
-- size: CONCAT(width, 'x', height) do catálogo de criativos.
--   Display MS: dimensões IAB reais (300x250, 728x90, 970x250, ...).
--   Video MS/MGID: resolução do vídeo quando disponível (1920x1080, 1280x720, ...).
--   Native, Push, Video sem dimensão (0x0), MGID (thumbnail nativo): 'sem_dimensao'.
--
-- Siprocal: omitido — sem catálogo de criativos com dimensões.
-- MGID: todos os criativos são 1280x720 (thumbnail de artigo nativo), agrupados
--   em 'sem_dimensao' pois não é um formato IAB mensurável.

CREATE OR REPLACE VIEW `adframework.gold.fact_delivery_by_size` AS

-- MediaSmart
SELECT
  d.date                                      AS day,
  'mediasmart'                                AS platform,
  d.client_id,
  d.formato,
  d.goal_type,
  CASE
    WHEN d.formato IN ('NATIVE', 'PUSH')                              THEN 'sem_dimensao'
    WHEN c.width IS NULL OR c.height IS NULL                          THEN 'sem_dimensao'
    WHEN SAFE_CAST(c.width AS FLOAT64) = 0
      OR SAFE_CAST(c.height AS FLOAT64) = 0                          THEN 'sem_dimensao'
    ELSE CONCAT(
      CAST(CAST(SAFE_CAST(c.width  AS FLOAT64) AS INT64) AS STRING),
      'x',
      CAST(CAST(SAFE_CAST(c.height AS FLOAT64) AS INT64) AS STRING)
    )
  END                                         AS size,
  SUM(d.impressions)                          AS impressions,
  SUM(d.clicks)                               AS clicks,
  SUM(d.conversions_1 + d.conversions_2 + d.conversions_3 + d.conversions_4 + d.conversions_5) AS conversions
FROM `adframework.stg.ms_delivery` d
LEFT JOIN `adframework.raw.ms_creatives` c USING (creative_id)
WHERE d.client_id IS NOT NULL AND d.creative_id IS NOT NULL
GROUP BY day, d.client_id, d.formato, d.goal_type, size

UNION ALL

-- MGID: formato nativo — sem dimensão IAB mensurável
SELECT
  d.date                                      AS day,
  'mgid'                                      AS platform,
  d.client_id,
  d.formato,
  d.goal_type,
  'sem_dimensao'                              AS size,
  SUM(d.impressions)                          AS impressions,
  SUM(d.clicks)                               AS clicks,
  SUM(d.conversions_interest + d.conversions_decision + d.conversions_buy) AS conversions
FROM `adframework.stg.mg_delivery` d
WHERE d.client_id IS NOT NULL
GROUP BY day, d.client_id, d.formato, d.goal_type;
