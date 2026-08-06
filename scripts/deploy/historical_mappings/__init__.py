"""historical_mappings — um arquivo Python por client_id, versionado no Git.

Cada arquivo <sanitized_client_id>.py neste pacote exporta uma funcao:

    def normalize(raw_rows: list[dict]) -> list[dict]:
        ...

Contrato de entrada (raw_rows) -- cada item e um dict:
    {
        "row_number": int,          # de raw.historical_uploads.row_number
        "raw_row": dict,            # JSON de raw.historical_uploads.raw_row
                                     # ja deserializado -- {coluna_original: valor_str_ou_None}
        "client_id": str,           # de raw.historical_uploads.client_id
        "source_filename": str,     # de raw.historical_uploads.source_filename
    }

Contrato de saida -- lista de dicts, cada um com EXATAMENTE as colunas que
scripts/deploy/load_historical_override.py espera (ver REQUIRED_COLUMNS
nesse modulo):
    client_id, day, platform, formato, goal_type, impressions, clicks,
    investimento, conversions, source_file, notes

`day` deve ser string 'YYYY-MM-DD' (ou objeto date/datetime -- o
orquestrador normaliza antes de escrever o CSV). `investimento`, `clicks`,
`impressions`, `conversions` devem ser float ou None (nunca string).

Por que um arquivo por cliente em vez de um parser generico
-------------------------------------------------------------
Cada cliente manda planilha com nomes de coluna, formato de data e unidade
diferentes (decisao registrada no proprio docstring de
load_historical_override.py: normalizacao nao e automatizavel de antemao).
Um arquivo por cliente:
  - e codigo versionado no Git (historico, review, blame) em vez de config
    solta (json/yaml) que não expressa transformacao arbitraria;
  - falha alto e cedo se nao existir mapeamento pra um client_id (ver
    normalize_historical_upload.py) -- nunca tenta adivinhar;
  - isola o "conhecimento tribal" de uma planilha (ex: "essa coluna as
    vezes vem em branco e significa zero, nao NULL") no lugar exato onde
    esse conhecimento importa, sem vazar pra um parser generico que ninguem
    entende depois de 6 meses.
"""
