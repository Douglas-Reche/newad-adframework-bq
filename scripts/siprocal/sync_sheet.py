#!/usr/bin/env python3
"""
Siprocal Sheet Sync
-------------------
Reads raw_daily tab from the Siprocal Google Sheet and appends only
new days (> current max in BQ) to raw.siprocal_delivery.

This is the single canonical ingestion path for Siprocal data.
No historical data is ever deleted.

Auth:
  BQ   : ADC (gcloud auth application-default login)
  Sheets: gcloud access token via env var GCLOUD_ACCESS_TOKEN
          Run: export GCLOUD_ACCESS_TOKEN=$(gcloud auth print-access-token)

Usage:
  GCLOUD_ACCESS_TOKEN=$(gcloud auth print-access-token) python sync_sheet.py
  python sync_sheet.py --force   # re-insert even if day already present
"""

import argparse
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import requests
from google.auth import default
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SPREADSHEET_ID = "1HaGrxaU-nt3fvqxaJ1CSlABYJGNY28rhQC49dcGzLWs"
SHEET_TAB      = "raw_daily"
PROJECT        = "adframework"
# Writes to siprocal_raw_sheet (staging table).
# The ETL job siprocal_daily_external reads from here and publishes to siprocal_delivery.
TARGET_REF     = f"{PROJECT}.raw.siprocal_raw_sheet"
UTC            = timezone.utc
EXCEL_EPOCH    = datetime(1899, 12, 30)

SCHEMA = [
    bigquery.SchemaField("day",            "STRING"),
    bigquery.SchemaField("advertiser",     "STRING"),
    bigquery.SchemaField("campaign_id",    "STRING"),
    bigquery.SchemaField("creative_type",  "STRING"),
    bigquery.SchemaField("creative",       "STRING"),
    bigquery.SchemaField("impressions",    "STRING"),
    bigquery.SchemaField("clicks",         "STRING"),
    bigquery.SchemaField("platform",       "STRING"),
    bigquery.SchemaField("report_name",    "STRING"),
    bigquery.SchemaField("raw_ingested_at","TIMESTAMP"),
]


def parse_date(val) -> str | None:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        try:
            return (EXCEL_EPOCH + timedelta(days=int(val))).strftime("%Y-%m-%d")
        except Exception:
            return None
    s = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Re-insert all rows, ignoring what is already in BQ")
    args = parser.parse_args()

    token = os.environ.get("GCLOUD_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Set GCLOUD_ACCESS_TOKEN first:\n"
            "  export GCLOUD_ACCESS_TOKEN=$(gcloud auth print-access-token)"
        )

    creds, _ = default(scopes=["https://www.googleapis.com/auth/bigquery"])
    bq = bigquery.Client(project=PROJECT, credentials=creds)

    # Current max day in BQ
    max_day_bq = "2000-01-01"
    if not args.force:
        row = list(bq.query(f"SELECT MAX(day) as d FROM `{TARGET_REF}`").result())[0]
        if row.d:
            max_day_bq = str(row.d)
    log.info(f"BQ max day: {max_day_bq} (force={args.force})")

    # Read sheet
    log.info(f"Reading sheet tab '{SHEET_TAB}'...")
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}"
        f"/values/{SHEET_TAB}?valueRenderOption=UNFORMATTED_VALUE"
    )
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    raw_values = resp.json().get("values", [])
    sheet_rows = raw_values[1:]  # skip header
    log.info(f"Sheet rows: {len(sheet_rows)}")

    def _col(row, idx, default=""):
        return row[idx] if idx < len(row) else default

    to_insert = []
    for i, row in enumerate(sheet_rows, 2):
        day       = parse_date(_col(row, 1))
        advertiser = str(_col(row, 2)).strip()
        if not day or not advertiser:
            continue
        if not args.force and day <= max_day_bq:
            continue
        to_insert.append({
            "day":            day,
            "advertiser":     advertiser,
            "campaign_id":    str(_col(row, 0)).strip(),
            "creative_type":  "",
            "creative":       str(_col(row, 3)).strip(),
            "impressions":    re.sub(r"[^\d]", "", str(_col(row, 4))) or "",
            "clicks":         re.sub(r"[^\d]", "", str(_col(row, 5))) or "",
            "platform":       "siprocal",
            "report_name":    SHEET_TAB,
            "raw_ingested_at": datetime.now(UTC).isoformat(),
        })

    if not to_insert:
        log.info("Nothing to insert — BQ is up to date.")
        return

    log.info(f"New rows to insert: {len(to_insert)}")
    from collections import Counter
    for d, c in sorted(Counter(r["day"] for r in to_insert).items()):
        log.info(f"  {d}: {c} rows")

    job = bq.load_table_from_json(
        to_insert, TARGET_REF,
        job_config=bigquery.LoadJobConfig(schema=SCHEMA, write_disposition="WRITE_APPEND"),
    )
    job.result()
    log.info(f"Inserted {len(to_insert)} rows.")

    result = list(bq.query(
        f"SELECT COUNT(*) as total, MIN(day) as min_d, MAX(day) as max_d FROM `{TARGET_REF}`"
    ).result())[0]
    log.info(f"Final state: {result.total} rows | {result.min_d} -> {result.max_d}")


if __name__ == "__main__":
    main()
