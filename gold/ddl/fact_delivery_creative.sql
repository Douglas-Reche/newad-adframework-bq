-- gold.fact_delivery_creative
-- Grain: day + platform + client_id + formato + goal_type + creative_id
-- View separada de fact_delivery para análise por criativo.
-- NAO alimenta fact_pacing (evita multiplicacao do planned_spend por criativo).
--
-- creative_id: ID estruturado da plataforma (ou string do campo 'criativo' p/ Siprocal).
-- creative_name: nome do catálogo (ms_creatives / mg_teasers). NULL quando
--   o criativo foi deletado/pausado e nao aparece mais na API.
-- creative_label: COALESCE(creative_name, creative_id) — usar no Power BI.
--   MS: ~131/4299 criativos no catálogo (snapshot dos ativos); demais mostram o ID.
--   MGID: cobertura quase total. Siprocal: nome direto da planilha.

CREATE OR REPLACE VIEW `adframework.gold.fact_delivery_creative` AS

-- MediaSmart: JOIN com ms_creatives para trazer nome quando disponível
SELECT
  d.date                                      AS day,
  'mediasmart'                                AS platform,
  d.client_id,
  d.formato,
  d.goal_type,
  d.creative_id,
  ANY_VALUE(c.creative_name)                  AS creative_name,
  COALESCE(ANY_VALUE(c.creative_name), ANY_VALUE(d.creative_id)) AS creative_label,
  SUM(d.impressions)                          AS impressions,
  SUM(d.clicks)                               AS clicks,
  SUM(d.conversions_1 + d.conversions_2 + d.conversions_3 + d.conversions_4 + d.conversions_5) AS conversions
FROM `adframework.stg.ms_delivery` d
LEFT JOIN `adframework.raw.ms_creatives` c USING (creative_id)
WHERE d.client_id IS NOT NULL AND d.creative_id IS NOT NULL
GROUP BY d.date, d.client_id, d.formato, d.goal_type, d.creative_id

UNION ALL

-- MGID: JOIN com mg_teasers para trazer nome
SELECT
  d.date                                      AS day,
  'mgid'                                      AS platform,
  d.client_id,
  d.formato,
  d.goal_type,
  d.creative_id,
  ANY_VALUE(t.creative_name)                  AS creative_name,
  COALESCE(ANY_VALUE(t.creative_name), ANY_VALUE(d.creative_id)) AS creative_label,
  SUM(d.impressions)                          AS impressions,
  SUM(d.clicks)                               AS clicks,
  SUM(d.conversions_interest + d.conversions_decision + d.conversions_buy) AS conversions
FROM `adframework.stg.mg_delivery` d
LEFT JOIN `adframework.raw.mg_teasers` t USING (creative_id)
WHERE d.client_id IS NOT NULL AND d.creative_id IS NOT NULL
GROUP BY d.date, d.client_id, d.formato, d.goal_type, d.creative_id

UNION ALL

-- Siprocal: sem ID estruturado, criativo = nome direto
SELECT
  date                                        AS day,
  'siprocal'                                  AS platform,
  client_id,
  formato,
  goal_type,
  criativo                                    AS creative_id,
  criativo                                    AS creative_name,
  criativo                                    AS creative_label,
  SUM(impressions)                            AS impressions,
  SUM(clicks)                                 AS clicks,
  CAST(0 AS FLOAT64)                          AS conversions
FROM `adframework.stg.sp_delivery`
WHERE client_id IS NOT NULL AND criativo IS NOT NULL
GROUP BY date, client_id, formato, goal_type, criativo;
