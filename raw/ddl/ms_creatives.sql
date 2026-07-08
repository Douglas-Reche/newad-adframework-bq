-- raw.ms_creatives
-- Cadastro de criativos da MediaSmart (T3), conforme raw_layer_design.md.
-- Grain: 1 linha por associacao criativo<->strategy
-- Fonte CORRETA (corrigida em 2026-06-22): GET /api/campaign/{id} (corpo completo)
-- -> itera strategies[].creatives.campaign_creatives[]. 1 chamada por campanha
-- (14 campanhas conhecidas).
--
-- Fonte ORIGINAL TENTADA E DESCARTADA: GET /api/campaign/{id}/creatives -- retorna
-- um conjunto DIFERENTE de associacoes (direto na campanha, nao na strategy), cujos
-- IDs nao batem com o "creativeid" usado pela API de analytics/entrega. Ver
-- CHANGELOG.md (entrada 2026-06-22, "Gap de join resolvido") para a investigacao completa.
--
-- creative_id gravado com prefixo "cr-" adicionado deliberadamente (f"cr-{cc['id']}")
-- para bater 1:1 com raw.ms_delivery.creative_id sem manipulacao de string na STG.
-- Join confirmado: 729/735 (99,2%) das linhas de ms_delivery.
--
-- Validado contra API real em 2026-06-22. advert_text e call_to_action confirmados
-- ausentes (campo "creative" aninhado da resposta nao os contem) -- nao incluidos,
-- conforme raw_layer_design.md ja previa ("nao existe na API").

CREATE OR REPLACE TABLE `adframework.raw.ms_creatives`
(
  creative_id       STRING,     -- id nativo (associacao criativo-campanha) -- PK
  creative_name     STRING,     -- nome do arquivo/criativo
  campaign_id       STRING,     -- FK para raw.ms_campaigns.campaign_id
  status            STRING,     -- active/inactive
  url               STRING,     -- click_url -- destino do clique
  thumbnail_url     STRING,     -- preview
  creative_type     STRING,     -- image/video/native/rich_media/tag/audio
  width             FLOAT64,    -- pixels (nullable -> FLOAT64, ver feedback_bq_nullable_int_float64)
  height            FLOAT64,    -- pixels
  platform          STRING,     -- 'mediasmart' (injetado)
  raw_ingested_at   TIMESTAMP   -- timestamp da ingestao (injetado)
)
OPTIONS (
  description = 'T3 MS — criativos por campanha. advert_text/call_to_action nao existem na API (confirmado). WRITE_TRUNCATE diario.'
);
