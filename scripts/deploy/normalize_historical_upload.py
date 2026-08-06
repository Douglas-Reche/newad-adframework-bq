#!/usr/bin/env python3
"""
normalize_historical_upload.py -- etapa 4 do fluxo "dado historico por
cliente": normalizacao versionada por cliente
--------------------------------------------------------------------------
Irma de load_historical_raw.py e load_historical_override.py (mesmo
diretorio, mesmo padrao de CLI). Fecha a lacuna entre as duas:

    etapa 2 (load_historical_raw.py)          etapa 4 (ESTE SCRIPT)              etapa 5 (load_historical_override.py)
    planilha crua                     -->     raw.historical_uploads      -->    CSV normalizado         -->   stg.historical_overrides_delivery
    (qualquer formato)                        (dump JSON literal)                (schema fixo)                 (tabela final)

O que este script faz
----------------------
1. Recebe um --upload-id (de raw.historical_uploads_meta, gerado pela
   etapa 2).
2. Busca o client_id e as linhas cruas em douglas-bq-staging.raw.* (sempre
   staging -- raw.historical_uploads so existe fisicamente la, mesma
   excecao documentada em load_historical_raw.py).
3. Importa scripts/deploy/historical_mappings/<client_id_sanitizado>.py e
   chama a funcao normalize(raw_rows) exportada por ele.
4. Valida que a saida tem exatamente as colunas que
   load_historical_override.py espera (REQUIRED_COLUMNS, importado direto
   desse modulo -- fonte unica, nao duplicada aqui).
5. Escreve um CSV pronto para scripts/deploy/load_historical_override.py.

O que este script NAO faz -- IMPORTANTE
-----------------------------------------
Nao insere nada em stg.historical_overrides_delivery. O CSV gerado ainda
precisa passar por load_historical_override.py (com --dry-run primeiro,
como sempre) -- dois passos deliberadamente separados, mesmo padrao de
"cada script faz uma coisa" do restante deste diretorio.

Se nao existir mapeamento pra um client_id, este script FALHA -- nunca tenta
adivinhar ou aplicar um mapeamento generico. A mensagem de erro diz
exatamente qual arquivo criar.

Uso
---
    python normalize_historical_upload.py \\
        --upload-id 39a0d9be-1ca8-4d41-b774-cc30489d2286 \\
        --output normalized_teste_agente_backend_xyz.csv

Auth: Application Default Credentials (mesmo padrao dos scripts irmaos).
Sempre le de douglas-bq-staging -- sem flag --project, mesma razao de
load_historical_raw.py (a tabela raw so existe fisicamente ali).
"""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

PROJECT_FIXED = "douglas-bq-staging"
TABLE_UPLOADS = "raw.historical_uploads"
TABLE_META = "raw.historical_uploads_meta"

MAPPINGS_DIR = Path(__file__).parent / "historical_mappings"

# Reaproveita a lista canonica de load_historical_override.py -- fonte
# unica, para nao divergir se aquele schema mudar.
sys.path.insert(0, str(Path(__file__).parent))
from load_historical_override import REQUIRED_COLUMNS  # noqa: E402


def _sanitize_module_name(client_id: str) -> str:
    """client_id -> nome de modulo Python valido. Mapeamentos reais ate
    agora ja sao snake_case valido (ex: banco_cora_fe13d78a); esta funcao
    e so uma rede de seguranca para client_ids com caracteres invalidos
    como identificador Python (hifen, espaco, etc)."""
    name = re.sub(r"[^0-9a-zA-Z_]", "_", client_id)
    if name and name[0].isdigit():
        name = f"_{name}"
    return name


def load_mapping_module(client_id: str):
    module_name = _sanitize_module_name(client_id)
    module_path = MAPPINGS_DIR / f"{module_name}.py"
    if not module_path.exists():
        raise SystemExit(
            f"[normalize_historical_upload] ERRO: nao existe mapeamento de "
            f"normalizacao para client_id={client_id!r}. "
            f"Esperado em: {module_path}. "
            f"Este script nao adivinha mapeamento -- crie o arquivo "
            f"(ver historical_mappings/__init__.py para o contrato de "
            f"normalize(raw_rows) -> list[dict], e "
            f"historical_mappings/teste_agente_backend_xyz.py como exemplo)."
        )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "normalize"):
        raise SystemExit(
            f"[normalize_historical_upload] ERRO: {module_path} nao exporta "
            f"uma funcao normalize(raw_rows) -> list[dict]."
        )
    return module


def fetch_upload(bq_client: bigquery.Client, upload_id: str):
    meta_query = f"""
        SELECT client_id, source_filename, column_names, row_count
        FROM `{PROJECT_FIXED}.{TABLE_META}`
        WHERE upload_id = @upload_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("upload_id", "STRING", upload_id)]
    )
    meta_rows = list(bq_client.query(meta_query, job_config=job_config).result())
    if not meta_rows:
        raise SystemExit(
            f"[normalize_historical_upload] ERRO: upload_id={upload_id!r} nao "
            f"encontrado em {PROJECT_FIXED}.{TABLE_META}."
        )
    if len(meta_rows) > 1:
        raise SystemExit(
            f"[normalize_historical_upload] ERRO: upload_id={upload_id!r} tem "
            f"{len(meta_rows)} linhas de metadado -- esperado exatamente 1 "
            f"(upload_id deveria ser unico, ver raw/ddl/historical_uploads_meta.sql)."
        )
    meta = meta_rows[0]

    rows_query = f"""
        SELECT row_number, raw_row
        FROM `{PROJECT_FIXED}.{TABLE_UPLOADS}`
        WHERE upload_id = @upload_id
        ORDER BY row_number
    """
    raw_rows_result = list(bq_client.query(rows_query, job_config=job_config).result())
    if not raw_rows_result:
        raise SystemExit(
            f"[normalize_historical_upload] ERRO: upload_id={upload_id!r} existe em "
            f"{TABLE_META} mas nao tem nenhuma linha em {TABLE_UPLOADS}."
        )
    if len(raw_rows_result) != int(meta.row_count):
        print(
            f"[normalize_historical_upload] AVISO: {TABLE_META}.row_count="
            f"{meta.row_count} mas {len(raw_rows_result)} linha(s) encontradas em "
            f"{TABLE_UPLOADS} -- prosseguindo com o que foi encontrado.",
            file=sys.stderr,
        )

    raw_rows = []
    for r in raw_rows_result:
        raw_rows.append({
            "row_number": r.row_number,
            "raw_row": json.loads(r.raw_row),
            "client_id": meta.client_id,
            "source_filename": meta.source_filename,
        })
    return meta.client_id, meta.source_filename, raw_rows


def validate_normalized(rows: list, upload_id: str):
    if not rows:
        raise SystemExit(
            f"[normalize_historical_upload] ERRO: normalize() retornou 0 linhas "
            f"para upload_id={upload_id!r}."
        )
    required = set(REQUIRED_COLUMNS)
    for i, row in enumerate(rows):
        keys = set(row.keys())
        missing = required - keys
        extra = keys - required
        if missing or extra:
            raise SystemExit(
                f"[normalize_historical_upload] ERRO: linha {i} da saida de "
                f"normalize() nao bate com REQUIRED_COLUMNS de "
                f"load_historical_override.py. Faltando: {sorted(missing)}. "
                f"Extra (nao esperado): {sorted(extra)}."
            )
        if row["client_id"] in (None, ""):
            raise SystemExit(
                f"[normalize_historical_upload] ERRO: linha {i} tem client_id vazio."
            )
        if row["day"] in (None, ""):
            raise SystemExit(
                f"[normalize_historical_upload] ERRO: linha {i} tem day vazio."
            )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--upload-id", required=True)
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Caminho do CSV de saida. Default: normalized_<client_id>_<upload_id>.csv no diretorio atual.",
    )
    args = parser.parse_args()

    bq_client = bigquery.Client(project=PROJECT_FIXED)
    client_id, source_filename, raw_rows = fetch_upload(bq_client, args.upload_id)

    print(
        f"[normalize_historical_upload] upload_id={args.upload_id} "
        f"client_id={client_id} source_filename={source_filename} -- "
        f"{len(raw_rows)} linha(s) crua(s) encontradas."
    )

    module = load_mapping_module(client_id)
    normalized_rows = module.normalize(raw_rows)
    validate_normalized(normalized_rows, args.upload_id)

    df = pd.DataFrame(normalized_rows)[REQUIRED_COLUMNS]

    output_path = args.output or Path(f"normalized_{_sanitize_module_name(client_id)}_{args.upload_id}.csv")
    df.to_csv(output_path, index=False)

    print(
        f"[normalize_historical_upload] OK -- {len(df)} linha(s) normalizadas "
        f"escritas em {output_path}."
    )
    print("----- preview (ate 5 linhas) -----")
    print(df.head(5).to_string(index=False))
    print(
        f"\n[normalize_historical_upload] Proximo passo: "
        f"python load_historical_override.py {output_path} --project {PROJECT_FIXED} --dry-run"
    )


if __name__ == "__main__":
    main()
