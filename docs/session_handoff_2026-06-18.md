# Handoff de Sessão — 2026-06-18

> Estado ao fim da sessão. Leia antes de continuar qualquer trabalho de ETL.

---

## O que foi feito nesta sessão

1. **DROP completo** de `raw.*` (exceto `io_plan_drive_snapshot`), `stg.*`, `gold.*` — 30+29+8 tabelas
2. **Design RAW** completo T1–T7 para MediaSmart, MGID, Siprocal — ver `raw_layer_design.md`
3. **T1 MS implementada e validada em produção:**
   - DDL: `raw/ddl/ms_advertisers.sql` ✅
   - Connector: `fetch_advertisers()` em `connectors/mediasmart.py` ✅
   - Orchestrator: dispatch `/api/advertisers` em `orchestrator.py` ✅
   - Firestore job: `mediasmart_firstlevel_advertisers` ✅
   - Resultado: `rows_loaded: 21` — Cloud Run `adframework-etl-00253-2kx`

---

## Estado atual da RAW

| Tabela | Estado |
|---|---|
| `raw.io_plan_drive_snapshot` | ✅ Existe (preservada) |
| `raw.ms_advertisers` | ✅ Existe — 21 linhas — schedule `0 4 * * *` |
| `raw.mg_clients` | ❌ Não existe — T1 MGID pendente |
| `raw.sp_clients` | ❌ Não existe — T1 Siprocal pendente |
| Todos os demais (T2–T7) | ❌ Não existem — a implementar |

---

## Próximos passos imediatos (próxima sessão)

### T1 MGID — `raw.mg_clients`

- A API MGID **não tem endpoint de listagem de clientes** — os `client_ids` devem vir de uma lista fixa no Firestore job config (`params_json.client_ids`)
- Para cada `client_id`: chamar `GET /v1/clients/{id}` + `GET /v1/goodhits/clients/{id}/campaigns`
- Gravar 1 linha por cliente (WRITE_TRUNCATE)
- Campos esperados: `client_id, client_name, currency, timezone, campaigns_count, platform, raw_ingested_at`
- **Descobrir os `client_ids` válidos antes de implementar** — ver `core.platform_client_links` para os IDs MGID ativos

### T1 Siprocal — `raw.sp_clients`

- Dados vêm do Google Sheets flat file (mesmo que `sp_delivery`)
- `SiproCalConnector.fetch_clients()` — derivar clientes únicos do flat file por `pi_externo`
- **Nota:** `pi_externo` não é estável por cliente — muda por campanha/período. T1 Siprocal tem valor limitado.
- Gravar 1 linha por `pi_externo` único (WRITE_TRUNCATE)

### Após T1 completo (todas as 3 plataformas): ir para T2

---

## Regras de orquestração descobertas nesta sessão

### Regra 1 — Credencial MediaSmart: SEMPRE usar fallback para env vars

**O Firestore `platform_credentials/mediasmart.secrets` está desatualizado.**

Todo job MediaSmart que usa `_run_generic_report()` deve ter o padrão try/except:

```python
try:
    connector = MediasmartConnector(connector_cfg)
    records = connector.fetch_something()
except Exception as exc:
    err = str(exc).lower()
    if connector_cfg.get("username") and "invalid" in err and "username" in err:
        has_env_fallback = bool(os.getenv("MEDIASMART_USERNAME") and os.getenv("MEDIASMART_PASSWORD"))
        if has_env_fallback:
            connector = MediasmartConnector({})  # lê MEDIASMART_USERNAME/PASSWORD das env vars
            records = connector.fetch_something()
        else:
            raise
    else:
        raise
```

- `connector_cfg` é montado pelo orquestrador como `{"username": creds.get("email"), "password": creds.get("password")}`
- `MediasmartConnector({})` funciona porque o `__init__` faz `os.getenv()` como fallback quando o config está vazio

### Regra 2 — `fetch_*()` methods: normalizar 3 formatos de resposta

A API MediaSmart pode retornar:
1. Lista de objetos: `[{...}, {...}]`
2. Dict keyed: `{"event_id1": {...}, "event_id2": {...}}`
3. Dict com wrapper: `{"data": [{...}, {...}]}`

O `fetch_advertisers()` implementado já trata os 3. Todos os novos `fetch_*()` devem usar a mesma lógica de normalização.

### Regra 3 — Deploy: `gcloud builds submit` + `gcloud run deploy --image` (NUNCA `--source .`)

```bash
IMAGE="us-central1-docker.pkg.dev/adframework/cloud-run-source-deploy/adframework-etl:latest"
gcloud builds submit --tag $IMAGE --quiet
gcloud run deploy adframework-etl --image $IMAGE --region us-central1 --quiet
```

`--source .` gera imagem sem tag que o Cloud Run não consegue importar (`ContainerImageImportFailed`).

### Regra 4 — Dispatch de job: POST com token de identidade

```powershell
$url = "https://adframework-etl-911847757485.us-central1.run.app/jobs/{job_name}/run"
$TOKEN = (gcloud auth print-identity-token)
Invoke-RestMethod -Uri $url -Method Post -Headers @{ Authorization = "Bearer $TOKEN" } -ContentType "application/json" -Body "{}"
```

### Regra 5 — O orchestrator despacha jobs por `(platform_id, update_type)`

```
mediasmart + daily     → _run_mediasmart_daily()
mediasmart + firstlevel → _run_generic_report() (onde o dispatch por endpoint_path vive)
mgid + daily           → _run_mgid_daily()
siprocal + daily       → _run_siprocal_daily()
```

Jobs firstlevel para MGID e Siprocal seguirão o mesmo padrão de `_run_generic_report()` — verificar se a função já tem dispatch para essas plataformas antes de criar novos métodos.

---

## Informações comerciais confirmadas (para uso futuro no core)

### `core.dict_format` — mapeamento formato × plataforma → goal_type

| Formato | Plataforma | goal_type |
|---|---|---|
| Display | MediaSmart | CPM |
| Vídeo | MediaSmart | CPM |
| Retargeting | MediaSmart | CPM |
| Native | MediaSmart / MGID | CPC |
| Push | MGID / Siprocal | CPC |
| App Install | *(futuro)* | CPI |
| Social (Facebook/Instagram/Google) | *(futuro)* | CPM |

### Tamanhos de imagem de criativo

| Plataforma | width | height |
|---|---|---|
| MediaSmart | variável (API expõe) | variável |
| MGID | 1280 | 720 (fixo pelo comercial) |
| Siprocal | 1280 | 720 (fixo pelo comercial) |

---

## Pendência — campo `estrategia` no IO Plan

O campo `estrategia` em `raw.io_plan_drive_snapshot` contém o formato de campanha embutido (native, push, display, etc.). Antes de usar esse campo no STG/gold, será necessário extrair o formato em uma coluna separada.

**Decisão de onde fazer o parse:** na **STG** (não na ingestão) — RAW deve permanecer fiel ao Google Drive.

**Exemplos:**
- `"Native - Performance"` → `formato = "native"`
- `"Push - Awareness"` → `formato = "push"`
- `"Display CPM"` → `formato = "display"`

Implementar no STG do IO Plan quando essa camada for construída.

---

## Referências rápidas

| O quê | Onde |
|---|---|
| Design da RAW layer | `docs/raw_layer_design.md` |
| Análise API-first MS | `docs/mediasmart_raw_sketch.md` |
| Análise API-first MGID | `docs/mgid_raw_sketch.md` |
| Análise Siprocal | `docs/siprocal_raw_sketch.md` |
| Histórico completo | `CHANGELOG.md` |
| DDL T1 MS | `raw/ddl/ms_advertisers.sql` |
| Orchestrator | `adframework_python/src/orchestrator.py` |
| Connector MS | `adframework_python/src/connectors/mediasmart.py` |
| Cloud Run | `adframework-etl-911847757485.us-central1.run.app` |
| Revisão atual | `adframework-etl-00253-2kx` |
