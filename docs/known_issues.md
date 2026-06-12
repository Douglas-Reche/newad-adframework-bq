# Problemas Conhecidos — AdFramework BigQuery

> Última atualização: 2026-06-12 — sanity check STG concluído; 4 raw tables Grupo A deduplicadas (by_device, by_os, by_hour, by_publisher); impressões confirmadas consistentes 0.029% δ.
> Autor: Douglas Reche

---

## ✅ Resolvidos em 2026-06-12

| # | Problema | Resolução |
|---|---|---|
| S1 | **4 raw tables Grupo A com duplicatas do backfill** — `by_device` (3.52×), `by_os` (3.76×), `by_hour` (2×), `by_publisher` (1.36×). Causa: múltiplos triggers de backfill com WRITE_APPEND sobrescreveram o mesmo período. `by_geo` e `creative_daily` não foram afetadas. | `CREATE OR REPLACE TABLE ... AS SELECT DISTINCT * FROM ...` executado em produção 2026-06-12. Row counts pós-dedup: by_device 58.610, by_os 72.741, by_hour 2.715, by_publisher 7.198.762. Sanity check confirmado: by_device = by_os = by_geo = creative_daily = 233.093.873 impressões; gap vs ms_delivery = 0.029% (esperado). |
| B1 | **Backfill Grupo A incompleto — 4 de 6 jobs com API timeout** — `delivery_by_hour` (dados com range errado Mai 28+), `delivery_by_geo` (sem tabela), `creative_daily` (parcial Jan 1-20), `delivery_by_publisher` (parcial Jan 1-6). | Causa raiz: `REQUEST_TIMEOUT_SECONDS = 10` muito baixo para drilldowns de alta cardinalidade (geo, publisher). Fix: timeout aumentado para 60s + deploy revision `adframework-etl-00238-n4h`. Backfill executado via múltiplos triggers sequenciais com `force_from_date` atualizado incrementalmente. `delivery_by_geo` deduplicada com `SELECT DISTINCT *` após duplicação acidental. `delivery_by_hour` confirmado que MediaSmart não tem dados hourly antes de 2026-05-28 para as contas monitoradas. Todos os 6 `force_from_date` removidos do Firestore. |
| T1 | **`REQUEST_TIMEOUT_SECONDS = 10` — timeout insuficiente para drilldowns de alta cardinalidade** — `delivery_by_geo` (country+area+city) e `delivery_by_publisher` (company+url+exchange) geram relatórios grandes que excedem 10s. Manifestou-se como `HTTPSConnectionPool Read timed out` em todos os requests desses jobs. | `adframework_python/src/connectors/mediasmart.py` linha 16: `REQUEST_TIMEOUT_SECONDS = 10` → `60`. Commit `7bee5f9`. Deploy Cloud Run revision `adframework-etl-00238-n4h`. Jobs que completavam ok antes (device, os, hour) não foram afetados (baixa cardinalidade = API responde rápido). |

---

## ✅ Resolvidos em 2026-06-11

| # | Problema | Resolução |
|---|---|---|
| 16 | **MediaSmart Grupo A (6 tabelas) — dimensões sem labels** — `operating_system`, `device_type`, `country`, `city`, `publisher_company`, etc. ausentes nas 6 tabelas recém-criadas, impossibilitando STG. | Causa: tabelas pré-criadas por processo do Shiro com schema antigo (`eventid`/`controlid`); `bigquery.py:load_data` dropou colunas não reconhecidas. Fix: DROP nas 6 tabelas + re-trigger via ETL HTTP API. Tabelas recriadas com schema nativo da API (`event_id`, `campaign_id`, `operating_system`, etc.). Ver CHANGELOG 2026-06-11 sessão 2. |
| 15 | **MediaSmart conector — sleep insuficiente, risco de rate limit** — `time.sleep(0.15)` = 400 req/min, 3× acima do limite de 128. | Commit `4d1662f`: `RATE_LIMIT_DELAY` 0.3 → 0.6, sleeps 0.15/0.3 → 0.6. Deploy Cloud Run revision `adframework-etl-00237-v88`. |
| D1 | **`raw.mediasmart_campaigns` com 39× duplicação** — WRITE_APPEND acumulou 5.451 linhas para 140 IDs únicos. | Firestore `write_mode: WRITE_TRUNCATE` + dedup BQ: `CREATE OR REPLACE TABLE ... WHERE rn = 1`. Resultado: 140 linhas. |
| D2 | **`raw.mediasmart_daily` — gap 25–26/mai/2026** — transição entre job antigo e novo deixou 2 dias sem dados. | `force_from_date` implementado em `_get_date_range` (orchestrator.py, commit `4d1662f`). Job temporário `mediasmart_backfill_may2526` carregou 26 linhas (13/dia). |
| 9 | **`raw.mediasmart_delivery` parado em 2026-05-24** — entendimento incorreto de que era timeout do Shiro. | Investigação confirmou: tabela ativa é `raw.mediasmart_daily` (usa campo `table_name`, não `bq_destiny`). Sem ação necessária. |
| 7.2 | **Colunas extras ausentes em `raw.mediasmart_delivery`** — baseado em tabela legada (24 cols). | `raw.mediasmart_daily` (ativa) já tem 31 cols incluindo `creative_type`, `id_type`, `client_currency`, etc. |

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
`platform_client_links` para Siprocal usa `link_value = 'luckbet'` tanto para `nwd_luckbet_69e72f18` quanto `nwd_luckbet_a485d6bc`. A tabela raw `siprocal_delivery` tem o campo `advertiser` como nome (ex: `NEWAD_LUCKBET_BR_XXX`), não um ID estruturado.

**Solução necessária:** Definir qual client ID é canônico para Siprocal e desativar o link do legacy.

---

## ✅ RESOLVIDO — 10. Siprocal: pipeline quebrado, dados parados em 2026-05-26

**Data identificado:** 2026-06-10  
**Data resolvido:** 2026-06-11

**Causa raiz:**  
A tabela `raw.siprocal_daily_native` (fonte original do ETL job) foi deletada entre 01/06 e 05/06, provavelmente durante uma limpeza. O ETL job `siprocal_daily:Daily` continuou tentando ler dela e falhando com 404 todos os dias.

**Diagnóstico (2026-06-11):**
- Automação ETL **sempre existiu**: Cloud Scheduler `adframework-etl-daily` (05:00 UTC) → job `siprocal_daily:Daily`
- Job lia de `platform_endpoints/siprocal_ep_external_daily.path_template` = `external://bq/raw.siprocal_daily_native`
- `siprocal_daily_native` sumiu → 404 a partir de ~02/06. Não existe Cloud Run Job ou outro scheduler que a populava.

**Resolução (2026-06-11):**
- Scripts redundantes deletados: `siprocal_full_reload.py`, `siprocal_backfill_from_sheets.py`, `siprocal_reconnect_etl.py`, `siprocal_sheet_meta.py`
- `raw.siprocal_sheet_ext` criada como BQ External Table (auxiliar, para inspeção via SQL)
- `raw.siprocal_raw_sheet` recriada como **TABLE nativa** com 1.078 linhas (ago/25 → 09/06/26)
- Firestore `platform_endpoints/siprocal_ep_external_daily.path_template` corrigido para `external://bq/adframework.raw.siprocal_raw_sheet`
- **ETL job rodou com sucesso às 12:01 UTC de 11/06** — `siprocal_delivery` com 1.078 linhas até 09/06

**Arquitetura atual (funcionando):**
```
Google Sheet (raw_daily)
  └─ scripts/siprocal/sync_sheet.py  [WRITE_APPEND incremental — rodar quando sheet atualizar]
       └─ raw.siprocal_raw_sheet  [TABLE nativa BQ — fonte do ETL]
            └─ ETL job siprocal_daily:Daily  [Cloud Scheduler 05:00 UTC — automático]
                 └─ raw.siprocal_delivery  [CREATE OR REPLACE diário]
                      └─ stg.siprocal_delivery → gold.fact_delivery

raw.siprocal_sheet_ext  [BQ External Table → Sheet — auxiliar para inspeção]
```

**Restrição do orchestrator:** rejeita External Tables com fonte Google Sheets como source do ETL.  
`siprocal_raw_sheet` deve ser sempre TABLE nativa; nunca substituir por VIEW sobre `siprocal_sheet_ext`.

**Passo manual restante:** rodar `sync_sheet.py` quando a Siprocal atualizar a planilha (antes das 05:00 UTC).  
Para automação zero-touch: Cloud Run Job agendado às 04:45 UTC — requer Shiro.

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

### 7.2 `mediasmart_daily_daily` — colunas extras na tabela ATIVA ✅ RESOLVIDO (2026-06-11)

**Investigação 2026-06-11 revelou que:**
- A tabela ativa é `raw.mediasmart_daily` (31 cols, desde 2026-05-25), NÃO `raw.mediasmart_delivery`
- `raw.mediasmart_daily` já inclui `creative_type`, `creative_id`, `id_type`, `mediasmart_id`, `nativesize`, `size`, `client_currency` — vindas do schema fixo da API
- Esses campos vêm vazios/NULL quando o drilldown não inclui dimensão de criativo
- `clientrevenue`, `convertedclientrevenue`, `client_cost` também já estão presentes (31 cols)

**Status:** as colunas "ausentes" já existem em `raw.mediasmart_daily`. O issue era baseado em
inspeção da tabela legada `raw.mediasmart_delivery` (24 cols). Sem ação necessária.

### 7.3 `raw.mediasmart_revenue` — colunas perdidas no merge

**Colunas que chegam no staging mas NÃO chegam ao final:**
`eventid`, `revenue_source` (renomeado para `revenuesource`), `conversion_source`

**Pendente:** Adicionar essas colunas ao schema de `raw.mediasmart_revenue` para não perder granularidade.

---

## ✅ RESOLVIDO — 8. `gold.fact_io_plan` — view quebrada, zero linhas

**Data identificado:** 2026-06-08  
**Data resolvido:** 2026-06-09

**Causa raiz:**
A view `gold.fact_io_plan` apontava para `raw.luckbet_io_plan_snapshot` (dropada). Toda query retornava 0 linhas.

**Resolução:**
Pipeline IO Plan completamente reconstruído (ver `docs/io_plan_pipeline.md`):
- `raw.io_plan_drive_snapshot` — nova tabela raw, particionada, grain estratégia × flight × cliente
- `core.io_plan_manual` — seed manual + sync Drive; grain flight × cliente
- `gold.fact_io_plan` — VIEW reconstruída com GENERATE_DATE_ARRAY (grain diário)
- `scripts/io_plan/sync_drive.py` — sync automático do Drive para o BQ
- `services/io-plan-admin/` — serviço Cloud Run com botões de sync on-demand

**Validado em BQ (2026-06-09):**
- `core.io_plan_manual`: 15 flights (Cora Jan-Ago + TecPar Jan-Jun)
- `gold.fact_io_plan`: 424 linhas diárias (243 Cora + 181 TecPar)
- Cora hoje: 194.520 imp/dia planejadas, R$2.540/dia gross, R$474/dia net ✓
- TecPar hoje: 132.269 imp/dia planejadas, R$423/dia gross ✓

---

## ✅ RESOLVIDO — 9. MediaSmart ETL — raw.mediasmart_delivery parado em 2026-05-24

**Data identificado:** ~2026-06-01 | **Data resolvido:** 2026-06-11 (investigação confirmou)

**Causa raiz (atualizada após investigação 2026-06-11):**
O job `mediasmart_daily_daily` NUNCA escreveu em `raw.mediasmart_delivery` após 2026-05-24 —
porque o orchestrator usa `table_name = "mediasmart_daily"` + `dataset_id = "raw"` como destino
real (não o campo `bq_destiny = "raw.mediasmart_delivery"` que é legado e ignorado).

`raw.mediasmart_daily` é a tabela ATIVA desde 2026-05-25 (criada com schema 31 cols quando a
API MediaSmart ampliou sua resposta). `raw.mediasmart_delivery` (24 cols) era o destino antigo.

**Estado atual (2026-06-11):**
- `raw.mediasmart_daily`: 170 linhas, 2026-05-25 → 2026-06-10, `last_status: ok`
- Job roda diariamente às 03:20 UTC via Cloud Scheduler
- `stg.mediasmart_delivery`: UNION de `raw.mediasmart_delivery` (histórico) + `raw.mediasmart_daily` (ativo) — cobertura completa ago/25 → hoje

**Nota:** o `bq_destiny` legado pode ser removido do Firestore para evitar confusão futura.
Ver `mediasmart_stg_design.md` seção "Descobertas sobre delivery vs daily".

---

---

## 11. platform_bindings_v3 — race condition entre dois processos (core_mvp)

**Identificado:** 2026-06-10 (auditoria Shiro)
**Impacto:** Bindings de plataforma podem ser sobrescritos silenciosamente.

**Causa raiz:**
`core_mvp.platform_bindings_v3` é escrita por **dois processos independentes**, ambos com `WRITE_TRUNCATE`:
- `POST /maintenance/sync-adops-mvp` → `adops_sync.sync_adops_to_bigquery()`
- `POST /maintenance/sync-governance-mvp` → `governance_sync.sync_governance_to_bigquery()`

O segundo a rodar substitui completamente o primeiro. Sem mecanismo de merge.

**Risco:** Se ambos rodarem em sequência (ex: deploy CI), um apaga o trabalho do outro.
**Solução necessária (Shiro):** Unificar num único processo ou usar `WRITE_APPEND` com deduplicação.

---

## ✅ RESOLVIDO — 12. raw.siprocal_daily_materialized — tabela órfã

**Identificado:** 2026-06-10 | **Resolvido:** 2026-06-11 (auditoria BQ confirmou: tabela não existe)

Auditoria de 11/06 listou todos os objetos `siprocal_*` no dataset `raw`: apenas `siprocal_delivery`, `siprocal_raw_sheet` e `siprocal_sheet_ext` existem. `siprocal_daily_materialized` não existe — sem risco de fonte paralela.

---

## ✅ RESOLVIDO — 13. Siprocal — ingestão automática quebrada

**Identificado:** 2026-06-10 | **Resolvido:** 2026-06-11

A automação ETL sempre existiu. O problema era a tabela fonte `siprocal_daily_native` deletada. Ver resolução do issue #10.

---

## 14. fact_io_plan — sem granularidade de plataforma (Power BI)

**Identificado:** 2026-06-10
**Impacto:** No Power BI não é possível filtrar/relacionar plano de investimento por plataforma ou campanha. Só funciona no nível cliente × data.

**Causa raiz:**
`core.io_plan_manual` agrega todas as estratégias num único flight por cliente (sem `platform`). `gold.fact_io_plan` herda esse grain, sem campo `platform`.
`gold.fact_delivery` tem `client_id + day + platform` — o JOIN só funciona no nível total do cliente.

**Solução proposta:** Adicionar coluna `platform` a `core.io_plan_manual` e mudar grain de `rebuild_core_for_client` para `client × flight × platform`. Requer: ALTER TABLE + update do script + re-sync dos dados DRIVE-SYNC existentes. DRIVE-SYNC rows ganham platform automaticamente (já existe em `raw.io_plan_drive_snapshot`). Rows manuais (Jan-Abr) ficam com `platform = NULL`.

---

## 15. MediaSmart conector — sleep insuficiente, risco de rate limit (iteração)

**Identificado:** 2026-06-11
**Impacto:** Jobs de iteração (creatives hoje, strategies_detail e unique_users futuros) podem receber rejeição temporária da API MediaSmart ao exceder 128 req/min.

**Causa raiz:**
```python
time.sleep(0.15)   # _fetch_mediasmart_creatives_iter → 400 req/min (3× acima do limite)
RATE_LIMIT_DELAY = 0.3  # fetch_json_paginated → 200 req/min (ainda acima)
```
Limite oficial da API: 128 req/min e 10 concurrent requests.

**Solução necessária (antes de criar Jobs 7 e 8):**
- `_fetch_mediasmart_creatives_iter`: alterar `time.sleep(0.15)` → `time.sleep(0.6)`
- `RATE_LIMIT_DELAY`: alterar `0.3` → `0.6`
- Com 0.6s entre calls = 100 req/min — margem segura de 22% abaixo do limite

**Escopo:**
- Jobs bulk (1–6, `/api/analytics/custom-report`): 1 call/dia cada — **sem risco, não precisam de ajuste**
- Jobs de iteração 7 (strategies_detail) e 8 (unique_users): ~140 calls cada — **aguardar fix antes de criar**
- Job de creatives (já em produção): também está em risco com 0.15s — corrigir junto

---

---

## ✅ RESOLVIDO — 16. MediaSmart Grupo A (6 tabelas) — dimensões sem labels de dimensão

**Data identificado:** 2026-06-11 (sessão 1) | **Data resolvido:** 2026-06-11 (sessão 2)

**Sintoma inicial:** `raw.mediasmart_delivery_by_os` ingerindo com granularidade correta (52 linhas vs 7 sem drilldown) mas sem coluna `operating_system` — impossível identificar qual linha é Android, iOS, etc.

**Investigação completa realizada (todos os paths confirmados):**
- ✅ `base.py:normalize_data` — apenas normalização BQ-safe, sem renomeação semântica
- ✅ `orchestrator.py:_run_mediasmart_daily` — sem schema enforcement ou adição de colunas
- ✅ `bigquery.py:load_data` — para tabelas EXISTENTES: dropa todas as colunas não presentes no schema BQ existente (linha chave: `dropped = [c for c in incoming_names if c not in existing_names]`)
- ✅ Código Shiro (Admin UI) — sem DDL pré-criado para as 6 tabelas Grupo A
- ✅ Firestore `iter_params`/`field_var` — metadados do Admin UI, ignorados pelo ETL pipeline
- ✅ API MediaSmart `custom-report` — **FLEXÍVEL** (não fixo), retorna headers human-readable conforme drilldown solicitado. Confirmado via test direto em 2026-06-10.
- ✅ `_resolve_bq_target()` — usa `table_name`+`dataset_id`, sem template de schema

**Root cause real:**
As 6 tabelas foram criadas ANTES pelo ETL do Shiro (`aat-console`) que usa um mapeamento inverso: `"Event ID"` → `eventid`, `"Campaign ID"` → `controlid`, `"Strategy ID"` → `strategyid`. Quando nosso ETL rodou e encontrou as tabelas existentes com schema antigo, `bigquery.py:load_data` jogou fora todas as colunas não reconhecidas (`event_id`, `campaign_id`, `operating_system`, etc.) — porque só mantém colunas que estão no schema BQ existente.

**Decisão de design (confirmada):**
Não adicionar dicionário de mapeamento ao ETL raw. `normalize_data` deve permanecer normalização pura. Mapeamento semântico pertence ao STG SQL. Ver CHANGELOG 2026-06-11 sessão 2 seção "Decisão de design".

**Resolução:**
1. DROP das 6 tabelas via BQ Python client
2. Re-trigger dos jobs via ETL HTTP API `POST /jobs/{job_name}/run` (endpoint descoberto nesta sessão)
3. Tabelas recriadas com schema nativo: `event_id`, `campaign_id`, `strategy_id`, `operating_system`, `device_type`, `country`, `area_name`, `city`, `publisher_company`, `publisher_url`, `ad_exchange`, `hour`, `creative_id`, `creative_type`, `size`, `app_vs_web` — todos confirmados nos schemas BQ

**Estado atual (2026-06-11):**
Todas as 6 STG (T7, T9, T10, by_os, by_hour, by_publisher) estão **DESBLOQUEADAS**.
Tabelas têm 1 dia de dados (2026-06-10). Backfill histórico de 2026 está pendente — ver `mediasmart_stg_design.md` seção "Plano de Backfill Grupo A".

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
