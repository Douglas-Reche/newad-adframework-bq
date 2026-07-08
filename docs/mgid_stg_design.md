# MGID STG Layer — Design e Plano de Implementação

---
> **⚠️ LEGADO — PRÉ-REBUILD 2026-06-16 ⚠️**
> Este documento descreve a pipeline **anterior ao reset completo de 2026-06-16**.
> Tabelas, views, schemas e colunas aqui descritos **foram dropados e não existem mais no BigQuery**.
> Mantenha para consulta histórica — **não use como referência para desenvolvimento novo.**
> Plano atual: [bq_restructuring_plan.md](bq_restructuring_plan.md) · [CHANGELOG.md](../CHANGELOG.md)
---

> Criado em: 2026-06-12 | Última atualização: 2026-06-14
> Status: **STG COMPLETA ✅** — Raw completo; STG T1–T4 + T8–T13b todos em produção (2026-06-14); fix firstlevel WRITE_TRUNCATE aplicado; próxima fase: gold layer unificado MGID+MediaSmart

---

## Contexto e motivação

O pipeline MGID existia de forma incompleta: apenas `raw.mgid_delivery` (day+campaignId) sem nenhum breakdown por dispositivo, geo, OS, browser, hora ou widget. A partir desta reestruturação criamos uma camada `raw` completa (8 tabelas novas) e uma STG estruturada seguindo os mesmos padrões da MediaSmart.

**Objetivo:** reproduzir na MGID o mesmo modelo dimensional da MediaSmart — dimensões canônicas, fact tables por grain específico — para que ambas as plataformas alimentem o mesmo gold layer com colunas alinhadas.

---

## Arquitetura da API MGID

- **Base URL:** `https://api.mgid.com/v1`
- **Auth:** Bearer token estático (não expira)
- **Credenciais:** Firestore `platform_credentials/mgid` → `secrets.token`, `secrets.client_id`
- **CLIENT_ID:** `824956`
- **Rate limit:** 128 req/min + 10 concurrent
- **Endpoints usados:**

| Endpoint | Uso |
|---|---|
| `/goodhits/clients/{id}/campaigns` | Catálogo de campanhas (firstlevel) |
| `/goodhits/clients/{id}/teasers` | Catálogo de criativos (firstlevel) |
| `/goodhits/clients/{id}/statistics-reports` | Stats por dimension (raw jobs A–G) |
| `/v1/dictionaries/geo` | Lookup de regiões (D-lookup, one-time) |

**Limitação crítica da API statistics-reports:**
- Máximo **3 dimensões** por request
- Máximo **90 dias** por request
- Paginação máxima 1.000 linhas/request

---

## Hierarquia de IDs na MGID

```
client_id (824956)  →  platform_client_links.platform_client_id
    └── raw.mgid_campaigns.id  (= campaignid na delivery = mgid_campaign_id)
             └── raw.mgid_creatives.id / raw.mgid_stats_creative.teaserid (= mgid_creative_id)
```

**Vínculo client → campaign:**
Não existe `event_id` (conceito exclusivo MediaSmart). O `client_id` é único por conta MGID e o link
com campanhas é feito via `platform_client_links` (table: `core`) usando `platform='mgid'` e `link_type='campaignid'`.

---

## Problema de duplicatas nas RAW de catálogo

Tabelas `firstlevel` usam `WRITE_APPEND`, gerando duplicatas acumuladas:

| Tabela | Linhas totais | IDs únicos | Fator dup | Fix |
|---|---|---|---|---|
| `raw.mgid_campaigns` | 19.789 | 248 | 79.8× | SELECT DISTINCT + mudar para WRITE_TRUNCATE |
| `raw.mgid_creatives` | ~10.660 | ~410 | ~26× | SELECT DISTINCT + mudar para WRITE_TRUNCATE |

**Fix aplicado 2026-06-14 ✅:** `write_mode` atualizado para `WRITE_TRUNCATE` nos docs Firestore `mgid_firstlevel_campaigns` e `mgid_firstlevel_creatives` via script Python (Firestore.update). Próximo run do cron vai truncar e recarregar (~178 campanhas às 03:20 UTC, ~408 criativos na terça 03:00 UTC).

> As tabelas de stats (A–G) usam `WRITE_APPEND` por design — dados históricos acumulam dia a dia. Dedup nas STGs via `ROW_NUMBER() OVER (PARTITION BY day, campaignid, [dim] ORDER BY raw_ingested_at DESC)`.

---

## Jobs de ingestão RAW — statistics-reports API

**Todos os jobs:** `platform_id=mgid`, `update_type=daily`, `schedule_cron=20 3 * * *`, `write_mode=WRITE_APPEND`
**Endpoint padrão:** `/goodhits/clients/{client_id}/statistics-reports` (configurado via `rules` no Firestore)
**Orchestrator:** `_run_mgid_daily()` em `adframework_python/src/orchestrator.py`

---

### Job A — `mgid_stats_daily` ✅ CRIADO E VALIDADO

```
firestore_doc:  mgid_stats_daily  (collection: platform_reports)
tabela BQ:      adframework.raw.mgid_stats_daily
dimensions:     day, campaignId
metrics:        impressions, clicks, ctr, spent, cpc, revenue, profit, roas,
                conversionsInterest, conversionsDecision, conversionsBuy
update_type:    daily
alimenta:       stg.mgid_delivery (T3) — delivery
                stg.mgid_revenue (T8) — financeiro

schema BQ (16 cols):
  day, campaignid,
  impressions, clicks, ctr,
  spent, cpc, revenue, profit, roas,
  conversionsinterest, conversionsdecision, conversionsbuy,
  platform, report_name, raw_ingested_at
```

**Validação 2026-06-14:**
- 7 linhas para 2026-06-13 (test 1 dia) ✅
- 2338 linhas backfill histórico (2025-10-01 → 2026-06-13) ✅
- Campos `platform='mgid'`, `report_name='mgid_stats_daily'`, `raw_ingested_at` populados ✅
- `spent`/`revenue`/`profit` retornam como dict Python: `{'amount': '190.2', 'currency': 'BRL'}`
- `roas` retorna como inteiro (0 para clientes sem pixel com valor configurado)
- `adrequests` devolvido pela API mas não está no schema → descartado automaticamente pelo BigQueryService

---

### Job B — `mgid_stats_creative` ✅ CRIADO E VALIDADO

```
firestore_doc:  mgid_stats_creative  (collection: platform_reports)
tabela BQ:      adframework.raw.mgid_stats_creative
dimensions:     day, campaignId, teaserId
metrics:        impressions, clicks, ctr, spent, cpc, revenue, profit, roas,
                conversionsInterest, conversionsDecision, conversionsBuy
update_type:    daily
alimenta:       stg.mgid_creative_delivery (T4)

schema BQ (17 cols):
  day, campaignid, teaserid,
  impressions, clicks, ctr,
  spent, cpc, revenue, profit, roas,
  conversionsinterest, conversionsdecision, conversionsbuy,
  platform, report_name, raw_ingested_at
```

**Validação 2026-06-14:**
- 13 linhas para 2026-06-13 ✅
- Grain confirmado: `day + campaignid + teaserid`

---

### Job C — `mgid_stats_by_device` ✅ CRIADO E VALIDADO

```
firestore_doc:  mgid_stats_by_device  (collection: platform_reports)
tabela BQ:      adframework.raw.mgid_stats_by_device
dimensions:     day, campaignId, deviceType
metrics:        impressions, clicks, spent, revenue, profit, roas,
                conversionsInterest, conversionsDecision, conversionsBuy
update_type:    daily
alimenta:       stg.mgid_delivery_by_device (T9)

schema BQ (15 cols):
  day, campaignid, devicetype,
  impressions, clicks,
  spent, revenue, profit, roas,
  conversionsinterest, conversionsdecision, conversionsbuy,
  platform, report_name, raw_ingested_at
```

**Validação 2026-06-14:**
- 12 linhas para 2026-06-13 ✅
- Valores de `devicetype` observados: `tablet`, `desktop`, `mobile`

---

### Job D — `mgid_stats_by_geo` ✅ CRIADO E VALIDADO

```
firestore_doc:  mgid_stats_by_geo  (collection: platform_reports)
tabela BQ:      adframework.raw.mgid_stats_by_geo
dimensions:     day, campaignId, region
metrics:        impressions, clicks, spent, revenue, profit, roas,
                conversionsInterest, conversionsDecision, conversionsBuy
update_type:    daily
alimenta:       stg.mgid_delivery_by_geo (T10)

schema BQ (15 cols):
  day, campaignid, region,
  impressions, clicks,
  spent, revenue, profit, roas,
  conversionsinterest, conversionsdecision, conversionsbuy,
  platform, report_name, raw_ingested_at
```

**Validação 2026-06-14:**
- 26 linhas para 2026-06-13 ✅
- ⚠️ **Atenção no design STG T10:** `region` retorna nome textual completo (ex: `"Campinas City"`, `"Brasília City"`, `"Belo Horizonte City"`) — NÃO retorna ID numérico como previsto inicialmente.
- Isso **simplifica** o T10: não precisa de JOIN com `raw.mgid_geo_regions` para obter o nome; pode precisar de JOIN apenas para obter `country_code`.
- Revisar design de `raw.mgid_geo_regions` (D-lookup) antes de criar T10.

---

### Job D-lookup — `mgid_geo_regions`

```
tabela BQ:      adframework.raw.mgid_geo_regions
endpoint:       /v1/dictionaries/geo
passo 1:        type=countries → lista todos os países
passo 2:        type=cities&countries[]=[todos] → regiões globais
update_type:    one-time (refresh manual quando necessário)
alimenta:       JOIN em stg.mgid_delivery_by_geo (T10) — para country_code

schema BQ (6 cols):
  region_id, region_name, region_name_latin,
  country_code, country_name, raw_ingested_at
```

> ⚠️ Tabela criada mas ainda não populada. Job D-lookup requer script Python pontual (não usa o orchestrator padrão). A revisar se necessário após validar T10 com dados reais.

---

### Job E1 — `mgid_stats_by_os` ✅ CRIADO E VALIDADO

```
firestore_doc:  mgid_stats_by_os  (collection: platform_reports)
tabela BQ:      adframework.raw.mgid_stats_by_os
dimensions:     day, campaignId, os
metrics:        impressions, clicks, spent, revenue, profit, roas,
                conversionsInterest, conversionsDecision, conversionsBuy
update_type:    daily
alimenta:       stg.mgid_delivery_by_os (T11)
nota:           browser é job separado (E2) — atributos independentes sem hierarquia

schema BQ (15 cols):
  day, campaignid, os,
  impressions, clicks,
  spent, revenue, profit, roas,
  conversionsinterest, conversionsdecision, conversionsbuy,
  platform, report_name, raw_ingested_at
```

**Validação 2026-06-14:**
- 130 linhas para 2026-06-13 ✅
- OS muito granular: `"Android mobile 14.xx"`, `"iOS mobile 15.xx"`, `"Android mobile 2.2 and lower"`, etc.
- Alta cardinalidade por campanha/dia — considerar normalização no STG T11

---

### Job E2 — `mgid_stats_by_browser` ✅ CRIADO E VALIDADO

```
firestore_doc:  mgid_stats_by_browser  (collection: platform_reports)
tabela BQ:      adframework.raw.mgid_stats_by_browser
dimensions:     day, campaignId, browser
metrics:        impressions, clicks, spent, revenue, profit, roas,
                conversionsInterest, conversionsDecision, conversionsBuy
update_type:    daily
alimenta:       stg.mgid_delivery_by_browser (T11b)
nota:           OS é job separado (E1) — atributos independentes sem hierarquia

schema BQ (15 cols):
  day, campaignid, browser,
  impressions, clicks,
  spent, revenue, profit, roas,
  conversionsinterest, conversionsdecision, conversionsbuy,
  platform, report_name, raw_ingested_at
```

**Validação 2026-06-14:**
- 57 linhas para 2026-06-13 ✅
- Browsers observados: `"Google Chrome"`, `"Firefox"`, `"Mobile Samsung Brows"`, `"Google Search App"`, `"Other"`

---

### Job F — `mgid_stats_by_hour` ✅ CRIADO E VALIDADO

```
firestore_doc:  mgid_stats_by_hour  (collection: platform_reports)
tabela BQ:      adframework.raw.mgid_stats_by_hour
dimensions:     day, campaignId, hour
metrics:        impressions, clicks, spent, revenue, profit, roas,
                conversionsInterest, conversionsDecision, conversionsBuy
update_type:    daily
alimenta:       stg.mgid_delivery_by_hour (T12)

schema BQ (15 cols):
  day, campaignid, hour,
  impressions, clicks,
  spent, revenue, profit, roas,
  conversionsinterest, conversionsdecision, conversionsbuy,
  platform, report_name, raw_ingested_at
```

**Validação 2026-06-14:**
- 82 linhas para 2026-06-13 ✅
- `hour` de 0 a 23 (string numérica)

---

### Job G — `mgid_stats_by_widget` ✅ CRIADO E VALIDADO

```
firestore_doc:  mgid_stats_by_widget  (collection: platform_reports)
tabela BQ:      adframework.raw.mgid_stats_by_widget
dimensions:     day, campaignId, widgetId
metrics:        impressions, clicks, spent, revenue, profit, roas
update_type:    daily
alimenta:       stg.mgid_delivery_by_widget (T13)
nota:           sem conversions — granularidade por widget tem baixo valor analítico

schema BQ (12 cols):
  day, campaignid, widgetid,
  impressions, clicks,
  spent, revenue, profit, roas,
  platform, report_name, raw_ingested_at
```

**Validação 2026-06-14:**
- 1.537 linhas para 2026-06-13 ✅
- Alta cardinalidade esperada: publishers/widgets únicos por campanha
- Sem `ctr` e sem conversions por design (too granular)

---

## Status das tabelas RAW

> Backfill finalizado em 2026-06-14. Todos os jobs de stats cobrem **2025-10-01 → 2026-06-13 (256 dias)**.

| Tabela | Tipo | Partição | Status | Linhas | Período |
|---|---|---|---|---|---|
| `raw.mgid_campaigns` | TABLE | — | ✅ Ativo (fix dedup pendente) | 740 | — |
| `raw.mgid_creatives` | TABLE | — | ✅ Ativo (fix dedup pendente) | 11.106 | — |
| `raw.mgid_delivery` | TABLE | — | ✅ Legado (histórico pré-out/2025) | 3.491 | — |
| `raw.mgid_daily` | TABLE | — | ✅ Ativo legado (sem `spent`) | 112 | — |
| `raw.mgid_stats_daily` | TABLE | DAY(raw_ingested_at) | ✅ BACKFILL COMPLETO | 4.560 | out/25→jun/26 |
| `raw.mgid_stats_creative` | TABLE | DAY(raw_ingested_at) | ✅ BACKFILL COMPLETO | 4.043 | out/25→jun/26 |
| `raw.mgid_stats_by_device` | TABLE | DAY(raw_ingested_at) | ✅ BACKFILL COMPLETO | 4.595 | out/25→jun/26 |
| `raw.mgid_stats_by_geo` | TABLE | DAY(raw_ingested_at) | ✅ BACKFILL COMPLETO | 31.679 | out/25→jun/26 |
| `raw.mgid_geo_regions` | TABLE | — | ⚠️ Vazia (one-time load pendente) | 0 | — |
| `raw.mgid_stats_by_os` | TABLE | DAY(raw_ingested_at) | ✅ BACKFILL COMPLETO | 58.010 | out/25→jun/26 |
| `raw.mgid_stats_by_browser` | TABLE | DAY(raw_ingested_at) | ✅ BACKFILL COMPLETO | 24.138 | out/25→jun/26 |
| `raw.mgid_stats_by_hour` | TABLE | DAY(raw_ingested_at) | ✅ BACKFILL COMPLETO | 22.596 | out/25→jun/26 |
| `raw.mgid_stats_by_widget` | TABLE | DAY(raw_ingested_at) | ✅ BACKFILL COMPLETO | 780.793 | out/25→jun/26 |

**Nota sobre duplicatas no raw:** O script de backfill rodou duas vezes (bjibkc0ej + PID 25108). As views STG deduplicam via `ROW_NUMBER() OVER (PARTITION BY day, campaignid, [dim] ORDER BY raw_ingested_at DESC) = 1` — sem impacto funcional. As tabelas firstlevel (`mgid_campaigns`, `mgid_creatives`) precisam do fix de `write_mode → WRITE_TRUNCATE`.

---

## Tabelas STG — planejadas

### T1 — `stg.mgid_campaigns` ✅ EM PRODUÇÃO

**Fonte:** `raw.mgid_campaigns` (deduplicado com ROW_NUMBER)
**Grain:** 1 linha por campanha (`mgid_campaign_id` único)
**Arquivo:** `stg/ddl/mgid_campaigns.sql`
**Executada em:** 2026-06-12

| Campo | Tipo | Fonte | Notas |
|---|---|---|---|
| `mgid_campaign_id` | STRING | `raw.id` | PK |
| `mgid_client_id` | STRING | `platform_client_links` | `platform='mgid'`, `link_type='campaignid'` |
| `mgid_campaign_name` | STRING | `raw.name` | |
| `campaign_type` | STRING | `raw.campaignType` | product / push / rich_media |
| `language_id` | STRING | `raw.language` | ID numérico (8=Portuguese) |
| `state` | STRING | `raw.status → $.name` | ended / active / paused |
| `state_reason` | STRING | `raw.status → $.reason` | managerPaused / expired / etc |
| `category_id` | INT64 | `raw.category → $.id` | |
| `category_name` | STRING | `raw.category → $.name` | |
| `started_at` | DATE | `raw.startDate` | |
| `finished_at` | DATE | `raw.endDate` | |
| `max_daily_cost` | FLOAT64 | `raw.limitsFilter → $.dailyLimit` | |
| `max_total_cost` | FLOAT64 | `raw.limitsFilter → $.overallLimit` | |
| `limit_type` | STRING | `raw.limitsFilter → $.limitType` | |
| `utm_source` | STRING | `raw.trackingOptions → $.utm_source` | |
| `utm_medium` | STRING | `raw.trackingOptions → $.utm_medium` | |
| `utm_campaign` | STRING | `raw.trackingOptions → $.utm_campaign` | |
| `created_at` | DATE | `raw.whenAdd` | sem `updated_at` na API |

**Decisões:** sem `event_id` (conceito exclusivo MS); `client_id` via `platform_client_links` direto; dedup via ROW_NUMBER por `whenAdd DESC`

---

### T2 — `stg.mgid_creatives` ✅ EM PRODUÇÃO (2026-06-14)

**Fonte:** `raw.mgid_creatives` (deduplicado com ROW_NUMBER — sem raw_ingested_at nesta tabela, usando ORDER BY (SELECT NULL))
**Resultado:** 408 creatives únicos (de 11.106 raw rows), 323 com mgid_client_id resolvido, 85 criativos órfãos (LEFT JOIN sem match em stg.mgid_campaigns).
**Grain:** 1 linha por criativo (`mgid_creative_id` único)
**Arquivo:** `stg/ddl/mgid_creatives.sql`
**Depende de:** T1 (`stg.mgid_campaigns`)

| Campo | Tipo | Fonte | Notas |
|---|---|---|---|
| `mgid_creative_id` | STRING | `raw.id` | PK |
| `mgid_campaign_id` | STRING | `raw.campaignId` | FK para T1 |
| `mgid_client_id` | STRING | via `stg.mgid_campaigns` | herdado do T1 |
| `creative_name` | STRING | `raw.title` | |
| `advert_text` | STRING | `raw.advertText` | |
| `landing_url` | STRING | `raw.url` | |
| `image_url` | STRING | `raw.imageLink` | |
| `creative_type` | STRING | `raw.ad_type` | `pg`=native / `r`=rich_media |
| `call_to_action` | STRING | `raw.callToAction` | |
| `state` | STRING | `raw.status → $.code` | active / blocked / campaignBlocked / rejected |
| `category_id` | INT64 | `raw.category → $.id` | |
| `category_name` | STRING | `raw.category → $.name` | |
| `category_iab_code` | STRING | `raw.category → $.iab_code` | ex: IAB21 — não disponível em T1 |
| `currency_id` | INT64 | `raw.currency` | ID numérico (não código ISO) |

---

### T3 — `stg.mgid_delivery` ✅ EM PRODUÇÃO (2026-06-14)

**Fonte:** `raw.mgid_stats_daily` (fonte única — Opção A, sem UNION)
**Grain:** `day + mgid_campaign_id`
**Arquivo:** `stg/ddl/mgid_delivery.sql`
**Depende de:** `core.platform_client_links`
**Job BQ:** `0781ab94-78e5-4f61-a458-02a47f770c39` — DONE

**Resultado validado:**
- 2.338 linhas únicas (raw tinha 4.560 com backfill duplo → dedup correto)
- 98 campanhas distintas
- 18 clientes resolvidos via `platform_client_links`
- Período: 2025-10-01 → 2026-06-13
- `conversions_*`: todos 0 — clientes sem pixel de conversão configurado (esperado)

**Decisões tomadas:**
- Fonte única `stats_daily` — `mgid_delivery` legado tem 237/238 dias sobrepostos; único dia exclusivo é 2025-09-30, não justifica UNION
- `ctr` excluído do STG — calculado no gold (`clicks/impressions`); MS não expõe no STG
- `spent/revenue/profit/roas` excluídos — separação delivery × revenue, vão para T8
- Nomes de conversão preservados como vêm da API MGID (`interest/decision/buy`) — NÃO mapear para `conversions_1/2/3` pois o significado semântico é diferente do MS (mapeamento por cliente acontece no gold)
- Dedup via `ROW_NUMBER() OVER (PARTITION BY day, campaignid ORDER BY raw_ingested_at DESC) = 1`

| Campo | Tipo | Fonte RAW | Notas |
|---|---|---|---|
| `day` | DATE | `raw.day` | `SAFE_CAST(day AS DATE)` |
| `mgid_client_id` | STRING | `platform_client_links.client_id` | `LEFT JOIN platform='mgid' AND link_type='campaignid' AND link_value=campaignid` |
| `mgid_campaign_id` | STRING | `raw.campaignid` | |
| `impressions` | INT64 | `raw.impressions` | `SAFE_CAST(impressions AS INT64)` |
| `clicks` | INT64 | `raw.clicks` | `SAFE_CAST(clicks AS INT64)` |
| `conversions_interest` | INT64 | `raw.conversionsinterest` | `SAFE_CAST` — topo de funil |
| `conversions_decision` | INT64 | `raw.conversionsdecision` | `SAFE_CAST` — meio de funil |
| `conversions_buy` | INT64 | `raw.conversionsbuy` | `SAFE_CAST` — fundo de funil |
| `source_table` | STRING | literal | `'stats_daily'` — rastreabilidade |

**DDL executado (`stg/ddl/mgid_delivery.sql`):**
```sql
CREATE OR REPLACE VIEW `adframework.stg.mgid_delivery` AS

WITH stats_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY day, campaignid ORDER BY raw_ingested_at DESC) AS rn
  FROM `adframework.raw.mgid_stats_daily`
  WHERE day IS NOT NULL
    AND campaignid IS NOT NULL
)

SELECT
  SAFE_CAST(s.day AS DATE)                       AS day,
  pcl.client_id                                  AS mgid_client_id,
  s.campaignid                                   AS mgid_campaign_id,
  SAFE_CAST(s.impressions          AS INT64)     AS impressions,
  SAFE_CAST(s.clicks               AS INT64)     AS clicks,
  SAFE_CAST(s.conversionsinterest  AS INT64)     AS conversions_interest,
  SAFE_CAST(s.conversionsdecision  AS INT64)     AS conversions_decision,
  SAFE_CAST(s.conversionsbuy       AS INT64)     AS conversions_buy,
  'stats_daily'                                  AS source_table
FROM stats_deduped s
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = s.campaignid
WHERE s.rn = 1;
```

---

### T4 — `stg.mgid_creative_delivery` ✅ EM PRODUÇÃO (2026-06-14)

**Fonte:** `raw.mgid_stats_creative` (Job B — fonte única, sem UNION)
**Grain:** `day + mgid_campaign_id + mgid_creative_id`
**Arquivo:** `stg/ddl/mgid_creative_delivery.sql`
**Depende de:** `core.platform_client_links`
**Job BQ:** `8e4e82f2-ec75-4b81-9235-463bd26db633` — DONE

**Resultado validado:**
- 4.030 linhas únicas (raw tinha 4.043 → dedup correto, 13 duplicatas removidas)
- 98 campanhas, 202 criativos, 18 clientes
- Período: 2025-10-01 → 2026-06-13
- Totais consistentes com T3: 62.872.277 impressions, 343.503 clicks ✅

**Decisões tomadas:**
- Fonte única `stats_creative` (mesmo padrão do T3 com `stats_daily`)
- `ctr/spent/cpc/revenue/profit/roas` excluídos — vão para T8 (revenue separado do delivery)
- Nomes de conversão preservados como vêm da API MGID (`interest/decision/buy`)
- Dedup: `ROW_NUMBER() OVER (PARTITION BY day, campaignid, teaserid ORDER BY raw_ingested_at DESC)`
- `teaserid` da API = `mgid_creative_id` no STG

| Campo | Tipo | Fonte RAW | Notas |
|---|---|---|---|
| `day` | DATE | `raw.day` | `SAFE_CAST(day AS DATE)` |
| `mgid_client_id` | STRING | `platform_client_links.client_id` | `LEFT JOIN platform='mgid' AND link_type='campaignid'` |
| `mgid_campaign_id` | STRING | `raw.campaignid` | |
| `mgid_creative_id` | STRING | `raw.teaserid` | nome API MGID para criativo |
| `impressions` | INT64 | `raw.impressions` | `SAFE_CAST` |
| `clicks` | INT64 | `raw.clicks` | `SAFE_CAST` |
| `conversions_interest` | INT64 | `raw.conversionsinterest` | `SAFE_CAST` — topo de funil |
| `conversions_decision` | INT64 | `raw.conversionsdecision` | `SAFE_CAST` — meio de funil |
| `conversions_buy` | INT64 | `raw.conversionsbuy` | `SAFE_CAST` — fundo de funil |
| `source_table` | STRING | literal | `'stats_creative'` — rastreabilidade |

**DDL executado (`stg/ddl/mgid_creative_delivery.sql`):**
```sql
CREATE OR REPLACE VIEW `adframework.stg.mgid_creative_delivery` AS

WITH stats_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY day, campaignid, teaserid ORDER BY raw_ingested_at DESC) AS rn
  FROM `adframework.raw.mgid_stats_creative`
  WHERE day IS NOT NULL
    AND campaignid IS NOT NULL
    AND teaserid IS NOT NULL
)

SELECT
  SAFE_CAST(s.day AS DATE)                       AS day,
  pcl.client_id                                  AS mgid_client_id,
  s.campaignid                                   AS mgid_campaign_id,
  s.teaserid                                     AS mgid_creative_id,
  SAFE_CAST(s.impressions          AS INT64)     AS impressions,
  SAFE_CAST(s.clicks               AS INT64)     AS clicks,
  SAFE_CAST(s.conversionsinterest  AS INT64)     AS conversions_interest,
  SAFE_CAST(s.conversionsdecision  AS INT64)     AS conversions_decision,
  SAFE_CAST(s.conversionsbuy       AS INT64)     AS conversions_buy,
  'stats_creative'                               AS source_table
FROM stats_deduped s
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = s.campaignid
WHERE s.rn = 1;
```

---

### T8 — `stg.mgid_revenue` ✅ EM PRODUÇÃO (2026-06-14)

**Fonte:** `raw.mgid_stats_daily` (Job A) — mesmo grain do T3, campos financeiros separados
**Grain:** `day + mgid_campaign_id`
**Arquivo:** `stg/ddl/mgid_revenue.sql`
**Depende de:** `core.platform_client_links`
**Job BQ:** `c3c7708c-e3e0-4669-aafd-4c81505df78c` — DONE

**Resultado validado:**
- 2.338 linhas (grain idêntico ao T3 ✅)
- 98 campanhas, 18 clientes, 2025-10-01 → 2026-06-13
- Total spent: R$ 157.271,98 | revenue: R$ 0 | profit: R$ -157.271,98
- currency: BRL (único valor) — 0 nulos em spent e cpc ✅

**Decisões tomadas:**
- `profit` incluído — API retorna diretamente, evita recalcular no gold
- `cpc` incluído — métrica de performance útil
- `roas` incluído — hoje 0, mas estará pronto quando pixel for configurado
- `currency` incluído — hoje sempre BRL, mas útil para future-proofing
- Parser dict: `REPLACE("'", '"') + REPLACE('None', 'null')` → `JSON_VALUE($.amount)`
- `roas` não é dict — `SAFE_CAST(roas AS FLOAT64)` direto

| Campo | Tipo | Fonte RAW | Notas |
|---|---|---|---|
| `day` | DATE | `raw.day` | `SAFE_CAST(day AS DATE)` |
| `mgid_client_id` | STRING | `platform_client_links.client_id` | `LEFT JOIN platform='mgid' AND link_type='campaignid'` |
| `mgid_campaign_id` | STRING | `raw.campaignid` | |
| `spent` | FLOAT64 | `raw.spent → $.amount` | dict Python → parser REPLACE+JSON_VALUE |
| `cpc` | FLOAT64 | `raw.cpc → $.amount` | dict Python → parser REPLACE+JSON_VALUE |
| `revenue` | FLOAT64 | `raw.revenue → $.amount` | 0 para clientes sem pixel com valor |
| `profit` | FLOAT64 | `raw.profit → $.amount` | = `revenue - spent` (retornado pela API) |
| `roas` | FLOAT64 | `raw.roas` | inteiro direto, não dict — `SAFE_CAST(roas AS FLOAT64)` |
| `currency` | STRING | `raw.spent → $.currency` | sempre `'BRL'` atualmente |
| `source_table` | STRING | literal | `'stats_daily'` |

**DDL executado (`stg/ddl/mgid_revenue.sql`):**
```sql
CREATE OR REPLACE VIEW `adframework.stg.mgid_revenue` AS

WITH stats_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY day, campaignid ORDER BY raw_ingested_at DESC) AS rn
  FROM `adframework.raw.mgid_stats_daily`
  WHERE day IS NOT NULL AND campaignid IS NOT NULL
),
parsed AS (
  SELECT
    day, campaignid,
    REPLACE(REPLACE(spent,   "'", '"'), 'None', 'null') AS spent_json,
    REPLACE(REPLACE(cpc,     "'", '"'), 'None', 'null') AS cpc_json,
    REPLACE(REPLACE(revenue, "'", '"'), 'None', 'null') AS revenue_json,
    REPLACE(REPLACE(profit,  "'", '"'), 'None', 'null') AS profit_json,
    roas, rn
  FROM stats_deduped
)
SELECT
  SAFE_CAST(p.day AS DATE)                                          AS day,
  pcl.client_id                                                     AS mgid_client_id,
  p.campaignid                                                      AS mgid_campaign_id,
  SAFE_CAST(JSON_VALUE(p.spent_json,   '$.amount') AS FLOAT64)     AS spent,
  SAFE_CAST(JSON_VALUE(p.cpc_json,     '$.amount') AS FLOAT64)     AS cpc,
  SAFE_CAST(JSON_VALUE(p.revenue_json, '$.amount') AS FLOAT64)     AS revenue,
  SAFE_CAST(JSON_VALUE(p.profit_json,  '$.amount') AS FLOAT64)     AS profit,
  SAFE_CAST(p.roas AS FLOAT64)                                      AS roas,
  JSON_VALUE(p.spent_json, '$.currency')                            AS currency,
  'stats_daily'                                                     AS source_table
FROM parsed p
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON pcl.platform = 'mgid' AND pcl.link_type = 'campaignid' AND pcl.link_value = p.campaignid
WHERE p.rn = 1;
```

---

### T9 — `stg.mgid_delivery_by_device` ✅ EM PRODUÇÃO (2026-06-14)

**Fonte:** `raw.mgid_stats_by_device` (Job C)
**Grain:** `day + mgid_campaign_id + device_type`
**Arquivo:** `stg/ddl/mgid_delivery_by_device.sql`
**Job BQ:** `8550163e-a5e7-4d33-b6d7-56fc032073ee` — DONE

**Resultado validado:**
- 4.583 linhas (raw tinha 4.595 → dedup correto)
- 98 campanhas, 4 device types: `mobile`, `desktop`, `tablet`, `smarttv`
- Período: 2025-10-01 → 2026-06-13
- Impressions: 62.872.277 ✅ (igual T3/T4)
- Total spent: R$ 157.271,98 ✅ (igual T8)
- Distribuição: mobile 84% spent, desktop 16%, tablet/smarttv < 1%

**Decisões tomadas:**
- Financeiro incluído neste grain (spent, revenue, profit, roas) — necessário para análise de gasto por device; não derivável do T8
- Sem `app_vs_web`, `conversion_source`, `strategy_id` (exclusivos MS)
- Sem video quartis (API MGID não retorna por device)
- Nomes de conversão preservados como API MGID (interest/decision/buy)
- Sem `cpc` — não disponível na fonte `stats_by_device`

| Campo | Tipo | Fonte RAW | Notas |
|---|---|---|---|
| `day` | DATE | `raw.day` | SAFE_CAST |
| `mgid_client_id` | STRING | `platform_client_links` | LEFT JOIN |
| `mgid_campaign_id` | STRING | `raw.campaignid` | |
| `device_type` | STRING | `raw.devicetype` | mobile/desktop/tablet/smarttv |
| `impressions` | INT64 | `raw.impressions` | SAFE_CAST |
| `clicks` | INT64 | `raw.clicks` | SAFE_CAST |
| `conversions_interest` | INT64 | `raw.conversionsinterest` | SAFE_CAST |
| `conversions_decision` | INT64 | `raw.conversionsdecision` | SAFE_CAST |
| `conversions_buy` | INT64 | `raw.conversionsbuy` | SAFE_CAST |
| `spent` | FLOAT64 | `raw.spent → $.amount` | dict parser |
| `revenue` | FLOAT64 | `raw.revenue → $.amount` | dict parser |
| `profit` | FLOAT64 | `raw.profit → $.amount` | dict parser |
| `roas` | FLOAT64 | `raw.roas` | SAFE_CAST direto |
| `source_table` | STRING | literal | `'stats_by_device'` |

---

### T10 — `stg.mgid_delivery_by_geo` ✅ EM PRODUÇÃO (2026-06-14)

**Fonte:** `raw.mgid_stats_by_geo` (Job D)
**Grain:** `day + mgid_campaign_id + region`
**Arquivo:** `stg/ddl/mgid_delivery_by_geo.sql`
**Job BQ:** `f123555e-7b22-4837-af64-e25142fecf52` — DONE

**Resultado validado:**
- 31.653 linhas (raw tinha 31.679 → dedup correto)
- 98 campanhas, 73 regiões, 2025-10-01 → 2026-06-13
- Impressions: 62.872.277 ✅ | Spent: R$ 157.271,98 ✅
- Top spend: São Paulo City (R$28k), Mato Grosso (R$25k), SP Region Other (R$14k)

**Decisões tomadas:**
- `region` mantido como texto bruto da API (ex: `"Belo Horizonte City"`, `"Bahia"`)
- `geo_level` derivado via CASE no sufixo: `city` / `state` / `region_aggregate` / `other`
- Sem `country_code` — `raw.mgid_geo_regions` nunca carregada (0 linhas); JOIN por nome de texto é frágil. Pendente próxima fase.
- Financeiro incluído (spent, revenue, profit, roas) — necessário para análise gasto por região
- Sem `cpc` — não disponível na fonte `stats_by_geo`

| Campo | Tipo | Fonte RAW | Notas |
|---|---|---|---|
| `day` | DATE | `raw.day` | SAFE_CAST |
| `mgid_client_id` | STRING | `platform_client_links` | LEFT JOIN |
| `mgid_campaign_id` | STRING | `raw.campaignid` | |
| `region` | STRING | `raw.region` | nome bruto da API |
| `geo_level` | STRING | derivado | `city`/`state`/`region_aggregate`/`other` via CASE |
| `impressions` | INT64 | `raw.impressions` | SAFE_CAST |
| `clicks` | INT64 | `raw.clicks` | SAFE_CAST |
| `conversions_interest` | INT64 | `raw.conversionsinterest` | SAFE_CAST |
| `conversions_decision` | INT64 | `raw.conversionsdecision` | SAFE_CAST |
| `conversions_buy` | INT64 | `raw.conversionsbuy` | SAFE_CAST |
| `spent` | FLOAT64 | `raw.spent → $.amount` | dict parser |
| `revenue` | FLOAT64 | `raw.revenue → $.amount` | dict parser |
| `profit` | FLOAT64 | `raw.profit → $.amount` | dict parser |
| `roas` | FLOAT64 | `raw.roas` | SAFE_CAST direto |
| `source_table` | STRING | literal | `'stats_by_geo'` |

---

### T11 — `stg.mgid_delivery_by_os` ✅ EM PRODUÇÃO (2026-06-14)

**Fonte:** `raw.mgid_stats_by_os` (Job E1)
**Grain:** `day + mgid_campaign_id + os`
**Arquivo:** `stg/ddl/mgid_delivery_by_os.sql`
**Job BQ:** `ff82802b-a070-4515-afb7-1bf4892213ea` — DONE

**Resultado validado:**
- 57.880 linhas (raw tinha 58.010 → dedup correto)
- 98 campanhas, 92 OS brutos → 7 famílias normalizadas
- Impressions: 62.872.277 ✅ | Spent: R$ 157.271,98 ✅
- Android domina: 70% impressions, 80% spend

**Decisões tomadas:**
- `os` mantido (valor bruto: `"Android mobile 14.02"`)
- `operating_system` adicionado — alinhado com `stg.ms_delivery_by_os` (MS usa mesmo nome)
  - Valores MS: `android` (lowercase) | MGID: `Android` (capitalizado) → normalizar no gold com LOWER()
- 7 famílias: Android, iOS, macOS, Windows, Tizen, Fire OS, Other
- Financeiro incluído (mesmo padrão T9/T10)

| Campo | Tipo | Fonte RAW | Notas |
|---|---|---|---|
| `day` | DATE | `raw.day` | SAFE_CAST |
| `mgid_client_id` | STRING | `platform_client_links` | LEFT JOIN |
| `mgid_campaign_id` | STRING | `raw.campaignid` | |
| `os` | STRING | `raw.os` | valor bruto da API |
| `operating_system` | STRING | derivado | família normalizada — alinhado com MS |
| `impressions` | INT64 | `raw.impressions` | SAFE_CAST |
| `clicks` | INT64 | `raw.clicks` | SAFE_CAST |
| `conversions_interest` | INT64 | `raw.conversionsinterest` | SAFE_CAST |
| `conversions_decision` | INT64 | `raw.conversionsdecision` | SAFE_CAST |
| `conversions_buy` | INT64 | `raw.conversionsbuy` | SAFE_CAST |
| `spent` | FLOAT64 | `raw.spent → $.amount` | dict parser |
| `revenue` | FLOAT64 | `raw.revenue → $.amount` | dict parser |
| `profit` | FLOAT64 | `raw.profit → $.amount` | dict parser |
| `roas` | FLOAT64 | `raw.roas` | SAFE_CAST direto |
| `source_table` | STRING | literal | `'stats_by_os'` |

---

### T11b — `stg.mgid_delivery_by_browser` ✅ EM PRODUÇÃO (2026-06-14)

**Fonte:** `raw.mgid_stats_by_browser` (Job E2)
**Grain:** `day + mgid_campaign_id + browser`
**Arquivo:** `stg/ddl/mgid_delivery_by_browser.sql`
**Job BQ:** executado com sucesso — DONE

**Resultado validado:**
- 24.081 linhas (raw tinha 24.138 → dedup correto)
- 98 campanhas, 18 browsers distintos, 2025-10-01 → 2026-06-13
- Impressions: 62.872.277 ✅ | Spent: R$ 157.271,98 ✅
- Distribuição: Chrome 55% spend, Samsung Browser ~15%, Edge/Safari ~10% cada

**Decisões tomadas:**
- Sem equivalente na MediaSmart — **não entra no gold unificado (Cenário B)**
- Power BI/dashboard consulta esta view STG diretamente para análise browser-específica
- Sem normalização necessária — nomes da API já são legíveis ("Google Chrome", "Microsoft Edge", "Safari", "Samsung Browser", etc.)
- Financeiro incluído (mesmo padrão T9-T11)
- Conversões incluídas (disponíveis neste grain)

| Campo | Tipo | Fonte RAW | Notas |
|---|---|---|---|
| `day` | DATE | `raw.day` | SAFE_CAST |
| `mgid_client_id` | STRING | `platform_client_links` | LEFT JOIN |
| `mgid_campaign_id` | STRING | `raw.campaignid` | |
| `browser` | STRING | `raw.browser` | nome legível da API — sem normalização |
| `impressions` | INT64 | `raw.impressions` | SAFE_CAST |
| `clicks` | INT64 | `raw.clicks` | SAFE_CAST |
| `conversions_interest` | INT64 | `raw.conversionsinterest` | SAFE_CAST |
| `conversions_decision` | INT64 | `raw.conversionsdecision` | SAFE_CAST |
| `conversions_buy` | INT64 | `raw.conversionsbuy` | SAFE_CAST |
| `spent` | FLOAT64 | `raw.spent → $.amount` | dict parser |
| `revenue` | FLOAT64 | `raw.revenue → $.amount` | dict parser |
| `profit` | FLOAT64 | `raw.profit → $.amount` | dict parser |
| `roas` | FLOAT64 | `raw.roas` | SAFE_CAST direto |
| `source_table` | STRING | literal | `'stats_by_browser'` |

**DDL executado (`stg/ddl/mgid_delivery_by_browser.sql`):**
```sql
CREATE OR REPLACE VIEW `adframework.stg.mgid_delivery_by_browser` AS

WITH stats_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY day, campaignid, browser ORDER BY raw_ingested_at DESC) AS rn
  FROM `adframework.raw.mgid_stats_by_browser`
  WHERE day IS NOT NULL
    AND campaignid IS NOT NULL
    AND browser IS NOT NULL
),

parsed AS (
  SELECT
    day, campaignid, browser, impressions, clicks,
    conversionsinterest, conversionsdecision, conversionsbuy,
    REPLACE(REPLACE(spent,   "'", '"'), 'None', 'null') AS spent_json,
    REPLACE(REPLACE(revenue, "'", '"'), 'None', 'null') AS revenue_json,
    REPLACE(REPLACE(profit,  "'", '"'), 'None', 'null') AS profit_json,
    roas, rn
  FROM stats_deduped
)

SELECT
  SAFE_CAST(p.day AS DATE)                                          AS day,
  pcl.client_id                                                     AS mgid_client_id,
  p.campaignid                                                      AS mgid_campaign_id,
  p.browser,
  SAFE_CAST(p.impressions         AS INT64)                        AS impressions,
  SAFE_CAST(p.clicks              AS INT64)                        AS clicks,
  SAFE_CAST(p.conversionsinterest AS INT64)                        AS conversions_interest,
  SAFE_CAST(p.conversionsdecision AS INT64)                        AS conversions_decision,
  SAFE_CAST(p.conversionsbuy      AS INT64)                        AS conversions_buy,
  SAFE_CAST(JSON_VALUE(p.spent_json,   '$.amount') AS FLOAT64)    AS spent,
  SAFE_CAST(JSON_VALUE(p.revenue_json, '$.amount') AS FLOAT64)    AS revenue,
  SAFE_CAST(JSON_VALUE(p.profit_json,  '$.amount') AS FLOAT64)    AS profit,
  SAFE_CAST(p.roas AS FLOAT64)                                     AS roas,
  'stats_by_browser'                                               AS source_table
FROM parsed p
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = p.campaignid
WHERE p.rn = 1;
```

---

### T12 — `stg.mgid_delivery_by_hour` ✅ EM PRODUÇÃO (2026-06-14)

**Fonte:** `raw.mgid_stats_by_hour` (Job F)
**Grain:** `day + mgid_campaign_id + hour`
**Arquivo:** `stg/ddl/mgid_delivery_by_hour.sql`
**Depende de:** `core.platform_client_links`
**Job BQ:** executado com sucesso — DONE

**Resultado validado:**
- 22.514 linhas (raw tinha 22.596 → dedup correto)
- 98 campanhas, 24 horas (0–23), 2025-10-01 → 2026-06-13
- Impressions: 62.872.277 ✅ | Spent: R$ 157.271,98 ✅
- Anomalia observada: horas 04–05 UTC têm ~53M impressions mas apenas R$2.3k spent — possível tráfego de baixíssimo custo nessa janela (bots ou inventário barato noturno)

**Decisões tomadas:**
- `hour` convertido de STRING para INT64 — alinhado com `stg.ms_delivery_by_hour` (MS usa mesmo tipo)
- Horário UTC (sem timezone local) — atenção ao interpretar horário no dashboard
- Financeiro incluído (mesmo padrão T9-T11b)
- Conversões incluídas (disponíveis neste grain)
- Sem `strategy_id`, `conversion_source`, vídeo quartis (exclusivos MS)

| Campo | Tipo | Fonte RAW | Notas |
|---|---|---|---|
| `day` | DATE | `raw.day` | SAFE_CAST |
| `mgid_client_id` | STRING | `platform_client_links` | LEFT JOIN |
| `mgid_campaign_id` | STRING | `raw.campaignid` | |
| `hour` | INT64 | `raw.hour` | STRING '0'–'23' → SAFE_CAST INT64; alinhado com MS |
| `impressions` | INT64 | `raw.impressions` | SAFE_CAST |
| `clicks` | INT64 | `raw.clicks` | SAFE_CAST |
| `conversions_interest` | INT64 | `raw.conversionsinterest` | SAFE_CAST |
| `conversions_decision` | INT64 | `raw.conversionsdecision` | SAFE_CAST |
| `conversions_buy` | INT64 | `raw.conversionsbuy` | SAFE_CAST |
| `spent` | FLOAT64 | `raw.spent → $.amount` | dict parser |
| `revenue` | FLOAT64 | `raw.revenue → $.amount` | dict parser |
| `profit` | FLOAT64 | `raw.profit → $.amount` | dict parser |
| `roas` | FLOAT64 | `raw.roas` | SAFE_CAST direto |
| `source_table` | STRING | literal | `'stats_by_hour'` |

**DDL executado (`stg/ddl/mgid_delivery_by_hour.sql`):**
```sql
CREATE OR REPLACE VIEW `adframework.stg.mgid_delivery_by_hour` AS

WITH stats_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY day, campaignid, hour ORDER BY raw_ingested_at DESC) AS rn
  FROM `adframework.raw.mgid_stats_by_hour`
  WHERE day IS NOT NULL
    AND campaignid IS NOT NULL
    AND hour IS NOT NULL
),

parsed AS (
  SELECT
    day, campaignid, hour, impressions, clicks,
    conversionsinterest, conversionsdecision, conversionsbuy,
    REPLACE(REPLACE(spent,   "'", '"'), 'None', 'null') AS spent_json,
    REPLACE(REPLACE(revenue, "'", '"'), 'None', 'null') AS revenue_json,
    REPLACE(REPLACE(profit,  "'", '"'), 'None', 'null') AS profit_json,
    roas, rn
  FROM stats_deduped
)

SELECT
  SAFE_CAST(p.day AS DATE)                                          AS day,
  pcl.client_id                                                     AS mgid_client_id,
  p.campaignid                                                      AS mgid_campaign_id,
  SAFE_CAST(p.hour AS INT64)                                       AS hour,
  SAFE_CAST(p.impressions         AS INT64)                        AS impressions,
  SAFE_CAST(p.clicks              AS INT64)                        AS clicks,
  SAFE_CAST(p.conversionsinterest AS INT64)                        AS conversions_interest,
  SAFE_CAST(p.conversionsdecision AS INT64)                        AS conversions_decision,
  SAFE_CAST(p.conversionsbuy      AS INT64)                        AS conversions_buy,
  SAFE_CAST(JSON_VALUE(p.spent_json,   '$.amount') AS FLOAT64)    AS spent,
  SAFE_CAST(JSON_VALUE(p.revenue_json, '$.amount') AS FLOAT64)    AS revenue,
  SAFE_CAST(JSON_VALUE(p.profit_json,  '$.amount') AS FLOAT64)    AS profit,
  SAFE_CAST(p.roas AS FLOAT64)                                     AS roas,
  'stats_by_hour'                                                  AS source_table
FROM parsed p
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = p.campaignid
WHERE p.rn = 1;
```

---

### T13 — `stg.mgid_delivery_by_widget` ✅ EM PRODUÇÃO (2026-06-14)

**Fonte:** `raw.mgid_stats_by_widget` (Job G)
**Grain:** `day + mgid_campaign_id + widget_id`
**Arquivo:** `stg/ddl/mgid_delivery_by_widget.sql`
**Depende de:** `core.platform_client_links`
**Job BQ:** `5b9594f0-fb87-4100-8f97-b5f400ec9620` — DONE

**Resultado validado:**
- 779.256 linhas (raw tinha 780.793 → dedup correto)
- 4.766 widgets únicos, 98 campanhas, 18 clientes
- Período: 2025-10-01 → 2026-06-13
- Impressions: 62.872.277 ✅ | Spent: R$ 157.271,98 ✅
- Top widget: `57713047` (10.5M impressions, R$16k spent)
- Alta cardinalidade: ~3k linhas/dia — maior tabela STG

**Decisões tomadas:**
- `widget_id` nomeado como MGID (`widgetid` na API) — **NÃO** `publisher_id` (evita falsa equivalência com MS)
  - MS identifica publisher por `company + url + exchange` (texto); MGID por ID numérico — JOIN impossível no gold
- Sem conversões — não disponível neste grain na API MGID (mesmo comportamento da `stg.ms_delivery_by_publisher`)
- Financeiro incluído (mesmo padrão T9-T12)
- Sem `cpc` (não disponível na fonte `stats_by_widget`)
- Dedup por `(day, campaignid, widgetid)` — grain único confirmado em produção

| Campo | Tipo | Fonte RAW | Notas |
|---|---|---|---|
| `day` | DATE | `raw.day` | SAFE_CAST |
| `mgid_client_id` | STRING | `platform_client_links` | LEFT JOIN |
| `mgid_campaign_id` | STRING | `raw.campaignid` | |
| `widget_id` | STRING | `raw.widgetid` | ID numérico do publisher placement |
| `impressions` | INT64 | `raw.impressions` | SAFE_CAST |
| `clicks` | INT64 | `raw.clicks` | SAFE_CAST |
| `spent` | FLOAT64 | `raw.spent → $.amount` | dict parser |
| `revenue` | FLOAT64 | `raw.revenue → $.amount` | dict parser |
| `profit` | FLOAT64 | `raw.profit → $.amount` | dict parser |
| `roas` | FLOAT64 | `raw.roas` | SAFE_CAST direto |
| `source_table` | STRING | literal | `'stats_by_widget'` |

**DDL executado (`stg/ddl/mgid_delivery_by_widget.sql`):**
```sql
CREATE OR REPLACE VIEW `adframework.stg.mgid_delivery_by_widget` AS

WITH stats_deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY day, campaignid, widgetid ORDER BY raw_ingested_at DESC) AS rn
  FROM `adframework.raw.mgid_stats_by_widget`
  WHERE day IS NOT NULL
    AND campaignid IS NOT NULL
    AND widgetid IS NOT NULL
),

parsed AS (
  SELECT
    day, campaignid, widgetid, impressions, clicks,
    REPLACE(REPLACE(spent,   "'", '"'), 'None', 'null') AS spent_json,
    REPLACE(REPLACE(revenue, "'", '"'), 'None', 'null') AS revenue_json,
    REPLACE(REPLACE(profit,  "'", '"'), 'None', 'null') AS profit_json,
    roas, rn
  FROM stats_deduped
)

SELECT
  SAFE_CAST(p.day AS DATE)                                          AS day,
  pcl.client_id                                                     AS mgid_client_id,
  p.campaignid                                                      AS mgid_campaign_id,
  p.widgetid                                                        AS widget_id,
  SAFE_CAST(p.impressions AS INT64)                                AS impressions,
  SAFE_CAST(p.clicks      AS INT64)                                AS clicks,
  SAFE_CAST(JSON_VALUE(p.spent_json,   '$.amount') AS FLOAT64)    AS spent,
  SAFE_CAST(JSON_VALUE(p.revenue_json, '$.amount') AS FLOAT64)    AS revenue,
  SAFE_CAST(JSON_VALUE(p.profit_json,  '$.amount') AS FLOAT64)    AS profit,
  SAFE_CAST(p.roas AS FLOAT64)                                     AS roas,
  'stats_by_widget'                                                AS source_table
FROM parsed p
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON  pcl.platform   = 'mgid'
  AND pcl.link_type  = 'campaignid'
  AND pcl.link_value = p.campaignid
WHERE p.rn = 1;
```

---

## Sumário final STG (todas as tabelas) ✅

| # | Tabela STG | Fonte RAW | Grain | Linhas STG | Status |
|---|---|---|---|---|---|
| T1 | `stg.mgid_campaigns` | `raw.mgid_campaigns` | por campanha | ~248 | ✅ EM PRODUÇÃO (2026-06-12) |
| T2 | `stg.mgid_creatives` | `raw.mgid_creatives` | por criativo | 408 | ✅ EM PRODUÇÃO (2026-06-14) |
| T3 | `stg.mgid_delivery` | `raw.mgid_stats_daily` | day+campaign | 2.338 | ✅ EM PRODUÇÃO (2026-06-14) |
| T4 | `stg.mgid_creative_delivery` | `raw.mgid_stats_creative` | day+campaign+creative | 4.030 | ✅ EM PRODUÇÃO (2026-06-14) |
| T8 | `stg.mgid_revenue` | `raw.mgid_stats_daily` | day+campaign | 2.338 | ✅ EM PRODUÇÃO (2026-06-14) |
| T9 | `stg.mgid_delivery_by_device` | `raw.mgid_stats_by_device` | day+campaign+device | 4.583 | ✅ EM PRODUÇÃO (2026-06-14) |
| T10 | `stg.mgid_delivery_by_geo` | `raw.mgid_stats_by_geo` | day+campaign+region | 31.653 | ✅ EM PRODUÇÃO (2026-06-14) |
| T11 | `stg.mgid_delivery_by_os` | `raw.mgid_stats_by_os` | day+campaign+os | 57.880 | ✅ EM PRODUÇÃO (2026-06-14) |
| T11b | `stg.mgid_delivery_by_browser` | `raw.mgid_stats_by_browser` | day+campaign+browser | 24.081 | ✅ EM PRODUÇÃO (2026-06-14) — STG only (sem gold) |
| T12 | `stg.mgid_delivery_by_hour` | `raw.mgid_stats_by_hour` | day+campaign+hour | 22.514 | ✅ EM PRODUÇÃO (2026-06-14) |
| T13 | `stg.mgid_delivery_by_widget` | `raw.mgid_stats_by_widget` | day+campaign+widget | 779.256 | ✅ EM PRODUÇÃO (2026-06-14) |

---

## Mapa STG × MediaSmart

| # | MediaSmart STG | MGID equivalente | Status |
|---|---|---|---|
| T1 | `stg.ms_clients` | ❌ Não existe — client_id via `platform_client_links` | — |
| T3 | `stg.ms_campaigns` | `stg.mgid_campaigns` | ✅ Em produção |
| T4 | `stg.ms_strategies` | ❌ MGID não tem estratégia | — |
| T5 | `stg.ms_creatives` | `stg.mgid_creatives` | ✅ Em produção |
| T6 | `stg.ms_delivery` | `stg.mgid_delivery` | ✅ Em produção |
| T7 | `stg.ms_creative_delivery` | `stg.mgid_creative_delivery` | ✅ Em produção |
| T8 | `stg.ms_revenue` | `stg.mgid_revenue` | ✅ Em produção |
| T9 | `stg.ms_delivery_by_device` | `stg.mgid_delivery_by_device` | ✅ Em produção |
| T10 | `stg.ms_delivery_by_geo` | `stg.mgid_delivery_by_geo` | ✅ Em produção |
| T11 | `stg.ms_delivery_by_os` | `stg.mgid_delivery_by_os` | ✅ Em produção |
| — | ❌ MS não tem browser | `stg.mgid_delivery_by_browser` | ✅ Em produção (STG only) |
| T12 | `stg.ms_delivery_by_hour` | `stg.mgid_delivery_by_hour` | ✅ Em produção |
| T13 | `stg.ms_delivery_by_publisher` | `stg.mgid_delivery_by_widget` | ✅ Em produção |

---

## Gaps confirmados vs MediaSmart

| Campo MS | Status MGID |
|---|---|
| `strategy_id/name` | ❌ MGID não tem estratégia |
| `event_id` | ❌ Não existe — client_id único por conta |
| `updated_at` em campanhas/criativos | ❌ API não retorna — só `whenAdd` |
| `conversion_source` | ❌ Conceito exclusivo MS |
| `app_vs_web` | ❌ Sem dimensão equivalente |
| `video_start/25/50/75/complete` em drilldowns | ❌ statistics-reports não tem quartis por drilldown |
| `media_cost_brl` | ❌ MGID reporta só BRL (moeda única) |
| Geo nível cidade com país separado | ⚠️ region retorna nome texto (ex: "Campinas City") — JOIN com geo_regions a avaliar |
| `publisher_company/url/ad_exchange` | ❌ MGID tem widgetId + source (sem metadados do publisher) |
| `size` width/height em criativos | ❌ API especifica min/rec mas não retorna no GET |
| Múltiplos clientes por conta | ❌ CLIENT_ID único (824956) = 1 cliente por API token |

---

## Decisões de design

- **`spent` para T8, não T3:** mesma separação delivery/revenue da MediaSmart — STG mantém padrão unificado
- **`revenue`/`profit` em todos os jobs:** aprovado em 2026-06-13 — verificar granularidade após ingestão inicial
- **Sem `strategy_id`:** MGID não tem estratégia — gold layer terá NULL nessa coluna para linhas MGID
- **2 jobs para OS/browser:** E1 + E2 separados porque `os` e `browser` são atributos independentes sem hierarquia (limite de 3 dims por request)
- **lookup geo D:** `region` retorna nome textual (não ID) — revisão do design T10 necessária antes de executar DDL
- **Python dict serializado:** `spent`/`cpc`/`revenue`/`profit` armazenados como STRING. STG faz: `SAFE_CAST(JSON_VALUE(REPLACE(REPLACE(col,"'",'"'),'None','null'), '$.amount') AS FLOAT64)`

---

## Próximos passos

1. ✅ Raw jobs A–G criados e validados (2026-06-14)
2. ✅ Backfill A–G completo: 2025-10-01 → 2026-06-13, 256 dias (2026-06-14)
3. ✅ STG T1–T4 + T8–T13b — todas as 11 views em produção (2026-06-14)
4. ✅ Fix firstlevel: `write_mode=WRITE_TRUNCATE` aplicado nos docs Firestore `mgid_firstlevel_campaigns` e `mgid_firstlevel_creatives` (2026-06-14)
5. **← PRÓXIMO** Gold layer: `gold.fact_delivery` + `gold.dim_campaign` com MGID alinhado à MediaSmart

### Pendências técnicas deferred

- **`country_code` para T10 (geo):** `raw.mgid_geo_regions` tem 0 linhas (job one-time nunca rodou). Carregar via endpoint `/v1/dictionaries/geo` e adicionar JOIN em T10 para incluir `country_code`. Enquanto isso, `region` como texto bruto funciona para análises.
- **Normalização `operating_system` no gold:** MS usa lowercase (`android`), MGID usa capitalizado (`Android`) — aplicar `LOWER()` na join do gold layer.
- **Firstlevel cleanup:** verificar no próximo cron (~178 campaigns às 03:20 UTC, ~408 creatives na terça 03:00 UTC) se a truncagem correu bem. Após confirmar, atualizar contagem em `raw.mgid_campaigns` e `raw.mgid_creatives`.
