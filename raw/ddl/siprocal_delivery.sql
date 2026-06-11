-- raw.siprocal_delivery
-- Entrega diária da Siprocal. Fonte de verdade para dados Siprocal no pipeline.
-- Grain: day + advertiser + campaign_id + creative_type + creative
--
-- PIPELINE DE INGESTÃO:
--   1. Google Sheet (raw_daily) → scripts/siprocal/sync_sheet.py → raw.siprocal_raw_sheet (TABLE nativa)
--   2. ETL job siprocal_daily_external (Cloud Run, Firestore: platform_reports/siprocal_daily_external)
--      lê de raw.siprocal_raw_sheet → sobrescreve esta tabela (CREATE OR REPLACE, diário 05:00 UTC)
--      Endpoint lido de: Firestore platform_endpoints/siprocal_ep_external_daily (path_template)
--
-- IMPORTANTE: raw.siprocal_raw_sheet DEVE ser TABLE nativa BQ.
--   O orchestrator valida o tipo da tabela e rejeita External Tables com fonte Google Sheets.
--   raw.siprocal_sheet_ext (External Table) existe como auxiliar para inspeção; nunca usá-la diretamente.
--   Para automação completa: agendar sync_sheet.py às 04:45 UTC via Cloud Run Job (pendente Shiro).
--
-- IMPORTANTE: O campo `advertiser` segue o padrão NEWAD_{CLIENTE}_BR_{MES}{ANO}.
--   stg.siprocal_delivery extrai o {CLIENTE} via regex e faz join com core.platform_client_links.
--   Qualquer variação de escrita pelo lado da Siprocal quebra a atribuição silenciosamente.

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
