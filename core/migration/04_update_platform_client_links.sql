-- Atualiza platform_client_links (2026-05-26):
-- 1. Resolve caloi de unresolved → caloi_8ac28140 (pending_confirmation)
-- 2. Insere Bet7k, Lab2Lab, Caloi, Catalise
-- 3. Insere campanhas MGID faltando: Banco Cora, Amigo, Senar, Pardini

-- Resolve caloi no MediaSmart
UPDATE `adframework.core.platform_client_links`
SET
  client_id = 'caloi_8ac28140',
  status    = 'pending_confirmation',
  notes     = 'CALOI — pendente confirmacao comercial; 689K imp no MediaSmart'
WHERE platform = 'mediasmart'
  AND link_type = 'eventid'
  AND link_value = 'newad_brazil-fqpt3ef3uv6gubwadgcrxdjmlum7njnx';

-- Novos mapeamentos
INSERT INTO `adframework.core.platform_client_links`
  (platform, link_type, link_value, client_id, status, notes, created_at)
VALUES
-- Caloi — MGID
  ('mgid','campaignid','12159901','caloi_8ac28140','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12116277','caloi_8ac28140','pending_confirmation',NULL,'2026-05-26'),
-- Bet7k — MGID
  ('mgid','campaignid','12060612','bet7k_b777ab9c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12078841','bet7k_b777ab9c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12083624','bet7k_b777ab9c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12083627','bet7k_b777ab9c','pending_confirmation',NULL,'2026-05-26'),
-- Lab2Lab — MGID
  ('mgid','campaignid','11877910','lab2lab_efb1cb34','pending_confirmation',NULL,'2026-05-26'),
-- Catalise — MGID
  ('mgid','campaignid','12384838','catalise_0b7d18d6','pending_confirmation','1.2M imp mar/2026 — cliente nao confirmado','2026-05-26'),
-- Banco Cora — campanha faltando
  ('mgid','campaignid','12220920','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
-- Amigo — campanhas faltando
  ('mgid','campaignid','12224046','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12246781','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12273460','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12196876','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12196878','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12184059','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12184060','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
-- Senar — campanha push faltando
  ('mgid','campaignid','12419236','senar_105bd174','active',NULL,'2026-05-26'),
-- Pardini — campanhas sem delivery (Rich Media, Anatomia, Podcast, Spotify)
  ('mgid','campaignid','11916496','pardini_60395024','active',NULL,'2026-05-26'),
  ('mgid','campaignid','11933911','pardini_60395024','active',NULL,'2026-05-26'),
  ('mgid','campaignid','11933918','pardini_60395024','active',NULL,'2026-05-26'),
  ('mgid','campaignid','11944803','pardini_60395024','active',NULL,'2026-05-26'),
  ('mgid','campaignid','11969737','pardini_60395024','active',NULL,'2026-05-26'),
  ('mgid','campaignid','11969739','pardini_60395024','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12093310','pardini_60395024','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12093311','pardini_60395024','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12093313','pardini_60395024','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12126341','pardini_60395024','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12126343','pardini_60395024','active',NULL,'2026-05-26');
