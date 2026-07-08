-- raw.mg_teasers
-- Cadastro de teasers (criativos) da MGID (T3), conforme raw_layer_design.md.
-- Grain: 1 linha por teaser
-- Fonte: GET /v1/goodhits/clients/{MGID_CLIENT_ID}/teasers -- conta unica, sem loop de client_ids
-- Ingestao: WRITE_TRUNCATE diario (catalogo)
--
-- Escopo deliberadamente magro: statistics/conversion (KPI snapshot) e category
-- NAO fazem parte deste schema -- raw_layer_design.md nao os inclui no T3 (KPIs
-- ficam nas tabelas de delivery; category e tematica de campanha, nao de criativo,
-- ja coberta em mg_campaigns).
--
-- width/height: MGID nao expoe resolucao por teaser na API -- fixo pelo comercial
-- (1280x720, confirmado em 2026-06-18), injetado na ingestao, nao lido do payload.

CREATE OR REPLACE TABLE `adframework.raw.mg_teasers`
(
  creative_id       STRING,     -- id nativo do teaser -- PK
  creative_name     STRING,     -- title
  campaign_id       STRING,     -- campaignId -- FK para raw.mg_campaigns.campaign_id
  status            STRING,     -- status.code: onModeration/rejected/active/new/goodPerformance/badPerformance/blocked/campaignBlocked
  url               STRING,     -- destino do clique
  thumbnail_url     STRING,     -- imageLink
  advert_text       STRING,     -- advertText
  call_to_action    STRING,     -- callToAction
  width             FLOAT64,    -- fixo 1280 (comercial, nao vem da API)
  height            FLOAT64,    -- fixo 720 (comercial, nao vem da API)
  platform          STRING,     -- 'mgid' (injetado)
  raw_ingested_at   TIMESTAMP   -- timestamp da ingestao (injetado)
)
OPTIONS (
  description = 'T3 MGID — teasers (criativos). width/height fixos pelo comercial, nao vem da API. WRITE_TRUNCATE diario.'
);
