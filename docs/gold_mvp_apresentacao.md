# AdFramework — Gold Layer MVP: Análise, Arquitetura e Implementação

> Documento gerado em 2026-04-28 | Projeto: `adframework` (GCP) | Autor: Douglas Reche

---

## Sumário

1. [Contexto e Problema](#1-contexto-e-problema)
2. [Diagnóstico do BigQuery Atual](#2-diagnóstico-do-bigquery-atual)
3. [Descobertas Críticas](#3-descobertas-críticas)
4. [Arquitetura Gold — Star Schema MVP](#4-arquitetura-gold--star-schema-mvp)
5. [Validação de Dados — Resultados Reais](#5-validação-de-dados--resultados-reais)
6. [SQLs Implementados](#6-sqls-implementados)
7. [Conexão Power BI](#7-conexão-power-bi)
8. [Medidas DAX](#8-medidas-dax)
9. [Problemas de Qualidade Identificados](#9-problemas-de-qualidade-identificados)
10. [Próximos Passos](#10-próximos-passos)

---

## 1. Contexto e Problema

### Objetivo

Criar uma conexão Power BI com o BigQuery da Newad para construção de dashboards de mídia programática (delivery, pacing, KPIs por IO line).

### Problema Central

O BigQuery possuía **~50 views encadeadas em 5 camadas** sem materialização física, tornando impossível:
- Rastrear linhagem de dados no Power BI
- Identificar IDs únicos estáveis entre tabelas
- Usar Import Mode (único viável para performance)
- Auditar custo de processamento por query

```
ANTES (problemático para BI):
raw → stg (views) → core (views) → marts (views) → share (views)
         ↑              ↑               ↑               ↑
   sem dados      sem dados       sem dados       sem dados
   armazenados    armazenados     armazenados     armazenados
```

---

## 2. Diagnóstico do BigQuery Atual

### Inventário Completo Encontrado

| Dataset | Tipo de Objetos | Quantidade | Status |
|---------|----------------|------------|--------|
| `raw` | Tabelas físicas | 19 tabelas | ✅ Ativo — fonte primária |
| `raw_mediasmart` | Tabelas físicas | 11 tabelas | ⚠️ Duplicata de `raw` |
| `raw_mgid` | Tabelas físicas | 6 tabelas | ⚠️ Duplicata de `raw` |
| `raw_siprocal` | Tabelas físicas | — | ⚠️ Duplicata de `raw` |
| `raw_newadframework` | Tabelas físicas | — | ⚠️ A verificar |
| `stg` | Views | 19 views | ✅ Views de transformação |
| `core` | Misto | 12 objetos | ⚠️ io_manager é EXTERNAL TABLE |
| `marts` | Misto | 22 objetos | ⚠️ Views + 4 tabelas materializadas |
| `share` | Views | 50+ views | ⚠️ Muitas redundantes/legado |
| `pixel` | Tabelas físicas + view | 4 objetos | ✅ Silo separado, funcional |
| `analytics` | — | — | A verificar |
| `finops_billing` | — | — | Billing |

**Total estimado: ~150+ objetos no BigQuery de produção.**

### Datasets Raw Duplicados

```
raw.mediasmart_daily          =  raw_mediasmart.mediasmart_daily
raw.mgid_daily                =  raw_mgid.mgid_daily
raw.siprocal_daily_materialized = raw_siprocal.*
```

Estes datasets paralelos existem por conta de migrações históricas e estão consumindo armazenamento desnecessário.

### Tabelas de Backup Esquecidas (produção)

```
raw.mediasmart_daily_backup_20260227_111821   ← backup manual de fev/2026
raw.mediasmart_daily_legacy_20260227_061441   ← legado fev/2026
raw.mediasmart_daily_legacy_20260227_065635   ← legado fev/2026
raw.mgid_daily_legacy_20260227_061627         ← legado fev/2026
raw.mgid_daily_legacy_20260227_065913         ← legado fev/2026
```

---

## 3. Descobertas Críticas

### 3.1 Objetos Quebrados (erram se consultados)

8 views em `core` leem de `marts.fact_delivery_daily_v2`, view que **não é mais criada** pelo `init_bq.py` atual:

| View Quebrada | Lê de |
|--------------|-------|
| `core.dim_platform` | `marts.fact_delivery_daily_v2` (inexistente) |
| `core.dim_campaign` | idem |
| `core.dim_advertiser` | idem |
| `core.dim_buying_model` | idem |
| `core.dim_device` | idem |
| `core.dim_format` | idem |
| `core.dim_creative` | idem |
| `marts.kpi_daily` | idem |

### 3.2 Taxa de Match Delivery × IO

Resultado do teste de join `stg.mediasmart_daily + stg.mgid_daily` × `core.io_manager_v2`:

| Período | Total Linhas | Com IO | Sem IO | % Match |
|---------|-------------|--------|--------|---------|
| Out/2025 | 95.885 | 49.392 | 46.493 | 51,5% |
| Nov/2025 | 39.983 | 6.708 | 33.275 | **16,8%** |
| Dez/2025 | 37.038 | 0 | 37.038 | **0,0%** |
| Jan/2026 | 84.046 | 37.188 | 46.858 | 44,2% |
| Fev/2026 | 103.266 | 56.718 | 46.548 | 54,9% |
| **Mar/2026** | **124.578** | **124.335** | **243** | **99,8%** ✅ |
| Abr/2026 | 14.726 | 3.754 | 10.972 | 25,5% |

**Conclusão:** O join funciona perfeitamente quando o IO Manager está preenchido (99,8% em março). O problema é operacional — campanhas rodando sem IO registrado.

### 3.3 Causas do Match Baixo em Abril

```sql
-- IOs com platform_campaign_id = NULL (nunca fazem match)
| NULL | Newad | Mídia Programática  | 2026-04-27 | 2026-05-30 |
| NULL | Newad | Retargeting         | 2026-04-27 | 2026-05-30 |

-- IOs duplicados para o mesmo campaign_id
xdclmxqedpue0sr9qrvavpotcjwwpvcu → aparece 2x em abril
```

### 3.4 Cost Platform = Zero

`client_cost` nas views `stg.*` retorna 0 para todos os registros. O custo real da plataforma está em tabelas separadas (`raw.mediasmart_revenue_daily`) que não fazem parte do pipeline `stg` atual.

**Solução MVP:** usar `cost_estimated` (calculado por buying_model × buying_value × volume) = **R$ 679.080** no período março-abril/2026.

---

## 4. Arquitetura Gold — Star Schema MVP

### Decisão de Design

- **Escopo:** março/2026 em diante (dados com cobertura adequada de IO)
- **Linhas sem IO:** incluídas com `io_id = NULL` (visibilidade de campanhas não gerenciadas)
- **Custo:** `cost_estimated` calculado pelo buying model (não custo real de plataforma)
- **Materialização:** tabelas físicas, sem views encadeadas


### Modelo Star Schema
### Modelo Star Schema (V2 - LuckBet MVP)

```
                    dim_date
                       │
         ┌─────────────┼──────────────┐
         │             │              │
         ▼             ▼              ▼
fct_delivery_    fct_io_plan_    dim_io_line ──── dim_advertiser
detail_daily     daily               │
         │             │         dim_platform
         └─────────────┘
              via io_id
```

### Tabelas Criadas no Dataset `adframework.gold`

| Tabela | Tipo | Grain | Partição | Cluster |
|--------|------|-------|----------|---------|
| `dim_date` | Dimensão | 1 linha por data | — | — |
| `dim_platform` | Dimensão | 1 linha por plataforma | — | — |
| `dim_advertiser` | Dimensão | 1 linha por anunciante | — | — |
| `dim_io_line` | Dimensão | 1 linha por IO line | — | — |
| `dim_creative` | Dimensão | 1 linha por criativo | — | — |
| `fct_delivery_detail_daily` | Fato | data × IO × campanha × criativo × device × fonte | `date` | `io_id, platform_id` |
| `fct_io_plan_daily` | Fato | data × IO line | `date` | `io_id` |

---

## 5. Validação de Dados — Resultados Reais

### fct_delivery_detail_daily

```
Total de linhas:     73.683
Com IO match:        62.302  (84,6%)
Sem IO match:        11.381  (15,4%)
Período:             2026-03-01 → 2026-04-27
Plataformas:         2 (mediasmart, mgid)
Campanhas distintas: 40
Impressões totais:   79,35 milhões
Custo estimado:      R$ 679.080,03
```

### fct_io_plan_daily

```
Total de linhas:     757
IO lines ativas:     26
Período:             2026-03-01 → 2026-04-29
Budget planejado:    R$ 786.258,40
Plataformas:         3 (mediasmart, mgid, siprocal)
```

### Amostra de Dados (abril/2026, top por custo)

| Data | Plataforma | Campanha | Modelo | Impressões | Cliques | Custo Est. | CPM Efet. |
|------|-----------|---------|--------|-----------|---------|------------|-----------|
| 2026-04-01 | mediasmart | Mídia Programática | CPM | 376.929 | 815 | R$ 4.231 | R$ 11,23 |
| 2026-04-16 | mediasmart | Mídia Programática | CPM | 438.192 | 1.743 | R$ 4.007 | R$ 9,14 |
| 2026-04-17 | mediasmart | Mídia Prog. (Cópia) | CPM | 315.265 | 746 | R$ 3.783 | R$ 12,00 |

---

## 6. SQLs Implementados

### Criar Dataset Gold

```sql
-- Rodar uma vez no BQ Console
CREATE SCHEMA IF NOT EXISTS `adframework.gold`
OPTIONS (location = 'US');
```

### gold.dim_date

```sql
CREATE OR REPLACE TABLE `adframework.gold.dim_date` AS
SELECT
  d                                AS date_key,
  FORMAT_DATE('%Y%m%d', d)         AS date_id,
  EXTRACT(YEAR FROM d)             AS year,
  EXTRACT(MONTH FROM d)            AS month_number,
  FORMAT_DATE('%B', d)             AS month_name,
  FORMAT_DATE('%b', d)             AS month_name_short,
  EXTRACT(DAY FROM d)              AS day,
  FORMAT_DATE('%A', d)             AS weekday_name,
  EXTRACT(DAYOFWEEK FROM d)        AS weekday_number,
  EXTRACT(QUARTER FROM d)          AS quarter,
  FORMAT_DATE('%Y-Q%Q', d)         AS year_quarter,
  FORMAT_DATE('%Y-%m', d)          AS year_month,
  DATE_TRUNC(d, WEEK(MONDAY))      AS week_start,
  DATE_TRUNC(d, MONTH)             AS month_start,
  DATE_TRUNC(d, QUARTER)           AS quarter_start
FROM UNNEST(GENERATE_DATE_ARRAY('2026-03-01',
  DATE_ADD(CURRENT_DATE(), INTERVAL 2 YEAR))) AS d;
```

### gold.dim_platform

```sql
CREATE OR REPLACE TABLE `adframework.gold.dim_platform` AS
SELECT 'mediasmart' AS platform_id, 'MediaSmart' AS platform_name
UNION ALL SELECT 'mgid',      'MGID'
UNION ALL SELECT 'siprocal',  'Siprocal';
```

### gold.dim_advertiser

```sql
CREATE OR REPLACE TABLE `adframework.gold.dim_advertiser` AS
SELECT DISTINCT
  COALESCE(
    NULLIF(advertiser_id, ''),
    TO_HEX(SHA256(LOWER(IFNULL(advertiser, ''))))
  )                  AS advertiser_id,
  advertiser         AS advertiser_name,
  newad_client_id
FROM `adframework.core.io_manager_v2`
WHERE advertiser IS NOT NULL;
```

### gold.dim_io_line

```sql
CREATE OR REPLACE TABLE `adframework.gold.dim_io_line` AS
WITH dedup AS (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY io_id
      ORDER BY updated_at DESC
    ) AS rn
  FROM `adframework.core.io_manager_v2`
)
SELECT
  io_id,
  proposal_id,
  line_id,
  line_number,
  line_item                                                              AS line_name,
  line_status,
  LOWER(platform)                                                        AS platform_id,
  COALESCE(
    NULLIF(advertiser_id, ''),
    TO_HEX(SHA256(LOWER(IFNULL(advertiser, ''))))
  )                                                                      AS advertiser_id,
  advertiser                                                             AS advertiser_name,
  newad_client_id,
  campaign_name,
  campaign_type,
  funnel,
  objective,
  target,
  interest,
  creative_type                                                          AS io_creative_type,
  target_device,
  buying_model,
  buying_value,
  deliverable_metric,
  deliverable_volume,
  total_budget,
  platform_campaign_id,
  platform_line_item_id,
  start_date,
  end_date,
  DATE_DIFF(end_date, start_date, DAY) + 1                              AS total_days,
  SAFE_DIVIDE(total_budget,       DATE_DIFF(end_date, start_date, DAY) + 1) AS daily_budget_target,
  SAFE_DIVIDE(deliverable_volume, DATE_DIFF(end_date, start_date, DAY) + 1) AS daily_volume_target
FROM dedup
WHERE rn = 1;
```

### gold.dim_creative

```sql
CREATE OR REPLACE TABLE `adframework.gold.dim_creative` AS
SELECT
  'mediasmart'                                                  AS platform_id,
  COALESCE(NULLIF(creative_id, ''), id)                        AS creative_id,
  campaign_id                                                   AS platform_campaign_id,
  type                                                          AS creative_type,
  name                                                          AS creative_name,
  COALESCE(NULLIF(image_url, ''), NULLIF(thumbnail_url, ''))   AS image_url
FROM `adframework.raw.mediasmart_creatives`
WHERE COALESCE(NULLIF(creative_id, ''), id) IS NOT NULL

UNION ALL

SELECT
  'mgid'        AS platform_id,
  id            AS creative_id,
  campaignId    AS platform_campaign_id,
  ad_type       AS creative_type,
  title         AS creative_name,
  imageLink     AS image_url
FROM `adframework.raw.mgid_creatives`
WHERE id IS NOT NULL;
```

### gold.dim_campaign

```sql
CREATE OR REPLACE TABLE `adframework.gold.dim_campaign` AS
SELECT DISTINCT
  LOWER(platform)          AS platform_id,
  platform_campaign_id,
  MAX(campaign_name)       AS campaign_name,
  MAX(io_id)               AS io_id -- Link opcional com IO
FROM (
  -- Campanhas que entregaram
  SELECT platform, platform_campaign_id, NULL as campaign_name FROM `adframework.stg.mediasmart_daily`
  UNION ALL
  SELECT platform, platform_campaign_id, NULL as campaign_name FROM `adframework.stg.mgid_daily`
  UNION ALL
  -- Campanhas que estão no IO
  SELECT platform, platform_campaign_id, campaign_name FROM `adframework.core.io_manager_v2`
)
WHERE platform_campaign_id IS NOT NULL
GROUP BY 1, 2;
```

### gold.fct_delivery_detail_daily (V2 com Custo Real e Atribuição)

```sql
CREATE OR REPLACE TABLE `adframework.gold.fct_delivery_detail_daily`
PARTITION BY date
CLUSTER BY io_id, platform_id
AS
WITH stg AS (
  SELECT * FROM `adframework.stg.mediasmart_daily` WHERE date >= '2026-03-01'
  UNION ALL
  SELECT * FROM `adframework.stg.mgid_daily`       WHERE date >= '2026-03-01'
),
io AS ( ... mesmo que antes ... ),
revenue AS (
  -- Busca o custo real da plataforma
  SELECT 
    SAFE_CAST(day AS DATE) as date,
    campaign_id,
    SAFE_CAST(client_cost AS NUMERIC) as cost_platform_real
  FROM `adframework.raw.mediasmart_revenue_daily`
)
SELECT
  s.date,
  LOWER(s.platform)                                            AS platform_id,
  s.platform_campaign_id,
  s.creative_id,
  s.creative_type,
  s.format,
  s.device_type,
  s.conversion_source,

  -- Chaves de IO (NULL quando campanha não tem IO registrado)
  io.io_id,
  io.line_id,
  COALESCE(NULLIF(io.advertiser_id,''),
    TO_HEX(SHA256(LOWER(IFNULL(io.advertiser,'')))))           AS advertiser_id,
  io.advertiser                                                AS advertiser_name,
  io.newad_client_id,
  io.campaign_name,
  io.buying_model,
  io.buying_value,
  io.deliverable_metric,

  -- Métricas de entrega
  s.impressions,
  s.clicks,
  s.video_start,
  s.video_25_viewed,
  s.video_50_viewed,
  s.video_75_viewed,
  s.video_completion,
  s.conversions_1,
  s.conversions_2,
  s.conversions_3,
  s.conversions_4,
  s.conversions_5,

  -- Custo da plataforma (Real vs Estimado)
  COALESCE(rev.cost_platform_real, 0)                         AS cost_platform,
  CAST(s.client_revenue AS NUMERIC)                           AS platform_revenue,

  -- Custo calculado pelo buying model do IO
  CAST(CASE
    WHEN UPPER(io.buying_model) = 'CPM'
      THEN SAFE_DIVIDE(s.impressions, 1000) * io.buying_value
    WHEN UPPER(io.buying_model) = 'CPC'
      THEN s.clicks * io.buying_value
    WHEN UPPER(io.buying_model) IN ('CPA','CPA_2_3_4')
      THEN (COALESCE(s.conversions_2,0)
          + COALESCE(s.conversions_3,0)
          + COALESCE(s.conversions_4,0)) * io.buying_value
    WHEN UPPER(io.buying_model) IN ('CPA2','CPA_2')
      THEN COALESCE(s.conversions_2,0) * io.buying_value
    WHEN UPPER(io.buying_model) IN ('CPA3','CPA_3')
      THEN COALESCE(s.conversions_3,0) * io.buying_value
    WHEN UPPER(io.buying_model) IN ('CPA4','CPA_4')
      THEN COALESCE(s.conversions_4,0) * io.buying_value
    ELSE NULL
  END AS NUMERIC)                                              AS cost_estimated,

  -- Volume entregue pela métrica do IO
  CASE
    WHEN UPPER(io.deliverable_metric) IN (
      'IMPRESSIONS','IMPRESSION','IMPRESSOES','IMPRESSÕES','IMPRESSAO','IMPRESSÃO'
    ) THEN s.impressions
    WHEN UPPER(io.deliverable_metric) IN ('CLICKS','CLICK','CLIQUE','CLIQUES')
      THEN s.clicks
    WHEN UPPER(io.deliverable_metric) IN ('CONVERSIONS_1','CPA1') THEN s.conversions_1
    WHEN UPPER(io.deliverable_metric) IN ('CONVERSIONS_2','CPA2') THEN s.conversions_2
    WHEN UPPER(io.deliverable_metric) IN ('CONVERSIONS_3','CPA3') THEN s.conversions_3
    WHEN UPPER(io.deliverable_metric) IN ('CONVERSIONS_4','CPA4') THEN s.conversions_4
    WHEN UPPER(io.deliverable_metric) IN ('CONVERSIONS_5','CPA5') THEN s.conversions_5
    ELSE NULL
  END                                                          AS delivered_volume,

  CURRENT_TIMESTAMP()                                          AS gold_updated_at

FROM stg s
LEFT JOIN revenue rev ON s.date = rev.date AND s.platform_campaign_id = rev.campaign_id
LEFT JOIN io
  ON  LOWER(io.platform)       = LOWER(s.platform)
  AND io.platform_campaign_id  = s.platform_campaign_id
  AND (io.start_date IS NULL OR s.date >= io.start_date)
  AND (io.end_date   IS NULL OR s.date <= io.end_date);
```

### gold.fct_io_plan_daily

```sql
CREATE OR REPLACE TABLE `adframework.gold.fct_io_plan_daily`
PARTITION BY date
CLUSTER BY io_id
AS
SELECT
  io_id,
  line_id,
  platform_id,
  platform_campaign_id,
  advertiser_id,
  advertiser_name,
  newad_client_id,
  buying_model,
  d                                                                           AS date,
  daily_budget_target                                                         AS planned_daily_budget,
  daily_volume_target                                                         AS planned_daily_volume,
  CAST(daily_budget_target * (DATE_DIFF(d, start_date, DAY) + 1) AS NUMERIC) AS planned_cost_to_date,
  CAST(daily_volume_target * (DATE_DIFF(d, start_date, DAY) + 1) AS NUMERIC) AS planned_volume_to_date,
  CURRENT_TIMESTAMP()                                                         AS gold_updated_at
FROM `adframework.gold.dim_io_line`,
UNNEST(GENERATE_DATE_ARRAY(
  GREATEST(start_date, DATE '2026-03-01'),
  LEAST(end_date, CURRENT_DATE())
)) AS d
WHERE start_date IS NOT NULL
  AND end_date   IS NOT NULL
  AND start_date <= end_date
  AND end_date   >= '2026-03-01';
```

### Query de Reprocessamento (rodar quando atualizar dados)

```sql
-- Recriar apenas as tabelas que mudam diariamente
-- Passo 1: atualizar fato de entrega
CREATE OR REPLACE TABLE `adframework.gold.fct_delivery_detail_daily`
PARTITION BY date
CLUSTER BY io_id, platform_id
AS [... SQL completo acima ...];

-- Passo 2: atualizar plano (caso IO Manager tenha mudado)
CREATE OR REPLACE TABLE `adframework.gold.fct_io_plan_daily`
PARTITION BY date
CLUSTER BY io_id
AS [... SQL completo acima ...];

-- Dimensões (só quando necessário)
-- dim_io_line   → quando adicionar/editar IOs no Admin UI
-- dim_creative  → quando atualizar criativos na plataforma
-- dim_advertiser → quando adicionar novo anunciante
-- dim_date      → uma vez por ano (adiciona datas futuras)
-- dim_platform  → raramente (nova plataforma)
```

---

## 7. Conexão Power BI

### Passo a Passo

**1. Obter Dados → Google BigQuery**
```
Project ID:  adframework
Dataset:     gold
Mode:        Import (NÃO usar DirectQuery)
```

**2. Tabelas a importar**

| Tabela | Refresh sugerido |
|--------|-----------------|
| `gold.fct_delivery_detail_daily` | Diário (após ETL rodar) |
| `gold.fct_io_plan_daily` | Diário (após IO atualizado) |
| `gold.dim_io_line` | Diário |
| `gold.dim_date` | Anual |
| `gold.dim_platform` | Raramente |
| `gold.dim_advertiser` | Semanal |
| `gold.dim_creative` | Diário |

**3. Relacionamentos no Model View**

```
fct_delivery_detail_daily[date]        → dim_date[date_key]          N:1  ativa
fct_delivery_detail_daily[io_id]       → dim_io_line[io_id]          N:1  ativa
fct_delivery_detail_daily[platform_id] → dim_platform[platform_id]   N:1  ativa
fct_io_plan_daily[date]                → dim_date[date_key]          N:1  ativa
fct_io_plan_daily[io_id]               → dim_io_line[io_id]          N:1  inativa*
dim_io_line[advertiser_id]             → dim_advertiser[advertiser_id] N:1 ativa
dim_io_line[platform_id]               → dim_platform[platform_id]   N:1  ativa
```

> *Deixar `fct_io_plan[date] → dim_date` como ativa e `fct_io_plan[io_id] → dim_io_line` como inativa, ativando via `USERELATIONSHIP()` no DAX quando necessário.

---

## 8. Medidas DAX

Cole estas medidas em uma tabela de medidas dedicada (`_Medidas`) no Power BI:

### Métricas Base

```dax
Impressões =
SUM(fct_delivery_detail_daily[impressions])

Cliques =
SUM(fct_delivery_detail_daily[clicks])

Custo Estimado =
SUM(fct_delivery_detail_daily[cost_estimated])

Volume Entregue =
SUM(fct_delivery_detail_daily[delivered_volume])
```

### KPIs de Performance

```dax
CTR =
DIVIDE(
    SUM(fct_delivery_detail_daily[clicks]),
    SUM(fct_delivery_detail_daily[impressions])
)

CPM Efetivo =
DIVIDE(
    SUM(fct_delivery_detail_daily[cost_estimated]),
    SUM(fct_delivery_detail_daily[impressions])
) * 1000

CPC Efetivo =
DIVIDE(
    SUM(fct_delivery_detail_daily[cost_estimated]),
    SUM(fct_delivery_detail_daily[clicks])
)

VTR (View-Through Rate) =
DIVIDE(
    SUM(fct_delivery_detail_daily[video_completion]),
    SUM(fct_delivery_detail_daily[video_start])
)

Taxa de Conversão 1 =
DIVIDE(
    SUM(fct_delivery_detail_daily[conversions_1]),
    SUM(fct_delivery_detail_daily[clicks])
)
```

### Pacing

```dax
-- Custo planejado acumulado até a última data com dados
Budget Planejado Acumulado =
CALCULATE(
    SUM(fct_io_plan_daily[planned_cost_to_date]),
    USERELATIONSHIP(fct_io_plan_daily[io_id], dim_io_line[io_id]),
    LASTDATE(dim_date[date_key])
)

-- % de pacing de custo
Pacing % Custo =
DIVIDE(
    [Custo Estimado],
    [Budget Planejado Acumulado]
)

-- Volume planejado acumulado
Volume Planejado Acumulado =
CALCULATE(
    SUM(fct_io_plan_daily[planned_volume_to_date]),
    USERELATIONSHIP(fct_io_plan_daily[io_id], dim_io_line[io_id]),
    LASTDATE(dim_date[date_key])
)

-- % de pacing de volume
Pacing % Volume =
DIVIDE(
    [Volume Entregue],
    [Volume Planejado Acumulado]
)

-- Status de pacing (para KPI card com cor)
Status Pacing =
VAR pct = [Pacing % Custo]
RETURN
    SWITCH(
        TRUE(),
        pct >= 0.95 && pct <= 1.05, "On Track",
        pct < 0.85,                  "Under Pacing",
        pct > 1.15,                  "Over Pacing",
        "Atenção"
    )
```

### Campanhas Sem IO (visibilidade de campanhas não gerenciadas)

```dax
Campanhas Sem IO =
CALCULATE(
    DISTINCTCOUNT(fct_delivery_detail_daily[platform_campaign_id]),
    ISBLANK(fct_delivery_detail_daily[io_id])
)

Impressões Sem IO =
CALCULATE(
    SUM(fct_delivery_detail_daily[impressions]),
    ISBLANK(fct_delivery_detail_daily[io_id])
)

% Entrega Sem IO =
DIVIDE(
    [Impressões Sem IO],
    [Impressões]
)
```

### Sugestão de Páginas do Dashboard

```
Página 1 — Visão Geral (cards KPI)
  Custo Estimado | Impressões | Cliques | CTR | CPM Efetivo | Pacing %

Página 2 — Pacing por IO Line
  Tabela: IO line × Budget Planejado × Custo Real × Pacing %
  Gráfico: Entrega diária vs Planejado

Página 3 — Performance por Campanha
  Breakdown por campanha, plataforma, formato, device

Página 4 — Criativos
  Top criativos por impressão, CTR, custo

Página 5 — Campanhas Sem IO
  Visibilidade de campanhas ativas sem IO registrado
```

---

## 9. Problemas de Qualidade Identificados

Estes problemas existem nos dados e precisam ser corrigidos operacionalmente:

| # | Problema | Impacto | Como Resolver |
|---|---------|---------|---------------|
| 1 | IO lines com `platform_campaign_id = NULL` | Nunca dão match com delivery | Preencher o ID da campanha na plataforma ao criar o IO |
| 2 | Campanhas ativas sem IO registrado (~15% em março) | Aparecem como "Sem IO" nos dashboards | Criar IO no Admin UI para cada campanha ativa |
| 3 | IOs duplicados (mesmo campaign_id, datas sobrepostas) | Join duplica entrega | Revisar e inativar IOs duplicados |
| 4 | `cost_platform` = zero nas views stg | Custo real indisponível no Gold | Integrar `raw.mediasmart_revenue_daily` no pipeline stg |
| 5 | Encoding UTF-8 em nomes de campanha | Display errado em alguns clientes SQL | Verificar collation na ingestão da API |
| 6 | Dados Siprocal desatualizados (último: 2026-03-08) | Siprocal ausente dos dashboards de abril | Verificar ETL do Siprocal e reprocessar |

---

## 10. Próximos Passos

### Fase 2 — Qualidade de Dados (recomendado antes de expandir dashboards)

- [ ] Corrigir IOs com `platform_campaign_id = NULL` no Admin UI
- [ ] Cadastrar IOs para campanhas ativas sem cobertura
- [ ] Investigar e corrigir ETL Siprocal (dados parados em março)
- [ ] Integrar `raw.mediasmart_revenue_daily` para ter `cost_platform` real

### Fase 3 — Reestruturação BigQuery (após validação do Gold)

**Proposta de limpeza:**

```
MANTER:
  raw.mediasmart_daily          ← fonte primária
  raw.mediasmart_creatives      ← fonte primária
  raw.mgid_daily                ← fonte primária
  raw.mgid_creatives            ← fonte primária
  raw.siprocal_daily_materialized ← fonte primária
  raw.mediasmart_revenue_daily  ← custo real (integrar ao gold)
  core.io_manager_v2            ← plano de mídia
  core.proposals / proposal_lines ← estrutura de proposta
  pixel.*                       ← silo separado, manter
  gold.*                        ← novo, star schema

DEPRECAR (após migrar Power BI):
  stg.*                         ← 19 views (substituídas pelo gold ETL)
  marts.* (views legadas)       ← substituídas pelo gold
  share.* (views legadas)       ← substituídas pelo gold
  core.dim_* (views quebradas)  ← substituídas por gold.dim_*

DELETAR (sem uso, liberando armazenamento):
  raw_mediasmart.*              ← duplicata de raw
  raw_mgid.*                    ← duplicata de raw
  raw_siprocal.*                ← duplicata de raw
  raw.*_legacy_20260227_*       ← backups antigos
  raw.*_backup_20260227_*       ← backups antigos
```

**Resultado esperado:** de ~150 objetos para ~30 objetos no BigQuery.

### Fase 4 — Automação (Cloud Scheduler)

```
Trigger diário (após ETL Python):
  1. CREATE OR REPLACE gold.fct_delivery_detail_daily
  2. CREATE OR REPLACE gold.fct_io_plan_daily
  3. (condicional) recrear dims se io_manager_v2 foi atualizado
```

---

## Glossário

| Termo | Definição |
|-------|-----------|
| `io_id` | ID único de uma IO line (gerado pelo Admin UI ou derivado por SHA256) |
| `platform_campaign_id` | ID da campanha na plataforma DSP (MediaSmart ou MGID) |
| `buying_model` | Modelo de compra: CPM, CPC, CPA, CPA_2, CPA_3, CPA_4 |
| `cost_estimated` | Custo calculado: volume × buying_value pelo buying_model |
| `cost_platform` | Custo real reportado pela plataforma (atualmente zero nas views stg) |
| `delivered_volume` | Métrica de entrega mapeada ao `deliverable_metric` do IO |
| `pacing` | Ritmo de entrega: custo/volume real ÷ custo/volume planejado acumulado |
| Gold Layer | Dataset `adframework.gold` — star schema físico para Power BI |
| Bronze Layer | Datasets `raw.*` — dados brutos da API, append-only |
| Silver Layer | Dataset `stg.*` — views com cast de tipos e joins de criativos |

---

*Documento gerado em 2026-04-28 | AdFramework — Newad | douglas@newad.com.br*
