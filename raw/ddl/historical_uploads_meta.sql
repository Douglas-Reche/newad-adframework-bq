-- raw.historical_uploads_meta -- 1 linha por upload, metadado de estrutura
-- ----------------------------------------------------------------------------
-- Irma de raw.historical_uploads (ver esse arquivo para o contexto completo
-- do fluxo e a decisao de schema). Esta tabela existe so pra responder
-- barato "quais colunas tinha esse upload, e quantas linhas" sem precisar
-- introspectar JSON via SQL a cada consulta do Hub -- escrita 1x por upload
-- pelo proprio script de carga (scripts/deploy/load_historical_raw.py), que
-- ja tem essa informacao em maos ao ler o arquivo original (nomes de coluna
-- na ORDEM em que apareciam no arquivo, antes de qualquer transformacao).
--
-- column_names e ARRAY<STRING> (nao um JSON) de proposito -- e uma lista
-- simples e plana, sem necessidade de aninhamento; ARRAY nativo e mais facil
-- de consumir de um SELECT direto no Hub (Streamlit) do que parsear JSON de
-- novo.
--
-- So existe em douglas-bq-staging (mesma excecao de raw.historical_uploads).

CREATE TABLE IF NOT EXISTS `douglas-bq-staging.raw.historical_uploads_meta`
(
  upload_id        STRING       NOT NULL,
  client_id        STRING       NOT NULL,
  source_filename  STRING,
  column_names     ARRAY<STRING>,
  row_count        INT64,
  uploaded_at       TIMESTAMP,
  uploaded_by       STRING,
  notes             STRING
)
OPTIONS (
  description = 'Metadado de 1 linha por upload_id de raw.historical_uploads -- nomes de coluna originais (na ordem do arquivo) + contagem de linhas, escrito 1x pelo script de carga no fim de cada upload. Existe pra evitar introspeccao de JSON via SQL no consumo do Hub. So existe em douglas-bq-staging.'
);

-- notes: comentario/contexto livre digitado por quem sobe o arquivo (ex: "planilha
-- so tem Jan-Jun, formato mudou a partir de Mar" -- coisas que ajudam na hora de
-- normalizar depois). Adicionado 2026-08-11, pedido do Douglas durante o teste ao
-- vivo do fluxo de override. Nullable -- uploads antigos (antes desta coluna
-- existir) ficam com notes NULL, tratado como "sem nota" na UI.
ALTER TABLE `douglas-bq-staging.raw.historical_uploads_meta`
  ADD COLUMN IF NOT EXISTS notes STRING;
