-- gold.fact_delivery
-- Grain: client_id + day + platform + formato + goal_type.
-- goal_type adicionado em 2026-07-07 para aumentar granularidade sem perda de dados
-- (goal_type e 1:1 com formato pelo protocolo core.dict_format, portanto o GROUP BY
-- resulta no mesmo numero de linhas -- nenhuma linha e duplicada nem perdida).
-- UNION das 3 stg.*_delivery, ja com client_id/formato/goal_type resolvidos.
--
-- formato NORMALIZADO aqui (mesma logica de gold.dim_campaign) -- evita
-- "DISPLAY" (MS) vs "Display" (MGID/Siprocal/IO Plan) aparecerem como
-- categorias diferentes num slicer do Power BI.

CREATE OR REPLACE VIEW `adframework.gold.fact_delivery` AS
WITH unioned AS (
  SELECT date AS day, 'mediasmart' AS platform, client_id, formato, goal_type,
         impressions, clicks,
         (conversions_1 + conversions_2 + conversions_3 + conversions_4 + conversions_5) AS conversions
  FROM `adframework.stg.ms_delivery`

  UNION ALL

  SELECT date AS day, 'mgid' AS platform, client_id, formato, goal_type,
         impressions, clicks,
         (conversions_interest + conversions_decision + conversions_buy) AS conversions
  FROM `adframework.stg.mg_delivery`

  UNION ALL

  SELECT date AS day, 'siprocal' AS platform, client_id, formato, goal_type,
         impressions, clicks,
         CAST(NULL AS FLOAT64) AS conversions
  FROM `adframework.stg.sp_delivery`
),
normalized AS (
  SELECT
    day, platform, client_id,
    CASE UPPER(TRANSLATE(formato, 'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç', 'AAAAEEEIIIOOOOUUUCaaaaeeeiiiooooouuuc'))
      WHEN 'DISPLAY' THEN 'Display'
      WHEN 'VIDEO' THEN 'Video'
      WHEN 'RETARGETING' THEN 'Retargeting'
      WHEN 'NATIVE' THEN 'Native'
      WHEN 'PUSH' THEN 'Push'
      WHEN 'APPINSTALL' THEN 'AppInstall'
      ELSE formato
    END AS formato,
    goal_type,
    impressions, clicks, conversions
  FROM unioned
)
SELECT
  day,
  platform,
  client_id,
  formato,
  goal_type,
  SUM(impressions) AS impressions,
  SUM(clicks) AS clicks,
  SUM(conversions) AS conversions
FROM normalized
WHERE client_id IS NOT NULL
GROUP BY day, platform, client_id, formato, goal_type;
