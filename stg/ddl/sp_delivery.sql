-- stg.sp_delivery
-- T4 STG Siprocal -- grain: 1 linha por (date, campaign_id, criativo).
--
-- raw.sp_delivery e dump literal (todas colunas STRING, decisao de 22/06) --
-- todo o parse de tipo acontece aqui.
--
-- client_id/formato/goal_type: herdados via join com stg.sp_campaigns (ja
-- resolvidos no T1/T2 -- aqui e so denormalizacao de conveniencia, a pedido
-- do usuario 2026-06-24, nao reabre a resolucao).
--
-- ctr: RECALCULADO (clicks/impressions), NAO usa o ctr da RAW -- decisao ja
-- estabelecida no design original (raw.ctr vem como string BR "1,82%",
-- arredondada em 2 casas). Confirmado contra dado real 2026-06-24: 10/1120
-- linhas tem diferenca de precisao entre o valor da fonte (arredondado) e o
-- recalculado (exato) -- recalculado e mais preciso.

CREATE OR REPLACE VIEW `adframework.stg.sp_delivery` AS
SELECT
  d.coluna_1 AS pi_externo,
  SAFE.PARSE_DATE('%d/%m/%Y', d.data) AS date,
  d.campanha AS campaign_id,
  SPLIT(d.campanha, '_')[OFFSET(1)] AS client_name,
  c.client_id,
  d.criativo,
  c.formato,
  c.goal_type,
  SAFE_CAST(d.impressions AS INT64) AS impressions,
  SAFE_CAST(d.clicks AS INT64) AS clicks,
  SAFE_DIVIDE(SAFE_CAST(d.clicks AS INT64), SAFE_CAST(d.impressions AS INT64)) AS ctr
FROM `adframework.raw.sp_delivery` d
LEFT JOIN `adframework.stg.sp_campaigns` c ON c.campaign_id = d.campanha;
