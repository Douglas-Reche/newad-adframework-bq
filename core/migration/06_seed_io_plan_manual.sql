-- core.io_plan_manual — carga inicial (Cora + TecPar/Amigo, Jan-Ago 2026)
-- Fonte: planilhas comerciais no Google Drive (estrutura CLIENT/ANO/MÊS/PLANO/)
-- Executado em: 2026-06-09
-- Referência: core/ddl/io_plan_manual.sql (schema + pendências comerciais)
--
-- Colunas com NULL:
--   planned_impressions  → Cora Jan-Mar: arquivo líquido não disponível (apenas totais brutos)
--   planned_spend_net    → TecPar todos os meses + Cora Jan-Abr: arquivo de taxas de mídia não disponível
--
-- Fontes por bloco:
--   Cora Jan-Mar   : Plano NEWAD CORA JAN-MAR 2026.xlsx  (mesmo arquivo para os 3 meses)
--   Cora Abr       : Plano NEWAD CORA ABR 2026 AJUSTADO.xlsx  (versão ajustada R$60K, down de R$70K)
--   Cora Mai-Ago   : Plano_RAFA_NEWAD_CORA_MAIO_JUNHO_JULHO_V3_08_05_26.xlsx  (V3 mais recente, mod 2026-05-29)
--   TecPar Jan-Mar : Plano NEWAD TEC PAR JAN-MAR 2026.xlsx  (mesmo arquivo para os 3 meses)
--   TecPar Abr     : Plano NEWAD TEC PAR ABR 2026.xlsx  (idêntico ao de Junho)
--   TecPar Mai     : Plano NEWAD TEC PAR MAI 2026.xlsx  ⚠️ R$60K — CONFIRMAR COM COMERCIAL
--   TecPar Jun     : Plano NEWAD RAFA_AMIGOCUIABÁ JUNHO 2026_29 05 25.xlsx

CREATE OR REPLACE TABLE `adframework.core.io_plan_manual`
(
  client_id            STRING   NOT NULL,
  flight_start         DATE     NOT NULL,
  flight_end           DATE     NOT NULL,
  planned_impressions  INT64,
  planned_clicks       INT64,
  planned_spend_gross  NUMERIC,
  planned_spend_net    NUMERIC,
  plan_version         STRING,
  source_file          STRING,
  loaded_at            TIMESTAMP
)
OPTIONS (
  description = 'Seed manual de plano de veiculação por flight x cliente. Fonte: planilhas comerciais Drive CLIENT/ANO/MES/PLANO/*.xlsx.'
);

INSERT INTO `adframework.core.io_plan_manual`
  (client_id, flight_start, flight_end,
   planned_impressions, planned_clicks,
   planned_spend_gross, planned_spend_net,
   plan_version, source_file, loaded_at)
VALUES

-- ═══════════════════════════════════════════════════════════════════════════
-- BANCO CORA (banco_cora_fe13d78a)
-- Estrutura de flights: 11→10 do mês seguinte (exceto Jan-Abr que eram mensais)
-- ═══════════════════════════════════════════════════════════════════════════

-- Jan-Mar 2026: plano mensal R$35K, impressões não extraídas do arquivo bruto
-- ⚠️ PENDÊNCIA: ler arquivo Plano NEWAD CORA JAN-MAR para extrair impressões/cliques
('banco_cora_fe13d78a', '2026-01-01', '2026-01-31',
  NULL, NULL, 35000.00, NULL,
  'PLANO-JAN-MAR', 'Plano NEWAD CORA JAN-MAR 2026.xlsx', CURRENT_TIMESTAMP()),

('banco_cora_fe13d78a', '2026-02-01', '2026-02-28',
  NULL, NULL, 35000.00, NULL,
  'PLANO-JAN-MAR', 'Plano NEWAD CORA JAN-MAR 2026.xlsx', CURRENT_TIMESTAMP()),

('banco_cora_fe13d78a', '2026-03-01', '2026-03-31',
  NULL, NULL, 35000.00, NULL,
  'PLANO-JAN-MAR', 'Plano NEWAD CORA JAN-MAR 2026.xlsx', CURRENT_TIMESTAMP()),

-- Abr 2026: plano ajustado (original era R$70K, ajustado para R$60K)
-- ⚠️ COMERCIAL [ARQUIVO_OFICIAL]: pasta Abr tem arquivo original + AJUSTADO. Usando AJUSTADO (R$60K).
('banco_cora_fe13d78a', '2026-04-01', '2026-04-30',
  4248274, 14162, 60000.00, NULL,
  'PLANO-ABR-AJUSTADO', 'Plano NEWAD CORA ABR AJUSTADO 2026.xlsx', CURRENT_TIMESTAMP()),

-- Flights Mai-Ago 2026: ciclo 11-10, fonte V3-RAFA (taxa plataforma + taxa cliente de arquivo separado)
-- planned_impressions = impressões CPM + estimativa CPC/Push (total do TOTAL MENSAL no xlsx)
-- planned_spend_gross = arquivo original (taxa cliente R$10-12 CPM)
-- planned_spend_net   = arquivo V3-RAFA (taxa mídia R$2-2.25 CPM)

-- Flight 1: 1 Mai → 10 Mai (10 dias)
('banco_cora_fe13d78a', '2026-05-01', '2026-05-10',
  914789, 3020, 12500.00, 2365.00,
  'V3-RAFA', 'Plano_RAFA_NEWAD_CORA_MAIO_JUNHO_JULHO_V3_08_05_26.xlsx', CURRENT_TIMESTAMP()),

-- Flight 2: 11 Mai → 10 Jun (31 dias) — FLIGHT ATIVO EM 2026-06-09
('banco_cora_fe13d78a', '2026-05-11', '2026-06-10',
  6030115, 18496, 78750.00, 14700.00,
  'V3-RAFA', 'Plano_RAFA_NEWAD_CORA_MAIO_JUNHO_JULHO_V3_08_05_26.xlsx', CURRENT_TIMESTAMP()),

-- Flight 3: 11 Jun → 10 Jul (30 dias)
('banco_cora_fe13d78a', '2026-06-11', '2026-07-10',
  2473157, 7786, 31500.00, 6100.00,
  'V3-RAFA', 'Plano_RAFA_NEWAD_CORA_MAIO_JUNHO_JULHO_V3_08_05_26.xlsx', CURRENT_TIMESTAMP()),

-- Flight 4: 11 Jul → 10 Ago (31 dias)
('banco_cora_fe13d78a', '2026-07-11', '2026-08-10',
  3631958, 11098, 47250.00, 8850.00,
  'V3-RAFA', 'Plano_RAFA_NEWAD_CORA_MAIO_JUNHO_JULHO_V3_08_05_26.xlsx', CURRENT_TIMESTAMP()),

-- Flight 5: 11 Ago → 31 Ago (21 dias)
('banco_cora_fe13d78a', '2026-08-11', '2026-08-31',
  914789, 3020, 12500.00, 2365.00,
  'V3-RAFA', 'Plano_RAFA_NEWAD_CORA_MAIO_JUNHO_JULHO_V3_08_05_26.xlsx', CURRENT_TIMESTAMP()),

-- ═══════════════════════════════════════════════════════════════════════════
-- TECPAR / AMIGO (amigo_db1c2f0c)
-- Estrutura mensal (mês calendário, não ciclo 11-10 como Cora)
-- planned_spend_net = NULL (arquivos disponíveis usam apenas taxa de cliente)
-- planned_impressions = total do TOTAL MENSAL do xlsx (CPM + push estimado)
-- ⚠️ COMERCIAL [PLANO_LIQUIDO]: sem arquivo separado com taxas de mídia para TecPar.
--    Para habilitar custo líquido, pedir ao comercial planilha com coluna VALOR_MIDIA.
-- ═══════════════════════════════════════════════════════════════════════════

-- Jan 2026
('amigo_db1c2f0c', '2026-01-01', '2026-01-31',
  3861607, 18089, 10450.00, NULL,
  'STANDARD', 'Plano NEWAD TEC PAR JAN 2026.xlsx', CURRENT_TIMESTAMP()),

-- Fev 2026 (arquivo idêntico ao de Janeiro)
('amigo_db1c2f0c', '2026-02-01', '2026-02-28',
  3861607, 18089, 10450.00, NULL,
  'STANDARD', 'Plano NEWAD TEC PAR FEV 2026.xlsx', CURRENT_TIMESTAMP()),

-- Mar 2026 (inclui Push MGID separado no arquivo)
('amigo_db1c2f0c', '2026-03-01', '2026-03-31',
  3861607, 18089, 10450.00, NULL,
  'STANDARD', 'Plano NEWAD TEC PAR MAR 2026.xlsx', CURRENT_TIMESTAMP()),

-- Abr 2026 (arquivo idêntico ao de Junho)
('amigo_db1c2f0c', '2026-04-01', '2026-04-30',
  3968065, 18114, 12700.00, NULL,
  'STANDARD', 'Plano NEWAD TEC PAR ABR 2026.xlsx', CURRENT_TIMESTAMP()),

-- Mai 2026 — ⚠️ ANOMALIA: R$60.000 = 5× acima da média mensal (R$10-12K).
-- CPM rate no arquivo era R$12 (taxa cliente), vs R$2-3 nos outros meses.
-- ⚠️ COMERCIAL [ANOMALIA]: confirmar se foi campanha especial, revisão de contrato
--    ou erro de digitação antes de usar este valor em projeções financeiras.
('amigo_db1c2f0c', '2026-05-01', '2026-05-31',
  3861607, 16920, 60000.00, NULL,
  'ANOMALIA-CONFIRMAR', 'Plano NEWAD TEC PAR MAI 2026.xlsx', CURRENT_TIMESTAMP()),

-- Jun 2026 — FLIGHT ATIVO EM 2026-06-09
('amigo_db1c2f0c', '2026-06-01', '2026-06-30',
  3968065, 18114, 12700.00, NULL,
  'STANDARD', 'Plano NEWAD RAFA_AMIGOCUIABA JUNHO 2026_29 05 25.xlsx', CURRENT_TIMESTAMP());
