"""
cora_sheets_sync.py
-------------------
Reads the Cora reporting Google Sheet and uploads 13 tables to
adframework.gold_cora in BigQuery.

Usage (local, with ADC):
    python cora_sheets_sync.py

Usage (CI / GitHub Actions):
    GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json python cora_sheets_sync.py

Required env vars (optional overrides):
    SPREADSHEET_ID   — Google Sheet ID (default: Cora production sheet)
    GCP_PROJECT      — BigQuery project (default: striped-bonfire-489318-t9)
    BQ_DATASET       — Target BigQuery dataset (default: gold_cora)

Dependencies:
    pip install gspread google-cloud-bigquery google-auth
"""

import os
import re
import io
import sys
import logging

import gspread
from google.oauth2 import service_account
from google.auth import default as google_auth_default
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1Y94CavDyMXnIy9sLyqcTP8yKdANiQ1j1RzZBzHi7YHk")
GCP_PROJECT    = os.getenv("GCP_PROJECT", "striped-bonfire-489318-t9")
BQ_DATASET     = os.getenv("BQ_DATASET", "gold_cora")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/bigquery",
]

# ---------------------------------------------------------------------------
# Auth — service account key (CI) or ADC (local)
# ---------------------------------------------------------------------------
def get_credentials():
    sa_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if sa_file and os.path.exists(sa_file):
        creds = service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)
        log.info("Auth: service account key")
    else:
        creds, _ = google_auth_default(scopes=SCOPES)
        log.info("Auth: ADC")
    return creds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def br_num(v):
    """Parse Brazilian-formatted number: '2.737' -> 2737.0, '13,69%' -> 13.69"""
    if not isinstance(v, str) or not v.strip() or v.strip() in ("-", ""):
        return None
    v = re.sub(r"R\$\s*", "", v).replace("%", "").strip()
    if not v or v == "-":
        return None
    if "," in v and "." in v:
        v = v.replace(".", "").replace(",", ".")
    elif "," in v:
        v = v.replace(",", ".")
    elif "." in v:
        parts = v.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            v = v.replace(".", "")
    try:
        return float(v)
    except Exception:
        return None


def fix_date(v):
    """DD/MM/YYYY -> YYYY-MM-DD  (pass through if already YYYY-MM-DD)"""
    if not isinstance(v, str):
        return None
    v = v.strip()
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", v)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        return v
    return None


def sheet_to_df(ws):
    """Convert gspread worksheet to list-of-dicts, skipping blank rows."""
    import pandas as pd
    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame()
    headers = rows[0]
    data = [r + [""] * max(0, len(headers) - len(r)) for r in rows[1:] if any(c.strip() for c in r)]
    return pd.DataFrame([r[:len(headers)] for r in data], columns=headers)


def upload(client, df, table_id, desc):
    """Upload DataFrame to BigQuery via CSV."""
    import pandas as pd
    if df is None or df.empty:
        log.info(f"  SKIP (empty): {table_id}")
        return
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    cfg = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        write_disposition="WRITE_TRUNCATE",
    )
    job = client.load_table_from_file(
        io.BytesIO(buf.getvalue().encode("utf-8")), table_id, job_config=cfg
    )
    job.result()
    t = client.get_table(table_id)
    log.info(f"  OK  {table_id.split('.')[-1]:35} {t.num_rows:>5} rows  {desc}")


NUM_ALL = [
    "impressoes", "impressoes_projetadas", "pacing_impressoes",
    "cpm", "cpm_projetado", "cliques", "cliques_projetados", "pacing_cliques",
    "cpc", "cpc_projetado", "ctr", "ctr_projetado",
    "investimento", "investimento_projetado", "pacing_investimento",
    "views", "vtr",
]

FULL_COLS = [
    "dia", "estrategia",
    "impressoes", "impressoes_projetadas", "pacing_impressoes",
    "cpm", "cpm_projetado",
    "cliques", "cliques_projetados", "pacing_cliques",
    "cpc", "cpc_projetado", "ctr", "ctr_projetado",
    "investimento", "investimento_projetado", "pacing_investimento",
]
FULL_COLS_VIDEO = FULL_COLS + ["views", "vtr"]


def process_full(df, cols):
    """Rename columns positionally, clean dates and numbers."""
    import pandas as pd
    rename = {df.columns[i]: cols[i] for i in range(min(len(cols), len(df.columns)))}
    df = df.rename(columns=rename)
    target = set(cols)
    df = df[[c for c in df.columns if c in target]]
    df["dia"] = df["dia"].apply(fix_date)
    df = df[df["dia"].notna()].copy()
    for c in NUM_ALL:
        if c in df.columns:
            df[c] = df[c].apply(br_num)
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    import pandas as pd

    creds = get_credentials()
    gc     = gspread.authorize(creds)
    bq     = bigquery.Client(project=GCP_PROJECT, credentials=creds)

    log.info(f"Opening spreadsheet {SPREADSHEET_ID} ...")
    ss = gc.open_by_key(SPREADSHEET_ID)
    sheets = ss.worksheets()
    log.info(f"Found {len(sheets)} sheets: {[s.title for s in sheets]}")

    # Ensure dataset exists
    bq.create_dataset(f"{GCP_PROJECT}.{BQ_DATASET}", exists_ok=True)

    def tbl(name):
        return f"{GCP_PROJECT}.{BQ_DATASET}.{name}"

    log.info(f"\n=== Syncing to {BQ_DATASET} ===\n")

    # Map by sheet index (order matches the Sheets tab order)
    # 0: veiculacao  1: consolidado_geral  2: regioes  3: devices
    # 4: formatos    5: criativos          6: consolidado_cpm  7: consolidado_cpc
    # 8: display     9: retargeting        10: video   11: push  12: native

    def ws(idx):
        return sheet_to_df(sheets[idx]) if idx < len(sheets) else pd.DataFrame()

    # 0 — cora_veiculacao
    df = ws(0)
    if not df.empty:
        df = df.rename(columns={df.columns[0]: "dia", df.columns[1]: "flight", df.columns[2]: "periodo"})
        df = df[["dia", "flight", "periodo"]]
        df["dia"] = df["dia"].apply(fix_date)
        df = df[df["dia"].notna()]
    upload(bq, df, tbl("cora_veiculacao"), "DIA / FLIGHT / PERÍODO")

    # 1 — cora_consolidado_geral
    upload(bq, process_full(ws(1), FULL_COLS), tbl("cora_consolidado_geral"), "Consolidado Geral")

    # 2 — cora_regioes
    df = ws(2)
    if not df.empty:
        df = df.rename(columns={df.columns[0]: "dia", df.columns[1]: "regiao",
                                  df.columns[2]: "impressoes", df.columns[3]: "cliques", df.columns[4]: "ctr"})
        df = df[["dia", "regiao", "impressoes", "cliques", "ctr"]]
        df["dia"] = df["dia"].apply(fix_date)
        df = df[df["dia"].notna()]
        for c in ["impressoes", "cliques", "ctr"]:
            df[c] = df[c].apply(br_num)
    upload(bq, df, tbl("cora_regioes"), "Dia x Região")

    # 3 — cora_devices
    df = ws(3)
    if not df.empty:
        df = df.rename(columns={df.columns[0]: "dia", df.columns[1]: "device",
                                  df.columns[2]: "impressoes", df.columns[3]: "cliques",
                                  df.columns[4]: "ctr", df.columns[5]: "cpm", df.columns[6]: "investimento"})
        df = df[["dia", "device", "impressoes", "cliques", "ctr", "cpm", "investimento"]]
        df["dia"] = df["dia"].apply(fix_date)
        df = df[df["dia"].notna()]
        for c in ["impressoes", "cliques", "ctr", "cpm", "investimento"]:
            df[c] = df[c].apply(br_num)
    upload(bq, df, tbl("cora_devices"), "Dia x Device")

    # 4 — cora_formatos
    df = ws(4)
    if not df.empty:
        df = df.rename(columns={df.columns[0]: "dia", df.columns[1]: "estrategia",
                                  df.columns[2]: "formato", df.columns[3]: "impressoes",
                                  df.columns[4]: "cliques", df.columns[5]: "ctr",
                                  df.columns[6]: "cpm", df.columns[7]: "investimento"})
        df = df[["dia", "estrategia", "formato", "impressoes", "cliques", "ctr", "cpm", "investimento"]]
        df["dia"] = df["dia"].apply(fix_date)
        df = df[df["dia"].notna()]
        for c in ["impressoes", "cliques", "ctr", "cpm", "investimento"]:
            df[c] = df[c].apply(br_num)
    upload(bq, df, tbl("cora_formatos"), "Dia x Estratégia x Formato")

    # 5 — cora_criativos
    df = ws(5)
    if not df.empty:
        df = df.rename(columns={df.columns[0]: "dia", df.columns[1]: "estrategia",
                                  df.columns[2]: "criativo", df.columns[3]: "impressoes",
                                  df.columns[4]: "cliques", df.columns[5]: "ctr",
                                  df.columns[6]: "cpm", df.columns[7]: "investimento"})
        df = df[["dia", "estrategia", "criativo", "impressoes", "cliques", "ctr", "cpm", "investimento"]]
        df["dia"] = df["dia"].apply(fix_date)
        df = df[df["dia"].notna()]
        for c in ["impressoes", "cliques", "ctr", "cpm", "investimento"]:
            df[c] = df[c].apply(br_num)
    upload(bq, df, tbl("cora_criativos"), "Dia x Estratégia x Criativo")

    # 6 — cora_consolidado_cpm
    upload(bq, process_full(ws(6), FULL_COLS), tbl("cora_consolidado_cpm"), "Consolidado CPM")

    # 7 — cora_consolidado_cpc
    upload(bq, process_full(ws(7), FULL_COLS), tbl("cora_consolidado_cpc"), "Consolidado CPC")

    # 8 — cora_display
    upload(bq, process_full(ws(8), FULL_COLS), tbl("cora_display"), "Display (CPM)")

    # 9 — cora_retargeting
    upload(bq, process_full(ws(9), FULL_COLS), tbl("cora_retargeting"), "Retargeting (CPM)")

    # 10 — cora_video (extra cols: views, vtr)
    upload(bq, process_full(ws(10), FULL_COLS_VIDEO), tbl("cora_video"), "Vídeo + views/vtr")

    # 11 — cora_push
    upload(bq, process_full(ws(11), FULL_COLS), tbl("cora_push"), "Push (CPC)")

    # 12 — cora_native
    upload(bq, process_full(ws(12), FULL_COLS), tbl("cora_native"), "Native (CPC)")

    log.info(f"\nDone. All tables synced to {BQ_DATASET}.")


if __name__ == "__main__":
    main()
