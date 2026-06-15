# ETL Expansion Plan — Novas Dimensões e Métricas

> Criado em: 2026-06-08  
> Atualizado em: 2026-06-09  
> Status: Planejado — implementação depende de alinhamento com Shiro (orchestrator)

**Ver também:** `docs/io_plan_pipeline.md` — pipeline de planejamento comercial (Drive → BQ) já implementado e funcionando.

---

## Princípio de arquitetura

Cada novo grupo de dimensão vira um **job separado com tabela raw própria**.
Não adicionar dimensões ao job principal — isso multiplica linhas e piora o timeout existente.

---

## Prioridades de implementação

| # | O que | Plataforma | Esforço | Depende de | Status |
|---|---|---|---|---|---|
| 1 | Corrigir timeout job principal | MediaSmart | Alto | Shiro | 🔴 Em aberto |
| 2 | Adicionar métricas financeiras | MGID | Baixo — mesmo call | Shiro | 🟡 Planejado |
| 3 | Surfar criativos ao gold | MediaSmart | Baixo — dado já existe | Douglas | 🟡 Planejado |
| 4 | Job device breakdown | MS + MGID | Médio — job novo | Shiro | 🟠 Planejado |
| 5 | Job geo breakdown | MS + MGID | Médio — job novo | Shiro | 🟠 Planejado |
| 6 | Métricas avançadas (viewability, ROAS, CPA) | MGID | Baixo — mesmo call | Shiro | ⚪ Futuro |
| 7 | Negociar device/spend com Siprocal | Siprocal | Comercial | Decisão comercial | ⚪ Futuro |

---

## Detalhamento por item

---

### #1 — Corrigir timeout MediaSmart (job `mediasmart_daily_daily`)

**Problema:** O job faz uma única chamada com range longo → timeout da API.

**Solução proposta:**
- Quebrar a chamada em janelas de **7 dias** por request
- Iterar as janelas sequencialmente no orchestrator
- Mesmo endpoint, mesmo schema — só muda o range

**Workaround ativo:** `stg.mediasmart_delivery` faz UNION com `raw.mediasmart_daily` para cobrir o gap enquanto o root cause não é resolvido.

---

### #2 — Métricas financeiras MGID (mesmo call, zero custo extra)

**Adicionar ao job `mgid_daily_daily` existente:**

```
kpis a adicionar: spent, cpc, vCpm, viewability, roas
```

**Schema a adicionar em `raw.mgid_delivery`:**
```sql
spent       FLOAT64,   -- investimento realizado
cpc         FLOAT64,   -- custo por clique
vcpm        FLOAT64,   -- CPM viewable
viewability FLOAT64,   -- % impressões viewable
roas        FLOAT64    -- retorno sobre investimento (se pixel com valor)
```

**Consideração:** `spent` já foi backfillado parcialmente em 2026-06-03. Confirmar com Shiro se já está no call atual ou precisa ser adicionado explicitamente.

---

### #3 — Surfar criativos MediaSmart ao gold (só pipeline, sem novo call)

**Dado já existe em:** `raw.mediasmart_daily` (campos: `creative_type`, `creative_id`, `size`, `nativesize`, `client_cost`, `video_start/25/50/75/completion`)

**O que fazer:**
1. Adicionar esses campos a `stg.mediasmart_delivery` (view atual não os expõe)
2. Criar `gold.dim_creative_mediasmart` ou adicionar ao `gold.fact_delivery`

**Nova tabela sugerida:** `gold.fact_delivery_detail` com grain: `day + client_id + platform + strategy + creative_type + size`

---

### #4 — Job device breakdown

**MediaSmart:**
- Endpoint: `/api/analytics/custom-report`
- Drilldown: `day,eventid,strategyid,devicetype`
- KPIs: `impressions,clicks,wonprice`
- Nova tabela raw: `raw.mediasmart_delivery_by_device`
- Grain: `day + eventid + strategyid + devicetype`
- Janela recomendada: 7 dias por chamada

**MGID:**
- Endpoint: `/v1/goodhits/clients/{id}/statistics-reports`
- Dimensions: `day`, `campaignId`, `deviceType` (exatamente 3 — limite máximo)
- Métricas: `impressions`, `clicks`, `spent`
- Nova tabela raw: `raw.mgid_delivery_by_device`
- Grain: `day + campaignId + deviceType`
- Paginação necessária: 1.000 linhas/página, iterar com offset
- Range máximo: 90 dias por chamada

**Tabela gold resultante:** `gold.fact_delivery_by_device`
```sql
day               DATE,
client_id         STRING,
platform          STRING,  -- mediasmart | mgid
device_type       STRING,  -- desktop | mobile | tablet | smarttv
impressions       INT64,
clicks            INT64,
spend             FLOAT64
```

---

### #5 — Job geo breakdown

**MediaSmart:**
- Drilldown: `day,eventid,strategyid,countrycode`
- KPIs: `impressions,clicks,wonprice`
- Nova tabela raw: `raw.mediasmart_delivery_by_geo`

**MGID:**
- Dimensions: `day`, `campaignId`, `country`
- Nova tabela raw: `raw.mgid_delivery_by_geo`
- Mesmas restrições de paginação do item #4

**Tabela gold resultante:** `gold.fact_delivery_by_geo`
```sql
day               DATE,
client_id         STRING,
platform          STRING,
country_code      STRING,
impressions       INT64,
clicks            INT64,
spend             FLOAT64
```

---

### #6 — Métricas avançadas MGID (viewability, ROAS, CPA)

**Adicionar ao call de métricas (mesmo do item #2):**
- `conversionsCostInterest`, `conversionsCostDecision`, `conversionsCostBuy`
- `conversionsRateInterest`, `conversionsRateDecision`, `conversionsRateBuy`

**Pré-requisito:** cliente precisa ter pixel de conversão com valor monetário para ROAS fazer sentido.

---

### #7b — Publisher breakdown MediaSmart *(no radar — 2026-06-11)*

**Dado disponível na API** — drilldown variables: `publishercompany`, `publisherurl`, `publisherid`, `exchange`, `domain`

**Novo job sugerido:**
- Tabela raw: `raw.mediasmart_delivery_by_publisher`
- Drilldown: `day,eventid,controlid,publishercompany,publisherurl,exchange`
- KPIs: `impressions,clicks,wonprice`

**Atenção:** publisher é dado volumoso — uma campanha pode ter centenas de publishers por dia.
Usar janela de 7 dias por chamada igual ao job de device.

**Tabela gold resultante:** `gold.fact_delivery_by_publisher`

---

### #7 — Siprocal — negociação comercial

Solicitar à Siprocal inclusão no export BQ:
- `spend` (custo por day + campaign_id)
- `device_type` (desktop/mobile/tablet)
- `country_code`

Não é mudança técnica nossa — é solicitação à Siprocal via relacionamento comercial.
