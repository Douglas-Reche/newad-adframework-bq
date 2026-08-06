# AdFramework — Auditoria de Linhagem de Dados: RAW → GOLD

---
> **⚠️ LEGADO — PRÉ-REBUILD 2026-06-16 ⚠️**
> Este documento descreve a pipeline **anterior ao reset completo de 2026-06-16**.
> Tabelas, views, schemas e colunas aqui descritos **foram dropados e não existem mais no BigQuery**.
> Mantenha para consulta histórica — **não use como referência para desenvolvimento novo.**
> Plano atual: [bq_restructuring_plan.md](../bq_restructuring_plan.md) · [CHANGELOG.md](../../CHANGELOG.md)
> Movido para `docs/_legacy/` em 2026-08-05 (referência histórica confirmada por Douglas).
---
**Data:** 2026-05-26  
**Elaborado por:** Douglas Reche  
**Para:** Reunião de auditoria com Shiro  
**Escopo:** Todas as camadas BigQuery — rastreamento de dados ponta a ponta, identificação de quebras de linhagem, objetos órfãos, problemas de qualidade e plano de ação

---

## Índice

1. [Resumo Executivo](#1-resumo-executivo)
2. [RAW — Ingestão das Plataformas](#2-raw--ingestão-das-plataformas)
3. [STG — Staging e Transformação](#3-stg--staging-e-transformação)
4. [CORE — Plano de Mídia e Bindings](#4-core--plano-de-mídia-e-bindings)
5. [MARTS — Camada Analítica Intermediária](#5-marts--camada-analítica-intermediária)
6. [SHARE — Consumo e Relatórios](#6-share--consumo-e-relatórios)
7. [GOLD — Star Schema (Power BI)](#7-gold--star-schema-power-bi)
8. [Problemas Transversais — Qualidade de IDs e Clientes](#8-problemas-transversais--qualidade-de-ids-e-clientes)
9. [Infraestrutura e Código](#9-infraestrutura-e-código)
10. [Matriz de Prioridades](#10-matriz-de-prioridades)
11. [Perguntas Abertas para o Shiro](#11-perguntas-abertas-para-o-shiro)
12. [Resumo dos Achados por Camada](#12-resumo-dos-achados-por-camada)

---

## 1. Resumo Executivo

O projeto BigQuery `adframework` (`striped-bonfire-489318-t9`) tem **dois pipelines paralelos** coexistindo:

| Pipeline | Status | Onde fica |
|----------|--------|-----------|
| **Pipeline A — Legado** | 🔴 Quebrado — objeto raiz nunca criado | `marts.fact_delivery_daily_v2` (inexistente) |
| **Pipeline B — V4** | ✅ Ativo, alimenta o Power BI | `marts.io_delivery_daily_v4` → gold |

O Pipeline B funciona, mas foi construído inteiramente **fora do código** (criado manualmente no BQ console). Se o ambiente for resetado ou um staging for criado, ele não existe.

**Os maiores riscos de linhagem identificados:**

| # | Risco | Camada | Impacto |
|---|-------|--------|---------|
| 1 | ~1.147 MB de dados duplicados/obsoletos (raw_* + backups fev/26) | RAW | Custo de storage + confusão operacional |
| 2 | 13 views STG + 6 views CORE + todas as views V4 de marts fora do código | STG/CORE/MARTS | Staging zerado = pipeline quebrado |
| 3 | `orchestrator.py` usa `io_manager_enriched` (legado, 62 IOs) para fetch de criativos | CORE | 73% dos IOs sem criativo atualizado |
| 4 | Siprocal: `CREATE OR REPLACE` destrói histórico a cada ETL | RAW | Histórico Siprocal inexistente |
| 5 | Luckbet: dois `newad_client_id` para o mesmo anunciante | CORE/GOLD | Delivery contada 2–3x em todas as views gerais |
| 6 | Cora: ~1.2M impressões não capturadas (MGID/Siprocal sem IO binding pré-março) | CORE/GOLD | Gap permanente até Shiro criar IOs retroativos |
| 7 | 2 campanhas Luckbet sem IO (5.47M + 479K impressões) | CORE | Dados invisíveis na gold |
| 8 | `io_id` determinístico (slug): colisão quando `io_number` em branco | CORE | IO sobrescrito silenciosamente |

---

## 2. RAW — Ingestão das Plataformas

### 2.1 Inventário das Tabelas Ativas

| Tabela | Rows | Última atualização | Ingerida por |
|--------|------|--------------------|-------------|
| `raw.mediasmart_daily` | 638.685 | Diário (~08h BRT) | `orchestrator.py` |
| `raw.mediasmart_creatives` | 20.353 | Diário (TRUNCATE) | `orchestrator.py` |
| `raw.mediasmart_campaigns` | 2.016 | Diário | `orchestrator.py` |
| `raw.mediasmart_revenue_daily` | 8.075 | — | **Não está no código** ⚠️ |
| `raw.mediasmart_bid_supply_daily` | 602.179 | — | **Não está no código** ⚠️ |
| `raw.mgid_daily` | 4.098 | Diário (~08h BRT) | `orchestrator.py` |
| `raw.mgid_creatives` | 9.314 | Diário | `orchestrator.py` |
| `raw.mgid_campaigns` | 12.907 | Diário | `orchestrator.py` |
| `raw.mgid_daily_device` | 803 | — | **Não está no código** ⚠️ |
| `raw.siprocal_daily_materialized` | 706 | 2026-04-30 | `orchestrator.py` ⚠️ |
| `raw.siprocal_daily` | 0 | — | External Table inativa |
| `raw.siprocal_daily_native` | 706 | — | **Não está no código** ⚠️ |

### 2.2 Achados Críticos na Camada RAW

#### F-RAW-1 🔴 Siprocal: CREATE OR REPLACE destrói histórico
`orchestrator.py._run_siprocal_external()` executa `CREATE OR REPLACE TABLE raw.siprocal_daily_materialized` a cada run. A tabela tem apenas **706 linhas** — todos provavelmente da mesma data. Se a planilha Siprocal for editada retroativamente, o histórico de prod muda. Não há acumulação histórica.

**Sugestão:** Mudar para INSERT incremental (`WHERE date NOT IN (SELECT DISTINCT date FROM raw.siprocal_daily_materialized)`).

#### F-RAW-2 🔴 ~1.147 MB de dados obsoletos e duplicados
Três grupos de lixo acumulado:

| Grupo | Tamanho | Conteúdo |
|-------|---------|----------|
| Backups fev/2026 em `raw` (5 tabelas) | ~400 MB | `mediasmart_daily_legacy_20260227_*`, `backup_*`, `mgid_legacy_*` — dados já presentes em `raw.mediasmart_daily` |
| Datasets `raw_mediasmart` + `raw_mgid` + `raw_siprocal` + `raw_newadframework` (snapshots órfãos) | ~747 MB | Criados em 2026-04-21, ETL nunca foi atualizado para escrever aqui. Congelados em 2026-04-19. **Nenhuma view ou script lê esses datasets.** |
| Tabelas vazias: `raw.mediasmart_daily_creative`, `raw.mediasmart_daily_operational` | ~0 MB | 0 linhas, nunca populadas |

**Sugestão:** DROP imediato — risco zero comprovado (nenhuma view aponta para eles).

#### F-RAW-3 🟡 Inconsistência de nomes de colunas entre plataformas

| Conceito | MediaSmart (raw) | MGID (raw) | Siprocal (raw) | STG (unificado) |
|----------|----------------|-----------|--------------|-|
| Campaign ID | `controlid` | `campaignid` | `campaign_id` | `platform_campaign_id` |
| Advertiser ID | `eventid` | *(não existe)* | `advertiser` | `advertiser_platform_id` |

O STG unifica os nomes. **O ponto de falha silenciosa está no JOIN da STG com o CORE** — se o CAST ou TRIM estiver errado, a entrega desaparece sem erro.

#### F-RAW-4 🟡 MGID salvo como STRING (autodetect)
`orchestrator.py` grava `mgid_daily` com `df.astype(str)` — todos os campos chegam como STRING no BigQuery. O STG faz `SAFE_CAST` para INT64, mas se a API do MGID retornar um campo novo ou renomear algo, o CAST falha silenciosamente (retorna NULL).

**Sugestão:** Adicionar schema explícito (`bigquery.SchemaField`) para `raw.mgid_daily` em `init_bq.py`.

#### F-RAW-5 🟡 Tabelas criadas manualmente sem documentação
`raw.mediasmart_revenue_daily`, `raw.mediasmart_bid_supply_daily` e `raw.mgid_daily_device` existem em prod mas não aparecem em nenhum arquivo do repositório. Se o ambiente for resetado, elas não serão recriadas.

---

## 3. STG — Staging e Transformação

### 3.1 Inventário das Views

| View | Gerenciada por código? | Usada pelo pipeline V4? |
|------|----------------------|------------------------|
| `stg.mediasmart_daily_std` | ✅ `init_bq.py` | ✅ Sim |
| `stg.mgid_daily_std` | ✅ `init_bq.py` | ✅ Sim |
| `stg.siprocal_daily_std` | ✅ `init_bq.py` | ✅ Sim |
| `stg.mediasmart_daily` *(alias)* | ✅ `init_bq.py` | ✅ Sim |
| `stg.mgid_daily` *(alias)* | ✅ `init_bq.py` | ✅ Sim |
| `stg.siprocal_daily` *(alias)* | ✅ `init_bq.py` | ✅ Sim |
| `stg.io_lines_v4` | ❌ **Manual — BQ console** | ✅ **Crítica** |
| `stg.newad_revenue_daily` | ❌ **Manual — BQ console** | ✅ Crítica |
| `stg.mediasmart_revenue_daily` | ❌ Manual | ⚠️ Verificar uso |
| `stg.mediasmart_operational_daily` | ❌ Manual | ⚠️ Legado |
| `stg.mediasmart_operational_v2` | ❌ Manual | ⚠️ Legado |
| `stg.mediasmart_creative_daily` | ❌ Manual | ⚠️ Verificar |
| `stg.mediasmart_bid_supply_daily` | ❌ Manual | ⚠️ Verificar |
| `stg.mgid_operational_v2` | ❌ Manual | ⚠️ Legado |
| `stg.newad_creative_daily` | ❌ Manual | ⚠️ Verificar |
| `stg.newad_daily` | ❌ Manual | ⚠️ Legado |
| `stg.newad_operational_daily` | ❌ Manual | ✅ Crítica (fonte de fct_cora) |

**Resumo:** 19 views em prod. Apenas 6 estão em código. **13 views foram criadas manualmente** — incluindo `stg.io_lines_v4` e `stg.newad_operational_daily`, que são pilares do pipeline.

### 3.2 Achados Críticos na Camada STG

#### F-STG-1 🔴 stg.io_lines_v4 não existe no código
Esta é a view mais crítica do pipeline V4 — une `core.io_manager_v2` com `core.io_line_bindings_v2` e alimenta toda a camada de planejamento. **Não existe em nenhum arquivo `.sql` ou `.py` do repositório.**

Se o BQ for resetado: toda a camada de planejamento (schedule, budget, IO lines) desaparece.

**Sugestão:** Extrair o DDL desta view do BQ (`INFORMATION_SCHEMA.VIEWS`) e registrar em `sql/stg/io_lines_v4.sql`.

#### F-STG-2 🔴 Dependência invertida arquitetural
`marts.io_delivery_daily_v4` — a view central de entrega — depende de views da camada `share`:

```
share.newad_operational_daily    ← combina MediaSmart + MGID + Siprocal
share.platform_campaign_catalog  ← catálogo de campanhas
```

Marts deveria ser base de share, não o contrário. Em prod isso funciona (BQ permite). No staging limpo, as views `share.*` precisam ser criadas **antes** de `marts.io_delivery_daily_v4`.

#### F-STG-3 🟡 Nome de campo muda silenciosamente ao cruzar a fronteira STG→SHARE

```
raw.mediasmart_daily.eventid
  → stg.mediasmart_daily.event_id          (snake_case adicionado)
    → stg.mediasmart_operational_v2.advertiser_platform_id  (renomeado)
      → share.newad_operational_daily.advertiser_platform_id
        = core.platform_client_links.link_value              ← JOIN crítico
```

Se os valores não baterem exatamente (case, espaço extra, formato), o cliente desaparece da gold **sem nenhum erro visível**.

---

## 4. CORE — Plano de Mídia e Bindings

### 4.1 Inventário das Tabelas

| Objeto | Tipo | Rows | Gerenciado por | Status |
|--------|------|------|----------------|--------|
| `core.io_manager_v2` | Table | 229 | Admin UI → Firestore → BQ | ✅ Fonte canônica |
| `core.io_line_bindings_v2` | Table | 170 | Admin UI → Firestore → BQ | ✅ Ativo |
| `core.platform_client_links` | Table | 27 | Admin UI → Firestore → BQ | ✅ Ativo |
| `core.io_manager` | External Table | 62 | `init_bq.py` | ⚠️ **Legado — Google Sheets** |
| `core.io_manager_legacy_cache` | Table | 62 | Manual | ⚠️ Cache de legado |
| `core.io_manager_enriched` | View | — | `init_bq.py` | 🔴 **Lê Google Sheets legado** |
| `core.io_manager_enriched_v2` | View | — | Manual | ✅ Lê io_manager_v2 |
| `core.io_binding_registry_v4` | View | — | Manual | ✅ Ativo |
| `core.io_registry_v4` | View | — | Manual | ✅ Ativo |
| `core.io_line_bindings_enriched_v2` | View | — | Manual | ✅ Ativo |
| `core.proposals` | Table | 0 | Manual | 🗑️ Vazia |
| `core.proposal_lines` | Table | 0 | Manual | 🗑️ Vazia |

### 4.2 Achados Críticos na Camada CORE

#### F-CORE-1 🔴 orchestrator.py usa io_manager legado (62 IOs) para fetch de criativos
`orchestrator.py` linha ~722 consulta `core.io_manager_enriched` para obter os `platform_campaign_id` ao fazer fetch de criativos do MediaSmart. **`core.io_manager_enriched` lê `core.io_manager` — a External Table do Google Sheets com apenas 62 IOs (legado).**

A fonte canônica `core.io_manager_v2` tem **229 IOs** (Firestore sync). Resultado: os criativos de **167 IOs** (~73%) nunca são buscados.

**Sugestão:** Substituir na linha ~722 do `orchestrator.py`:
```python
# DE: core.io_manager_enriched (lê Google Sheets, 62 IOs)
# PARA: core.io_manager_v2 (lê Firestore, 229 IOs)
```

#### F-CORE-2 🔴 Nenhum sync automático Firestore → BQ
As três tabelas que alimentam toda a linhagem (`io_manager_v2`, `io_line_bindings_v2`, `platform_client_links`) são sincronizadas do Firestore **manualmente**. Não existe job ou Cloud Function que faça isso automaticamente.

**Perguntas para Shiro:**
- Quem executa o sync? Com que frequência?
- Qual o lag máximo entre criar um IO no Admin UI e ele aparecer na gold?

**Sugestão:** Cloud Function disparada por Firestore `onWrite` que atualiza as tabelas BQ correspondentes.

#### F-CORE-3 🔴 io_id determinístico — risco de colisão por sobrescrita silenciosa
`io_id` é gerado como `io_{slug(io_number)}`. Se `io_number` for deixado em branco ao cadastrar um IO no Admin UI, dois IOs do mesmo anunciante geram o **mesmo `io_id`**. O segundo `.set()` no Firestore sobrescreve o primeiro silenciosamente. O BQ herda o dado errado.

**Sugestão:** Tornar `io_number` campo obrigatório e validar unicidade antes de salvar; ou trocar para UUID aleatório.

#### F-CORE-4 🟡 Coexistência de io_manager (legado) e io_manager_v2 (novo) sem separação clara
`core.io_manager` (External Table → Google Sheets, 62 linhas) e `core.io_manager_v2` (Firestore, 229 linhas) têm nomes semelhantes mas dados completamente diferentes. Qualquer desenvolvedor novo vai usar o objeto errado por confusão de nomenclatura.

**Sugestão:** Após migrar `orchestrator.py` para usar `io_manager_v2`, dropar `core.io_manager`, `core.io_manager_legacy_cache` e `core.io_manager_enriched`.

#### F-CORE-5 🟡 platform_client_links não garante unicidade de link_value por plataforma
Nada impede dois `newad_client_id` diferentes de ter o mesmo `link_value` na mesma plataforma. Isso **já aconteceu** (Luckbet tem dois client IDs apontando para o mesmo event_id no MediaSmart). O resultado é entrega contada múltiplas vezes.

---

## 5. MARTS — Camada Analítica Intermediária

### 5.1 Os Dois Pipelines Paralelos

#### Pipeline A — Legado (QUEBRADO)

| View | Status | Motivo |
|------|--------|--------|
| `marts.fact_delivery_daily_v2` | ❌ **Não existe** | Função definida em `init_bq.py` mas **nunca chamada** em `main()` |
| `marts.delivery_daily` | ❌ Não existe | Idem |
| `marts.fact_daily_detail` | 0 linhas | Lê `stg.siprocal_daily_std` (OK) mas também `core.io_manager_enriched` (legado) |
| `marts.fact_daily_io` | 0 linhas | Depende de `fact_daily_detail` |
| `marts.io_plan_daily` | 0 linhas | Lê `marts.delivery_daily` (não existe) |
| `marts.kpi_daily` | 0 linhas | Lê `marts.fact_delivery_daily_v2` (não existe) |

**Raiz do problema:** `init_bq.py` tem ~1.500 linhas de código morto que descrevem o Pipeline A. A função `build_marts_fact_delivery_daily_v2()` existe no arquivo, mas `main()` nunca a chama. A view nunca foi criada em prod. Todo o cascata de views que a referencia retorna erro ou 0 linhas.

#### Pipeline B — V4 (ATIVO)

| View | Status | Gerenciada por código? |
|------|--------|----------------------|
| `marts.io_delivery_daily_v4` | ✅ Ativo | ❌ Manual |
| `marts.io_schedule_daily_v4` | ✅ Ativo | ❌ Manual |
| `marts.io_calc_daily_v4` | ✅ Ativo | ❌ Manual |

**Crítico:** As 3 views do pipeline V4 funcionam mas **não existem em nenhum arquivo do repositório**.

### 5.2 Achados Críticos na Camada MARTS

#### F-MART-1 🔴 init_bq.py descreve uma arquitetura que não existe em prod
Qualquer nova execução de `python scripts/init_bq.py` vai criar o Pipeline A legado no ambiente alvo (staging, novo dev, etc.). O Pipeline V4 não será criado. O resultado é um ambiente que parece funcional mas não produz dados na gold.

**14 funções definidas em `init_bq.py` que nunca são chamadas em `main()`:** `build_marts_fact_delivery_daily_v2`, `build_marts_pacing_view`, `build_core_dim_platform_view`, `build_core_dim_campaign_view`, `build_core_dim_device_view`, `build_core_dim_format_view`, `build_core_dim_creative_view`, `build_share_fact_delivery_daily_view`, e mais 6.

**Sugestão:** Reescrever `init_bq.py` (~3.490 → ~900 linhas) removendo código morto e adicionando o Pipeline V4.

#### F-MART-2 🟡 4 tabelas materializadas vazias — nunca atualizadas
`marts.io_kpis_daily_v3_mat`, `marts.io_kpis_daily_by_model_v3_mat`, `marts.io_line_kpis_daily_v3_mat`, `marts.io_roas_daily_v3_mat` — todas com 0 linhas. Foram criadas como materializadas mas nenhum job as popula.

**Sugestão:** DROP imediato.

---

## 6. SHARE — Consumo e Relatórios

### 6.1 Inventário por Status

| Grupo | Views | Status |
|-------|-------|--------|
| **Ativas — fundação do Pipeline V4** | `newad_operational_daily`, `platform_daily_detail`, `platform_campaign_catalog`, `io_calc_daily_v4`, `newad_revenue_daily` | ✅ Críticas — manter |
| **Ativas — LuckBet** | `luckbet_sheet_strategy_daily`, `luckbet_sheet_campaign_daily`, `luckbet_sheet_plan_map` | ✅ Manter |
| **Ativas — Admin UI** | `admin_client_linking_options` | ✅ Manter |
| **Ativas — verificar uso** | `adops_mediasmart_bid_supply_*`, `io_kpis_daily_v3`, `io_line_kpis_daily_v3`, `pacing_daily` | ⚠️ Verificar antes de remover |
| **Legadas — encadeadas no Pipeline A quebrado** | `report_daily_*` (~8 views), `kpi_daily`, `io_kpis_daily_v2`, `io_line_kpis_daily_v2`, `pacing_daily_*`, `dashboard_cards_*` | 🔴 Quebradas (dependem de `marts.fact_delivery_daily_v2`) |
| **Legadas — versões paralelas obsoletas** | `io_kpis_daily_by_model_v2/v3`, `io_line_actual_daily_v2/v3`, `io_line_plan_daily_v2/v3`, `io_line_revenue_daily_v3` | 🗑️ Remover |
| **Dados de teste** | `report_daily_campaign_demo` | 🗑️ Remover |

**Total: ~67 objetos, estimativa: ~20 vivos, ~40 legados/quebrados, ~7 incertos.**

### 6.2 Achados Críticos na Camada SHARE

#### F-SHARE-1 🔴 Admin UI fallback aponta para view legada
Em `admin_ui/app/main.py`:
```python
BQ_LINKING_CAMPAIGN_TABLE = "admin_client_linking_options"   # ✅ ativo
BQ_LINKING_FALLBACK_TABLE  = "report_daily_campaign"         # 🔴 legado — Pipeline A
```
Se o Admin UI não encontrar dados na primeira tabela, cai no fallback que depende de `core.io_manager` (Google Sheets). Corromperia a UI silenciosamente.

**Sugestão:** Substituir fallback por `admin_client_linking_options` também, ou remover a lógica de fallback.

#### F-SHARE-2 🟡 ~40 views legadas consomem slots de query se acessadas
As views encadeadas do Pipeline A retornam 0 linhas ou erro, mas ainda existem e aparecem na listagem do BQ console. Qualquer AdOps que tentar usar `share.kpi_daily`, `share.report_daily_campaign` ou `share.pacing_daily` vai ver dados falsos ou não vai ver nada — sem mensagem de erro clara.

**Sugestão:** Após confirmar zero uso via `INFORMATION_SCHEMA.JOBS` (últimos 60 dias), executar DROP em cascata a partir dos objetos mais dependentes.

#### F-SHARE-3 🟡 Dependência invertida confirmada (ver F-STG-2)
`share.newad_operational_daily` alimenta `marts.io_delivery_daily_v4`. A ordem de criação em staging deve ser: `stg → core → share.newad_operational_daily + share.platform_campaign_catalog → marts.io_delivery_daily_v4 → share.restante → gold`.

---

## 7. GOLD — Star Schema (Power BI)

### 7.1 Inventário Atual das Views Gold

| View | Descrição | Estado |
|------|-----------|--------|
| `gold.fct_delivery_daily` | Entrega geral de todos os clientes via pipeline padrão | ✅ View automática |
| `gold.fct_delivery_daily_mvp` | Versão corrigida: remove phantom nwd_internal_newad, dedup binding_scope | ✅ View automática |
| `gold.fct_cora_delivery_full` | MVP workaround Cora: 3 caminhos de atribuição (MS + MGID reg + MGID unreg) | ✅ View automática |
| `gold.fct_luckbet_delivery_full` | MVP workaround Luckbet: elimina double-count dos 2 client IDs | ✅ View automática |
| `gold.fct_newad_bet_daily` | Vista vertical Bet (Luckbet) com nomes de negócio, KPIs calculados | ✅ View automática |
| `gold.fct_newad_fintech_daily` | Vista vertical Fintech (Cora) com nomes de negócio, KPIs calculados | ✅ View automática |
| `gold.fct_creative_daily` | Criativos com entrega (filtro zero-metric aplicado) | ✅ View automática |
| `gold.fct_io_plan_daily` | Planejamento diário por IO line | ✅ View automática |
| `gold.fct_luckbet_daily` | View Luckbet via share.luckbet_sheet_strategy_daily | ✅ View automática |
| `gold.dim_io_line` | Dimensão IO com normalização de buying_model/deliverable_metric | ✅ View automática |
| `gold.dim_client` | Dimensão de clientes | ✅ View automática |
| `gold.dim_creative` | Dimensão de criativos | ✅ View automática |
| `gold.dim_date` | Calendário 2025–2027 | ✅ View automática |
| `gold.dim_platform` | Plataformas (3 linhas) | ✅ View automática |
| `gold.dim_client_semantics` | Mapeamento semântico de conv1–5 por cliente | ✅ View automática |

**Gold layer convertida para views em 2026-05-05** — refresh automático, sem necessidade de rebuild manual.

### 7.2 Achados Críticos na Camada GOLD

#### F-GOLD-1 🔴 Cora: ~1.2M impressões fora do pipeline (14.4M de 15.6M capturados)
O `fct_cora_delivery_full` captura ~14.4M impressões (Jan–Mai 2026) via 3 caminhos de atribuição. A diferença de ~1.2M corresponde a campanhas MGID/Siprocal **anteriores a março de 2026** que nunca foram registradas na `io_binding_registry_v4`.

**Ação necessária do Shiro:** Criar IO bindings retroativos para as campanhas MGID/Siprocal da Cora de Ago/2025–Fev/2026.

#### F-GOLD-2 🔴 Luckbet: dois campaign IDs MediaSmart órfãos (6M impressões invisíveis)

| campaign_id | Impressões | Período |
|------------|-----------|---------|
| `35ey8fny8gizx3vfxwac4ft1xjitbfbe` | 5,47M | Abr/26 |
| `toarsf57a3lky0xmw7w16m4e68iqt5xy` | 479K | Set/25 |

Estas campanhas têm entrega real em `raw.mediasmart_daily` mas **nunca foram vinculadas a nenhum IO** no Admin UI. Não aparecem em nenhuma view gold.

**Ação necessária do Shiro:** Criar IO bindings para estas campanhas no Admin UI.

#### F-GOLD-3 🔴 fct_delivery_daily padrão não serve para Luckbet e Cora
A view geral `fct_delivery_daily` produz números incorretos para os dois maiores clientes:
- **Luckbet:** Dupla contagem (2 client IDs, mesmos campaigns)
- **Cora:** Cobertura apenas a partir de março/2026

O Power BI deve usar `fct_luckbet_delivery_full` para Luckbet e `fct_cora_delivery_full` (ou `fct_newad_fintech_daily`) para Cora. A view geral `fct_delivery_daily_mvp` é mais segura que a original, mas ainda não elimina todos os problemas.

#### F-GOLD-4 🟡 dim_io_line aplica normalização de dados corrompidos via CASE
Campos `buying_model` e `deliverable_metric` em IOs antigos (2025) tinham valores numéricos no lugar do tipo (`"476190.4762"` onde deveria estar `"CPM"`). A view aplica um `CASE` para corrigir isso em tempo de query. O dado original em `core.io_manager_v2` continua corrompido.

**Ação necessária no Admin UI:** Validar os campos `buying_model` e `deliverable_metric` no formulário de cadastro para rejeitar valores numéricos.

#### F-GOLD-5 🟡 Semantics de conv1–5 mapeadas apenas para Luckbet

| Cliente | conv1 | conv2 | conv3 | conv4 | conv5 |
|---------|-------|-------|-------|-------|-------|
| Luckbet | pageviews | cadastros | ftds | depositos_recorrentes | inicio_cadastro |
| Cora | pageviews | `pending` | `pending` | `pending` | `pending` |
| TecPar | pageviews | `pending` | `pending` | `pending` | `pending` |
| Einstein | pageviews | `pending` | `pending` | `pending` | `pending` |

**Ação necessária do Shiro:** Confirmar o mapeamento comercial de conv2–5 para Cora, TecPar e Einstein.

#### F-GOLD-6 🟡 Gold layer não está no código do repositório
Todas as 15 views gold foram criadas manualmente (via BQ console ou scripts locais). O repositório não tem nenhum arquivo que as crie/recrie automaticamente. Se o BQ for resetado, a gold desaparece.

**Sugestão:** Mover as DDLs para `sql/gold/` e incluir no `init_bq.py` reescrito.

---

## 8. Problemas Transversais — Qualidade de IDs e Clientes

### 8.1 Luckbet: Dupla/Triple Contagem

**Causa raiz:** Existem dois `newad_client_id` para o mesmo anunciante real:
- `nwd_luckbet_a485d6bc` — conta ativa (advertiser_id: `adv_b559ffdcbd`)
- `nwd_luckbet_69e72f18` — conta legada (advertiser_id: `luckbet`)

Adicionalmente, `nwd_internal_newad` tem o mesmo `link_value` no MediaSmart que `nwd_luckbet_a485d6bc`.

**Impacto:** Qualquer soma de entrega em `fct_delivery_daily` (padrão) conta Luckbet 2–3 vezes.

**Ação necessária do Shiro:**
1. Desativar todos os IOs e bindings de `nwd_luckbet_69e72f18` no Admin UI
2. Corrigir `link_value` de `nwd_internal_newad` para a conta MediaSmart real da agência (ou desativar o link com `status = inactive`)

### 8.2 Clientes sem Cobertura de IO

| Cliente | Problema | Dados missing |
|---------|---------|--------------|
| Cora | 1 IO apenas (mar/26) + MGID/Siprocal sem bindings pré-mar | ~1.2M impressões |
| Dr. Consulta | IOs cobrem apenas fev–mar/26 | Histórico anterior missing |
| TecPar | `advertiser_id` inconsistente entre IOs (`tecpar` vs `nwd_tec-par_4ee38788`) | JOINs podem quebrar |
| Stocco | **0 IOs cadastrados** | **100% da entrega invisível na gold** |
| Luckbet | 2 campaigns sem IO (ver F-GOLD-2) | ~5.95M impressões |

### 8.3 Cadeia de IDs: Cada Seta é um Ponto de Falha

```
raw.mediasmart_daily.eventid
  → stg.event_id
    → share.advertiser_platform_id
      = core.platform_client_links.link_value          ← JOIN 1 (advertiser → cliente)
        → core.platform_client_links.newad_client_id

raw.mediasmart_daily.controlid
  → stg.platform_campaign_id
    = core.io_line_bindings_v2.platform_campaign_id    ← JOIN 2 (campaign → IO)
      → io_id, line_id, proposal_id

RESULTADO: sem JOIN 1 + JOIN 2, a linha de entrega não tem cliente nem IO na gold.
```

**Se qualquer um desses valores tiver espaço extra, capitalização diferente ou formato inconsistente, a entrega desaparece silenciosamente.** Não há alert ou log de linhas não-joinadas.

**Sugestão:** Criar uma query de monitoramento diária:
```sql
-- Entrega em raw sem atribuição de cliente (JOIN 1 falhou)
SELECT date, platform, advertiser_platform_id, SUM(impressions) AS lost_impressions
FROM `adframework.share.newad_operational_daily`
WHERE advertiser_platform_id NOT IN (
  SELECT link_value FROM `adframework.core.platform_client_links`
  WHERE LOWER(COALESCE(status,'active')) = 'active'
)
GROUP BY 1,2,3
ORDER BY lost_impressions DESC;
```

---

## 9. Infraestrutura e Código

### 9.1 ETL (orchestrator.py)

| Problema | Impacto |
|---------|---------|
| Siprocal usa `CREATE OR REPLACE` | Histórico destruído a cada run |
| Fetch de criativos usa `io_manager_enriched` (62 IOs) | 73% dos IOs sem criativo |
| Sem retry em falhas | Job longo pode falhar silenciosamente |
| Sem alertas (PubSub / Cloud Monitoring) | Falhas passam despercebidas |
| Incremento por `MAX(date)`: outlier de data futura para o ETL | Ingestão para sem aviso |
| Gold não é refreshada após ETL | Power BI apenas reflete hoje quando alguém executar manualmente (RESOLVIDO: gold agora é view) |

### 9.2 init_bq.py (3.490 linhas)

| Problema | Impacto |
|---------|---------|
| ~1.500 linhas de código morto (Pipeline A) | Qualquer bootstrap cria arquitetura errada |
| SQLs inline como f-strings Python | Dificulta versionamento e testing |
| Pipeline V4 inteiro ausente | Staging/novo dev = pipeline quebrado |
| Dataset names hardcoded | Dificulta múltiplos ambientes |

### 9.3 Cobertura de Código vs. BigQuery

| Camada | Objetos em prod | Gerenciados por código | % cobertura |
|--------|----------------|----------------------|-------------|
| RAW | ~15 tabelas | ~8 | 53% |
| STG | 19 views | 6 | 32% |
| CORE | 12 objetos | 1 (external table legada) | ~8% |
| MARTS | ~20 views | ~6 (pipeline A) | 30% (pipeline errado) |
| SHARE | ~67 objetos | ~2 | 3% |
| GOLD | ~15 views | 0 | **0%** |

**O pipeline que funciona (V4) tem cobertura de código ~0%.** Todo ele foi construído manualmente no BQ console.

---

## 10. Matriz de Prioridades

### 🔴 Alta — Corrigir antes de qualquer novo cliente

| # | Item | Onde | Esforço |
|---|------|------|---------|
| P1 | Desativar `nwd_luckbet_69e72f18` e `nwd_internal_newad` no Admin UI | Admin UI / Firebase | 30min |
| P2 | Corrigir `orchestrator.py` linha ~722: usar `io_manager_v2` (229 IOs) para fetch de criativos | Python | 1h |
| P3 | Criar IO bindings para as 2 campaigns Luckbet órfãs (5.95M impressões) | Admin UI | 1h |
| P4 | Criar IO bindings retroativos para Cora MGID/Siprocal Ago/25–Fev/26 | Admin UI | 2-4h |
| P5 | Deletar raw_* datasets + backups fev/26 (~1.147 MB) | BQ console | 30min |
| P6 | Mudar Siprocal para INSERT incremental (evitar destruição de histórico) | Python | 2h |

### 🟡 Média — Fazer na próxima sprint

| # | Item | Onde | Esforço |
|---|------|------|---------|
| P7 | Extrair DDL das views V4 do BQ e registrar no repositório | Repositório | 1-2 dias |
| P8 | Confirmar semântica conv1–5 para Cora, TecPar, Einstein | Reunião comercial | — |
| P9 | Criar IOs para Dr. Consulta e TecPar (histórico completo) | Admin UI | 2-4h |
| P10 | Criar IO para Stocco (0 visibilidade na gold) | Admin UI | 1h |
| P11 | Corrigir fallback do Admin UI (`BQ_LINKING_FALLBACK_TABLE`) | Python | 30min |
| P12 | Adicionar query de monitoramento diária (entrega sem cliente) | BQ / Script | 1h |
| P13 | Tornar `io_number` obrigatório e único no Admin UI | Admin UI | 2h |
| P14 | Deletar 4 tabelas materializadas vazias + views legadas marts | BQ console | 30min |

### 🟢 Baixa — Reestruturação estrutural (Sprint dedicada)

| # | Item | Onde | Esforço |
|---|------|------|---------|
| P15 | Reescrever `init_bq.py` (~3.490 → ~900 linhas, Pipeline V4 completo) | Python | 2-3 dias |
| P16 | Automatizar sync Firestore → BQ (Cloud Function) | GCP | 2-3 dias |
| P17 | Deprecar share.report_daily_* (40 views legadas) após confirmar zero uso | BQ | 1 dia |
| P18 | Adicionar schema explícito para `raw.mgid_daily` | Python | 2h |
| P19 | Separar SQL inline do Python em arquivos `.sql` | Repositório | 1 semana |
| P20 | Criar ambiente staging (projeto GCP separado, Pipeline V4 clean) | GCP + Python | 3 semanas |

---

## 11. Perguntas Abertas para o Shiro

### Decisões que bloqueiam P1–P6

| # | Pergunta | Por que importa |
|---|----------|----------------|
| Q1 | `nwd_luckbet_69e72f18`: pode ser desativado com segurança? Algum IO externo (Power BI, relatório do cliente) ainda aponta pra esse ID? | P1 — se não, o double-count continua |
| Q2 | `nwd_internal_newad`: qual é a conta MediaSmart real da agência NewAD? Qual `link_value` deveria ter? | P1 — o phantom vai continuar poluindo se não corrigir o link |
| Q3 | Siprocal: quem atualiza a planilha Google Sheets que alimenta `raw.siprocal_daily_materialized`? Com que frequência? É seguro mudar para INSERT? | P6 — se a planilha cresce retroativamente, o INSERT vai pular esses dados |
| Q4 | Cora: temos os campaign IDs MGID/Siprocal de Ago/25–Fev/26? É possível criar IOs retroativos? | P4 — gap de ~1.2M impressões |
| Q5 | Dr. Consulta: a conta `nwd_dr-consulta_*` tem campanhas ativas além de fev–mar/26? Temos que criar IOs retroativos? | P9 |
| Q6 | TecPar: dois `advertiser_id` diferentes (`tecpar` e `nwd_tec-par_4ee38788`) nos IOs. Qual é o correto? | P9 |
| Q7 | Stocco: existe alguma entrega do Stocco no MediaSmart que deveríamos estar capturando? Qual é o `event_id`/`link_value` da conta deles? | P10 |
| Q8 | Quem executa o sync Firestore → BQ Core? Com que frequência? Existe documentação disso? | P12 |
| Q9 | Cora: quais são as conversões 2–5 do pixel deles? (`pageviews` está confirmado como conv1) | P8 / `dim_client_semantics` |
| Q10 | A reestruturação para projeto staging separado: Alexandre tem acesso de org-admin no GCP para criar `adframework-stg`? | P20 blocker |

---

## 12. Resumo dos Achados por Camada

| Camada | Achados | Críticos | Sugeridos para reunião |
|--------|---------|---------|----------------------|
| **RAW** | 5 | 2 (Siprocal destroy history, ~1.147 MB lixo) | Deletar raw_* imediato + fix Siprocal |
| **STG** | 3 | 2 (io_lines_v4 fora do código, dependência invertida) | Extrair DDLs do BQ e registrar |
| **CORE** | 5 | 3 (orquestrador usa legado, sem sync auto, io_id colisão) | Fix orchestrator + dedup Luckbet |
| **MARTS** | 2 | 2 (Pipeline A morto em código, V4 fora do código) | Priorizar reescrita init_bq.py |
| **SHARE** | 3 | 1 (Admin UI fallback legado) + ~40 views quebradas | Auditar uso + deprecar em cascata |
| **GOLD** | 6 | 3 (Cora gap, Luckbet orphans, no code coverage) | IO bindings retroativos (Shiro) |
| **Transversal IDs** | 7 | 4 (Luckbet dup, phantom, campaigns orphans, no JOIN monitor) | Prioridade máxima antes de novos clientes |

**Estado atual da pipeline de dados em uma frase:** O Pipeline V4 funciona e alimenta o Power BI, mas foi construído inteiramente fora do código, tem dois clientes com dados distorcidos (Luckbet double-count, Cora gap), e não sobrevive a um reset de ambiente — qualquer deploy do repositório reconstrói o Pipeline A legado que está quebrado.

---

*Documento gerado em 2026-05-26 por Douglas Reche | Baseado em: bigquery_analysis.md (30/04), prod_audit_and_restructuring_plan.md (30/04 + 05/05), known_issues.md (12/05), id_quality_issues.md (12/05), id_dependency_map.md (13/05), inspeção de todos os arquivos SQL do repositório*
