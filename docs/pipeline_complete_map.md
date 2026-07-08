# AdFramework — Mapa Completo do Pipeline de Dados

---
> **⚠️ LEGADO — PRÉ-REBUILD 2026-06-16 ⚠️**
> Este documento descreve a pipeline **anterior ao reset completo de 2026-06-16**.
> Tabelas, views, schemas e colunas aqui descritos **foram dropados e não existem mais no BigQuery**.
> Mantenha para consulta histórica — **não use como referência para desenvolvimento novo.**
> Plano atual: [bq_restructuring_plan.md](bq_restructuring_plan.md) · [CHANGELOG.md](../CHANGELOG.md)
---
**Projeto GCP:** `adframework`  
**Gerado em:** 2026-06-03  
**Autor:** Douglas Reche  
**Objetivo:** Documentação exaustiva de cada objeto BQ — origem, schema, granularidade, transformações, campos calculados, campos nulos, dependências e correlações do RAW ao GOLD.

---

## Sumário

1. [Arquitetura Geral](#1-arquitetura-geral)
2. [Fontes de Ingestão](#2-fontes-de-ingestão)
3. [Camada RAW](#3-camada-raw)
4. [Camada STG](#4-camada-stg)
5. [Camada CORE](#5-camada-core)
6. [Camada GOLD](#6-camada-gold)
7. [Mapa de Dependências](#7-mapa-de-dependências)
8. [Campos Calculados e Relacionais](#8-campos-calculados-e-relacionais)
9. [Campos Nulos e Limitações](#9-campos-nulos-e-limitações)
10. [IDs e Chaves de Join](#10-ids-e-chaves-de-join)
11. [Pendências e Itens Open](#11-pendências-e-itens-open)

---

## 1. Arquitetura Geral

### Princípio Medallion (Bronze → Silver → Gold)

```
FONTES EXTERNAS
    │
    ├── MediaSmart API (api.mediasmart.io)
    ├── MGID API (api.mgid.com)
    ├── Google Sheet (Siprocal)
    │
    ▼
┌─────────────────────────────────────────────────┐
│  RAW  (Bronze) — dado bruto STRING, sem filtro  │
│  Grain: linha exata da fonte                    │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│  STG  (Silver) — VIEWs, tipagem, normalização   │
│  Grain: mesmo do RAW, só tipado                 │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│  CORE — dimensões canônicas, vínculos           │
│  dim_client, platform_client_links,             │
│  campaign_format_map                            │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│  GOLD — Star Schema para Power BI               │
│  fact_delivery, dim_client, dim_campaign,       │
│  dim_conversion_mapping, fact_io_plan           │
└─────────────────────────────────────────────────┘
```

### Regra de separação do dataset `core`

| Tabela | Sistema | Usar no pipeline? |
|---|---|---|
| `core.dim_client` | Nosso pipeline | ✓ SIM |
| `core.platform_client_links` | Nosso pipeline | ✓ SIM |
| `core.campaign_format_map` | Nosso pipeline | ✓ SIM |
| `core.io_manager_v2` | Admin UI do Shiro | ✗ NÃO |
| `core.io_line_bindings_v2` | Admin UI do Shiro | ✗ NÃO |
| `core.proposals` | Admin UI do Shiro | ✗ NÃO |
| `core.proposal_lines` | Admin UI do Shiro | ✗ NÃO |
| Views `*_enriched_v2`, `*_v4` | Admin UI do Shiro | ✗ NÃO |

---

## 2. Fontes de Ingestão

### 2.1 MediaSmart API
- **Base URL:** `https://api.mediasmart.io`
- **Auth:** Bearer token (login via `/login` com username/password, expira em 50 min)
- **Credenciais:** Firestore `platform_credentials/mediasmart` → `secrets.email`, `secrets.password`
- **Jobs ativos (Firestore `platform_reports`):**

| Job ID | Endpoint | Destino | Schedule | Status |
|---|---|---|---|---|
| `mediasmart_daily_daily` | `/api/analytics/custom-report` | `raw.mediasmart_delivery` | 03:20 UTC diário | ⚠ Timeout |
| `mediasmart_revenue_daily` | `/api/analytics/custom-report` | `raw.mediasmart_revenue` | 03:25 UTC diário | ⚠ Running/stuck |
| `mediasmart_firstlevel_campaigns` | `/api/campaigns` | `raw.mediasmart_campaigns` | 03:20 UTC diário | ✓ OK |
| `mediasmart_firstlevel_creatives` | `/api/creatives` | `raw.mediasmart_creatives` | 03:00 UTC semanal | ✓ OK |
| `mediasmart_firstlevel_advertisers` | `/api/advertisers` | `raw.mediasmart_advertisers` | 03:00 UTC semanal | ✓ OK |
| `mediasmart_bid_supply_hourly` | `/api/analytics/custom-report` | `raw.mediasmart_bid_supply` | — | ✗ INATIVO (stuck desde mar/26) |

**Parâmetros de ingestão delivery (params_json atual):**
```json
{
  "drilldown": "day,eventid,controlid,strategyid,strategyname,convsource",
  "kpis": "impressions,clicks,videostart,videofirstquartile,videomidpoint,videothirdquartile,videocomplete,events1,events2,events3,events4,events5,clientrevenue,convertedclientrevenue,client_cost",
  "format": "csv",
  "raw": "true"
}
```

> ⚠ **Nota:** `creativeid`, `creativetype`, `nativesize`, `size` estão disponíveis na API mas bloqueados no handler `update_type: daily` do orchestrator.py do Shiro. Precisam de job separado `daily_creative`.

**Parâmetros de ingestão revenue:**
```json
{
  "drilldown": "day,controlid,eventid,strategyid,revenuesource,convsource",
  "kpis": "clientrevenue",
  "format": "csv",
  "raw": "true",
  "max_backfill_days": 14
}
```
> ✓ `rules` filter removido em 2026-06-03 — agora captura todos os `revenuesource`.

### 2.2 MGID API
- **Base URL:** `https://api.mgid.com/v1`
- **Auth:** Bearer token estático (não expira)
- **Credenciais:** Firestore `platform_credentials/mgid` → `secrets.token`, `secrets.client_id`
- **CLIENT_ID:** `824956`
- **Jobs ativos:**

| Job ID | Endpoint | Destino | Schedule | Status |
|---|---|---|---|---|
| `mgid_daily_daily` | `/goodhits/clients/824956/statistics-reports` | `raw.mgid_delivery` | 03:20 UTC diário | ✓ OK |
| `mgid_firstlevel_campaigns` | `/goodhits/clients/824956/campaigns` | `raw.mgid_campaigns` | 03:20 UTC diário | ✓ OK |
| `mgid_firstlevel_creatives` | `/goodhits/clients/824956/teasers` | `raw.mgid_creatives` | 03:00 UTC semanal | ✓ OK |

**Parâmetros de ingestão delivery (params_json atual):**
```
metrics[]=clicks&metrics[]=impressions&metrics[]=conversionsInterest
&metrics[]=conversionsDecision&metrics[]=conversionsBuy&metrics[]=spent
&dimensions[]=day&dimensions[]=campaignId
```
> ✓ `metrics[]=spent` adicionado em 2026-06-03. Histórico de `spent` foi backfillado manualmente.

### 2.3 Siprocal (Google Sheet)
- **Fonte:** Google Sheets `1HaGrxaU-nt3fvqxaJ1CSlABYJGNY28rhQC49dcGzLWs`
- **Aba:** `Planilha1`
- **Auth:** Service account `adframework-etl@adframework.iam.gserviceaccount.com` (precisa ser Viewer na sheet)
- **Job ativo:**

| Job ID | Endpoint | Destino | Schedule |
|---|---|---|---|
| `siprocal_daily_external` | `external://bq/adframework.raw.siprocal_raw_sheet` | `raw.siprocal_delivery` | 05:00 UTC diário |

**Fluxo Siprocal:**
```
Google Sheet → raw.siprocal_raw_sheet (EXTERNAL) → ETL lê → raw.siprocal_delivery
```

> ⚠ **Campo `format` (Display/Native/Push/Retargeting):** NÃO vem da API nem da planilha. Deve ser gerenciado em `core.campaign_format_map`.

---

## 3. Camada RAW

### 3.1 `raw.mediasmart_delivery`
**Tipo:** TABLE  
**Rows:** 641.798  
**Período:** 2025-08-01 → 2026-05-24  
**Grain:** `day + eventid + strategyid + conversion_source` (múltiplas linhas por campanha/dia)  
**Alimentado por:** `mediasmart_daily_daily` (staging via `raw.mediasmart_daily`)  
**Modificado:** 2026-05-26  

> ⚠ **Gap crítico:** Dados param em 2026-05-24. Job com `error:Timeout` desde jun/26. Dados mais recentes ficam presos em `raw.mediasmart_daily` (staging).

| Campo | Tipo | Nulos | Notas |
|---|---|---|---|
| `day` | STRING | 0 | Formato `YYYY-MM-DD` |
| `eventid` | STRING | 0 | 14 distintos — chave de join com `platform_client_links` |
| `controlid` | STRING | 0 | ID da campanha pai (join com `raw.mediasmart_campaigns`) |
| `strategyid` | STRING | ~0 | ID da estratégia — **425.076 NULL** (dados ago–dez/2025 via pipeline legado) |
| `strategyname` | STRING | varia | Valor como "CPM", "CPC" — **NÃO é o nome real da campanha** |
| `conversion_source` | STRING | varia | click, view, etc. |
| `impressions` | STRING | 0 | SAFE_CAST para INT64 na STG |
| `clicks` | STRING | 0 | SAFE_CAST para INT64 na STG |
| `video_start` | STRING | varia | — |
| `video_25_viewed` | STRING | varia | — |
| `video_50_viewed` | STRING | varia | — |
| `video_75_viewed` | STRING | varia | — |
| `video_completion` | STRING | varia | — |
| `conversions_1..5` | STRING | varia | Significado por cliente em `gold.dim_conversion_mapping` |
| `clientrevenue` | STRING | **641.798 (100%)** | ✗ VAZIO — novos campos adicionados em 2026-06-03, populate no próximo ETL |
| `convertedclientrevenue` | STRING | **641.798 (100%)** | ✗ VAZIO — mesmo motivo |
| `client_cost` | STRING | **641.798 (100%)** | ✗ VAZIO — mesmo motivo |
| `platform` | STRING | 0 | Sempre `mediasmart` |
| `report_name` | STRING | 0 | Sempre `Daily` |
| `raw_ingested_at` | TIMESTAMP | 0 | UTC |

**Staging interno (não pipeline):**
- `raw.mediasmart_daily` (75 rows) — tabela intermediária do ETL (`table_name` do job). Tem schema mais rico (31 colunas) incluindo `creative_id`, `creative_type` que não chegam ao destino final.

---

### 3.2 `raw.mediasmart_revenue`
**Tipo:** TABLE  
**Rows:** 9.247  
**Período:** 2026-03-06 → 2026-05-16  
**Grain:** `day + controlid + strategyid + revenuesource`  
**Alimentado por:** `mediasmart_revenue_daily` (staging via `raw.mediasmart_revenue_daily`)  

> ⚠ **Revenue só existe a partir de mar/2026.** Dados de ago/2025–fev/2026 não têm custo.

| Campo | Tipo | Nulos | Notas |
|---|---|---|---|
| `day` | STRING | 0 | — |
| `controlid` | STRING | 0 | Campanha pai |
| `strategyid` | STRING | 0 | 229 estratégias distintas |
| `revenuesource` | STRING | 0 | `event4` (R$11.7M), `event3` (R$996k), `1` (R$0) |
| `clientrevenue` | STRING | 0 | **Total: R$12.702.913** |
| `eventid` | STRING | **9.247 (100%)** | ✗ VAZIO — campo novo adicionado 2026-06-03 |
| `revenue_source` | STRING | **9.247 (100%)** | ✗ VAZIO — campo novo, populate no próximo ETL |
| `conversion_source` | STRING | **9.247 (100%)** | ✗ VAZIO — campo novo |
| `platform` | STRING | 0 | `mediasmart` |
| `report_name` | STRING | 0 | `DailyRevenue` |

**Distribuição por revenuesource:**
- `event4` → 3.430 linhas → R$11.706.863 (92% do total)
- `event3` → 1.803 linhas → R$996.049 (8%)
- `1` → 4.014 linhas → R$0,00 (linhas de rastreamento sem valor)

**Staging interno:** `raw.mediasmart_revenue_daily` (267 rows, 3 dias apenas — staging temp do ETL).

---

### 3.3 `raw.mgid_delivery`
**Tipo:** TABLE  
**Rows:** 3.491  
**Período:** 2025-09-30 → 2026-05-25  
**Grain:** `day + campaignid + teaserid`  
**Alimentado por:** `mgid_daily_daily` (staging via `raw.mgid_daily`)  

| Campo | Tipo | Nulos | Notas |
|---|---|---|---|
| `day` | STRING | 0 | — |
| `campaignid` | STRING | 0 | 95 campanhas distintas |
| `teaserid` | STRING | varia | 167 teasers distintos |
| `impressions` | STRING | 0 | Total: 61.831.674 |
| `clicks` | STRING | 0 | Total: 333.116 |
| `conversionsinterest` | STRING | 0 | Total: 0 (sem dados) |
| `conversionsdecision` | STRING | 0 | Total: 0 (sem dados) |
| `conversionsbuy` | STRING | 0 | Total: 0 (sem dados) |
| `spent` | STRING | **3.491 (100%)** | ✗ VAZIO — adicionado manualmente como coluna. ETL ainda não popula (params_json atualizado 2026-06-03, novo dado no próximo run) |
| `platform` | STRING | 0 | `mgid` |
| `report_name` | STRING | 0 | `Daily` |

**Staging interno:** `raw.mgid_daily` (28 rows) — staging temp do ETL.

---

### 3.4 `raw.siprocal_delivery`
**Tipo:** TABLE  
**Rows:** 1.021  
**Período:** 2025-08-22 → 2026-05-26  
**Grain:** `day + advertiser + campaign_id + creative`  
**Alimentado por:** `siprocal_daily_external` (via `raw.siprocal_raw_sheet` EXTERNAL)  

| Campo | Tipo | Nulos | Notas |
|---|---|---|---|
| `day` | STRING | 0 | Pode vir como `dd/mm/yyyy` da planilha — normalizado na STG |
| `advertiser` | STRING | 0 | 33 distintos — chave de join com `platform_client_links` |
| `campaign_id` | STRING | 0 | 25 distintos (incluindo string vazia `""`) |
| `creative_type` | STRING | **1.021 (100%)** | ✗ SEMPRE NULL — planilha não fornece |
| `creative` | STRING | varia | — |
| `impressions` | STRING | 0 | Total: 6.932.031 |
| `clicks` | STRING | 0 | Total: 114.056 |
| `platform` | STRING | 0 | `siprocal` |
| `report_name` | STRING | 0 | `Daily` |

> ⚠ **Formato (Display/Native/Push):** NÃO existe na planilha. Mapeado em `core.campaign_format_map` como `Push` (suposição — confirmar com equipe).

**Pipeline Siprocal:**
```
Google Sheet (1HaGrxaU...)
    ↓
raw.siprocal_raw_sheet   (EXTERNAL TABLE — pointer para a sheet)
    ↓  ETL job siprocal_daily_external
raw.siprocal_delivery    (TABLE canônica)
```

---

### 3.5 Tabelas Dimensionais RAW (First-Level)

| Tabela | Rows | Grain | Alimentado por | Uso |
|---|---|---|---|---|
| `raw.mediasmart_campaigns` | 4.531 | `id` (campaign/control) | `mediasmart_firstlevel_campaigns` | Join via `controlid` para obter nome da campanha |
| `raw.mediasmart_creatives` | 31.192 | `id` (creative) | `mediasmart_firstlevel_creatives` | `gold.dim_campaign` |
| `raw.mediasmart_advertisers` | 21 | `id` | `mediasmart_firstlevel_advertisers` | Referência apenas |
| `raw.mgid_campaigns` | 18.420 | `id` | `mgid_firstlevel_campaigns` | `gold.dim_campaign` |
| `raw.mgid_creatives` | 10.228 | `id` | `mgid_firstlevel_creatives` | `gold.dim_campaign` |

> ⚠ **`raw.mediasmart_campaigns`:** `campaign_id` e `creative_id` aparecem como NULL em muitas linhas — truncate diário pode perder referências. O campo `name` contém o formato da campanha (ex: `CORA_CONTADIGITAL_DISPLAY_MAIO26`).

---

### 3.6 Tabelas Órfãs e Staging

| Tabela | Rows | Status |
|---|---|---|
| `raw.mediasmart_daily` | 75 | Staging temp do ETL `mediasmart_daily_daily` — NÃO dropar |
| `raw.mediasmart_revenue_daily` | 267 | Staging temp do ETL `mediasmart_revenue_daily` — NÃO dropar |
| `raw.mgid_daily` | 28 | Staging temp do ETL `mgid_daily_daily` — NÃO dropar |
| `raw.mediasmart_bid_supply` | 602.179 | Job INATIVO desde mar/2026. Não alimenta o pipeline gold |
| `raw.siprocal_raw_sheet` | EXTERNAL | Fonte da planilha Siprocal — pointer para Google Sheet |

---

## 4. Camada STG

Todas as STG são **VIEWs** — não armazenam dados, leem do RAW em tempo real.

### 4.1 `stg.mediasmart_delivery`
**Grain:** Mesmo do RAW (`day + eventid + strategyid + conversion_source`)  
**Fonte:** `raw.mediasmart_delivery`  
**Rows efetivos:** 641.798 (idêntico ao RAW — nenhuma linha filtrada)

**Transformações:**
| Campo RAW | Campo STG | Transformação |
|---|---|---|
| `day` (STRING) | `day` (DATE) | `SAFE_CAST(day AS DATE)` — remove linhas com `day IS NULL` (0 linhas) |
| `impressions` (STRING) | `impressions` (INT64) | `SAFE_CAST` |
| `clicks` (STRING) | `clicks` (INT64) | `SAFE_CAST` |
| `video_*` (STRING) | `video_*` (INT64) | `SAFE_CAST` |
| `conversions_1..5` (STRING) | `conversions_1..5` (INT64) | `SAFE_CAST` |
| `clientrevenue` (STRING) | `clientrevenue` (FLOAT64) | `SAFE_CAST` — **100% NULL hoje** |
| `client_cost` (STRING) | `client_cost` (FLOAT64) | `SAFE_CAST` — **100% NULL hoje** |
| `convertedclientrevenue` | `convertedclientrevenue` | `SAFE_CAST` — **100% NULL hoje** |

**Campos que EXISTEM no raw mas NÃO estão na STG:** nenhum — todos os campos passam.

---

### 4.2 `stg.mediasmart_revenue`
**Grain:** `day + controlid + strategyid + revenuesource`  
**Fonte:** `raw.mediasmart_revenue`  
**Rows:** 9.247

**Transformações:**
| Campo RAW | Campo STG | Transformação |
|---|---|---|
| `day` (STRING) | `day` (DATE) | `SAFE_CAST` |
| `clientrevenue` (STRING) | `clientrevenue` (NUMERIC) | `SAFE_CAST` |
| `revenuesource` | `revenuesource` | pass-through (sem rename) |

**Campos novos (eventid, revenue_source, conversion_source):** ainda NULL no raw — passarão quando o próximo ETL rodar com os novos params.

---

### 4.3 `stg.mgid_delivery`
**Grain:** `day + campaignid + teaserid`  
**Fonte:** `raw.mgid_delivery`  
**Rows:** 3.491

**Transformações:**
| Campo RAW | Campo STG | Transformação |
|---|---|---|
| `day` (STRING) | `day` (DATE) | `SAFE_CAST` |
| `impressions` (STRING) | `impressions` (INT64) | `SAFE_CAST` |
| `clicks` (STRING) | `clicks` (INT64) | `SAFE_CAST` |
| `conversions*` (STRING) | `conversions*` (INT64) | `SAFE_CAST` |
| `spent` (STRING) | `spent` (FLOAT64) | `SAFE_CAST` — **100% NULL hoje** (ETL não popula ainda) |

---

### 4.4 `stg.siprocal_delivery`
**Grain:** `day + advertiser + campaign_id + creative`  
**Fonte:** `raw.siprocal_delivery`  
**Rows:** 1.021

**Transformações (incluindo normalização de data — movida para STG em 2026-06-03):**
| Campo RAW | Campo STG | Transformação |
|---|---|---|
| `day` (STRING `dd/mm/yyyy` ou `yyyy-mm-dd`) | `day` (DATE) | `CASE WHEN REGEXP_CONTAINS(...) THEN PARSE_DATE('%d/%m/%Y', day) ELSE SAFE_CAST(day AS DATE) END` |
| `advertiser` (STRING) | `advertiser` (STRING) | `COALESCE(REGEXP_EXTRACT(UPPER(TRIM(...)), r'^NEWAD_(.+)_BR_\w+$'), UPPER(TRIM(advertiser)))` — extrai nome limpo |
| `advertiser` original | `campaign_name` (STRING) | Mantém o advertiser bruto como campo de nome |
| `impressions` (STRING) | `impressions` (INT64) | `SAFE_CAST` |
| `clicks` (STRING) | `clicks` (INT64) | `SAFE_CAST` |

**Campo `creative_type`:** sempre NULL no raw → NULL na STG.

---

### 4.5 `stg.luckbet_io_plan` — QUEBRADA
**Status:** ✗ VIEW quebrada — depende de `raw.luckbet_io_plan_snapshot` que foi dropado.  
**Impacto:** `gold.fact_io_plan` lê desta view → retorna 0 rows.

---

### 4.6 `stg.mediasmart_bid_supply`
**Status:** VIEW funcional (lê `raw.mediasmart_bid_supply` com 602K rows).  
**Uso no pipeline:** ✗ Nenhum — não alimenta o GOLD. Dados de bid supply disponíveis mas sem consumo.

---

## 5. Camada CORE

### 5.1 `core.dim_client` ✓ NOSSO PIPELINE
**Tipo:** TABLE  
**Rows:** 26  
**Alimentado por:** Admin UI (Firestore sync)  
**Grain:** `client_id` (único por cliente)

| Campo | Tipo | Notas |
|---|---|---|
| `client_id` | STRING | PK. Formato: `nome_hash8` ex: `banco_cora_fe13d78a` |
| `slug` | STRING | Slug URL-friendly |
| `name` | STRING | Nome comercial |
| `sector` | STRING | Setor/indústria |
| `status` | STRING | `active` (todos os 26 ativos) |
| `created_at` | TIMESTAMP | — |
| `deactivated_at` | TIMESTAMP | NULL para todos (nenhum inativo) |
| `notes` | STRING | Livre |
| `seed_loaded_at` | TIMESTAMP | Data da carga inicial |
| `parent_client_id` | STRING | FK para si mesmo — 6 clientes têm parent (hierarquia agência/cliente) |
| `client_level` | INT64 | `1` = raiz (20 clientes), `2` = filho (6 clientes) |
| `newad_account_id` | STRING | ID interno da conta NewAD |

**Hierarquia:**
- **Nível 1** (20 clientes): clientes diretos
- **Nível 2** (6 clientes): sub-clientes com `parent_client_id` referenciando um nível 1

---

### 5.2 `core.platform_client_links` ✓ NOSSO PIPELINE
**Tipo:** TABLE  
**Rows:** 149  
**Alimentado por:** Admin UI  
**Grain:** `platform + link_type + link_value` (único)  
**Propósito:** Atribuir entregas de plataformas a clientes via chave de join

| Campo | Tipo | Notas |
|---|---|---|
| `platform` | STRING | `mediasmart`, `mgid`, `siprocal` |
| `link_type` | STRING | `eventid` (MS), `campaignid` (MGID), `advertiser` (Siprocal) |
| `link_value` | STRING | Valor do ID/nome na plataforma |
| `client_id` | STRING | FK para `core.dim_client.client_id` — **1 link com `client_id=NULL` (unresolved)** |
| `status` | STRING | `active`, `pending_confirmation`, `unresolved` |
| `notes` | STRING | — |
| `created_at` | TIMESTAMP | — |

**Distribuição por plataforma:**

| Plataforma | Link Type | Ativo | Pending | Unresolved | Clientes |
|---|---|---|---|---|---|
| `mediasmart` | `eventid` | 9 | 4 | 1 | 13 |
| `mgid` | `campaignid` | 68 | 56 | 0 | 22 |
| `siprocal` | `advertiser` | 11 | 0 | 0 | 11 |

> ⚠ **56 links MGID `pending_confirmation`:** Campanhas MGID vinculadas a clientes mas não confirmadas pelo time AdOps. São usadas na atribuição do gold (sem filtro de status).  
> ⚠ **1 link `unresolved`:** MediaSmart `eventid=newad_brazil-neu83z5jjnkcnrbmwwxjsrzzfwaigdx7` com `client_id=NULL` — cliente não identificado, gera linhas `unattributed` no gold.

**Join com gold.fact_delivery:**
```sql
-- MediaSmart: join por eventid
LEFT JOIN core.platform_client_links pcl
  ON pcl.platform='mediasmart' AND pcl.link_type='eventid' AND pcl.link_value = d.eventid

-- MGID: join por campaignid
LEFT JOIN core.platform_client_links pcl
  ON pcl.platform='mgid' AND pcl.link_type='campaignid' AND pcl.link_value = d.campaignid

-- Siprocal: join por advertiser
LEFT JOIN core.platform_client_links pcl
  ON pcl.platform='siprocal' AND pcl.link_type='advertiser' AND pcl.link_value = d.advertiser
```

---

### 5.3 `core.campaign_format_map` ✓ NOSSO PIPELINE (criado 2026-06-03)
**Tipo:** TABLE  
**Rows:** 18 (apenas Cora por enquanto)  
**Grain:** `platform + platform_campaign_id`  
**Propósito:** Mapear o formato de campanha (Display, Native, Push, Retargeting, Video) — informação que NÃO vem de nenhuma API

| Campo | Tipo | Notas |
|---|---|---|
| `platform` | STRING | `mediasmart`, `mgid`, `siprocal` |
| `platform_campaign_id` | STRING | ID da estratégia/campanha |
| `client_id` | STRING | FK para `core.dim_client` |
| `format` | STRING | `Display`, `Native`, `Push`, `Retargeting`, `Video`, `Outros` |
| `source` | STRING | `campaign_name` (extraído do nome), `manual`, `io_plan` |
| `notes` | STRING | Nome original da campanha que gerou a classificação |
| `created_at` | TIMESTAMP | — |
| `updated_at` | TIMESTAMP | — |

**Origem do formato por plataforma:**
- **MediaSmart:** extraído de `raw.mediasmart_campaigns.name` via `controlid` (ex: `CORA_CONTADIGITAL_VIDEO_FEVEREIRO` → `Video`)
- **MGID:** extraído de `raw.mgid_campaigns.name` (ex: `Banco Cora | NewAd | Native | 01/01-31/01` → `Native`)
- **Siprocal:** `Push` — **assumido**, não vem da planilha. Confirmar com equipe.

**Estado atual (Cora):**

| Plataforma | Formato | Campanhas |
|---|---|---|
| mediasmart | Display | 2 |
| mediasmart | Retargeting | 2 |
| mediasmart | Video | 2 |
| mgid | Native | 7 |
| mgid | Push | 1 |
| siprocal | Push | 4 |

---

## 6. Camada GOLD

### 6.1 `gold.fact_delivery` ✓ TABELA PRINCIPAL
**Tipo:** TABLE (particionada por `day`, clusterizada por `client_id + platform`)  
**Rows:** 13.874  
**Grain:** `day + client_id + platform + platform_campaign_id`  
**Rebuild:** Manual ou via Scheduled Query `gold_daily_rebuild` (06:00 BRT diário)

**Schema:**

| Campo | Tipo | Origem | Notas |
|---|---|---|---|
| `day` | DATE | RAW → STG | Partição |
| `client_id` | STRING | `core.platform_client_links` | `'unattributed'` quando sem match |
| `platform` | STRING | Literal | `mediasmart`, `mgid`, `siprocal` |
| `platform_campaign_id` | STRING | STG | `strategyid` (MS), `campaignid` (MGID), `campaign_id` (Siprocal) |
| `impressions` | INT64 | STG | `SUM(d.impressions)` |
| `clicks` | INT64 | STG | `SUM(d.clicks)` |
| `spend` | FLOAT64 | STG revenue (MS) / RAW spent (MGID) | MS: `stg.mediasmart_revenue.clientrevenue` / MGID: `stg.mgid_delivery.spent` |
| `conversions_1..5` | INT64 | STG (MS only) | Significado por cliente em `dim_conversion_mapping` |
| `mgid_conv_interest` | INT64 | STG (MGID only) | Funil MGID |
| `mgid_conv_decision` | INT64 | STG (MGID only) | Funil MGID |
| `mgid_conv_buy` | INT64 | STG (MGID only) | Funil MGID |

**Métricas por plataforma:**

| Plataforma | Rows | Campanhas | Clientes | Impressões | Cliques | Spend |
|---|---|---|---|---|---|---|
| `mediasmart` | 10.966 | 322 | 13+unattr | 352.532.729 | 944.690 | R$12.702.913 |
| `mgid` | 2.234 | 95 | 22 | 61.831.674 | 333.116 | R$0 (spent vazio ainda) |
| `siprocal` | 674 | 25 | 11 | 6.932.031 | 114.056 | NULL |
| **TOTAL** | **13.874** | **442** | **24** | **421.296.434** | **1.391.862** | **R$12.702.913** |

**Unattributed (sem cliente vinculado):**
- 116 linhas → 4.286.522 impressões (1,0% do total)
- Causa: eventid MediaSmart sem match em `platform_client_links`

**Lógica de atribuição de spend (CORRIGIDA em 2026-06-03):**
```sql
-- MediaSmart: agregar delivery PRIMEIRO, depois join revenue — evita multiplicação
WITH ms_delivery AS (
  SELECT day, COALESCE(pcl.client_id,'unattributed') AS client_id, d.strategyid,
         SUM(d.impressions) AS impressions, ...
  FROM stg.mediasmart_delivery d
  LEFT JOIN core.platform_client_links pcl ON pcl.link_value=d.eventid
  GROUP BY 1,2,3
),
ms_revenue AS (
  SELECT day, strategyid, SUM(clientrevenue) AS spend
  FROM stg.mediasmart_revenue GROUP BY 1,2
)
SELECT ... FROM ms_delivery d LEFT JOIN ms_revenue rev ON rev.day=d.day AND rev.strategyid=d.platform_campaign_id
-- MGID: SUM(d.spent) — coluna direta da STG
-- Siprocal: NULL (sem dado de custo)
```

> ✓ **Bug corrigido:** Antes o join gerava multiplicação 16x (R$12.7M virava R$205.2M). Agora spend=R$12.702.913 = exatamente igual ao raw.

---

### 6.2 `gold.dim_client` ✓
**Tipo:** VIEW  
**Grain:** `client_id`  
**Fonte:** `core.dim_client` (LEFT JOIN consigo mesmo para parent)

```sql
SELECT c.client_id, c.slug, c.name, c.sector, c.status,
       c.created_at, c.deactivated_at, c.notes,
       c.parent_client_id, c.client_level, c.newad_account_id,
       p.name AS parent_name, p.slug AS parent_slug
FROM core.dim_client c
LEFT JOIN core.dim_client p ON c.parent_client_id = p.client_id
```

---

### 6.3 `gold.dim_campaign` ✓
**Tipo:** TABLE  
**Rows:** 465  
**Grain:** `platform + platform_campaign_id` (⚠ 5 campanhas duplicadas)  
**Alimentado por:** Rebuild manual/scheduled  
**Fonte:** `raw.mediasmart_campaigns` + `raw.mgid_campaigns` + join com `platform_client_links`

| Campo | Tipo | Notas |
|---|---|---|
| `platform` | STRING | — |
| `platform_campaign_id` | STRING | — |
| `platform_campaign_name` | STRING | Nome real da campanha. MediaSmart: `name` de `raw.mediasmart_campaigns`. MGID: `name` de `raw.mgid_campaigns` |
| `platform_advertiser_id` | STRING | — |
| `client_id` | STRING | FK `core.dim_client` |

> ⚠ **5 campanhas duplicadas:** Mesma `platform_campaign_id` com múltiplas linhas. Causa joins incorretos se usar `dim_campaign` sem DISTINCT ou QUALIFY.

---

### 6.4 `gold.dim_conversion_mapping` ✓
**Tipo:** TABLE  
**Rows:** 5  
**Grain:** `client_id + conversion_field` (ou NULL para global)  
**Alimentado por:** Manual  

| `client_id` | `conversion_field` | `conversion_label` | `platform` |
|---|---|---|---|
| NULL | `conversions_1` | `Pageview` | NULL (global) |
| `luckbet_bea15ebc` | `conversions_2` | `Cadastro` | `mediasmart` |
| `luckbet_bea15ebc` | `conversions_3` | `FTD` | `mediasmart` |
| `luckbet_bea15ebc` | `conversions_4` | `Depósito Recorrente` | `mediasmart` |
| `luckbet_bea15ebc` | `conversions_5` | `Início Cadastro` | `mediasmart` |

> **`client_id=NULL`** = mapeamento global (conversions_1 = Pageview para todos os clientes).  
> Outros clientes pendentes: Cora, Einstein, TecPar (sem mapeamento confirmado).

---

### 6.5 `gold.fact_io_plan` ✗ QUEBRADA
**Tipo:** VIEW  
**Rows:** 0  
**Status:** Chain morta: `stg.luckbet_io_plan → raw.luckbet_io_plan_snapshot` (dropado)

**Correção necessária:** reescrever para ler de `core.io_manager_v2`. Porém há conflito de client_id:
- `core.io_manager_v2.newad_client_id` = `nwd_banco-cora_acfae3ab`
- `core.dim_client.client_id` = `banco_cora_fe13d78a`
- **Formatos incompatíveis — JOIN não funciona sem mapeamento**

---

## 7. Mapa de Dependências

```
FONTES
──────
MediaSmart API ─────────────────────► raw.mediasmart_delivery ──► stg.mediasmart_delivery ──┐
                                      raw.mediasmart_daily (staging, não pipeline)           │
MediaSmart API ─────────────────────► raw.mediasmart_revenue ───► stg.mediasmart_revenue ────┤
                                      raw.mediasmart_revenue_daily (staging)                 │
MediaSmart API ─────────────────────► raw.mediasmart_campaigns ──────────────────────────────┤ ──► gold.dim_campaign
MediaSmart API ─────────────────────► raw.mediasmart_creatives ──────────────────────────────┘
MediaSmart API ─────────────────────► raw.mediasmart_advertisers (referência, não no gold)
MediaSmart API [INATIVO] ───────────► raw.mediasmart_bid_supply ──► stg.mediasmart_bid_supply (orphan)

MGID API ───────────────────────────► raw.mgid_delivery ─────────► stg.mgid_delivery ───────┐
                                      raw.mgid_daily (staging)                               │
MGID API ───────────────────────────► raw.mgid_campaigns ────────────────────────────────────┤ ──► gold.dim_campaign
MGID API ───────────────────────────► raw.mgid_creatives ───────────────────────────────────┘

Google Sheet ───────────────────────► raw.siprocal_raw_sheet (EXTERNAL)
                                          └──► ETL ──► raw.siprocal_delivery ──► stg.siprocal_delivery ──► ┐

Admin UI (Firestore) ───────────────► core.dim_client ───────────────────────────────────────────────────► gold.dim_client
Admin UI ───────────────────────────► core.platform_client_links ────────────────────────────────────────► ┘
Manual (2026-06-03) ────────────────► core.campaign_format_map (novo)

                                                                                              ┌──── core.platform_client_links
                                                                                              │
stg.mediasmart_delivery ──────────────────────────────────────────────────────────────────────┤
stg.mediasmart_revenue ──────────────────────────────────────────────────────────────────────►│──► gold.fact_delivery ──► Power BI
stg.mgid_delivery ──────────────────────────────────────────────────────────────────────────► │
stg.siprocal_delivery ──────────────────────────────────────────────────────────────────────► ┘

raw.mediasmart_campaigns + raw.mgid_campaigns ────────────────────────────────────────────────────────────► gold.dim_campaign
Manual ───────────────────────────────────────────────────────────────────────────────────────────────────► gold.dim_conversion_mapping
core.dim_client ──────────────────────────────────────────────────────────────────────────────────────────► gold.dim_client

BROKEN CHAINS:
stg.luckbet_io_plan ──────────────────────────────────────────────────────────────────────────────────────► gold.fact_io_plan (0 rows)
  └── raw.luckbet_io_plan_snapshot [DROPADO]
```

---

## 8. Campos Calculados e Relacionais

### 8.1 Campos calculados na STG

| Tabela | Campo | Cálculo |
|---|---|---|
| `stg.siprocal_delivery` | `advertiser` | `COALESCE(REGEXP_EXTRACT(UPPER(TRIM(advertiser)), r'^NEWAD_(.+)_BR_\w+$'), UPPER(TRIM(advertiser)))` |
| `stg.siprocal_delivery` | `campaign_name` | `advertiser` original (raw) |
| `stg.siprocal_delivery` | `day` | Normalização de data: `dd/mm/yyyy` → `DATE` ou `SAFE_CAST` |

### 8.2 Campos calculados no GOLD

| Tabela | Campo | Cálculo |
|---|---|---|
| `gold.fact_delivery` | `client_id` | `COALESCE(pcl.client_id, 'unattributed')` |
| `gold.fact_delivery` | `spend` (MS) | `SUM(rev.spend)` onde rev = `stg.mediasmart_revenue` agrupado por `day+strategyid` |
| `gold.fact_delivery` | `spend` (MGID) | `SUM(d.spent)` — direto da STG |
| `gold.dim_client` | `parent_name` | Self-join `core.dim_client` via `parent_client_id` |
| `gold.dim_client` | `parent_slug` | Self-join `core.dim_client` via `parent_client_id` |

### 8.3 Campos relacionais (chaves de join)

| De | Para | Via |
|---|---|---|
| `raw.mediasmart_delivery.eventid` | `core.platform_client_links.link_value` | `WHERE platform='mediasmart' AND link_type='eventid'` |
| `raw.mediasmart_delivery.controlid` | `raw.mediasmart_campaigns.id` | Join direto |
| `raw.mediasmart_delivery.strategyid` | `raw.mediasmart_revenue.strategyid` | Join por `day+strategyid` |
| `raw.mgid_delivery.campaignid` | `core.platform_client_links.link_value` | `WHERE platform='mgid' AND link_type='campaignid'` |
| `raw.mgid_delivery.campaignid` | `raw.mgid_campaigns.id` | Join direto |
| `raw.siprocal_delivery.advertiser` | `core.platform_client_links.link_value` | `WHERE platform='siprocal' AND link_type='advertiser'` |
| `gold.fact_delivery.platform_campaign_id` | `gold.dim_campaign.platform_campaign_id` | Join por `platform+platform_campaign_id` |
| `gold.fact_delivery.client_id` | `gold.dim_client.client_id` | FK direto |
| `gold.fact_delivery.client_id` | `gold.dim_conversion_mapping.client_id` | Para semantizar conversions_1..5 |

---

## 9. Campos Nulos e Limitações

### 9.1 Campos 100% nulos hoje (populam no próximo ETL run — 2026-06-04 03:20 UTC)

| Campo | Tabela | Motivo | Quando popula |
|---|---|---|---|
| `clientrevenue` | `raw.mediasmart_delivery` | Campo adicionado 2026-06-03, ETL ainda não rodou | Próximo ETL |
| `client_cost` | `raw.mediasmart_delivery` | Mesmo motivo | Próximo ETL |
| `convertedclientrevenue` | `raw.mediasmart_delivery` | Mesmo motivo | Próximo ETL |
| `eventid` | `raw.mediasmart_revenue` | Campo adicionado 2026-06-03 | Próximo ETL |
| `revenue_source` | `raw.mediasmart_revenue` | Campo adicionado 2026-06-03 | Próximo ETL |
| `conversion_source` | `raw.mediasmart_revenue` | Campo adicionado 2026-06-03 | Próximo ETL |
| `spent` | `raw.mgid_delivery` | Backfill histórico feito, mas ETL novo não rodou ainda | Próximo ETL |

### 9.2 Campos estruturalmente nulos (limitação da fonte)

| Campo | Tabela | Motivo permanente |
|---|---|---|
| `strategyid` | `raw.mediasmart_delivery` | 425.076 linhas (ago–dez/2025) sem strategyid — pipeline legado sem essa dimensão |
| `creative_type` | `raw.siprocal_delivery` | Planilha Siprocal não fornece esse campo |
| `conv_interest/decision/buy` | `raw.mgid_delivery` | API retorna 0 — produto sem conversões configuradas |
| `spend` | `gold.fact_delivery` (MGID) | `spent` no raw está vazio (preenche no próximo ETL) |
| `spend` | `gold.fact_delivery` (Siprocal) | Siprocal não tem dado de custo |
| `conversions_1..5` | `gold.fact_delivery` (MGID/Siprocal) | Somente MediaSmart tem essas métricas |
| `mgid_conv_*` | `gold.fact_delivery` (MS/Siprocal) | Somente MGID tem funil de conversão |

### 9.3 Gaps históricos de dados

| Lacuna | Impacto |
|---|---|
| MediaSmart spend (ago/2025–fev/2026) | 0 dados de custo para esse período — revenue só existe a partir de mar/2026 |
| MediaSmart delivery (mai/24–hoje) | Dado mais recente é 2026-05-24 — ETL com timeout |
| MGID spent histórico | `spent` adicionado em 2026-06-03 via backfill manual — valores históricos devem ser conferidos |
| MediaSmart strategyid 2025 | 425K linhas sem strategyid — impossível juntar com IO plan para esse período |

---

## 10. IDs e Chaves de Join

### 10.1 Identificadores por camada

| Conceito | RAW | STG | CORE | GOLD |
|---|---|---|---|---|
| Cliente | `eventid` (MS) / `campaignid` (MGID) / `advertiser` (Siprocal) | idem | `client_id` (dim_client) | `client_id` |
| Campanha/Estratégia | `strategyid` (MS) / `campaignid` (MGID) / `campaign_id` (Siprocal) | idem | `link_value` (pcl) | `platform_campaign_id` |
| Campanha pai MS | `controlid` | idem | — | — |
| Formato | — (não existe nas APIs) | — | `format` (campaign_format_map) | — (join necessário) |

### 10.2 Formato dos IDs

| Sistema | Formato | Exemplo |
|---|---|---|
| MediaSmart eventid | `{account}-{random32}` | `newad_brazil-dzynxhmnrdg2ec0czgdiabqmwvy0qhgj` |
| MediaSmart strategyid/controlid | `{random32}` | `xhhllbabxmo2qkxc9whasy8hhkyiezcz` |
| MGID campaignid | Numérico | `12326714` |
| MGID teaserid | Numérico | `1234567` |
| Siprocal campaign_id | Numérico pequeno ou string curta | `30`, `NW0825` |
| Siprocal advertiser | Nome em maiúsculas | `BANCOCORA`, `LUCKBET` |
| `dim_client.client_id` | `{slug}_{hash8}` | `banco_cora_fe13d78a` |
| `io_manager_v2.newad_client_id` (Shiro) | `nwd_{slug-com-hifens}_{hash8}` | `nwd_banco-cora_acfae3ab` |

> ⚠ **INCOMPATIBILIDADE:** `io_manager_v2.newad_client_id` e `dim_client.client_id` usam formatos diferentes — JOIN direto impossível.

---

## 11. Pendências e Itens Open

### 🔴 Crítico

| # | Pendência | Impacto |
|---|---|---|
| 1 | **MediaSmart ETL com Timeout** — job `mediasmart_daily_daily` falhando desde jun/26. Dados param em 2026-05-24 | Gold desatualizado em 10+ dias |
| 2 | **`gold.fact_io_plan` quebrada** — lê chain morta. Nenhum dado de IO plan disponível no gold | Sem análise previsto vs realizado |
| 3 | **`mediasmart_revenue_daily` stuck** — job aparece como `running` desde jun/01. Possível processo preso | Revenue pode não atualizar |

### 🟡 Importante

| # | Pendência | Impacto |
|---|---|---|
| 4 | **MGID spent não chega ainda** — params_json atualizado 2026-06-03. Próximo ETL popula, mas dados históricos (antes do backfill) sem spend no raw | MGID spend = 0 no gold até próximo ETL |
| 5 | **56 MGID links `pending_confirmation`** — vinculados mas não validados pelo AdOps | Atribuição correta mas governança pendente |
| 6 | **1 MediaSmart eventid `unresolved`** (`newad_brazil-neu83z5jjnkcnrbmwwxjsrzzfwaigdx7`) | 4.286.522 impressões sem cliente |
| 7 | **`dim_campaign` com 5 duplicatas** | Joins com dim_campaign retornam linhas duplicadas |
| 8 | **`clientrevenue`/`client_cost` em `raw.mediasmart_delivery`** — colunas criadas 2026-06-03, ainda vazias | Revenue por estratégia não disponível até próximo ETL |

### 🟢 Planejado

| # | Pendência |
|---|---|
| 9 | Google Ads API — integração pendente confirmação (dados Stocco/Cora) |
| 10 | `core.campaign_format_map` — expandir para todos os clientes além da Cora |
| 11 | MediaSmart backfill de strategyid 2025 — 425K linhas sem strategyid no raw (requer Shiro) |
| 12 | `gold.fact_io_plan` — reconectar para `core.io_manager_v2` (bloqueado pelo formato de client_id diferente) |
| 13 | `dim_conversion_mapping` — mapear Cora, Einstein, TecPar, demais clientes |
| 14 | Job `daily_creative` MediaSmart — para capturar `creativeid`, `creativetype`, `size` (requer Shiro) |
| 15 | Siprocal spend — verificar se planilha tem dado de custo (aguarda Shiro) |

---

## Datasets Vazios (candidatos a cleanup futuro)

| Dataset | Status |
|---|---|
| `marts` | Vazio — arquitetura V4 do Shiro, nunca populada no nosso pipeline |
| `share` | Vazio — idem |
| `raw_siprocal` | Vazio — remanescente de tentativa de reestruturação abr/2026 |

---

---

## 12. Schema Completo — Todas as Colunas de Cada Tabela/View

> Legenda: `PK` = chave primária | `FK` = chave estrangeira | `⚠` = campo com problema | `✗` = campo vazio/null estruturalmente

---

### RAW.MEDIASMART_DELIVERY — `641.798 rows` | TABLE | 2025-08-01→2026-05-24

| Coluna | Tipo BQ | Grain/Papel | Status |
|---|---|---|---|
| `day` | STRING | `YYYY-MM-DD` — partição temporal | OK |
| `eventid` | STRING | FK → `platform_client_links.link_value` (14 distintos) | OK |
| `controlid` | STRING | FK → `raw.mediasmart_campaigns.id` (campanha pai) | OK |
| `strategyid` | STRING | PK da estratégia — FK → `raw.mediasmart_revenue` | ⚠ 425.076 NULL (dados ago–dez/2025) |
| `strategyname` | STRING | Nome da estratégia — valores: "CPM", "CPC", "Strategy 1" (NÃO é o nome real) | OK |
| `conversion_source` | STRING | click, view, etc. | OK |
| `impressions` | STRING | Total: 352.532.729 | OK |
| `clicks` | STRING | Total: 944.690 | OK |
| `video_start` | STRING | Início de vídeo | OK |
| `video_25_viewed` | STRING | Primeiro quartil de vídeo | OK |
| `video_50_viewed` | STRING | Segundo quartil | OK |
| `video_75_viewed` | STRING | Terceiro quartil | OK |
| `video_completion` | STRING | Vídeo completo | OK |
| `conversions_1` | STRING | Semântica por cliente em `dim_conversion_mapping` | OK |
| `conversions_2` | STRING | idem | OK |
| `conversions_3` | STRING | idem | OK |
| `conversions_4` | STRING | idem | OK |
| `conversions_5` | STRING | idem | OK |
| `platform` | STRING | Sempre `mediasmart` | OK |
| `report_name` | STRING | Sempre `Daily` | OK |
| `raw_ingested_at` | TIMESTAMP | UTC, data da carga | OK |
| `clientrevenue` | STRING | Receita do cliente — **coluna adicionada 2026-06-03** | ✗ 100% NULL hoje |
| `convertedclientrevenue` | STRING | Receita convertida — **adicionada 2026-06-03** | ✗ 100% NULL hoje |
| `client_cost` | STRING | Custo do cliente — **adicionada 2026-06-03** | ✗ 100% NULL hoje |

---

### RAW.MEDIASMART_REVENUE — `9.247 rows` | TABLE | 2026-03-06→2026-05-16

| Coluna | Tipo BQ | Papel | Status |
|---|---|---|---|
| `day` | STRING | `YYYY-MM-DD` | OK |
| `controlid` | STRING | FK campanha pai | OK |
| `strategyid` | STRING | FK → delivery por strategyid+day | OK — 229 distintos |
| `revenuesource` | STRING | `event4` (R$11.7M), `event3` (R$996k), `1` (R$0) | OK |
| `clientrevenue` | STRING | Valor de receita — Total: **R$12.702.913** | OK |
| `platform` | STRING | Sempre `mediasmart` | OK |
| `report_name` | STRING | Sempre `DailyRevenue` | OK |
| `raw_ingested_at` | TIMESTAMP | UTC | OK |
| `eventid` | STRING | **Adicionado 2026-06-03** | ✗ 100% NULL hoje |
| `revenue_source` | STRING | **Adicionado 2026-06-03** (com underscore, diferente de `revenuesource`) | ✗ 100% NULL hoje |
| `conversion_source` | STRING | **Adicionado 2026-06-03** | ✗ 100% NULL hoje |

---

### RAW.MEDIASMART_CAMPAIGNS — `4.531 rows` | TABLE | Truncate diário

| Coluna | Tipo BQ | Papel |
|---|---|---|
| `id` | STRING | PK — FK para `delivery.controlid` (sem sufixo `r`) |
| `name` | STRING | Nome real da campanha — **contém o formato** (ex: `CORA_CONTADIGITAL_VIDEO_MAIO26`) |
| `type` | STRING | Sempre `generic` |
| `state` | STRING | Estado da campanha |
| `active` | STRING | Boolean como string |
| `goal` | STRING | Objetivo — sempre `{}` (vazio) |
| `strategies` | STRING | JSON serializado das estratégias |
| `creatives` | STRING | JSON serializado dos criativos |
| `schedule` | STRING | JSON de agendamento |
| `pricing` | STRING | JSON de precificação |
| `tags` | STRING | Tags |
| `description` | STRING | Descrição livre |
| `created_at` | STRING | Data de criação |
| `updated_at` | STRING | Data de atualização |
| `favorite` / `ms_version` / `color` / `search` / `hidden` / `pending_approval` / `session_data_enabled` / `deals_and_pricing` | STRING | Metadados internos MS |

---

### RAW.MEDIASMART_CREATIVES — `31.192 rows` | TABLE | Truncate semanal

| Coluna | Tipo BQ | Papel |
|---|---|---|
| `id` | STRING | PK do criativo |
| `campaign_id` | STRING | FK campanha ⚠ muitas linhas com NULL |
| `creative_id` | STRING | ID alternativo ⚠ muitas NULL |
| `type` | STRING | Tipo: `image`, `video`, `native`, etc. |
| `name` | STRING | Nome do criativo |
| `thumbnail_url` | STRING | URL miniatura |
| `image_url` | STRING | URL imagem |
| `created_at` | STRING | — |
| `updated_at` | STRING | — |
| `campaign` | STRING | JSON da campanha pai |
| `creative` | STRING | JSON completo do criativo |
| `description` | STRING | — |

---

### RAW.MEDIASMART_ADVERTISERS — `21 rows` | TABLE | Truncate semanal

| Coluna | Tipo BQ | Papel |
|---|---|---|
| `id` | STRING | PK do advertiser |
| `event_id` | STRING | Equivalente ao `eventid` na delivery |
| `name` | STRING | Nome do advertiser |
| `domain` | STRING | Domínio |
| `iab_category` | STRING | Categoria IAB |
| `sensitive_content` | STRING | Flag conteúdo sensível |

---

### RAW.MEDIASMART_BID_SUPPLY — `602.179 rows` | TABLE | Job INATIVO desde mar/2026

| Coluna | Tipo BQ | Papel |
|---|---|---|
| `day` / `hour` | STRING | Período horário |
| `eventid` / `controlid` / `strategyid` | STRING | IDs da hierarquia |
| `auction_type` | STRING | Tipo de leilão |
| `ad_exchange` | STRING | Exchange (Google, OpenX, etc.) |
| `publisher_id` / `publisher_name` / `publisher_domain` / `publisher_url` | STRING | Publisher |
| `iab_category` / `iab_subcategory` | STRING | Categoria IAB |
| `bid_offers` / `bids` / `won` | STRING | Lances |
| `media_cost` / `total_bids_cost` | STRING | Custos |
| `impressions` / `clicks` / `conversions_1..5` | STRING | Métricas |
| `platform` / `report_name` / `raw_ingested_at` | STRING/TIMESTAMP | Metadados |

> ✗ **Não alimenta o pipeline gold.** `stg.mediasmart_bid_supply` existe mas não é consumida pelo gold.

---

### RAW.MEDIASMART_DAILY — `75 rows` | TABLE | Staging interno do ETL

> Tabela intermediária do job `mediasmart_daily_daily`. **NÃO dropar.** Tem schema mais rico que o destino.

| Coluna extra vs raw.mediasmart_delivery | Tipo | Observação |
|---|---|---|
| `creative_type` | STRING | Bloqueado no handler daily — sempre NULL |
| `creative_id` | STRING | Bloqueado — sempre NULL |
| `id_type` | STRING | Tipo de ID |
| `mediasmart_id` | STRING | ID interno MS |
| `nativesize` | STRING | Tamanho nativo |
| `size` | STRING | Tamanho do anúncio |
| `client_currency` | STRING | Moeda |

---

### RAW.MEDIASMART_REVENUE_DAILY — `267 rows` | TABLE | Staging interno do ETL revenue

> Staging temporário do job `mediasmart_revenue_daily`. **NÃO dropar.** Schema mais granular que o destino.

Colunas: `day`, `controlid`, `eventid`, `strategyid`, `revenue_source`, `conversion_source`, `clientrevenue`, `platform`, `report_name`, `raw_ingested_at`

---

### RAW.MGID_DELIVERY — `3.491 rows` | TABLE | 2025-09-30→2026-05-25

| Coluna | Tipo BQ | Papel | Status |
|---|---|---|---|
| `day` | STRING | `YYYY-MM-DD` | OK |
| `campaignid` | STRING | PK+FK — 95 campanhas distintas | OK |
| `teaserid` | STRING | ID do teaser/criativo — 167 distintos | OK |
| `impressions` | STRING | Total: 61.831.674 | OK |
| `clicks` | STRING | Total: 333.116 | OK |
| `conversionsinterest` | STRING | Funil: interesse — Total: 0 | OK (sem dados) |
| `conversionsdecision` | STRING | Funil: decisão — Total: 0 | OK (sem dados) |
| `conversionsbuy` | STRING | Funil: compra — Total: 0 | OK (sem dados) |
| `platform` | STRING | Sempre `mgid` | OK |
| `report_name` | STRING | Sempre `Daily` | OK |
| `raw_ingested_at` | TIMESTAMP | UTC | OK |
| `spent` | STRING | Custo em BRL — formato `{'amount': '54.4', 'currency': 'BRL'}` achatado para `amount` | ✗ 100% NULL hoje (ETL atualizado 2026-06-03, popula no próximo run) |

---

### RAW.MGID_CAMPAIGNS — `18.420 rows` | TABLE | Truncate diário

| Coluna | Tipo BQ | Papel |
|---|---|---|
| `id` | STRING | PK — FK para `delivery.campaignid` |
| `name` | STRING | Nome da campanha — **contém cliente e formato** (ex: `Banco Cora \| NewAd \| Native \| 01/01-31/01`) |
| `status` | STRING | JSON com `id`, `name`, `reason` |
| `language` | STRING | Idioma |
| `startDate` / `endDate` | STRING | Período |
| `campaignType` | STRING | Tipo |
| `category` | STRING | Categoria |
| `targets` | STRING | JSON de segmentação |
| `statistics` | STRING | JSON de estatísticas |
| `domainsFilter` / `ipsFilter` / `widgetsFilterUid` | STRING | Filtros |
| `limitsFilter` / `trackingOptions` / `languageTargeting` / `browserTargeting` | STRING | Config |
| `whenAdd` / `sourcesOptimization` / `sourceFilters` | STRING | Metadados |

---

### RAW.MGID_CREATIVES — `10.228 rows` | TABLE | Truncate semanal

| Coluna | Tipo BQ | Papel |
|---|---|---|
| `id` | STRING | PK do teaser/criativo |
| `campaignId` | STRING | FK → `raw.mgid_campaigns.id` |
| `title` | STRING | Título do anúncio |
| `advertText` | STRING | Texto do anúncio |
| `url` | STRING | URL de destino |
| `imageLink` | STRING | URL da imagem |
| `ad_type` | STRING | Tipo: native, push, etc. |
| `goodPrice` / `goodOldPrice` | STRING | Preços |
| `currency` | STRING | Moeda |
| `category` | STRING | Categoria |
| `callToAction` | STRING | CTA |
| `status` | STRING | Status do criativo |
| `who_add` | STRING | Quem criou |
| `previewLinks` / `cropLeft` / `cropTop` / `cropWidth` | STRING | Metadados visuais |
| `priceOfClickByLocations` / `conversion` / `blocked_by` / `statistics` | STRING | Dados operacionais |

---

### RAW.MGID_DAILY — `28 rows` | TABLE | Staging interno do ETL

> Staging temporário do job `mgid_daily_daily`. **NÃO dropar.** Schema idêntico ao `raw.mgid_delivery` (sem `spent`).

---

### RAW.SIPROCAL_DELIVERY — `1.021 rows` | TABLE | 2025-08-22→2026-05-26

| Coluna | Tipo BQ | Papel | Status |
|---|---|---|---|
| `day` | STRING | Pode ser `dd/mm/yyyy` ou `yyyy-mm-dd` — normalizado na STG | OK |
| `advertiser` | STRING | Nome do anunciante — FK via `platform_client_links` — 33 distintos | OK |
| `campaign_id` | STRING | ID numérico da campanha (ex: `30`, `38`) ou string (`NW0825`) | OK — 25 distintos |
| `creative_type` | STRING | Tipo de criativo | ✗ 100% NULL (planilha não fornece) |
| `creative` | STRING | Nome do criativo | OK (alguns NULL) |
| `impressions` | STRING | Total: 6.932.031 | OK |
| `clicks` | STRING | Total: 114.056 | OK |
| `platform` | STRING | Sempre `siprocal` | OK |
| `report_name` | STRING | Sempre `Daily` | OK |
| `raw_ingested_at` | TIMESTAMP | UTC | OK |

---

### RAW.SIPROCAL_RAW_SHEET — `0 rows visíveis` | EXTERNAL | Pointer para Google Sheet

| Coluna | Tipo BQ | Papel |
|---|---|---|
| `day` | STRING | Data na planilha |
| `advertiser` | STRING | Nome do anunciante |
| `campaign_id` | STRING | ID |
| `creative_type` | STRING | Tipo (geralmente vazio na planilha) |
| `creative` | STRING | Nome do criativo |
| `impressions` | STRING | — |
| `clicks` | STRING | — |
| `ctr` | STRING | CTR calculado na planilha |

> Fonte: `https://docs.google.com/spreadsheets/d/1HaGrxaU-nt3fvqxaJ1CSlABYJGNY28rhQC49dcGzLWs` / Planilha1

---

### STG.MEDIASMART_DELIVERY — VIEW sobre `raw.mediasmart_delivery`

| Coluna | Tipo STG | Transformação vs RAW |
|---|---|---|
| `day` | DATE | `SAFE_CAST(day AS DATE)` — filtra `WHERE day IS NOT NULL` |
| `eventid` | STRING | pass-through |
| `controlid` | STRING | pass-through |
| `strategyid` | STRING | pass-through |
| `strategyname` | STRING | pass-through |
| `conversion_source` | STRING | pass-through |
| `impressions` | INT64 | `SAFE_CAST(impressions AS INT64)` |
| `clicks` | INT64 | `SAFE_CAST(clicks AS INT64)` |
| `video_start` | INT64 | `SAFE_CAST` |
| `video_25_viewed` | INT64 | `SAFE_CAST` |
| `video_50_viewed` | INT64 | `SAFE_CAST` |
| `video_75_viewed` | INT64 | `SAFE_CAST` |
| `video_completion` | INT64 | `SAFE_CAST` |
| `conversions_1..5` | INT64 | `SAFE_CAST` |
| `platform` / `report_name` / `raw_ingested_at` | STRING/TIMESTAMP | pass-through |
| `clientrevenue` | FLOAT64 | `SAFE_CAST` — ✗ NULL hoje |
| `convertedclientrevenue` | FLOAT64 | `SAFE_CAST` — ✗ NULL hoje |
| `client_cost` | FLOAT64 | `SAFE_CAST` — ✗ NULL hoje |

> **Colunas ausentes na STG vs RAW:** nenhuma — todos os campos passam.

---

### STG.MEDIASMART_REVENUE — VIEW sobre `raw.mediasmart_revenue`

| Coluna | Tipo STG | Transformação |
|---|---|---|
| `day` | DATE | `SAFE_CAST` + `WHERE day IS NOT NULL` |
| `controlid` | STRING | pass-through |
| `strategyid` | STRING | pass-through |
| `revenuesource` | STRING | pass-through |
| `clientrevenue` | FLOAT64 | `SAFE_CAST(clientrevenue AS FLOAT64)` |
| `platform` / `report_name` / `raw_ingested_at` | STRING/TIMESTAMP | pass-through |

> **Colunas não incluídas:** `eventid`, `revenue_source`, `conversion_source` — existem no RAW mas não na STG ainda (precisam ser adicionadas).

---

### STG.MGID_DELIVERY — VIEW sobre `raw.mgid_delivery`

| Coluna | Tipo STG | Transformação |
|---|---|---|
| `day` | DATE | `SAFE_CAST` + `WHERE day IS NOT NULL` |
| `campaignid` | STRING | pass-through |
| `teaserid` | STRING | pass-through |
| `impressions` | INT64 | `SAFE_CAST` |
| `clicks` | INT64 | `SAFE_CAST` |
| `conversionsinterest` | INT64 | `SAFE_CAST` |
| `conversionsdecision` | INT64 | `SAFE_CAST` |
| `conversionsbuy` | INT64 | `SAFE_CAST` |
| `spent` | FLOAT64 | `SAFE_CAST(spent AS FLOAT64)` — ✗ NULL hoje |
| `platform` / `report_name` / `raw_ingested_at` | STRING/TIMESTAMP | pass-through |

---

### STG.SIPROCAL_DELIVERY — VIEW sobre `raw.siprocal_delivery`

| Coluna | Tipo STG | Transformação |
|---|---|---|
| `day` | DATE | Normalização: `dd/mm/yyyy` → `PARSE_DATE` OU `SAFE_CAST` |
| `advertiser` | STRING | **Calculado:** `COALESCE(REGEXP_EXTRACT(UPPER(TRIM(advertiser)), r'^NEWAD_(.+)_BR_\w+$'), UPPER(TRIM(advertiser)))` — extrai nome limpo |
| `campaign_name` | STRING | `advertiser` original (raw) — nome bruto para referência |
| `campaign_id` | STRING | pass-through |
| `creative_type` | STRING | pass-through — ✗ sempre NULL |
| `creative` | STRING | pass-through |
| `impressions` | INT64 | `SAFE_CAST` |
| `clicks` | INT64 | `SAFE_CAST` |
| `platform` / `report_name` / `raw_ingested_at` | STRING/TIMESTAMP | pass-through |

> `ctr` da planilha: **não incluído** na STG — campo descartado.

---

### STG.MEDIASMART_BID_SUPPLY — VIEW sobre `raw.mediasmart_bid_supply`

> Funcional mas **órfã no gold** — não alimenta nenhuma tabela GOLD. Disponível para análise ad-hoc de inventário.

Todas as colunas do raw são tipadas (STRING → tipos nativos). Ver schema completo em `raw.mediasmart_bid_supply`.

---

### CORE.DIM_CLIENT — `26 rows` | TABLE | PK: `client_id`

| Coluna | Tipo | FK/Papel |
|---|---|---|
| `client_id` | STRING | **PK** — formato `{slug}_{hash8}` ex: `banco_cora_fe13d78a` |
| `slug` | STRING | URL-friendly |
| `name` | STRING | Nome comercial |
| `sector` | STRING | Setor |
| `status` | STRING | `active` (todos os 26) |
| `created_at` | DATE | — |
| `deactivated_at` | DATE | NULL para todos |
| `notes` | STRING | Livre |
| `seed_loaded_at` | TIMESTAMP | Data carga inicial |
| `parent_client_id` | STRING | **FK → si mesmo** — 6 clientes com parent (nível 2) |
| `client_level` | INT64 | `1` = raiz (20), `2` = filho (6) |
| `newad_account_id` | STRING | ID interno NewAD |

---

### CORE.PLATFORM_CLIENT_LINKS — `149 rows` | TABLE | PK: `platform+link_type+link_value`

| Coluna | Tipo | Papel |
|---|---|---|
| `platform` | STRING | `mediasmart`, `mgid`, `siprocal` |
| `link_type` | STRING | `eventid` (MS), `campaignid` (MGID), `advertiser` (Siprocal) |
| `link_value` | STRING | Valor do identificador na plataforma |
| `client_id` | STRING | **FK → `core.dim_client.client_id`** — 1 NULL (unresolved) |
| `status` | STRING | `active` (88), `pending_confirmation` (60), `unresolved` (1) |
| `notes` | STRING | — |
| `created_at` | DATE | — |

---

### CORE.CAMPAIGN_FORMAT_MAP — `18 rows` | TABLE | PK: `platform+platform_campaign_id` | NOVO 2026-06-03

| Coluna | Tipo | Papel |
|---|---|---|
| `platform` | STRING | `mediasmart`, `mgid`, `siprocal`, `google_ads` (futuro) |
| `platform_campaign_id` | STRING | **PK** — ID da campanha/estratégia |
| `client_id` | STRING | FK → `core.dim_client` |
| `format` | STRING | `Display`, `Native`, `Push`, `Retargeting`, `Video`, `Outros` |
| `source` | STRING | `campaign_name` (nome da campanha), `manual`, `io_plan` |
| `notes` | STRING | Nome original da campanha que gerou a classificação |
| `created_at` | TIMESTAMP | — |
| `updated_at` | TIMESTAMP | — |

---

### GOLD.FACT_DELIVERY — `13.874 rows` | TABLE | PK: `day+client_id+platform+platform_campaign_id`

| Coluna | Tipo | Origem | Por Plataforma | Status |
|---|---|---|---|---|
| `day` | DATE | STG | Todas | Partição |
| `client_id` | STRING | `core.platform_client_links` | Todas | `'unattributed'` se sem match (116 linhas) |
| `platform` | STRING | Literal | Todas | `mediasmart`, `mgid`, `siprocal` |
| `platform_campaign_id` | STRING | `strategyid`/`campaignid`/`campaign_id` | Todas | FK → `gold.dim_campaign` |
| `impressions` | INT64 | `SUM(stg.impressions)` | Todas | OK — 421.296.434 total |
| `clicks` | INT64 | `SUM(stg.clicks)` | Todas | OK — 1.391.862 total |
| `spend` | FLOAT64 | MS: `stg.mediasmart_revenue` / MGID: `stg.mgid_delivery.spent` | MS=R$12.7M / MGID=R$0 / Siprocal=NULL | MGID null hoje |
| `conversions_1` | INT64 | `SUM(stg.conversions_1)` | **Somente MediaSmart** | NULL para MGID/Siprocal |
| `conversions_2` | INT64 | idem | **Somente MediaSmart** | NULL para MGID/Siprocal |
| `conversions_3` | INT64 | idem | **Somente MediaSmart** | NULL para MGID/Siprocal |
| `conversions_4` | INT64 | idem | **Somente MediaSmart** | NULL para MGID/Siprocal |
| `conversions_5` | INT64 | idem | **Somente MediaSmart** | NULL para MGID/Siprocal |
| `mgid_conv_interest` | INT64 | `SUM(stg.conversionsinterest)` | **Somente MGID** | NULL para MS/Siprocal, 0 para MGID |
| `mgid_conv_decision` | INT64 | `SUM(stg.conversionsdecision)` | **Somente MGID** | idem |
| `mgid_conv_buy` | INT64 | `SUM(stg.conversionsbuy)` | **Somente MGID** | idem |

---

### GOLD.DIM_CLIENT — VIEW sobre `core.dim_client` (self-join para parent)

| Coluna | Tipo | Origem |
|---|---|---|
| `client_id` | STRING | `core.dim_client.client_id` |
| `slug` | STRING | — |
| `name` | STRING | — |
| `sector` | STRING | — |
| `status` | STRING | — |
| `created_at` | DATE | — |
| `deactivated_at` | DATE | — |
| `notes` | STRING | — |
| `parent_client_id` | STRING | FK para si mesmo |
| `client_level` | INT64 | 1 ou 2 |
| `newad_account_id` | STRING | — |
| `parent_name` | STRING | **Calculado** via self-join `WHERE parent_client_id = client_id` |
| `parent_slug` | STRING | **Calculado** idem |

---

### GOLD.DIM_CAMPAIGN — `465 rows` | TABLE | ⚠ 5 duplicatas

| Coluna | Tipo | Papel |
|---|---|---|
| `platform` | STRING | `mediasmart`, `mgid` |
| `platform_campaign_id` | STRING | **PK** (com duplicatas!) |
| `platform_campaign_name` | STRING | Nome real da campanha (de `raw.mediasmart_campaigns.name` ou `raw.mgid_campaigns.name`) |
| `platform_advertiser_id` | STRING | ID do advertiser |
| `client_id` | STRING | FK → `core.dim_client` |

> ⚠ **5 platform_campaign_ids duplicados** — causa multiplicação em queries que fazem JOIN com dim_campaign sem DISTINCT/QUALIFY.

---

### GOLD.DIM_CONVERSION_MAPPING — `5 rows` | TABLE

| Coluna | Tipo | Papel |
|---|---|---|
| `client_id` | STRING | FK → `core.dim_client` — NULL = global (todos os clientes) |
| `platform` | STRING | NULL = todas as plataformas |
| `conversion_slot` | STRING | `conversions_1` a `conversions_5` |
| `conversion_name` | STRING | Nome da conversão (ex: `FTD`, `Pageview`) |
| `conversion_description` | STRING | Descrição detalhada |
| `is_primary` | BOOLEAN | Se é a conversão principal |
| `created_at` | DATE | — |

**Registros atuais:**
- `NULL` / `conversions_1` / `Pageview` (global)
- `luckbet_bea15ebc` / `conversions_2` / `Cadastro`
- `luckbet_bea15ebc` / `conversions_3` / `FTD`
- `luckbet_bea15ebc` / `conversions_4` / `Depósito Recorrente`
- `luckbet_bea15ebc` / `conversions_5` / `Início Cadastro`

---

### GOLD.FACT_IO_PLAN — ✗ QUEBRADA — `0 rows` | VIEW

| Coluna | Tipo | Papel |
|---|---|---|
| `id` | STRING | ID do IO plan |
| `cliente` | STRING | Nome do cliente (em português — campo legado) |
| `plataforma` | STRING | Plataforma |
| `estrategia` | STRING | Nome da estratégia |
| `formato` | STRING | Formato (Display, Native, etc.) |
| `device` | STRING | Dispositivo |
| `modelo_compra` | STRING | CPM, CPC, CPV |
| `tipo_entrega` | STRING | Tipo de entrega |
| `inicio_previsto` | DATE | Data início planejada |
| `fim_previsto` | DATE | Data fim planejada |
| `dias_campanha` | INT64 | Duração em dias |
| `investimento_previsto_usd` | FLOAT64 | Budget planejado em USD |
| `investimento_diario_usd` | FLOAT64 | Budget diário |
| `valor_unit_usd` | FLOAT64 | Taxa (CPM ou CPC) em USD |
| `volume_previsto` | FLOAT64 | Volume (impressões ou cliques) planejado |
| `volume_diario` | FLOAT64 | Volume diário |
| `impressoes_previstas` | FLOAT64 | Impressões planejadas |
| `cliques_previstos` | FLOAT64 | Cliques planejados |
| `video_views_previstos` | FLOAT64 | Views de vídeo planejadas |
| `video_completed_views_previstos` | FLOAT64 | Views completas planejadas |
| `alcance_previsto` | FLOAT64 | Alcance planejado |
| `id_campanha` | STRING | FK → `gold.fact_delivery.platform_campaign_id` |

> **Status:** VIEW lê `stg.luckbet_io_plan` → `raw.luckbet_io_plan_snapshot` (DROPADO). Retorna 0 rows.  
> **Correção necessária:** Reconectar para `core.io_manager_v2` (bloqueado pelo formato incompatível de client_id).

---

*Documento gerado em 2026-06-03. Para atualizar executar os scripts em `C:\Temp\collect_details.py`.*  
*Próxima revisão recomendada: após próximo ciclo completo de ETL (2026-06-04 manhã).*
