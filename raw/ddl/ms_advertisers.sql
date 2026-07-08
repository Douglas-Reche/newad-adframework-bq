-- raw.ms_advertisers
-- Cadastro de anunciantes/contas da MediaSmart (T1).
-- Grain: 1 linha por event_id (conta do advertiser)
-- Fonte: GET /api/advertisers — objeto JSON keyed by event_id
-- Ingestão: WRITE_TRUNCATE diário (advertisers raramente mudam)
-- Join com delivery: ms_advertisers.event_id = ms_delivery.event_id

CREATE OR REPLACE TABLE `adframework.raw.ms_advertisers`
(
  event_id          STRING,     -- ID nativo da plataforma: 'newad_brazil-{32chars}'
  id                STRING,     -- sufixo curto (32 chars) — útil para join no STG
  name              STRING,     -- nome do advertiser (cliente final)
  iab_category      STRING,     -- categoria IAB do advertiser
  domain            STRING,     -- domínio do advertiser
  sensitive_content STRING,     -- flag de conteúdo sensível
  platform          STRING,     -- 'mediasmart' (injetado)
  raw_ingested_at   TIMESTAMP   -- timestamp da ingestão (injetado)
)
OPTIONS (
  description = 'T1 MS — cadastro de advertisers. event_id é o client_id nativo. WRITE_TRUNCATE diário.'
);
