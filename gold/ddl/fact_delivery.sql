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
--
-- 2026-08-05 -- 4a fonte adicionada (task "Ambientes Staging x Producao"):
-- stg.historical_overrides_delivery (movida de core para stg em
-- 2026-08-06 -- dado normalizado pertence a STG, nao a CORE), para o(s)
-- client_id+dia onde core.resolve_reporting_source() decide 'override' em
-- vez de 'platform'.
-- Generaliza o hardcode que ate aqui so existia em
-- gold.vw_fact_delivery_reporting (client_id = 'banco_cora_fe13d78a' AND
-- day < '2026-07-01' cravado no SQL daquela view) -- agora fact_delivery em
-- si ja resolve isso, e vw_fact_delivery_reporting pode ser simplificada
-- para so fazer SELECT * FROM fact_delivery (nao alterada neste arquivo --
-- fora do escopo desta mudanca, ver relato).
--
-- Sem duplicar nem perder linha: cada uma das 3 fontes reais EXCLUI as
-- linhas de client_id+dia onde resolve_reporting_source() = 'override'
-- (mesmo predicado usado para INCLUIR a linha correspondente no override),
-- entao um client_id+dia especifico so pode vir de uma fonte por vez --
-- nunca das duas ao mesmo tempo, nunca de nenhuma.

CREATE OR REPLACE VIEW `adframework.gold.fact_delivery` AS
WITH unioned AS (
  SELECT date AS day, 'mediasmart' AS platform, client_id, formato, goal_type,
         impressions, clicks,
         (conversions_1 + conversions_2 + conversions_3 + conversions_4 + conversions_5) AS conversions
  FROM `adframework.stg.ms_delivery`
  WHERE `adframework.core.resolve_reporting_source`(client_id, date, CURRENT_DATE()) != 'override'

  UNION ALL

  SELECT date AS day, 'mgid' AS platform, client_id, formato, goal_type,
         impressions, clicks,
         (conversions_interest + conversions_decision + conversions_buy) AS conversions
  FROM `adframework.stg.mg_delivery`
  WHERE `adframework.core.resolve_reporting_source`(client_id, date, CURRENT_DATE()) != 'override'

  UNION ALL

  SELECT date AS day, 'siprocal' AS platform, client_id, formato, goal_type,
         impressions, clicks,
         CAST(NULL AS FLOAT64) AS conversions
  FROM `adframework.stg.sp_delivery`
  WHERE `adframework.core.resolve_reporting_source`(client_id, date, CURRENT_DATE()) != 'override'

  UNION ALL

  SELECT day, platform, client_id, formato, goal_type,
         impressions, clicks, conversions
  FROM `adframework.stg.historical_overrides_delivery`
  WHERE `adframework.core.resolve_reporting_source`(client_id, day, CURRENT_DATE()) = 'override'
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
