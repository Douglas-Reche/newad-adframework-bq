# AdFramework — Auditoria Profunda BQ Prod + Plano de Reestruturação Total

---
> **⚠️ LEGADO — PRÉ-REBUILD 2026-06-16 ⚠️**
> Este documento descreve a pipeline **anterior ao reset completo de 2026-06-16**.
> Tabelas, views, schemas e colunas aqui descritos **foram dropados e não existem mais no BigQuery**.
> Mantenha para consulta histórica — **não use como referência para desenvolvimento novo.**
> Plano atual: [bq_restructuring_plan.md](bq_restructuring_plan.md) · [CHANGELOG.md](../CHANGELOG.md)
---
**Projeto:** adframework  
**Data:** 2026-04-30  
**Elaborado por:** Douglas Reche  
**Para revisão:** Shiro · Alexandre  
**Objetivo:** Documentar o estado real do BigQuery de produção cruzado com o repositório GitHub, identificar todos os problemas e definir a arquitetura limpa que será construída no ambiente staging zerado.

---

## 1. Visão Geral: O que foi auditado

| Fonte | O que foi lido | Profundidade |
|-------|---------------|-------------|
| BigQuery prod | 14 datasets, ~120 tabelas/views, sizes e row counts | Completa |
| `init_bq.py` | 3.490 linhas — toda lógica de criação de schema | Completa |
| `orchestrator.py` | 945 linhas — todo fluxo de ingestão ETL | Completa |
| `bigquery.py` | 120 linhas — serviço de escrita no BQ | Completa |
| `main.py` | Endpoints FastAPI (ETL + Pixel) | Completa |
| `deploy-cloud-run.yml` | CI/CD GitHub Actions staging + prod | Completa |
| Schemas e views do pipeline V4 | io_delivery_daily_v4, io_lines_v4, gold layer | Via DDL |

---

## 2. A Descoberta Mais Crítica: Dois Pipelines em Produção

Existem **dois pipelines paralelos e independentes** coexistindo no mesmo projeto BigQuery. Nenhum dos dois está documentado formalmente. São completamente diferentes em arquitetura, fontes de dados e estado operacional.

### Pipeline A — Legado (init_bq.py) — **QUEBRADO**

```
raw.mediasmart_daily  ──┐
raw.mgid_daily         ├──► stg.*_daily_std ──► marts.delivery_daily
raw.siprocal_daily_mat ─┘                               │
                                                         ▼
core.io_manager [External Table: Google Sheets]  ──► marts.fact_delivery_daily_v2  ← NÃO EXISTE
                                                         │
                                                         ▼
                                              share.report_daily_*  ← TODOS QUEBRADOS
```

**Por que está quebrado:**  
`marts.fact_delivery_daily_v2` é definido como função Python em `init_bq.py` (linha 448) mas **nunca é chamado no `main()`** (linha 3416). A função existe, o SQL existe, mas `ensure_view()` nunca é chamado para criar essa view. Como resultado, `marts.fact_delivery_daily_v2` **nunca foi criada em prod**. Todas as views que dependem dela retornam erro silencioso (tabela vazia ou erro de referência).

**Objetos que dependem de `marts.fact_delivery_daily_v2` e estão quebrados:**
- `core.dim_device` (função existe, não está em main())
- `core.dim_format` (função existe, não está em main())
- `core.dim_creative` (função existe, não está em main())
- `share.fact_delivery_daily` (função existe, não está em main())
- `share.fact_delivery_daily_enriched` (função existe, não está em main())
- `share.daily_kpis` (função existe, não está em main())
- `share.campaign_kpis` (função existe, não está em main())
- `marts.pacing` (função existe em init_bq.py, não está em main())
- `marts.pacing_daily` (função existe em init_bq.py, não está em main())

**Total de funções definidas em init_bq.py que NUNCA são chamadas em main():**

| Função | Objeto que criaria | Status em Prod |
|--------|--------------------|----------------|
| `build_marts_fact_delivery_daily_v2()` | `marts.fact_delivery_daily_v2` | Não existe |
| `build_marts_pacing_view()` | `marts.pacing` | Não existe |
| `build_marts_pacing_daily_view()` | `marts.pacing_daily` | Não existe |
| `build_core_dim_platform_view()` | `core.dim_platform` | Não existe |
| `build_core_dim_campaign_view()` | `core.dim_campaign` | Não existe |
| `build_core_dim_advertiser_view()` | `core.dim_advertiser` | Não existe |
| `build_core_dim_buying_model_view()` | `core.dim_buying_model` | Não existe |
| `build_core_dim_device_view()` | `core.dim_device` | Não existe |
| `build_core_dim_format_view()` | `core.dim_format` | Não existe |
| `build_core_dim_creative_view()` | `core.dim_creative` | Não existe |
| `build_share_fact_delivery_daily_view()` | `share.fact_delivery_daily` | Não existe |
| `build_share_fact_delivery_daily_enriched_view()` | `share.fact_delivery_daily_enriched` | Não existe |
| `build_share_daily_kpis_view()` | `share.daily_kpis` | Não existe |
| `build_share_campaign_kpis_view()` | `share.campaign_kpis` | Não existe |

**Conclusão:** init_bq.py tem ~1.500 linhas de código morto. O Pipeline A nunca chegou a funcionar completamente em prod.

---

### Pipeline B — V4 (criado manualmente) — **ATIVO E FUNCIONANDO**

```
raw.mediasmart_daily  ──┐
raw.mgid_daily         ├──► stg.*_daily_std ──► marts.io_delivery_daily_v4
raw.siprocal_daily_mat ─┘         ▲                        │
                                   │                        ▼
core.io_manager_v2 [Firestore]    │          share.io_kpis_daily_v3
core.io_line_bindings_v2    ──► stg.io_lines_v4              │
                                                              ▼
                                                    gold.fct_delivery_daily
                                                    gold.fct_io_plan_daily
                                                    gold.fct_luckbet_daily
                                                             │
                                                             ▼
                                                       Power BI
```

**Por que está funcionando:**  
`core.io_manager_v2` (229 rows) vem do Firestore via sync do Admin UI. `stg.io_lines_v4` e `stg.io_lines_v4` são views criadas manualmente via BQ console. A camada gold foi criada manualmente via `docs/gold_layer_ddl.sql`. Todo esse pipeline foi construído incrementalmente fora do `init_bq.py`.

**Problema:** Nenhum arquivo no repositório cria ou documenta o Pipeline B. Ele existe exclusivamente no BQ console e em `docs/gold_layer_ddl.sql`.

---

## 3. Inventário Completo: Código vs. BigQuery Prod

### O que o código cria vs. o que existe em prod

#### Camada RAW

| Tabela | Quem cria | Existe em Prod? | Rows | Observação |
|--------|-----------|-----------------|------|------------|
| `raw.mediasmart_daily` | orchestrator.py (APPEND) | ✅ Sim | 638.595 | Pipeline ativo |
| `raw.mediasmart_creatives` | orchestrator.py (TRUNCATE) | ✅ Sim | 20.353 | Truncate diário |
| `raw.mediasmart_campaigns` | orchestrator.py (generic) | ✅ Sim | 1.996 | |
| `raw.mediasmart_bid_supply_daily` | **Não está no código** | ✅ Sim | 602.179 | Criada manualmente |
| `raw.mediasmart_revenue_daily` | **Não está no código** | ✅ Sim | 8.042 | Criada manualmente |
| `raw.mediasmart_daily_creative` | **Não está no código** | ✅ Sim | 0 rows | Vazia — deletar |
| `raw.mediasmart_daily_operational` | **Não está no código** | ✅ Sim | 0 rows | Vazia — deletar |
| `raw.mediasmart_daily_legacy_*` (3x) | **Não está no código** | ✅ Sim | ~400 MB | Backups manuais — deletar |
| `raw.mgid_daily` | orchestrator.py (APPEND) | ✅ Sim | 4.093 | |
| `raw.mgid_creatives` | orchestrator.py (generic) | ✅ Sim | 9.314 | |
| `raw.mgid_campaigns` | orchestrator.py (generic) | ✅ Sim | 12.741 | |
| `raw.mgid_daily_device` | **Não está no código** | ✅ Sim | 803 | |
| `raw.siprocal_daily_materialized` | orchestrator.py (CREATE OR REPLACE) | ✅ Sim | 706 | |
| `raw.siprocal_daily` | **EXTERNAL TABLE** | ✅ Sim | 0 rows | Ext Table inativa |
| `raw.siprocal_daily_native` | **Não está no código** | ✅ Sim | 706 | |
| `raw.mgid_daily_std` | init_bq.py (view) | ❌ **Não existe** | — | Não chamado no main |

**⚠ Achado crítico:** `init_bq.py` cria `stg.mgid_daily_std` mas **não existe schema para `raw.mgid_daily`** no init_bq.py. O orchestrator salva mgid_daily com autodetect (todos STRING). O stg view faz SAFE_CAST para INT64, mas pode quebrar se a API mudar o formato de alguma coluna.

#### Camada STG

| Tabela/View | Quem cria | Existe em Prod? | Observação |
|-------------|-----------|-----------------|------------|
| `stg.mediasmart_daily_std` | init_bq.py | ✅ Sim (View) | Join com creatives para creative_url |
| `stg.mgid_daily_std` | init_bq.py | ✅ Sim (View) | Join com mgid_creatives |
| `stg.siprocal_daily_std` | init_bq.py | ✅ Sim (View) | Lê raw.siprocal_daily_materialized |
| `stg.mediasmart_daily` | init_bq.py (alias) | ✅ Sim (View) | SELECT * FROM mediasmart_daily_std |
| `stg.mgid_daily` | init_bq.py (alias) | ✅ Sim (View) | SELECT * FROM mgid_daily_std |
| `stg.siprocal_daily` | init_bq.py (alias) | ✅ Sim (View) | SELECT * FROM siprocal_daily_std |
| `stg.io_lines_v4` | **Não está no código** | ✅ Sim (View) | Fonte da camada gold — criada manualmente |
| `stg.newad_revenue_daily` | **Não está no código** | ✅ Sim (View) | Usada por fct_delivery_daily — criada manualmente |
| `stg.mediasmart_revenue_daily` | **Não está no código** | ✅ Sim (View) | Lê raw.mediasmart_revenue_daily |
| `stg.mediasmart_daily_std` | init_bq.py | ✅ Sim (View) | |
| `stg.mediasmart_operational_daily` | **Não está no código** | ✅ Sim (View) | |
| `stg.mediasmart_operational_v2` | **Não está no código** | ✅ Sim (View) | |
| `stg.mediasmart_creative_daily` | **Não está no código** | ✅ Sim (View) | |
| `stg.mediasmart_bid_supply_daily` | **Não está no código** | ✅ Sim (View) | |
| `stg.mgid_daily_std` | init_bq.py | ✅ Sim (View) | |
| `stg.mgid_operational_v2` | **Não está no código** | ✅ Sim (View) | |
| `stg.newad_creative_daily` | **Não está no código** | ✅ Sim (View) | |
| `stg.newad_daily` | **Não está no código** | ✅ Sim (View) | |
| `stg.newad_operational_daily` | **Não está no código** | ✅ Sim (View) | |

**Sumário STG:** 19 views existem em prod. Apenas 6 são gerenciadas por código (init_bq.py). As outras 13 foram criadas manualmente via BQ console sem registro no repositório.

#### Camada CORE

| Tabela/View | Quem cria | Existe em Prod? | Rows | Observação |
|-------------|-----------|-----------------|------|------------|
| `core.io_manager` | init_bq.py (External Table) | ✅ Sim | 62 | Google Sheets legado |
| `core.io_manager_legacy_cache` | **Não está no código** | ✅ Sim | 62 | Cache do External Table |
| `core.io_manager_v2` | **Não está no código** | ✅ Sim | 229 | Firestore sync — fonte canônica |
| `core.io_line_bindings_v2` | **Não está no código** | ✅ Sim | 170 | Bindings IO↔Campanha |
| `core.platform_client_links` | **Não está no código** | ✅ Sim | 27 | Links plataforma↔cliente |
| `core.io_manager_enriched` | init_bq.py (view) | ✅ Sim (View) | — | Lê core.io_manager (legado!) |
| `core.io_manager_enriched_v2` | **Não está no código** | ✅ Sim (View) | — | Versão nova — não chamada por init_bq |
| `core.io_binding_registry_v4` | **Não está no código** | ✅ Sim (View) | — | |
| `core.io_registry_v4` | **Não está no código** | ✅ Sim (View) | — | |
| `core.io_line_bindings_enriched_v2` | **Não está no código** | ✅ Sim (View) | — | |
| `core.proposals` | **Não está no código** | ✅ Sim | 0 rows | |
| `core.proposal_lines` | **Não está no código** | ✅ Sim | 0 rows | |

**⚠ Achado crítico:** `core.io_manager_enriched` (criada por init_bq.py e chamada pelo orchestrator.py linha 723 para buscar campaign_ids) ainda **lê `core.io_manager` (External Table do Google Sheets)** — o legado. Enquanto isso, a fonte canônica real é `core.io_manager_v2` (Firestore), mas o orchestrator não usa ela para o lookup de campaign IDs nas creatives.

#### Camada MARTS

| View/Tabela | Quem cria | Existe em Prod? | Rows | Observação |
|-------------|-----------|-----------------|------|------------|
| `marts.delivery_daily` | init_bq.py (view) | ❌ **Não existe** | — | Criada no código mas não em main() |
| `marts.fact_delivery_daily_v2` | init_bq.py (NUNCA chamado) | ❌ **Não existe** | — | **Raiz de 9+ objetos quebrados** |
| `marts.io_delivery_daily_v4` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | Pipeline V4 ativo |
| `marts.io_schedule_daily_v4` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_calc_daily_v4` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_plan_daily` | init_bq.py (view) | ✅ Sim (View) | 0 rows¹ | Lê marts.delivery_daily (não existe!) |
| `marts.kpi_daily` | init_bq.py (view) | ✅ Sim (View) | 0 rows¹ | |
| `marts.fact_daily_detail` | init_bq.py (view) | ✅ Sim (View) | 0 rows | Depende de siprocal_daily_std que depende de siprocal_daily_materialized ✅ |
| `marts.fact_daily_io` | init_bq.py (view) | ✅ Sim (View) | 0 rows | |
| `marts.io_kpis_daily_v2` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_kpis_daily_v3` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_kpis_daily_by_model_v2` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_kpis_daily_by_model_v3` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_line_actual_daily_v2` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_line_actual_daily_v3` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_line_kpis_daily_v2` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_line_kpis_daily_v3` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_line_plan_daily_v2` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_line_plan_daily_v3` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_line_revenue_daily_v3` | **Não está no código** | ✅ Sim (View) | 0 rows¹ | |
| `marts.io_roas_daily_v3_mat` | **Não está no código** | ✅ Sim (Table) | 0 rows | Materializada, vazia |
| `marts.io_kpis_daily_v3_mat` | **Não está no código** | ✅ Sim (Table) | 0 rows | Materializada, vazia |
| `marts.io_kpis_daily_by_model_v3_mat` | **Não está no código** | ✅ Sim (Table) | 0 rows | Materializada, vazia |
| `marts.io_line_kpis_daily_v3_mat` | **Não está no código** | ✅ Sim (Table) | 0 rows | Materializada, vazia |
| `marts.fact_daily_detail` | init_bq.py (view) | ✅ Sim (View) | 0 rows | |
| `marts.fact_daily_io` | init_bq.py (view) | ✅ Sim (View) | 0 rows | |

¹ Views são 0 rows apenas quando consultadas sem dados no período, não indicam erro.

#### Camada GOLD (totalmente manual — nenhum arquivo Python gerencia)

| Tabela | Rows | Storage |
|--------|------|---------|
| `gold.dim_date` | 1.215 | 0.1 MB |
| `gold.dim_platform` | 3 | 0 MB |
| `gold.dim_client` | 8 | 0 MB |
| `gold.dim_io_line` | 229 | 0.1 MB |
| `gold.dim_creative` | 3.629 | 0.8 MB |
| `gold.fct_delivery_daily` | 4.420 | 1.8 MB |
| `gold.fct_io_plan_daily` | 10.467 | 2.6 MB |
| `gold.fct_luckbet_daily` | 8.065 | 3.7 MB |

**Criação:** `docs/gold_layer_ddl.sql` (executado manualmente no BQ console)  
**Refresh:** Manual — nenhum job automático reconstrói a camada gold

---

## 4. Problemas Críticos Identificados

### P1 — init_bq.py está desincronizado com a realidade (ALTA SEVERIDADE)

O arquivo mais crítico do repositório descreve uma arquitetura que **não existe mais em prod**. Qualquer novo desenvolvedor que ler init_bq.py vai entender o sistema errado. Qualquer execução de `python scripts/init_bq.py` no ambiente de staging vai criar a arquitetura errada (Pipeline A legado).

**Impacto:** Qualquer bootstrap de novo ambiente cria um sistema quebrado.

### P2 — Gold layer sem refresh automático (ALTA SEVERIDADE)

As 3 tabelas de fatos da camada gold (`fct_delivery_daily`, `fct_io_plan_daily`, `fct_luckbet_daily`) são reconstruídas manualmente. O ETL roda diariamente em `raw.*` mas os dados nunca chegam automaticamente no Power BI.

**Impacto:** Dashboards desatualizados se refresh manual for esquecido.

### P3 — core.io_manager_enriched usa Google Sheets legado (MÉDIA SEVERIDADE)

O `orchestrator.py` (linha 723) consulta `core.io_manager_enriched` para obter os `platform_campaign_id` ao fazer o fetch de creatives do MediaSmart. Essa view lê `core.io_manager` que é uma External Table do Google Sheets — o legado com apenas 62 rows. A fonte canônica `core.io_manager_v2` (229 rows, Firestore sync) não é usada aqui.

**Impacto:** O fetch de creatives do MediaSmart consulta apenas 62 IOs antigos, perdendo os ~167 IOs mais recentes que estão somente em `core.io_manager_v2`.

### P4 — Siprocal usa CREATE OR REPLACE (MÉDIA SEVERIDADE)

`orchestrator.py._run_siprocal_external()` faz `CREATE OR REPLACE TABLE raw.siprocal_daily_materialized` em cada execução. Isso **apaga todo o histórico** e recria a tabela com os dados atuais da planilha. Não há registro histórico de entregas diárias do Siprocal.

**Impacto:** Se a planilha do Siprocal for editada retroativamente, o histórico de prod muda.

### P5 — Nenhuma tabela raw tem schema explícito para mgid_daily (BAIXA SEVERIDADE)

`init_bq.py` define `build_raw_mediasmart_daily_schema()` explicitamente, mas para `mgid_daily` confia no autodetect do BigQuery (todos os campos vêm como STRING do orchestrator, via `df.astype(str)`). O stg view faz `SAFE_CAST` depois, mas se a API do MGID retornar um campo novo ou renomear um campo, pode passar silenciosamente sem alerta.

### P6 — Datasets duplicados (raw_*) e backups manuais (P0 em custo)

Já documentado em `bigquery_cleanup_proposal.md`. ~1.147 MB removíveis com risco zero.

### P7 — 13+ views de stg sem representação no código

Foram criadas manualmente via BQ console. Se o ambiente for resetado (ou staging for criado), essas views não existem. Qualquer pipeline que depende delas quebra silenciosamente.

---

## 5. Mapa de Dependências do Pipeline Ativo (V4)

Este é o fluxo **real** de dados de prod, de ponta a ponta:

```
Plataformas                   ETL (orchestrator.py)
┌──────────────┐               ┌──────────────────────────────────────────────┐
│  MediaSmart  │──API──────►  raw.mediasmart_daily (APPEND diário)           │
│  MGID        │──API──────►  raw.mgid_daily (APPEND diário)                 │
│  Siprocal    │──Sheets───►  raw.siprocal_daily_materialized (REPLACE diário)│
│              │──API──────►  raw.mediasmart_creatives (TRUNCATE)             │
│              │──API──────►  raw.mgid_creatives (TRUNCATE)                  │
│              │──API──────►  raw.mediasmart_campaigns                        │
│              │──API──────►  raw.mgid_campaigns                             │
│              │──API──────►  raw.mediasmart_revenue_daily                   │
└──────────────┘               └──────────────────────────────────────────────┘
                                         │ (autodetect STRING)
                                         ▼
                               stg.mediasmart_daily_std (view — cast + join creatives)
                               stg.mgid_daily_std       (view — cast + join creatives)
                               stg.siprocal_daily_std   (view — cast)
                                         │
                                         ▼ (join com io_line_bindings_v2)
                               stg.io_lines_v4          (view — IO config)
                               core.io_line_bindings_v2 (tabela — Firestore sync)
                               core.io_manager_v2       (tabela — Firestore sync)
                                         │
                                         ▼
                               marts.io_delivery_daily_v4   (view — binding_scope filter)
                               marts.io_schedule_daily_v4   (view — planejamento)
                                         │
                                         ▼
                               share.luckbet_sheet_strategy_daily  (view — LuckBet específico)
                               share.io_kpis_daily_v3             (view — KPIs gerais)
                               stg.newad_revenue_daily            (view — receita DSP)
                                         │
                                         ▼  [MANUAL — sem automatização]
                               gold.fct_delivery_daily  (tabela particionada)
                               gold.fct_io_plan_daily   (tabela particionada)
                               gold.fct_luckbet_daily   (tabela particionada)
                               gold.dim_*               (5 dimensões)
                                         │
                                         ▼
                                    Power BI
```

**Firestore → BQ sync** (Admin UI):  
`Admin UI` → `Firestore.platform_reports` → `core.io_manager_v2` via sync  
O sync não está no código do repositório — é gerenciado pelo Admin UI separadamente.

---

## 6. Arquitetura Limpa para Staging

### O que vai ser construído

A arquitetura de staging deve **conter apenas o Pipeline V4**, totalmente gerenciada por código, sem nenhum objeto criado manualmente no BQ console.

#### Princípios da nova arquitetura

1. **Infrastructure as Code completo:** Nenhum objeto BQ existe sem um arquivo no repositório que o cria
2. **Uma única fonte da verdade por layer:** Sem pipelines paralelos, sem versões v2/v3/v4 coexistindo
3. **Gold layer automatizado:** O orchestrator reconstrói os fcts após cada ingestão
4. **Schemas explícitos:** Todas as tabelas raw com SchemaField definido, sem depender de autodetect
5. **Siprocal com histórico:** Append incremental em vez de CREATE OR REPLACE
6. **io_manager sem Google Sheets:** Somente `core.io_manager_v2` (Firestore), External Table removida

#### Estrutura de datasets no staging

```
adframework-stg (projeto GCP)
├── raw/             8 tabelas com schema explícito
├── stg/             6 views (3 normalização + 3 alias)
├── core/            3 tabelas base + 3 views
├── marts/           4 views (somente v4)
├── share/           6 views essenciais + luckbet views
├── gold/            8 tabelas (5 dims + 3 facts)
├── pixel/           3 tabelas base + 7 views
└── adtracking/      3 tabelas base + 1 view
```

**Total staging: ~55 objetos vs. 120 em prod**

---

## 7. Plano de Reestruturação — O Que Muda no Código

### 7.1 init_bq.py — Reescrita completa

O arquivo atual tem 3.490 linhas e descreve uma arquitetura que não existe. A reescrita deve:

**Remover (código morto):**
- `build_marts_fact_delivery_daily_v2()` e todas as funções que dependem dela (9+ funções)
- `build_marts_delivery_daily_view()` — Pipeline A
- `build_marts_pacing_view()`, `build_marts_pacing_daily_view()` — Pipeline A
- `build_core_dim_*_view()` (7 funções) — nunca chamadas
- `build_share_fact_delivery_daily_*()` — nunca chamadas
- `build_share_daily_kpis_view()`, `build_share_campaign_kpis_view()` — nunca chamadas
- Qualquer referência a `core.io_manager` (External Table legado)

**Adicionar (Pipeline V4):**
- Schema explícito para `raw.mgid_daily`
- Schema explícito para `raw.mediasmart_revenue_daily`
- Schema explícito para `raw.mediasmart_bid_supply_daily`
- Schema explícito para `raw.mgid_campaigns`, `raw.mediasmart_campaigns`
- `stg.io_lines_v4` view (SQL completo)
- `stg.newad_revenue_daily` view (SQL completo)
- `marts.io_delivery_daily_v4` view (SQL completo)
- `marts.io_schedule_daily_v4` view (SQL completo)
- `share.luckbet_sheet_strategy_daily` view (SQL completo)
- `share.admin_client_linking_options` view
- Todas as 8 tabelas gold via DDL SQL
- `pixel.*` schemas (atualmente só em pixel_storage.py)

**Resultado esperado:** ~900 linhas em vez de 3.490, descreve exatamente o que existe.

### 7.2 orchestrator.py — 3 mudanças cirúrgicas

**Mudança 1 — Substituir lookup de io_manager_enriched por io_manager_v2:**
```python
# ANTES (linha 722) — lê core.io_manager (Google Sheets, 62 rows)
io_query = f"""
SELECT DISTINCT CAST(platform_campaign_id AS STRING) AS campaign_id
FROM `{project_id}.core.io_manager_enriched`
WHERE LOWER(platform) = 'mediasmart'
"""

# DEPOIS — lê core.io_manager_v2 (Firestore sync, 229 rows)
io_query = f"""
SELECT DISTINCT CAST(platform_campaign_id AS STRING) AS campaign_id
FROM `{project_id}.core.io_manager_v2`
WHERE LOWER(platform) = 'mediasmart'
  AND platform_campaign_id IS NOT NULL
"""
```

**Mudança 2 — Siprocal: append incremental em vez de CREATE OR REPLACE:**
```python
# ANTES — apaga histórico a cada run
materialize_sql = f"CREATE OR REPLACE TABLE `{target_ref}` AS SELECT ..."

# DEPOIS — append apenas registros novos
materialize_sql = f"""
INSERT INTO `{target_ref}`
SELECT ... FROM `{source_ref}` s
WHERE NOT EXISTS (
  SELECT 1 FROM `{target_ref}` t
  WHERE SAFE_CAST(t.day AS DATE) = SAFE_CAST(s.day AS DATE)
)
"""
```

**Mudança 3 — Adicionar refresh da camada gold após ingestão:**
```python
def _rebuild_gold_layer(self, project_id: str) -> None:
    """Reconstrói as tabelas fct_* da camada gold após ingestão diária."""
    client = bigquery.Client(project=project_id)
    gold_ddls = _load_gold_ddls(project_id)  # lê docs/gold_layer_ddl.sql
    for ddl in gold_ddls:
        client.query(ddl).result()
```

### 7.3 CI/CD (.github/workflows/deploy-cloud-run.yml) — Adicionar step de init

```yaml
- name: Initialize BigQuery schema (staging)
  run: |
    cd adframework_python
    GOOGLE_CLOUD_PROJECT="adframework-stg" python scripts/init_bq.py \
      --project adframework-stg \
      --location US
```

Isso garante que toda vez que a branch `staging` receber um push, o BQ de staging é atualizado com os schemas mais recentes.

---

## 8. Objetos a Criar no Staging (Inventário Final)

### Dataset: raw (8 tabelas)

| Tabela | Schema | Partição | Cluster | Ingestão |
|--------|--------|----------|---------|---------|
| `mediasmart_daily` | Explícito (21 campos STRING) | Nenhuma | — | APPEND por day |
| `mediasmart_creatives` | Explícito (12 campos STRING) | Nenhuma | campaign_id | TRUNCATE |
| `mediasmart_campaigns` | Autodetect → migrar para explícito | Nenhuma | — | TRUNCATE |
| `mediasmart_revenue_daily` | Explícito (novo) | Nenhuma | — | APPEND |
| `mediasmart_bid_supply_daily` | Explícito (novo) | day | — | APPEND |
| `mgid_daily` | Explícito (novo) | Nenhuma | — | APPEND |
| `mgid_creatives` | Autodetect → migrar para explícito | Nenhuma | campaignId | TRUNCATE |
| `mgid_campaigns` | Autodetect → migrar para explícito | Nenhuma | — | TRUNCATE |
| `siprocal_daily_materialized` | Explícito (10 campos STRING) | Nenhuma | — | **APPEND incremental** |

### Dataset: stg (6 views)

| View | Lê de | Propósito |
|------|-------|-----------|
| `mediasmart_daily_std` | raw.mediasmart_daily + raw.mediasmart_creatives | Cast + enrich URL |
| `mgid_daily_std` | raw.mgid_daily + raw.mgid_creatives | Cast + enrich URL |
| `siprocal_daily_std` | raw.siprocal_daily_materialized | Cast |
| `io_lines_v4` | core.io_line_bindings_v2 + core.io_manager_v2 | Config IO |
| `newad_revenue_daily` | raw.mediasmart_revenue_daily | Receita DSP |
| `mediasmart_revenue_daily` | raw.mediasmart_revenue_daily | Alias normalizado |

### Dataset: core (6 objetos)

| Objeto | Tipo | Fonte | Gerenciado por |
|--------|------|-------|----------------|
| `io_manager_v2` | Table | Firestore sync (Admin UI) | Admin UI |
| `io_line_bindings_v2` | Table | Admin UI | Admin UI |
| `platform_client_links` | Table | Admin UI | Admin UI |
| `io_manager_enriched_v2` | View | core.io_manager_v2 | init_bq.py |
| `io_binding_registry_v4` | View | io_line_bindings_v2 | init_bq.py |
| `io_registry_v4` | View | io_manager_v2 | init_bq.py |

**Removidos:** `io_manager` (External Table legado), `io_manager_legacy_cache`, `io_manager_enriched` (versão antiga)

### Dataset: marts (4 views)

| View | Lê de | Propósito |
|------|-------|-----------|
| `io_delivery_daily_v4` | stg.*_std + core.io_line_bindings_v2 | Fatos diários com binding |
| `io_schedule_daily_v4` | stg.io_lines_v4 | Planejamento diário |
| `io_calc_daily_v4` | io_delivery_daily_v4 | Cálculos de KPI |
| `fact_daily_detail` | io_delivery_daily_v4 | Detalhe por criativo/device |

**Removidos:** Todas as versões v2/v3, `delivery_daily`, `fact_delivery_daily_v2`, `kpi_daily` legado, 4 tabelas materializadas vazias

### Dataset: share (10 views essenciais)

| View | Propósito |
|------|-----------|
| `io_kpis_daily_v3` | KPIs diários — consumo principal |
| `io_line_kpis_daily_v3` | KPIs por IO line |
| `luckbet_sheet_strategy_daily` | LuckBet por estratégia |
| `luckbet_sheet_campaign_daily` | LuckBet por campanha |
| `luckbet_sheet_plan_map` | Mapa de planejamento LuckBet |
| `admin_client_linking_options` | Admin UI dropdown |
| `pacing_daily` | Pacing diário |
| `mediasmart_creative_daily` | Criativo diário |
| `newad_operational_daily` | Operacional consolidado |
| `report_daily_campaign` | Relatório por campanha (necessário para admin_ui fallback) |

**Removidos:** ~20 views legadas v1/v2 não usadas

### Dataset: gold (8 tabelas — via gold_layer_ddl.sql)

Sem mudanças na estrutura. DDL já está documentado e correto.

### Datasets: pixel e adtracking

Sem mudanças estruturais. Schemas adicionados ao init_bq.py.

---

## 9. Resumo: Prod vs. Staging

| Métrica | Prod Atual | Staging Proposto |
|---------|-----------|-----------------|
| Datasets | 14 | 8 |
| Total de objetos | ~120 | ~55 |
| Pipelines paralelos | 2 (1 quebrado) | 1 (V4 limpo) |
| Objetos gerenciados por código | ~25 (~21%) | **~55 (100%)** |
| Tabelas manuais sem código | ~60 | 0 |
| Código morto em init_bq.py | ~1.500 linhas | 0 |
| Gold refresh automático | Não | **Sim** |
| io_manager via Google Sheets | Sim (legado) | **Não** |
| Siprocal com histórico | Não | **Sim** |
| Storage (excl. finops_billing) | ~1.515 MB | ~250 MB (inicial) |

---

## 10. Sequência de Implementação no Staging

### Sprint 1 — Fundação (2-3 dias)
1. Criar projeto GCP `adframework-stg`
2. Reescrever `init_bq.py` — só Pipeline V4, sem código morto
3. Executar `init_bq.py` no staging → cria raw + stg + core views
4. Importar dados de `core.io_manager_v2` e `core.io_line_bindings_v2` de prod para staging (dump + load)

### Sprint 2 — ETL funcionando (2-3 dias)
5. Corrigir `orchestrator.py` — 3 mudanças (io_manager_v2, siprocal append, gold refresh)
6. Configurar Firestore do staging com os jobs (copy de prod)
7. Push para branch `staging` → GitHub Actions faz deploy automático
8. Rodar ETL no staging, verificar que escreve em `adframework-stg.raw.*`

### Sprint 3 — Camada analítica (1-2 dias)
9. Adicionar ao CI/CD o step de `init_bq.py` que cria marts + share + gold views
10. Executar `gold_layer_ddl.sql` no staging → primeira carga manual da gold
11. Verificar que gold refresh automático funciona após ETL

### Sprint 4 — Validação (3-5 dias)
12. Rodar ETL por 3+ dias em paralelo com prod
13. Comparar row counts e métricas chave entre staging e prod
14. Conectar Power BI no gold layer do staging
15. Validar dashboards LuckBet + pacing

### Sprint 5 — Cutover (1 dia)
16. Mudar Cloud Scheduler para apontar para staging
17. Confirmar que prod + staging produzem os mesmos números no último dia
18. Staging vira o novo prod

---

*Documento gerado em 2026-04-30. Para dúvidas: Douglas Reche.*

---

## 11. Novos Achados e Correções — Sessão 2026-05-05

> Atualizações feitas após análise da planilha Lille + auditoria do Power BI via MCP.

---

### 11.1 Gold Layer — Convertida de Tables para Views ✅

**Problema anterior (P2):** Gold layer sem refresh automático — tabelas reconstruídas manualmente.

**Resolução executada em prod:** As 8 tabelas foram dropadas e recriadas como `CREATE OR REPLACE VIEW`. Agora refletem o estado atual do pipeline automaticamente, sem refresh manual.

| View | Fonte |
|------|-------|
| `gold.dim_client` | `stg.io_lines_v4` |
| `gold.dim_platform` | `stg.io_lines_v4` |
| `gold.dim_date` | `GENERATE_DATE_ARRAY(2025–2027)` |
| `gold.dim_io_line` | `stg.io_lines_v4` (com normalização) |
| `gold.dim_creative` | `share.newad_creative_daily` |
| `gold.fct_io_plan_daily` | `marts.io_schedule_daily_v4` |
| `gold.fct_delivery_daily` | `share.io_calc_daily_v4` + `share.newad_revenue_daily` |
| `gold.fct_luckbet_daily` | `share.luckbet_sheet_strategy_daily` + join `stg.io_lines_v4` |
| `gold.fct_creative_daily` *(novo)* | `share.platform_daily_detail` — filtrado sem linhas zero-metric |

**P2 resolvido.** O doc do staging (Section 8) ainda lista gold como tabelas — atualizar quando for para staging.

---

### 11.2 Double-Counting no Projetado — Raiz Identificada e Corrigida ✅

**Problema:** Ao somar `budget_total` de `dim_io_line` para LuckBet março/2026 o resultado era ~R$731k em vez de R$365k.

**Causa raiz:** Para o mesmo `(newad_client_id, proposal_month, platform_campaign_id)`, o `core.io_manager_v2` continha dois registros:
- IO consolidado `_001` (10 linhas, distribuição orçamentária diferente — versão antiga do plano)
- IOs individuais `_003` a `_012` (1 linha por campanha, distribuição atual)

A planilha Lille foi usada como referência para validação: os budgets dos IOs `_003`-`_012` batem exatamente com os valores da planilha. O `_001` é versão supersedida.

**Resolução em prod:** `stg.io_lines_v4` reescrita com deduplicação:
```sql
ROW_NUMBER() OVER (
  PARTITION BY newad_client_id, proposal_month, platform_campaign_id
  ORDER BY io_id DESC  -- io_id maior = versão mais recente
)
```
Apenas o IO mais recente por campanha/mês é mantido.

**⚠ Open question:** A campanha `uvachnidmgdf6jwjxogqplurkcheovcl` ("Retenção 2") aparece no `_001` de março com R$25.307 mas **não consta na planilha Lille de março** (era uma campanha de fevereiro). Com o dedup atual, ela é mantida (único IO para essa campanha em março). **Aguarda confirmação do Shiro se é dado correto ou erro de cadastro.**

---

### 11.3 Corrupção de Dados em dim_io_line — Normalização Aplicada ✅

**Problema detectado via análise Power BI (MCP):**

`dim_io_line.buying_model` continha valor numérico `"476190.4762"` — era o `deliverable_volume` salvo no campo errado por bug do Admin UI em IOs antigos de 2025.

`dim_io_line.deliverable_metric` continha 7 valores inconsistentes:
- `"Impressões"`, `"Cliques"` (português — deveriam ser `IMPRESSIONS`/`CLICKS`)
- `"4277777.778"`, `"6526315.7895"` (volumes numéricos no campo de tipo)
- `"***"` (placeholder)
- `NULL`s

**Causa raiz:** Bug de input no Admin UI em IOs `_002` de Set/Out/Nov 2025 — o campo `deliverable_metric` recebia o valor calculado de `deliverable_volume` ao invés do tipo de entrega.

**Resolução em prod:** `gold.dim_io_line` aplica normalização via CASE:
```sql
CASE
  WHEN UPPER(buying_model) IN ('CPC','CPM') THEN UPPER(buying_model)
  ELSE NULL
END AS buying_model,

CASE
  WHEN UPPER(deliverable_metric) IN ('IMPRESSIONS','IMPRESSÕES','IMPRESSOES') THEN 'IMPRESSIONS'
  WHEN UPPER(deliverable_metric) IN ('CLICKS','CLIQUES') THEN 'CLICKS'
  WHEN UPPER(buying_model) = 'CPM' AND (
    SAFE_CAST(deliverable_metric AS FLOAT64) IS NOT NULL
    OR deliverable_metric = '***'
  ) THEN 'IMPRESSIONS'
  WHEN UPPER(buying_model) = 'CPC' AND (
    SAFE_CAST(deliverable_metric AS FLOAT64) IS NOT NULL
    OR deliverable_metric = '***'
  ) THEN 'CLICKS'
  ELSE UPPER(deliverable_metric)
END AS deliverable_metric
```

**Ação pendente no Admin UI:** Validar campos `buying_model` e `deliverable_metric` no formulário de cadastro de IO para rejeitar valores numéricos.

---

### 11.4 fct_creative_daily — Nova View Gold para Criativos ✅

**Problema (identificado via Power BI MCP):** A tabela `fct_delivery_detail_daily` no Power BI estava conectada a uma fonte com 81k linhas brutas, onde a maioria eram linhas de rastreamento de banner sem nenhuma métrica (impressions=0, clicks=0, video=0). Isso inflava contagens e travava performance.

**Resolução em prod:** Nova view `gold.fct_creative_daily` criada:
- Fonte: `share.platform_daily_detail` (cobre MediaSmart, MGID, Siprocal)
- Filtro: `WHERE NOT (impressions=0 AND clicks=0 AND video_start=0 AND video_completed=0)`
- Adiciona `io_id` e `newad_client_id` via LEFT JOIN com `stg.io_lines_v4`

**Ação pendente no Power BI:** Reconectar `fct_delivery_detail_daily` para `adframework.gold.fct_creative_daily`.

---

### 11.5 Achados Power BI — Análise MCP (2026-05-05)

Problemas identificados no modelo Power BI que precisam de ação fora do BigQuery:

| # | Problema | Severidade | Onde corrigir |
|---|----------|-----------|---------------|
| 1 | `Qtd Campanhas Ativas` referencia `campaign_id` inexistente | 🔴 Quebrado | Power BI (DAX) |
| 2 | Relacionamento `fct_io_plan_daily → dim_io_line` **INATIVO** | 🔴 Quebrado | Power BI (modelo) |
| 3 | `fnt_RAW_Campaign` sem relacionamentos — DirectQuery | 🔴 Sem impacto visual | Power BI |
| 4 | `fnt_RAW_Campaign[funnel/objective/target_device]` com dados corrompidos | 🔴 Bug pipeline | `share.pacing_daily_by_source` (Pydantic bug) |
| 5 | `fct_io_plan_v2` derivada de `dim_io_line` via Power Query hardcoded | ⚠️ Frágil | Power BI |
| 6 | CTR e CTR% medidas duplicadas | ⚠️ Redundância | Power BI |
| 7 | `dim_month` redundante (derivada de dim_date) | ⚠️ Limpeza | Power BI |

**P4 original (`fnt_RAW_Campaign` corrompido):** Investigar `share.pacing_daily_by_source` — suspeita de bug de serialização Pydantic/dataclass nos campos `funnel`, `objective`, `target_device` do pipeline.

---

### 11.6 Validação do Projetado via Planilha Lille

A planilha Lille (modelo de distribuição de IO para clientes) foi usada como fonte de verdade para validar os valores de `budget_total` na camada gold. Conclusões:

- **Os IOs individuais `_003`-`_012` batem 100% com os valores da planilha** → fonte canônica confirmada
- **O IO consolidado `_001` usa distribuição orçamentária diferente** → versão antiga, não deve ser somada
- **`budget_total` em `fct_luckbet_daily` não deve ser somado diretamente** no Power BI (é o total mensal repetido por linha diária). Usar `MAX(planned_investment)` por campanha/mês ou `dim_io_line.budget_total` (1 linha por IO line, já deduplicado)

---

### 11.7 Prioridades de Cleanup — Camada por Camada (Reunião 2026-05-05)

A abordagem acordada é limpeza incremental de baixo para cima, sem depender da construção do staging:

**Camada RAW — executar primeiro (baixo risco)**
- Deletar backups manuais `raw.*_legacy_*` (~400 MB) — já detalhado em `bigquery_cleanup_proposal.md` Fase 1
- Deletar `raw.mediasmart_daily_creative` e `raw.mediasmart_daily_operational` (0 rows)
- Deletar `raw.siprocal_daily` (External Table inativa, 0 rows)
- Deletar datasets `raw_*` órfãos (~747 MB) — `bigquery_cleanup_proposal.md` Fase 2

**Camada STG — após raw**
- Remover 13 views manuais sem documentação que nunca são usadas pelo pipeline V4
- Manter apenas: `mediasmart_daily_std`, `mgid_daily_std`, `siprocal_daily_std`, `io_lines_v4`, `newad_revenue_daily`, `mediasmart_revenue_daily`

**Camada CORE — após stg**
- Remover `core.io_manager` (External Table Google Sheets legado)
- Remover `core.io_manager_legacy_cache`
- Remover `core.io_manager_enriched` (versão antiga que lê o Google Sheets)
- Remover `core.proposals` e `core.proposal_lines` (0 rows, nunca usadas)

**Camada MARTS — após core**
- Remover 4 tabelas materializadas vazias (`*_mat`)
- Remover views v2/v3 não utilizadas pelo pipeline V4
- Manter apenas: `io_delivery_daily_v4`, `io_schedule_daily_v4`, `io_calc_daily_v4`

**Camada SHARE — após marts**
- Remover ~20 views legadas v1/v2 sem consumidores ativos
- Manter: views v3/v4 + luckbet_* + operational + pacing

**Camada GOLD — já resolvida ✅**
- Convertida para views automáticas em 2026-05-05
- Nenhuma ação adicional necessária (exceto fix Power BI listado em 11.5)
