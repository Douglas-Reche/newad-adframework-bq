-- stg.sp_campaigns
-- T2 STG Siprocal -- grain: 1 linha por campaign_id (= campanha, ja eh a chave).
-- Herda client_id de stg.sp_clients via client_name parseado (mesma logica,
-- ver stg/ddl/sp_clients.sql).
--
-- formato: 'Push' fixo -- decisao ja registrada no raw_layer_design.md
-- (Siprocal so entrega push, sem necessidade de parse).
--
-- goal_type: join core.dict_format (regra de negocio confirmada pelo
-- comercial em 2026-06-18) -- sempre CPC para Siprocal.

CREATE OR REPLACE VIEW `adframework.stg.sp_campaigns` AS
WITH campaigns AS (
  SELECT DISTINCT
    campanha AS campaign_id,
    SPLIT(campanha, '_')[OFFSET(1)] AS client_name
  FROM `adframework.raw.sp_delivery`
)
SELECT
  c.campaign_id,
  c.client_name,
  sc.client_id,
  'Push' AS formato,
  df.goal_type
FROM campaigns c
LEFT JOIN `adframework.stg.sp_clients` sc ON sc.client_name = c.client_name
LEFT JOIN `adframework.core.dict_format` df ON df.formato = 'Push' AND df.platform = 'siprocal';
