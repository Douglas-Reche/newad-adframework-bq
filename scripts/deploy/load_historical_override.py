#!/usr/bin/env python3
"""
load_historical_override.py — carrega dado (nao schema) em
stg.historical_overrides_delivery
--------------------------------------------------------------------------
Irma do apply_ddl.py (mesmo diretorio, mesmo padrao de --project/--dry-run),
mas para DADO em vez de DDL: le um arquivo ja normalizado (CSV ou parquet,
colunas ja mapeadas 1:1 para o schema de stg.historical_overrides_delivery
-- ver stg/ddl/historical_overrides_delivery.sql, tabela movida de core
para stg em 2026-08-06) e insere as linhas na tabela, no projeto indicado.

O QUE ESTA FERRAMENTA NAO FAZ -- IMPORTANTE
---------------------------------------------
Esta ferramenta so CARREGA. Ela nao normaliza. Pegar a planilha crua que um
cliente manda (nomes de coluna, formatos de data, unidades, ambiguidade de
qual platform/formato uma linha representa) e transformar isso no formato
de stg.historical_overrides_delivery e trabalho de analise humana + IA
caso a caso -- decisao do usuario (Douglas) em 2026-08-05, ao desenhar este
script: a normalizacao NAO e automatizavel de antemao (cada fonte de
historico manual chega com um formato diferente, sem contrato de API por
tras). Se o arquivo de entrada nao estiver exatamente no formato de saida
esperado (ver COLUNAS_ESPERADAS abaixo), este script falha alto e cedo --
nao tenta adivinhar mapeamento de coluna.

Uso
---
    # Dry-run -- mostra o que seria inserido, nao grava nada
    python load_historical_override.py overrides_cora_jul2026.csv --dry-run

    # Carrega de fato, contra o projeto de producao (default)
    python load_historical_override.py overrides_cora_jul2026.csv \\
        --loaded-by douglas

    # Carrega contra o projeto de staging (douglas-bq-staging) -- mesmos
    # nomes de dataset (sem sufixo _test), o projeto ja significa teste
    python load_historical_override.py overrides_cora_jul2026.csv \\
        --project douglas-bq-staging --dry-run

Formato de entrada aceito: .csv ou .parquet, com exatamente as colunas
abaixo (nomes iguais, ordem livre). Colunas ausentes = erro (nao
preenchidas com NULL silenciosamente -- um arquivo faltando `client_id`
por exemplo e quase certamente um bug de normalizacao upstream, nao uma
omissao intencional).

Validacao de `platform` (2026-08-11): quando a coluna nao for NULL, o
valor precisa bater (normalizado para minusculo) com
historical_mappings.VALID_PLATFORMS = {"mediasmart", "mgid", "siprocal"}
-- lista fechada, mesma usada em gold/ddl/fact_delivery.sql. Falha alto e
cedo em validate_rows() -- ver comentario la para o raciocinio completo
(platform, diferente de formato, nao tinha nenhuma reconciliacao em
nenhum outro lugar do fluxo ate esta mudanca).

Auth: usa Application Default Credentials, mesmo padrao do apply_ddl.py
(`gcloud auth application-default login`).
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

from historical_mappings import VALID_PLATFORMS

PROJECT_DEFAULT = "adframework"
TABLE_ID = "stg.historical_overrides_delivery"

# Mantido em sincronia manual com stg/ddl/historical_overrides_delivery.sql
# (tabela movida de core para stg em 2026-08-06 -- dado normalizado
# pertence a STG, nao a CORE; ver o header desse arquivo para o historico
# completo, incluindo a criacao original em hub/ddl_historical_overrides.sql
# + ALTER que adicionou `conversions`).
# Nao ha introspeccao automatica do schema do BQ aqui de proposito -- o
# --dry-run precisa funcionar sem credencial/rede nenhuma.
#
# `planned_impressions_daily`/`planned_clicks_daily`/`planned_spend_daily`/
# `unit_price` adicionados em 2026-08-12: a DDL (stg/ddl/historical_overrides_delivery.sql)
# ja tinha essas 4 colunas desde 2026-08-10 (ALTER TABLE ADD COLUMN IF NOT
# EXISTS, task "Materializar base de fact_pacing na STG"), mas esta lista
# nunca foi atualizada para acompanhar -- achado real ao implementar o
# mapeamento de banco_cora_fe13d78a, cujo `normalize()` precisa preencher o
# lado planejado. Sem este fix, normalize_historical_upload.py rejeitaria
# qualquer normalize() que preenchesse essas colunas como "coluna extra nao
# esperada" (ver validate_normalized() la). Todas as 4 sao NULLABLE -- um
# normalize() que nao usa o lado planejado (como
# historical_mappings/teste_agente_backend_xyz.py) so preenche com None.
REQUIRED_COLUMNS = [
    "client_id",
    "day",
    "platform",
    "formato",
    "goal_type",
    "impressions",
    "clicks",
    "investimento",
    "conversions",
    "planned_impressions_daily",
    "planned_clicks_daily",
    "planned_spend_daily",
    "unit_price",
    "source_file",
    "notes",
]

# Preenchidas pelo proprio script no momento do load -- nao devem vir no
# arquivo de entrada (se vierem, sao ignoradas e sobrescritas, ver load()).
AUTOFILLED_COLUMNS = ["loaded_by", "loaded_at"]


def read_input_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        raise ValueError(
            f"Extensao nao suportada: {path.suffix} -- esperado .csv ou .parquet"
        )

    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"Arquivo de entrada nao esta no formato normalizado esperado. "
            f"Colunas faltando: {sorted(missing)}. "
            f"Este script so carrega dado ja normalizado -- ver docstring do "
            f"modulo. Colunas esperadas: {REQUIRED_COLUMNS}"
        )

    extra = set(df.columns) - set(REQUIRED_COLUMNS) - set(AUTOFILLED_COLUMNS)
    if extra:
        print(
            f"[load_historical_override] AVISO: colunas extras no arquivo, "
            f"serao ignoradas no insert: {sorted(extra)}",
            file=sys.stderr,
        )

    return df[REQUIRED_COLUMNS].copy()


def validate_rows(df: pd.DataFrame) -> list:
    """Validacoes minimas de sanidade antes de tentar o insert -- nao
    substitui a normalizacao (que ja deve ter acontecido antes deste
    script rodar), so pega erros obvios de arquivo malformado."""
    problems = []

    if df["client_id"].isna().any():
        problems.append("Existem linhas com client_id vazio/NULL.")

    try:
        pd.to_datetime(df["day"])
    except Exception as e:
        problems.append(f"Coluna 'day' tem valor(es) que nao parseiam como data: {e}")

    dupe_key = df.duplicated(subset=["client_id", "day", "platform", "formato"], keep=False)
    if dupe_key.any():
        n = int(dupe_key.sum())
        problems.append(
            f"{n} linha(s) com a mesma chave (client_id, day, platform, formato) "
            f"repetida dentro do proprio arquivo -- historical_overrides_delivery "
            f"e append-only, um arquivo com chave duplicada internamente quase "
            f"certamente indica erro de normalizacao upstream, nao correcao "
            f"intencional (correcao intencional = nova linha com dado novo, nao "
            f"duplicata identica)."
        )

    # platform contra lista fechada (2026-08-11, achado ao blindar o JOIN
    # novo em stg/ddl/fact_pacing_base_refresh.sql com
    # stg.historical_overrides_delivery): diferente de `formato`
    # (reconciliado via core.dict_format/core.resolve_dict_format), a coluna
    # `platform` nao tem NENHUMA validacao/reconciliacao em nenhum outro
    # lugar do fluxo hoje -- um mapeamento de cliente com "MediaSmart" (em
    # vez do padrao real, minusculo, hardcoded em gold/ddl/fact_delivery.sql)
    # passaria por aqui sem erro e so quebraria silenciosamente mais tarde
    # (JOIN contra stg.historical_overrides_delivery cai pra formula sem
    # avisar ninguem). Falha alto e cedo, aqui, em vez de la. `platform`
    # pode ser NULL (nem todo cliente historico precisa preencher) -- so
    # valida quando nao-NULL. Comparacao normalizada pra minusculo (mesmo
    # criterio de match do JOIN em fact_pacing_base_refresh.sql, que agora
    # usa UPPER() dos dois lados) -- nao exige que o arquivo de entrada ja
    # venha em minusculo, so que o VALOR seja um dos 3 validos.
    non_null_platform = df["platform"].dropna()
    if not non_null_platform.empty:
        normalized = non_null_platform.astype(str).str.strip().str.lower()
        invalid_mask = ~normalized.isin(VALID_PLATFORMS)
        if invalid_mask.any():
            bad_rows = df.loc[non_null_platform.index[invalid_mask], ["client_id", "platform"]]
            details = ", ".join(
                f"linha client_id={row.client_id!r} platform={row.platform!r}"
                for row in bad_rows.itertuples(index=False)
            )
            problems.append(
                f"{int(invalid_mask.sum())} linha(s) com `platform` fora da lista "
                f"fechada {sorted(VALID_PLATFORMS)} (comparacao normalizada para "
                f"minusculo): {details}. Corrija o mapeamento de cliente "
                f"(historical_mappings/<client_id>.py) -- este script nao tenta "
                f"adivinhar o valor certo."
            )

    return problems


def build_rows(df: pd.DataFrame, loaded_by: str) -> list:
    now = datetime.now(timezone.utc).isoformat()
    df = df.copy()
    df["loaded_by"] = loaded_by
    df["loaded_at"] = now
    # day como string ISO -- insert_rows_json exige tipos serializaveis;
    # BigQuery aceita 'YYYY-MM-DD' para coluna DATE via streaming insert.
    df["day"] = pd.to_datetime(df["day"]).dt.strftime("%Y-%m-%d")
    rows = df.to_dict(orient="records")
    # Colunas nullable (platform, goal_type, impressions, conversions, etc)
    # chegam como float('nan') do pandas quando a celula esta vazia --
    # float('nan') NAO e JSON valido (o padrao JSON nao tem NaN; a lib do
    # BigQuery serializa como o literal `NaN`, que a API rejeita com 400
    # Bad Request). Trocar por None (-> `null` em JSON) antes do insert --
    # achado real ao rodar o teste ponta-a-ponta do fluxo de normalizacao
    # (scripts/deploy/normalize_historical_upload.py) contra um cliente com
    # varias colunas nullable vazias.
    for row in rows:
        for key, value in row.items():
            if isinstance(value, float) and pd.isna(value):
                row[key] = None
    return rows


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input_file", type=Path, help="CSV ou parquet ja normalizado (ver docstring)"
    )
    parser.add_argument("--project", default=PROJECT_DEFAULT)
    parser.add_argument(
        "--loaded-by", default=None, help="Default: usuario do SO local"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="So mostra o que seria inserido (contagem + preview), nao grava nada e nao precisa de credencial",
    )
    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Arquivo nao encontrado: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    try:
        df = read_input_file(args.input_file)
    except ValueError as e:
        print(f"[load_historical_override] ERRO: {e}", file=sys.stderr)
        sys.exit(1)

    problems = validate_rows(df)
    if problems:
        print("[load_historical_override] Arquivo reprovado na validacao:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    import getpass

    loaded_by = args.loaded_by or getpass.getuser()
    rows = build_rows(df, loaded_by)

    print(
        f"[load_historical_override] {len(rows)} linha(s) prontas para "
        f"{args.project}.{TABLE_ID} (loaded_by={loaded_by})"
    )
    print("----- preview (ate 5 linhas) -----")
    for row in rows[:5]:
        print(row)

    if args.dry_run:
        print("[load_historical_override] --dry-run: nada foi gravado.")
        return

    bq_client = bigquery.Client(project=args.project)
    table_ref = f"{args.project}.{TABLE_ID}"
    errors = bq_client.insert_rows_json(table_ref, rows)
    if errors:
        print(f"[load_historical_override] ERRO ao inserir: {errors}", file=sys.stderr)
        sys.exit(1)

    print(f"[load_historical_override] OK -- {len(rows)} linha(s) inseridas em {table_ref}.")


if __name__ == "__main__":
    main()
