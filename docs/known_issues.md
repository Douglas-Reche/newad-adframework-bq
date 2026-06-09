# Problemas Conhecidos — AdFramework BigQuery

> Última atualização: 2026-06-08
> Autor: Douglas Reche

---

## ✅ Resolvidos em 2026-06-08

| # | Problema | Resolução |
|---|---|---|
| R1 | **Amigo (`amigo_db1c2f0c`) com 39 links `pending_confirmation`** — 1 eventid MediaSmart + 38 campaignids MGID criados em 2026-05-26 nunca foram ativados, zerando a entrega de Amigo na gold. | `core/migration/05_activate_amigo_links.sql` rodado em prod — 39 linhas promovidas para `active`. Verificado: 40 links ativos totais (1 MS + 38 MGID + 1 Siprocal pré-existente). |
| R2 | **`gold.fact_delivery` com dados de MediaSmart parados em 2026-05-24** — ETL do orchestrator com timeout, 12 dias de gap. | `stg.mediasmart_delivery` atualizado para incluir `raw.mediasmart_daily` (tabela staging do orchestrator) como fonte complementar. `gold.fact_delivery` reconstruída em 2026-06-08 com dados até 2026-06-07. Root cause (timeout no orchestrator) ainda pendente — ver issue #8. |

---

---

## 0. Separação de responsabilidades no dataset `core`

**Contexto:** O dataset `core` no BigQuery contém tabelas de dois sistemas diferentes que coexistem durante a transição.

**Tabelas do NOSSO pipeline** (usar livremente):
- `core.dim_client` — cadastro de clientes
- `core.platform_client_links` — atribuição plataforma → cliente (usado em `gold.fact_delivery`)
- `core.campaign_format_map` — mapeamento formato de campanha (Display, Native, Push, Retargeting, Video)

**Tabelas do Admin UI do Shiro** (NÃO referenciar no pipeline gold):
- `core.io_manager_v2` — escrito pelo Admin UI via `adops/io_bq_sync.py`
- `core.io_line_bindings_v2` — escrito pelo Admin UI
- `core.proposals` / `core.proposal_lines` — módulo de planning do Admin UI
- `core.io_manager_enriched_v2`, `core.io_registry_v4`, `core.io_binding_registry_v4`, `core.io_line_bindings_enriched_v2` — views do sistema do Shiro

**Por que não conectar:** O `io_manager_v2.newad_client_id` usa formato `nwd_banco-cora_acfae3ab` (prefixo `nwd_` + hifens) enquanto o `dim_client.client_id` usa `banco_cora_fe13d78a` (sem prefixo, underscores). JOINs entre os dois sistemas nunca funcionam.

---

## 1. Duplicação de clientes Luckbet no sistema

**Impacto:** Qualquer soma de entrega na gold layer aparece duplicada para Luckbet.

**Causa raiz:**  
Existem dois `newad_client_id` para o mesmo cliente real (Luckbet):
- `nwd_luckbet_a485d6bc` — conta **canônica** (advertiser_id: `adv_b559ffdcbd`)
- `nwd_luckbet_69e72f18` — conta **legacy** (advertiser_id: `luckbet`)

Os mesmos campaign IDs físicos no MediaSmart estão vinculados a IOs de **ambos** os client IDs simultaneamente. Resultado: 23 dos 25 campaigns MediaSmart da Luckbet aparecem contados duas vezes.

**Solução necessária (Admin UI):**  
Desativar todos os IOs e bindings do `nwd_luckbet_69e72f18`. Manter apenas o `nwd_luckbet_a485d6bc` como conta ativa.

---

## 2. nwd_internal_newad aponta para conta MediaSmart da Luckbet

**Impacto:** Entrega da Luckbet aparece triplicada — sob `_69e72f18`, `_a485d6bc` e `nwd_internal_newad`.

**Causa raiz:**  
Em `platform_client_links`, o cliente `nwd_internal_newad` tem `link_value = newad_brazil-dzynxhmnrdg2ec0czgdiabqmwvy0qhgj` — que é **a mesma conta MediaSmart** da Luckbet canônica. Nenhuma campanha real pertence ao "NewAD Interno" — todas são Luckbet.

**Solução necessária (Admin UI / Firebase):**  
Corrigir o `link_value` do `nwd_internal_newad` para a conta MediaSmart correta da agência, ou desativar o link (`status = inactive`).

---

## 3. Dois campaign IDs MediaSmart sem IO (órfãos)

**Impacto:** Entrega real nunca aparece na gold layer.

| campaign_id | Impressões | Período |
|---|---|---|
| `35ey8fny8gizx3vfxwac4ft1xjitbfbe` | 5,47M | abr/26 |
| `toarsf57a3lky0xmw7w16m4e68iqt5xy` | 479k | set/25 |

**Causa raiz:**  
Campanhas ativas no MediaSmart que nunca foram vinculadas a nenhum IO no Admin UI.

**Solução necessária:** Criar ou retroativamente vincular a um IO no Admin UI.

---

## 4. Cora: histórico MediaSmart (ago/25–fev/26) fora da gold

**Impacto:** `fct_delivery_daily` e `fct_newad_fintech_daily` via `io_calc` só mostram dados da Cora a partir de março/26.

**Causa raiz:**  
Existe apenas um IO para Cora (`io_202603_nwd-banco-cora-acfae3ab_001`). O `io_calc_daily_v4` é schedule-driven — só gera linhas para datas cobertas pelo IO. Os dados de ago/25–fev/26 existem em `raw.mediasmart_daily_operational` mas nunca foram formalizados em um IO.

**Workaround aplicado:**  
`gold.fct_newad_fintech_daily` lê diretamente de `share.platform_daily_detail` + LEFT JOIN `stg.io_lines_v4` para capturar todos os meses.

**Solução definitiva:** Criar IOs retroativos para ago/25–fev/26 no Admin UI com os campaign IDs corretos.

---

## 5. Siprocal: atribuição por nome, não por ID

**Impacto:** Impossível distinguir campaigns Siprocal entre dois client IDs que compartilham o mesmo `link_value`.

**Causa raiz:**  
`platform_client_links` para Siprocal usa `link_value = 'luckbet'` tanto para `nwd_luckbet_69e72f18` quanto `nwd_luckbet_a485d6bc`. A tabela raw `siprocal_daily_materialized` tem o campo `advertiser` como nome (ex: `LUCKBET`), não um ID estruturado.

**Solução necessária:** Definir qual client ID é canônico para Siprocal e desativar o link do legacy.

---

## 7. Filtros removidos da camada RAW — pendente revisão no STG

**Data:** 2026-06-03  
**Contexto:** Auditoria da camada raw identificou filtragens acontecendo antes/durante a ingestão, violando o princípio medallion (RAW = tudo sem filtro).

### 7.1 `mediasmart_revenue_daily` — rules removido

**Filtro que existia (removido em 2026-06-03):**
```json
"rules": "revenuesource=[event1,event2,event3,event4,event5,2,3,4,5]"
"from": "2026-03-06"
```

**O que esse filtro fazia:**
- Limitava os `revenuesource` aceitos — qualquer outro tipo de receita era descartado antes de chegar ao BQ
- Limitava o backfill a partir de 2026-03-06

**Pendente no STG:** `stg.mediasmart_revenue` precisa ser revisada para aplicar o filtro de `revenuesource` se necessário para análise (ex: excluir fontes irrelevantes para o negócio).

### 7.2 `mediasmart_daily_daily` — drilldown limitado

**Configuração atual (não alterada ainda — pendente aprovação Shiro):**
```json
"drilldown": "day,eventid,controlid,strategyid,strategyname,convsource"
"kpis": "impressions,clicks,video_start,video_completion,conversions_1-5"
```

**Colunas que a API retorna mas NÃO chegam à `raw.mediasmart_delivery`:**
`creative_id`, `creative_type`, `id_type`, `mediasmart_id`, `nativesize`, `size`, `client_currency`, `clientrevenue`, `convertedclientrevenue`, `client_cost`

**Ação necessária (requer Shiro):**
1. Ampliar `drilldown` para incluir dimensões de criativo (`creativeid`, `creativetype`, `size`, etc.)
2. Ampliar `kpis` para incluir `clientrevenue`, `clientcost`, `clientcurrency`
3. Adicionar colunas correspondentes ao schema de `raw.mediasmart_delivery`

### 7.3 `raw.mediasmart_revenue` — colunas perdidas no merge

**Colunas que chegam no staging mas NÃO chegam ao final:**
`eventid`, `revenue_source` (renomeado para `revenuesource`), `conversion_source`

**Pendente:** Adicionar essas colunas ao schema de `raw.mediasmart_revenue` para não perder granularidade.

---

## 8. `gold.fact_io_plan` — view quebrada, zero linhas

**Data identificado:** 2026-06-08
**Impacto:** Todos os KPIs "Projetado" e de Pacing estão indisponíveis no dashboard — Investimento Projetado, Impressões Projetadas, Cliques Projetados, CTR Projetado, Pacing %, CPC/CPM Projetado.

**Causa raiz:**
A view `gold.fact_io_plan` lê `stg.luckbet_io_plan` → `raw.luckbet_io_plan_snapshot`. A tabela `raw.luckbet_io_plan_snapshot` foi **dropada** — a chain está morta. Toda query retorna 0 linhas.

**Solução necessária:**
Identificar a fonte atual de IO plan no sistema do Shiro (Admin UI) e reconectar a view. Os dados de planejamento (investimento previsto, impressões previstas, cliques previstos por campanha) provavelmente existem em `core.io_manager_v2` ou similar. Requer alinhamento com Shiro.

---

## 9. MediaSmart ETL — timeout no orchestrator (root cause aberta)

**Data identificado:** ~2026-06-01 (job parou de atualizar)
**Impacto:** `raw.mediasmart_delivery` parado em 2026-05-24. Workaround aplicado em `stg.mediasmart_delivery` cobre até 2026-06-07 via `raw.mediasmart_daily`.

**Causa raiz:**
Job `mediasmart_daily_daily` no orchestrator (Shiro) retorna `error:Timeout` desde ~01/jun. O `raw.mediasmart_daily` ainda é alimentado (é a tabela staging intermediária do mesmo job), mas os dados não chegam ao destino final `raw.mediasmart_delivery`.

**Workaround atual:** `stg.mediasmart_delivery` faz UNION com `raw.mediasmart_daily` para cobrir o gap.

**Solução necessária:** Shiro investigar e corrigir timeout no job `mediasmart_daily_daily`. Provável causa: janela de datas muito longa na query de API. Ver `docs/etl_expansion_plan.md` para proposta de refatoração.

---

## 6. Conversões conv1–5 sem semântica nas views genéricas

**Impacto:** `fct_delivery_daily` e `fct_creative_daily` expõem `conversions1`–`conversions5` sem significado de negócio.

**Status:**  
Mapeamento criado em `gold.dim_client_semantics`. Luckbet confirmado por Shiro (29/04/2026). Cora, Einstein, TecPar ainda pendentes de confirmação comercial.

| Campo | Luckbet | Cora (pendente) |
|---|---|---|
| conversions1 | pageviews | pageviews |
| conversions2 | cadastros | leads |
| conversions3 | ftds | contas_abertas |
| conversions4 | depositos_recorrentes | ativacoes |
| conversions5 | inicio_cadastro | inicio_cadastro |
