"""
Reads Cora Google Sheet via HTTP Sheets API (using gcloud user token)
and uploads all 13 tabs to gold_cora in BigQuery.
"""
import os, re, io, json
import requests
import pandas as pd
from google.cloud import bigquery
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

OAUTH_CLIENT_FILE = r"C:\Temp\io-plan-oauth-client.json"
OAUTH_TOKEN_FILE  = r"C:\Temp\io-plan-token.json"
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/cloud-platform",
]

creds = None
if os.path.exists(OAUTH_TOKEN_FILE):
    creds = Credentials.from_authorized_user_file(OAUTH_TOKEN_FILE, SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CLIENT_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
    with open(OAUTH_TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

token = creds.token
HEADERS = {"Authorization": f"Bearer {token}"}
SPREADSHEET_ID = "1Y94CavDyMXnIy9sLyqcTP8yKdANiQ1j1RzZBzHi7YHk"

client = bigquery.Client(project="striped-bonfire-489318-t9")

# ---------------------------------------------------------------------------
def get_sheet_names():
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}?fields=sheets.properties"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return [(s["properties"]["title"], s["properties"]["sheetId"]) for s in r.json()["sheets"]]

def read_sheet(sheet_name):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{requests.utils.quote(sheet_name)}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    data = r.json()
    rows = data.get("values", [])
    if not rows: return pd.DataFrame()
    headers = rows[0]
    data_rows = [r + [""] * max(0, len(headers) - len(r)) for r in rows[1:] if any(c.strip() for c in r)]
    return pd.DataFrame([r[:len(headers)] for r in data_rows], columns=headers)

# ---------------------------------------------------------------------------
def br_num(v):
    if not isinstance(v, str) or not v.strip() or v.strip() in ("-", ""): return None
    v = re.sub(r"R[$]\s*", "", v).replace("%", "").strip()
    if not v or v == "-": return None
    if "," in v and "." in v: v = v.replace(".", "").replace(",", ".")
    elif "," in v: v = v.replace(",", ".")
    elif "." in v:
        parts = v.split(".")
        if len(parts) == 2 and len(parts[1]) == 3: v = v.replace(".", "")
    try: return float(v)
    except: return None

def fix_date(v):
    if not isinstance(v, str): return None
    v = v.strip()
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", v)
    if m: return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", v): return v
    return None

NUM_ALL = ["impressoes","impressoes_projetadas","pacing_impressoes","cpm","cpm_projetado",
           "cliques","cliques_projetados","pacing_cliques","cpc","cpc_projetado",
           "ctr","ctr_projetado","investimento","investimento_projetado","pacing_investimento","views","vtr"]

FULL_COLS = ["dia","estrategia","impressoes","impressoes_projetadas","pacing_impressoes",
             "cpm","cpm_projetado","cliques","cliques_projetados","pacing_cliques",
             "cpc","cpc_projetado","ctr","ctr_projetado","investimento","investimento_projetado","pacing_investimento"]
FULL_COLS_VIDEO = FULL_COLS + ["views","vtr"]

def process_full(df, cols):
    rename = {df.columns[i]: cols[i] for i in range(min(len(cols), len(df.columns)))}
    df = df.rename(columns=rename)
    df = df[[c for c in df.columns if c in set(cols)]]
    df["dia"] = df["dia"].apply(fix_date)
    df = df[df["dia"].notna()].copy()
    for c in NUM_ALL:
        if c in df.columns: df[c] = df[c].apply(br_num)
    return df

def upload(df, table_id, desc):
    if df is None or df.empty: print(f"  SKIP: {table_id}"); return
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    cfg = bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.CSV, skip_leading_rows=1,
                                  autodetect=True, write_disposition="WRITE_TRUNCATE")
    job = client.load_table_from_file(io.BytesIO(buf.getvalue().encode()), table_id, job_config=cfg)
    job.result()
    t = client.get_table(table_id)
    print(f"  OK  {table_id.split('.')[-1]:35} {t.num_rows:>6} rows  {desc}")

def tbl(name): return f"gold_cora.{name}"

# ---------------------------------------------------------------------------
print("=== Cora Sheets -> BigQuery (via Sheets API) ===\n")
sheets = get_sheet_names()
print(f"Sheets found ({len(sheets)}): {[s[0] for s in sheets]}\n")

def ws(idx): return read_sheet(sheets[idx][0]) if idx < len(sheets) else pd.DataFrame()

# 0 — veiculacao
df = ws(0)
if not df.empty:
    df = df.rename(columns={df.columns[0]:"dia", df.columns[1]:"flight", df.columns[2]:"periodo"})
    df = df[["dia","flight","periodo"]]
    df["dia"] = df["dia"].apply(fix_date)
    df = df[df["dia"].notna()]
upload(df, tbl("cora_veiculacao"), "DIA / FLIGHT / PERÍODO")

# 1 — consolidado_geral
upload(ws(1).pipe(lambda d: process_full(d, FULL_COLS)), tbl("cora_consolidado_geral"), "Consolidado Geral")

# 2 — regioes
df = ws(2)
if not df.empty:
    df = df.rename(columns={df.columns[0]:"dia", df.columns[1]:"regiao",
                              df.columns[2]:"impressoes", df.columns[3]:"cliques", df.columns[4]:"ctr"})
    df = df[["dia","regiao","impressoes","cliques","ctr"]]
    df["dia"] = df["dia"].apply(fix_date)
    df = df[df["dia"].notna()]
    for c in ["impressoes","cliques","ctr"]: df[c] = df[c].apply(br_num)
upload(df, tbl("cora_regioes"), "Dia x Região")

# 3 — devices
df = ws(3)
if not df.empty:
    df = df.rename(columns={df.columns[0]:"dia", df.columns[1]:"device",
                              df.columns[2]:"impressoes", df.columns[3]:"cliques",
                              df.columns[4]:"ctr", df.columns[5]:"cpm", df.columns[6]:"investimento"})
    df = df[["dia","device","impressoes","cliques","ctr","cpm","investimento"]]
    df["dia"] = df["dia"].apply(fix_date)
    df = df[df["dia"].notna()]
    for c in ["impressoes","cliques","ctr","cpm","investimento"]: df[c] = df[c].apply(br_num)
upload(df, tbl("cora_devices"), "Dia x Device")

# 4 — formatos
df = ws(4)
if not df.empty:
    df = df.rename(columns={df.columns[0]:"dia", df.columns[1]:"estrategia",
                              df.columns[2]:"formato", df.columns[3]:"impressoes",
                              df.columns[4]:"cliques", df.columns[5]:"ctr",
                              df.columns[6]:"cpm", df.columns[7]:"investimento"})
    df = df[["dia","estrategia","formato","impressoes","cliques","ctr","cpm","investimento"]]
    df["dia"] = df["dia"].apply(fix_date)
    df = df[df["dia"].notna()]
    for c in ["impressoes","cliques","ctr","cpm","investimento"]: df[c] = df[c].apply(br_num)
upload(df, tbl("cora_formatos"), "Dia x Estratégia x Formato")

# 5 — criativos
df = ws(5)
if not df.empty:
    df = df.rename(columns={df.columns[0]:"dia", df.columns[1]:"estrategia",
                              df.columns[2]:"criativo", df.columns[3]:"impressoes",
                              df.columns[4]:"cliques", df.columns[5]:"ctr",
                              df.columns[6]:"cpm", df.columns[7]:"investimento"})
    df = df[["dia","estrategia","criativo","impressoes","cliques","ctr","cpm","investimento"]]
    df["dia"] = df["dia"].apply(fix_date)
    df = df[df["dia"].notna()]
    for c in ["impressoes","cliques","ctr","cpm","investimento"]: df[c] = df[c].apply(br_num)
upload(df, tbl("cora_criativos"), "Dia x Estratégia x Criativo")

# 6-13 — estrategias individuais
upload(process_full(ws(6),  FULL_COLS),       tbl("cora_consolidado_cpm"), "Consolidado CPM")
upload(process_full(ws(7),  FULL_COLS),       tbl("cora_consolidado_cpc"), "Consolidado CPC")
upload(process_full(ws(8),  FULL_COLS),       tbl("cora_display"),         "Display (CPM)")
upload(process_full(ws(9),  FULL_COLS),       tbl("cora_retargeting"),     "Retargeting (CPM)")
upload(process_full(ws(10), FULL_COLS_VIDEO), tbl("cora_video"),           "Vídeo + views/vtr")
upload(process_full(ws(11), FULL_COLS),       tbl("cora_push"),            "Push (CPC)")
upload(process_full(ws(12), FULL_COLS),       tbl("cora_native"),          "Native (CPC)")

print("\nConcluído.")
