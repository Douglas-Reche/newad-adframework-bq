-- stg.mgid_creatives (T2 MGID)
-- Dimensão de criativos MGID com mgid_client_id resolvido via stg.mgid_campaigns.
-- Grain: 1 linha por criativo (mgid_creative_id único).
-- Fonte: raw.mgid_creatives (WRITE_APPEND — ~26× dup; dedup por ROW_NUMBER)
-- NOTA: status e category armazenados como Python dict (single-quotes) — REPLACE necessário.
-- statistics e conversion são totais acumulados — NÃO expor na STG (pertencem às fact tables).
-- Depende de: T1 stg.mgid_campaigns

CREATE OR REPLACE VIEW `adframework.stg.mgid_creatives` AS

WITH creatives_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY id ORDER BY (SELECT NULL)) AS rn
  FROM `adframework.raw.mgid_creatives`
  WHERE id IS NOT NULL
),

creatives_latest AS (
  SELECT
    id, title, advertText, url, imageLink, ad_type,
    callToAction, campaignId, currency,
    REPLACE(REPLACE(status,   "'", '"'), 'None', 'null') AS status_json,
    REPLACE(REPLACE(category, "'", '"'), 'None', 'null') AS category_json
  FROM creatives_deduped
  WHERE rn = 1
)

SELECT
  cr.id                                                               AS mgid_creative_id,
  cr.campaignId                                                       AS mgid_campaign_id,
  c.mgid_client_id,
  cr.title                                                            AS creative_name,
  cr.advertText                                                       AS advert_text,
  cr.url                                                              AS landing_url,
  cr.imageLink                                                        AS image_url,
  cr.ad_type                                                          AS creative_type,
  cr.callToAction                                                     AS call_to_action,
  JSON_VALUE(cr.status_json,   '$.code')                             AS state,
  SAFE_CAST(JSON_VALUE(cr.category_json, '$.id') AS INT64)           AS category_id,
  JSON_VALUE(cr.category_json, '$.name')                             AS category_name,
  JSON_VALUE(cr.category_json, '$.iab_code')                         AS category_iab_code,
  SAFE_CAST(SAFE_CAST(cr.currency AS FLOAT64) AS INT64)              AS currency_id
FROM creatives_latest cr
LEFT JOIN `adframework.stg.mgid_campaigns` c
  ON c.mgid_campaign_id = cr.campaignId;
