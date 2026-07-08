-- stg.mg_campaigns
-- T2 STG MGID -- grain: 1 linha por campaign_id.
-- Herda client_id de stg.mg_advertisers via advertiser_name extraido do
-- campaign_name (mesma logica de extracao, ver stg/ddl/mg_advertisers.sql).
--
-- formato: derivado de campaign_type (campo nativo, NAO parse de texto --
-- campaign_name da MGID e texto livre, sem padrao, diferente da MS):
--   push                    -> Push
--   product/content        -> Native
--   rich_media              -> Native (confirmado pelo usuario 2026-06-24 --
--                              variacao de criativo dentro do mesmo modelo CPC)
--   search_feed             -> NULL (baixo volume, avaliar quando aparecer)
--
-- goal_type: join core.dict_format (regra de negocio confirmada pelo
-- comercial em 2026-06-18).

CREATE OR REPLACE VIEW `adframework.stg.mg_campaigns` AS
WITH segments AS (
  SELECT
    campaign_id,
    campaign_name,
    campaign_type,
    status_name,
    start_date,
    end_date,
    SPLIT(REPLACE(campaign_name, '-', '|'), '|') AS parts
  FROM `adframework.raw.mg_campaigns`
),
extracted AS (
  SELECT
    campaign_id,
    campaign_name,
    status_name AS status,
    start_date,
    end_date,
    CASE
      WHEN (
        LOWER(TRIM(parts[OFFSET(0)])) IN ('brand', 'new ad', 'newad', 'push')
        OR REGEXP_CONTAINS(TRIM(parts[OFFSET(0)]), r'^[0-9]+$')
      ) AND ARRAY_LENGTH(parts) > 1
        THEN TRIM(parts[OFFSET(1)])
      ELSE TRIM(parts[OFFSET(0)])
    END AS advertiser_name,
    CASE campaign_type
      WHEN 'push' THEN 'Push'
      WHEN 'product' THEN 'Native'
      WHEN 'content' THEN 'Native'
      WHEN 'rich_media' THEN 'Native'
      ELSE NULL
    END AS formato
  FROM segments
)
SELECT
  e.campaign_id,
  e.advertiser_name,
  ma.client_id,
  e.campaign_name,
  e.formato,
  df.goal_type,
  e.status,
  e.start_date,
  e.end_date
FROM extracted e
LEFT JOIN `adframework.stg.mg_advertisers` ma ON ma.advertiser_name = e.advertiser_name
LEFT JOIN `adframework.core.dict_format` df
  ON UPPER(df.formato) = UPPER(e.formato) AND df.platform = 'mgid';
