# newad-adframework-bq

Repositório de SQL, DDLs e seeds do **BigQuery AdFramework NewAD**.
Mantido por Douglas Reche — fonte da verdade para schema, migrações e IDs canônicos.

**Projeto GCP:** `adframework`
**Stack:** BigQuery · Firestore · Firebase · FastAPI (repo Shiro)
**Maintainers:** Douglas Reche, Shiro

---

## Arquitetura — 4 camadas

```
RAW  →  STG  →  CORE  →  GOLD
```

| Camada | Tipo | Responsabilidade |
|--------|------|-----------------|
| **RAW** | Tabelas físicas particionadas | Ingestão crua do ETL — tudo STRING, grain original |
| **STG** | Views | Typing correto (DATE, INT64, FLOAT64), normalização por plataforma |
| **CORE** | Tabelas + Views | Atribuição de `client_id`, IO binding, regras de negócio |
| **GOLD** | Views | Output analítico por cliente — consumido pelo dashboard |

> Datasets `pixel`, `adtracking`, `analytics`, `finops_billing` são geridos por serviços
> externos e **nunca devem ser modificados** neste repositório.

---

## Estrutura do repositório

```
/
├── raw/
│   ├── ddl/            # DDL das 10 tabelas canônicas RAW
│   └── migration/      # Scripts de migração executados (histórico)
│
├── stg/
│   └── ddl/            # DDL das 5 views STG (1 por plataforma/entrega)
│
├── core/
│   ├── seeds/          # clients.csv — fonte da verdade dos IDs de cliente
│   ├── ddl/            # DDL das tabelas CORE (dim_client, platform_client_links...)
│   └── migration/      # Scripts de carga inicial
│
├── gold/               # (em reconstrução — ver roadmap abaixo)
│   └── ...
│
├── audit/              # SQLs de auditoria e análise one-off
├── scripts/            # Scripts operacionais (ETL, inspecção, DQ)
└── docs/               # Decisões arquiteturais e contexto de negócio
```

---

## RAW — Tabelas canônicas

Executado em 2026-05-26. Todas as tabelas são particionadas por `DATE(raw_ingested_at)`.

| Tabela | Substitui | Linhas | Período |
|--------|-----------|--------|---------|
| `mediasmart_delivery` | `mediasmart_daily` | 641.798 | ago/25 → mai/26 |
| `mediasmart_revenue` | `mediasmart_revenue_daily` | 9.247 | mar/26 → mai/26 |
| `mediasmart_bid_supply` | `mediasmart_bid_supply_daily` | 602.179 | mar/26 → mar/26 |
| `mgid_delivery` | `mgid_daily` | 4.239 | ago/25 → mai/26 |
| `siprocal_delivery` | `siprocal_daily_materialized` | 706 | ago/25 → mar/26 |
| `mediasmart_advertisers` | — | — | ref. (ETL repopula) |
| `mediasmart_campaigns` | — | 2.116+ | ref. |
| `mediasmart_creatives` | — | 24.932+ | ref. |
| `mgid_campaigns` | — | 15.070+ | ref. |
| `mgid_creatives` | — | 9.858+ | ref. |

O ETL (repo Shiro) escreve nos novos nomes via `bq_destiny` no Firestore — sem alteração de código.

---

## STG — Views de normalização

Views criadas em 2026-05-26. Tipagem via `SAFE_CAST` — nunca quebra por dado sujo na RAW.

| View | Base RAW |
|------|----------|
| `stg.mediasmart_delivery` | `raw.mediasmart_delivery` |
| `stg.mediasmart_revenue` | `raw.mediasmart_revenue` |
| `stg.mediasmart_bid_supply` | `raw.mediasmart_bid_supply` |
| `stg.mgid_delivery` | `raw.mgid_delivery` |
| `stg.siprocal_delivery` | `raw.siprocal_delivery` — `advertiser` normalizado com `UPPER(TRIM())` |

---

## CORE — IDs canônicos e atribuição

### Sistema de IDs de cliente

Formato: `{slug}_{8hex}` — imutável após geração.
Fonte da verdade: [`core/seeds/clients.csv`](core/seeds/clients.csv)

Este ID é o **ID oficial da empresa** — adframework, pixel e analytics serão
migrados para usar estes IDs.

**Regra:** nunca gerar IDs fora do `clients.csv`. Para adicionar cliente: editar o CSV
e executar `core/migration/01_load_dim_client.sql`.

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

> 5 clientes `pending_confirmation` — aguardando confirmação do time comercial
> sobre separação Amigo/TecPar, Dr. Consulta/RJ e Stocco/Stoquinho.

---

## Roadmap

- [x] RAW — DDL canônico + migração executada
- [x] STG — 5 views de normalização
- [x] CORE — `dim_client` com 21 clientes e IDs canônicos
- [ ] CORE — `platform_client_links` (eventid/campaignid/advertiser → client_id)
- [ ] GOLD — views por cliente (entrega, receita, bid supply)
- [ ] Migrar adframework para usar novos client_ids
- [ ] Deletar `raw_siprocal` dataset (replica cross-region — requer console BQ)

---

## Projetos GCP

| Projeto | Uso |
|---------|-----|
| `adframework` | Produção — BQ principal, Firestore, Firebase Auth |
| `striped-bonfire-489318-t9` | Dashboard emergencial temporário — não modificar |
