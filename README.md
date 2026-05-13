# NewAD AdFramework — BigQuery SQL & Documentation

Repositório de versionamento do código SQL e documentação da arquitetura de dados do **AdFramework NewAD**.

**Projeto:** Plataforma ETL + Admin UI para mídia programática  
**Stack:** BigQuery (Google Cloud) · Firebase · FastAPI  
**Maintainer:** Douglas Reche

---

## Estrutura

```
/
├── gold/               # Views da camada gold (produção BigQuery)
│   ├── delivery/       # Fatos de entrega diária
│   ├── creative/       # Fatos de criativo diário
│   └── dimensions/     # Dimensões semânticas
├── audit/              # Queries de diagnóstico e auditoria
│   ├── raw_layer/      # Auditoria da camada raw
│   └── client_analysis/# Análise de clientes e duplicações
└── docs/               # Documentação técnica
```

---

## Camada Gold — Views em produção

### Delivery (Entrega)
| View | Descrição |
|---|---|
| `gold/delivery/fct_delivery_daily.sql` | Entrega diária genérica — todos os clientes |
| `gold/delivery/fct_luckbet_delivery_daily.sql` | Entrega diária Luckbet com semântica de bet |
| `gold/delivery/fct_newad_bet_daily.sql` | Dashboard MVP — vertical Bet (anônimo) |
| `gold/delivery/fct_newad_fintech_daily.sql` | Dashboard MVP — vertical Fintech (anônimo) |

### Creative (Criativo)
| View | Descrição |
|---|---|
| `gold/creative/fct_creative_daily.sql` | Criativo diário genérico — todos os clientes |
| `gold/creative/fct_luckbet_creative_daily.sql` | Criativo diário Luckbet |

### Dimensions (Dimensões)
| View | Descrição |
|---|---|
| `gold/dimensions/dim_client_semantics.sql` | Mapeamento semântico conv1-5 por cliente |

---

## Problemas Conhecidos (documentados em `docs/known_issues.md`)

1. **Duplicação Luckbet** — `nwd_luckbet_69e72f18` (legacy) e `nwd_luckbet_a485d6bc` (canônico) referenciam os mesmos campaign IDs físicos no MediaSmart
2. **nwd_internal_newad** — `platform_client_links` aponta para a mesma conta MediaSmart que Luckbet, causando duplicação na gold
3. **Campanhas sem IO** — 2 campaigns MediaSmart com entrega real nunca foram vinculadas a um IO
4. **Cora MediaSmart histórico** — dados de ago/25–fev/26 existem na raw mas não chegam à gold via `io_calc` por ausência de IO nesses meses

---

## Dataset BigQuery

Projeto: `adframework`

| Dataset | Descrição |
|---|---|
| `raw` | Dados brutos das plataformas (MediaSmart, MGID, Siprocal) |
| `raw_newadframework` | Views do Admin UI (Firebase) — IOs, bindings, clientes |
| `stg` | Staging — normalização e tipagem |
| `core` | Registros operacionais (IO binding registry) |
| `marts` | Views intermediárias de cálculo |
| `share` | Dados consolidados acessíveis entre camadas |
| `gold` | Camada analítica final — Power BI conecta aqui |
