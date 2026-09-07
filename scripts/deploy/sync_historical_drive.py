#!/usr/bin/env python3
"""
sync_historical_drive.py -- ingestao RECORRENTE de historico manual direto
do Google Drive, idempotente por modifiedTime
--------------------------------------------------------------------------
2a mudanca de arquitetura confirmada com o Douglas em 2026-09-07 (redesenho
Casa do Construtor/Audio, sobre a carga UNICA construida mais cedo no
mesmo dia): a campanha de Audio e continua e a agencia atualiza o arquivo
do Drive todo mes -- a ingestao nao pode mais depender de alguem rodar
load_historical_raw.py na mao com um arquivo baixado manualmente.

Este script fecha o fluxo, mesmo espirito de scripts/io_plan/sync_drive.py
(mesmas credenciais/Drive, mesma logica de "so reprocessa se
modifiedTime mudou"), mas para o pipeline de historical_uploads (raw ->
normalize -> stg.historical_overrides_delivery) em vez do de IO Plan:

    1. Baixa o(s) arquivo(s) configurados em SYNC_TARGETS do Google Drive.
    2. Compara o modifiedTime do Drive contra o MAX(drive_modified_time) ja
       registrado em raw.historical_uploads_meta para esse
       client_id+drive_file_id. Se nao mudou, PARA aqui -- nao baixa de
       novo, nao gera upload_id novo, nao roda normalize/load (idempotente
       de verdade, nao so "sem duplicar no INSERT final").
    3. Se mudou (ou e a 1a vez): extrai o bloco relevante via a funcao
       extract_daily_breakdown() do modulo de mapeamento do cliente (ver
       historical_mappings/<client_id>.py -- cada cliente recorrente
       precisa exportar essa funcao, alem de normalize()), grava um
       upload_id NOVO em raw.historical_uploads/_meta (raw continua
       append-only, sempre -- um snapshot novo por sync, nunca sobrescreve
       o anterior), roda normalize() e carrega em
       stg.historical_overrides_delivery com --skip-existing (equivalente
       chamado aqui direto, ver reuse de load_historical_override.py) --
       so as chaves (client_id, day, platform, formato, target_group) NOVAS
       sao inseridas; dias ja carregados em execucoes anteriores sao
       pulados, nunca duplicados nem sobrescritos.

O QUE ESTE SCRIPT NAO FAZ -- IMPORTANTE
------------------------------------------
Nao cria Cloud Scheduler/Cloud Run nenhum -- fica fora de escopo desta
rodada (task explicita do Douglas, 2026-09-07). O agendamento automatico
(rodar isto todo dia/semana sem intervencao) e um proximo passo documentado,
nao bloqueante: hoje o script e rodavel repetidamente a mao (ou via um cron
local/Task Scheduler simples) e e seguro rodar de novo a qualquer momento
(idempotente) -- ver "Proximo passo" no fim deste docstring.

Nao promove sozinho pra producao -- carrega SEMPRE em douglas-bq-staging por
padrao (--project explicito exigido para apontar pra outro lugar, mesma
convencao do resto do repo -- nunca produção sem confirmacao humana).

Config: SYNC_TARGETS
---------------------
Um dict client_id -> config, generalizavel para outros clientes recorrentes
no futuro (hoje so casa_construtor_adf15c2c). Cada entrada precisa de:
  - "drive_folder_id": pasta do Drive onde o arquivo vive.
  - "file_name_pattern": regex (aplicado ao nome do arquivo, case-insensitive)
    para achar o arquivo certo dentro da pasta (pode ter mais de 1 arquivo
    la, ex: o DASH e a planilha Sequencia_Targets_* tambem estao na mesma
    pasta da Casa do Construtor -- ver achado ao investigar em 2026-09-07).
  - "mapping_module": nome do arquivo em historical_mappings/ (sem .py).

Uso
---
    # Roda o sync para todos os clientes configurados, contra staging
    python sync_historical_drive.py --project douglas-bq-staging

    # So um cliente
    python sync_historical_drive.py --client casa_construtor_adf15c2c --project douglas-bq-staging

    # Forca reprocessamento mesmo se modifiedTime nao mudou (debug)
    python sync_historical_drive.py --client casa_construtor_adf15c2c --project douglas-bq-staging --force

    # So mostra o que faria, sem gravar nada (ainda precisa de credencial --
    # faz leitura real no Drive + BQ para simular a decisao de skip/reprocessar)
    python sync_historical_drive.py --project douglas-bq-staging --dry-run

Auth: mesma logica de scripts/io_plan/sync_drive.py (_get_credentials --
reaproveitada de la, nao duplicada aqui): OAuth Desktop
(C:/Temp/io-plan-oauth-client.json + token cacheado) localmente, workload
identity em Cloud Run.

Proximo passo (fora de escopo desta rodada, documentado para o Douglas)
-------------------------------------------------------------------------
Agendamento automatico via Cloud Scheduler (mesmo padrao ja usado para
scripts/io_plan/sync_drive.py, se houver, ou um novo job Cloud Scheduler +
Cloud Run/Cloud Function chamando este script). Sem isso, o sync so roda
quando alguem disparar manualmente -- idempotente entao seguro fazer isso
com qualquer frequencia (diario, semanal), so nao acontece sozinho ainda.
"""

import argparse
import io
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import bigquery
from googleapiclient.discovery import build

# Reaproveita credenciais + download do script irmao de IO Plan -- mesmo
# Drive, mesma auth, nao duplicar.
sys.path.insert(0, str(Path(__file__).parent.parent / "io_plan"))
from sync_drive import _get_credentials, _list_folder, download_file  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from historical_mappings import VALID_PLATFORMS  # noqa: E402,F401 (validacao indireta via load_historical_override)
import load_historical_override as loader  # noqa: E402
import normalize_historical_upload as normalizer  # noqa: E402

TABLE_UPLOADS = "raw.historical_uploads"
TABLE_META = "raw.historical_uploads_meta"

# ─── CONFIG -- 1 entrada por cliente recorrente ────────────────────────────
SYNC_TARGETS = {
    "casa_construtor_adf15c2c": {
        "drive_folder_id": "1A1p-ubmIgEcLklfs10hRWvWQADyrvEl-",
        # Confirmado 2026-09-07: pasta tem "DASH - ..." (Google Sheet, nao
        # xlsx -- ja excluido por so listarmos XLSX_MIME),
        # "Sequencia_Targets_*.xlsx" (NAO e o arquivo certo -- outra fonte,
        # sequencia de targets, nao o breakdown diario) e
        # "RParcial_CasaDoConstrutor_*_Audio*.xlsx" (o arquivo certo, "RParcial"
        # = relatorio parcial). Pattern restrito a RParcial para nao pegar o
        # Sequencia_Targets por engano.
        # [aá] em vez de so "a" -- o nome real do arquivo tem "Áudio"
        # acentuado (confirmado 2026-09-07 baixando do Drive), e
        # re.IGNORECASE NAO faz fold de acento (nao acha "audio" dentro de
        # "Áudio").
        "file_name_pattern": re.compile(r"^RParcial.*[aá]udio", re.IGNORECASE),
        "mapping_module": "casa_construtor_adf15c2c",
    },
}

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _find_target_file(drive_svc, folder_id: str, pattern: "re.Pattern"):
    files = [f for f in _list_folder(drive_svc, folder_id, XLSX_MIME) if pattern.search(f["name"])]
    if not files:
        raise SystemExit(
            f"[sync_historical_drive] ERRO: nenhum arquivo .xlsx na pasta {folder_id!r} "
            f"bate com o padrao {pattern.pattern!r}."
        )
    if len(files) > 1:
        # Mesmo criterio de find_plano_files() em sync_drive.py -- pega so o
        # mais recente, nao arrisca processar 2 arquivos concorrentes.
        files.sort(key=lambda f: f["modifiedTime"], reverse=True)
    return files[0]


def _get_last_drive_modified(bq_client: bigquery.Client, project: str, client_id: str, drive_file_id: str):
    query = f"""
        SELECT MAX(drive_modified_time) AS ts
        FROM `{project}.{TABLE_META}`
        WHERE client_id = @client_id AND drive_file_id = @drive_file_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
            bigquery.ScalarQueryParameter("drive_file_id", "STRING", drive_file_id),
        ]
    )
    row = list(bq_client.query(query, job_config=job_config).result())[0]
    return row.ts


def _import_mapping(module_name: str):
    import importlib.util

    module_path = Path(__file__).parent / "historical_mappings" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _insert_raw_upload(bq_client: bigquery.Client, project: str, client_id: str,
                        source_filename: str, drive_file_id: str, drive_modified_time: str,
                        raw_rows: list) -> str:
    """Grava um snapshot NOVO em raw.historical_uploads/_meta -- sempre um
    upload_id novo por sync (raw e append-only, nunca sobrescreve; a
    deduplicacao acontece so na promocao pra stg.historical_overrides_delivery,
    ver load_historical_override.py --skip-existing)."""
    import json

    upload_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    column_names = list(raw_rows[0].keys()) if raw_rows else []

    upload_table_rows = [
        {
            "upload_id": upload_id,
            "client_id": client_id,
            "source_filename": source_filename,
            "row_number": i,
            "raw_row": json.dumps(row, ensure_ascii=False),
            "uploaded_at": now,
            "uploaded_by": "sync_historical_drive",
        }
        for i, row in enumerate(raw_rows, start=1)
    ]
    meta_row = {
        "upload_id": upload_id,
        "client_id": client_id,
        "source_filename": source_filename,
        "column_names": column_names,
        "row_count": len(raw_rows),
        "uploaded_at": now,
        "uploaded_by": "sync_historical_drive",
        "notes": "Carregado automaticamente por sync_historical_drive.py (Drive -> raw, sem passo manual).",
        "drive_file_id": drive_file_id,
        "drive_modified_time": drive_modified_time,
    }

    errors = bq_client.insert_rows_json(f"{project}.{TABLE_UPLOADS}", upload_table_rows)
    if errors:
        raise RuntimeError(f"Erro ao inserir em {TABLE_UPLOADS}: {errors}")
    errors = bq_client.insert_rows_json(f"{project}.{TABLE_META}", [meta_row])
    if errors:
        raise RuntimeError(f"Erro ao inserir em {TABLE_META}: {errors}")
    return upload_id


def sync_client(drive_svc, bq_client: bigquery.Client, project: str,
                client_id: str, config: dict, force: bool, dry_run: bool) -> dict:
    file_meta = _find_target_file(drive_svc, config["drive_folder_id"], config["file_name_pattern"])
    drive_file_id = file_meta["id"]
    drive_modified_time = datetime.fromisoformat(file_meta["modifiedTime"].replace("Z", "+00:00"))

    last_modified = _get_last_drive_modified(bq_client, project, client_id, drive_file_id)
    if not force and last_modified and last_modified >= drive_modified_time:
        print(
            f"[sync_historical_drive] {client_id}: SKIP -- arquivo "
            f"{file_meta['name']!r} sem mudanca (Drive modificado em "
            f"{drive_modified_time.isoformat()}, ultimo sync em "
            f"{last_modified.isoformat()})."
        )
        return {"client_id": client_id, "action": "skip", "file": file_meta["name"]}

    print(
        f"[sync_historical_drive] {client_id}: arquivo {file_meta['name']!r} "
        f"{'novo' if not last_modified else 'mudou'} (Drive modificado em "
        f"{drive_modified_time.isoformat()}) -- baixando e reprocessando..."
    )

    mapping = _import_mapping(config["mapping_module"])
    if not hasattr(mapping, "extract_daily_breakdown"):
        raise SystemExit(
            f"[sync_historical_drive] ERRO: historical_mappings/{config['mapping_module']}.py "
            f"nao exporta extract_daily_breakdown(xlsx_bytes) -- necessario para sync "
            f"recorrente direto do Drive (ver docstring deste script)."
        )

    file_bytes = download_file(drive_svc, drive_file_id)
    raw_rows = mapping.extract_daily_breakdown(file_bytes)
    print(f"[sync_historical_drive] {client_id}: {len(raw_rows)} linha(s) extraidas do xlsx.")

    if dry_run:
        print(f"[sync_historical_drive] {client_id}: --dry-run -- nao grava raw/stg, so simula.")
        return {"client_id": client_id, "action": "would_sync", "file": file_meta["name"], "rows": len(raw_rows)}

    upload_id = _insert_raw_upload(
        bq_client, project, client_id, file_meta["name"], drive_file_id,
        drive_modified_time.isoformat(), raw_rows,
    )
    print(f"[sync_historical_drive] {client_id}: upload_id={upload_id} gravado em raw.historical_uploads.")

    raw_rows_ctx = [
        {"row_number": i, "raw_row": row, "client_id": client_id, "source_filename": file_meta["name"]}
        for i, row in enumerate(raw_rows, start=1)
    ]
    normalized_rows = mapping.normalize(raw_rows_ctx)
    normalizer.validate_normalized(normalized_rows, upload_id)

    import pandas as pd
    df = pd.DataFrame(normalized_rows)[loader.REQUIRED_COLUMNS]

    existing_keys = loader.fetch_existing_keys(bq_client, project, [client_id])
    rows_to_insert = loader.build_rows(df, "sync_historical_drive")
    novas, ja_carregadas = loader.filter_already_loaded(rows_to_insert, existing_keys)

    print(
        f"[sync_historical_drive] {client_id}: {len(normalized_rows)} linha(s) normalizadas, "
        f"{len(ja_carregadas)} ja existiam (puladas), {len(novas)} nova(s) a inserir."
    )

    if novas:
        errors = bq_client.insert_rows_json(f"{project}.{loader.TABLE_ID}", novas)
        if errors:
            raise RuntimeError(f"Erro ao inserir em {loader.TABLE_ID}: {errors}")

    # ACHADO REAL (2026-09-07, testado em douglas-bq-staging): diferente de
    # load_historical_override.py --upload-id (onde o upload normalmente ja
    # foi inserido minutos/horas antes, em outra execucao manual), aqui o
    # INSERT em raw.historical_uploads_meta e o UPDATE de promoted_at
    # acontecem na MESMA execucao, segundos depois -- e a linha ainda esta
    # no streaming buffer do BigQuery (pode levar ate ~90min para assentar).
    # BQ rejeita qualquer UPDATE/DELETE sobre linha em streaming buffer
    # (BadRequest 400). Como promoted_at e so sinalizacao de UI no Hub (nao
    # bloqueia nenhum fluxo de dado -- ver raw/ddl/historical_uploads_meta.sql),
    # tratado aqui como nao-fatal: avisa e segue. O upload fica "aguardando
    # normalizacao" na tela do Hub ate a proxima vez que algo tocar essa
    # linha (ou ate alguem rodar manualmente o UPDATE depois que o buffer
    # assentar) -- puramente cosmetico, os dados ja foram promovidos de
    # verdade em stg.historical_overrides_delivery acima.
    try:
        update_sql = (
            f"UPDATE `{project}.{TABLE_META}` SET promoted_at = CURRENT_TIMESTAMP() "
            "WHERE upload_id = @upload_id"
        )
        bq_client.query(
            update_sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("upload_id", "STRING", upload_id)]
            ),
        ).result()
    except Exception as exc:
        print(
            f"[sync_historical_drive] {client_id}: AVISO -- nao consegui marcar "
            f"promoted_at para upload_id={upload_id} agora (provavelmente streaming "
            f"buffer do BQ ainda nao assentou essa linha, comum quando o INSERT e o "
            f"UPDATE acontecem na mesma execucao). So afeta o indicador visual no "
            f"Hub, nao os dados -- ja promovidos em stg.historical_overrides_delivery. "
            f"Detalhe: {exc}"
        )

    return {
        "client_id": client_id,
        "action": "synced",
        "file": file_meta["name"],
        "upload_id": upload_id,
        "rows_extracted": len(raw_rows),
        "rows_normalized": len(normalized_rows),
        "rows_inserted": len(novas),
        "rows_skipped_existing": len(ja_carregadas),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--client", default=None, help="So sincroniza este client_id (default: todos em SYNC_TARGETS)")
    parser.add_argument("--project", default="douglas-bq-staging", help="Default: douglas-bq-staging (nunca producao sem --project explicito)")
    parser.add_argument("--force", action="store_true", help="Reprocessa mesmo se modifiedTime nao mudou")
    parser.add_argument("--dry-run", action="store_true", help="So mostra o que faria (ainda le Drive+BQ de verdade)")
    args = parser.parse_args()

    targets = SYNC_TARGETS
    if args.client:
        if args.client not in SYNC_TARGETS:
            raise SystemExit(
                f"[sync_historical_drive] client_id={args.client!r} nao esta em SYNC_TARGETS "
                f"(disponiveis: {list(SYNC_TARGETS.keys())})."
            )
        targets = {args.client: SYNC_TARGETS[args.client]}

    credentials = _get_credentials()
    drive_svc = build("drive", "v3", credentials=credentials)
    bq_client = bigquery.Client(project=args.project, credentials=credentials)

    results = []
    for client_id, config in targets.items():
        result = sync_client(drive_svc, bq_client, args.project, client_id, config, args.force, args.dry_run)
        results.append(result)

    print("\n----- resumo -----")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
