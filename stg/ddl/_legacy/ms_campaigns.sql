-- stg.ms_campaigns (T3)
-- Dimensão de campanhas MediaSmart com ms_client_id resolvido.
-- Grain: 1 linha por campanha (ms_campaign_id único).
-- Fontes:
--   raw.mediasmart_campaigns  → metadata da campanha (WRITE_TRUNCATE)
--   raw.mediasmart_delivery + raw.mediasmart_daily → único source do vínculo controlid → eventid
--
-- LIMITAÇÃO DA API: /api/campaigns NÃO retorna event_id do advertiser.
-- O vínculo campanha → cliente é resolvido via JOIN com tabelas de delivery.
-- Campanhas sem nenhuma entrega registrada terão ms_client_id = NULL.
--
-- Depende de: stg.ms_clients (T1)
-- NÃO substitui nenhuma view existente — view nova.

CREATE OR REPLACE VIEW `adframework.stg.ms_campaigns` AS

WITH campaign_event AS (
  -- extrai o vínculo controlid → eventid a partir das tabelas de entrega
  SELECT DISTINCT controlid AS campaign_id, eventid AS ms_event_id
  FROM `adframework.raw.mediasmart_delivery`
  WHERE controlid IS NOT NULL AND eventid IS NOT NULL

  UNION DISTINCT

  SELECT DISTINCT controlid AS campaign_id, eventid AS ms_event_id
  FROM `adframework.raw.mediasmart_daily`
  WHERE controlid IS NOT NULL AND eventid IS NOT NULL
),

campaigns_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY id
      ORDER BY SAFE_CAST(updated_at AS TIMESTAMP) DESC
    ) AS rn
  FROM `adframework.raw.mediasmart_campaigns`
  WHERE id IS NOT NULL
)

SELECT
  c.id                                                                    AS ms_campaign_id,
  cl.ms_client_id,
  ce.ms_event_id,
  c.name                                                                  AS ms_campaign_name,
  c.state,
  SAFE_CAST(JSON_VALUE(c.schedule, '$.started_at')          AS DATE)     AS started_at,
  SAFE_CAST(JSON_VALUE(c.schedule, '$.finished_at')         AS DATE)     AS finished_at,
  SAFE_CAST(JSON_VALUE(c.schedule, '$.max_daily_cost')      AS FLOAT64)  AS max_daily_cost,
  SAFE_CAST(JSON_VALUE(c.schedule, '$.max_global_cost')     AS FLOAT64)  AS max_global_cost,
  SAFE_CAST(JSON_VALUE(c.schedule, '$.max_global_impressions') AS INT64) AS max_global_impressions,
  SAFE_CAST(c.created_at AS TIMESTAMP)                                   AS created_at,
  SAFE_CAST(c.updated_at AS TIMESTAMP)                                   AS updated_at
FROM campaigns_deduped c
LEFT JOIN campaign_event ce ON ce.campaign_id = c.id
LEFT JOIN `adframework.stg.ms_clients` cl ON cl.ms_event_id = ce.ms_event_id
WHERE c.rn = 1;
