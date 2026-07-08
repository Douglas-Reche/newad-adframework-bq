-- raw.mg_campaigns
-- Cadastro de campanhas da MGID (T2).
-- Grain: 1 linha por campaign_id
-- Fonte: GET /v1/goodhits/clients/{MGID_CLIENT_ID}/campaigns — conta unica da NewAd (sem loop de client_ids)
-- Ingestao: WRITE_TRUNCATE diario (catalogo)
--
-- NOTA: nao existe client_id (FK de cliente) nesta tabela. A API MGID nao expoe
-- advertiserName em nenhuma chamada de leitura (testado e confirmado em 2026-06-18,
-- inclusive pedindo o campo explicitamente via fields=[]). O vinculo campaign->cliente
-- e resolvido na STG via core.platform_client_links (campaignid -> client_id) +
-- core.dim_client (client_id -> name, sector). Ver docs/raw_layer_design.md (T1).

CREATE OR REPLACE TABLE `adframework.raw.mg_campaigns`
(
  campaign_id               STRING,     -- id nativo da campanha — PK
  campaign_name             STRING,     -- nome da campanha (texto livre, sem padrao)
  status_id                 INT64,      -- codigo do status (ver tabela em mgid_raw_sketch.md)
  status_name               STRING,     -- descricao do status: paused/ended/active/etc
  status_reason             STRING,     -- razao do status atual (ex: managerPaused)
  category_id               STRING,     -- id da categoria tematica da campanha
  category_name             STRING,     -- nome da categoria (NAO e cliente — ex: "Other services")
  campaign_type             STRING,     -- product/content/push/search_feed
  language_id               INT64,      -- id do idioma da campanha
  start_date                DATE,       -- data de inicio (pode ser null)
  end_date                  DATE,       -- data de termino (null = sem fim definido)
  when_add                  DATE,       -- data de criacao da campanha
  limit_type                STRING,     -- clicks_limits / budget_limits
  daily_limit               FLOAT64,
  overall_limit             FLOAT64,
  split_daily_limit_evenly  BOOL,
  statistics_clicks         INT64,      -- cliques acumulados hoje (no momento da chamada)
  statistics_wages          FLOAT64,    -- gasto acumulado hoje (no momento da chamada)
  utm_source                STRING,
  utm_campaign              STRING,
  utm_medium                STRING,
  utm_custom                STRING,
  platform                  STRING,     -- 'mgid' (injetado)
  raw_ingested_at           TIMESTAMP   -- timestamp da ingestao (injetado)
)
OPTIONS (
  description = 'T2 MGID — cadastro de campanhas. Sem client_id: vinculo de cliente resolvido na STG via core.platform_client_links. WRITE_TRUNCATE diario.'
);
