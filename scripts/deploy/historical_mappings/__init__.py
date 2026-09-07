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
nesse modulo, fonte unica -- lista completa la, nao duplicada aqui).

`target_group` (adicionado 2026-09-07, redesenho Casa do Construtor/Audio):
NULLABLE, NULL no caso comum (nenhum split por target na fonte). So
preenchido quando a planilha tem blocos "TARGET N" lado a lado com o total
blended (mesmo conceito/nome ja usado em raw.io_plan_drive_snapshot) --
nesse caso normalize() deve emitir 1 linha por target ALEM da linha
blended (target_group=NULL), nunca substituir a blended pelas linhas de
target. Ver historical_mappings/casa_construtor_adf15c2c.py para o exemplo
completo e stg/ddl/historical_overrides_delivery.sql para o porque
target_group nao entra na chave lida por gold.fact_delivery/
stg.fact_pacing_base_refresh.sql (so a linha blended alimenta producao).

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
#
# "unknown" ADICIONADO em 2026-09-07 (historical_mappings/casa_construtor_adf15c2c.py,
# ingestao de Audio -- decisao de plataforma real MiQ vs Adsmovil ainda
# PENDENTE de confirmacao do Douglas, task Notion em aberto). Motivo, 2
# partes:
#   1. Instrucao explicita da task: tratar `platform` como valor a definir
#      depois sem bloquear a ingestao, mesmo padrao ja usado para Push
#      nesse cliente (gold.fact_io_plan ja emite platform="unknown" hoje
#      pra Push da Casa do Construtor).
#   2. Motivo TECNICO, nao so de conveniencia: gold.fact_io_plan JA emite
#      platform="unknown" para a estrategia real "Audio Ads" da Casa do
#      Construtor (confirmado ao vivo em douglas-bq-staging). O JOIN em
#      stg/ddl/fact_pacing_base_refresh.sql exige
#      UPPER(ov.platform) = UPPER(j.platform) -- se o override usasse
#      platform=NULL em vez de "unknown", o JOIN NUNCA bateria (NULL !=
#      'unknown' em SQL) e a linha ficaria com is_override=TRUE mas os
#      valores do override vazios, um bug silencioso pior do que a falta
#      de confirmacao de negocio.
# Esta extensao afeta a validacao de QUALQUER client_id/mapeamento futuro
# que declarar platform="unknown", nao so Casa do Construtor -- decisao de
# impacto compartilhado, reportada explicitamente para o Douglas confirmar
# (ver AVISO 1 na docstring de casa_construtor_adf15c2c.py).
VALID_PLATFORMS = {"mediasmart", "mgid", "siprocal", "unknown"}
