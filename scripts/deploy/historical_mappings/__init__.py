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

# VALID_PLATFORMS -- lista fechada de `platform` (2026-08-11).
# Constante compartilhada entre os mapeamentos de cliente (`normalize()` de
# cada arquivo deste pacote) e a validacao em
# scripts/deploy/load_historical_override.py. Confirmada por leitura de
# gold/ddl/fact_delivery.sql -- as 3 unicas plataformas com conector real no
# pipeline hoje, sempre em minusculo (convencao hardcoded la, ex:
# `'mediasmart' AS platform`). `platform` pode ser NULL na saida de
# `normalize()` (nem todo cliente historico precisa preencher) -- so quando
# NAO-NULL o valor precisa bater com esta lista (normalizado para minusculo
# antes de comparar). Mesmo principio ja usado para `formato`
# (core.dict_format/core.resolve_dict_format -- reconciliar com taxonomia
# existente, falhar alto e cedo se nao bater) -- aqui aplicado no ponto de
# entrada do dado (load_historical_override.py), antes de chegar no
# BigQuery, porque `platform` nao tem NENHUMA reconciliacao/normalizacao em
# nenhum outro lugar do fluxo hoje (achado real, 2026-08-11, ao blindar o
# JOIN novo em stg/ddl/fact_pacing_base_refresh.sql com
# stg.historical_overrides_delivery -- um mapeamento de cliente escrevendo
# "MediaSmart" em vez de "mediasmart" faria esse JOIN falhar silenciosamente,
# sem nenhum aviso).
VALID_PLATFORMS = {"mediasmart", "mgid", "siprocal"}
