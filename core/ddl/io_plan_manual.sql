-- core.io_plan_manual
-- Seed manual de plano de investimento por flight × cliente.
-- Grain: 1 linha por período de veiculação (flight) por cliente.
-- Fonte: planilhas comerciais no Google Drive, estrutura CLIENT/ANO/MÊS/PLANO/*.xlsx
-- Ingestão: manual via core/migration/06_seed_io_plan_manual.sql
-- VIEW downstream: gold.fact_io_plan (distribui para grain diário via GENERATE_DATE_ARRAY)
--
-- ══════════════════════════════════════════════════════════════════════════════
-- ⚠️  PENDÊNCIAS PARA ALINHAMENTO COM COMERCIAL
-- ══════════════════════════════════════════════════════════════════════════════
--
-- [1] ARQUIVO OFICIAL
--     Quando a pasta PLANO/ tiver mais de um .xlsx (ex: Cora/2026/MAIO/PLANO/),
--     qual arquivo é o vigente? Regra sugerida: arquivo com prefixo "PLANO_OFICIAL_"
--     ou o mais recente por data de modificação. Decidir e comunicar ao time.
--
-- [2] SEPARAÇÃO BRUTO × LÍQUIDO
--     Arquivo original usa taxas de cliente (gross: R$10-12 CPM).
--     Arquivo V3-RAFA usa taxas de mídia (net: R$2-2.25 CPM).
--     Proposta: adicionar colunas VALOR_CLIENTE e VALOR_MIDIA lado a lado em cada
--     linha de estratégia — elimina a necessidade de dois arquivos distintos.
--
-- [3] IDENTIFICAÇÃO DO CLIENTE
--     Planos são criados antes de subir na plataforma, sem ID nativo disponível.
--     Mapeamento atual: nome da pasta → client_id (manual, no pipeline).
--     Para escalar: adicionar campo "CLIENTE_ID" na aba de dados da planilha.
--     (pode ser preenchido pelo comercial após subir a campanha)
--
-- [4] ESTRATÉGIAS SEM PLATAFORMA CONFIRMADA
--     "Vídeo Ads" e "Push APPTARGETING" aparecem nos planos da Cora mas não
--     mapeiam para nenhuma das 3 plataformas do pipeline (mediasmart/mgid/siprocal).
--     Confirmar qual plataforma opera cada uma para habilitar pacing por plataforma.
--
-- [5] FLIGHTS vs MESES CALENDÁRIO
--     Cora usa ciclos 11-10 (ex: 11 Mai → 10 Jun) — diferente de meses calendário.
--     TecPar usa meses calendário (1-30/31).
--     No dashboard, o filtro "Junho 2026" vai pro-ratar corretamente via VIEW diária,
--     mas o comercial precisa saber que "Investimento Projetado para Junho" pode
--     cruzar dois flights da Cora.
--
-- [6] ANOMALIA TECPAR MAIO 2026
--     Plano de Maio do TecPar registra R$60.000 — 5× acima da média mensal (R$10-12K).
--     Confirmar se foi campanha especial, erro de digitação ou revisão do contrato.
-- ══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE TABLE `adframework.core.io_plan_manual`
(
  client_id            STRING   NOT NULL,   -- FK → core.dim_client.client_id
  flight_start         DATE     NOT NULL,   -- início do período de veiculação
  flight_end           DATE     NOT NULL,   -- fim do período de veiculação (inclusive)

  planned_impressions  INT64,               -- impressões totais planejadas (CPM + estimativa CPC/Push)
  planned_clicks       INT64,               -- cliques planejados

  planned_spend_gross  NUMERIC,             -- investimento cobrado ao cliente (taxa cliente)
  planned_spend_net    NUMERIC,             -- custo líquido de mídia (taxa plataforma) — NULL se não disponível

  plan_version         STRING,              -- ex: 'V3-RAFA', 'PLANO-JAN-MAR', 'ANOMALIA-CONFIRMAR'
  source_file          STRING,              -- nome do arquivo .xlsx de origem (rastreabilidade)
  loaded_at            TIMESTAMP            -- data de carga no BQ
)
OPTIONS (
  description = 'Seed manual de plano de veiculação por flight x cliente. Fonte: planilhas comerciais Drive CLIENT/ANO/MES/PLANO/*.xlsx. Ver pendencias de alinhamento no header deste arquivo.'
);
