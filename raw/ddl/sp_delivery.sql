-- raw.sp_delivery
-- Dump literal da planilha Siprocal (Google Sheets, aba raw_daily).
-- Sem nenhum tratamento semantico: nomes de coluna sao os headers reais da
-- planilha, so sanitizados para nomenclatura BQ (lowercase, espacos->underscore).
-- Renomeacao semantica (coluna_1 -> pi_externo, parse de data, derivacao de
-- client_name a partir de "campanha") acontece na STG.
--
-- Header real confirmado em 2026-06-22 via planilha 1HaGr...LWs, aba raw_daily:
--   Coluna 1, Data, Campanha, Criativo, Impressions, Clicks, CTR
-- "Coluna 1" = pi_externo (confirmado pelo usuario) -- nome generico na planilha,
-- nao e erro de mapeamento do conector.
--
-- Filtro de sanidade aplicado na ingestao (nao e tratamento semantico):
-- linhas onde TODAS as colunas de dado (exceto CTR) estao vazias sao descartadas.
-- Motivo: a planilha tem uma formula de CTR arrastada milhares de linhas alem do
-- dado real, gerando #DIV/0! em linhas sem nenhum outro valor.
--
-- Grain: 1 linha por (data, campanha, criativo) na planilha
-- Ingestao: incremental (WRITE_APPEND, so chaves novas) desde 2026-08-03.
-- Antes disso era WRITE_TRUNCATE diario (replace total). A mudanca manteve a
-- resiliencia a correcoes retroativas do Siprocal na planilha: toda run ainda
-- compara a planilha inteira contra o que ja esta aqui (custo irrelevante,
-- tabela pequena); uma chave existente com valor diferente NUNCA e sobrescrita
-- automaticamente -- vai para raw.sp_delivery_pending_corrections para revisao
-- manual. Ver adframework_python/src/orchestrator.py:_run_siprocal_daily e
-- src/connectors/siprocal.py:diff_rows().

CREATE OR REPLACE TABLE `adframework.raw.sp_delivery`
(
  coluna_1          STRING,     -- pi_externo (nome literal da planilha) -- renomeado na STG
  data              STRING,     -- data em texto, formato dd/mm/yyyy -- parse na STG
  campanha          STRING,     -- nome completo da campanha, ex: NEWAD_LUCKBET_BR_SET25
  criativo          STRING,     -- label do criativo (texto livre, sem padrao)
  impressions       STRING,     -- texto literal da planilha -- cast na STG
  clicks            STRING,     -- texto literal da planilha -- cast na STG
  ctr               STRING,     -- texto literal, ex: "1,82%" -- parse na STG
  platform          STRING,     -- 'siprocal' (injetado)
  raw_ingested_at   TIMESTAMP   -- timestamp da ingestao (injetado)
)
OPTIONS (
  description = 'RAW literal da planilha Siprocal (raw_daily). Sem aliasing/normalizacao -- ver STG para renomeacao semantica. WRITE_TRUNCATE diario.'
);
