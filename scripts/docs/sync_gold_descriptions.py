#!/usr/bin/env python3
"""
sync_gold_descriptions.py — RASCUNHO NAO TESTADO, NAO EXECUTAR CONTRA PRODUCAO
--------------------------------------------------------------------------------
Criado em 2026-08-08 como esboco de mecanismo, a pedido do Douglas, depois de
uma auditoria em `docs/gold_layer_design.md` confirmar que NENHUMA das 9 views
de `adframework.gold` tem `description` aplicada hoje (nem a nivel de tabela
via `TABLE_OPTIONS`, nem a nivel de coluna) -- verificado ao vivo via
`INFORMATION_SCHEMA.TABLE_OPTIONS` e `bq show --format=json` em 2026-08-08.

Este arquivo NUNCA foi executado contra o BigQuery. E uma proposta de forma,
nao um mecanismo pronto. NAO rodar sem antes:
  1. o Douglas decidir o formato de origem das descricoes (ver secao
     "DECISAO PENDENTE" abaixo -- este rascunho assume a opcao A a titulo de
     exemplo, mas isso NAO esta confirmado);
  2. testar em --dry-run contra `douglas-bq-staging` (nunca direto em
     `adframework` -- mesmo principio de `scripts/deploy/apply_ddl.py`,
     que testa em ambiente `_test`/staging antes de promover);
  3. revisao de alguem alem de quem escreveu o script.

Por que isso existe
--------------------
`docs/gold_layer_design.md` documenta as views manualmente em Markdown --
funciona para a narrativa de design (grains, trade-offs), mas diverge da
producao no primeiro dia em que alguem cria/altera uma coluna sem lembrar de
atualizar o doc (foi exatamente o que a auditoria de 2026-08-08 encontrou: 4
views reais fora do doc). A ideia deste script e o INVERSO do fluxo manual:
descricoes vivem perto da DDL versionada (nao dentro do doc Markdown, que
deve ser regenerado por consulta ao INFORMATION_SCHEMA, nao editado a mao) e
sao aplicadas no BQ via `ALTER VIEW ... SET OPTIONS(description=...)` -- dai
`bq show`/`INFORMATION_SCHEMA` passam a ser a fonte de verdade que tanto o
doc quanto ferramentas de terceiro (dbt docs, data catalog, Power BI) podem
ler diretamente, sem depender de um Markdown mantido a mao.

DECISAO TOMADA (Douglas, 2026-08-08) -- formato de origem das descricoes
------------------------------------------------------------------
Confirmado: **Opcao B -- YAML irmao por arquivo** (ex: `gold/ddl/fact_delivery.yml`,
`gold/ddl/vw_fact_delivery_reporting.yml`), no estilo schema/description do
dbt (`description:` + `columns: {nome: descricao}`). Motivo: parsing trivial,
sem regex sobre SQL, formato ja familiar (dbt-like) caso o repo adote dbt no
futuro -- o custo de mais um arquivo por view foi aceito. Os YAMLs ja existem
manualmente para as views documentadas em `docs/gold_layer_design.md`
("Inventario Atual"); este script ainda nao os le.

A opcao (A) -- bloco de comentario estruturado no topo do `.sql`
(`-- description: ...` / `-- column.<nome>: ...`) -- foi descartada por
misturar metadado de documentacao com o arquivo executavel que o
`apply_ddl.py` aplica literalmente. O esqueleto abaixo (`parse_descriptions`,
`DESCRIPTION_RE`, `COLUMN_DESCRIPTION_RE`) ainda implementa (A) apenas a
titulo de exemplo historico de como o rascunho comecou -- **nao reflete mais
a decisao** e precisa ser reescrito para ler os `.yml` irmaos (Opcao B) antes
deste script ser considerado pronto para uso. Ver "Uso pretendido" abaixo --
continua nao validado, a logica funcional nao foi implementada nesta correcao
de docstring.

Uso pretendido (nao validado)
------------------------------
    # Mostra o que seria alterado, sem executar nada
    python sync_gold_descriptions.py --env=test --dry-run

    # Aplica contra o projeto de staging (nunca contra adframework direto)
    python sync_gold_descriptions.py --project=douglas-bq-staging --env=test

    # Only depois de validado no staging: promove pra producao
    python sync_gold_descriptions.py --env=prod

Auth: Application Default Credentials, mesmo padrao dos outros scripts do
repo (`gcloud auth application-default login`).
"""

import argparse
import re
import sys
from pathlib import Path

from google.cloud import bigquery

PROJECT_DEFAULT = "adframework"
GOLD_DDL_DIR = Path(__file__).resolve().parent.parent.parent / "gold" / "ddl"

# Opcao (A): bloco de comentario estruturado no topo do arquivo.
# `-- description: <texto>` (nivel de view/tabela)
# `-- column.<nome>: <texto>` (nivel de coluna)
DESCRIPTION_RE = re.compile(r"^\s*--\s*description:\s*(.+)$", re.IGNORECASE)
COLUMN_DESCRIPTION_RE = re.compile(r"^\s*--\s*column\.(\w+):\s*(.+)$", re.IGNORECASE)

# Mesmo padrao de deteccao de alvo usado em scripts/deploy/apply_ddl.py --
# reutilizar aquela regex/logica se este rascunho for adiante, em vez de
# duplicar (nao duplicado aqui de proposito, so pra manter o rascunho
# autocontido e facil de ler isoladamente).
CREATE_STATEMENT_RE = re.compile(
    r"""
    CREATE \s+ (?:OR \s+ REPLACE \s+)?
    (?:VIEW | TABLE | MATERIALIZED \s+ VIEW)
    \s+
    `?(?P<project>[\w-]+)\.(?P<dataset>\w+)\.(?P<object>\w+)`?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def parse_descriptions(sql_text: str):
    """Le o bloco de comentarios no TOPO do arquivo (para de procurar assim
    que encontrar a primeira linha que nao seja comentario nem em branco --
    mesma convencao de `apply_ddl.parse_cascade_directive`). Retorna
    (view_description: str|None, column_descriptions: dict[str, str])."""
    view_description = None
    column_descriptions = {}
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m_view = DESCRIPTION_RE.match(stripped)
        if m_view:
            view_description = m_view.group(1).strip()
            continue
        m_col = COLUMN_DESCRIPTION_RE.match(stripped)
        if m_col:
            column_descriptions[m_col.group(1).strip()] = m_col.group(2).strip()
            continue
        if not stripped.startswith("--"):
            break
    return view_description, column_descriptions


def find_creation_target(sql_text: str):
    match = CREATE_STATEMENT_RE.search(sql_text)
    if not match:
        return None
    return match.group("project"), match.group("dataset"), match.group("object")


def build_alter_statements(project: str, dataset: str, object_name: str,
                            view_description: str, column_descriptions: dict):
    """Monta as instrucoes SET OPTIONS -- NUNCA executadas por esta funcao,
    so retornadas como texto para quem chamar decidir (dry-run vs execucao)."""
    statements = []
    fq_name = f"`{project}.{dataset}.{object_name}`"
    if view_description:
        escaped = view_description.replace("'", "\\'")
        statements.append(
            f"ALTER VIEW {fq_name} SET OPTIONS(description = '{escaped}');"
        )
    for column, description in column_descriptions.items():
        escaped = description.replace("'", "\\'")
        statements.append(
            f"ALTER TABLE {fq_name} ALTER COLUMN {column} "
            f"SET OPTIONS(description = '{escaped}');"
        )
        # Nota: BigQuery usa `ALTER TABLE ... ALTER COLUMN` mesmo para
        # colunas de VIEW -- nao verificado nesta rodada (rascunho), so
        # assumido a partir da documentacao publica do BQ. CONFIRMAR contra
        # staging antes de usar de verdade.
    return statements


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=PROJECT_DEFAULT)
    parser.add_argument("--env", choices=["test", "prod"], required=True)
    parser.add_argument("--dry-run", action="store_true", default=True,
                         help="Default True neste rascunho -- execucao real exige --no-dry-run explicito, ainda nao implementado de proposito.")
    args = parser.parse_args()

    print(
        "[sync_gold_descriptions] RASCUNHO NAO TESTADO -- este script nunca "
        "rodou contra producao. Saindo sem fazer nada ate a decisao de "
        "formato (bloco SQL vs YAML) ser confirmada pelo Douglas. "
        "Ver docstring do arquivo.",
        file=sys.stderr,
    )
    sys.exit(2)

    # --- codigo abaixo nao e alcancado -- esqueleto do fluxo pretendido ---
    if not GOLD_DDL_DIR.exists():
        print(f"Diretorio nao encontrado: {GOLD_DDL_DIR}", file=sys.stderr)
        sys.exit(1)

    all_statements = []
    for sql_file in sorted(GOLD_DDL_DIR.glob("*.sql")):
        sql_text = sql_file.read_text(encoding="utf-8")
        target = find_creation_target(sql_text)
        if not target:
            print(f"[sync_gold_descriptions] Aviso: sem CREATE reconhecido em {sql_file.name}, pulando.")
            continue
        project, dataset, object_name = target
        view_description, column_descriptions = parse_descriptions(sql_text)
        if not view_description and not column_descriptions:
            continue
        statements = build_alter_statements(
            args.project, dataset, object_name, view_description, column_descriptions
        )
        all_statements.extend(statements)

    print(f"[sync_gold_descriptions] {len(all_statements)} instrucao(oes) ALTER geradas:")
    for stmt in all_statements:
        print(f"  {stmt}")

    if args.dry_run:
        print("[sync_gold_descriptions] --dry-run: nada foi executado.")
        return

    bq_client = bigquery.Client(project=args.project)
    for stmt in all_statements:
        job = bq_client.query(stmt)
        job.result()
    print("[sync_gold_descriptions] OK -- descricoes aplicadas.")


if __name__ == "__main__":
    main()
