"""
Generate DBML ERD from BigQuery INFORMATION_SCHEMA extracts.
Cross-layer relationships only; view DDL JOIN inference; legacy tables excluded from refs.
"""

import csv
import json
import re
from collections import defaultdict

TABLES_FILE  = r"C:\Temp\erd_tables.csv"
COLUMNS_FILE = r"C:\Temp\erd_columns.csv"
VIEWS_FILE   = r"C:\Temp\erd_views.json"
DBML_OUT     = r"C:\Temp\adframework_erd.dbml"
MERMAID_OUT  = r"C:\Temp\adframework_erd_mermaid.md"

DATASET_ORDER = ["raw", "raw_newadframework", "stg", "core", "marts", "share", "gold"]

# Tables to skip when building relationship inference (legacy/backup noise)
SKIP_REF_PATTERN = re.compile(
    r"legacy|_backup|_old|_v1\b|_v2\b|_v3\b|_std\b|20260227|_cache\b|_enriched\b|"
    r"operational_daily\b|_daily_detail\b|powerdata|postview|postclick|pivot|"
    r"newad_bet_daily|newad_fintech|luckbet_creative|pacing|dashboard|report_",
    re.IGNORECASE,
)

# --- Load tables -------------------------------------------------------------
tables = {}
with open(TABLES_FILE, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        key = f"{row['dataset']}.{row['table_name']}"
        tables[key] = row

# --- Load columns -------------------------------------------------------------
columns = defaultdict(list)
with open(COLUMNS_FILE, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        key = f"{row['dataset']}.{row['table_name']}"
        columns[key].append(row)

# --- Load views ---------------------------------------------------------------
views = {}
with open(VIEWS_FILE, encoding="utf-8-sig") as f:
    raw_json = json.load(f)

for entry in raw_json:
    key = f"{entry['dataset']}.{entry['table_name']}"
    views[key] = entry.get("view_definition", "")

print(f"Loaded: {len(tables)} tables, {len(columns)} table-column-sets, {len(views)} views")

# --- Curated critical cross-layer relationships (from id_dependency_map.md) ---
# Format: (from_ds, from_table, col, to_ds, to_table)
cross_layer_refs = [
    # Campaign ID chain
    ("raw",                "mediasmart_daily",             "controlid",             "stg", "mediasmart_daily"),
    ("raw",                "mgid_daily",                   "campaignid",            "stg", "mgid_daily"),
    ("raw",                "siprocal_daily_materialized",  "campaign_id",           "stg", "siprocal_daily"),
    ("stg",                "mediasmart_daily",             "platform_campaign_id",  "core", "io_line_bindings_v2"),
    ("stg",                "mgid_daily",                   "platform_campaign_id",  "core", "io_line_bindings_v2"),
    # Advertiser/event_id chain
    ("raw",                "mediasmart_daily",             "eventid",               "stg", "mediasmart_daily"),
    ("stg",                "mediasmart_daily",             "event_id",              "stg", "mediasmart_operational_v2"),
    ("stg",                "mediasmart_operational_v2",    "advertiser_platform_id","share", "platform_daily_detail"),
    ("share",              "platform_daily_detail",        "advertiser_platform_id","core", "platform_client_links"),
    # IO chain
    ("raw_newadframework", "io_manager_v2",                "io_id",                 "stg", "io_lines_v4"),
    ("raw_newadframework", "io_line_bindings_v2",          "line_id",               "stg", "io_lines_v4"),
    ("raw_newadframework", "platform_client_links",        "newad_client_id",       "core", "platform_client_links"),
    ("stg",                "io_lines_v4",                  "io_id",                 "core", "io_registry_v4"),
    ("stg",                "io_lines_v4",                  "line_id",               "core", "io_binding_registry_v4"),
    ("core",               "io_binding_registry_v4",       "binding_id",            "marts", "io_delivery_daily_v4"),
    ("core",               "platform_client_links",        "newad_client_id",       "gold", "dim_client"),
    ("marts",              "io_delivery_daily_v4",         "io_id",                 "marts", "io_calc_daily_v4"),
    ("marts",              "io_calc_daily_v4",             "io_id",                 "share", "io_calc_daily_v4"),
    ("share",              "io_calc_daily_v4",             "io_id",                 "gold", "fct_delivery_daily"),
    ("gold",               "fct_delivery_daily",           "newad_client_id",       "gold", "dim_client"),
    # Strategy chain
    ("raw",                "mediasmart_daily",             "strategyid",            "stg", "mediasmart_daily"),
    ("stg",                "mediasmart_operational_v2",    "platform_strategy_id",  "share", "platform_daily_detail"),
    # Proposal chain
    ("raw_newadframework", "io_manager_v2",                "proposal_id",           "raw_newadframework", "proposals"),
    ("stg",                "io_lines_v4",                  "proposal_id",           "core", "io_registry_v4"),
]

print(f"Cross-layer ID refs: {len(cross_layer_refs)}")

# --- Infer relationships from view DDL JOIN conditions ------------------------
# Pattern: JOIN `project.dataset.table` or `dataset.table`
join_ref_pattern = re.compile(
    r"(?:FROM|JOIN)\s+`?(?:[\w\-]+\.)?(\w+)\.(\w+)`?",
    re.IGNORECASE,
)

view_refs = []
seen_view_refs = set()

for view_key, ddl in views.items():
    if not ddl:
        continue
    vds, vtbl = view_key.split(".", 1)
    if SKIP_REF_PATTERN.search(vtbl):
        continue
    for match in join_ref_pattern.finditer(ddl):
        ref_ds = match.group(1)
        ref_tbl = match.group(2)
        if ref_ds not in DATASET_ORDER:
            continue
        if ref_ds == vds and ref_tbl == vtbl:  # self-reference
            continue
        if SKIP_REF_PATTERN.search(ref_tbl):
            continue
        pair = tuple(sorted([(vds, vtbl), (ref_ds, ref_tbl)]))
        if pair in seen_view_refs:
            continue
        seen_view_refs.add(pair)
        # Direction: view references source table
        view_refs.append((ref_ds, ref_tbl, vds, vtbl))

print(f"View JOIN refs: {len(view_refs)}")

# --- DBML generation ----------------------------------------------------------
BQ_TO_DBML = {
    "STRING": "varchar", "INT64": "bigint", "INTEGER": "int",
    "FLOAT64": "float", "FLOAT": "float", "NUMERIC": "decimal",
    "BIGNUMERIC": "decimal", "BOOL": "boolean", "BOOLEAN": "boolean",
    "DATE": "date", "DATETIME": "datetime", "TIMESTAMP": "timestamp",
    "TIME": "time", "BYTES": "blob", "ARRAY": "array",
    "STRUCT": "json", "RECORD": "json", "JSON": "json",
    "GEOGRAPHY": "varchar", "INTERVAL": "varchar",
}

def bq_type(bq):
    t = bq.upper().split("<")[0].strip()
    return BQ_TO_DBML.get(t, bq.lower())

def safe(name):
    if re.search(r"[^a-zA-Z0-9_]", name):
        return f'"{name}"'
    return name

lines = []
lines.append("// AdFramework BigQuery ERD")
lines.append("// 7 datasets | 164 objects | 4,289 columns")
lines.append("// Import: https://dbdiagram.io/d  (paste DBML content)")
lines.append("")

# Group all tables by dataset
by_dataset = defaultdict(list)
for key in set(list(columns.keys()) + list(tables.keys())):
    ds, tbl = key.split(".", 1)
    by_dataset[ds].append(tbl)
for ds in by_dataset:
    by_dataset[ds] = sorted(set(by_dataset[ds]))

# Emit tables
for ds in DATASET_ORDER:
    if ds not in by_dataset:
        continue
    lines.append(f"// {'='*48}")
    lines.append(f"// Layer: {ds.upper()}")
    lines.append(f"// {'='*48}")
    lines.append("")

    for tbl in by_dataset[ds]:
        key = f"{ds}.{tbl}"
        cols = columns.get(key, [])
        meta = tables.get(key, {})
        tbl_type = meta.get("table_type", "")
        row_count = meta.get("row_count", "")

        dbml_name = f"{ds}__{tbl}"
        note_parts = [f"{ds}.{tbl}"]
        if tbl_type:
            note_parts.append(tbl_type)
        if row_count:
            try:
                note_parts.append(f"{int(float(row_count)):,} rows")
            except ValueError:
                pass

        lines.append(f"Table {safe(dbml_name)} {{")
        lines.append(f"  Note: '{' | '.join(note_parts)}'")

        if not cols:
            lines.append("  // (no column metadata available)")
        else:
            pk_cols = {"id", "binding_id", "io_id", "line_id", "proposal_id"}
            # Only mark pk if exactly ONE pk-candidate column exists in this table
            col_names_lower = [c["column_name"].lower() for c in cols]
            pk_candidates = [n for n in col_names_lower if n in pk_cols]
            sole_pk = pk_candidates[0] if len(pk_candidates) == 1 else None

            for col in sorted(cols, key=lambda c: int(c.get("ordinal_position", 0))):
                cname = col["column_name"]
                dtype = bq_type(col.get("data_type", "varchar"))
                nullable = col.get("is_nullable", "YES")
                flags = []
                cl = cname.lower()
                if sole_pk and cl == sole_pk:
                    flags.append("pk")
                if nullable == "NO":
                    flags.append("not null")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                # Quote column names that are invalid DBML identifiers
                safe_cname = f'"{cname}"' if re.search(r"[^a-zA-Z0-9_]|^[0-9]|_$", cname) else cname
                lines.append(f"  {safe_cname} {dtype}{flag_str}")
        lines.append("}")
        lines.append("")

# --- Cross-layer ID-based references -----------------------------------------
lines.append("")
lines.append(f"// {'-'*60}")
lines.append("// Cross-layer references inferred from shared ID column names")
lines.append(f"// {'-'*60}")
lines.append("")

for ds1, t1, col, ds2, t2 in sorted(cross_layer_refs, key=lambda r: (DATASET_ORDER.index(r[0]), r[1])):
    n1 = f"{ds1}__{t1}"
    n2 = f"{ds2}__{t2}"
    lines.append(f"Ref: {safe(n1)}.{safe(col)} > {safe(n2)}.{safe(col)}")

# --- View JOIN references -----------------------------------------------------
lines.append("")
lines.append(f"// {'-'*60}")
lines.append("// References inferred from view DDL JOIN patterns")
lines.append(f"// {'-'*60}")
lines.append("")

for src_ds, src_tbl, vds, vtbl in sorted(view_refs, key=lambda r: (DATASET_ORDER.index(r[2]) if r[2] in DATASET_ORDER else 99, r[3])):
    n_src = f"{src_ds}__{src_tbl}"
    n_view = f"{vds}__{vtbl}"
    # Find a shared column to anchor the ref; fall back to first col of the source
    src_cols = {c["column_name"].lower() for c in columns.get(f"{src_ds}.{src_tbl}", [])}
    view_cols = {c["column_name"].lower() for c in columns.get(f"{vds}.{vtbl}", [])}
    shared = src_cols & view_cols
    # Prefer ID columns as anchor
    anchor = None
    for candidate in ["io_id", "line_id", "binding_id", "newad_client_id",
                       "platform_campaign_id", "date", "id"]:
        if candidate in shared:
            anchor = candidate
            break
    if not anchor and shared:
        anchor = sorted(shared)[0]
    if anchor:
        lines.append(f"Ref: {safe(n_src)}.{anchor} - {safe(n_view)}.{anchor} // view join")

with open(DBML_OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"\nDBML written -> {DBML_OUT}")
print(f"  Lines: {len(lines)}")

# --- Mermaid (core pipeline only) --------------------------------------------
CORE_TABLES = [
    ("raw", "mediasmart_daily"),
    ("raw", "mgid_daily"),
    ("raw", "siprocal_daily_materialized"),
    ("raw_newadframework", "io_manager_v2"),
    ("raw_newadframework", "io_line_bindings_v2"),
    ("raw_newadframework", "platform_client_links"),
    ("stg", "mediasmart_daily"),
    ("stg", "io_lines_v4"),
    ("core", "io_binding_registry_v4"),
    ("core", "platform_client_links"),
    ("marts", "io_calc_daily_v4"),
    ("marts", "io_delivery_daily_v4"),
    ("share", "platform_daily_detail"),
    ("gold", "fct_delivery_daily"),
    ("gold", "dim_client"),
]

CORE_RELS = [
    ("raw__mediasmart_daily",                  "stg__mediasmart_daily",           "controlid->platform_campaign_id"),
    ("raw__mgid_daily",                        "stg__mgid_daily",                 "campaignid->platform_campaign_id"),
    ("raw__siprocal_daily_materialized",       "stg__siprocal_daily",             "campaign_id->platform_campaign_id"),
    ("raw_newadframework__io_manager_v2",      "stg__io_lines_v4",                "io_id, line_id"),
    ("raw_newadframework__io_line_bindings_v2","stg__io_lines_v4",                "line_id"),
    ("raw_newadframework__platform_client_links","core__platform_client_links",   "newad_client_id"),
    ("stg__io_lines_v4",                       "core__io_binding_registry_v4",    "io_id, line_id"),
    ("stg__mediasmart_daily",                  "core__io_binding_registry_v4",    "platform_campaign_id"),
    ("core__io_binding_registry_v4",           "marts__io_delivery_daily_v4",     "binding_id"),
    ("marts__io_delivery_daily_v4",            "marts__io_calc_daily_v4",         "io_id, line_id"),
    ("marts__io_calc_daily_v4",                "share__platform_daily_detail",    "io_id, line_id"),
    ("share__platform_daily_detail",           "core__platform_client_links",     "advertiser_platform_id=link_value"),
    ("share__platform_daily_detail",           "gold__fct_delivery_daily",        "io_id, line_id"),
    ("gold__fct_delivery_daily",               "gold__dim_client",                "newad_client_id"),
]

ml = ["# AdFramework ERD — Core Delivery Pipeline", "", "```mermaid", "erDiagram"]

for ds, tbl in CORE_TABLES:
    key = f"{ds}.{tbl}"
    ent = f"{ds}__{tbl}".replace("-", "_")
    cols = columns.get(key, [])
    ml.append(f"  {ent} {{")
    shown = 0
    for col in sorted(cols, key=lambda c: int(c.get("ordinal_position", 0))):
        if shown >= 15:
            ml.append(f"    string __{len(cols)-15}_more_columns__")
            break
        dtype = bq_type(col.get("data_type", "varchar"))
        cname = re.sub(r"[^a-zA-Z0-9_]", "_", col["column_name"])
        ml.append(f"    {dtype} {cname}")
        shown += 1
    ml.append("  }")

ml.append("")
for left, right, label in CORE_RELS:
    label_safe = label.replace('"', "'")
    ml.append(f'  {left} ||--o{{ {right} : "{label_safe}"')

ml.append("```")

with open(MERMAID_OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(ml))

print(f"Mermaid written -> {MERMAID_OUT}")
