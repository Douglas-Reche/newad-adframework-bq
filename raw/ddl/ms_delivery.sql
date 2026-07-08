-- raw.ms_delivery
-- Fato de entrega diaria da MediaSmart (T4), conforme raw_layer_design.md.
-- Grain: dia + client + campanha + creative
-- Fonte: GET /api/analytics/custom-report
--   drilldown = day,eventid,controlid,creativeid
--   kpis = impressions,clicks,events1,events2,events3,events4,events5,
--          videostart,videofirstquartile,videomidpoint,videothirdquartile,videocomplete
-- Ingestao: diaria incremental
--
-- NOTA DE JOIN (descoberta em 2026-06-22, RESOLVIDA na mesma sessao):
-- creative_id aqui vem do campo "creativeid" da API ("Campaign Creative ID",
-- formato "cr-xxxxx..."). Inicialmente nao batia com raw.ms_creatives.creative_id
-- porque o T3 buscava de um endpoint errado (/api/campaign/{id}/creatives).
-- CORRIGIDO: T3 agora busca de campaign.strategies[].creatives.campaign_creatives[]
-- (mesmo namespace de ID usado pela entrega) e grava o prefixo "cr-" no creative_id
-- armazenado, para join direto. Join confirmado: 729/735 (99,2%). Ver CHANGELOG.md
-- (entrada 2026-06-22, "Gap de join resolvido") e raw/ddl/ms_creatives.sql.
--
-- ctr: NAO gravado aqui -- e derivado, sempre recalculado no STG (SAFE_DIVIDE).

CREATE OR REPLACE TABLE `adframework.raw.ms_delivery`
(
  date              DATE,       -- "Day"
  client_id         STRING,     -- "Event ID" -- FK para raw.ms_advertisers.event_id
  campaign_id       STRING,     -- "Campaign ID" (controlid) -- FK para raw.ms_campaigns.campaign_id
  creative_id       STRING,     -- "Creative ID" (creativeid) -- gap de join, ver nota acima
  impressions       FLOAT64,
  clicks            FLOAT64,
  conversions_1     FLOAT64,
  conversions_2     FLOAT64,
  conversions_3     FLOAT64,
  conversions_4     FLOAT64,
  conversions_5     FLOAT64,
  video_start       FLOAT64,
  video_25          FLOAT64,    -- "Video 25% viewed"
  video_50          FLOAT64,    -- "Video 50% viewed"
  video_75          FLOAT64,    -- "Video 75% viewed"
  video_complete    FLOAT64,    -- "Video completion"
  platform          STRING,     -- 'mediasmart' (injetado)
  raw_ingested_at   TIMESTAMP   -- timestamp da ingestao (injetado)
)
PARTITION BY date
OPTIONS (
  description = 'T4 MS — fato de entrega diaria. creative_id NAO faz join com ms_creatives (gap conhecido). Particionado por date, incremental.'
);
