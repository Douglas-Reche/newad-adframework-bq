#!/usr/bin/env python3
"""
apply_ddl.py — Nivel 2 de teste para DDL de gold/core/stg/raw
--------------------------------------------------------------
Aplica um unico arquivo .sql (o mesmo arquivo versionado em raw/ddl, stg/ddl,
core/ddl ou gold/ddl -- nunca uma copia) contra o dataset real (`--env=prod`)
ou contra o dataset `_test` gemeo (`--env=test`), sem duplicar DDL em pastas
espelhadas.

Por que isso existe
--------------------
A camada `gold` (e boa parte de `core`/`stg`) e compartilhada por todos os
clientes -- toda view e `CREATE OR REPLACE`, nunca materializada. Mudar uma
view direto em producao arrisca o dashboard de qualquer cliente ja ao vivo.
Este script formaliza o metodo ad hoc ja usado manualmente (task "Analisar
resiliencia e rastreabilidade da camada Gold", 2026-08-04): criar uma copia
`_test` do objeto, aplicar, comparar, e so depois promover pra producao
reaplicando o MESMO arquivo com `--env=prod`.

Decisao de design: qual dataset e trocado
-------------------------------------------
Por padrao, so o dataset ALVO da criacao (o `CREATE OR REPLACE VIEW/TABLE/...`
do proprio arquivo) e trocado para `_test`. Qualquer outro dataset que o
arquivo LEIA (ex: uma view em `gold_test` fazendo JOIN em `stg` real)
continua apontando pro dado real -- isso e o proprio Nivel 2: testar a
LOGICA da regra/view isoladamente, sem precisar replicar dado nenhum.

Quando o teste precisar ser mais profundo (ex: uma mudanca de STG que precisa
ser validada ponta-a-ponta antes de a view gold ler dela), o arquivo pode
declarar explicitamente quais datasets adicionais devem ser redirecionados
para as suas versoes `_test` quando `--env=test`, via um comentario na
PRIMEIRA linha do arquivo que comecar com `-- apply_ddl: cascade=`:

    -- apply_ddl: cascade=stg,core

Isso evita hardcode no script (o autor do arquivo decide, arquivo por
arquivo) e evita reescrever o SQL toda vez que so a logica interna do
arquivo mudar (o comentario e metadado, nao dado). Ausencia do comentario =
comportamento padrao (so o alvo da criacao troca).

`--env=prod` roda o arquivo exatamente como esta no git, sem nenhuma
substituicao.

Registro de auditoria
----------------------
Toda execucao (test OU prod) grava uma linha em `core.schema_change_log`
(sempre no dataset `core` real -- nunca em `core_test`, e o log de tudo que
foi tentado nao pode desaparecer se o teste for descartado). O script
preenche sozinho `object_dataset`/`object_name`/`tested_env`/`tested_at`/
`requested_by`/`status`; `reason` e `change_summary` (o "por que" e o "o que
mudou" em linguagem simples) sao opcionais via flag -- preenchimento mais
rico pode ser feito depois com um UPDATE manual na linha, usando
`change_id` como chave.

Uso
---
    # Testa uma view em gold_test, sem tocar em gold real
    python apply_ddl.py ../../gold/ddl/fact_io_plan.sql --env=test

    # Depois de validar, promove o MESMO arquivo pra producao
    python apply_ddl.py ../../gold/ddl/fact_io_plan.sql --env=prod \\
        --reason="Corrige duplo-count de unit_price" \\
        --summary="fact_io_plan agora usa SUM ao inves de MAX para unit_price"

    # Ve o SQL final sem executar nada (debug)
    python apply_ddl.py ../../gold/ddl/fact_io_plan.sql --env=test --dry-run

Auth: usa Application Default Credentials (mesma auth do `bq`/outros scripts
do repo -- `gcloud auth application-default login`).

--project e o projeto douglas-bq-staging
--------------------------------------------
2026-08-05 -- `--project` passou a suportar apontar para um projeto GCP
inteiramente separado (ex: `douglas-bq-staging`), nao so o dataset `_test`
gemeo dentro do projeto `adframework`. Datasets nesse projeto usam os
MESMOS nomes de producao (`raw`/`stg`/`core`/`gold`, sem sufixo `_test`) --
o projeto inteiro ja significa "isto e teste", entao quando `--project`
difere do default NENHUM sufixo `_test` e aplicado: o arquivo .sql e
aplicado como esta, so trocando o project id literal nos identificadores
totalmente qualificados (`adframework.dataset.objeto` -> `{seu-projeto}.
dataset.objeto`).

Rollback
--------
Antes de aplicar em `--env=prod`, o script tenta capturar a definicao
ATUAL do objeto (se ja existir) via INFORMATION_SCHEMA e grava em
`core.schema_change_log.previous_definition`. `--rollback <change_id>`
le essa coluna daquela linha e reaplica a definicao antiga, registrando
uma nova linha de auditoria (nunca apagando a linha original). Se a linha
nao tiver `previous_definition` (objeto era novo naquela execucao, ou a
captura falhou), o rollback aborta com erro em vez de aplicar algo vazio.

commit_hash
-----------
Toda execucao tenta capturar `git rev-parse HEAD` (do repo que contem o
arquivo .sql) e grava em `core.schema_change_log.commit_hash`. Falha
silenciosa se nao estiver num repo git -- nao bloqueia o deploy.
"""

import argparse
import getpass
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import bigquery

PROJECT_DEFAULT = "adframework"
LAYER_DATASETS = ("raw", "stg", "core", "gold")

# Datasets que sao fisicamente espelhados dentro do projeto alt (--project),
# ex: douglas-bq-staging.raw, douglas-bq-staging.stg, douglas-bq-staging.core,
# douglas-bq-staging.gold -- referencias CRUZADAS (um arquivo de gold fazendo
# JOIN em stg, por exemplo) so devem trocar de projeto quando o dataset lido
# tambem existe fisicamente la. Isso e conceitualmente DIFERENTE de "qual
# dataset e o ALVO do CREATE deste arquivo" (ver swap_project) -- o alvo
# sempre troca de projeto quando --project e usado, nao importa o dataset;
# esta lista so serve para decidir REFERENCIAS CRUZADAS dentro do arquivo.
#
# Historico: ate 2026-08-05, raw/stg nunca eram fisicamente replicados (so
# core/gold), entao ficavam de fora desta lista de proposito -- uma leitura
# cross-project deliberada sempre apontando pra producao. Bug real encontrado
# em 2026-08-05: swap_project() trocava TODAS as ocorrencias literais de
# `adframework.`, inclusive `adframework.stg.ms_delivery` ->
# `douglas-bq-staging.stg.ms_delivery` (tabela que nao existia la na epoca).
#
# 2026-08-06: `douglas-bq-staging` virou standalone de verdade -- raw e
# copiado fisicamente via `bq cp` e stg/core/gold rodam 100% locais, sem
# NENHUMA leitura cross-project a producao. raw/stg entram na lista.
#
# Bug real corrigido nesta mesma data: antes, so as REFERENCIAS CRUZADAS
# eram redirecionadas por esta lista -- o ALVO do CREATE (ex: um arquivo de
# stg/ddl, dataset "stg", que nao estava na lista antiga {core, gold}) NUNCA
# era redirecionado. Isso significava que `apply_ddl.py stg/ddl/x.sql
# --project douglas-bq-staging` gerava uma query cujo CREATE ainda citava
# `adframework.stg.x` (produção real) -- o billing project era
# douglas-bq-staging, mas o objeto criado/sobrescrito era o de producao.
# Corrigido separando os dois conceitos: veja swap_project().
ALT_PROJECT_MIRRORED_DATASETS = set(LAYER_DATASETS)  # {"raw", "stg", "core", "gold"}

# Reconhece o layer (raw/stg/core/gold) a partir da pasta que contem o
# arquivo (ex: .../gold/ddl/fact_io_plan.sql -> "gold", ou o mesmo caminho
# relativo sem separador na frente: "gold/ddl/fact_io_plan.sql"). E so um
# fallback usado para o log de auditoria quando a propria instrucao CREATE
# nao for encontrada no arquivo (ex: um ALTER TABLE isolado, como
# core/ddl/historical_overrides_delivery.sql, ou um arquivo com apenas
# comentarios de topo, ou um GRANT avulso). `(?:^|[\\/])` -- e nao so
# `[\\/]` -- para tambem casar quando o caminho passado e relativo e
# COMECA direto pela pasta do dataset (ex: "core/ddl/x.sql"), sem barra
# antes de "core" -- bug real encontrado ao testar --dry-run em 2026-08-05
# (path relativo nao batia, layer voltava None, --env=test abortava com
# "Nao foi possivel determinar o dataset" mesmo para arquivo valido).
LAYER_FROM_PATH_RE = re.compile(
    r"(?:^|[\\/])(raw|stg|core|gold)[\\/]ddl[\\/]", re.IGNORECASE
)

# Casa a instrucao de criacao (CREATE [OR REPLACE] VIEW|TABLE|MATERIALIZED
# VIEW|FUNCTION|TABLE FUNCTION `project.dataset.object`) e captura os 3
# componentes do identificador para sabermos exatamente qual dataset e o
# ALVO da criacao (o unico que --env=test deve redirecionar por padrao).
CREATE_STATEMENT_RE = re.compile(
    r"""
    CREATE \s+ (?:OR \s+ REPLACE \s+)?
    (?:VIEW | TABLE | MATERIALIZED \s+ VIEW | FUNCTION | TABLE \s+ FUNCTION | SCHEMA)
    \s+
    `?(?P<project>[\w-]+)\.(?P<dataset>\w+)\.(?P<object>\w+)`?
    """,
    re.IGNORECASE | re.VERBOSE,
)

CASCADE_DIRECTIVE_RE = re.compile(
    r"^\s*--\s*apply_ddl:\s*cascade\s*=\s*([\w,\s]+)\s*$", re.IGNORECASE
)


def parse_cascade_directive(sql_text: str) -> set:
    """Le a primeira linha nao-vazia do arquivo procurando o comentario
    `-- apply_ddl: cascade=stg,core`. Retorna o conjunto de datasets extras
    (alem do alvo da criacao) que devem ser redirecionados para `_test`
    quando --env=test. Vazio se o arquivo nao declarar nada (padrao)."""
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = CASCADE_DIRECTIVE_RE.match(stripped)
        if match:
            names = {n.strip().lower() for n in match.group(1).split(",")}
            invalid = names - set(LAYER_DATASETS)
            if invalid:
                raise ValueError(
                    f"cascade= invalido: {invalid} -- valores aceitos: {LAYER_DATASETS}"
                )
            return names
        # Para de procurar assim que a primeira linha nao-comentario aparecer
        # -- a diretiva so vale se estiver no topo do arquivo (metadado, nao
        # deve ficar perdida no meio do SQL).
        if not stripped.startswith("--"):
            break
    return set()


def find_creation_target(sql_text: str):
    """Retorna (project, dataset, object, match_span) da instrucao CREATE
    do arquivo, ou None se nao encontrar (arquivo sem CREATE reconhecido)."""
    match = CREATE_STATEMENT_RE.search(sql_text)
    if not match:
        return None
    return match.group("project"), match.group("dataset"), match.group("object"), match.span()


def layer_from_path(file_path: Path) -> str:
    match = LAYER_FROM_PATH_RE.search(str(file_path))
    return match.group(1).lower() if match else None


def swap_project(sql_text: str, from_project: str, to_project: str, creation_dataset: str = None) -> str:
    """Troca o project id literal em identificadores totalmente
    qualificados (com ou sem backtick de abertura), preservando dataset e
    objeto intactos. Usado quando --project aponta para um projeto GCP
    separado (ex: douglas-bq-staging) -- nesse caso o projeto inteiro ja
    significa "teste", entao NAO aplicamos o sufixo `_test` de dataset
    (ver build_test_sql), so redirecionamos o project id.

    Dois conceitos SEPARADOS, de proposito (bug corrigido em 2026-08-06 --
    ver comentario de ALT_PROJECT_MIRRORED_DATASETS):

    (a) O dataset ALVO da criacao (`creation_dataset`, o dataset do proprio
        `CREATE OR REPLACE ...` deste arquivo) SEMPRE troca de projeto quando
        este parametro e informado, nao importa se esse dataset esta ou nao
        em ALT_PROJECT_MIRRORED_DATASETS. O objeto tem que ser fisicamente
        criado/sobrescrito no projeto passado em --project, sempre -- nunca
        em producao, mesmo que a lista de mirrored datasets um dia fique
        desatualizada.

    (b) REFERENCIAS CRUZADAS (outros datasets que o arquivo LE, ex: uma view
        de gold fazendo JOIN em stg) so trocam de projeto se esse dataset
        tambem estiver em ALT_PROJECT_MIRRORED_DATASETS (fisicamente presente
        no projeto alvo). Um dataset fora dessa lista fica apontando de
        proposito pro projeto de producao (`from_project`) -- leitura
        cross-project deliberada.
    """
    datasets_to_swap = set(ALT_PROJECT_MIRRORED_DATASETS)
    if creation_dataset:
        datasets_to_swap.add(creation_dataset)
    for dataset in datasets_to_swap:
        pattern = re.compile(
            rf"`?{re.escape(from_project)}\.{re.escape(dataset)}\.", re.IGNORECASE
        )
        sql_text = pattern.sub(f"`{to_project}.{dataset}.", sql_text)
    return sql_text


def get_git_commit_hash(file_path: Path) -> str:
    """git rev-parse HEAD do repo que contem file_path. Retorna None (nunca
    levanta excecao) se o arquivo nao estiver dentro de um repo git, se o
    git nao estiver instalado, ou qualquer outra falha -- commit_hash e
    metadado de auditoria opcional, nunca motivo para abortar um deploy."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(file_path.resolve().parent),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def fetch_current_definition(bq_client: bigquery.Client, project: str, dataset: str, object_name: str):
    """Melhor esforco para capturar a definicao ATUAL de um objeto antes de
    sobrescreve-lo, para permitir --rollback depois. Tenta
    INFORMATION_SCHEMA.TABLES.ddl primeiro (cobre TABLE/VIEW/MATERIALIZED
    VIEW), depois INFORMATION_SCHEMA.ROUTINES.ddl (cobre FUNCTION/TABLE
    FUNCTION). Retorna None se o objeto nao existir ainda (primeira
    criacao -- nao ha "antes" para capturar) ou se a query falhar por
    qualquer motivo (nunca levanta excecao -- nao pode bloquear o deploy
    em si por causa de uma captura de auditoria)."""
    try:
        query = f"""
            SELECT ddl
            FROM `{project}.{dataset}.INFORMATION_SCHEMA.TABLES`
            WHERE table_name = @object_name
        """
        job = bq_client.query(
            query,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("object_name", "STRING", object_name)]
            ),
        )
        rows = list(job.result())
        if rows and rows[0].get("ddl"):
            return rows[0]["ddl"]
    except Exception as e:
        print(f"[apply_ddl] AVISO: falha ao consultar INFORMATION_SCHEMA.TABLES para captura de rollback: {e}", file=sys.stderr)

    try:
        query = f"""
            SELECT ddl
            FROM `{project}.{dataset}.INFORMATION_SCHEMA.ROUTINES`
            WHERE routine_name = @object_name
        """
        job = bq_client.query(
            query,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("object_name", "STRING", object_name)]
            ),
        )
        rows = list(job.result())
        if rows and rows[0].get("ddl"):
            return rows[0]["ddl"]
    except Exception as e:
        print(f"[apply_ddl] AVISO: falha ao consultar INFORMATION_SCHEMA.ROUTINES para captura de rollback: {e}", file=sys.stderr)

    return None


def build_test_sql(sql_text: str, project: str, creation_dataset: str, cascade: set) -> str:
    """Constroi o SQL final para --env=test:
    - substitui o dataset do ALVO da criacao (creation_dataset) por
      `{creation_dataset}_test` em TODAS as ocorrencias literais de
      `{project}.{creation_dataset}.` (cobre o CREATE em si e qualquer
      auto-referencia, ex: uma funcao SQL que se chama recursivamente).
    - para cada dataset em `cascade`, faz a mesma substituicao -- essas sao
      leituras que o autor do arquivo marcou explicitamente como devendo
      apontar pro ambiente de teste tambem.
    - qualquer outro dataset mencionado no arquivo (nao e o alvo nem esta em
      cascade) fica intocado -- e uma leitura deliberada do dado real.
    """
    result = sql_text
    datasets_to_redirect = {creation_dataset} | cascade
    for dataset in datasets_to_redirect:
        pattern = re.compile(
            rf"`?{re.escape(project)}\.{re.escape(dataset)}\.", re.IGNORECASE
        )
        result = pattern.sub(f"`{project}.{dataset}_test.", result)
    return result


def log_change(
    bq_client: bigquery.Client,
    project: str,
    object_dataset: str,
    object_name: str,
    env: str,
    reason: str,
    summary: str,
    requested_by: str,
    previous_definition: str = None,
    commit_hash: str = None,
    status_override: str = None,
) -> str:
    now = datetime.now(timezone.utc)
    status = status_override or ("promoted" if env == "prod" else "testing")
    change_id = str(uuid.uuid4())
    row = {
        "change_id": change_id,
        "object_dataset": object_dataset,
        "object_name": object_name,
        "change_summary": summary,
        "reason": reason,
        "requested_by": requested_by,
        "tested_at": now.isoformat(),
        "tested_env": env,
        "approved_by": None,
        "promoted_at": now.isoformat() if env == "prod" else None,
        "status": status,
        "previous_definition": previous_definition,
        "commit_hash": commit_hash,
    }
    # Log SEMPRE no core real do projeto informado -- nunca em core_test --
    # o registro de "o que foi tentado" nao pode desaparecer se o teste for
    # descartado (ver header do modulo). Quando --project e um projeto
    # separado (douglas-bq-staging), o log fica no core desse projeto (ele
    # e self-contained -- precisa ter a propria core.schema_change_log
    # aplicada la, ver core/ddl/schema_change_log.sql).
    errors = bq_client.insert_rows_json(f"{project}.core.schema_change_log", [row])
    if errors:
        print(f"[apply_ddl] AVISO: falha ao gravar em core.schema_change_log: {errors}", file=sys.stderr)
    else:
        print(f"[apply_ddl] Log gravado em core.schema_change_log (change_id={change_id}, status={status})")
    return change_id


def do_rollback(bq_client: bigquery.Client, project: str, change_id: str, requested_by: str):
    """Le previous_definition da linha change_id em core.schema_change_log
    e reaplica. Aborta (sem tocar em nada) se a linha nao existir ou nao
    tiver previous_definition capturado."""
    query = """
        SELECT object_dataset, object_name, previous_definition
        FROM `{project}.core.schema_change_log`
        WHERE change_id = @change_id
        ORDER BY tested_at DESC
        LIMIT 1
    """.format(project=project)
    job = bq_client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("change_id", "STRING", change_id)]
        ),
    )
    rows = list(job.result())
    if not rows:
        print(f"[apply_ddl] ERRO: change_id={change_id} nao encontrado em {project}.core.schema_change_log", file=sys.stderr)
        sys.exit(1)

    row = rows[0]
    previous_definition = row["previous_definition"]
    if not previous_definition:
        print(
            f"[apply_ddl] ERRO: change_id={change_id} nao tem previous_definition capturado "
            f"(objeto era novo naquela execucao, ou a captura falhou) -- nao ha nada seguro "
            f"para reaplicar. Rollback abortado.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[apply_ddl] Rollback de change_id={change_id} -- reaplicando definicao anterior de {row['object_dataset']}.{row['object_name']}:")
    print(previous_definition)

    # Trava de nivel 2, mesma logica do fluxo principal de --env=prod (ver
    # main()): rollback SEMPRE escreve em producao (nao existe rollback
    # "de teste"), entao nenhuma reaplicacao pode acontecer sem uma pessoa
    # digitando ao vivo num terminal interativo. De proposito NAO existe
    # flag de bypass (--yes/--force). Um ambiente nao-interativo (CI, agente
    # de IA sem terminal humano) recebe EOF no input() abaixo e portanto
    # falha a confirmacao automaticamente.
    print("=" * 70, file=sys.stderr)
    print("[apply_ddl] CONFIRMACAO OBRIGATORIA -- ROLLBACK EM PRODUCAO", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"  Projeto:     {project}", file=sys.stderr)
    print(f"  Change ID:   {change_id}", file=sys.stderr)
    print(f"  Dataset:     {row['object_dataset']}", file=sys.stderr)
    print(f"  Objeto:      {row['object_name']}", file=sys.stderr)
    print("----- Preview da definicao anterior a ser reaplicada -----", file=sys.stderr)
    print(previous_definition, file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    try:
        confirmation = input(
            f"Digite o nome exato do objeto ({row['object_name']}) para confirmar "
            f"o ROLLBACK em PRODUCAO, ou qualquer outra coisa para abortar: "
        )
    except EOFError:
        print(
            "[apply_ddl] ABORTADO -- input() recebeu EOF (ambiente nao-interativo, "
            "sem terminal humano para confirmar). Nenhuma alteracao foi aplicada.",
            file=sys.stderr,
        )
        sys.exit(1)
    if confirmation.strip() != row["object_name"]:
        print(
            f"[apply_ddl] ABORTADO -- confirmacao '{confirmation.strip()}' nao "
            f"corresponde ao objeto esperado '{row['object_name']}'. Nenhuma alteracao "
            f"foi aplicada.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"[apply_ddl] Confirmado -- prosseguindo com ROLLBACK em PRODUCAO.")

    query_job = bq_client.query(previous_definition)
    query_job.result()
    print(f"[apply_ddl] OK -- rollback aplicado.")

    log_change(
        bq_client=bq_client,
        project=project,
        object_dataset=row["object_dataset"],
        object_name=row["object_name"],
        env="prod",
        reason=f"Rollback de change_id={change_id}",
        summary=f"Reaplicada a definicao anterior a change_id={change_id}",
        requested_by=requested_by,
        status_override="promoted",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "sql_file", type=Path, nargs="?", default=None,
        help="Caminho do .sql (raw/ddl, stg/ddl, core/ddl ou gold/ddl). Nao usado com --rollback.",
    )
    parser.add_argument("--env", choices=["test", "prod"], help="Obrigatorio exceto com --rollback")
    parser.add_argument("--project", default=PROJECT_DEFAULT, help="Default: adframework (producao). Um projeto diferente (ex: douglas-bq-staging) e tratado como projeto de teste inteiro -- sem sufixo _test.")
    parser.add_argument("--reason", default=None, help="Por que essa mudanca (texto livre, opcional)")
    parser.add_argument("--summary", default=None, help="O que mudou, em linguagem simples (opcional)")
    parser.add_argument("--requested-by", default=None, help="Default: usuario do SO local")
    parser.add_argument("--dry-run", action="store_true", help="So imprime o SQL final, nao executa nem loga")
    parser.add_argument("--no-log", action="store_true", help="Pula o INSERT em core.schema_change_log (uso: debug)")
    parser.add_argument("--rollback", metavar="CHANGE_ID", default=None, help="Reaplica a previous_definition gravada para essa change_id em core.schema_change_log, em vez de aplicar um arquivo novo")
    args = parser.parse_args()

    requested_by = args.requested_by or getpass.getuser()

    # --- Modo rollback: caminho totalmente separado, nao le sql_file ---
    if args.rollback:
        if args.dry_run:
            print(f"[apply_ddl] --dry-run com --rollback: nao ha SQL local para mostrar -- a definicao "
                  f"a reaplicar so e conhecida depois de consultar core.schema_change_log (precisa de credencial). "
                  f"Rode sem --dry-run para ver + confirmar antes de continuar.")
            return
        bq_client = bigquery.Client(project=args.project)
        do_rollback(bq_client, args.project, args.rollback, requested_by)
        return

    if not args.env:
        print("--env e obrigatorio (exceto com --rollback).", file=sys.stderr)
        sys.exit(1)
    if not args.sql_file:
        print("sql_file e obrigatorio (exceto com --rollback).", file=sys.stderr)
        sys.exit(1)
    if not args.sql_file.exists():
        print(f"Arquivo nao encontrado: {args.sql_file}", file=sys.stderr)
        sys.exit(1)

    is_alt_project = args.project != PROJECT_DEFAULT
    sql_text = args.sql_file.read_text(encoding="utf-8")

    # Acha o alvo do CREATE ANTES de qualquer swap de projeto -- precisamos
    # do creation_dataset original (ex: "stg") para passar pra swap_project()
    # e garantir que o ALVO da criacao sempre redirecione pro --project
    # informado, nao so as referencias cruzadas (ver bug corrigido
    # 2026-08-06 no header de ALT_PROJECT_MIRRORED_DATASETS / swap_project).
    creation = find_creation_target(sql_text)

    if creation:
        creation_project, creation_dataset, creation_object, _ = creation
    else:
        # Fallback: nao achou um CREATE reconhecido no arquivo -- ainda assim
        # tentamos inferir o dataset a partir da pasta, so para o log de
        # auditoria ficar util. Sem instrucao CREATE identificavel, --env=test
        # nao troca nada (nao ha um "alvo" seguro para redirecionar) a menos
        # que o arquivo use cascade= explicitamente.
        creation_project, creation_dataset, creation_object = args.project, layer_from_path(args.sql_file), args.sql_file.stem
        print(
            "[apply_ddl] AVISO: nenhuma instrucao CREATE reconhecida no arquivo -- "
            "em --env=test, nenhuma substituicao automatica de dataset-alvo sera feita "
            "(so cascade=, se declarado). Em --project alternativo, o ALVO tambem nao "
            "sera redirecionado automaticamente -- so cascade= ou referencias a datasets "
            "em ALT_PROJECT_MIRRORED_DATASETS.",
            file=sys.stderr,
        )

    if is_alt_project:
        sql_text = swap_project(sql_text, PROJECT_DEFAULT, args.project, creation_dataset=creation_dataset)
        creation_project = args.project
        print(
            f"[apply_ddl] --project={args.project} (!= default {PROJECT_DEFAULT}): "
            f"tratado como projeto de teste inteiro -- NENHUM sufixo _test sera aplicado "
            f"ao dataset. O ALVO do CREATE ({creation_dataset}) SEMPRE foi redirecionado "
            f"para este projeto; referencias cruzadas so foram redirecionadas para "
            f"datasets em ALT_PROJECT_MIRRORED_DATASETS={sorted(ALT_PROJECT_MIRRORED_DATASETS)}."
        )

    commit_hash = get_git_commit_hash(args.sql_file)

    cascade = parse_cascade_directive(sql_text)

    if args.env == "test":
        if creation_dataset is None:
            print("Nao foi possivel determinar o dataset (nem por CREATE nem pelo caminho do arquivo).", file=sys.stderr)
            sys.exit(1)
        if is_alt_project:
            # O projeto ja significa teste -- nao sufixar o dataset.
            final_sql = sql_text
            log_dataset = creation_dataset
        else:
            final_sql = build_test_sql(sql_text, args.project, creation_dataset, cascade)
            log_dataset = f"{creation_dataset}_test"
    else:
        final_sql = sql_text
        log_dataset = creation_dataset

    if cascade:
        print(f"[apply_ddl] cascade declarado no arquivo: {sorted(cascade)}")

    if args.dry_run:
        print("----- SQL final (dry-run, nada executado) -----")
        print(final_sql)
        return

    bq_client = bigquery.Client(project=args.project)

    # Captura a definicao ATUAL do objeto antes de sobrescreve-la, para
    # permitir --rollback depois. So faz sentido tentar quando sabemos o
    # dataset/objeto alvo real (log_dataset/creation_object) -- melhor
    # esforco, nunca bloqueia o deploy (ver fetch_current_definition).
    previous_definition = None
    if creation_object and log_dataset:
        previous_definition = fetch_current_definition(bq_client, args.project, log_dataset, creation_object)
        if previous_definition:
            print(f"[apply_ddl] Definicao anterior de {log_dataset}.{creation_object} capturada para rollback.")
        else:
            print(f"[apply_ddl] Sem definicao anterior encontrada para {log_dataset}.{creation_object} (objeto novo, ou nao e VIEW/TABLE/FUNCTION reconhecida).")

    if args.env == "prod":
        # Trava de nivel 2: nenhuma aplicacao em producao pode acontecer sem
        # uma pessoa digitando ao vivo num terminal interativo. De proposito
        # NAO existe flag de bypass (--yes/--force) -- ver header do modulo e
        # o relato da task que motivou isto. Um ambiente nao-interativo (CI,
        # agente de IA sem terminal humano) recebe EOF/string vazia no
        # input() abaixo e portanto falha a confirmacao automaticamente.
        print("=" * 70, file=sys.stderr)
        print("[apply_ddl] CONFIRMACAO OBRIGATORIA -- APLICACAO EM PRODUCAO", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(f"  Projeto:  {args.project}", file=sys.stderr)
        print(f"  Dataset:  {log_dataset}", file=sys.stderr)
        print(f"  Objeto:   {creation_object}", file=sys.stderr)
        print(f"  Arquivo:  {args.sql_file}", file=sys.stderr)
        print("----- Preview do SQL final -----", file=sys.stderr)
        print(final_sql, file=sys.stderr)
        print("-" * 70, file=sys.stderr)
        try:
            confirmation = input(
                f"Digite o nome exato do objeto ({creation_object}) para confirmar "
                f"aplicacao em PRODUCAO, ou qualquer outra coisa para abortar: "
            )
        except EOFError:
            print(
                "[apply_ddl] ABORTADO -- input() recebeu EOF (ambiente nao-interativo, "
                "sem terminal humano para confirmar). Nenhuma alteracao foi aplicada.",
                file=sys.stderr,
            )
            sys.exit(1)
        if confirmation.strip() != creation_object:
            print(
                f"[apply_ddl] ABORTADO -- confirmacao '{confirmation.strip()}' nao "
                f"corresponde ao objeto esperado '{creation_object}'. Nenhuma alteracao "
                f"foi aplicada.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"[apply_ddl] Confirmado -- prosseguindo com aplicacao em PRODUCAO.")

    print(f"[apply_ddl] Executando contra --env={args.env} (dataset alvo: {log_dataset})")
    query_job = bq_client.query(final_sql)
    query_job.result()  # espera terminar, propaga erro se a query falhar
    print(f"[apply_ddl] OK -- objeto {log_dataset}.{creation_object} aplicado.")

    if not args.no_log:
        log_change(
            bq_client=bq_client,
            project=args.project,
            object_dataset=creation_dataset,
            object_name=creation_object,
            env=args.env,
            reason=args.reason,
            summary=args.summary,
            requested_by=requested_by,
            previous_definition=previous_definition,
            commit_hash=commit_hash,
        )


if __name__ == "__main__":
    main()
