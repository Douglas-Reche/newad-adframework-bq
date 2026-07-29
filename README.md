# newad-adframework-bq

---
> **⚠️ REESTRUTURAÇÃO EM ANDAMENTO — 2026-06-16 ⚠️**
> A pipeline RAW/STG/GOLD foi **resetada e está sendo reconstruída do zero** devido a inconsistências estruturais acumuladas na ingestão (normalize_data no RAW, all-STRING, schema enforcement silencioso).
> Plano de rebuild: [`docs/bq_restructuring_plan.md`](docs/bq_restructuring_plan.md) · Backup core: [`docs/core_config_backup.md`](docs/core_config_backup.md)
> Documentos com schema antigo estão marcados com banner `⚠️ LEGADO` — **não use para desenvolvimento novo.**
---

Repositório de SQL, DDLs e seeds do **BigQuery AdFramework NewAD**.
Mantido por Douglas Reche — fonte da verdade para schema, migrações e IDs canônicos.

**Projeto GCP:** `adframework`
**Stack:** BigQuery · Firestore · Firebase · FastAPI (repo ETL: `rshiro-newad/adframework`)
**Maintainers:** Douglas Reche (escrita), Shiro (leitura/análise)

> Datasets `pixel`, `adtracking`, `analytics`, `finops_billing` são geridos por serviços
> externos e **nunca devem ser modificados** neste repositório.

---

## Arquitetura — 4 camadas

```
RAW  →  STG  →  CORE  →  GOLD
```

| Camada | Tipo | Responsabilidade |
|--------|------|-----------------|
| **RAW** | Tabelas físicas | Ingestão crua do ETL — grain original, tipos nativos (INT64/FLOAT64/DATE), sanitização mínima de colunas |
| **STG** | Views | Typing correto (DATE, INT64, FLOAT64), normalização por plataforma |
| **CORE** | Tabelas + Views | Atribuição de `client_id`, IO binding, regras de negócio |
| **GOLD** | Views | Output analítico por cliente — consumido pelo dashboard |

---

## Estrutura do repositório

```
/
├── raw/
│   ├── ddl/            # DDL das tabelas canônicas RAW (12 tabelas)
│   └── migration/      # Scripts de migração executados + script Firestore
│
├── stg/
│   └── ddl/            # DDL das 5 views STG de normalização
│
├── core/
│   ├── seeds/          # clients.csv + platform_client_links.csv + conversion_mapping.csv
│   ├── ddl/            # DDL das tabelas CORE (dim_client, platform_client_links, io_plan_manual)
│   └── migration/      # Scripts de carga inicial e manutenção (01–06)
│
├── gold/
│   ├── ddl/            # DDL das views GOLD (fact_delivery, fact_io_plan, dims, health)
│   ├── delivery/       # Views de entrega por cliente (Luckbet, Cora, NewAD...)
│   ├── creative/       # Views de criativos por cliente
│   └── dimensions/     # Views dimensionais gold (dim_client_semantics)
│
├── audit/
│   ├── client_analysis/  # SQLs de auditoria de propriedade de campanhas e clientes
│   └── raw_layer/        # SQLs de auditoria de schema e amostras da camada RAW
│
├── scripts/
│   ├── data_quality/   # Checks de qualidade (campaign ownership, client dedup, volumes)
│   ├── etl/            # Scripts ETL operacionais (Cora Sheets sync, Apps Script trigger)
│   ├── inspect/        # SQLs de inspeção do pipeline (overview, colunas, ERD, row counts)
│   ├── io_plan/        # Sync planilhas IO Plan (Google Drive → BQ)
│   └── siprocal/       # Sync Siprocal sheet
│
├── services/
│   └── io-plan-admin/  # Cloud Run service para admin do IO Plan
│
├── docs/               # Decisões arquiteturais, contexto de negócio e referências de API
├── CHANGELOG.md        # Histórico cronológico de decisões e mudanças
└── README.md           # Este arquivo
```

---

## RAW — Tabelas canônicas

### Tabelas de entrega e histórico (ETL ativo)

| Tabela | ETL Status | Linhas | Período | Notas |
|--------|-----------|--------|---------|-------|
| `mediasmart_delivery` | Job morto — histórico | 641.798 | ago/25 → mai/24/26 | Substituído por `mediasmart_daily` |
| `mediasmart_daily` | **Ativo** — 03:00 UTC | 170+ | mai/25/26 → hoje | 31 cols; `event_id` + `campaign_id` na mesma linha |
| `mediasmart_revenue` | Ativo | 9.247+ | mar/26 → hoje | Receita por campanha/dia |
| `mediasmart_bid_supply` | Ativo | 602.179+ | mar/26 → hoje | Inventário de leilão |
| `mgid_delivery` | Ativo | 4.239+ | ago/25 → hoje | |
| `siprocal_delivery` | Ativo | 706+ | ago/25 → hoje | |

### Tabelas de catálogo (firstlevel — WRITE_TRUNCATE)

| Tabela | Linhas | Notas |
|--------|--------|-------|
| `mediasmart_advertisers` | 21 únicos | Referência de contas (event_id) |
| `mediasmart_campaigns` | 140 únicos | Fix write_mode 2026-06-11 |
| `mediasmart_creatives` | 24.932+ | |
| `mgid_campaigns` | 15.070+ | |
| `mgid_creatives` | 9.858+ | |

### Tabelas Grupo A — MediaSmart analytics por dimensão ✅ BACKFILL JAN–JUN/2026 CONCLUÍDO

Criadas 2026-06-11. Endpoint `/api/analytics/custom-report` — schema flexível, headers normalizados via `normalize_data`. Fix `REQUEST_TIMEOUT_SECONDS = 60` deployado 2026-06-12 (commit `7bee5f9`).

| Tabela | Linhas | Período | Cron UTC |
|--------|--------|---------|----------|
| `mediasmart_creative_daily` | 394.347 | jan/26 → hoje | 03:30 |
| `mediasmart_delivery_by_device` | 206.541 | jan/26 → hoje | 03:35 |
| `mediasmart_delivery_by_geo` | 8.417.374 | jan/26 → hoje | 03:40 |
| `mediasmart_delivery_by_publisher` | 9.804.184 | jan/26 → hoje | 03:45 |
| `mediasmart_delivery_by_os` | 273.799 | jan/26 → hoje | 03:50 |
| `mediasmart_delivery_by_hour` | 5.430 | mai/28/26 → hoje | 03:55 |

### Outras tabelas RAW

| Tabela | DDL | Notas |
|--------|-----|-------|
| `io_plan_drive_snapshot` | `raw/ddl/io_plan_drive_snapshot.sql` | IO Plans do Google Drive (grain: estratégia × flight) |

---

## STG — Views de normalização

Views em `stg/ddl/`. Tipagem via `SAFE_CAST` — nunca quebra por dado sujo na RAW.

| View | Base RAW | Notas |
|------|----------|-------|
| `stg.mediasmart_delivery` | UNION `raw.mediasmart_delivery` + `raw.mediasmart_daily` | Cobertura total ago/25 → hoje sem gap |
| `stg.mediasmart_revenue` | `raw.mediasmart_revenue` | |
| `stg.mediasmart_bid_supply` | `raw.mediasmart_bid_supply` | |
| `stg.mgid_delivery` | `raw.mgid_delivery` | |
| `stg.siprocal_delivery` | `raw.siprocal_delivery` | `advertiser` normalizado com `UPPER(TRIM())` |

> **STG Grupo A (T7–T13) — design fechado, DDLs a implementar.** Ver `docs/mediasmart_stg_design.md`.

---

## CORE — IDs canônicos e atribuição

### Tabelas CORE

| Tabela | DDL | Descrição |
|--------|-----|-----------|
| `core.dim_client` | `core/ddl/dim_client.sql` | 25 clientes (16 active, 9 pending) |
| `core.platform_client_links` | `core/ddl/platform_client_links.sql` | eventid/campaignid → client_id |
| `core.io_plan_manual` | `core/ddl/io_plan_manual.sql` | IO Plans manuais (grain: flight × cliente) |

### Sistema de IDs de cliente

Formato: `{slug}_{8hex}` — imutável após geração.
**Fonte da verdade:** [`core/seeds/clients.csv`](core/seeds/clients.csv)

**Regra:** nunca gerar IDs fora do CSV. Para adicionar cliente: editar o CSV e executar `core/migration/01_load_dim_client.sql`.

| client_id | Nome | Setor | Status |
|-----------|------|-------|--------|
| `luckbet_bea15ebc` | LuckBet | apostas | active |
| `banco_cora_fe13d78a` | Banco Cora | fintech | active |
| `aperam_14d1f27e` | Aperam | industria | active |
| `einstein_6b33a588` | Einstein | saude_educacao | active |
| `mrv_f19a2136` | MRV | imobiliario | active |
| `efi_bank_ee79e91b` | Efi Bank | fintech | active |
| `pardini_60395024` | Pardini | saude_labs | active |
| `casa_construtor_adf15c2c` | Casa do Construtor | construcao | active |
| `fox_lux_55ed8992` | Fox Lux | unknown | active |
| `dooing_994db77e` | Dooing | imobiliario | active |
| `senar_105bd174` | Senar | unknown | active |
| `mopar_a47949f4` | Mopar | automotivo | active |
| `patio_medeiros_874a0358` | Patio Medeiros | unknown | active |
| `townhouses_bc40f009` | TownHouses | imobiliario | active |
| `ocupacional_98c851f5` | Ocupacional | saude_ocupacional | active |
| `dr_consulta_215378ef` | Dr. Consulta | saude | active |
| `amigo_db1c2f0c` | Amigo | unknown | pending_confirmation |
| `tecpar_edfcc744` | TecPar | unknown | pending_confirmation |
| `stocco_b712c66e` | Stocco | unknown | pending_confirmation |
| `stoquinho_56a6ee2a` | Stoquinho | educacao | pending_confirmation |
| `dr_consulta_rj_11040bf9` | Dr. Consulta RJ | saude | pending_confirmation |
| `bet7k_b777ab9c` | Bet7k | apostas | pending_confirmation |
| `lab2lab_efb1cb34` | Lab2Lab | unknown | pending_confirmation |
| `caloi_8ac28140` | Caloi | unknown | pending_confirmation |
| `catalise_0b7d18d6` | Catalise | unknown | pending_confirmation |

---

## GOLD — Views analíticas

DDLs em `gold/ddl/`. Views de entrega por cliente em `gold/delivery/` e `gold/creative/`.

| View / Tabela | Arquivo | Descrição |
|---|---|---|
| `gold.fact_delivery` | `gold/ddl/fact_delivery.sql` | Entrega consolidada por cliente/dia (todas as plataformas) |
| `gold.fact_io_plan` | `gold/ddl/fact_io_plan.sql` | IO Plan expandido por dia (`GENERATE_DATE_ARRAY`) |
| `gold.dim_campaign` | `gold/ddl/dim_campaign.sql` | Dimensão de campanhas |
| `gold.dim_client` | `gold/ddl/dim_client.sql` | Dimensão de clientes |
| `gold.dim_conversion_mapping` | `gold/ddl/dim_conversion_mapping.sql` | Mapeamento de conversões |
| `gold.pipeline_health` | `gold/ddl/pipeline_health.sql` | Monitoramento de saúde do pipeline |
| Views por cliente | `gold/delivery/`, `gold/creative/` | Views específicas Luckbet, Cora, NewAD Bet/Fintech |

---

## Projetos GCP

| Projeto | Uso |
|---------|-----|
| `adframework` | Produção — BQ principal, Firestore, Firebase Auth, Cloud Run ETL |
| `striped-bonfire-489318-t9` | Dashboard emergencial temporário — **não modificar** |

**Cloud Run ETL:** `https://adframework-etl-911847757485.us-central1.run.app`
**Revisão ativa:** `adframework-etl-00238-n4h` (com `REQUEST_TIMEOUT_SECONDS = 60`)

---

## Roadmap

- [x] RAW — DDL canônico + migração executada (2026-05-26)
- [x] STG — 5 views de normalização (2026-05-26)
- [x] CORE — `dim_client` com 25 clientes e IDs canônicos
- [x] CORE — `platform_client_links` (eventid/campaignid → client_id)
- [x] RAW — 6 tabelas Grupo A MediaSmart + backfill jan–jun/2026 (2026-06-12)
- [x] Fix ETL — `RATE_LIMIT_DELAY` 0.3→0.6 + `REQUEST_TIMEOUT_SECONDS` 10→60 (commits `4d1662f`, `7bee5f9`)
- [ ] STG — implementar DDLs Grupo A (T7–T13) no BigQuery
- [ ] STG — design MGID (ms_campaigns, mgid_delivery_by_device, mgid_delivery_by_geo...)
- [ ] STG — design Siprocal
- [ ] RAW — Jobs 7–8: `mediasmart_strategies_detail` + `mediasmart_unique_users` (iteração por ID)
- [ ] Meta Ads — integração pendente (acesso obtido 2026-06-12, token pendente)
- [ ] Google Ads — integração pendente (dados Stocco, confirmar com Douglas)
- [ ] Deletar `raw_siprocal` dataset (replica cross-region — requer console BQ)
