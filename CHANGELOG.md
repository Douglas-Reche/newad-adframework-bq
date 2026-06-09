# CHANGELOG — AdFramework BQ Pipeline

> Registro cronológico de decisões, mudanças e evoluções arquiteturais.
> **Regra:** toda mudança relevante no pipeline, arquitetura ou decisão de negócio deve ser registrada aqui com data, motivo e arquivos tocados.
> Formato: mais recente no topo.

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
