# CHANGELOG — AdFramework BQ Pipeline

> Registro cronológico de decisões, mudanças e evoluções arquiteturais.
> **Regra:** toda mudança relevante no pipeline, arquitetura ou decisão de negócio deve ser registrada aqui com data, motivo e arquivos tocados.
> Formato: mais recente no topo.

---

## 2026-06-12 — MediaSmart: backfill 2026 Grupo A — CONCLUÍDO ✅ + fix timeout ETL 10s→60s

**Autor:** Douglas Reche | **Resultado:** todas as 6 tabelas RAW Grupo A com histórico completo 2026.

### Estado final

| Tabela | Rows | Período | Obs |
|---|---|---|---|
| `raw.mediasmart_delivery_by_device` | 206.541 | 2026-01-01 → 2026-06-11 | ✅ |
| `raw.mediasmart_delivery_by_os` | 273.799 | 2026-01-01 → 2026-06-11 | ✅ |
| `raw.mediasmart_delivery_by_hour` | 5.430 | 2026-05-28 → 2026-06-11 | ✅ — sem dados no MS antes de Mai/28 |
| `raw.mediasmart_delivery_by_geo` | 8.417.374 | 2026-01-01 → 2026-06-11 | ✅ — dedup necessário (ver abaixo) |
| `raw.mediasmart_creative_daily` | 394.347 | 2026-01-01 → 2026-06-11 | ✅ |
| `raw.mediasmart_delivery_by_publisher` | 9.804.184 | 2026-01-01 → 2026-06-11 | ✅ |

### Fix: REQUEST_TIMEOUT_SECONDS 10s → 60s

Drilldowns de alta cardinalidade (`geo`: country+area+city, `publisher`: company+url+exchange) geravam relatórios na API que excediam o timeout de 10s. Fix: `adframework_python/src/connectors/mediasmart.py` linha 16 — `REQUEST_TIMEOUT_SECONDS = 60`. Commit `7bee5f9`. Deploy: Cloud Run revision `adframework-etl-00238-n4h`.

### Problemas enfrentados durante o backfill

1. **Cloud Run timeout (30 min)**: tabelas de alto volume (`geo`, `publisher`) precisaram de múltiplos triggers sequenciais — o ETL carrega dia a dia e 162 dias de geo levam ~43 min. Estratégia: atualizar `force_from_date` no Firestore a cada parada e retrigger.

2. **Duplicatas em delivery_by_geo**: segundo trigger com `force_from_date=2026-04-14` sobrepôs dados do primeiro trigger (Jan-Apr 13). Detectadas via `COUNT(*) vs COUNT(DISTINCT combos)`. Fix: `CREATE OR REPLACE TABLE ... AS SELECT DISTINCT *` → deduplication bem-sucedida.

3. **HTTP 503 MediaSmart**: servidor da MediaSmart retornou `Login failed: HTTP 503 - Under maintenance` durante publisher backfill. Transiente — retrigger após 30s resolveu.

4. **delivery_by_hour sem dados antes de Mai/28**: confirmado que MediaSmart não tem dados hourly antes de 2026-05-28 para as contas monitoradas. Dados corretos e completos para o período disponível.

### Arquivos tocados
- `adframework_python/src/connectors/mediasmart.py` ← timeout 10→60s (commit 7bee5f9)
- Firestore `platform_reports`: todos os `force_from_date` removidos de 6 docs
- `raw.mediasmart_delivery_by_geo` ← deduplicada com `SELECT DISTINCT *`
- `docs/known_issues.md` ← B1 + T1 movidos para Resolvidos; detalhe de causa raiz e fix (commit 6227da7)
- `docs/mediasmart_stg_design.md` ← backfill section: resultado real, volume comparativo, lições aprendidas; caminhos: `REQUEST_TIMEOUT_SECONDS` e `RATE_LIMIT_DELAY` com commits de ref (commit 6227da7)
- `docs/INDEX.md` ← datas e descrições atualizadas (commit 6227da7)

---

## 2026-06-12 — MediaSmart: backfill 2026 Grupo A — estado, problemas de API timeout e Firestore corrigidos

**Autor:** Douglas Reche | **Contexto:** executar backfill desde 2026-01-01 das 6 tabelas Grupo A criadas na sessão anterior. ETL disparado via HTTP API sequencialmente.

### Estado do backfill ao final da sessão 2026-06-12

| Tabela | Linhas BQ | Intervalo | Status | Ação pendente |
|---|---|---|---|---|
| `mediasmart_delivery_by_device` | 196.653 | 2026-01-01 → 2026-06-11 | ✅ COMPLETO | Nenhuma |
| `mediasmart_delivery_by_os` | 190.169 | 2026-01-01 → 2026-06-11 | ✅ COMPLETO | Nenhuma |
| `mediasmart_delivery_by_hour` | DROPPED | — | ❌ RESET | Retrigger após API recover |
| `mediasmart_delivery_by_geo` | sem tabela | — | ❌ API timeout | Retrigger após API recover |
| `mediasmart_creative_daily` | 42.531 | 2026-01-01 → 2026-01-20 | ⚠️ PARCIAL | Retrigger — continuará de Jan 21 |
| `mediasmart_delivery_by_publisher` | 117.867 | 2026-01-01 → 2026-01-06 | ⚠️ PARCIAL | Retrigger — continuará de Jan 7 |

### Problemas encontrados

**1. API MediaSmart — timeouts em cascata às ~12:17 UTC**

Todos os 4 jobs que falharam apresentaram o mesmo erro: `HTTPSConnectionPool(host='api.mediasmart.io', port=443): Read timed out. (read timeout=10)`. A API ficou lenta nesse horário. Os jobs `device` e `os` completaram antes (~12:18-12:19). Os jobs `hour`, `geo`, `creative`, `publisher` foram atingidos pelo timeout.

**2. delivery_by_hour — dados parciais com intervalo errado**

Quando o backfill do `hour` foi disparado, tinha data de início errada (carregou Mai 28-Jun 11 em vez de Jan 1-Jun 11). Causa: o `force_from_date=2026-01-01` estava correto no Firestore, mas o job pode ter encontrado a tabela já existente com dados históricos (de um trigger anterior ao DROP), e o `_get_date_range` usou max_date+1 em vez de force_from_date. Tabela dropada ao final da sessão para garantir reload limpo.

**3. force_from_date deixado em todos os docs — risco de duplicata**

Os jobs `device` e `os`, após completar, tinham `force_from_date=2026-01-01` ainda ativo no Firestore. Se o cron diário fosse rodar, recarregaria desde Jan 1 e duplicaria todo o histórico. Corrigido ao final da sessão.

### Correções aplicadas ao final desta sessão (Firestore + BQ)

```
Ação executada                                Estado após ação
─────────────────────────────────────────────────────────────
remove force_from_date → device               next cron carrega de max_date+1
remove force_from_date → os                  next cron carrega de max_date+1
force_from_date 2026-01-01 → 2026-01-21 → creative_daily   continua de Jan 21 sem duplicar
force_from_date 2026-01-01 → 2026-01-07 → publisher         continua de Jan 7 sem duplicar
force_from_date mantido 2026-01-01 → hour    tabela foi dropada, reload completo
force_from_date mantido 2026-01-01 → geo     sem tabela, reload completo
DROP raw.mediasmart_delivery_by_hour          removida para garantir schema correto no reload
```

### Próximos passos — quando MediaSmart API estiver estável

1. **Verificar API com request teste** (ver seção "Como testar API" em `mediasmart_stg_design.md`)
2. **Retrigger os 4 jobs** via HTTP API:
   ```
   TOKEN=$(gcloud auth print-identity-token)
   BASE=https://adframework-etl-911847757485.us-central1.run.app

   # menor volume primeiro — respeitar rate limit 128 req/min
   curl -s -X POST "$BASE/jobs/mediasmart_daily%3Adelivery_by_hour/run" -H "Authorization: Bearer $TOKEN"
   curl -s -X POST "$BASE/jobs/mediasmart_daily%3Adelivery_by_geo/run" -H "Authorization: Bearer $TOKEN"
   curl -s -X POST "$BASE/jobs/mediasmart_daily%3Acreative_daily/run" -H "Authorization: Bearer $TOKEN"
   curl -s -X POST "$BASE/jobs/mediasmart_daily%3Adelivery_by_publisher/run" -H "Authorization: Bearer $TOKEN"
   ```
3. **Verificar BQ após cada job** (row count + date range)
4. **Verificar schema de delivery_by_hour** após reload: `event_id`, `campaign_id`, `strategy_id`, `hour`, `final_price`, `media_cost__brl` presentes
5. **Após todos completos:** confirmar que `force_from_date` foi removido de todos os 6 docs no Firestore

### Arquivos tocados
- `CHANGELOG.md` ← este
- Firestore `platform_reports`: `params_json.force_from_date` atualizado para 4 docs
- `raw.mediasmart_delivery_by_hour` ← DROPPED (será recriado no próximo trigger)

---

## 2026-06-11 (sessão 2) — MediaSmart: correção de schema das 6 tabelas RAW Grupo A + investigação de ingestão

**Autor:** Douglas Reche | **Contexto:** investigação de `delivery_by_os` sem coluna `os` → revelou problema sistêmico de schema em todas as 6 tabelas Grupo A → diagnóstico, fix e verificação completa.

### Problema identificado e resolvido

**Sintoma inicial:** `raw.mediasmart_delivery_by_os` ingerindo dados (52 linhas/dia, granularidade correta) mas sem coluna `operating_system` — impossível saber qual OS corresponde a cada linha.

**Investigação (todos os paths verificados):**
- ✅ Código ETL `base.py` `normalize_data` — sem column mapping, apenas normalização BQ-safe
- ✅ Código ETL `orchestrator.py` `_run_mediasmart_daily` — sem schema enforcement
- ✅ Código ETL `bigquery.py` `load_data` — para tabelas EXISTENTES: mantém só colunas do schema existente
- ✅ Código Shiro (Admin UI `rshiro-newad/adframework`) — sem DDL pré-criado para as 6 tabelas
- ✅ Firestore `iter_params`/`field_var` — metadados do Admin UI, ignorados pelo ETL
- ✅ API MediaSmart — endpoint `/api/analytics/custom-report` é **FLEXÍVEL** (não fixo), retorna headers human-readable por drilldown
- ✅ API confirmada via test direto (2026-06-10): `"Event ID"` → `event_id`, `"Operating system"` → `operating_system`, `"Device type"` → `device_type`, etc.

**Root cause real:**
As 6 tabelas tinham sido criadas previamente por outro processo (ETL Shiro `aat-console`) que usa um **dicionário de mapeamento inverso**: `"Event ID"` → `eventid`, `"Campaign ID"` → `controlid`, `"Strategy ID"` → `strategyid`. Quando nosso ETL rodou pela primeira vez e encontrou as tabelas existentes, `bigquery.py:load_data` chamou o caminho "EXISTENTE" → dropped todas as colunas que não estavam no schema antigo (`event_id`, `operating_system`, `device_type`, etc.). Resultado: dimensões ingeridas com granularidade correta mas labels completamente perdidas.

**Fix executado:**
1. Todas as 6 tabelas dropadas via BQ Python client
2. Jobs re-trigados via ETL HTTP API `POST /jobs/{job_name}/run` (endpoint descoberto nesta sessão)
3. Tabelas recriadas do zero pelo ETL com schema nativo da API após `normalize_data`

**ETL HTTP API — endpoint descoberto (não estava documentado):**
```
Base URL: https://adframework-etl-911847757485.us-central1.run.app
GET  /jobs                      → lista todos os jobs enabled
POST /jobs/{job_name}/run       → dispara job específico (síncrono, Cloud Run-safe)
POST /run-all                   → dispara todos os jobs enabled
POST /scheduler/run-due         → dispara jobs cujo schedule_cron é due agora

Formato job_name: {platform_id}_{update_type}:{name}
Exemplos:
  mediasmart_daily:delivery_by_device
  mediasmart_daily:creative_daily
  mediasmart_firstlevel:campaigns
  mgid_daily:daily
  siprocal_daily:Daily

Autenticação: Bearer token (gcloud auth print-identity-token)
```

### Schemas verificados (tabelas recriadas com nomes nativos da API)

| Tabela | Cols | IDs | Dimensão | KPIs | Financeiro |
|---|---|---|---|---|---|
| `mediasmart_delivery_by_device` | 21 | `event_id, campaign_id, strategy_id` | `device_type, app_vs_web` | impressions…conv5 + video | `final_price, media_cost__brl` |
| `mediasmart_delivery_by_geo` | 22 | `event_id, campaign_id, strategy_id` | `country, area_name, city` | impressions…conv5 + video | `final_price, media_cost__brl` |
| `mediasmart_delivery_by_os` | 20 | `event_id, campaign_id, strategy_id` | `operating_system` | impressions…conv5 + video | `final_price, media_cost__brl` |
| `mediasmart_delivery_by_hour` | 20 | `event_id, campaign_id, strategy_id` | `hour` | impressions…conv5 + video | `final_price, media_cost__brl` |
| `mediasmart_delivery_by_publisher` | 12 | `event_id, campaign_id, strategy_id` | `publisher_company, publisher_url, ad_exchange` | impressions, clicks | `final_price, media_cost__brl` |
| `mediasmart_creative_daily` | 23 | `event_id, campaign_id, strategy_id` | `creative_id, creative_type, size, app_vs_web` | impressions…conv5 + video | `final_price, media_cost__brl` |

### Mapeamento completo API → BQ (confirmado por test direto 2026-06-10)

```
Drilldown param → API CSV header    → normalize_data (base.py) → BQ column
day             → "Day"              → day
eventid         → "Event ID"         → event_id
controlid       → "Campaign ID"      → campaign_id
strategyid      → "Strategy ID"      → strategy_id
strategyname    → "Strategy"         → strategy
convsource      → "Conversion source"→ conversion_source
devicetype      → "Device type"      → device_type
os              → "Operating system" → operating_system
source          → "App vs. Web"      → app_vs_web
countrycode     → "Country"          → country
georegion_areaname → "Area Name"     → area_name
city            → "City"             → city
publishercompany→ "Publisher Company"→ publisher_company
publisherurl    → "Publisher URL"    → publisher_url
exchange        → "Ad Exchange"      → ad_exchange
hour            → "Hour"             → hour
creativeid      → "Creative ID"      → creative_id
creativetype    → "Creative Type"    → creative_type
size            → "Size"             → size

KPIs (API header → BQ):
clientrevenue   → "Event revenue"    → event_revenue
convertedclientrevenue → "Final Price" → final_price
client_cost     → "Media Cost - BRL" → media_cost__brl   ← nota: double underscore (espaço + hífen)
```

### Decisão de design documentada

**Princípio: NO mapping dictionary no ETL raw layer.**

O `normalize_data` em `base.py` faz apenas normalização BQ-safe (lowercase, spaces→_, remove chars especiais). NÃO faz renomeação semântica. Motivação:

> "pois se adicionarmos no dicionário toda vez que tivermos um novo temos que mudar novamente não?" — Douglas, 2026-06-11

Com mapping dict: cada nova dimensão da API requer mudança de código. Com normalize puro: nova dimensão aparece automaticamente no RAW com nome derivado do header da API. O STG SQL é onde aplicamos renomeação semântica explícita via SELECT col AS alias.

Shiro fez o mapeamento no ETL dele provavelmente para padronizar todas as plataformas em uma nomenclatura comum — mas o lugar correto é o STG layer, não o RAW.

### Inconsistência de nomes entre fontes RAW (importante para STG)

| Tabela RAW | ID columns | Origem |
|---|---|---|
| `raw.mediasmart_delivery` | `eventid, controlid, strategyid, strategyname` | Schema antigo (Shiro mapping) |
| `raw.mediasmart_daily` | `eventid, controlid, strategyid, strategyname` | Schema antigo (Shiro/aat-console ainda popula) |
| `raw.mediasmart_delivery_by_*` | `event_id, campaign_id, strategy_id` | Schema novo (normalize_data puro) |
| `raw.mediasmart_creative_daily` | `event_id, campaign_id, strategy_id, creative_id` | Schema novo (normalize_data puro) |

**Impacto no STG:** T6 (`stg.ms_delivery`) usa `controlid`/`strategyid` das fontes antigas. T7/T9/T10/os/hour/publisher usam `campaign_id`/`strategy_id` das fontes novas. Ambos são o mesmo valor — nomes diferentes, mesma chave.

### Repositório e caminhos dos arquivos-chave

```
Repo: rshiro-newad/adframework  (local: c:\Users\dougl\OneDrive\Área de Trabalho\NEWAD PROJECT\DATASETS\adframework)
Branch ativa: chore/machine-restore-org

Arquivos do ETL Python:
  adframework_python/src/base.py           → normalize_data (normalização BQ-safe, sem mapping)
  adframework_python/src/connectors/mediasmart.py → RATE_LIMIT_DELAY=0.6, fetch_data, _build_url
  adframework_python/src/bigquery.py       → load_data (lógica NEW vs EXISTING table + column drop)
  adframework_python/src/orchestrator.py   → _resolve_bq_target, _get_date_range, _run_mediasmart_daily
  adframework_python/main.py               → FastAPI routes: /jobs, /jobs/{job_name}/run, /run-all

GCP:
  Cloud Run service: adframework-etl-911847757485.us-central1.run.app
  Firestore collection: platform_reports (doc_id = mediasmart_delivery_by_device etc.)
  BigQuery: adframework.raw.mediasmart_delivery_by_*  adframework.raw.mediasmart_creative_daily
```

### Linhas de dados carregadas após fix (2026-06-10 only — backfill pendente)

| Job | Linhas D-1 (2026-06-10) |
|---|---|
| `mediasmart_daily:delivery_by_device` | 31 |
| `mediasmart_daily:delivery_by_geo` | 728 |
| `mediasmart_daily:delivery_by_os` | 51 |
| `mediasmart_daily:delivery_by_hour` | 107 |
| `mediasmart_daily:delivery_by_publisher` | 9.820 |
| `mediasmart_daily:creative_daily` | 606 |

### Próximos passos documentados (backfill + STG)

Ver seção "Plano de Backfill Grupo A" em `mediasmart_stg_design.md`.

### Arquivos tocados (este repo — newad-adframework-bq)
- `docs/known_issues.md` ← issue #16 marcada como ✅ resolvida
- `docs/mediasmart_stg_design.md` ← Group A atualizado, schemas corretos, colnames, backfill plan
- `docs/CHANGELOG.md` ← este

---

## 2026-06-11 — MediaSmart: 6 novos jobs RAW, fixes Grupo D, rate limit fix, backfill

**Autor:** Douglas Reche | **Contexto:** expansão da ingestão MediaSmart — novos drilldowns e correções estruturais

### O que mudou

**1. Grupo A — 6 jobs bulk criados no Firestore e testados via Cloud Run**

| Job (Firestore doc id) | Tabela RAW | Drilldown principal | Schedule | Linhas D-1 |
|---|---|---|---|---|
| `mediasmart_creative_daily` | `raw.mediasmart_creative_daily` | creativeid, creativetype, size, source | 03:30 UTC | 12 |
| `mediasmart_delivery_by_device` | `raw.mediasmart_delivery_by_device` | devicetype, source | 03:35 UTC | 12 |
| `mediasmart_delivery_by_geo` | `raw.mediasmart_delivery_by_geo` | countrycode, georegion_areaname, city | 03:40 UTC | 739 |
| `mediasmart_delivery_by_publisher` | `raw.mediasmart_delivery_by_publisher` | publishercompany, publisherurl, exchange | 03:45 UTC | 10.735 |
| `mediasmart_delivery_by_os` | `raw.mediasmart_delivery_by_os` | os | 03:50 UTC | 52 |
| `mediasmart_delivery_by_hour` | `raw.mediasmart_delivery_by_hour` | hour | 03:55 UTC | 147 |

Todos usam `endpoint_id: mediasmart_ep_api-analytics-custom-report`, `update_type: daily`.
`convsource` adicionado ao drilldown de cada job (não é KPI — confirmado em produção com erro 400).
Schema do CSV é fixo (31 colunas) independente do drilldown — o drilldown controla granularidade.

**2. Grupo B — Rate limit fix (pré-requisito para Jobs 7-8)**

Commit `4d1662f` em `rshiro-newad/adframework`, branch `chore/machine-restore-org`:
- `adframework_python/src/connectors/mediasmart.py` — `RATE_LIMIT_DELAY` 0.3 → 0.6
- `adframework_python/src/orchestrator.py` — `time.sleep(0.3/0.15)` → 0.6 nos loops de iteração
- Deployado em Cloud Run revision `adframework-etl-00237-v88`

**3. Grupo D — Fixes em jobs existentes**

- `mediasmart_firstlevel_advertisers` → Firestore `write_mode: WRITE_TRUNCATE`
- `mediasmart_firstlevel_creatives` → Firestore `write_mode: WRITE_TRUNCATE`
- `mediasmart_firstlevel_campaigns` → Firestore `write_mode: WRITE_TRUNCATE` + BQ dedup: `CREATE OR REPLACE TABLE raw.mediasmart_campaigns ... WHERE rn = 1` (5.451 → 140 linhas)
- Gap 25–26/mai/2026 em `raw.mediasmart_daily` → `force_from_date` implementado em `_get_date_range` (orchestrator.py, mesmo commit `4d1662f`), job temporário `mediasmart_backfill_may2526` rodado e deletado, 26 linhas carregadas

**4. Descobertas documentadas**

- `convsource` é dimensão de drilldown, não KPI (API retorna 400 se colocado em `kpis`)
- `/api/analytics/custom-report` retorna schema fixo de 31 colunas; drilldown afeta agrupamento, não schema
- `os` como drilldown gera granularidade (52 linhas vs 7 do job principal) mas coluna `os` não aparece no CSV fixo — pendente investigar nome correto
- `force_from_date` em `params_json` permite backfills pontuais em qualquer job `update_type: daily`

**Arquivos tocados (este repo):**
- `docs/mediasmart_stg_design.md` ← atualizado (jobs 1-6 como ✅, Grupo D como ✅, pré-req B como ✅)
- `docs/known_issues.md` ← atualizado (issues 15, D1, D2 como resolvidas)
- `docs/INDEX.md` ← atualizado
- `CHANGELOG.md` ← este

**Arquivos tocados (repo `rshiro-newad/adframework`, commit `4d1662f`):**
- `adframework_python/src/connectors/mediasmart.py`
- `adframework_python/src/orchestrator.py`

---

## 2026-06-11 — Mapa de atribuição de IDs RAW→client_id + auditoria de cobertura

**Autor:** Douglas Reche | **Contexto:** auditoria de IDs antes de expandir o GOLD

### O que mudou

**1. `docs/id_attribution_map.md` — criado**
- Mapa completo da cadeia de atribuição para cada plataforma (MediaSmart, MGID, Siprocal, IO Plan)
- Tabela de cobertura de vínculos para os 26 clientes em `dim_client`
- Problemas identificados:
  - `ocupacional_98c851f5` sem nenhum vínculo em `platform_client_links` (100% unattributed)
  - `eventid` MediaSmart compartilhado Pardini/Ocupacional com `client_id` NULL (unresolved)
  - `fact_delivery.sql` usando `strategyid` em vez de `controlid` como `platform_campaign_id` para MediaSmart
  - 44 MGID campaignids ainda em `pending_confirmation`
- Lista priorizada de ações: 3 imediatas (A1-A3), 4 aguardando comercial (B1-B4), 4 contínuas (C1-C4)

**Arquivos tocados:**
- `docs/id_attribution_map.md` ← novo
- `docs/INDEX.md` ← atualizado
- `CHANGELOG.md` ← atualizado

---

## 2026-06-11 — Mapa de linhagem de colunas RAW→GOLD

**Autor:** Douglas Reche | **Contexto:** auditoria de cobertura de colunas — suspeita de perda de informações entre camadas

### O que mudou

**1. `docs/column_lineage_map.md` — criado**
- **Problema:** não havia documentação rastreando quais colunas do RAW sobrevivem até o GOLD. Suspeita de perda de métricas antes dos KPIs.
- **Conteúdo:** diagrama de arquitetura em camadas, cadeia de atribuição de cliente, tabelas de linhagem por plataforma (MediaSmart delivery/revenue/bid_supply, MGID, Siprocal, IO Plan), matriz de cobertura de métricas por view GOLD, e resumo priorizado de 9 lacunas identificadas.
- **Lacunas críticas documentadas:**
  - `mediasmart_bid_supply` inteiro fica órfão na STG (win rate, media cost, publisher performance nunca chegam no GOLD)
  - `unit_price` e `impressions_cpm` do IO plan não mapeados (CPM planejado impossível)
  - `video_*` ausentes no `fact_delivery` principal (Cora e Fintech sem métricas de vídeo)
  - Conversões MGID em colunas separadas (`mgid_conv_*`) — funis cross-platform somam só MediaSmart
  - `conversions_1-5` ausentes no `fct_cora_delivery_full`

**Arquivos tocados:**
- `docs/column_lineage_map.md` ← novo
- `docs/INDEX.md` ← atualizado
- `CHANGELOG.md` ← atualizado

---

## 2026-06-08 — Ativação de links Amigo + workaround MediaSmart + auditoria de APIs

**Autor:** Douglas Reche | **Contexto:** sprint de entrega dashboard Cora/TecPar (prazo 2026-06-11)

### O que mudou

**1. `core.platform_client_links` — 39 links Amigo ativados**
- **Problema:** `amigo_db1c2f0c` tinha 39 vínculos em `pending_confirmation` desde 2026-05-26 (1 eventid MediaSmart + 38 campaignids MGID). Toda entrega de Amigo aparecia como `unattributed` na gold.
- **Decisão:** Amigo é sub-cliente legítimo de TecPar (relação pai-filho confirmada por Douglas), não um erro de atribuição. Confirmação comercial já tinha acontecido do lado do Shiro. Os vínculos ficaram travados por falta de sincronização.
- **Ação:** `core/migration/05_activate_amigo_links.sql` — UPDATE de 39 linhas para `status = 'active'`.
- **Resultado:** `amigo_db1c2f0c` agora tem 40 links ativos (1 MS + 38 MGID + 1 Siprocal).

**2. `stg.mediasmart_delivery` — workaround para gap de dados**
- **Problema:** Job `mediasmart_daily_daily` no orchestrator (Shiro) com timeout desde ~01/jun/26. `raw.mediasmart_delivery` parado em 2026-05-24. `raw.mediasmart_daily` (staging intermediário do mesmo job) continua sendo alimentado.
- **Decisão:** Aplicar workaround na STG enquanto root cause é resolvido no orchestrator.
- **Ação:** `stg/ddl/mediasmart_delivery.sql` atualizado — adicionado `UNION ALL` com `raw.mediasmart_daily` filtrando datas > 2026-05-24. Comentário no SQL indica que este branch deve ser removido quando o orchestrator for corrigido.
- **Resultado:** `stg.mediasmart_delivery` agora cobre até 2026-06-07.

**3. `gold.fact_delivery` — reconstruída**
- **Ação:** `gold/ddl/fact_delivery.sql` executado em prod. Absorveu os dois fixes acima.
- **Resultado:** Cora e Amigo aparecem no gold com dados até 2026-06-07. TecPar hierarchy correta (Amigo level 2, TecPar level 1).

**4. Auditoria de APIs — MediaSmart e MGID**
- **Ação:** OpenAPI spec do MediaSmart (github.com/mediasmart/api-reference) e docs MGID analisados.
- **Resultado:** documentado em `docs/api_capabilities.md` e `docs/etl_expansion_plan.md`.

**Arquivos tocados:**
- `core/migration/05_activate_amigo_links.sql` ← novo
- `stg/ddl/mediasmart_delivery.sql` ← alterado
- `docs/known_issues.md` ← atualizado
- `docs/api_capabilities.md` ← novo
- `docs/etl_expansion_plan.md` ← novo
- `docs/commercial_questions.md` ← novo
- `CHANGELOG.md` ← novo
- `docs/INDEX.md` ← novo

**Issues abertas geradas:**
- `#8` `gold.fact_io_plan` — view quebrada, zero linhas (chain morta via `raw.luckbet_io_plan_snapshot` dropada)
- `#9` MediaSmart ETL timeout — root cause aberta no orchestrator (Shiro)

---

## 2026-06-03 — Gold layer unificada + pipeline health + conversions mapping

**Autor:** Douglas Reche

### O que mudou

**1. `gold.fact_delivery` — criada (substituindo views fragmentadas)**
- **Problema:** gold tinha views separadas por cliente (`fct_cora_delivery_full`, `fct_luckbet_delivery_full`) sem modelo unificado. Power BI conectava a múltiplas fontes inconsistentes.
- **Decisão:** criar tabela materializada única `gold.fact_delivery` com grain `day + client_id + platform + platform_campaign_id`, cobrindo MediaSmart + MGID + Siprocal. Revenue MediaSmart agora joinado DEPOIS da agregação de delivery para evitar multiplicação por número de eventids.
- **Arquivo:** `gold/ddl/fact_delivery.sql`

**2. `gold.dim_campaign` — criada**
- **Arquivo:** `gold/ddl/dim_campaign.sql`

**3. `gold.dim_conversion_mapping` — criada**
- Mapeamento de conv_1-5 por cliente para labels de negócio. Luckbet mapeado. Outros clientes pendentes de confirmação comercial.
- **Arquivo:** `gold/ddl/dim_conversion_mapping.sql` + `core/seeds/conversion_mapping.csv`

**4. `gold.pipeline_health` — view de monitoramento**
- **Arquivo:** `gold/ddl/pipeline_health.sql`

**5. `docs/pipeline_complete_map.md` — mapeamento completo do pipeline**
- 1.300+ linhas documentando cada tabela, grain, fonte, período e issues abertas.

**Arquivos tocados:**
- `gold/ddl/fact_delivery.sql` ← novo
- `gold/ddl/dim_campaign.sql` ← novo
- `gold/ddl/dim_conversion_mapping.sql` ← novo
- `gold/ddl/pipeline_health.sql` ← novo
- `core/seeds/conversion_mapping.csv` ← novo
- `docs/pipeline_complete_map.md` ← novo
- `docs/known_issues.md` ← atualizado

---

## 2026-05-26 — RAW + STG rebuild: sistema canônico de IDs de cliente

**Commit:** `7ac505c` | **Autor:** Douglas Reche

### O que mudou e por quê

**Decisão central:** Adotar `{slug}_{hash8}` como formato canônico de `client_id` (ex: `banco_cora_fe13d78a`). O formato anterior do Shiro (`nwd_{slug-com-hifens}_{hash8}`) continua existindo no Admin UI mas nunca é usado no pipeline ETL. JOINs diretos entre os dois sistemas são impossíveis por design.

**1. `core.dim_client` + `core.platform_client_links` — criadas**
- `dim_client`: tabela de clientes com hierarquia pai-filho (`parent_client_id`, `client_level`), slugs imutáveis, seed via CSV.
- `platform_client_links`: mapeamento `(platform, link_type, link_value)` → `client_id` com campo de status (`active`/`pending_confirmation`/`unresolved`).
- **Arquivos:** `core/ddl/dim_client.sql`, `core/seeds/clients.csv`, `core/migration/01_load_dim_client.sql`

**2. Raw DDLs formalizados para todas as plataformas**
- `raw.mediasmart_delivery` — grain: day+eventid+controlid+strategyid+convsource
- `raw.mediasmart_revenue` — grain: day+controlid+strategyid+revenuesource
- `raw.mediasmart_bid_supply` — dados de leilão horário
- `raw.mgid_delivery` — grain: day+campaignid+(teaserId opcional)
- `raw.siprocal_delivery` — grain: day+advertiser+campaign_id+creative_type+creative
- + DDLs de dimensões: mediasmart_advertisers, campaigns, creatives; mgid_campaigns, creatives
- **Decisão:** RAW = dado bruto, sem filtro, sem transformação. Todo filtro vai para STG.

**3. STG views normalizadas**
- Typing (SAFE_CAST), limpeza de nulos, padronização de nomes de campo.
- `stg.mediasmart_delivery`, `stg.mediasmart_revenue`, `stg.mediasmart_bid_supply`, `stg.mgid_delivery`, `stg.siprocal_delivery`

**4. Migração de limpeza**
- `raw/migration/01_create_canonical_tables.sql` — cria estrutura canônica
- `raw/migration/02_drop_legacy_and_orphans.sql` — dropa tabelas órfãs (incluindo `raw.luckbet_io_plan_snapshot` ← causa da quebra futura de `gold.fact_io_plan`)

**Arquivos tocados:** ver commit `7ac505c` — 22 arquivos alterados/criados.

---

## 2026-05-21 — ETL Cora via Google Sheets → BigQuery

**Commits:** `b2c96e9`, `f26b69b` | **Autor:** Douglas Reche

### O que mudou e por quê

**Problema:** Cora precisava de dados de delivery históricos (ago/25–fev/26) que nunca foram formalizados em um IO no Admin UI. A pipeline padrão não capturava esses dados.

**Decisão:** workaround operacional — exportar dados de device, regiões e consolidado geral da plataforma MediaSmart para Google Sheets, e sincronizar para BQ via script Python com autenticação gcloud.

**Arquivos criados:**
- `scripts/etl/cora_sheets_sync.py` — sync principal (Cloud Run/GitHub Actions)
- `scripts/etl/cora_sheets_sync_local.py` — versão local com token gcloud
- `scripts/etl/apps_script_trigger.js` — trigger Google Workspace
- `.github/workflows/cora_sheets_sync.yml` — CI/CD GitHub Actions

**Limitação conhecida:** solução manual, não escalável. Depende de export manual para Sheets.

---

## 2026-05-20 — Gold MVP: workarounds Cora gap + Luckbet duplication

**Commits:** `c2c933a`, `7c4d182`, `3df2b43` | **Autor:** Douglas Reche

### O que mudou e por quê

**Problema #1 — Cora:** pipeline padrão mostrava apenas ~823K impressões para Cora porque o único IO (mar/26) cobria só março. Dados de ago/25–fev/26 existiam no raw mas nunca chegavam ao gold.

**Problema #2 — Luckbet:** entrega duplicada — mesmo delivery aparecia contado 2× por causa de dois `client_id` para o mesmo cliente (`nwd_luckbet_a485d6bc` canônico + `nwd_luckbet_69e72f18` legacy).

**Decisão:** criar views MVP específicas por cliente com lógica de atribuição explícita, como ponte até a pipeline canônica ficar pronta.

**Arquivos criados:**
- `gold/delivery/fct_cora_delivery_full.sql` — 3 paths de atribuição (MediaSmart via eventid, MGID/Siprocal registrados via io_binding_registry_v4, MGID/Siprocal não-registrados via hardcode)
- `gold/delivery/fct_luckbet_delivery_full.sql` — entrega Luckbet sem duplicação
- `gold/delivery/fct_delivery_daily_mvp.sql` — view unificada temporária

**Nota arquitetural:** `fct_cora_delivery_full.sql` ainda referencia `core.io_binding_registry_v4` (Admin UI do Shiro) — viola a separação de responsabilidades definida em 2026-05-26. Esta view é um workaround legado e **não deve ser expandida**.

---

## 2026-05-12/13 — Auditoria completa, ERD e sistema de IDs

**Commits:** `8d84e24` a `117987e` | **Autor:** Douglas Reche

### O que mudou e por quê

**Contexto:** Primeiro commit no repositório GitHub. Projeto já existia no BigQuery (desde ~2025) mas sem versionamento de código.

**O que foi documentado:**
- `docs/bigquery_analysis.md` (gerado 2026-04-30) — inventário dos 14 datasets, 97 tabelas, 116 views. Identificação dos dois pipelines paralelos em produção.
- `docs/known_issues.md` — problemas conhecidos: Luckbet duplicada, Cora sem histórico, Siprocal sem ID estruturado, etc.
- `docs/gold_mvp_apresentacao.md` — análise da gold layer MVP, star schema inicial.
- ERD completo: `docs/adframework_erd.dbml` (164 tabelas, 116 relacionamentos), `docs/adframework_erd_mermaid.md`
- `docs/id_quality_issues.md`, `docs/id_dependency_map.md` — análise de qualidade de IDs e dependências RAW→GOLD

**Descobertas críticas documentadas:**
- **Dois pipelines paralelos em produção:** Pipeline A (legado, `init_bq.py`, quebrado) + Pipeline B (V4, Admin UI Shiro, ativo)
- `marts.fact_delivery_daily_v2` nunca foi criado em prod — 14 funções Python definidas mas nunca chamadas no `main()`
- `share.*` inteiro quebrado como consequência

---

## 2026-05-04/05 — Reunião de viabilidade: decisão de construir nova pipeline

**Doc:** `docs/viability_assessment_terça.md` | **Presentes:** Douglas, Shiro, Alexandre

### Decisão tomada

Construir a nova pipeline ETL canônica (RAW→STG→CORE→GOLD) em paralelo ao sistema legado, sem quebrar o Admin UI do Shiro. A reestruturação do BQ é viável em ~3 semanas.

**Pré-requisitos definidos na reunião:**
1. Nova pipeline ETL escreve APENAS em `raw.*`, `stg.*`, `core.*`, `gold.*` (datasets do Douglas)
2. Admin UI do Shiro continua escrevendo em `core.io_manager_v2` e derivados — nunca referenciar no pipeline gold
3. `gold.fact_io_plan` será reconstruída usando dados do IO plan do Shiro como fonte
4. Manter `raw.*` como único ponto de verdade (dropar raw_mediasmart, raw_mgid, raw_siprocal)

**Achado arquitetural:** `marts.io_delivery_daily_v4` (view central do pipeline V4 do Shiro) depende de `share.newad_operational_daily` — inversão arquitetural que funciona em prod mas precisa ser respeitada na ordem de criação no staging.

---

## 2026-04-28/30 — Gold Layer MVP inicial + auditoria BQ

**Docs:** `docs/gold_mvp_apresentacao.md`, `docs/bigquery_analysis.md`, `docs/prod_audit_and_restructuring_plan.md`

### O que foi feito

**Contexto:** primeiro esforço de criar uma gold layer utilizável para Power BI. O BQ tinha ~50 views encadeadas sem materialização física tornando queries de BI impossíveis.

**Arquitetura gold MVP definida:**
- Star schema: `fact_delivery_daily` + `dim_client` + `dim_date` + `dim_platform` + `dim_io_line`
- Grain: `date × IO line × platform`
- Modo Power BI: Import (não DirectQuery — pacing acumulado com DAX inviabiliza DirectQuery)
- `gold.fact_io_plan` planejada para conter dados de planejamento (investimento previsto, impressões previstas, cliques previstos)

**Estado identificado do BQ (2026-04-30):** 14 datasets, ~2.576 MB total, raw_mediasmart/raw_mgid/raw_siprocal congelados desde 2026-04-21 (reestruturação iniciada e abandonada).

---

## ~2025-08 — Início da operação: dados MediaSmart entram no BQ

**Não versionado** — reconstruído a partir de datas de dados no BQ

- Primeiros dados de `raw.mediasmart_delivery`: 2025-08-01
- Pipeline operacional: MediaSmart → `raw.mediasmart_daily` → processamento manual
- MGID: dados desde 2025-09-30
- Siprocal: dados desde 2025-08-22
- Sistema de IDs nessa época: baseado no Admin UI do Shiro (`nwd_*` format)
