-- stg.mgid_campaigns (T1 MGID)
-- Dimensão de campanhas MGID com mgid_client_id resolvido.
-- Grain: 1 linha por campanha (mgid_campaign_id único).
-- Fonte: raw.mgid_campaigns (WRITE_APPEND — 79.8× dup; dedup por ROW_NUMBER)
-- Client linkage: core.platform_client_links WHERE platform='mgid' AND link_type='campaignid'
-- NOTA: campos JSON armazenados como Python dict (single-quotes) — REPLACE necessário antes de JSON_VALUE.
-- Sem event_id (conceito exclusivo da MediaSmart); sem updated_at (API MGID não retorna).

CREATE OR REPLACE VIEW `adframework.stg.mgid_campaigns` AS

WITH campaigns_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY id
      ORDER BY whenAdd DESC
    ) AS rn
  FROM `adframework.raw.mgid_campaigns`
  WHERE id IS NOT NULL
),

campaigns_latest AS (
  SELECT
    id,
    name,
    language,
    campaignType,
    REPLACE(REPLACE(status,          "'", '"'), 'None', 'null') AS status_json,
    REPLACE(REPLACE(category,        "'", '"'), 'None', 'null') AS category_json,
    REPLACE(REPLACE(limitsFilter,    "'", '"'), 'None', 'null') AS limits_json,
    REPLACE(REPLACE(trackingOptions, "'", '"'), 'None', 'null') AS tracking_json,
    startDate,
    endDate,
    whenAdd
  FROM campaigns_deduped
  WHERE rn = 1
)

SELECT
  c.id                                                                        AS mgid_campaign_id,
  pcl.client_id                                                               AS mgid_client_id,
  c.name                                                                      AS mgid_campaign_name,
  c.campaignType                                                              AS campaign_type,
  c.language                                                                  AS language_id,
  JSON_VALUE(c.status_json,   '$.name')                                       AS state,
  JSON_VALUE(c.status_json,   '$.reason')                                     AS state_reason,
  SAFE_CAST(JSON_VALUE(c.category_json, '$.id')   AS INT64)                  AS category_id,
  JSON_VALUE(c.category_json, '$.name')                                       AS category_name,
  SAFE_CAST(c.startDate AS DATE)                                              AS started_at,
  SAFE_CAST(c.endDate   AS DATE)                                              AS finished_at,
  SAFE_CAST(JSON_VALUE(c.limits_json, '$.dailyLimit')   AS FLOAT64)          AS max_daily_cost,
  SAFE_CAST(JSON_VALUE(c.limits_json, '$.overallLimit') AS FLOAT64)          AS max_total_cost,
  JSON_VALUE(c.limits_json, '$.limitType')                                    AS limit_type,
  JSON_VALUE(c.tracking_json, '$.utm_source')                                 AS utm_source,
  JSON_VALUE(c.tracking_json, '$.utm_medium')                                 AS utm_medium,
  JSON_VALUE(c.tracking_json, '$.utm_campaign')                               AS utm_campaign,
  SAFE_CAST(c.whenAdd AS DATE)                                                AS created_at
FROM campaigns_latest c
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = c.id;
