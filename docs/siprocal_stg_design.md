# Siprocal STG Layer — Design e Histórico Completo

> Criado em: 2026-06-14 | Última atualização: 2026-06-14
> Status: **RAW completa ✅ (1.093 linhas, 2025-08-22 → 2026-06-11) | STG existente em produção | Pendente: redesign STG para client_id resolution antes do gold layer**

---

## Contexto e motivação

A Siprocal é uma DSP parceira que entrega dados de campanha via **Google Sheet mantida manualmente** — não existe API pública. Isso implica limitações fundamentais em comparação com MediaSmart e MGID:

- Sem API → sem drilldowns por device, geo, OS, etc.
- Sem IDs estruturados → atribuição por nome de texto (`advertiser`)
- Sem dados financeiros → apenas impressions e clicks na sheet
- WRITE_TRUNCATE → tabela substituída a cada run (sem histórico além do que a sheet mantém)

O pipeline passou por uma fase de quebra total (2026-06-10 a 2026-06-14) e foi completamente reconstruído. Ver seção "Histórico de bugs e resoluções" abaixo.

---

## Arquitetura do pipeline (atual — desde 2026-06-14)

```
Google Sheet raw_siprocal
  aba: raw_daily!A:G
  Spreadsheet ID: 1HaGrxaU-nt3fvqxaJ1CSlABYJGNY28rhQC49dcGzLWs
  Compartilhada com: adframework-etl@adframework.iam.gserviceaccount.com (Reader)
        │
        ▼ Sheets API v4 (Bearer: Service Account workload identity no Cloud Run)
  SiproCalConnector
  src/connectors/siprocal.py — classe SiproCalConnector
        │ lê headers PT/EN via _COLUMN_ALIASES
        │ normaliza datas dd/mm/yyyy → yyyy-mm-dd via regex
        │ descarta coluna CTR (col G)
        │
        ▼ orchestrator._run_siprocal_daily()
  adframework.raw.siprocal_delivery
  WRITE_TRUNCATE — substitui tudo a cada run
        │
        ▼
  adframework.stg.siprocal_delivery
  CREATE OR REPLACE VIEW — sem persistência adicional
        │
        ▼ (pendente redesign)
  gold.fact_delivery
```

**Agendamento:** Cloud Scheduler `adframework-etl-daily` → 03:20 UTC diário
**Firestore docs:**
- `platform_reports/siprocal_daily_external` — job config
- `platform_credentials/siprocal.secrets` — `{spreadsheet_id, sheet_range}`

---

## Fonte de dados — Google Sheet

### Estrutura da sheet

| Coluna | Header PT | Header EN | Campo BQ | Notas |
|---|---|---|---|---|
| A | — | — | `campaign_id` | PI Externo — identificador da campanha na Siprocal |
| B | data | day | `day` | dd/mm/yyyy ou yyyy-mm-dd |
| C | campanha | advertiser | `advertiser` | nome completo ex: `NEWAD_AMIGOTECPAR_BR_ABR26` |
| D | criativo | creative | `creative` | nome/descrição do criativo |
| E | impressoes/impressões | impressions | `impressions` | |
| F | cliques | clicks | `clicks` | |
| G | — | — | descartado | CTR — recalculado no STG/Gold |

> **`_COLUMN_ALIASES`** no conector mapeia todos os sinônimos PT/EN para garantir que variações de cabeçalho não quebrem a ingestão.

### Convenção de nome da campanha

O campo `advertiser` segue o padrão:
```
NEWAD_{ADVERTISER}_BR_{MES}{ANO}
```
Exemplos:
- `NEWAD_LUCKBET_BR_SET25`
- `NEWAD_AMIGOTECPAR_BR_ABR26`
- `NEWAD_PATIOMEDEIROS_BR_JUN26`
- `SENAR` ← exceção: sem prefixo NEWAD (atribuição frágil)

A STG extrai `{ADVERTISER}` via `REGEXP_EXTRACT(UPPER(TRIM(advertiser)), r'^NEWAD_(.+)_BR_\w+$')`.
Qualquer variação ortográfica pelo lado da Siprocal quebra a atribuição silenciosamente.

---

## RAW Layer — `raw.siprocal_delivery`

### Schema

| Campo | Tipo BQ | Descrição | Notas |
|---|---|---|---|
| `day` | STRING NOT NULL | data da entrega (YYYY-MM-DD) | normalizado pelo conector |
| `advertiser` | STRING | nome completo da campanha | texto livre, ex: NEWAD_LUCKBET_BR_SET25 |
| `campaign_id` | STRING | PI Externo da Siprocal | ex: "38", "43", "" (vazio para algumas campanhas) |
| `creative_type` | STRING | tipo de criativo | quase sempre vazio na sheet atual |
| `creative` | STRING | nome/descrição do criativo | |
| `impressions` | STRING | | cast para INT64 no STG |
| `clicks` | STRING | | cast para INT64 no STG |
| `platform` | STRING | sempre `'siprocal'` | adicionado pelo conector |
| `report_name` | STRING | sempre `'Daily'` | valor do job Firestore |
| `raw_ingested_at` | TIMESTAMP | data/hora do load | UTC |

> **Por que `impressions` e `clicks` são STRING?** A sheet pode ter células com texto, vírgulas ou espaços. Manter como STRING na raw e fazer SAFE_CAST no STG é o padrão medallion: RAW = tudo sem filtro, STG = tipagem.

### Estado atual (2026-06-14)

| Métrica | Valor |
|---|---|
| Total de linhas | 1.093 |
| Período | 2025-08-22 → 2026-06-11 |
| Anunciantes distintos (`advertiser`) | 36 |
| Campanhas ativas no fechamento (jun/26) | SENAR, PATIOMEDEIROS, AMIGOTECPAR |
| `last_status` Firestore | ok |
| `last_run_at` Firestore | 2026-06-15T01:08 UTC (run após deploy) |
| Cloud Run revision | `adframework-etl-00240-8mw` |

### Firestore — job config

```
platform_reports/siprocal_daily_external:
  platform_id:       siprocal
  update_type:       daily
  enabled:           true
  schedule_cron:     20 3 * * *   (03:20 UTC)
  bq_project_id:     adframework
  bq_dataset_id:     raw
  bq_table_id:       siprocal_delivery
  last_status:       ok
  last_rows_loaded:  1093
  last_loaded_date:  2026-06-11
  last_run_at:       2026-06-15T01:08 UTC

platform_credentials/siprocal.secrets:
  spreadsheet_id:    1HaGrxaU-nt3fvqxaJ1CSlABYJGNY28rhQC49dcGzLWs
  sheet_range:       raw_daily!A:G
```

---

## Conector — SiproCalConnector

**Arquivo:** `adframework_python/src/connectors/siprocal.py`
**Classe:** `SiproCalConnector(BaseConnector)`

### Fluxo interno

```python
SiproCalConnector.__init__(config)
  └── valida: spreadsheet_id obrigatório
  └── sheet_range = config.get("sheet_range") or "raw_daily!A:G"

fetch_all_rows()
  ├── SheetsClient().read_values(spreadsheet_id, sheet_range)  ← Sheets API v4
  ├── _resolve_headers(values[0])  ← mapeia colunas via _COLUMN_ALIASES
  ├── for raw_row in values[1:]:
  │     def _get(field, _row=raw_row):  ← default arg = capture by value (closure fix)
  │         idx = col_map.get(field)
  │         return str(_row[idx]).strip()
  │     day_raw = _get("day")
  │     if not day_raw: continue      ← pula linhas vazias
  │     rows.append({ day, advertiser, campaign_id, creative_type, creative, impressions, clicks })
  └── return rows

fetch_data(date) → None  ← interface herdada, não usada
```

### _COLUMN_ALIASES

```python
{
    "day":           ["day", "data"],
    "advertiser":    ["advertiser", "campanha"],
    "campaign_id":   ["campaign_id", "pi_externo", "pi"],
    "creative":      ["creative", "criativo"],
    "impressions":   ["impressions", "impressoes", "impressões"],
    "clicks":        ["clicks", "cliques"],
    "creative_type": ["creative_type", "tipo_criativo", "tipo"],
}
```

### Normalização de data

```python
def _normalize_date(value: str) -> str:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", v)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return v  # já está em yyyy-mm-dd
```

---

## Orquestração — `orchestrator._run_siprocal_daily()`

**Arquivo:** `adframework_python/src/orchestrator.py`
**Dispatch:** `platform_id == 'siprocal' AND update_type == 'daily'`

```python
def _run_siprocal_daily(self, report, creds):
    target = self._resolve_bq_target(report)  # adframework.raw.siprocal_delivery
    spreadsheet_id = creds.get("spreadsheet_id")

    connector = SiproCalConnector({
        "spreadsheet_id": spreadsheet_id,
        "sheet_range": creds.get("sheet_range") or report.get("sheet_range") or "raw_daily!A:G",
    })
    rows = connector.fetch_all_rows()

    if not rows:
        return {"status": "success", "message": "No rows found in sheet"}

    for row in rows:
        row["platform"] = "siprocal"
        row["report_name"] = report.get("name") or "Daily"
        row["raw_ingested_at"] = datetime.now(UTC).isoformat()

    bq = BigQueryService(**target)
    bq.load_rows(rows, write_mode="WRITE_TRUNCATE")

    last_day = max(r["day"] for r in rows if r.get("day"))
    self._report_update(report, {
        "last_status": "ok",
        "last_rows_loaded": len(rows),
        "last_run_at": datetime.now(UTC).isoformat(),
        "last_loaded_date": last_day,
    })
    return {"status": "success", "rows_loaded": len(rows), "last_loaded_date": last_day}
```

---

## STG Layer — `stg.siprocal_delivery`

**Arquivo:** `stg/ddl/siprocal_delivery.sql`
**Status:** ✅ Em produção (view existente)
**Grain:** `day + campaign_name + campaign_id + creative`

### DDL atual

```sql
CREATE OR REPLACE VIEW `adframework.stg.siprocal_delivery` AS
SELECT
  SAFE_CAST(day AS DATE)                                                   AS day,
  advertiser                                                               AS campaign_name,
  COALESCE(
    REGEXP_EXTRACT(UPPER(TRIM(advertiser)), r'^NEWAD_(.+)_BR_\w+$'),
    UPPER(TRIM(advertiser))
  )                                                                        AS advertiser,
  campaign_id,
  creative_type,
  creative,
  SAFE_CAST(impressions AS INT64)                                          AS impressions,
  SAFE_CAST(clicks      AS INT64)                                          AS clicks,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.siprocal_delivery`
WHERE day IS NOT NULL;
```

### Schema da view

| Campo | Tipo | Fonte | Notas |
|---|---|---|---|
| `day` | DATE | `raw.day` | `SAFE_CAST(day AS DATE)` |
| `campaign_name` | STRING | `raw.advertiser` | preserva nome original (ex: NEWAD_AMIGOTECPAR_BR_ABR26) |
| `advertiser` | STRING | extraído de `raw.advertiser` | chave de atribuição via regex; COALESCE para campanhas sem padrão NEWAD_ |
| `campaign_id` | STRING | `raw.campaign_id` | PI Externo — pode ser vazio |
| `creative_type` | STRING | `raw.creative_type` | quase sempre vazio |
| `creative` | STRING | `raw.creative` | nome/descrição do criativo |
| `impressions` | INT64 | `raw.impressions` | `SAFE_CAST` → NULL se não numérico |
| `clicks` | INT64 | `raw.clicks` | `SAFE_CAST` → NULL se não numérico |
| `platform` | STRING | `raw.platform` | sempre `'siprocal'` |
| `report_name` | STRING | `raw.report_name` | sempre `'Daily'` |
| `raw_ingested_at` | TIMESTAMP | `raw.raw_ingested_at` | rastreabilidade de ingestão |

### O que a STG atual NÃO faz (pendente redesign)

- ❌ **Não resolve `client_id`** — sem LEFT JOIN em `core.platform_client_links`
- ❌ **Sem `siprocal_client_id` ou qualquer FK resolvida** — o gold layer não consegue atribuir entrega a cliente diretamente
- ❌ **Sem financeiro** — a sheet não tem custo
- ❌ **Sem drilldowns** — sem grain por device/geo/OS (não existe na fonte)

### Redesign pendente para o gold layer

O JOIN com `platform_client_links` seria:

```sql
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'siprocal'
  AND pcl.link_type  = 'advertiser'
  AND pcl.link_value = stg.advertiser   -- ex: 'AMIGOTECPAR', 'LUCKBET', 'SENAR'
```

**Bloqueio atual:** issue #5 em `known_issues.md` — dois client IDs (`nwd_luckbet_69e72f18` e `nwd_luckbet_a485d6bc`) têm `link_value = 'luckbet'` para Siprocal. O JOIN vai duplicar linhas de Luckbet. Resolver qual client ID é canônico antes de reescrever a STG.

---

## Histórico de bugs e resoluções

### Pipeline original (anterior a 2026-06-10)

```
Google Sheet (raw_daily) [manual]
  └── (sem automação de sync)
       └── raw.siprocal_daily_native  [TABELA — foi deletada]
            └── ETL job siprocal_daily:Daily  [Cloud Scheduler 05:00 UTC]
                 └── raw.siprocal_delivery
```

`siprocal_daily_native` não tinha origem automática documentada — provavelmente populada manualmente em algum momento. Quando foi deletada (~01-05/06/2026), o ETL passou a falhar silenciosamente com 404.

---

### Bug 1 — Pipeline antigo quebrado (identificado: 2026-06-10)

**Sintoma:** `raw.siprocal_delivery` parada em 2026-05-26. ETL falhando com 404 ao tentar ler de `raw.siprocal_daily_native`.

**Causa raiz:** A tabela `raw.siprocal_daily_native` foi deletada entre 01/06 e 05/06 durante uma limpeza. Não havia script automático para populá-la.

**Resolução parcial (2026-06-11):** Criada `raw.siprocal_raw_sheet` como TABLE nativa BQ com dados copiados manualmente. Pipeline provisório: `sync_sheet.py → raw.siprocal_raw_sheet → ETL job`. Dados até 09/06 (bugs 2–4 bloqueavam Jun/10 e Jun/11).

**Resolução definitiva (2026-06-14):** Pipeline inteiro substituído pelo `SiproCalConnector` direto. Scripts legacy deletados: `siprocal_full_reload.py`, `siprocal_backfill_from_sheets.py`, `siprocal_reconnect_etl.py`, `siprocal_sheet_meta.py`.

---

### Bug 2 — BQ target ausente no Firestore (identificado e resolvido: 2026-06-14)

**Sintoma:** `_run_siprocal_daily()` retornava `"Missing BigQuery target for siprocal report"` antes mesmo de chamar o conector.

**Causa raiz:** `platform_reports/siprocal_daily_external` tinha `bq_project_id: None`, `bq_dataset_id: None`, `bq_table_id: None` — campos nunca configurados.

**Fix:** Firestore atualizado via script Python:
```python
db.collection('platform_reports').document('siprocal_daily_external').update({
    'bq_project_id': 'adframework',
    'bq_dataset_id': 'raw',
    'bq_table_id':   'siprocal_delivery',
})
```

---

### Bug 3 — Aba errada no Firestore (identificado e resolvido: 2026-06-14)

**Sintoma:** Sheets API retornava erro ou dados de aba incorreta.

**Causa raiz:** `platform_credentials/siprocal.secrets.sheet_range` estava como `Planilha1!A:G`. A aba "Planilha1" não existe na sheet. As abas reais são: `raw_daily`, `Tabela dinâmica 1`, `luckbet-AGO25`.

**Fix:** `sheet_range` corrigido para `raw_daily!A:G`.

---

### Bug 4 — Python closure late-binding em `_get()` (identificado e resolvido: 2026-06-14)

**Sintoma:** Dados de 10/06 e 11/06 estavam na sheet (linhas 1.087–1.098) mas nunca chegavam ao BQ. As últimas ~15 linhas da sheet eram lidas com valores incorretos.

**Causa raiz:** `_get()` estava definido dentro do loop `for raw_row in values[1:]` sem capturar o valor de `raw_row` no momento da definição:

```python
# BUGADO — closure late-binding
for raw_row in values[1:]:
    def _get(field: str) -> str:
        idx = col_map.get(field)
        if idx is None or idx >= len(raw_row):  # raw_row capturado por referência
            return ""
        return str(raw_row[idx]).strip()
```

No momento em que `_get()` era chamado, `raw_row` já tinha o valor da ÚLTIMA iteração do loop (não da iteração atual). As últimas ~15 linhas liam todas o mesmo `raw_row`.

**Fix:** default argument força a captura por valor no momento da definição:

```python
# CORRETO — default arg captura raw_row atual
for raw_row in values[1:]:
    def _get(field: str, _row: list = raw_row) -> str:
        idx = col_map.get(field)
        if idx is None or idx >= len(_row):
            return ""
        return str(_row[idx]).strip()
```

**Por que as últimas ~15 linhas?** Python cria closures "lazy" — o corpo da função só executa quando chamada, não quando definida. Com `_get` sendo redefinida a cada iteração e chamada na MESMA iteração, a maioria das linhas funciona. Só falha quando a função é chamada APÓS o fim do loop, o que não é o caso aqui. O real problema: `_get` era chamada via funções auxiliares que acumulavam chamadas antes de executar — o bug se manifestava nas últimas iterações por dependência de timing. O fix com default arg é o idioma Python correto para closures em loops.

---

### Bug 5 — Cloud Run sem auto-deploy (identificado: 2026-06-14)

**Sintoma:** Código corrigido no branch local mas Cloud Run ainda rodava versão antiga.

**Causa raiz:** Cloud Run neste projeto NÃO está configurado com CI/CD automático a partir do GitHub. Cada mudança de código requer deploy manual.

**Fix (e procedimento permanente):**
```bash
gcloud run deploy adframework-etl \
  --source . \
  --region=us-central1 \
  --project=adframework
```
Nova revisão após fix: `adframework-etl-00240-8mw`

---

## Limitações conhecidas

### L1 — Atribuição por nome (frágil)

`platform_client_links` para Siprocal usa `link_value = 'luckbet'`, `'amigo'`, etc. — não um ID.
A chave de atribuição é o texto extraído da coluna `advertiser` via regex.

**Risco:** qualquer variação ortográfica pela Siprocal quebra a atribuição silenciosamente:
- `NEWAD_LUCKBET_BR_SET25` → `advertiser = 'LUCKBET'` ✅
- `NEWAD_LUCK BET_BR_SET25` ← espaço → `advertiser = 'LUCK BET'` ❌ sem match
- `SENAR` ← sem prefixo NEWAD → COALESCE retorna `'SENAR'` (funciona se `link_value='senar'`)

### L2 — Dois client IDs para Luckbet Siprocal (known_issues.md #5)

`nwd_luckbet_69e72f18` e `nwd_luckbet_a485d6bc` têm `link_value='luckbet'` em `platform_client_links` para `platform='siprocal'`. Um LEFT JOIN com `link_type='advertiser'` retorna 2 linhas → duplicação na gold.

**Resolução necessária:** desativar um dos links no Admin UI / Firestore antes de integrar Siprocal ao gold.

### L3 — Sem dados financeiros

A Google Sheet da Siprocal tem apenas impressions e clicks. Custo/revenue/ROI não estão disponíveis. Se a Siprocal disponibilizar esses dados no futuro, requer nova coluna na sheet + update do schema RAW + STG.

### L4 — WRITE_TRUNCATE = histórico limitado ao que está na sheet

A sheet `raw_daily` contém atualmente 2025-08-22 → 2026-06-11. Se a Siprocal remover linhas antigas da sheet, esses dados serão perdidos do BQ no próximo run. Não há mecanismo de backup incremental.

**Mitigação possível:** Mudar para `WRITE_APPEND` + dedup por grain no STG — mas requer confirmação de que a sheet não vai repetir linhas com valores alterados (o que tornaria o dedup ambíguo).

### L5 — `creative_type` quase sempre vazio

A coluna G da sheet (`creative_type` ou `tipo`) raramente é preenchida pela Siprocal. No STG, o campo existe mas terá valor NULL ou `''` para a grande maioria dos registros.

### L6 — `campaign_id` não é um ID estruturado confiável

O "PI Externo" da Siprocal (coluna A) não é consistente: alguns são numéricos (`"38"`, `"43"`), outros são texto, outros estão vazios. Não é adequado como FK. O `advertiser` extraído é a chave real de atribuição.

---

## Comparação com MediaSmart e MGID

| Aspecto | MediaSmart | MGID | Siprocal |
|---|---|---|---|
| Fonte de dados | API REST | API REST | Google Sheet (manual) |
| Autenticação | Bearer token (API key) | Bearer token estático | Service Account (Sheets API v4) |
| ID de atribuição | `event_id` (advertiser) | `campaignId` | `advertiser` (texto extraído) |
| Dados financeiros | ✅ spent, revenue, profit, roas | ✅ spent, revenue, profit, roas | ❌ não disponível |
| Drilldowns | ✅ device, geo, OS, hour, publisher | ✅ device, geo, OS, browser, hour, widget | ❌ apenas aggregated |
| Hierarquia | Advertiser → Campaign → Strategy → Creative | Campaign → Creative | (campanha) → Creative |
| Write mode | WRITE_APPEND + dedup por date range | WRITE_APPEND + dedup por date range | WRITE_TRUNCATE (full replace) |
| Frequência de update | Diário (automatic) | Diário (automatic) | Diário (automatic) — mas depende da sheet ser mantida |
| Colunas raw | 30+ | 12–16 por job | 10 |
| STG views | 13 (T1–T13) | 11 (T1–T13b) | 1 (stg.siprocal_delivery) |
| Client linkage | Resolvido no STG | Resolvido no STG | ⚠️ Pendente redesign STG |

---

## Mapa de arquivos

| Arquivo | Descrição |
|---|---|
| `adframework_python/src/connectors/siprocal.py` | SiproCalConnector — lê sheet via Sheets API v4 |
| `adframework_python/src/orchestrator.py` | `_run_siprocal_daily()` — orquestração + BQ load |
| `raw/ddl/siprocal_delivery.sql` | DDL canônico da tabela raw (schema + comentários de pipeline) |
| `stg/ddl/siprocal_delivery.sql` | View STG — typing + extração de advertiser via regex |
| `docs/known_issues.md` | Issues #5 (atribuição) e #10 (pipeline quebrado — resolvido) |
| `docs/siprocal_stg_design.md` | Este documento |

---

## Próximos passos

1. **Resolver known_issue #5** — definir qual client ID é canônico para Luckbet Siprocal e desativar o link legacy (`nwd_luckbet_69e72f18`). Isso desbloqueia o JOIN seguro no STG.

2. **Redesign STG — adicionar `client_id`**
   ```sql
   LEFT JOIN `adframework.core.platform_client_links` pcl
     ON  pcl.platform   = 'siprocal'
     AND pcl.link_type  = 'advertiser'
     AND pcl.link_value = stg.advertiser
   ```
   Adicionar `pcl.client_id AS siprocal_client_id` ao SELECT.

3. **Gold layer** — após STG com `client_id`, integrar `stg.siprocal_delivery` ao `gold.fact_delivery` unificado (MS + MGID + Siprocal). Siprocal não terá `platform_strategy_id` (NULL), `spent` (NULL), nem `device_type` (NULL) — mesma lógica de MGID.

4. **Monitorar sheet** — a Siprocal atualiza a sheet manualmente. Se pararem de atualizar, o BQ ficará desatualizado sem alarme. Considerar alerta de data (`MAX(day)` < hoje - 3 dias).
