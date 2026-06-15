-- raw.siprocal_delivery
-- Entrega diária da Siprocal. Fonte de verdade para dados Siprocal no pipeline.
-- Grain: day + advertiser + campaign_id + creative_type + creative
--
-- PIPELINE DE INGESTÃO (atual — desde 2026-06-15):
--   Google Sheet raw_siprocal (aba raw_daily!A:G)
--   → SiproCalConnector (src/connectors/siprocal.py)
--   → ETL job siprocal_daily_external (Firestore: platform_reports/siprocal_daily_external)
--   → WRITE_TRUNCATE → adframework.raw.siprocal_delivery
--   Schedule: 03:20 UTC diário (schedule_cron: "20 3 * * *")
--   Credentials: Firestore platform_credentials/siprocal.secrets
--     {spreadsheet_id: "1HaGrxaU-...", sheet_range: "raw_daily!A:G"}
--
-- LEGADO (DESCONTINUADO): o pipeline antigo usava sync_sheet.py → raw.siprocal_raw_sheet
--   e um endpoint BQ para query intermediária. Foi substituído pelo conector direto.
--
-- SCHEMA DA SHEET: PI Externo | Data | Campanha | Criativo | Impressions | Clicks | CTR
--   Suporta headers em PT e EN via _COLUMN_ALIASES no conector.
--   Datas em dd/mm/yyyy ou yyyy-mm-dd — normalizadas para yyyy-mm-dd na ingestão.
--   CTR (col G) é descartada — recalculada no STG/Gold se necessário.
--
-- IMPORTANTE: O campo `advertiser` segue o padrão NEWAD_{CLIENTE}_BR_{MES}{ANO}.
--   stg.siprocal_delivery extrai o {CLIENTE} via regex e faz join com core.platform_client_links.
--   Qualquer variação de escrita pelo lado da Siprocal quebra a atribuição silenciosamente.
--
-- NOTA SCHEMA: tabela criada via load_rows (WRITE_TRUNCATE) — sem partição real.
--   DDL abaixo define o schema canônico; a partição PARTITION BY DATE(raw_ingested_at)
--   não está ativa na tabela atual (recriada a cada load completo).

CREATE OR REPLACE TABLE `adframework.raw.siprocal_delivery`
(
  -- Dimensões
  day             STRING    NOT NULL,  -- YYYY-MM-DD
  advertiser      STRING,              -- nome do anunciante (texto livre da Siprocal)
  campaign_id     STRING,              -- ID da campanha na Siprocal
  creative_type   STRING,              -- tipo de criativo (Push, Native, Display, etc.)
  creative        STRING,              -- nome/ID do criativo

  -- Métricas de entrega
  impressions     STRING,
  clicks          STRING,

  -- Metadados de ingestão
  platform        STRING,             -- sempre 'siprocal'
  report_name     STRING,
  raw_ingested_at TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (
  description = 'Entrega diária Siprocal. Grain: day+advertiser+campaign_id+creative_type+creative. advertiser é texto livre — join frágil. Atribuição via core.platform_client_links.'
);
