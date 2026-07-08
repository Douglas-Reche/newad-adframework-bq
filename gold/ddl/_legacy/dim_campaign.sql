-- gold.dim_campaign
-- Dimensão de campanhas unificada das 3 plataformas.
-- PK: (platform, platform_campaign_id) — 1 linha por campanha.
-- Inclui campo category para JOIN com gold.fact_io_plan via client_id + day + category.
--
-- Lógica de category por plataforma:
--   MediaSmart: via JOIN core.campaign_format_map (mapeamento manual por strategy_id)
--   MGID: constante 'NATIVE' (todos clientes atuais são Native Ads)
--   Siprocal: constante 'PUSH'
--
-- Correções vs DDL anterior (quebrado):
--   MS: stg.mediasmart_delivery (legado) → stg.ms_delivery (T6, pipeline atual)
--   MS: raw.mgid_campaigns (raw) → stg.mgid_campaigns (STG, pipeline atual)
--   MS: LIKE em strategy_name (nomes como 'CPC','CPM') → JOIN com core.campaign_format_map
--   Siprocal: campaign_id (pi_externo, não confiável) → campaign_name (identificador natural)
--
-- Dedup: GROUP BY garante 1 linha por (platform, platform_campaign_id, client_id).
--   ms_strategy_name varia para o mesmo strategy_id (NULL/CPC/CPM) — MAX() escolhe um.
--
-- Limitações conhecidas:
--   category = 'OTHER' para MS strategies não presentes em core.campaign_format_map.
--   TecPar MS strategies não estão no mapa — ver known_issues.md G3.

CREATE OR REPLACE TABLE `adframework.gold.dim_campaign`
OPTIONS (description = 'Dimensao de campanhas unificada — mediasmart/mgid/siprocal com category')
AS

-- MediaSmart — grain: ms_strategy_id; category via core.campaign_format_map
SELECT
  'mediasmart'                                                            AS platform,
  d.ms_strategy_id                                                        AS platform_campaign_id,
  MAX(d.ms_strategy_name)                                                 AS platform_campaign_name,
  d.ms_client_id                                                          AS client_id,
  COALESCE(UPPER(ANY_VALUE(cfm.format)), 'OTHER')                         AS category
FROM `adframework.stg.ms_delivery` d
LEFT JOIN `adframework.core.campaign_format_map` cfm
  ON  cfm.platform             = 'mediasmart'
  AND cfm.platform_campaign_id = d.ms_strategy_id
WHERE d.ms_strategy_id IS NOT NULL
GROUP BY d.ms_strategy_id, d.ms_client_id

UNION ALL

-- MGID — grain: mgid_campaign_id; category = constante NATIVE
SELECT DISTINCT
  'mgid'                                                                  AS platform,
  c.mgid_campaign_id                                                      AS platform_campaign_id,
  c.mgid_campaign_name                                                    AS platform_campaign_name,
  c.mgid_client_id                                                        AS client_id,
  'NATIVE'                                                                AS category
FROM `adframework.stg.mgid_campaigns` c
WHERE c.mgid_campaign_id IS NOT NULL

UNION ALL

-- Siprocal — grain: campaign_name (ex: NEWAD_BANCOCORA_BR_JUN26); category = constante PUSH
SELECT DISTINCT
  'siprocal'                                                              AS platform,
  d.campaign_name                                                         AS platform_campaign_id,
  d.campaign_name                                                         AS platform_campaign_name,
  d.siprocal_client_id                                                    AS client_id,
  'PUSH'                                                                  AS category
FROM `adframework.stg.siprocal_delivery` d
WHERE d.campaign_name IS NOT NULL;
