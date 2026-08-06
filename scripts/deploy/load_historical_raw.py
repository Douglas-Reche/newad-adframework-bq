#!/usr/bin/env python3
"""
load_historical_raw.py — carrega planilha BRUTA (sem nenhuma normalizacao)
em raw.historical_uploads + raw.historical_uploads_meta, em douglas-bq-staging
--------------------------------------------------------------------------
Irma do load_historical_override.py (mesmo diretorio, mesmo padrao de CLI --
--dry-run, preview, mensagens de erro), mas para a etapa ANTES da
normalizacao: recebe o arquivo exatamente como o comercial/cliente mandou
(qualquer nome de coluna, qualquer ordem, qualquer formato de numero/data) e
so pousa o dado, linha a linha, sem tentar interpretar nada.

Ver raw/ddl/historical_uploads.sql e raw/ddl/historical_uploads_meta.sql
para o design completo e o motivo de cada escolha de schema.

O QUE ESTA FERRAMENTA NAO FAZ -- IMPORTANTE
---------------------------------------------
Nao normaliza, nao tipa, nao valida formato de data/numero, nao mapeia
coluna nenhuma. TODAS as colunas do arquivo de entrada sao lidas como
STRING (dtype=str, sem inferencia de tipo do pandas) e guardadas
literalmente. Se o arquivo tiver "1.234,56" (formato BR) ou "31/12/2026",
isso pousa exatamente assim -- e trabalho de outra etapa (Douglas + IA
olhando o Hub) decidir o que aquilo significa.

Diferente de load_historical_override.py, este script SEMPRE grava contra
douglas-bq-staging -- nunca aceita --project apontando pra outro lugar,
porque a tabela raw.historical_uploads so existe fisicamente ali (excecao
deliberada, ver DDL). Nao ha flag --project aqui de proposito.

Uso
---
    # Dry-run -- mostra o que seria inserido, nao grava nada, nao precisa
    # de credencial nem de rede
    python load_historical_raw.py planilha_cora.xlsx --client-id cora_xxxx --dry-run

    # Carrega de fato
    python load_historical_raw.py planilha_cora.csv --client-id cora_xxxx \\
        --uploaded-by douglas

Formato de entrada aceito: .csv, .xlsx ou .xls. Todas as colunas do
arquivo (na ordem em que aparecem) sao preservadas -- nomes de coluna
originais, sem sanitizacao.

Auth: usa Application Default Credentials, mesmo padrao do apply_ddl.py /
load_historical_override.py (`gcloud auth application-default login`).
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

PROJECT_FIXED = "douglas-bq-staging"  # sempre staging -- nao configuravel, ver docstring
TABLE_UPLOADS = "raw.historical_uploads"
TABLE_META = "raw.historical_uploads_meta"


def read_input_file(path: Path) -> pd.DataFrame:
    """Le o arquivo bruto com TODAS as colunas como STRING, sem inferencia
    de tipo nenhuma -- mesmo principio 'RAW = dump literal' do resto do
    pipeline. Preserva a ordem original das colunas do arquivo."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str, keep_default_na=False, na_values=[""])
    else:
        raise ValueError(
            f"Extensao nao suportada: {path.suffix} -- esperado .csv, .xlsx ou .xls"
        )

    if df.empty:
        raise ValueError("Arquivo nao tem nenhuma linha de dado.")

    return df


def build_upload_rows(df: pd.DataFrame, upload_id: str, client_id: str,
                       source_filename: str, uploaded_by: str, uploaded_at: str) -> list:
    """1 linha de raw.historical_uploads por linha do arquivo original.
    raw_row = JSON-text de {coluna_original: valor_como_string_ou_None},
    preservando a ordem original das colunas (dict do Python 3.7+ preserva
    ordem de insercao)."""
    columns = list(df.columns)
    rows = []
    for i, record in enumerate(df.to_dict(orient="records"), start=1):
        raw_row = {col: record.get(col) for col in columns}
        # NaN (celula vazia) nao serializa em JSON valido -- vira None/null.
        raw_row = {k: (None if pd.isna(v) else v) for k, v in raw_row.items()}
        rows.append({
            "upload_id": upload_id,
            "client_id": client_id,
            "source_filename": source_filename,
            "row_number": i,
            "raw_row": json.dumps(raw_row, ensure_ascii=False),
            "uploaded_at": uploaded_at,
            "uploaded_by": uploaded_by,
        })
    return rows


def build_meta_row(df: pd.DataFrame, upload_id: str, client_id: str,
                    source_filename: str, uploaded_by: str, uploaded_at: str) -> dict:
    return {
        "upload_id": upload_id,
        "client_id": client_id,
        "source_filename": source_filename,
        "column_names": list(df.columns),
        "row_count": len(df),
        "uploaded_at": uploaded_at,
        "uploaded_by": uploaded_by,
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input_file", type=Path, help="CSV, XLSX ou XLS bruto (nao normalizado)"
    )
    parser.add_argument("--client-id", required=True, help="client_id do cliente dono do historico")
    parser.add_argument(
        "--uploaded-by", default=None, help="Default: usuario do SO local"
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
        print(f"[load_historical_raw] ERRO: {e}", file=sys.stderr)
        sys.exit(1)

    import getpass

    upload_id = str(uuid.uuid4())
    uploaded_by = args.uploaded_by or getpass.getuser()
    uploaded_at = datetime.now(timezone.utc).isoformat()
    source_filename = args.input_file.name

    upload_rows = build_upload_rows(df, upload_id, args.client_id, source_filename, uploaded_by, uploaded_at)
    meta_row = build_meta_row(df, upload_id, args.client_id, source_filename, uploaded_by, uploaded_at)

    print(
        f"[load_historical_raw] upload_id={upload_id} client_id={args.client_id} "
        f"arquivo={source_filename} -- {len(upload_rows)} linha(s), "
        f"{len(meta_row['column_names'])} coluna(s): {meta_row['column_names']}"
    )
    print("----- preview (ate 3 linhas de raw_row) -----")
    for row in upload_rows[:3]:
        print(row["raw_row"])

    if args.dry_run:
        print("[load_historical_raw] --dry-run: nada foi gravado.")
        return

    bq_client = bigquery.Client(project=PROJECT_FIXED)

    uploads_table = f"{PROJECT_FIXED}.{TABLE_UPLOADS}"
    errors = bq_client.insert_rows_json(uploads_table, upload_rows)
    if errors:
        print(f"[load_historical_raw] ERRO ao inserir em {uploads_table}: {errors}", file=sys.stderr)
        sys.exit(1)

    meta_table = f"{PROJECT_FIXED}.{TABLE_META}"
    errors = bq_client.insert_rows_json(meta_table, [meta_row])
    if errors:
        print(f"[load_historical_raw] ERRO ao inserir em {meta_table}: {errors}", file=sys.stderr)
        print(
            f"[load_historical_raw] AVISO: {len(upload_rows)} linha(s) ja foram "
            f"gravadas em {uploads_table} (upload_id={upload_id}) antes desta "
            f"falha -- meta ficou inconsistente com uploads, corrigir manualmente.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"[load_historical_raw] OK -- {len(upload_rows)} linha(s) em {uploads_table} "
        f"+ 1 linha de metadado em {meta_table} (upload_id={upload_id})."
    )


if __name__ == "__main__":
    main()
