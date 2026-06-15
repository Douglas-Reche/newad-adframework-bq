"""
IO Plan Admin — mini Cloud Run service
Protected by static token in URL: /?token=<SYNC_TOKEN>
Provides on-demand sync buttons + last-sync status.
"""

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

# Ensure the sync script is importable (same container image)
sys.path.insert(0, "/app/scripts/io_plan")
from sync_drive import run_sync, CLIENT_MAP  # noqa: E402

log = logging.getLogger("uvicorn.error")

app = FastAPI(docs_url=None, redoc_url=None)

SYNC_TOKEN = os.environ.get("SYNC_TOKEN", "")

# Simple in-memory log of the last sync result (reset on container restart)
_last_result: dict = {}


def _check_token(token: Optional[str]):
    if not SYNC_TOKEN:
        raise RuntimeError("SYNC_TOKEN env var not set — refusing all requests")
    if token != SYNC_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


@app.get("/", response_class=HTMLResponse)
def index(token: Optional[str] = Query(default=None)):
    _check_token(token)

    client_buttons = "".join(
        f"""
        <form method="post" action="/sync" style="display:inline">
          <input type="hidden" name="token" value="{token}">
          <input type="hidden" name="client" value="{name.lower()}">
          <button type="submit" class="btn btn-client">Sync {name}</button>
        </form>"""
        for name in CLIENT_MAP
    )

    last_html = ""
    if _last_result:
        ts = _last_result.get("timestamp", "—")
        results = _last_result.get("results", [])
        rows = "".join(
            f"<tr><td>{r['client']}</td><td>{r.get('processed',0)}</td>"
            f"<td>{r.get('skipped',0)}</td>"
            f"<td>{'✅' if not r.get('error') else '❌ ' + r.get('error','')}</td></tr>"
            for r in results
        )
        last_html = f"""
        <div class="card">
          <h3>Last sync — {ts}</h3>
          <table>
            <thead><tr><th>Client</th><th>Synced</th><th>Skipped</th><th>Status</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IO Plan Admin</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, sans-serif; background: #f0f2f5; color: #1a1a2e;
            display: flex; justify-content: center; padding: 40px 16px; }}
    .container {{ width: 100%; max-width: 640px; }}
    h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
    p.sub {{ font-size: .85rem; color: #666; margin-bottom: 24px; }}
    .card {{ background: #fff; border-radius: 10px; padding: 24px;
             box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 20px; }}
    .card h2 {{ font-size: 1rem; margin-bottom: 16px; }}
    .card h3 {{ font-size: .9rem; color: #555; margin-bottom: 12px; }}
    .btn {{ display: inline-flex; align-items: center; justify-content: center;
            border: none; border-radius: 6px; font-size: .9rem;
            padding: 10px 18px; cursor: pointer; font-weight: 500;
            transition: background .15s; }}
    .btn-primary {{ background: #2563eb; color: #fff; }}
    .btn-primary:hover {{ background: #1d4ed8; }}
    .btn-client {{ background: #e8f0fe; color: #2563eb; margin-right: 8px; }}
    .btn-client:hover {{ background: #d2e3fc; }}
    .btn-force {{ background: #fef3c7; color: #92400e; margin-left: 8px; }}
    .btn-force:hover {{ background: #fde68a; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
    th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }}
    th {{ color: #6b7280; font-weight: 500; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>IO Plan Admin</h1>
    <p class="sub">Sincronização de planos de veiculação do Google Drive → BigQuery</p>

    <div class="card">
      <h2>Sync todos os clientes</h2>
      <div class="actions">
        <form method="post" action="/sync">
          <input type="hidden" name="token" value="{token}">
          <button type="submit" class="btn btn-primary">&#9654; Sync All</button>
        </form>
        <form method="post" action="/sync">
          <input type="hidden" name="token" value="{token}">
          <input type="hidden" name="force" value="true">
          <button type="submit" class="btn btn-force">&#9654; Sync All (forçar)</button>
        </form>
      </div>
    </div>

    <div class="card">
      <h2>Sync por cliente</h2>
      <div class="actions">
        {client_buttons}
      </div>
    </div>

    {last_html}
  </div>
</body>
</html>
""")


@app.post("/sync")
async def sync(request: Request):
    form = await request.form()
    token = form.get("token") or request.query_params.get("token")
    client_filter = form.get("client") or request.query_params.get("client")
    force = (form.get("force") or request.query_params.get("force", "")).lower() == "true"

    _check_token(token)

    log.info(f"Manual sync triggered — client={client_filter or 'all'} force={force}")
    try:
        results = run_sync(client_filter=client_filter or None, force=force)
    except Exception as e:
        log.error(f"Sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    global _last_result
    _last_result = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "results": results,
    }

    # Redirect back to the main page
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/?token={token}", status_code=303)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
def status(token: Optional[str] = Query(default=None)):
    _check_token(token)
    return JSONResponse(_last_result or {"message": "No sync run yet in this instance"})
