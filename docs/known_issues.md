# Problemas Conhecidos — AdFramework BigQuery

> Última atualização: 2026-06-11 (automação completa Siprocal via BQ External Table)
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
`platform_client_links` para Siprocal usa `link_value = 'luckbet'` tanto para `nwd_luckbet_69e72f18` quanto `nwd_luckbet_a485d6bc`. A tabela raw `siprocal_delivery` tem o campo `advertiser` como nome (ex: `NEWAD_LUCKBET_BR_XXX`), não um ID estruturado.

**Solução necessária:** Definir qual client ID é canônico para Siprocal e desativar o link do legacy.

---

## ✅ RESOLVIDO — 10. Siprocal: pipeline fragmentado, dados parados em 2026-05-26

**Data identificado:** 2026-06-10  
**Data resolvido:** 2026-06-11 (automação completa)

**Causa raiz:**  
Pipeline Siprocal tinha 3 caminhos de ingestão paralelos e conflitantes:
1. `siprocal_full_reload.py` — WRITE_TRUNCATE da planilha (perigoso, apaga histórico)
2. `siprocal_backfill_from_sheets.py` — WRITE_APPEND incremental (scope OAuth insuficiente)
3. Job ETL `siprocal_daily:Daily` — lia de `raw.siprocal_daily_native` (tabela deletada durante migração → 404)

**Resolução (2026-06-10/11):**
- Scripts redundantes deletados: `siprocal_full_reload.py`, `siprocal_backfill_from_sheets.py`, `siprocal_reconnect_etl.py`, `siprocal_sheet_meta.py`
- `raw.siprocal_raw_sheet` TABLE dropada e substituída por **VIEW** sobre `raw.siprocal_sheet_ext`
- `raw.siprocal_sheet_ext` criada como **BQ External Table** apontando para Google Sheet `1HaGrxaU-nt3fvqxaJ1CSlABYJGNY28rhQC49dcGzLWs` (tab `raw_daily`)
- Sheet compartilhada com `adframework-etl@adframework.iam.gserviceaccount.com` (Viewer)
- VIEW `siprocal_raw_sheet` normaliza colunas (PT→EN) e converte datas DD/MM/YYYY → YYYY-MM-DD
- `scripts/siprocal/sync_sheet.py` mantido como fallback manual; não é mais necessário para automação

**Arquitetura final:**
```
Google Sheet (raw_daily)
  └─ raw.siprocal_sheet_ext   [BQ External Table — auxiliar]
  └─ scripts/siprocal/sync_sheet.py  [sincronização manual ou agendada]
       └─ raw.siprocal_raw_sheet  [TABLE nativa — única fonte válida para o orchestrator]
            └─ ETL job siprocal_daily:Daily  [Cloud Run, 05:00 UTC — automático]
                 └─ raw.siprocal_delivery  [tabela física]
                      └─ stg.siprocal_delivery → gold.fact_delivery
```

**Nota:** O orchestrator do Shiro valida que a fonte seja uma tabela/view BQ nativa e rejeita External Tables com fonte Google Sheets. Por isso `siprocal_raw_sheet` deve ser TABLE nativa. A External Table `siprocal_sheet_ext` existe como auxiliar para inspeção e backfill manual via `sync_sheet.py`.

**Para automação completa zero-touch:** Criar Cloud Run Job que rode `sync_sheet.py` às 04:45 UTC via Cloud Scheduler — requer deploy por Shiro.

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

## 9. MediaSmart ETL — timeout no orchestrator (root cause aberta)

**Data identificado:** ~2026-06-01 (job parou de atualizar)
**Impacto:** `raw.mediasmart_delivery` parado em 2026-05-24. Workaround aplicado em `stg.mediasmart_delivery` cobre até 2026-06-07 via `raw.mediasmart_daily`.

**Causa raiz:**
Job `mediasmart_daily_daily` no orchestrator (Shiro) retorna `error:Timeout` desde ~01/jun. O `raw.mediasmart_daily` ainda é alimentado (é a tabela staging intermediária do mesmo job), mas os dados não chegam ao destino final `raw.mediasmart_delivery`.

**Workaround atual:** `stg.mediasmart_delivery` faz UNION com `raw.mediasmart_daily` para cobrir o gap.

**Solução necessária:** Shiro investigar e corrigir timeout no job `mediasmart_daily_daily`. Provável causa: janela de datas muito longa na query de API. Ver `docs/etl_expansion_plan.md` para proposta de refatoração.

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

## 12. raw.siprocal_daily_materialized — tabela órfã potencial

**Identificado:** 2026-06-10 (auditoria Shiro)

O código do `orchestrator.py` do Shiro referencia `raw.siprocal_daily_materialized` como target histórico do job Siprocal. A config Firestore atual aponta para `raw.siprocal_delivery`, mas a tabela `siprocal_daily_materialized` pode ainda existir como órfã no BQ.

**Ação:** Verificar se `raw.siprocal_daily_materialized` existe e se tem dados. Se sim, avaliar se está sendo lida por alguma view downstream (seria uma fonte paralela não intencional).

---

## ✅ RESOLVIDO — 13. Siprocal — ingestão automática inexistente (caminho manual)

**Identificado:** 2026-06-10 | **Resolvido:** 2026-06-11

O job ETL `siprocal_daily:Daily` agora lê de `raw.siprocal_raw_sheet` (VIEW sobre BQ External Table → Google Sheet live). Automação completa sem passo manual. Ver resolução do issue #10.

---

## 14. fact_io_plan — sem granularidade de plataforma (Power BI)

**Identificado:** 2026-06-10
**Impacto:** No Power BI não é possível filtrar/relacionar plano de investimento por plataforma ou campanha. Só funciona no nível cliente × data.

**Causa raiz:**
`core.io_plan_manual` agrega todas as estratégias num único flight por cliente (sem `platform`). `gold.fact_io_plan` herda esse grain, sem campo `platform`.
`gold.fact_delivery` tem `client_id + day + platform` — o JOIN só funciona no nível total do cliente.

**Solução proposta:** Adicionar coluna `platform` a `core.io_plan_manual` e mudar grain de `rebuild_core_for_client` para `client × flight × platform`. Requer: ALTER TABLE + update do script + re-sync dos dados DRIVE-SYNC existentes. DRIVE-SYNC rows ganham platform automaticamente (já existe em `raw.io_plan_drive_snapshot`). Rows manuais (Jan-Abr) ficam com `platform = NULL`.

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
