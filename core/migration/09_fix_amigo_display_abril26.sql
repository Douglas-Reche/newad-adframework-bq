-- raw.ms_campaigns — Migração: Passo 9
-- Insere campanha Amigo encerrada que existia na plataforma MS mas nao foi capturada
-- pelo ETL de campaigns (campanha em estado "ended" nao retornada por GET /api/campaigns).
-- Confirmado pelo usuario 2026-07-07: nome = AMIGO_DISPLAY_700_ABRIL26.
-- Periodo derivado de raw.ms_delivery (2025-11-01 -> 2026-06-01).
-- Impacto: stg.ms_campaigns resolve formato=DISPLAY, goal_type=CPM para
-- 5.72M impressoes de amigo_db1c2f0c que apareciam com NULL formato.

INSERT INTO `adframework.raw.ms_campaigns`
  (campaign_id, campaign_name, client_id, state, started_at, finished_at, platform, raw_ingested_at)
VALUES
  ('54ajzyrqztlnf877at1y3vzmfmidhbvk', 'AMIGO_DISPLAY_700_ABRIL26',
   'newad_brazil-oqdfn8xxlwghvcsezq0ixv7ldvckzozp',
   'ended', '2025-11-01', '2026-06-01', 'mediasmart', '2026-07-07');
