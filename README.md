# NewAD AdFramework — BigQuery SQL & Documentação

Repositório pessoal de SQL, scripts de inspeção e documentação de arquitetura do **AdFramework NewAD**.

**Projeto GCP:** `striped-bonfire-489318` (alias: `adframework`)
**Stack:** BigQuery · Firebase · FastAPI
**Maintainer:** Douglas Reche

> Estrutura extraída diretamente do BigQuery em 2026-05-12 via `scripts/inspect/`.
> Para atualizar, rode `01_all_tables_overview.sql` e `04_row_counts_and_dates.sql`.

---

## Estrutura do repositório

```
/
├── scripts/
│   ├── inspect/        # Extrai estrutura real do BigQuery (INFORMATION_SCHEMA)
│   └── data_quality/   # Verifica integridade: duplicação, orphans, volume
├── gold/
│   ├── delivery/       # Views de entrega diária
│   ├── creative/       # Views de criativo diário
│   └── dimensions/     # Dimensões semânticas
├── audit/
│   ├── client_analysis/
│   └── raw_layer/
└── docs/               # Contexto de negócio (não deriva do código)
```

---

## Camadas BigQuery — estado real

### `raw` — Dados brutos das plataformas (tabelas físicas)

| Tabela | Linhas | Tamanho | Última atualização |
|---|---|---|---|
| `mediasmart_daily` | 640.438 | 140,7 MB | 2026-05-12 |
| `mediasmart_bid_supply_daily` | 602.179 | 161,8 MB | 2026-03-21 |
| `mediasmart_creatives` | 24.932 | 6,6 MB | 2026-05-12 |
| `mediasmart_revenue_daily` | 8.840 | 1,0 MB | 2026-05-12 |
| `mediasmart_campaigns` | 2.116 | 2,7 MB | 2026-05-12 |
| `mediasmart_advertisers` | 746 | 0,1 MB | 2026-05-12 |
| `mgid_daily` | 4.154 | 0,3 MB | 2026-05-12 |
| `mgid_campaigns` | 15.070 | 24,9 MB | 2026-05-12 |
| `mgid_creatives` | 9.858 | 18,6 MB | 2026-05-12 |
| `mgid_daily_device` | 803 | — | 2026-04-14 |
| `siprocal_daily_materialized` | 706 | 0,1 MB | 2026-05-12 |
| `siprocal_daily_native` | 706 | — | 2026-03-09 |
| `siprocal_daily` | — | — | externa (GCS) |
| `mediasmart_daily_operational` | **0** | — | ⚠️ vazia |
| `mediasmart_daily_creative` | **0** | — | ⚠️ vazia |

**Backups antigos (fev/26) — candidatos a drop:**
- `mediasmart_daily_backup_20260227_111821` (595k linhas)
- `mediasmart_daily_legacy_20260227_061441` (626k linhas)
- `mediasmart_daily_legacy_20260227_065635` (626k linhas)
- `mgid_daily_legacy_20260227_061627` / `mgid_daily_legacy_20260227_065913`

### `raw_newadframework` — Admin UI via Firebase (todas views)

| View | Descrição |
|---|---|
| `platform_client_links` | Mapeamento newad_client_id → conta de plataforma |
| `io_manager_v2` | IOs criados no Admin UI |
| `io_line_bindings_v2` | Bindings campaign/strategy → IO line |
| `proposal_lines` | Linhas de proposta |
| `proposals` | Cabeçalhos de proposta |

### `stg` — Staging (normalização e tipagem, todas views)

| View | Descrição |
|---|---|
| `mediasmart_daily_std` | `raw.mediasmart_daily` normalizada |
| `mediasmart_operational_daily` | Entrega operacional MediaSmart |
| `mediasmart_operational_v2` | Entrega operacional MediaSmart v2 |
| `mediasmart_revenue_daily` | Receita DSP MediaSmart |
| `mediasmart_creative_daily` | Criativo MediaSmart |
| `mediasmart_bid_supply_daily` | Bid supply MediaSmart |
| `mgid_daily_std` | `raw.mgid_daily` normalizada |
| `mgid_operational_v2` | Entrega operacional MGID |
| `siprocal_daily_std` | `raw.siprocal_daily_materialized` normalizada |
| `siprocal_operational_v2` | Entrega operacional Siprocal |
| `newad_operational_daily` | Consolidado das 3 plataformas |
| `newad_operational_daily_v2` | Consolidado v2 |
| `newad_creative_daily` | Criativo consolidado |
| `newad_revenue_daily` | Receita consolidada |
| `io_lines_v4` | IO lines enriquecidas com contexto de IO |

### `core` — Registros operacionais (tabelas físicas + views)

| Objeto | Tipo | Linhas | Descrição |
|---|---|---|---|
| `io_manager_v2` | tabela | 229 | IOs (espelho Firebase) |
| `io_line_bindings_v2` | tabela | 170 | Bindings campaign/strategy |
| `platform_client_links` | tabela | 27 | Links cliente-plataforma |
| `io_manager_legacy_cache` | tabela | 62 | Cache de IOs legados |
| `proposal_lines` | tabela | **0** | ⚠️ vazia |
| `proposals` | tabela | **0** | ⚠️ vazia |
| `io_manager` | externa | — | Planilha Google Sheets |
| `io_binding_registry_v4` | view | — | Registro de bindings v4 |
| `io_line_bindings_enriched_v2` | view | — | Bindings com contexto |
| `io_registry_v4` | view | — | Registry de IOs v4 |
| `io_manager_enriched` / `_v2` | view | — | IO manager enriquecido |

### `marts` — Cálculo intermediário (todas views em uso; tabelas físicas vazias)

| View | Descrição |
|---|---|
| `io_calc_daily_v4` | Delivery + planejamento por IO line (schedule-driven) |
| `io_delivery_daily_v4` | Join delivery × bindings × datas do IO |
| `io_schedule_daily_v4` | Calendário de dias úteis do IO |
| `io_line_plan_daily_v3` | Budget diário previsto |
| `io_line_actual_daily_v3` | Budget realizado diário |
| `io_line_kpis_daily_v3` | KPIs por linha de IO |
| `io_line_revenue_daily_v3` | Receita por linha de IO |
| `io_kpis_daily_v3` | KPIs agregados por IO |
| `io_kpis_daily_by_model_v3` | KPIs por modelo de compra |
| `fact_daily_detail` / `fact_daily_io` | Fatos intermediários |

⚠️ Tabelas físicas `io_kpis_daily_*_mat` e `io_roas_daily_v3_mat` estão vazias — descontinuadas.

### `share` — Dados consolidados (acesso cross-layer)

| Objeto | Tipo | Linhas | Descrição |
|---|---|---|---|
| `io_calc_daily_v4` | view | — | Espelho de `marts.io_calc_daily_v4` |
| `io_delivery_daily_v4` | view | — | Espelho de `marts.io_delivery_daily_v4` |
| `newad_operational_daily` | view | — | Entrega consolidada 3 plataformas |
| `platform_daily_detail` | view | — | Detalhe por campaign/strategy/criativo |
| `newad_revenue_daily` | view | — | Receita DSP consolidada |
| `io_kpis_daily_v3` | view | — | KPIs por IO |
| `admin_client_linking_options` | view | — | Opções de linking para Admin UI |
| `dashboard_cards_campaign` / `_detail` | view | — | Cards dashboard interno |
| `adops_mediasmart_bid_supply_*` | views | — | Supply para adops |
| `report_daily_campaign_demo` | **tabela** | 6.039 | Dados de demo comercial |
| `io_validation_full` | **tabela** | 48 | Validação antiga (fev/26) |

### `gold` — Camada analítica final (Power BI conecta aqui)

Todas são views. Nenhuma tabela física.

| View | Descrição |
|---|---|
| `fct_delivery_daily` | Entrega diária — todos os clientes |
| `fct_luckbet_delivery_daily` | Entrega Luckbet com semântica de bet |
| `fct_newad_bet_daily` | MVP dashboard vertical Bet (anônimo) |
| `fct_newad_fintech_daily` | MVP dashboard vertical Fintech (anônimo) |
| `fct_creative_daily` | Criativo diário — todos os clientes |
| `fct_luckbet_creative_daily` | Criativo Luckbet |
| `fct_io_plan_daily` | Planejamento de IO diário |
| `dim_client` | Dimensão de clientes |
| `dim_client_semantics` | Mapeamento semântico conv1-5 por cliente |
| `dim_creative` | Dimensão de criativos |
| `dim_date` | Dimensão de calendário |
| `dim_io_line` | Dimensão de linhas de IO |
| `dim_platform` | Dimensão de plataformas |

---

## Problemas conhecidos

Ver [`docs/known_issues.md`](docs/known_issues.md) para detalhes com causa raiz e ação necessária.

1. **Duplicação Luckbet** — `nwd_luckbet_69e72f18` (legacy) referencia os mesmos campaigns que `nwd_luckbet_a485d6bc` (canônico)
2. **nwd_internal_newad** — aponta para a mesma conta MediaSmart da Luckbet, contamina a gold
3. **Campanhas órfãs** — 2 campaigns MediaSmart com entrega real sem IO binding
4. **Cora histórico** — dados ago/25–fev/26 existem na raw mas não chegam à gold via io_calc (workaround em `fct_newad_fintech_daily`)
5. **Siprocal** — atribuição por nome, não por ID — risco de colisão entre client IDs

---

## Como inspecionar o estado atual

```bash
# O que existe em cada camada (sem custo de processamento)
bq query --use_legacy_sql=false < scripts/inspect/01_all_tables_overview.sql

# Schema completo de colunas
bq query --use_legacy_sql=false < scripts/inspect/02_columns_by_layer.sql

# DDL real das views gold (fonte de verdade)
bq query --use_legacy_sql=false < scripts/inspect/03_gold_view_definitions.sql

# Volume por tabela (sem custo — usa metadados)
bq query --use_legacy_sql=false < scripts/inspect/04_row_counts_and_dates.sql

# Intervalo de datas por tabela de fato (processa dados)
bq query --use_legacy_sql=false < scripts/inspect/05_date_ranges_per_table.sql
```
