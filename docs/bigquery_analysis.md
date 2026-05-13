# AdFramework — Análise Completa BigQuery + GitHub
> Auditoria profunda: redundâncias, duplicatas, linhagem, custos e proposta de otimização
> Atualizado: 2026-04-30 | Projeto GCP: `adframework` (striped-bonfire-489318)

---

## Sumário

1. [Inventário Completo — Todos os 14 Datasets](#1-inventário-completo--todos-os-14-datasets)
2. [Diagnóstico de Duplicação — raw vs raw_*](#2-diagnóstico-de-duplicação--raw-vs-raw_)
3. [Mapa de Linhagem de Dados](#3-mapa-de-linhagem-de-dados)
4. [Redundâncias e Objetos Obsoletos](#4-redundâncias-e-objetos-obsoletos)
5. [Objetos Quebrados](#5-objetos-quebrados)
6. [Análise por Dataset](#6-análise-por-dataset)
7. [Análise do Código Python (GitHub)](#7-análise-do-código-python-github)
8. [Análise do Admin UI](#8-análise-do-admin-ui)
9. [Mapa de Custos de Storage](#9-mapa-de-custos-de-storage)
10. [Proposta de Limpeza — 3 Fases](#10-proposta-de-limpeza--3-fases)
11. [Decisão Arquitetural: Manter raw vs Migrar para raw_*](#11-decisão-arquitetural-manter-raw-vs-migrar-para-raw_)
12. [Plano de Execução](#12-plano-de-execução)

---

## 1. Inventário Completo — Todos os 14 Datasets

### Visão Geral por Dataset (estado 2026-04-30)

| Dataset | Tabelas | Views | Size (MB) | Última Escrita | Status |
|---------|---------|-------|-----------|----------------|--------|
| `raw` | 20 | 0 | **752 MB** | 2026-04-30 | ✅ Ativo — ETL escreve aqui |
| `raw_mediasmart` | 11 | 0 | **710 MB** | 2026-04-21 | 🔴 Snapshot órfão — ETL não atualiza |
| `raw_mgid` | 6 | 0 | **37 MB** | 2026-04-21 | 🔴 Snapshot órfão — ETL não atualiza |
| `raw_siprocal` | 3 | 0 | **0.1 MB** | 2026-04-21 | 🔴 Snapshot órfão |
| `raw_newadframework` | 5 | 0 | **0 MB** | 2026-04-21 | 🔴 VAZIO — reestruturação não concluída |
| `stg` | 0 | 14 | 0 MB | — | ✅ Ativo (views) |
| `core` | 7 | 6 | **0.3 MB** | 2026-04-30 | ✅ Ativo (ETL + Admin UI) |
| `marts` | 4 mat. | 14 | 0 MB | — | ⚠️ Mat. vazias, views ativas |
| `share` | 2 | 65 | **~0 MB** | — | ⚠️ Maioria legado |
| `gold` | 8 | 0 | **9 MB** | 2026-04-29 | ✅ MVP ativo — Power BI |
| `pixel` | 7 | 10 | **0.3 MB** | — | ✅ MVP (volume baixo) |
| `adtracking` | 6 | 1 | **6.2 MB** | — | ⚠️ Atribuição vazia |
| `analytics` | 5 | 0 | **0 MB** | 2026-03-25 | 🔴 VAZIO — schema futuro nunca usado |
| `finops_billing` | 3 | 6 | **1.061 MB** | 2026-04-30 | ✅ Legítimo — billing GCP ativo |
| **TOTAL** | **97** | **116** | **~2.576 MB** | | |

---

## 2. Diagnóstico de Duplicação — raw vs raw_*

### O que são os datasets raw_* ?

Os 4 novos datasets foram criados em **2026-04-21** como início de uma reestruturação de separação de plataformas. A intenção era ter `raw_mediasmart`, `raw_mgid`, `raw_siprocal` e `raw_newadframework` como datasets isolados por plataforma. Porém:

- **O ETL Python não foi atualizado** — continua escrevendo em `raw.*`
- **As stg views não foram atualizadas** — continuam lendo de `raw.*`
- Os novos datasets são **snapshots congelados de 2026-04-19**

### Comparação detalhada raw vs raw_mediasmart

| Tabela | raw (atual) | raw_mediasmart (congelado) | Diferença |
|--------|------------|--------------------------|-----------|
| `mediasmart_daily` | 638.685 linhas | 637.790 linhas | +895 (raw está atualizado) |
| `mediasmart_daily` max_day | **2026-04-29** | 2026-04-19 | 10 dias atrasado |
| `mediasmart_bid_supply_daily` | 602.179 | 602.179 | IDÊNTICO |
| `mediasmart_creatives` | 20.353 | 16.149 | +4.204 (raw mais atualizado) |
| `mediasmart_campaigns` | 2.016 | 1.848 | +168 |
| `mediasmart_revenue_daily` | 8.075 | 7.755 | +320 |
| `mediasmart_advertisers` | 704 | 662 | +42 |
| `mediasmart_daily_legacy_*` | ✅ PRESENTE (3 tabelas, ~400 MB) | ✅ PRESENTE (3 tabelas, ~400 MB) | **DUPLICADO — 800 MB no total** |

### Comparação raw vs raw_mgid

| Tabela | raw (atual) | raw_mgid (congelado) | Diferença |
|--------|------------|---------------------|-----------|
| `mgid_daily` | 4.098 linhas | 4.056 linhas | +42 (raw atualizado) |
| `mgid_daily` max_day | **2026-04-29** | 2026-04-19 | 10 dias atrasado |
| `mgid_campaigns` | 12.907 | 11.613 | +1.294 |
| `mgid_creatives` | 9.314 | 9.006 | +308 |
| `mgid_daily_legacy_*` | ✅ PRESENTE (2 tabelas, ~0.4 MB) | ✅ PRESENTE (2 tabelas, ~0.4 MB) | **DUPLICADO** |
| `mgid_daily_device` | 803 | 803 | IDÊNTICO |

### raw_siprocal vs raw

| Tabela | raw | raw_siprocal | Situação |
|--------|-----|-------------|----------|
| `siprocal_daily_materialized` | 706 linhas | 706 linhas | IDÊNTICO |
| `siprocal_daily_native` | 706 linhas | 706 linhas | IDÊNTICO |
| `siprocal_daily_view` | não existe | 0 linhas | NOVA — vazia |

### raw_newadframework vs core

| Tabela | core (ativo) | raw_newadframework | Situação |
|--------|-------------|-------------------|----------|
| `io_manager_v2` | 229 linhas | **0 linhas** | VAZIO — cópia nunca sincronizada |
| `io_line_bindings_v2` | 170 linhas | **0 linhas** | VAZIO |
| `platform_client_links` | 27 linhas | **0 linhas** | VAZIO |
| `proposal_lines` | 0 linhas | **0 linhas** | VAZIO (ambos) |
| `proposals` | 0 linhas | **0 linhas** | VAZIO (ambos) |

**Conclusão crítica:** `raw_newadframework` foi criado para ser o novo home dos dados de IO/core, mas nunca foi populado. O Admin UI e o ETL continuam escrevendo em `core.*`.

### Impacto Total da Duplicação

| Origem | Tamanho Duplicado | Observação |
|--------|------------------|-----------|
| raw_mediasmart (dados principais) | ~307 MB | Cópia de raw de 2026-04-19 |
| raw_mediasmart (backups legacy) | ~400 MB | **Os mesmos backups que já existem em raw!** |
| raw_mgid | ~37 MB | Cópia de raw de 2026-04-19 |
| raw_siprocal | ~0.1 MB | Cópia idêntica de raw |
| raw_newadframework | 0 MB | Vazio (schema sem dados) |
| **Total duplicado** | **~744 MB** | |

Somando com os backups originais em `raw` (~400 MB): **~1,144 MB de dados desnecessários**.

---

## 3. Mapa de Linhagem de Dados

### Pipeline ATIVO (v4 — escreve para Gold)

```
╔══════════════════════════════════════════════════════════════╗
║  INGESTÃO (ETL Python / Cloud Run / Cloud Scheduler)         ║
╚══════════════════════════════════════════════════════════════╝
   orchestrator.py → raw.mediasmart_daily    (diário, 08:00 BRT)
   orchestrator.py → raw.mgid_daily          (diário, 08:00 BRT)
   orchestrator.py → raw.mediasmart_creatives, campaigns, etc.
   MANUAL          → raw.siprocal_daily_materialized (PARADO EM mar/2026)

         ▼ (stg views — transformação)

   stg.mediasmart_daily_std  ←── raw.mediasmart_daily
   stg.mgid_daily_std        ←── raw.mgid_daily
   stg.mediasmart_revenue_daily ←── raw.mediasmart_revenue_daily
   stg.io_lines_v4           ←── core.io_registry_v4
                                       ↑
                              core.io_manager_v2 (Admin UI → Firestore → BQ)
                              core.io_line_bindings_v2

         ▼ (marts views — joins e cálculos)

   marts.io_delivery_daily_v4  ←── stg.*_daily_std + core.io_line_bindings_v2
   marts.io_schedule_daily_v4  ←── stg.io_lines_v4 (UNNEST date array)

         ▼ (gold — star schema físico para Power BI)

   gold.fct_delivery_daily   ←── marts.io_delivery_daily_v4 + stg.io_lines_v4
                                  + stg.newad_revenue_daily
   gold.fct_io_plan_daily    ←── marts.io_schedule_daily_v4
   gold.fct_luckbet_daily    ←── share.luckbet_sheet_strategy_daily + gold.dim_io_line
   gold.dim_io_line          ←── stg.io_lines_v4
   gold.dim_creative         ←── raw.mediasmart_creatives + raw.mgid_creatives
   gold.dim_client           ←── core.io_line_bindings_v2
   gold.dim_date             ←── GENERATE_DATE_ARRAY (estática)
   gold.dim_platform         ←── estática (3 linhas)
```

### Pipeline LEGADO (via Google Sheets External — NÃO usar)

```
   core.io_manager [EXTERNAL TABLE → Google Sheets]
         ▼
   core.io_manager_enriched  ←── core.io_manager [EXTERNAL]
         ▼
   marts.fact_daily_detail   ←── stg.*_daily_std + io_manager_enriched
   marts.fact_daily_io       ←── marts.fact_daily_detail
         ▼
   share.report_daily_detail
   share.report_daily_campaign  (+ 40+ share views encadeadas)
   share.pacing_daily
   share.kpi_daily  ←── QUEBRADO (lê marts.kpi_daily que lê view inexistente)
```

### Datasets raw_* — Pipeline INEXISTENTE (orphans)

```
   raw_mediasmart.*   ←── snapshot de 2026-04-21 (ETL NÃO ESCREVE AQUI)
   raw_mgid.*         ←── snapshot de 2026-04-21 (ETL NÃO ESCREVE AQUI)
   raw_siprocal.*     ←── snapshot de 2026-04-21 (ETL NÃO ESCREVE AQUI)
   raw_newadframework.* ←── VAZIO (Admin UI NÃO ESCREVE AQUI)
   analytics.*        ←── VAZIO (nenhum pipeline popula)
```

---

## 4. Redundâncias e Objetos Obsoletos

### 4.1 Backups de Fevereiro/2026 — Triplicados!

Os backups gerados em 27/02/2026 durante uma migração de schema existem em:

| Tabela | raw | raw_mediasmart | Total Cópias |
|--------|-----|----------------|-------------|
| `mediasmart_daily_legacy_20260227_065635` (139.9 MB) | ✅ | ✅ | **2x = 279.8 MB** |
| `mediasmart_daily_backup_20260227_111821` (130.3 MB) | ✅ | ✅ | **2x = 260.6 MB** |
| `mediasmart_daily_legacy_20260227_061441` (129.6 MB) | ✅ | ✅ | **2x = 259.2 MB** |
| `mgid_daily_legacy_20260227_061627` (0.2 MB) | ✅ | ✅ (raw_mgid) | **2x = 0.4 MB** |
| `mgid_daily_legacy_20260227_065913` (0.2 MB) | ✅ | ✅ (raw_mgid) | **2x = 0.4 MB** |
| **TOTAL backups** | **~400 MB** | **~400 MB** | **~800 MB** |

**Os dados desses backups já estão em `raw.mediasmart_daily` e `raw.mgid_daily` atuais.**
Período coberto pelos backups: 2025-08-01 a 2026-02-27 — presente em ambas as tabelas ativas.

### 4.2 Datasets raw_* inteiros — Dados Duplicados Congelados

```
raw_mediasmart.*  ≈ raw.mediasmart_* (snapshot 2026-04-19, 10 dias atrasado)
raw_mgid.*        ≈ raw.mgid_* (snapshot 2026-04-19, 10 dias atrasado)
raw_siprocal.*    ≈ raw.siprocal_* (idêntico)
```

**Nenhum processo lê desses datasets** — stg/marts/gold todos apontam para `raw.*`.

### 4.3 Versões Paralelas de Views (cadeias v2/v3)

| Cadeia | Objetos redundantes | Onde está |
|--------|--------------------|---------| 
| `io_kpis_daily` | v2 + v3 em marts + v2 + v3 em share + mat vazia | marts + share |
| `io_line_kpis_daily` | v2 + v3 em marts + v2 + v3 em share + mat vazia | marts + share |
| `io_line_actual_daily` | v2 + v3 em marts + v3 em share | marts + share |
| `io_line_plan_daily` | v2 + v3 em marts + v3 em share | marts + share |
| `io_kpis_daily_by_model` | v2 + v3 em marts + v2 + v3 share + mat vazia | marts + share |
| `report_daily` | detail + campaign + by_source + device + format + creative + grouped | share |
| `roas` | 7 objetos (roas_campaign/io/line/pivot/reconciled/unmatched + io_roas_daily) + 1 mat | share+marts |
| `pacing` | pacing_daily + pacing_cards + pacing_daily_cpc/cpm/by_source | share |

**Total:** ~35 views/tabelas redundantes na cadeia legada.

### 4.4 Tabelas Físicas Vazias Confirmadas

| Dataset | Tabela | Linhas | Criada em | Ação |
|---------|--------|--------|-----------|------|
| `raw` | `mediasmart_daily_creative` | 0 | 2026-03-13 | 🗑️ Deletar |
| `raw` | `mediasmart_daily_operational` | 0 | 2026-03-13 | 🗑️ Deletar |
| `raw_mediasmart` | `mediasmart_daily_creative` | 0 | 2026-04-21 | 🗑️ Deletar (junto com dataset) |
| `raw_mediasmart` | `mediasmart_daily_operational` | 0 | 2026-04-21 | 🗑️ Deletar (junto com dataset) |
| `raw_newadframework` | `io_manager_v2` | 0 | 2026-04-21 | 🗑️ Deletar dataset |
| `raw_newadframework` | `io_line_bindings_v2` | 0 | 2026-04-21 | 🗑️ Deletar dataset |
| `raw_newadframework` | `platform_client_links` | 0 | 2026-04-21 | 🗑️ Deletar dataset |
| `raw_newadframework` | `proposal_lines` | 0 | 2026-04-21 | 🗑️ Deletar dataset |
| `raw_newadframework` | `proposals` | 0 | 2026-04-21 | 🗑️ Deletar dataset |
| `core` | `io_binding_registry_v4` | 0 | — | ⏳ Aguardar implementação |
| `core` | `proposal_lines` | 0 | — | ⏳ Aguardar |
| `core` | `proposals` | 0 | — | ⏳ Aguardar |
| `marts` | `io_kpis_daily_v3_mat` | 0 | — | 🗑️ Deletar |
| `marts` | `io_kpis_daily_by_model_v3_mat` | 0 | — | 🗑️ Deletar |
| `marts` | `io_line_kpis_daily_v3_mat` | 0 | — | 🗑️ Deletar |
| `marts` | `io_roas_daily_v3_mat` | 0 | — | 🗑️ Deletar |
| `analytics` | `conversion_attribution_v2` | 0 | 2026-03-25 | ⏳ Schema futuro (deixar) |
| `analytics` | `conversion_journeys_v2` | 0 | 2026-03-24 | ⏳ Schema futuro (deixar) |
| `analytics` | `session_event_summary_v2` | 0 | 2026-03-24 | ⏳ Schema futuro (deixar) |
| `analytics` | `session_touchpoints_v2` | 0 | 2026-03-24 | ⏳ Schema futuro (deixar) |
| `analytics` | `sessions_v2` | 0 | 2026-03-24 | ⏳ Schema futuro (deixar) |
| `adtracking` | `attribution_results` | 1 | — | ⚠️ Pipeline incompleto |
| `adtracking` | `conversions` | 1 | — | ⚠️ Pipeline incompleto |
| `pixel` | `audience_memberships` | 0 | — | ⚠️ Feature futura |

---

## 5. Objetos Quebrados

### 5.1 Views que leem `marts.fact_delivery_daily_v2` (NÃO EXISTE)

Esta view foi removida do `init_bq.py` durante refatoração, mas 8 objetos ainda a referenciam:

| Objeto | Dataset | Erro |
|--------|---------|------|
| `dim_platform` | core | ❌ Not found |
| `dim_campaign` | core | ❌ Not found |
| `dim_advertiser` | core | ❌ Not found |
| `dim_buying_model` | core | ❌ Not found |
| `dim_device` | core | ❌ Not found |
| `dim_format` | core | ❌ Not found |
| `dim_creative` | core | ❌ Not found (conflita com gold.dim_creative) |
| `kpi_daily` | marts | ❌ Not found |

### 5.2 `stg.siprocal_daily_std` — referenciada mas inexistente

`marts.fact_daily_detail` tenta `SELECT * FROM stg.siprocal_daily_std` — view nunca criada.

### 5.3 `core.io_manager` — EXTERNAL TABLE risco alto

Vinculada a Google Sheets. 40+ views encadeadas dependem dela:
```
core.io_manager_enriched → marts.fact_daily_detail → marts.fact_daily_io
  → share.report_daily_detail → share.report_daily_campaign
  → share.pacing_daily → share.kpi_daily (quebrado)
  → share.report_daily_* (40+ views)
```
Se a planilha for movida, desautorizada ou o token expirar → tudo quebra instantaneamente.

### 5.4 `marts.fact_daily_detail` — 3 problemas simultâneos

1. Lê `stg.siprocal_daily_std` (inexistente)
2. Lê `core.io_manager_enriched` que lê EXTERNAL table
3. Retorna sempre 0 linhas por causa de #1

### 5.5 `share.kpi_daily` — Cadeia quebrada completa

```
share.kpi_daily → marts.kpi_daily → marts.fact_delivery_daily_v2 (INEXISTENTE)
```
3 objetos encadeados, todos retornando erro.

---

## 6. Análise por Dataset

### 6.1 `raw` — Dataset Principal (ETL ativo)

**Tamanho total:** ~752 MB | **Última escrita:** 2026-04-30 (hoje, ETL roda)

**Composição:**

| Grupo | Tabelas | Tamanho | Situação |
|-------|---------|---------|----------|
| Delivery ativo | mediasmart_daily, mgid_daily | ~140.6 MB | ✅ Fonte primária |
| Supply | mediasmart_bid_supply_daily | 161.8 MB | ✅ Ativo |
| Backups fev/2026 | 5 tabelas legacy/backup | **~400 MB** | 🗑️ DELETAR |
| Metadados | creatives, campaigns, advertisers | ~29.8 MB | ✅ Ativo |
| Receita DSP | mediasmart_revenue_daily | 0.9 MB | ✅ Fonte dsp_revenue gold |
| Siprocal | siprocal_daily_materialized, native, (external) | ~0.2 MB | ⚠️ Parado mar/2026 |
| Vazias | mediasmart_daily_creative/operational | 0 MB | 🗑️ Deletar |
| Device | mgid_daily_device | 0.0 MB | ⚠️ Verificar uso |

**Situação Siprocal:** `last_modified` da `siprocal_daily_materialized` = **2026-04-30 08:00:52** — ETL rodou hoje, mas os dados têm apenas 706 linhas. Verificar se está inserindo normalmente ou acumulando.

### 6.2 `raw_mediasmart` — Snapshot Órfão

**Tamanho total:** ~710 MB | **Última escrita:** 2026-04-21 (9 dias sem atualização)

Criado como início de reestruturação. Contém cópia completa dos dados mediasmart até 2026-04-19. Inclui os mesmos backups já presentes em `raw`, dobrando o desperdício.

**Nenhum processo lê deste dataset.** Stg, marts e gold todos apontam para `raw.*`.

### 6.3 `raw_mgid` — Snapshot Órfão

**Tamanho total:** ~37 MB | **Última escrita:** 2026-04-21

Mesmo problema que `raw_mediasmart`. Snapshot congelado em 2026-04-19.

### 6.4 `raw_siprocal` — Snapshot Quase Idêntico

**Tamanho total:** ~0.1 MB | **Última escrita:** 2026-04-21

`siprocal_daily_materialized` e `siprocal_daily_native` são idênticos ao `raw`. A nova tabela `siprocal_daily_view` tem 0 linhas.

### 6.5 `raw_newadframework` — Reestruturação Core Abandonada

**Tamanho total:** 0 MB | **Última escrita:** 2026-04-21

Foram criadas as 5 tabelas com o mesmo schema de `core.*`, mas **nenhuma foi populada**. O Admin UI e o ETL continuam escrevendo em `core.*`. Este dataset é um artefato da intenção de reestruturação.

### 6.6 `stg` — Views de Transformação

**Tamanho:** 0 MB (apenas views) | Status: ✅ Ativo para o pipeline v4

Problemas mantidos:
- `stg.newad_creative_daily`, `stg.newad_daily`, `stg.newad_operational_daily` — substituídos pelo gold, mas ainda existem
- `stg.mediasmart_operational_daily`, `stg.mediasmart_operational_v2` — leem tabelas raw vazias
- `stg.mgid_operational_v2` — verificar se tem uso

### 6.7 `core` — Plano de Mídia e Bindings

**Tamanho:** ~0.3 MB | **ETL ativo:** Admin UI → Firestore → BQ (escrita em io_manager_v2)

**Tabela crítica:** `core.io_manager_v2` (229 linhas) é a fonte de verdade de todo o plano de mídia. Atualizada pelo Admin UI.

**Problema crítico:** Coexistência de `core.io_manager` (EXTERNAL/Sheets legado) e `core.io_manager_v2` (novo, Admin UI) com nomes confusos. Views que dependem do EXTERNAL têm risco de quebra.

### 6.8 `marts` — Dois Pipelines

**Pipeline v4 (ATIVO):**
- `marts.io_delivery_daily_v4` ✅
- `marts.io_schedule_daily_v4` ✅
- `marts.io_calc_daily_v4` ✅

**Pipeline legado (INATIVO/QUEBRADO):**
- `marts.fact_daily_detail` — quebrado (depende de siprocal_daily_std inexistente)
- `marts.fact_daily_io` — quebrado (depende de fact_daily_detail)
- 10+ views legadas com versões v2/v3

**Materializadas vazias (nunca atualizadas):**
- `io_kpis_daily_v3_mat`, `io_kpis_daily_by_model_v3_mat`, `io_line_kpis_daily_v3_mat`, `io_roas_daily_v3_mat`

### 6.9 `share` — 67 Objetos, Maioria Legado

**Views ATIVAS (fontes reais):**
```
share.luckbet_sheet_strategy_daily  ← fonte de gold.fct_luckbet_daily
share.io_delivery_daily_v4          ← wrapper marts.io_delivery_daily_v4
share.io_schedule_daily_v4          ← wrapper marts.io_schedule_daily_v4
share.admin_client_linking_options  ← Admin UI (linking campanhas)
share.adops_mediasmart_bid_supply_* ← 3 views de supply (verificar uso)
```

**Views POSSIVELMENTE em uso externo (auditar antes de deletar):**
```
share.report_daily_campaign   ← pode haver BI externo conectado
share.report_daily_detail     ← idem
share.io_kpis_daily_v3        ← pode haver uso externo
share.newad_operational_daily ← verificar
share.newad_powerdata_daily   ← verificar
```

**Tabelas BASE em share:**
```
share.io_validation_full       ← BASE TABLE (verificar uso)
share.report_daily_campaign_demo ← dados de demo/teste (deletar?)
```

**LuckBet views (10 no total):**
```
share.luckbet_sheet_strategy_daily     ← ATIVO (manter)
share.luckbet_sheet_campaign_daily     ← derivado (verificar)
share.luckbet_sheet_plan_map           ← derivado (verificar)
share.luckbet_strategy_daily           ← derivado (pode deletar)
share.luckbet_campaign_strategy_daily  ← derivado
share.luckbet_campaign_group_daily     ← derivado
share.luckbet_campaign_group_strategy_daily ← derivado
share.luckbet_io_line_daily            ← derivado
share.luckbet_io_line_strategy_daily   ← derivado
share.luckbet_io_line_strategy_daily_no_fallback ← derivado
```

### 6.10 `gold` — MVP Ativo e Saudável

**Tamanho:** ~9 MB | Status: ✅ Fonte do Power BI

| Tabela | Linhas | Status |
|--------|--------|--------|
| `fct_luckbet_daily` | 8.065 | ✅ |
| `fct_io_plan_daily` | 10.467 | ✅ |
| `fct_delivery_daily` | 4.420 | ✅ |
| `dim_creative` | 3.629 | ✅ |
| `dim_date` | 1.215 | ✅ |
| `dim_io_line` | 229 | ✅ |
| `dim_client` | 8 | ✅ |
| `dim_platform` | 3 | ✅ |

### 6.11 `pixel` — MVP Funcional, Volume Baixo

**Tamanho:** ~0.3 MB | 135 eventos registrados

Pipeline completo funciona (raw_events → touchpoints), mas adoção pelos clientes é mínima. Dashboard views retornam 0 linhas.

### 6.12 `adtracking` — Parcialmente Funcional

**Tamanho:** ~6.2 MB | 12.240 raw_events, 12.187 impression_events

Ingestão funciona bem (raw_events → impression_events), mas atribuição está praticamente vazia (attribution_results = 1 linha, conversions = 1 linha). Pipeline de atribuição não está rodando ou critérios são muito restritivos.

### 6.13 `analytics` — Schema Futuro Vazio

**Tamanho:** 0 MB | 5 tabelas vazias, criadas 2026-03-24

Tabelas preparadas para uma camada de analytics de sessão/jornada/conversão. Não há pipeline que as popule atualmente. Manter como schema futuro — custo = zero.

### 6.14 `finops_billing` — LEGÍTIMO E ATIVO

**Tamanho:** ~1.061 MB | Última escrita: **2026-04-30 (hoje)**

| Tabela | MB | Linhas | Tipo | Status |
|--------|-----|--------|------|--------|
| `cloud_pricing_export` | 929.4 | 1.569.785 | BASE TABLE | ✅ Export GCP Pricing |
| `gcp_billing_export_resource_v1_*` | 90.9 | 126.408 | BASE TABLE | ✅ Billing detalhado |
| `gcp_billing_export_v1_*` | 40.9 | 65.140 | BASE TABLE | ✅ Billing padrão |
| `vw_cloud_run_daily` | 0 | 0 | VIEW | ✅ Dashboard FinOps |
| `vw_app_engine_daily` | 0 | 0 | VIEW | ✅ Dashboard FinOps |
| `vw_cost_daily_service` | 0 | 0 | VIEW | ✅ Dashboard FinOps |
| `vw_cost_monthly_service` | 0 | 0 | VIEW | ✅ Dashboard FinOps |
| `vw_cost_monthly_sku` | 0 | 0 | VIEW | ✅ Dashboard FinOps |
| `vw_finops_focus_top` | 0 | 0 | VIEW | ✅ Dashboard FinOps |

> **NÃO TOCAR.** Este é o billing export oficial do GCP — exportado automaticamente pelo Google. Deletar causaria perda de histórico de custos irrecuperável.

---

## 7. Análise do Código Python (GitHub)

### 7.1 Estrutura do Projeto

```
adframework/
├── adframework_python/
│   ├── main.py              ← FastAPI: ETL orchestrator + Pixel MVP (2 serviços, 1 app)
│   ├── src/
│   │   ├── orchestrator.py  ← ETL logic (945 linhas): jobs lidos do Firestore
│   │   ├── connectors/      ← MediaSmart, MGID, Siprocal connectors
│   │   └── pixel/           ← Pixel server-side tracking
│   └── scripts/
│       └── init_bq.py       ← Schema + DDL SQL (~3.500 linhas, mistura Python e SQL)
├── admin_ui/app/
│   ├── main.py              ← FastAPI Admin UI (auth, IO, clients, pipeline trigger)
│   ├── auth.py              ← Firebase Auth
│   └── db.py                ← Firestore client
└── docs/
```

### 7.2 ETL Endpoints (adframework_python/main.py)

```
GET|POST /v1/collect          ← Pixel: recebe evento + HMAC validation → pixel.raw_events
POST     /jobs/{name}/run     ← Executa job ETL por nome (lê config do Firestore)
POST     /run-all             ← Executa todos os jobs do Firestore
POST     /scheduler/run-due   ← Trigger do Cloud Scheduler (cron diário)
```

### 7.3 orchestrator.py — Problemas Identificados

**Jobs configurados:**

| Job Name | Connector | Destino BQ | Cron |
|----------|-----------|-----------|------|
| `mediasmart_daily:Daily` | `_run_mediasmart_daily` | `raw.mediasmart_daily` | Diário |
| `mgid_daily:daily` | `_run_mgid_daily` | `raw.mgid_daily` | Diário |
| Siprocal | `_run_siprocal_external` | `raw.siprocal_daily_materialized` | Periódico |

**Destinos hardcoded em `raw.*`** — os novos datasets `raw_mediasmart.*`, `raw_mgid.*` nunca são escritos pelo ETL.

**Problemas críticos:**

1. **Siprocal status:** `raw.siprocal_daily_materialized` tem `last_modified = 2026-04-30 08:00:52` (hoje). Porém apenas 706 linhas no total — se o ETL está rodando, ou está inserindo 0 linhas ou sobrescrevendo sempre os mesmos dados. Investigar.

2. **Sem retry em falhas:** Cloud Run timeout = 60 min. Jobs longos podem falhar silenciosamente sem reprocessar o dia.

3. **Sem alertas de falha:** Nenhum PubSub / Cloud Monitoring alert configurado para jobs falhos.

4. **Carga incremental via MAX(date):** Se houver um registro com data futura na tabela (outlier), o ETL para de ingerir dados pois `start_date = MAX(date) + 1 = futuro`.

5. **Gold não é refreshado automaticamente:** Após o ETL ingerir dados em `raw`, as tabelas `gold.fct_delivery_daily` etc. não são recriadas. Processo manual.

### 7.4 init_bq.py — Análise (~3.500 linhas)

**Problemas estruturais:**

1. **Mistura Python com SQL inline:** Funções retornam f-strings SQL. Dificulta versionamento, revisão e testing dos SQLs.

2. **`build_marts_fact_delivery_daily_v2()` — função morta:** Referenciada por ~6 outras funções mas a função que cria a view foi removida. Resulta nas 8 views quebradas que leem de uma view inexistente.

3. **Hardcode de dataset names:** `RAW_DATASET = "raw"`, `CORE_DATASET = "core"` etc. hardcoded. Se a reestruturação para `raw_mediasmart/*` for executada, exige mudar N variáveis.

4. **Funções definidas mas nunca chamadas (geram views quebradas):**
   ```python
   build_core_dim_platform_view()    # ← não chamada, view quebrada em BQ
   build_core_dim_campaign_view()    # ← idem
   build_core_dim_device_view()      # ← idem
   build_core_dim_format_view()      # ← idem
   ```

5. **Proposta de melhoria:** Separar SQLs em arquivos `.sql` por dataset:
   ```
   adframework_python/sql/
   ├── stg/mediasmart_daily_std.sql
   ├── stg/io_lines_v4.sql
   ├── marts/io_delivery_daily_v4.sql
   ├── marts/io_schedule_daily_v4.sql
   └── gold/  (já temos em docs/gold_layer_ddl.sql)
   ```

---

## 8. Análise do Admin UI

### 8.1 Dependências BQ

```python
# admin_ui/app/main.py (constantes)
BQ_LINKING_DATASET = "share"
BQ_LINKING_CAMPAIGN_TABLE = "admin_client_linking_options"   # ← ativo
BQ_LINKING_FALLBACK_TABLE  = "report_daily_campaign"         # ← LEGADO (pipeline antigo)
```

**Problema:** `report_daily_campaign` é uma view do pipeline legado (via `core.io_manager` EXTERNAL). Se o Admin UI precisar do fallback, vai chamar uma view que depende de Google Sheets.

**Solução:** Criar uma view `share.admin_campaign_options_v2` baseada em `core.io_line_bindings_v2` + `core.io_manager_v2` e substituir o fallback.

### 8.2 Fluxo IO Manager

```
Admin UI → Firebase Auth → validação
    ↓
Firestore (io_lines, io_bindings, client_links)
    ↓
ETL sync job → core.io_manager_v2 (BQ)
              core.io_line_bindings_v2 (BQ)
              core.platform_client_links (BQ)
    ↓
core.io_registry_v4 (VIEW)
    ↓
stg.io_lines_v4 (VIEW)
    ↓
gold.dim_io_line  ←── REBUILD MANUAL NECESSÁRIO
gold.fct_io_plan_daily ←── REBUILD MANUAL NECESSÁRIO
```

**Gap:** Não há trigger automático quando o Admin UI atualiza um IO. O gold precisa ser recriado manualmente.

### 8.3 Plataformas Suportadas vs Configuradas

```python
PLATFORM_DAILY_JOB_NAMES = {
    "mediasmart": "mediasmart_daily:Daily",
    "mgid": "mgid_daily:daily",
    # Siprocal NÃO está aqui — job nome undefined no Admin UI
}
```

Se alguém tentar disparar o ETL do Siprocal pelo Admin UI, a UI não sabe o nome do job.

---

## 9. Mapa de Custos de Storage

### Storage Atual (2026-04-30)

```
Dataset              │ Size (MB) │ Custo/mês ($)  │ Situação
─────────────────────┼───────────┼────────────────┼──────────────────────
finops_billing       │  1.061 MB │ ~$0.021        │ ✅ Legítimo, ativo
raw                  │   752 MB  │ ~$0.015        │ ✅ Ativo (com lixo)
  └ backups fev/2026 │  (~400 MB)│  (~$0.008)     │ 🗑️ DELETAR
raw_mediasmart       │   710 MB  │ ~$0.014        │ 🔴 DUPLICATA ÓRFÃ
  └ backups included │  (~400 MB)│  (~$0.008)     │ 🗑️ DELETAR
raw_mgid             │    37 MB  │ ~$0.001        │ 🔴 DUPLICATA ÓRFÃ
raw_siprocal         │   0.1 MB  │ ~$0.000        │ 🔴 DUPLICATA
raw_newadframework   │     0 MB  │ ~$0.000        │ 🔴 VAZIO
stg                  │     0 MB  │ $0.000         │ views
core                 │   0.3 MB  │ ~$0.000        │ ✅ Ativo
marts                │     0 MB  │ $0.000         │ views + mat vazias
share                │   ~0 MB   │ $0.000         │ views
gold                 │     9 MB  │ ~$0.000        │ ✅ MVP
pixel                │   0.3 MB  │ ~$0.000        │ ✅ MVP
adtracking           │   6.2 MB  │ ~$0.000        │ ⚠️
analytics            │     0 MB  │ $0.000         │ vazio
─────────────────────┼───────────┼────────────────┼──────────────────────
TOTAL ATUAL          │ ~2.576 MB │ ~$0.052/mês    │
─────────────────────┼───────────┼────────────────┼──────────────────────
REMOVÍVEL (backups)  │ ~800 MB   │ ~$0.016/mês    │ 5 tabelas raw + 5 raw_mediasmart
REMOVÍVEL (dups)     │ ~747 MB   │ ~$0.015/mês    │ raw_mediasmart + raw_mgid main data
─────────────────────┼───────────┼────────────────┼──────────────────────
TOTAL APÓS LIMPEZA   │ ~1.029 MB │ ~$0.021/mês    │ Redução de ~60%
```

> BigQuery cobra **$0.020/GB/mês** para storage ativo (primeiros 10 GB grátis). O custo real está nas **queries** sobre essas tabelas, não no storage. O maior custo é o `finops_billing.cloud_pricing_export` com 929 MB que é legítimo.

### Custo de Query (impacto)

Cada query full scan sobre `raw_mediasmart.mediasmart_daily` (140 MB) = ~$0.00070. Parece pequeno, mas se o pipeline legado rodar queries sobre essas tabelas diariamente, o custo acumula. Com os datasets duplicados órfãos **não sendo lidos por ninguém**, o custo real é zero — mas o risco operacional é alto se alguém começar a usar o dataset errado por engano.

---

## 10. Proposta de Limpeza — 3 Fases

### Fase 1 — Quick Wins Imediatos (baixo risco, 1-2 dias)

**1.1 Confirmar cobertura do raw.mediasmart_daily antes de qualquer delete:**
```sql
SELECT MIN(day), MAX(day), COUNT(DISTINCT day) AS dias_cobertos
FROM `adframework.raw.mediasmart_daily`;
-- Resultado esperado: 2025-08-01 → hoje, ~242 dias
```

**1.2 Deletar backups raw (libera ~400 MB):**
```sql
DROP TABLE `adframework.raw.mediasmart_daily_legacy_20260227_065635`;
DROP TABLE `adframework.raw.mediasmart_daily_backup_20260227_111821`;
DROP TABLE `adframework.raw.mediasmart_daily_legacy_20260227_061441`;
DROP TABLE `adframework.raw.mgid_daily_legacy_20260227_061627`;
DROP TABLE `adframework.raw.mgid_daily_legacy_20260227_065913`;
```

**1.3 Deletar tabelas raw vazias (0 linhas, nunca populadas):**
```sql
DROP TABLE `adframework.raw.mediasmart_daily_creative`;
DROP TABLE `adframework.raw.mediasmart_daily_operational`;
```

**1.4 Deletar views core quebradas (leem view inexistente):**
```sql
DROP VIEW `adframework.core.dim_platform`;
DROP VIEW `adframework.core.dim_campaign`;
DROP VIEW `adframework.core.dim_advertiser`;
DROP VIEW `adframework.core.dim_buying_model`;
DROP VIEW `adframework.core.dim_device`;
DROP VIEW `adframework.core.dim_format`;
DROP VIEW `adframework.core.dim_creative`;  -- conflita com gold.dim_creative
```

**1.5 Deletar tabelas materializadas vazias em marts:**
```sql
DROP TABLE `adframework.marts.io_kpis_daily_v3_mat`;
DROP TABLE `adframework.marts.io_kpis_daily_by_model_v3_mat`;
DROP TABLE `adframework.marts.io_line_kpis_daily_v3_mat`;
DROP TABLE `adframework.marts.io_roas_daily_v3_mat`;
```

**Resultado Fase 1:** -400 MB storage, -13 objetos inúteis, zero risco.

---

### Fase 2 — Decisão sobre raw_* (ver Seção 11 primeiro)

#### Opção A: Abandonar reestruturação raw_* — Deletar tudo

Se a decisão for manter `raw.*` como único dataset de ingestão:

```sql
-- Deletar datasets inteiros (todos os objetos dentro)
-- Primeiro confirmar via BQ Console que nenhuma stg/marts view lê raw_mediasmart:
-- SELECT view_definition FROM adframework.stg.INFORMATION_SCHEMA.VIEWS
-- WHERE view_definition LIKE '%raw_mediasmart%';

-- Depois:
DROP SCHEMA `adframework.raw_mediasmart` CASCADE;  -- libera ~710 MB
DROP SCHEMA `adframework.raw_mgid` CASCADE;         -- libera ~37 MB
DROP SCHEMA `adframework.raw_siprocal` CASCADE;     -- libera ~0.1 MB
DROP SCHEMA `adframework.raw_newadframework` CASCADE; -- libera ~0 MB
```
**Resultado:** -747 MB, -25 objetos, pipeline permanece em `raw.*`.

#### Opção B: Completar reestruturação raw_* — Migrar ETL

Se a decisão for manter a arquitetura separada por plataforma:

1. Atualizar `orchestrator.py`:
   ```python
   # trocar destino de:
   DEST_TABLE = f"{project}.raw.mediasmart_daily"
   # para:
   DEST_TABLE = f"{project}.raw_mediasmart.mediasmart_daily"
   ```

2. Atualizar todas as stg views para ler de `raw_mediasmart.*`:
   ```sql
   -- Atualizar stg.mediasmart_daily (atualmente lê raw.mediasmart_daily)
   CREATE OR REPLACE VIEW `adframework.stg.mediasmart_daily` AS
   SELECT ... FROM `adframework.raw_mediasmart.mediasmart_daily` ...;
   ```

3. Limpar backups do `raw_mediasmart` (os mesmos de raw):
   ```sql
   DROP TABLE `adframework.raw_mediasmart.mediasmart_daily_legacy_20260227_065635`;
   -- etc.
   ```

4. Deletar `raw.*` mediasmart tables após validação
5. Deletar `raw_newadframework` (duplica core, nunca funcionou)

**Custo Opção B:** ~2-3 semanas de trabalho. Resultado: pipeline mais organizado, mas mesma funcionalidade.

---

### Fase 3 — Depreciação Legado (médio risco, 2-4 semanas)

**3.1 Auditar uso real das share views (executar no Cloud Logging):**
```sql
SELECT
  referenced_table.dataset_id,
  referenced_table.table_id,
  COUNT(*) AS query_count,
  MAX(creation_time) AS last_used
FROM `region-us`.INFORMATION_SCHEMA.JOBS,
UNNEST(referenced_tables) AS referenced_table
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
  AND referenced_table.project_id = 'adframework'
  AND referenced_table.dataset_id IN ('share', 'marts', 'core')
GROUP BY 1, 2
ORDER BY query_count DESC;
```

**3.2 Corrigir Admin UI fallback:**
```python
# admin_ui/app/main.py — substituir:
BQ_LINKING_FALLBACK_TABLE = "report_daily_campaign"  # legado
# por:
BQ_LINKING_FALLBACK_TABLE = "admin_client_linking_options"  # já existe
```

**3.3 Deprecar cadeia share.report_daily_* após confirmar zero uso:**
```sql
-- Em ordem de dependência (mais dependentes primeiro)
DROP VIEW `adframework.share.report_daily_roas_line_pivot_reconciled`;
DROP VIEW `adframework.share.report_daily_roas_line_pivot_unmatched`;
DROP VIEW `adframework.share.report_daily_roas_line_pivot`;
DROP VIEW `adframework.share.report_daily_roas_line`;
DROP VIEW `adframework.share.report_daily_roas_io`;
DROP VIEW `adframework.share.report_daily_roas_campaign`;
DROP VIEW `adframework.share.report_daily_roas_unmatched`;
DROP VIEW `adframework.share.io_roas_daily`;
DROP VIEW `adframework.share.report_daily_campaign_by_source`;
DROP VIEW `adframework.share.report_daily_creative_grouped`;
DROP VIEW `adframework.share.report_daily_creative`;
DROP VIEW `adframework.share.report_daily_device`;
DROP VIEW `adframework.share.report_daily_format`;
DROP VIEW `adframework.share.report_daily_revenue`;
DROP VIEW `adframework.share.pacing_daily_cpc`;
DROP VIEW `adframework.share.pacing_daily_cpm`;
DROP VIEW `adframework.share.pacing_daily_by_source`;
DROP VIEW `adframework.share.pacing_daily`;
DROP VIEW `adframework.share.pacing_cards`;
DROP VIEW `adframework.share.dashboard_cards_campaign`;
DROP VIEW `adframework.share.dashboard_cards_detail`;
DROP VIEW `adframework.share.kpi_daily`;
DROP VIEW `adframework.share.report_daily_campaign`;
DROP VIEW `adframework.share.report_daily_detail`;
-- io_kpis versões
DROP VIEW `adframework.share.io_kpis_daily_v2`;
DROP VIEW `adframework.share.io_kpis_daily_v3`;
DROP VIEW `adframework.share.io_kpis_daily_by_model_v2`;
DROP VIEW `adframework.share.io_kpis_daily_by_model_v3`;
DROP VIEW `adframework.share.io_line_kpis_daily_v2`;
DROP VIEW `adframework.share.io_line_kpis_daily_v3`;
DROP VIEW `adframework.share.io_line_actual_daily_v3`;
DROP VIEW `adframework.share.io_line_plan_daily_v2`;
DROP VIEW `adframework.share.io_line_plan_daily_v3`;
DROP VIEW `adframework.share.io_line_revenue_daily_v3`;
-- platform views
DROP VIEW `adframework.share.platform_campaign_catalog`;
DROP VIEW `adframework.share.platform_creative_catalog`;
DROP VIEW `adframework.share.platform_daily_campaign`;
DROP VIEW `adframework.share.platform_daily_creative`;
DROP VIEW `adframework.share.platform_daily_detail`;
DROP VIEW `adframework.share.platform_daily_strategy`;
DROP VIEW `adframework.share.platform_strategy_catalog`;
-- marts legado
DROP VIEW `adframework.marts.fact_daily_detail`;
DROP VIEW `adframework.marts.fact_daily_io`;
DROP VIEW `adframework.marts.io_plan_daily`;
DROP VIEW `adframework.marts.io_kpis_daily_v2`;
DROP VIEW `adframework.marts.io_kpis_daily_v3`;
DROP VIEW `adframework.marts.io_kpis_daily_by_model_v2`;
DROP VIEW `adframework.marts.io_kpis_daily_by_model_v3`;
DROP VIEW `adframework.marts.io_line_kpis_daily_v2`;
DROP VIEW `adframework.marts.io_line_kpis_daily_v3`;
DROP VIEW `adframework.marts.io_line_actual_daily_v2`;
DROP VIEW `adframework.marts.io_line_actual_daily_v3`;
DROP VIEW `adframework.marts.io_line_plan_daily_v2`;
DROP VIEW `adframework.marts.io_line_plan_daily_v3`;
DROP VIEW `adframework.marts.io_line_revenue_daily_v3`;
DROP VIEW `adframework.marts.io_plan_daily`;
DROP VIEW `adframework.marts.kpi_daily`;
-- core legado (após migrar enriched para v2)
DROP VIEW `adframework.core.io_manager_enriched`;  -- lê EXTERNAL
-- depois:
-- DROP TABLE `adframework.core.io_manager`;  -- EXTERNAL Sheets
```

**3.4 Automatizar Gold refresh:**
```python
# orchestrator.py — adicionar ao final de cada job run:
def _refresh_gold_after_etl(self):
    """Rebuild fct_* tables after ETL ingestion."""
    for sql_file in ['fct_delivery_daily', 'fct_io_plan_daily', 'fct_luckbet_daily']:
        sql = open(f'sql/gold/{sql_file}.sql').read()
        self.bq_client.query(sql).result()
```

---

## 11. Decisão Arquitetural: Manter raw vs Migrar para raw_*

### Opção A: Abandonar raw_* e centralizar em raw (RECOMENDADO agora)

**Prós:**
- ETL já escreve em `raw.*` e funciona
- Stg/marts/gold já apontam para `raw.*`
- Zero mudança de código
- Libera ~747 MB imediatamente
- Risco zero

**Contras:**
- `raw` mistura mediasmart + mgid + siprocal no mesmo dataset
- Crescerá com o tempo sem separação por plataforma

**Quando escolher:** Agora, antes de conectar o Power BI e subir para produção.

### Opção B: Completar a reestruturação raw_* (PARA FASE FUTURA)

**Prós:**
- Melhor organização por plataforma
- Facilita billing/cost allocation por plataforma
- Mais alinhado com boas práticas (um dataset por fonte)

**Contras:**
- Requer ~2-3 semanas de trabalho
- Atualizar orchestrator.py + 14 stg views + testes
- Enquanto não completa, os datasets ficam inconsistentes

**Quando escolher:** Após estabilizar o Gold + Power BI em produção. Fazer como uma sprint dedicada.

### Recomendação Final

```
AGORA:     Executar Fase 1 + Opção A da Fase 2
           → deletar raw_* órfãos + backups
           → focar em Power BI e Gold

PRÓXIMA SPRINT (2-4 semanas):
           → Executar Fase 3 (depreciação legado)
           → Automatizar gold refresh

FUTURO (quando tiver banda):
           → Considerar Opção B (raw_* por plataforma)
           → Junto com migração para sql/ files no Python
```

---

## 12. Plano de Execução

### Sprint 0 — Segurança (antes de qualquer delete)

```
Dia 1 (hoje):
  [ ] Auditar queries Cloud Logging (Fase 3.1) — identificar views share com uso real
  [ ] Confirmar cobertura raw.mediasmart_daily (MIN/MAX day)
  [ ] Confirmar que nenhuma stg view lê raw_mediasmart/*
      → SELECT view_definition FROM stg.INFORMATION_SCHEMA.VIEWS
         WHERE view_definition LIKE '%raw_mediasmart%' OR ...
```

### Sprint 1 — Limpeza Imediata (Fase 1 + Fase 2 Opção A)

```
Dia 2:
  [ ] DELETE: raw.mediasmart_daily_legacy/backup (5 tabelas, ~400 MB)
  [ ] DELETE: raw.mediasmart_daily_creative/operational (2 tabelas, 0 MB)
  [ ] DELETE: core.dim_* quebradas (7 views)
  [ ] DELETE: marts.*_mat vazias (4 tabelas)

Dia 3:
  [ ] DELETE: raw_mediasmart (dataset inteiro, ~710 MB)
  [ ] DELETE: raw_mgid (dataset inteiro, ~37 MB)
  [ ] DELETE: raw_siprocal (dataset inteiro, ~0.1 MB)
  [ ] DELETE: raw_newadframework (dataset inteiro, vazio)

Dia 4:
  [ ] Testar Gold Layer completamente
  [ ] Testar Power BI conexão
  [ ] Verificar Admin UI /clients e /pipeline ainda funcionam

Dia 5:
  [ ] Commit + documentação do que foi feito
```

### Sprint 2 — Legado e Admin UI (Fase 3)

```
Semana 1:
  [ ] Corrigir BQ_LINKING_FALLBACK_TABLE no Admin UI
  [ ] Verificar resultado do Cloud Logging audit
  [ ] Deprecar share.report_daily_* (após confirmar zero uso)

Semana 2:
  [ ] Deprecar marts pipeline legado
  [ ] Atualizar init_bq.py (remover funções mortas)
  [ ] Implementar gold refresh automático no ETL
```

### Checklist de Validação Antes de Deletar Qualquer Objeto

```sql
-- 1. Verificar uso recente (últimos 60 dias)
SELECT referenced_table.table_id, COUNT(*) AS uses
FROM `region-us`.INFORMATION_SCHEMA.JOBS,
UNNEST(referenced_tables) AS referenced_table
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
  AND referenced_table.dataset_id = 'DATASET_ALVO'
GROUP BY 1 ORDER BY 2 DESC;

-- 2. Verificar dependentes (views que leem o objeto)
SELECT table_name, SUBSTR(view_definition,1,200) AS ddl_preview
FROM `adframework.DATASET.INFORMATION_SCHEMA.VIEWS`
WHERE view_definition LIKE '%NOME_DO_OBJETO%';

-- 3. Grep no código Python
-- grep -r "NOME_DO_OBJETO" adframework_python/ admin_ui/

-- 4. Confirmar Power BI não conecta diretamente
-- (verificar no Power BI Desktop: Model → External tools ou dataset source)
```

---

## Resumo Executivo

| Métrica | Antes | Após Fase 1+2A | Após Fase 1+2A+3 |
|---------|-------|----------------|-----------------|
| Datasets | 14 | 10 | 10 |
| Objetos totais | ~213 | ~180 | ~100 |
| Storage total | ~2.576 MB | ~1.029 MB | ~1.029 MB |
| Storage removível | ~1.147 MB | 0 | 0 |
| Views legadas share | 65 | 65 | ~8 |
| Views quebradas | 8 | 0 | 0 |
| Tabelas mat. vazias | 4 | 0 | 0 |
| Backups obsoletos | 10 (2 cópias de 5) | 0 | 0 |
| finops_billing (intocável) | 1.061 MB | 1.061 MB | 1.061 MB |

**Ação mais urgente e segura:** Deletar os 4 datasets `raw_*` órfãos + 5 backups de fevereiro em `raw`. Libera ~1.1 GB, risco zero, nenhuma view depende deles.

---

*Documento: AdFramework BigQuery Deep Analysis v2 | 2026-04-30 | douglas@newad.com.br*
