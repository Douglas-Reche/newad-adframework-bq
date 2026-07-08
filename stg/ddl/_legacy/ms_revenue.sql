-- stg.ms_revenue (T8)
-- Receita MediaSmart com ms_client_id resolvido via campanha.
-- Grain: day + campaign_id + strategy_id + revenue_source
-- Fonte: raw.mediasmart_revenue (histórico, sem eventid direto)
--
-- Como raw.mediasmart_revenue não tem eventid, ms_client_id é resolvido via
-- controlid → stg.ms_campaigns → ms_client_id (1 campanha = 1 cliente).
-- Sem risco de duplicação: ms_campaigns tem 1 row por ms_campaign_id.
--
-- revenue_source normalizado: REGEXP_EXTRACT harmoniza formatos entre tabelas
--   ('event3' → '3', '3' → '3'). Mapeia para conversions_1..5 via stg.ms_campaigns.
--
-- NOTA FUTURA: quando raw.mediasmart_revenue_daily existir (com eventid),
-- adicionar UNION ALL e resolver via caminho direto eventid → ms_clients.
--
-- SUBSTITUI: stg.mediasmart_revenue (legado, sem ms_client_id)
-- DROP stg.mediasmart_revenue SOMENTE após gold.fact_delivery migrar para esta view.
-- Depende de: stg.ms_campaigns (T3) → stg.ms_clients (T1)

CREATE OR REPLACE VIEW `adframework.stg.ms_revenue` AS
SELECT
  SAFE_CAST(r.day AS DATE)                       AS day,
  c.ms_client_id,
  r.controlid                                    AS ms_campaign_id,
  r.strategyid                                   AS ms_strategy_id,
  REGEXP_EXTRACT(r.revenuesource, r'[0-9]+')     AS revenue_source,
  CAST(NULL AS STRING)                           AS conversion_source,
  SAFE_CAST(r.clientrevenue AS FLOAT64)          AS clientrevenue,
  'revenue'                                      AS source_table
FROM `adframework.raw.mediasmart_revenue` r
LEFT JOIN `adframework.stg.ms_campaigns` c ON c.ms_campaign_id = r.controlid
WHERE r.day IS NOT NULL;
