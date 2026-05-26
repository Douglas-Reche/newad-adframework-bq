-- core — Migração: Passo 1 — Criar e popular dim_client a partir do seed
-- Executar após: core/ddl/dim_client.sql
-- Fonte da verdade: core/seeds/clients.csv
-- ATENÇÃO: IDs são imutáveis. Para adicionar cliente: INSERT, nunca UPDATE do client_id.
-- Para os 5 pending_confirmation: atualizar status após confirmação comercial.

INSERT INTO `adframework.core.dim_client`
  (client_id, slug, name, sector, status, created_at, deactivated_at, notes, seed_loaded_at)
VALUES
  -- Confirmados
  ('luckbet_bea15ebc',         'luckbet',          'LuckBet',             'apostas',          'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('banco_cora_fe13d78a',      'banco_cora',        'Banco Cora',          'fintech',          'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('aperam_14d1f27e',          'aperam',            'Aperam',              'industria',        'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('einstein_6b33a588',        'einstein',          'Einstein',            'saude_educacao',   'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('mrv_f19a2136',             'mrv',               'MRV',                 'imobiliario',      'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('fox_lux_55ed8992',         'fox_lux',           'Fox Lux',             'unknown',          'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('efi_bank_ee79e91b',        'efi_bank',          'Efi Bank',            'fintech',          'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('pardini_60395024',         'pardini',           'Pardini',             'saude_labs',       'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('casa_construtor_adf15c2c', 'casa_construtor',   'Casa do Construtor',  'construcao',       'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('dooing_994db77e',          'dooing',            'Dooing',              'imobiliario',      'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('senar_105bd174',           'senar',             'Senar',               'unknown',          'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('mopar_a47949f4',           'mopar',             'Mopar',               'automotivo',       'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('patio_medeiros_874a0358',  'patio_medeiros',    'Patio Medeiros',      'unknown',          'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('townhouses_bc40f009',      'townhouses',        'TownHouses',          'imobiliario',      'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('ocupacional_98c851f5',     'ocupacional',       'Ocupacional',         'saude_ocupacional','active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  ('dr_consulta_215378ef',     'dr_consulta',       'Dr. Consulta',        'saude',            'active',                DATE '2026-05-26', NULL, '',                                    CURRENT_TIMESTAMP()),
  -- Pendentes confirmação comercial
  ('amigo_db1c2f0c',           'amigo',             'Amigo',               'unknown',          'pending_confirmation',  DATE '2026-05-26', NULL, 'aguardando confirmacao comercial',    CURRENT_TIMESTAMP()),
  ('tecpar_edfcc744',          'tecpar',            'TecPar',              'unknown',          'pending_confirmation',  DATE '2026-05-26', NULL, 'aguardando confirmacao comercial',    CURRENT_TIMESTAMP()),
  ('stocco_b712c66e',          'stocco',            'Stocco',              'unknown',          'pending_confirmation',  DATE '2026-05-26', NULL, 'aguardando confirmacao comercial',    CURRENT_TIMESTAMP()),
  ('stoquinho_56a6ee2a',       'stoquinho',         'Stoquinho',           'educacao',         'pending_confirmation',  DATE '2026-05-26', NULL, 'aguardando confirmacao comercial',    CURRENT_TIMESTAMP()),
  ('dr_consulta_rj_11040bf9',  'dr_consulta_rj',    'Dr. Consulta RJ',     'saude',            'pending_confirmation',  DATE '2026-05-26', NULL, 'aguardando confirmacao comercial',    CURRENT_TIMESTAMP());
