-- raw.siprocal_raw_sheet
-- Tabela de staging Siprocal. Alimentada por scripts/siprocal/sync_sheet.py.
-- Lida pelo ETL job siprocal_daily_external → grava raw.siprocal_delivery.
--
-- IMPORTANTE: Deve ser TABLE nativa BQ. O orchestrator rejeita External Tables Sheets como fonte.
-- Consulte também: raw.siprocal_sheet_ext (External Table auxiliar para inspeção da planilha).
--
-- Colunas mapeadas da planilha Google Sheets (tab raw_daily):
--   PI Externo (col A) → campaign_id
--   Data      (col B) → day  (normalizado para YYYY-MM-DD pelo sync_sheet.py)
--   Campanha  (col C) → advertiser
--   Criativo  (col D) → creative
--   Impressions (col E) → impressions
--   Clicks    (col F) → clicks
--   creative_type sempre '' (coluna não existe na planilha)

CREATE OR REPLACE TABLE `adframework.raw.siprocal_raw_sheet`
(
  day             STRING,    -- YYYY-MM-DD
  advertiser      STRING,    -- campo Campanha da planilha (NEWAD_{CLIENTE}_BR_{MES}{ANO})
  campaign_id     STRING,    -- campo PI Externo
  creative_type   STRING,    -- sempre '' (não disponível na planilha)
  creative        STRING,    -- campo Criativo
  impressions     STRING,
  clicks          STRING
)
OPTIONS (
  description = 'Staging Siprocal. Populada por sync_sheet.py. ETL job lê daqui e grava raw.siprocal_delivery.'
);
