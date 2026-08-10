#!/usr/bin/env python3
"""
sync_gold_descriptions.py -- aplica descricoes de dbt-style YAML irmao ao
BigQuery, via ALTER VIEW/TABLE ... SET OPTIONS(description=...)
--------------------------------------------------------------------------
Implementado em 2026-08-09 (B8 da Frente B de reestruturacao de docs), sobre
o rascunho criado em 2026-08-08 (nunca executado). Le os arquivos `.yml`
IRMAOS de cada `.sql` em `gold/ddl/` (ex: `gold/ddl/fact_delivery_by_device.yml`
ao lado de `gold/ddl/fact_delivery_by_device.sql`) -- formato dbt-like ja
confirmado pelo Douglas em 2026-08-08 (Opcao B, ver historico abaixo) e ja
usado manualmente para as views documentadas em `docs/gold_layer_design.md`.

Por que isso existe
--------------------
`docs/gold_layer_design.md` documentava as views manualmente em Markdown --
funciona para a narrativa de design (grains, trade-offs), mas diverge da
producao no primeiro dia em que alguem cria/altera uma coluna sem lembrar de
atualizar o doc (a auditoria de 2026-08-08 encontrou 4 views reais fora do
doc). A ideia deste script e o INVERSO do fluxo manual: descricoes vivem
perto da DDL versionada (no YAML irmao, nao dentro do doc Markdown) e sao
aplicadas no BQ via `ALTER ... SET OPTIONS(description=...)` -- dai
`bq show`/`INFORMATION_SCHEMA` passam a ser a fonte de verdade que tanto o
doc quanto ferramentas de terceiro (dbt docs, data catalog, Power BI) podem
ler diretamente, sem depender de um Markdown mantido a mao.

Historico da decisao de formato (Douglas, 2026-08-08)
------------------------------------------------------
Confirmado: YAML irmao por arquivo (`gold/ddl/<nome>.yml`), estilo
schema/description do dbt (`description:` + `columns: {nome: descricao}`).
A opcao alternativa (bloco de comentario estruturado no topo do `.sql`) foi
descartada por misturar metadado de documentacao com o arquivo executavel
que o `apply_ddl.py` aplica literalmente.

O que este script FAZ
----------------------
1. Para cada `.sql` em `gold/ddl/` com um `.yml` irmao, le `description`
   (nivel de view/tabela) e `columns` (dict nome -> descricao) do YAML.
2. Extrai o alvo real (`project.dataset.object`) do `CREATE OR REPLACE
   VIEW/TABLE ...` no `.sql` correspondente -- nao confia no nome do
   arquivo sozinho, o alvo real e o que importa.
3. Monta as instrucoes `ALTER VIEW ... SET OPTIONS(description=...)` e
   `ALTER TABLE ... ALTER COLUMN ... SET OPTIONS(description=...)`.
4. Em `--dry-run` (default), so IMPRIME as instrucoes -- nunca conecta no
   BigQuery, nunca precisa de credencial. Em execucao real (`--no-dry-run`,
   exige confirmacao explicita), aplica via `google-cloud-bigquery`.

O que este script NAO FAZ -- IMPORTANTE
------------------------------------------
Nao decide sozinho se uma coluna existe de fato na tabela/view -- se o YAML
citar uma coluna que nao existe mais no SQL (drift entre os dois arquivos
irmaos), o BigQuery vai rejeitar o `ALTER COLUMN` na hora de aplicar (falha
alto, nao silenciosamente). Este script nao faz esse cruzamento antes --
fica para uma v2 se o drift virar problema recorrente.

Uso
---
    # Dry-run (default) -- mostra o que seria alterado, nao executa nada,
    # nao precisa de credencial nem de rede
    python sync_gold_descriptions.py

    # Mesma coisa, explicito
    python sync_gold_descriptions.py --dry-run

    # Aplica de verdade contra staging (nunca direto em producao sem passar
    # por staging primeiro -- mesmo principio de scripts/deploy/apply_ddl.py)
    python sync_gold_descriptions.py --project douglas-bq-staging --no-dry-run

    # So depois de validado no staging: promove pra producao
    python sync_gold_descriptions.py --project adframework --no-dry-run

Auth (só quando --no-dry-run): Application Default Credentials, mesmo padrao
dos outros scripts do repo (`gcloud auth application-default login`).

Testado nesta correcao (2026-08-09)
--------------------------------------
Rodado em --dry-run contra os 3 YAMLs reais existentes hoje em `gold/ddl/`
(`fact_delivery_by_device.yml`, `fact_delivery_creative.yml`,
`vw_fact_delivery_reporting.yml`) -- gera as instrucoes ALTER esperadas, sem
tocar no BigQuery. NAO executado com `--no-dry-run` contra nenhum projeto
nesta correcao -- aplicar de verdade e decisao separada do Douglas.
"""

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "[sync_gold_descriptions] Dependencia faltando: PyYAML. "
        "Instale com `pip install pyyaml` antes de rodar (mesmo em --dry-run).",
        file=sys.stderr,
    )
    sys.exit(1)

import re

PROJECT_DEFAULT = "adframework"
GOLD_DDL_DIR = Path(__file__).resolve().parent.parent.parent / "gold" / "ddl"

# Mesmo padrao de deteccao de alvo usado em scripts/deploy/apply_ddl.py --
# reutilizado aqui (nao importado direto do apply_ddl.py de proposito, pra
# manter este script autocontido e facil de ler isoladamente, mesma decisao
# de design do rascunho original).
CREATE_STATEMENT_RE = re.compile(
    r"""
    CREATE \s+ (?:OR \s+ REPLACE \s+)?
    (?:VIEW | TABLE | MATERIALIZED \s+ VIEW)
    \s+
    `?(?P<project>[\w-]+)\.(?P<dataset>\w+)\.(?P<object>\w+)`?
    """,
    re.IGNORECASE | re.VERBOSE,
)

# `CREATE ... VIEW` vs `CREATE ... TABLE` importa porque a sintaxe de
# ALTER COLUMN e a mesma nos dois casos no BigQuery (ALTER TABLE, mesmo para
# view) -- mas o ALTER de description no nivel do OBJETO usa ALTER VIEW para
# views e ALTER TABLE para tabelas. Detectado aqui para montar o statement
# certo.
OBJECT_KIND_RE = re.compile(
    r"CREATE \s+ (?:OR \s+ REPLACE \s+)? (?P<kind>VIEW|TABLE|MATERIALIZED\s+VIEW)",
    re.IGNORECASE | re.VERBOSE,
)


def find_creation_target(sql_text: str):
    match = CREATE_STATEMENT_RE.search(sql_text)
    if not match:
        return None
    return match.group("project"), match.group("dataset"), match.group("object")


def find_object_kind(sql_text: str) -> str:
    match = OBJECT_KIND_RE.search(sql_text)
    if not match:
        return "VIEW"
    kind = match.group("kind").upper()
    return "TABLE" if "TABLE" in kind else "VIEW"


def load_yaml_description(yml_path: Path):
    """Le o YAML irmao no formato dbt-like (Opcao B, decidida 2026-08-08).
    Retorna (view_description: str|None, column_descriptions: dict[str, str])."""
    data = yaml.safe_load(yml_path.read_text(encoding="utf-8")) or {}
    view_description = data.get("description")
    if isinstance(view_description, str):
        view_description = view_description.strip()
    column_descriptions = {}
    for column, desc in (data.get("columns") or {}).items():
        if isinstance(desc, str):
            column_descriptions[column] = desc.strip()
    return view_description, column_descriptions


def build_alter_statements(project: str, dataset: str, object_name: str, object_kind: str,
                            view_description: str, column_descriptions: dict):
    """Monta as instrucoes SET OPTIONS -- NUNCA executadas por esta funcao,
    so retornadas como texto para quem chamar decidir (dry-run vs execucao)."""
    statements = []
    fq_name = f"`{project}.{dataset}.{object_name}`"
    if view_description:
        escaped = view_description.replace("'", "\\'")
        statements.append(
            f"ALTER {object_kind} {fq_name} SET OPTIONS(description = '{escaped}');"
        )
    for column, description in column_descriptions.items():
        escaped = description.replace("'", "\\'")
        # BigQuery usa `ALTER TABLE ... ALTER COLUMN` mesmo para colunas de
        # VIEW -- confirmado contra a documentacao publica do BQ (ALTER
        # COLUMN nao tem variante ALTER VIEW ... ALTER COLUMN). Nao
        # reconfirmado contra staging nesta correcao (script segue em
        # --dry-run only nesta entrega) -- CONFIRMAR antes do primeiro
        # --no-dry-run real.
        statements.append(
            f"ALTER TABLE {fq_name} ALTER COLUMN {column} "
            f"SET OPTIONS(description = '{escaped}');"
        )
    return statements


def collect_statements(project: str):
    if not GOLD_DDL_DIR.exists():
        print(f"[sync_gold_descriptions] Diretorio nao encontrado: {GOLD_DDL_DIR}", file=sys.stderr)
        sys.exit(1)

    all_statements = []
    yml_files = sorted(GOLD_DDL_DIR.glob("*.yml"))
    if not yml_files:
        print("[sync_gold_descriptions] Nenhum .yml encontrado em gold/ddl/ -- nada a fazer.")
        return all_statements

    for yml_path in yml_files:
        sql_path = yml_path.with_suffix(".sql")
        if not sql_path.exists():
            print(
                f"[sync_gold_descriptions] Aviso: {yml_path.name} nao tem .sql irmao "
                f"({sql_path.name} nao existe) -- pulando.",
                file=sys.stderr,
            )
            continue

        sql_text = sql_path.read_text(encoding="utf-8")
        target = find_creation_target(sql_text)
        if not target:
            print(f"[sync_gold_descriptions] Aviso: sem CREATE reconhecido em {sql_path.name}, pulando.")
            continue

        _original_project, dataset, object_name = target
        object_kind = find_object_kind(sql_text)
        view_description, column_descriptions = load_yaml_description(yml_path)

        if not view_description and not column_descriptions:
            print(f"[sync_gold_descriptions] Aviso: {yml_path.name} sem description/columns, pulando.")
            continue

        statements = build_alter_statements(
            project, dataset, object_name, object_kind, view_description, column_descriptions
        )
        all_statements.extend(statements)

    return all_statements


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=PROJECT_DEFAULT,
                         help="Default: adframework (producao). Testar em douglas-bq-staging primeiro.")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                         help="Default. So imprime as instrucoes ALTER, nao executa nada.")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false",
                         help="Executa de fato contra o --project indicado. Requer confirmacao "
                              "interativa (digitar 'sim') alem da flag.")
    args = parser.parse_args()

    all_statements = collect_statements(args.project)

    print(f"[sync_gold_descriptions] {len(all_statements)} instrucao(oes) ALTER geradas "
          f"(fonte: YAMLs irmaos em gold/ddl/, alvo: projeto '{args.project}'):")
    for stmt in all_statements:
        print(f"  {stmt}")

    if not all_statements:
        return

    if args.dry_run:
        print("[sync_gold_descriptions] --dry-run (default): nada foi executado contra o BigQuery.")
        return

    confirm = input(
        f"\n[sync_gold_descriptions] Confirma aplicar {len(all_statements)} instrucao(oes) "
        f"ALTER contra '{args.project}'? Digite 'sim' para continuar: "
    )
    if confirm.strip().lower() != "sim":
        print("[sync_gold_descriptions] Cancelado pelo usuario.")
        return

    from google.cloud import bigquery  # import tardio: so precisa de credencial em execucao real

    bq_client = bigquery.Client(project=args.project)
    for stmt in all_statements:
        job = bq_client.query(stmt)
        job.result()
        print(f"  OK: {stmt}")
    print("[sync_gold_descriptions] Concluido -- descricoes aplicadas.")


if __name__ == "__main__":
    main()
