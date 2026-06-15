-- core.platform_client_links — carga inicial
-- Fonte: core/seeds/platform_client_links.csv
-- 118 linhas: 14 MediaSmart (eventid) + 8 Siprocal (advertiser) + 96 MGID (campaignid)
-- Pendências:
--   CALOI (mediasmart eventid newad_brazil-fqpt3ef3uv6gubwadgcrxdjmlum7njnx): cliente não cadastrado
--   Pardini+Ocupacional (eventid newad_brazil-neu83z5jjnkcnrbmwwxjsrzzfwaigdx7): eventid compartilhado
-- Executado em: 2026-05-26

CREATE OR REPLACE TABLE `adframework.core.platform_client_links`
(
  platform    STRING NOT NULL,
  link_type   STRING NOT NULL,
  link_value  STRING NOT NULL,
  client_id   STRING,
  status      STRING NOT NULL,
  notes       STRING,
  created_at  DATE   NOT NULL
)
OPTIONS (
  description = 'Mapeamento de identificadores de plataforma (eventid/campaignid/advertiser) para client_id canonico. Fonte: core/seeds/platform_client_links.csv'
);

INSERT INTO `adframework.core.platform_client_links`
  (platform, link_type, link_value, client_id, status, notes, created_at)
VALUES
-- ─── MEDIASMART — por eventid (nivel advertiser) ─────────────────────────────
  ('mediasmart','eventid','newad_brazil-dzynxhmnrdg2ec0czgdiabqmwvy0qhgj','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  ('mediasmart','eventid','newad_brazil-2ruu4wonoghjuhvngq7lz3xbxcx6mcui','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mediasmart','eventid','newad_brazil-oqdfn8xxlwghvcsezq0ixv7ldvckzozp','amigo_db1c2f0c','pending_confirmation','aguardando confirmacao comercial Amigo vs TecPar','2026-05-26'),
  ('mediasmart','eventid','newad_brazil-nvwu1cidagrt331cqxqvatuyauxjtofa','casa_construtor_adf15c2c','active',NULL,'2026-05-26'),
  ('mediasmart','eventid','newad_brazil-a5e1oyk9h6lgr3mhby5exudluugkiuma','dr_consulta_rj_11040bf9','pending_confirmation','aguardando confirmacao comercial Dr Consulta vs RJ','2026-05-26'),
  ('mediasmart','eventid','newad_brazil-oignlzzcisjwprmdxjlilzc3v1j28fi1','einstein_6b33a588','active',NULL,'2026-05-26'),
  ('mediasmart','eventid','newad_brazil-lmslprwlhne8cbxmbatffxhsspboav5q','aperam_14d1f27e','active',NULL,'2026-05-26'),
  ('mediasmart','eventid','newad_brazil-4au3o3liw2fjujlj6bup6fm05xyqm8a1','stocco_b712c66e','pending_confirmation','aguardando confirmacao comercial Stocco vs Stoquinho','2026-05-26'),
  ('mediasmart','eventid','newad_brazil-1viks0pwxjnv2hafcvkdjajucmfxxlnq','mrv_f19a2136','active',NULL,'2026-05-26'),
  ('mediasmart','eventid','newad_brazil-neu83z5jjnkcnrbmwwxjsrzzfwaigdx7',NULL,'unresolved','eventid compartilhado por Pardini e Ocupacional — aguardando esclarecimento','2026-05-26'),
  ('mediasmart','eventid','newad_brazil-mew7xi9ewnwy7xysvolgxa6whskxtmmu','efi_bank_ee79e91b','active',NULL,'2026-05-26'),
  ('mediasmart','eventid','newad_brazil-0ormcgkknfdbfjkmqeoxbbdwl5xsxng7','fox_lux_55ed8992','active',NULL,'2026-05-26'),
  ('mediasmart','eventid','newad_brazil-plbe1ab6ic2aoxdlelqrb4h5v2xxqtus','dooing_994db77e','active',NULL,'2026-05-26'),
  ('mediasmart','eventid','newad_brazil-fqpt3ef3uv6gubwadgcrxdjmlum7njnx',NULL,'unresolved','CALOI — cliente nao cadastrado em dim_client; adicionar antes de ativar','2026-05-26'),
-- ─── SIPROCAL — por advertiser (UPPER TRIM) ──────────────────────────────────
  ('siprocal','advertiser','LUCKBET','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  ('siprocal','advertiser','AMIGOTECPAR','amigo_db1c2f0c','pending_confirmation','advertiser unico que cobre Amigo+TecPar no Siprocal','2026-05-26'),
  ('siprocal','advertiser','TECPAR','tecpar_edfcc744','pending_confirmation','aguardando confirmacao comercial','2026-05-26'),
  ('siprocal','advertiser','APERAM','aperam_14d1f27e','active',NULL,'2026-05-26'),
  ('siprocal','advertiser','DRCONSULTA','dr_consulta_215378ef','active',NULL,'2026-05-26'),
  ('siprocal','advertiser','BANCOCORA','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('siprocal','advertiser','DOOING','dooing_994db77e','active',NULL,'2026-05-26'),
  ('siprocal','advertiser','PARDINI','pardini_60395024','active',NULL,'2026-05-26'),
-- ─── MGID — por campaignid ───────────────────────────────────────────────────
  -- LuckBet
  ('mgid','campaignid','12220857','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12246847','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12212612','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12273475','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12246849','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12220858','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12333892','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12372673','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12372675','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12212704','luckbet_bea15ebc','active',NULL,'2026-05-26'),
  -- Aperam
  ('mgid','campaignid','12273319','aperam_14d1f27e','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12251786','aperam_14d1f27e','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12301954','aperam_14d1f27e','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12322530','aperam_14d1f27e','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12322529','aperam_14d1f27e','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12251219','aperam_14d1f27e','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12301953','aperam_14d1f27e','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12273321','aperam_14d1f27e','active',NULL,'2026-05-26'),
  -- Dr Consulta
  ('mgid','campaignid','12321171','dr_consulta_215378ef','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12297181','dr_consulta_215378ef','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12321172','dr_consulta_215378ef','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12297182','dr_consulta_215378ef','active',NULL,'2026-05-26'),
  -- Fox Lux
  ('mgid','campaignid','12241369','fox_lux_55ed8992','active',NULL,'2026-05-26'),
  -- Banco Cora
  ('mgid','campaignid','12246818','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12273458','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12298849','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12220919','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12196874','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12326714','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12339730','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12368531','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12400006','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12298848','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12196873','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12246817','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12273457','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12414814','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12414810','banco_cora_fe13d78a','active',NULL,'2026-05-26'),
  -- Efi Bank
  ('mgid','campaignid','12289450','efi_bank_ee79e91b','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12298879','efi_bank_ee79e91b','active',NULL,'2026-05-26'),
  -- Amigo (pending_confirmation)
  ('mgid','campaignid','12246782','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12224045','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12298866','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12273461','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12339736','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12339737','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12298875','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12322545','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12322540','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12196875','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12196877','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12368544','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12368541','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12400002','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12400004','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12322541','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12322542','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12224048','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12246780','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12246779','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12224047','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12339738','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12339734','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12368539','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12368543','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12273462','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12273466','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12298867','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12298872','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12414816','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12414818','amigo_db1c2f0c','pending_confirmation',NULL,'2026-05-26'),
  -- Pardini
  ('mgid','campaignid','12264568','pardini_60395024','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12231080','pardini_60395024','active',NULL,'2026-05-26'),
  -- MRV
  ('mgid','campaignid','12236535','mrv_f19a2136','active',NULL,'2026-05-26'),
  -- Dr Consulta RJ (pending_confirmation)
  ('mgid','campaignid','12333908','dr_consulta_rj_11040bf9','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12374019','dr_consulta_rj_11040bf9','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12333909','dr_consulta_rj_11040bf9','pending_confirmation',NULL,'2026-05-26'),
  -- Stoquinho (pending_confirmation)
  ('mgid','campaignid','12324550','stoquinho_56a6ee2a','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12259284','stoquinho_56a6ee2a','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12281333','stoquinho_56a6ee2a','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12301951','stoquinho_56a6ee2a','pending_confirmation',NULL,'2026-05-26'),
  -- Stocco (pending_confirmation)
  ('mgid','campaignid','12281330','stocco_b712c66e','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12259280','stocco_b712c66e','pending_confirmation',NULL,'2026-05-26'),
  ('mgid','campaignid','12301950','stocco_b712c66e','pending_confirmation',NULL,'2026-05-26'),
  -- Mopar
  ('mgid','campaignid','12298832','mopar_a47949f4','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12276194','mopar_a47949f4','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12276195','mopar_a47949f4','active',NULL,'2026-05-26'),
  -- Patio Medeiros
  ('mgid','campaignid','12334682','patio_medeiros_874a0358','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12366313','patio_medeiros_874a0358','active',NULL,'2026-05-26'),
  -- TownHouses
  ('mgid','campaignid','12224819','townhouses_bc40f009','active',NULL,'2026-05-26'),
  -- Einstein
  ('mgid','campaignid','12374021','einstein_6b33a588','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12400020','einstein_6b33a588','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12416908','einstein_6b33a588','active',NULL,'2026-05-26'),
  ('mgid','campaignid','12414276','einstein_6b33a588','active',NULL,'2026-05-26'),
  -- Dooing
  ('mgid','campaignid','12283455','dooing_994db77e','active',NULL,'2026-05-26'),
  -- Senar
  ('mgid','campaignid','12419235','senar_105bd174','active',NULL,'2026-05-26');
