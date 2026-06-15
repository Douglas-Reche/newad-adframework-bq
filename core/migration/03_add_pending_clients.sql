-- Adiciona 4 clientes encontrados na varredura completa das tabelas RAW (2026-05-26)
-- Todos pending_confirmation — questionamento enviado ao time comercial
-- Bet7k, Lab2Lab: sem delivery ainda (campanhas MGID cadastradas, sem dados)
-- Caloi: 689K imp no MediaSmart + 2 campanhas MGID sem delivery
-- Catalise: 1.2M imp no MGID (mar/2026), sem cadastro anterior

INSERT INTO `adframework.core.dim_client`
  (client_id, slug, name, sector, status, created_at, deactivated_at, notes, seed_loaded_at)
VALUES
  ('bet7k_b777ab9c',   'bet7k',   'Bet7k',   'apostas', 'pending_confirmation', '2026-05-26', NULL, 'Aparece em MGID sem delivery. Aguardando confirmacao comercial.', CURRENT_TIMESTAMP()),
  ('lab2lab_efb1cb34', 'lab2lab', 'Lab2Lab', 'unknown', 'pending_confirmation', '2026-05-26', NULL, 'Aparece em MGID sem delivery. Aguardando confirmacao comercial.', CURRENT_TIMESTAMP()),
  ('caloi_8ac28140',   'caloi',   'Caloi',   'unknown', 'pending_confirmation', '2026-05-26', NULL, '689K imp no MediaSmart + 2 campanhas MGID sem delivery. Aguardando confirmacao.', CURRENT_TIMESTAMP()),
  ('catalise_0b7d18d6','catalise','Catalise','unknown', 'pending_confirmation', '2026-05-26', NULL, '1.2M imp no MGID (mar/2026). Nao estava na lista de clientes. Aguardando confirmacao.', CURRENT_TIMESTAMP());
