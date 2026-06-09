# API Capabilities — MediaSmart, MGID, Siprocal

> Auditoria realizada em: 2026-06-08
> Fontes: OpenAPI spec (github.com/mediasmart/api-reference), help.mgid.com/api-advertisers, DDLs raw do repo

---

## MediaSmart

**Endpoints relevantes:**

| Endpoint | Uso |
|---|---|
| `GET /api/analytics/custom-report` | Relatório customizado por período — **usado pelo ETL atual** |
| `GET /api/analytics/drilldown/{variable}` | Breakdown por qualquer dimensão |
| `GET /api/analytics/daystats` / `daystats-report` | Dados em tempo real |
| `GET /api/analytics/availability/drilldown/{variable}` | Análise de supply/leilão |
| `GET /api/analytics/publishers/drilldown/{variable}` | Análise de publishers |

**Todas as dimensões disponíveis:**

| Categoria | Dimensão | Coletando hoje? |
|---|---|---|
| Tempo | `day` | ✅ |
| Campanha | `eventid`, `controlid`, `strategyid`, `strategyname` | ✅ |
| Device | `devicetype` | ✗ — ver etl_expansion_plan.md |
| OS | `os` | ✗ |
| Geo | `countrycode`, `geo`, `region` | ✗ — ver etl_expansion_plan.md |
| Criativo | `creativetype`, `creativename`, `size` (ad size), `nativesize` | ⚠️ só em `raw.mediasmart_daily`, não sobe ao gold |
| Publisher | `publisher`, `exchange`, `url`, `appsite` | ✗ |
| Conexão | `connectiontype`, `carrier`, `isp`, `operator` | ✗ |
| Audiência | `age`, `agegroup`, `gender`, `language` | ✗ |
| Inventário | `iabcategory`, `iabsubcategory`, `deal`, `idtype` | ✗ |
| Conversão | `convsource` (conversion_source) | ✅ |

**Todas as métricas disponíveis:**

| Métrica | Campo | Coletando hoje? |
|---|---|---|
| Impressões | `impressions` | ✅ |
| Cliques | `clicks` | ✅ |
| Spend | `wonprice` → `clientrevenue` | ✅ em `raw.mediasmart_daily` |
| Custo ao cliente | `client_cost` | ✅ em `raw.mediasmart_daily`, não sobe ao gold |
| CPM | `cpm` | ✗ (calculável) |
| CPC | `cpc` | ✗ (calculável) |
| CPA por slot | `cpa1` a `cpa5` | ✗ |
| Conversões | `conversions_1` a `conversions_5` | ✅ |
| Vídeo | `video_start`, `video_25/50/75`, `video_completion` | ✅ em `raw.mediasmart_daily`, não sobe ao gold |

**Restrições de API:**
- Rate limit: 429 após exceder quota por minuto (número exato não documentado)
- Sem limite de range de datas documentado — mas job atual dá timeout com range longo
- Formato de saída: JSON (default), CSV, Excel

---

## MGID

**Endpoint principal:** `GET /v1/goodhits/clients/{client_id}/statistics-reports`

**Dimensões disponíveis (máx. 3 por chamada):**

| Categoria | Dimensão | Coletando hoje? |
|---|---|---|
| Tempo | `day`, `week`, `month`, `hour` | ✅ `day` |
| Campanha | `campaignId`, `campaignName`, `campaignType`, `teaserId` | ✅ `campaignId` + `teaserId` |
| Device | `deviceType` → desktop/mobile/tablet/smarttv | ✗ — ver etl_expansion_plan.md |
| Device detalhe | `os`, `browser` | ✗ |
| Geo | `country`, `region` | ✗ — ver etl_expansion_plan.md |
| Fonte | `widgetId`, `source` | ✗ |

**Todas as métricas disponíveis:**

| Categoria | Métrica | Coletando hoje? |
|---|---|---|
| Entrega | `impressions`, `clicks`, `adRequests` | ✅ impressions + clicks |
| Qualidade | `viewability`, `vCtr` | ✗ |
| Financeiro | `spent`, `cpc`, `vCpm`, `revenue`, `profit`, `roas`, `epc`, `cpcWithoutDataFee` | ⚠️ `spent` (backfill parcial jun/03) |
| Conversão funil | `conversionsInterest`, `conversionsDecision`, `conversionsBuy` | ✅ |
| Conversão taxa | `conversionsRateInterest`, `conversionsRateDecision`, `conversionsRateBuy` | ✗ (calculável) |
| Conversão custo | `conversionsCostInterest`, `conversionsCostDecision`, `conversionsCostBuy` | ✗ |

**Restrições de API:**
- Máximo **3 dimensões** por chamada
- Máximo **90 dias** por request
- Máximo **1.000 linhas** por response (paginação via `limit` + `offset`)
- Implicação: device + geo requerem chamadas separadas obrigatoriamente

---

## Siprocal

**Modelo:** BQ-to-BQ export passivo — Siprocal controla o schema, não temos API própria.

**O que recebemos:**

| Campo | Tipo |
|---|---|
| `day` | Data |
| `advertiser` | Nome do anunciante (texto livre) |
| `campaign_id` | ID da campanha |
| `creative_type` | Push / Native / Display |
| `creative` | Nome do criativo |
| `impressions`, `clicks` | Métricas de entrega |

**O que NÃO temos e não controlamos:**
- `spend` / custo
- `device`
- `country` / geo
- Qualquer métrica de conversão

**Para obter dados adicionais:** negociação comercial direta com Siprocal para que incluam os campos no export.
