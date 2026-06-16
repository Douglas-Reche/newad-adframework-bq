# Problemas Conhecidos — AdFramework BigQuery

> Última atualização: 2026-06-15 — MS eventid NULL corrigido (rename fix + deploy 00249-c4j); backfill Mai 25-26 e Jun 11-15 concluídos; STG 3 plataformas 100% atribuído.
> Autor: Douglas Reche

---

## 🗑️ Limpeza pendente (executar após STG Siprocal estabilizar)

| # | Tabela | Motivo | Ação |
|---|---|---|---|
| C1 | `raw.siprocal_raw_sheet` | Pipeline antigo (`sync_sheet.py`) — descontinuado em 2026-06-14 quando `SiproCalConnector` entrou em produção. Tabela vazia ou com dados legados, não usada por nenhum job atual. | `DROP TABLE adframework.raw.siprocal_raw_sheet` |
| C2 | `raw.siprocal_sheet_ext` | External Table auxiliar linkada direto na Google Sheet — usada só para inspeção ad-hoc. Não faz parte do pipeline. Pode ser recriada a qualquer momento se precisar inspecionar a sheet. | `DROP EXTERNAL TABLE adframework.raw.siprocal_sheet_ext` |

> **Quando executar:** após `stg.siprocal_delivery` e `gold.fact_delivery` Siprocal validados em produção (ver próximos passos do pipeline Siprocal).

---

## ✅ Resolvidos em 2026-06-15

| # | Problema | Resolução |
|---|---|---|
| MS1 | **`raw.mediasmart_daily` — `eventid` NULL desde 2026-06-11 (e no backfill Mai 25-26)** — `stg.ms_delivery` mostrava `ms_client_id = NULL` para todas as datas a partir de Jun/11. Causa raiz: `normalize_data()` em `base.py` converte headers da API para snake_case (`event_id`, `campaign_id`, `strategy_id`), mas `raw.mediasmart_daily` tem schema BQ com nomes antigos (`eventid`, `controlid`, `strategyid`) herdados do sistema do Shiro (aat-console). `load_data()` em `bigquery.py` dropa colunas do DataFrame não presentes no schema existente, então `event_id` era descartado e `eventid` ficava NULL. O bug existia desde que o Python ETL assumiu o carregamento (Shiro parou em Jun/11); o backfill de Mai 25-26 (issue D2) também foi afetado pelo mesmo motivo. | Fix: adicionado rename explícito em `_run_mediasmart_daily()` (orchestrator.py) ANTES de `bq.load_data()`: `df.rename(columns={"event_id":"eventid","campaign_id":"controlid","strategy_id":"strategyid","strategy_name":"strategyname"})`. Commit `842ab47`. Deploy revision `adframework-etl-00249-c4j` via tagged image (workaround: `gcloud builds submit --tag ... --dockerfile adframework_python/Dockerfile` + `gcloud run deploy --image` — o flow `--source .` gera imagens sem tag que Cloud Run não importa). Backfill: DELETE nas rows NULL + `force_from_date` → 34 rows Jun 11-15 + 204 rows Mai 25-Jun 15. STG resultado: ms_delivery 642.180 rows, 0 NULL client_id, max Jun 15. |
| MS2 | **Deploy `gcloud run deploy --source .` gerando imagens sem tag não importáveis** — revisões 00244 a 00247 falharam com `ContainerImageImportFailed`. Imagem buildada com sucesso no Artifact Registry mas sem tag (`TAGS: []`), Cloud Run não conseguia importar. | Workaround: usar `gcloud builds submit --tag <image>:<tag> --project <proj>` no diretório com Dockerfile, depois `gcloud run deploy --image <image>:<tag>`. Imagem tagueada importa normalmente. Causa raiz exata do comportamento `--source .` não investigada — pode ser bug do gcloud SDK local ou política do projeto. |
| SIP1 | **`raw.siprocal_delivery` — dados truncados em Jun/09 (1.078 rows, max Jun/09)** — filtro básico ativo na coluna C da Google Sheet (`Campanha`) ocultava ~27 linhas de Jun/10-14 via API `values.get()`. Service account ETL tem acesso Viewer; `values.get()` respeita filtros básicos para Viewers. | Fix: `SheetsClient.read_values()` trocado de `values.get()` para `spreadsheets.get(includeGridData=True)` — lê GridData raw, imune a qualquer filtro independente do nível de acesso. Commit `ff1f6f5`. Deploy revision `adframework-etl-00243-hg5`. Resultado: 1.105 rows / 2025-08-22 → 2026-06-14. |

**Estado STG pós-correções (2026-06-15):**

| Tabela | Rows | NULL client_id | Min date | Max date |
|---|---|---|---|---|
| `stg.ms_delivery` | 642.180 | **0** | 2025-08-01 | 2026-06-15 |
| `stg.mgid_delivery` | 2.344 | **0** | 2025-10-01 | 2026-06-14 |
| `stg.siprocal_delivery` | 1.105 | **0** | 2025-08-22 | 2026-06-14 |

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
**Data resolvido (definitivo):** 2026-06-14

**Causa raiz:**  
A tabela `raw.siprocal_daily_native` (fonte original do ETL job) foi deletada entre 01/06 e 05/06, provavelmente durante uma limpeza. O ETL job `siprocal_daily:Daily` continuou tentando ler dela e falhando com 404 todos os dias.

**Diagnóstico (2026-06-11):**
- Automação ETL **sempre existiu**: Cloud Scheduler `adframework-etl-daily` (05:00 UTC) → job `siprocal_daily:Daily`
- Job lia de `platform_endpoints/siprocal_ep_external_daily.path_template` = `external://bq/raw.siprocal_daily_native`
- `siprocal_daily_native` sumiu → 404 a partir de ~02/06. Não existe Cloud Run Job ou outro scheduler que a populava.

**Resolução parcial (2026-06-11):**
Criada `raw.siprocal_raw_sheet` como TABLE nativa BQ com 1.078 linhas. Pipeline provisório:
`sync_sheet.py → raw.siprocal_raw_sheet → ETL job → raw.siprocal_delivery`
Funcionou parcialmente (dados até 09/06), mas dependia de passo manual + 3 bugs bloqueavam Jun/10 e Jun/11.

**Resolução definitiva (2026-06-14) — SiproCalConnector:**

Pipeline inteiro substituído por conector direto `SiproCalConnector` (`src/connectors/siprocal.py`).
Elimina `sync_sheet.py`, `siprocal_raw_sheet` intermediário e qualquer dependência de ADC local.

4 bugs corrigidos em 2026-06-14:
1. Firestore `siprocal_daily_external`: `bq_project_id/dataset_id/table_id` eram `None` → adicionado `adframework/raw/siprocal_delivery`
2. Firestore `siprocal.secrets.sheet_range`: `Planilha1!A:G` (aba inexistente) → `raw_daily!A:G`
3. Python closure late-binding em `_get()` dentro do loop `for raw_row in values[1:]` → corrigido com `def _get(field, _row=raw_row)` (default arg captura valor atual)
4. Cloud Run não faz auto-deploy por push → deploy manual obrigatório após cada mudança

**Bug adicional descoberto e corrigido em 2026-06-15 — SheetsClient filtro básico:**

**Sintoma:** `raw.siprocal_delivery` travou em Jun/09 (1.078 rows) apesar de a sheet ter dados até Jun/14.
**Causa raiz:** `SheetsClient.read_values()` usava `values.get()` que respeita filtros básicos ativos quando a conta tem acesso **Viewer**. O service account `adframework-etl@adframework.iam.gserviceaccount.com` é Viewer na sheet. A equipe Siprocal ativou um filtro na coluna Campanha (C) que escondia ~27 linhas de Jun/10-14, tornando-as invisíveis para a API.

**Fix (commit `ff1f6f5`):** `SheetsClient.read_values()` trocou `values.get()` por `spreadsheets.get(includeGridData=True)`. O `includeGridData` lê o GridData raw da planilha, que não é afetado por filtros de qualquer tipo, independente do nível de acesso da conta.

```python
# ANTES (afetado por filtros básicos para Viewer accounts)
result = self.service.spreadsheets().values().get(spreadsheetId=..., range=...).execute()

# DEPOIS (imune a filtros)
response = self.service.spreadsheets().get(
    spreadsheetId=..., ranges=[range_name], includeGridData=True
).execute()
# extrai formattedValue de cada cell em response["sheets"][0]["data"][0]["rowData"]
```

**Arquitetura atual (funcionando desde 2026-06-15):**
```
Google Sheet raw_siprocal (aba raw_daily!A:G)
  └─ SheetsClient.read_values() → spreadsheets.get(includeGridData=True)
       └─ SiproCalConnector (src/connectors/siprocal.py)
            └─ orchestrator._run_siprocal_daily()
                 └─ raw.siprocal_delivery [WRITE_TRUNCATE — substitui tudo a cada run]
                      └─ stg.siprocal_delivery → gold.fact_delivery

Firestore:
  platform_reports/siprocal_daily_external  — schedule: 03:20 UTC
  platform_credentials/siprocal.secrets     — {spreadsheet_id, sheet_range: raw_daily!A:G}
```

**Nota de qualidade de dados:** 181 das 1.105 linhas têm `campaign_id = "(vazio)"` — campo PI Externo não preenchido pela Siprocal. Não bloqueia atribuição de cliente (usa campo `advertiser`/Campanha), mas é dado incompleto. Clientes afetados: AMIGOTECPAR, BANCOCORA, DRCONSULTA, PATIOMEDEIROS, SENAR, TECPAR.

**Estado atual (2026-06-15):**
- `raw.siprocal_delivery`: 1.105 linhas | 2025-08-22 → 2026-06-14 | `last_status: ok`
- Cloud Run revision: `adframework-etl-00243-hg5` (deploy manual 2026-06-15)
- Zero passos manuais necessários — pipeline 100% automático e imune a filtros da sheet

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

## ✅ RESOLVIDO — M1. MGID raw tables com alta duplicação

**Resolvido em 2026-06-14.** Firestore `write_mode` alterado para `WRITE_TRUNCATE` em `mgid_firstlevel_campaigns` e `mgid_firstlevel_creatives`. Auditado em 2026-06-15: `raw.mgid_campaigns` = 173 rows / 173 IDs únicos (1.0×). `raw.mgid_creatives` = 165 rows. Sem duplicação.

---

## ✅ RESOLVIDO — M2. MGID `spent` sem dados

**Resolvido em 2026-06-14.** `raw.mgid_stats_daily` (Job A) criado via endpoint `statistics-reports` com métricas `spent`, `cpc`, `revenue`, `profit`, `roas`. `stg.mgid_revenue` (T8) em produção com 2.344 rows, período 2025-10-01 → hoje. Total spent histórico: R$157.271,98. `raw.mgid_delivery` (legacy) descontinuado como fonte de spent.

---

## M4. MGID — novas campanhas não vinculadas automaticamente ao `platform_client_links` 🔧 BACKLOG PÓS-ENTREGA

**Identificado:** 2026-06-15
**Impacto:** Cada novo flight MGID (mensal por cliente) cria um `campaignid` novo que não existe em `platform_client_links` → STG mostra `mgid_client_id IS NULL` → dados ficam como `unattributed` na gold até correção manual.

**Workaround atual (2026-06-15):** detecção e INSERT manuais via `C:\Temp\add_mgid_campaigns_jun2026.py`. Rodado manualmente após auditoria — 6 campanhas de jun/2026 adicionadas (Einstein, Senar ×2, Amigo, Stoquinho, Banco Cora). `stg.mgid_delivery` agora 100% atribuído.

**Solução planejada:** novo job Python no orchestrador `mgid_link_new_campaigns`, roda após `mgid_firstlevel_campaigns`:
1. Detecta campanhas em `raw.mgid_stats_daily` (últimos 7 dias) sem entrada em `platform_client_links`
2. Infere `client_id` pelo nome da campanha (CASE WHEN keyword map)
3. Insere como `pending_confirmation` (match confiante) ou `unresolved` (ambíguo)
4. Loga para revisão humana semanal

**Plataformas afetadas:** somente MGID (campaignid por flight). MediaSmart (eventid por advertiser) e Siprocal (advertiser string) mudam só ao onboarbar cliente novo — manual é suficiente.

**Pré-requisito:** coordenar com Shiro para adicionar job ao orchestrador, ou criar Cloud Scheduler independente.

---

## M3. `raw.mgid_stats_daily` com 1.95× duplicação no raw

**Identificado:** 2026-06-15 (auditoria)
**Impacto:** Baixo — `stg.mgid_delivery` (T3) e `stg.mgid_revenue` (T8) já aplicam `ROW_NUMBER() OVER (PARTITION BY day, campaignid ORDER BY raw_ingested_at DESC)` para dedup. STG entrega 2.344 rows únicos corretamente.

**Causa:** Job A usa `WRITE_APPEND` (comportamento correto para ingestão diária). O backfill foi executado em múltiplos triggers sobrepostos, acumulando ~2.222 linhas duplicadas.

| Tabela | Total rows | Grains únicos | Fator dup |
|---|---|---|---|
| `raw.mgid_stats_daily` | 4.566 | 2.344 | 1.95× |

**Ação:** Dedup pontual `SELECT DISTINCT *` reduz raw para 2.344 rows. Não urgente pois a STG já corrige. Executar junto com próxima janela de manutenção.
```sql
CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_daily`
AS SELECT DISTINCT * FROM `adframework.raw.mgid_stats_daily`;
```

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
