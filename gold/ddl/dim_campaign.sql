-- gold.dim_campaign
-- Grain: 1 linha por (platform, campaign_id). UNION das 3 stg.*_campaigns --
-- client_id/goal_type ja vem resolvidos da STG, sem re-derivar nada.
--
-- formato NORMALIZADO aqui (Title Case fixo: Display/Video/Retargeting/
-- Native/Push/AppInstall) -- a STG preserva o texto original por design
-- (ms_campaigns.formato vem em CAIXA ALTA do campaign_name, ex: "DISPLAY",
-- "V�DEO" com erro de acento; mg/sp_campaigns ja vem Title Case). Sem
-- normalizar, Power BI trataria "DISPLAY" e "Display" como categorias
-- diferentes num slicer -- confirmado contra dado real 2026-06-24.
--
-- sp_campaigns nao tem campaign_name/status/start_date/end_date na fonte
-- (Siprocal nao expoe essas datas por campanha) -- campaign_name usa
-- campaign_id (ja e descritivo, ex: NEWAD_BANCOCORA_BR_FEV26), demais NULL.

CREATE OR REPLACE VIEW `adframework.gold.dim_campaign` AS
WITH unioned AS (
  SELECT
    'mediasmart' AS platform,
    campaign_id,
    client_id,
    campaign_name,
    formato,
    goal_type,
    status,
    start_date,
    end_date
  FROM `adframework.stg.ms_campaigns`

  UNION ALL

  SELECT
    'mgid' AS platform,
    campaign_id,
    client_id,
    campaign_name,
    formato,
    goal_type,
    status,
    start_date,
    end_date
  FROM `adframework.stg.mg_campaigns`

  UNION ALL

  SELECT
    'siprocal' AS platform,
    campaign_id,
    client_id,
    campaign_id AS campaign_name,
    formato,
    goal_type,
    CAST(NULL AS STRING) AS status,
    CAST(NULL AS DATE) AS start_date,
    CAST(NULL AS DATE) AS end_date
  FROM `adframework.stg.sp_campaigns`
)
SELECT
  platform,
  campaign_id,
  client_id,
  campaign_name,
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
  status,
  start_date,
  end_date
FROM unioned;
