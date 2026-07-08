-- stg.ms_strategies (T4)
-- Dimensão de strategies MediaSmart (= line items / ad groups).
-- Grain: 1 linha por strategy_id único.
-- Fonte: campo JSON strategies[] de raw.mediasmart_campaigns (UNNEST).
--
-- Uma strategy é a camada entre campanha e criativo que define bid,
-- targeting, budget allocation e modelo de compra (CPM vs CPC).
-- Na delivery, strategyid identifica qual strategy gerou cada impressão.
--
-- Campos disponíveis hoje (do JSON resumido em campaigns.strategies[]):
--   id, name, parent.id (= campaign_id), state
-- Campos FUTUROS (via job 7 mediasmart_strategies_detail, GET /api/campaign/:strategy_id):
--   bid_cpm, bid_cpc, deal_policy, max_daily_cost, targeting_device, targeting_countries,
--   targeting_os, targeting_daypart — ver docs/mediasmart_stg_design.md T4
--
-- Depende de: raw.mediasmart_campaigns (mesma fonte de T3, independente)
-- NÃO substitui nenhuma view existente — view nova.

CREATE OR REPLACE VIEW `adframework.stg.ms_strategies` AS
SELECT DISTINCT
  JSON_VALUE(s, '$.id')                        AS ms_strategy_id,
  JSON_VALUE(s, '$.parent.id')                 AS ms_campaign_id,
  JSON_VALUE(s, '$.name')                      AS ms_strategy_name,
  JSON_VALUE(s, '$.state')                     AS state,
  SAFE_CAST(c.updated_at AS TIMESTAMP)         AS updated_at
FROM (
  SELECT id, strategies, updated_at,
    ROW_NUMBER() OVER (
      PARTITION BY id
      ORDER BY SAFE_CAST(updated_at AS TIMESTAMP) DESC
    ) AS rn
  FROM `adframework.raw.mediasmart_campaigns`
  WHERE strategies IS NOT NULL
    AND strategies != '[]'
) c,
UNNEST(JSON_QUERY_ARRAY(c.strategies)) AS s
WHERE c.rn = 1
  AND JSON_VALUE(s, '$.id') IS NOT NULL;
