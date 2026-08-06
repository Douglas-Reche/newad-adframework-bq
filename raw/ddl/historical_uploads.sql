-- raw.historical_uploads -- landing literal de uploads manuais de planilha
-- historica (Cora/TecPar/futuros clientes), ANTES de qualquer normalizacao.
-- ----------------------------------------------------------------------------
-- Contexto (2026-08-06, preparacao pra reuniao): o fluxo completo de "dado
-- historico por cliente" tem 5 etapas -- ver docs (a serem escritas pelo
-- agente `docs` a partir do relato desta mudanca). Esta tabela cobre so a
-- etapa 2: "Hub sobe a planilha crua, sem tratamento nenhum". A etapa 5
-- (carga do dado JA normalizado em stg.historical_overrides_delivery) ja
-- existe -- ver scripts/deploy/load_historical_override.py e
-- stg/ddl/historical_overrides_delivery.sql. Este arquivo e a peca que
-- faltava: onde o dump cru pousa entre a etapa 1 (comercial manda a
-- planilha) e a etapa 3 (Douglas + IA olham a estrutura real no Hub pra
-- desenhar o mapeamento).
--
-- EXCECAO DELIBERADA: existe SO em douglas-bq-staging.raw -- nao em
-- producao, nao espelhada por apply_ddl.py (raw/stg normalmente sao leitura
-- cross-project apontando pra producao, nunca fisicamente replicadas -- ver
-- PHYSICAL_DATASETS em scripts/deploy/apply_ddl.py). O dataset `raw` dentro
-- de douglas-bq-staging so existe fisicamente por causa deste caso de uso
-- especifico (upload manual de planilha de formato desconhecido, trabalho
-- de descoberta) -- nao e o inicio de um padrao geral de "raw tambem existe
-- em staging".
--
-- Escolha de schema: tabela generica linha-a-linha com coluna JSON, em vez
-- de uma tabela por upload (`raw.historical_upload_<client_id>_<ts>`) com
-- DDL proprio por cliente/arquivo. Motivo: cada planilha de cliente chega
-- com colunas totalmente diferentes (nomes, quantidade, ordem) e o objetivo
-- desta etapa e SO permitir visualizar a estrutura real (nomes de coluna +
-- amostra + contagem) antes de desenhar o mapeamento -- criar DDL novo por
-- upload seria overhead sem beneficio (ninguem faz JOIN tipado nesta
-- tabela, e um dump de descoberta). Uma tabela generica tambem elimina o
-- gargalo de "precisa de deploy/DDL novo toda vez que um cliente novo manda
-- uma planilha" -- o script de carga (scripts/deploy/load_historical_raw.py)
-- funciona pra qualquer estrutura de arquivo sem alteracao nenhuma aqui.
--
-- raw_row e STRING (nao o tipo nativo JSON do BQ) guardando um JSON-text
-- serializado a partir de um dict {nome_da_coluna_original: valor_como_string}.
-- TODAS as colunas do arquivo de origem sao lidas como STRING no momento da
-- carga (dtype=str, sem inferencia de tipo do pandas) -- e o mesmo
-- principio "RAW = dump literal" do resto do pipeline (STRING mesmo quando
-- o valor e numerico, SAFE_CAST acontece so no STG/normalizacao, nunca
-- aqui). Isso preserva formatos ambiguos ou nao-parseaveis sem tentar
-- adivinhar (ex: "1.234,56" em formato brasileiro, "Data Ref" com um
-- formato de data nao-ISO) -- exatamente o que esta etapa precisa mostrar
-- fielmente pra decisao humana na etapa 3.
--
-- Nomes de coluna originais NAO sao normalizados nem sanitizados aqui (BQ
-- nao aceita nomes de coluna arbitrarios como identificador de coluna real,
-- por isso JSON em vez de colunas nativas -- uma planilha pode ter nomes
-- como "Formato (PT)" ou colunas duplicadas, que quebrariam um CREATE TABLE
-- tipado).
--
-- A lista de nomes de coluna (na ordem original do arquivo) e a contagem de
-- linhas ficam em raw.historical_uploads_meta (uma linha por upload,
-- escrita pelo mesmo script no fim da carga) -- ver esse arquivo para o
-- motivo de nao depender de introspeccao de JSON via SQL (JSON_QUERY/
-- JSON_EXTRACT em BQ nao tem uma funcao direta de "listar chaves de um
-- objeto JSON" equivalente a JSON_KEYS de outros warehouses; e mais simples
-- e mais barato o proprio script Python, que ja tem os nomes de coluna em
-- maos ao ler o arquivo, gravar isso uma vez por upload do que pedir pro
-- Hub reconstruir isso via SQL a cada consulta).

CREATE TABLE IF NOT EXISTS `douglas-bq-staging.raw.historical_uploads`
(
  upload_id        STRING    NOT NULL,
  client_id        STRING    NOT NULL,
  source_filename  STRING,
  row_number       INT64,
  raw_row          STRING,
  uploaded_at       TIMESTAMP,
  uploaded_by       STRING
)
OPTIONS (
  description = 'Dump literal (uma linha por linha de dado da planilha original) de uploads manuais de historico por cliente, ANTES de normalizacao. raw_row = JSON-text de {coluna_original: valor_como_string}, sem nenhuma tipagem/interpretacao. So existe em douglas-bq-staging (excecao deliberada, nao mirrorada em producao). Carregada por scripts/deploy/load_historical_raw.py. Ver raw.historical_uploads_meta para nomes de coluna + contagem por upload_id.'
);
