# Column Lineage Map — RAW → STG → CORE → GOLD

---
> **⚠️ LEGADO — PRÉ-REBUILD 2026-06-16 ⚠️**
> Este documento descreve a pipeline **anterior ao reset completo de 2026-06-16**.
> Tabelas, views, schemas e colunas aqui descritos **foram dropados e não existem mais no BigQuery**.
> Mantenha para consulta histórica — **não use como referência para desenvolvimento novo.**
> Plano atual: [bq_restructuring_plan.md](bq_restructuring_plan.md) · [CHANGELOG.md](../CHANGELOG.md)
---

> Última atualização: 2026-06-11  
> Autor: Douglas Reche  
> Propósito: Rastrear transformação **coluna a coluna** por todas as camadas do pipeline. Identifica onde informações são perdidas antes de chegar nos KPIs.  
> Complementa: `pipeline_complete_map.md` (grain e dependências por tabela)

---

## 1. Arquitetura Geral — Visão em Camadas

```mermaid
flowchart TD
    classDef apiStyle  fill:#E9ECEF,stroke:#6C757D,color:#212529
    classDef rawStyle  fill:#FFF3CD,stroke:#856404,color:#212529
    classDef stgStyle  fill:#D1ECF1,stroke:#0C5460,color:#212529
    classDef coreStyle fill:#D4EDDA,stroke:#155724,color:#212529
    classDef goldStyle fill:#CCE5FF,stroke:#004085,color:#212529
    classDef gapStyle  fill:#F8D7DA,stroke:#721C24,color:#721C24,stroke-dasharray:5 5

    subgraph FONTES["☁️ FONTES EXTERNAS"]
        direction LR
        F1["MediaSmart API\n/analytics + /revenue"]:::apiStyle
        F2["MGID API\n/statistics-reports"]:::apiStyle
        F3["Siprocal\nGoogle Sheet"]:::apiStyle
        F4["Google Drive\n*.xlsx — IO Plans"]:::apiStyle
    end

    subgraph RAW["🗃️ RAW — todas colunas STRING, sem transformação"]
        direction LR
        R1["mediasmart_delivery\nday · eventid · controlid · strategyid\nimpressions · clicks · conversions_1-5\nvideo_start/25/50/75/completion"]:::rawStyle
        R2["mediasmart_revenue\nday · controlid · strategyid\nrevenuesource · clientrevenue"]:::rawStyle
        R3["mediasmart_bid_supply ⚠️\nday · hour · eventid · controlid\nauction_type · publisher_* · iab_*\nbid_offers · bids · won · media_cost"]:::rawStyle
        R4["mgid_delivery\nday · campaignid · teaserid\nimpressions · clicks · spent\nconversionsinterest/decision/buy"]:::rawStyle
        R5["siprocal_delivery\nday · advertiser · campaign_id\ncreative_type · creative\nimpressions · clicks"]:::rawStyle
        R6["io_plan_drive_snapshot\nclient_id · flight_start/end · platform\nunit_price · impressions_cpm\nmonthly_spend · video_views"]:::rawStyle
    end

    subgraph STG["🔧 STG — tipagem SAFE_CAST, normalização de nomes"]
        direction LR
        S1["stg.mediasmart_delivery\n✅ day→DATE · impressions→INT64\n✅ conversions_1-5→INT64\n✅ video_*→INT64\n+ UNION raw.mediasmart_daily workaround"]:::stgStyle
        S2["stg.mediasmart_revenue\n✅ day→DATE · clientrevenue→FLOAT64"]:::stgStyle
        S3["stg.mediasmart_bid_supply\n✅ todas colunas tipadas\n❌ ÓRFÃO — não referenciada no GOLD"]:::gapStyle
        S4["stg.mgid_delivery\n✅ day→DATE · impressions→INT64\n✅ spent→FLOAT64\nconversions renomeadas: mgid_conv_*"]:::stgStyle
        S5["stg.siprocal_delivery\n✅ day→DATE · impressions→INT64\n✅ advertiser via REGEXP_EXTRACT\n❌ spend não existe na fonte"]:::stgStyle
    end

    subgraph CORE["🧩 CORE — dimensões canônicas e atribuição de cliente"]
        direction LR
        C1["dim_client\n26 clientes\nsource of truth"]:::coreStyle
        C2["platform_client_links\nevtid·campaignid·advertiser\n→ client_id"]:::coreStyle
        C3["io_plan_manual\n⚠️ unit_price NÃO mapeado\n⚠️ impressions_cpm NÃO mapeado\n⚠️ video_views NÃO mapeado"]:::coreStyle
    end

    subgraph GOLD["⭐ GOLD — camada analítica final"]
        direction LR
        G1["fact_delivery\n✅ impressions · clicks · spend\n✅ conversions_1-5 MS\n✅ mgid_conv_*\n❌ video_* ausente\n❌ strategyname ausente\n❌ teaserid ausente"]:::goldStyle
        G2["fact_io_plan\n✅ planned_spend · planned_impressions\n✅ planned_clicks\n❌ unit_price ausente\n❌ impressions_cpm ausente"]:::goldStyle
        G3["fct_luckbet_delivery_daily\n✅ impressions · clicks · spend\n✅ video_* completo\n✅ conversions com nomes semânticos\n✅ CTR · CPM · CPC derivados\n✅ strategyname · pacing_pct"]:::goldStyle
        G4["fct_delivery_daily_mvp\n✅ impressions · clicks\n✅ video_* presente\n⚠️ spend parcial — sem Siprocal"]:::goldStyle
        G5["fct_cora_delivery_full\n✅ impressions · clicks · spend\n❌ video_* ausente\n❌ conversions ausente"]:::goldStyle
        G6["pipeline_health\nfreshness · row counts\natribuição · delta raw→gold"]:::goldStyle
    end

    F1 --> R1 & R2 & R3
    F2 --> R4
    F3 --> R5
    F4 --> R6

    R1 --> S1
    R2 --> S2
    R3 --> S3
    R4 --> S4
    R5 --> S5

    S1 & S2 -->|"JOIN anti-multiplicação\napós agregação"| G1
    S4 & C2 --> G1
    S5 & C2 --> G1
    C1 --> G1

    R6 -->|"06_seed_io_plan_manual\nunit_price · video_views\nnão mapeados"| C3
    C3 --> G2

    S1 & S2 & C1 & C2 --> G3
    S1 & S4 & S5 & C1 & C2 --> G4
    S1 & S4 & S5 & C1 & C2 --> G5

    G1 & G2 --> G6
```

---

## 2. Cadeia de Atribuição de Cliente

A atribuição é o **ponto crítico de perda de linhas**: se um `eventid` / `campaignid` / `advertiser` não tiver vínculo ativo em `platform_client_links`, a entrega fica como `unattributed` — existe no RAW mas é invisível nos KPIs por cliente.

```mermaid
flowchart LR
    classDef rawStyle  fill:#FFF3CD,stroke:#856404,color:#212529
    classDef coreStyle fill:#D4EDDA,stroke:#155724,color:#212529
    classDef goldStyle fill:#CCE5FF,stroke:#004085,color:#212529
    classDef gapStyle  fill:#F8D7DA,stroke:#721C24,color:#721C24

    subgraph MS["MediaSmart"]
        R_MS["stg.mediasmart_delivery\neventid = identificador da conta"]:::rawStyle
    end

    subgraph MG["MGID"]
        R_MG["stg.mgid_delivery\ncampaignid = ID da campanha"]:::rawStyle
    end

    subgraph SP["Siprocal"]
        R_SP["stg.siprocal_delivery\nadvertiser = REGEXP_EXTRACT do nome\n⚠️ frágil — falha silenciosa se\nSiprocal mudar o nome"]:::rawStyle
    end

    PCL["core.platform_client_links\nplatform + link_type + link_value → client_id\nstatus: active / pending_confirmation / unresolved"]:::coreStyle

    DC["core.dim_client\nclient_id · slug · name\nsector · status"]:::coreStyle

    ATR{"client_id\nresolvido?"}:::coreStyle

    OK["✅ entrega atribuída\nclient_id = luckbet_bea15ebc\nou banco_cora_fe13d78a etc."]:::goldStyle
    NOK["⚠️ unattributed\nentrega existe no RAW\nnão aparece nos KPIs por cliente"]:::gapStyle

    R_MS -->|"JOIN ON\nplatform='mediasmart'\nlink_type='eventid'\nlink_value=d.eventid"| PCL
    R_MG -->|"JOIN ON\nplatform='mgid'\nlink_type='campaignid'\nlink_value=d.campaignid"| PCL
    R_SP -->|"JOIN ON\nplatform='siprocal'\nlink_type='advertiser'\nlink_value=UPPER(TRIM(advertiser))"| PCL

    PCL -->|"LEFT JOIN"| ATR
    DC --> ATR

    ATR -->|"status='active'\ne link encontrado"| OK
    ATR -->|"link ausente ou\nstatus='pending_confirmation'"| NOK
```

**Regra de atribuição por plataforma:**

| Plataforma | Campo de JOIN | Granularidade | Risco |
|---|---|---|---|
| MediaSmart | `eventid` | Conta (herda todas as campanhas) | Baixo — 1 vínculo cobre toda conta |
| MGID | `campaignid` | Campanha individual | Médio — cada campanha precisa de 1 vínculo |
| Siprocal | `advertiser` (texto) | Nome do anunciante | Alto — texto frágil, falha silenciosa |

---

## 3. Linhagem de Colunas — MediaSmart Delivery

### 3.1 Fluxo do JOIN Revenue anti-multiplicação

O spend MediaSmart vem em grain diferente (`day + controlid + strategyid + revenuesource`). Se o JOIN for feito antes da agregação, cada linha de delivery é multiplicada pelo número de `revenuesource` por estratégia — gerando spend inflado.

```mermaid
flowchart LR
    classDef stgStyle fill:#D1ECF1,stroke:#0C5460,color:#212529
    classDef goldStyle fill:#CCE5FF,stroke:#004085,color:#212529
    classDef wrongStyle fill:#F8D7DA,stroke:#721C24,color:#721C24

    D["stg.mediasmart_delivery\ngrain: day+eventid+controlid+strategyid\n+conversion_source"]:::stgStyle
    R["stg.mediasmart_revenue\ngrain: day+controlid+strategyid\n+revenuesource"]:::stgStyle

    AGG_D["Agregar delivery\nSUM(impressions, clicks, conversions_*)\nGROUP BY day, controlid, strategyid"]:::stgStyle
    AGG_R["Agregar revenue\nSUM(clientrevenue)\nGROUP BY day, controlid, strategyid"]:::stgStyle

    WRONG["❌ JOIN antes da agregação\nresultado: spend × N revenuesources\n= spend INFLADO"]:::wrongStyle

    JOIN["✅ JOIN após agregação\nd.platform_campaign_id = r.platform_campaign_id\nAND d.day = r.day\n= spend correto"]:::goldStyle

    G["gold.fact_delivery\nspend = SUM(clientrevenue)"]:::goldStyle

    D --> AGG_D
    R --> AGG_R
    AGG_D & AGG_R --> JOIN --> G
    D -->|"❌ padrão errado\nevitar"| WRONG
    R --> WRONG
```

### 3.2 Tabela de colunas — mediasmart_delivery

| Coluna RAW | Tipo RAW | Transformação STG | Tipo STG | fact_delivery | fct_luckbet | fct_mvp | fct_cora | Observação |
|---|---|---|---|---|---|---|---|---|
| `day` | STRING | `SAFE_CAST AS DATE` | DATE | ✅ `day` | ✅ `date` | ✅ `date` | ✅ `date` | |
| `eventid` | STRING | pass-through | STRING | JOIN PCL | JOIN PCL | JOIN PCL | JOIN PCL | Identifica conta MediaSmart |
| `controlid` | STRING | pass-through | STRING | `platform_campaign_id` | `platform_campaign_id` | `platform_campaign_id` | `platform_campaign_id` | ID da campanha |
| `strategyid` | STRING | pass-through | STRING | agregado (perdido) | agregado (perdido) | agregado (perdido) | agregado (perdido) | ID da estratégia — perde granularidade |
| `strategyname` | STRING | pass-through | STRING | ❌ ausente | ✅ presente | ❌ ausente | ❌ ausente | Nome da estratégia perdido na maioria dos views |
| `conversion_source` | STRING | pass-through | STRING | ❌ ausente | ❌ ausente | ❌ ausente | ❌ ausente | Fonte da conversão — perdida no gold |
| `impressions` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ SUM | ✅ SUM | ✅ SUM | ✅ SUM | |
| `clicks` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ SUM | ✅ SUM | ✅ SUM | ✅ SUM | |
| `conversions_1` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ SUM | ✅ `pageviews` | ✅ SUM | ❌ ausente | Mapeamento semântico via dim_conversion_mapping |
| `conversions_2` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ SUM | ✅ `cadastros` | ✅ SUM | ❌ ausente | |
| `conversions_3` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ SUM | ✅ `ftds` | ✅ SUM | ❌ ausente | is_primary=TRUE para Luckbet |
| `conversions_4` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ SUM | ✅ `depositos_recorrentes` | ✅ SUM | ❌ ausente | |
| `conversions_5` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ SUM | ✅ `inicio_cadastro` | ✅ SUM | ❌ ausente | |
| `video_start` | STRING | `SAFE_CAST AS INT64` | INT64 | ❌ ausente | ✅ SUM | ✅ SUM | ❌ ausente | Perdido no fact_delivery principal |
| `video_25_viewed` | STRING | `SAFE_CAST AS INT64` | INT64 | ❌ ausente | ✅ SUM | ✅ SUM | ❌ ausente | |
| `video_50_viewed` | STRING | `SAFE_CAST AS INT64` | INT64 | ❌ ausente | ✅ SUM | ✅ SUM | ❌ ausente | |
| `video_75_viewed` | STRING | `SAFE_CAST AS INT64` | INT64 | ❌ ausente | ✅ SUM | ✅ SUM | ❌ ausente | |
| `video_completion` | STRING | `SAFE_CAST AS INT64` | INT64 | ❌ ausente | ✅ SUM | ✅ SUM | ❌ ausente | |
| `platform` | STRING | literal `'mediasmart'` | STRING | ✅ | ✅ | ✅ | ✅ | Adicionado na STG |
| `raw_ingested_at` | TIMESTAMP | pass-through | TIMESTAMP | ❌ ausente | ❌ ausente | ❌ ausente | ❌ ausente | Apenas para auditoria RAW/STG |

### 3.3 Tabela de colunas — mediasmart_revenue

| Coluna RAW | Tipo RAW | Transformação STG | Tipo STG | fact_delivery | fct_luckbet | Observação |
|---|---|---|---|---|---|---|
| `day` | STRING | `SAFE_CAST AS DATE` | DATE | JOIN key | JOIN key | |
| `controlid` | STRING | → `platform_campaign_id` | STRING | JOIN key | JOIN key | |
| `strategyid` | STRING | pass-through | STRING | agregado antes do JOIN | agregado antes do JOIN | |
| `revenuesource` | STRING | pass-through | STRING | ❌ ausente | ❌ ausente | Canal de revenue — perdido no gold |
| `clientrevenue` | STRING | `SAFE_CAST AS FLOAT64` | FLOAT64 | ✅ `spend` SUM | ✅ `receita_dsp` | JOIN feito APÓS agregação para evitar multiplicação |

---

## 4. Linhagem de Colunas — mediasmart_bid_supply ⚠️ TABELA ÓRFÃ

> **Status: ÓRFÃ.** A view `stg.mediasmart_bid_supply` existe e está tipada corretamente, mas **nenhum arquivo em `gold/`** a referencia. Toda informação de eficiência de leilão está inacessível para KPIs.

| Coluna RAW | Tipo RAW | Tipo STG | Chega no GOLD? | KPI perdido |
|---|---|---|---|---|
| `day` | STRING | DATE | ❌ | — |
| `hour` | STRING | INT64 | ❌ | Análise intraday impossível |
| `eventid` | STRING | STRING | ❌ | — |
| `controlid` | STRING | STRING | ❌ | — |
| `strategyid` | STRING | STRING | ❌ | — |
| `auction_type` | STRING | STRING | ❌ | Distribuição leilão aberto vs privado |
| `ad_exchange` | STRING | STRING | ❌ | Performance por exchange |
| `publisher_id` | STRING | STRING | ❌ | Performance por publisher |
| `publisher_name` | STRING | STRING | ❌ | — |
| `iab_category` | STRING | STRING | ❌ | Performance por categoria IAB |
| `iab_subcategory` | STRING | STRING | ❌ | — |
| `bid_offers` | STRING | INT64 | ❌ | Oportunidades de leilão |
| `bids` | STRING | INT64 | ❌ | Lances enviados |
| `won` | STRING | INT64 | ❌ | Lances ganhos (win rate = won/bids) |
| `media_cost` | STRING | FLOAT64 | ❌ | Custo de mídia real (antes de markup) |
| `total_bids_cost` | STRING | FLOAT64 | ❌ | Custo total de lances |
| `impressions` | STRING | INT64 | ❌ | Redundante com delivery, mas em grain horário |
| `clicks` | STRING | INT64 | ❌ | — |
| `conversions_1-5` | STRING | INT64 | ❌ | — |

**Para desbloquear:** criar `gold/ddl/fact_bid_supply.sql` que consome `stg.mediasmart_bid_supply` com JOIN em `platform_client_links`. Ver `docs/etl_expansion_plan.md`.

---

## 5. Linhagem de Colunas — MGID

| Coluna RAW | Tipo RAW | Transformação STG | Tipo STG | fact_delivery | fct_mvp | fct_cora | Observação |
|---|---|---|---|---|---|---|---|
| `day` | STRING | `SAFE_CAST AS DATE` | DATE | ✅ | ✅ | ✅ | |
| `campaignid` | STRING | → `platform_campaign_id` | STRING | JOIN PCL | JOIN PCL | JOIN PCL | |
| `teaserid` | STRING | pass-through | STRING | ❌ ausente | ❌ ausente | ❌ ausente | ID do criativo/teaser — perdido na agregação |
| `impressions` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ SUM | ✅ SUM | ✅ SUM | |
| `clicks` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ SUM | ✅ SUM | ✅ SUM | |
| `spent` | STRING | `SAFE_CAST AS FLOAT64` | FLOAT64 | ✅ `spend` SUM | ✅ SUM | ✅ SUM | Spend já vem na mesma grain da delivery |
| `conversionsinterest` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ `mgid_conv_interest` | ⚠️ renomeado? | ❌ ausente | Funil MGID — nome diferente do MediaSmart |
| `conversionsdecision` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ `mgid_conv_decision` | ⚠️ renomeado? | ❌ ausente | |
| `conversionsbuy` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ `mgid_conv_buy` | ⚠️ renomeado? | ❌ ausente | |
| `platform` | STRING | literal `'mgid'` | STRING | ✅ | ✅ | ✅ | |

> **Atenção — KPIs cruzados:** qualquer cálculo de conversão que soma `conversions_1 + conversions_2 + ...` **ignora MGID completamente**, pois MGID usa `mgid_conv_*`. Funis cross-platform ficam incorretos.

---

## 6. Linhagem de Colunas — Siprocal

| Coluna RAW | Tipo RAW | Transformação STG | Tipo STG | fact_delivery | fct_mvp | fct_cora | Observação |
|---|---|---|---|---|---|---|---|
| `day` | STRING | `SAFE_CAST AS DATE` | DATE | ✅ | ✅ | ✅ | |
| `advertiser` | STRING | `REGEXP_EXTRACT(UPPER(TRIM(advertiser)), r'^NEWAD_(.+)_BR_\w+$')` | STRING | JOIN PCL | JOIN PCL | JOIN PCL | Extrai slug do nome "NEWAD_{SLUG}_BR_{MES}{ANO}" |
| `campaign_id` | STRING | → `platform_campaign_id` | STRING | ✅ | ✅ | ✅ | |
| `campaign_name` | STRING | pass-through | STRING | ❌ ausente | ❌ ausente | ❌ ausente | Nome completo perdido no gold |
| `creative_type` | STRING | pass-through | STRING | ❌ ausente | ❌ ausente | ❌ ausente | Tipo do criativo — perdido |
| `creative` | STRING | pass-through | STRING | ❌ ausente | ❌ ausente | ❌ ausente | Nome do criativo — perdido |
| `impressions` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ SUM | ✅ SUM | ✅ SUM | |
| `clicks` | STRING | `SAFE_CAST AS INT64` | INT64 | ✅ SUM | ✅ SUM | ✅ SUM | |
| `spend` | ❌ não existe | — | — | NULL | NULL | NULL | Siprocal não fornece dado de custo |
| `platform` | STRING | literal `'siprocal'` | STRING | ✅ | ✅ | ✅ | |

> **Dado desatualizado:** última atualização do Siprocal foi março/2026. ETL depende de `scripts/etl/sync_sheet.py` rodado manualmente.

---

## 7. Linhagem — IO Plan (Drive Snapshot → Core → Gold)

```mermaid
flowchart LR
    classDef rawStyle  fill:#FFF3CD,stroke:#856404,color:#212529
    classDef coreStyle fill:#D4EDDA,stroke:#155724,color:#212529
    classDef goldStyle fill:#CCE5FF,stroke:#004085,color:#212529
    classDef gapStyle  fill:#F8D7DA,stroke:#721C24,color:#721C24,stroke-dasharray:5 5

    subgraph IO_RAW["raw.io_plan_drive_snapshot"]
        DR1["client_id · drive_folder · source_file"]:::rawStyle
        DR2["flight_label · flight_start · flight_end\nstrategy_name · platform"]:::rawStyle
        DR3["unit_price · impressions_cpm\nmonthly_spend · impressions_est\nvideo_views · clicks"]:::rawStyle
    end

    subgraph SEED["06_seed_io_plan_manual.sql\n(mapeamento parcial)"]
        MAP1["✅ client_id"]:::coreStyle
        MAP2["✅ flight_start · flight_end\n✅ strategy_name · platform\n✅ planned_spend_gross · planned_spend_net\n✅ planned_impressions · planned_clicks"]:::coreStyle
        GAP_MAP["❌ unit_price não mapeado\n❌ impressions_cpm não mapeado\n❌ video_views não mapeado\n❌ source_file não chega no gold"]:::gapStyle
    end

    subgraph CORE_IO["core.io_plan_manual"]
        C1["client_id · flight_start · flight_end\nplanned_impressions · planned_clicks\nplanned_spend_gross · planned_spend_net\nplan_version · source_file · loaded_at"]:::coreStyle
    end

    subgraph GOLD_IO["gold.fact_io_plan"]
        G1["report_date (expandido via GENERATE_DATE_ARRAY)\nclient_id\nplanned_impressions_daily\nplanned_clicks_daily\nplanned_spend_gross_daily\nplanned_spend_net_daily"]:::goldStyle
        GAP_G["❌ unit_price ausente\n→ CPM planejado impossível\n❌ video_views ausente\n→ volume de vídeo planejado indisponível"]:::gapStyle
    end

    DR1 --> MAP1
    DR2 --> MAP2
    DR3 --> GAP_MAP

    MAP1 & MAP2 --> C1
    GAP_MAP -.->|"perdido"| C1

    C1 --> G1
    C1 -.->|"colunas ausentes"| GAP_G
```

| Coluna RAW (drive_snapshot) | Tipo | Chega em core.io_plan_manual? | Chega em gold.fact_io_plan? | Observação |
|---|---|---|---|---|
| `client_id` | STRING | ✅ | ✅ | |
| `flight_label` | STRING | ✅ | ✅ | |
| `flight_start` | STRING | ✅ → DATE | ✅ | |
| `flight_end` | STRING | ✅ → DATE | ✅ | |
| `strategy_name` | STRING | ✅ | ✅ | |
| `platform` | STRING | ✅ | ✅ | |
| `monthly_spend` | STRING | ✅ → NUMERIC `planned_spend_gross` | ✅ `planned_spend_gross_daily` | Distribuído linearmente por dia |
| `impressions_est` | STRING | ✅ → INT64 `planned_impressions` | ✅ `planned_impressions_daily` | |
| `clicks` | STRING | ✅ → INT64 `planned_clicks` | ✅ `planned_clicks_daily` | |
| `unit_price` | STRING | ❌ não mapeado | ❌ ausente | Necessário para CPM/CPC planejado |
| `impressions_cpm` | STRING | ❌ não mapeado | ❌ ausente | Impressões previstas para compra CPM |
| `video_views` | STRING | ❌ não mapeado | ❌ ausente | Volume de vídeo planejado |
| `drive_folder` | STRING | ✅ `source_file` (auditoria) | ❌ ausente | Rastreabilidade do arquivo fonte |

---

## 8. Matriz de Cobertura de Métricas por View GOLD

> ✅ = presente e correto | ⚠️ = parcial ou com ressalvas | ❌ = ausente | — = não aplicável

| Métrica | fact_delivery | fct_luckbet_daily | fct_delivery_mvp | fct_cora_full | fct_newad_bet | fct_newad_fintech | pipeline_health |
|---|---|---|---|---|---|---|---|
| impressions | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ delta |
| clicks | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ delta |
| spend (MS + MGID) | ✅ | ✅ | ⚠️ sem Siprocal | ✅ | ✅ | ✅ | ✅ |
| spend (Siprocal) | ❌ fonte | ❌ fonte | ❌ fonte | ❌ fonte | ❌ fonte | ❌ fonte | ❌ fonte |
| conversions_1-5 (MS) | ✅ | ✅ semântico | ✅ | ❌ | ✅ | ✅ | — |
| mgid_conv_interest | ✅ | — | ⚠️ | ❌ | ⚠️ | ⚠️ | — |
| mgid_conv_decision | ✅ | — | ⚠️ | ❌ | ⚠️ | ⚠️ | — |
| mgid_conv_buy | ✅ | — | ⚠️ | ❌ | ⚠️ | ⚠️ | — |
| video_start | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | — |
| video_25/50/75 | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | — |
| video_completion | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | — |
| video_completion_rate % | ❌ | ✅ derivado | ✅ derivado | ❌ | ❌ | ❌ | — |
| CTR % | ❌ | ✅ derivado | ⚠️ | ❌ | ❌ | ❌ | — |
| CPM realizado | ❌ | ✅ derivado | ❌ | ❌ | ❌ | ❌ | — |
| CPC realizado | ❌ | ✅ derivado | ❌ | ❌ | ❌ | ❌ | — |
| pacing % | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ⚠️ |
| planned_spend | — | ✅ via IO | ❌ | ❌ | ❌ | ❌ | ✅ |
| unit_price | — | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| strategyname | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | — |
| creative_type | — | — | ❌ | ❌ | ❌ | ❌ | — |
| publisher/exchange | — | — | — | — | — | — | — |
| win_rate (bids/won) | — | — | — | — | — | — | — |

---

## 9. Resumo de Lacunas — Priorizado por Impacto nos KPIs

```mermaid
flowchart TD
    classDef p1 fill:#F8D7DA,stroke:#721C24,color:#212529,font-weight:bold
    classDef p2 fill:#FFF3CD,stroke:#856404,color:#212529
    classDef p3 fill:#D4EDDA,stroke:#155724,color:#212529

    subgraph P1["🔴 PRIORIDADE ALTA — KPIs de custo/eficiência impossíveis"]
        L1["bid_supply inteiro não chega no GOLD\n→ win rate, media cost, publisher performance\n→ Arquivo: gold/ddl/fact_bid_supply.sql a criar"]:::p1
        L2["unit_price e impressions_cpm não mapeados do IO plan\n→ CPM planejado vs realizado impossível\n→ Arquivo: core/migration/06_seed_io_plan_manual.sql a corrigir"]:::p1
    end

    subgraph P2["🟡 PRIORIDADE MÉDIA — KPIs de vídeo e conversão incompletos"]
        L3["video_* ausente no fact_delivery principal\n→ Cora, Fintech, Bet não têm métricas de vídeo\n→ Arquivo: gold/ddl/fact_delivery.sql a expandir"]:::p2
        L4["conversions MGID ignoradas em KPIs cross-platform\n→ Funis somam apenas MediaSmart\n→ Padronizar nomenclatura ou criar coluna unificada"]:::p2
        L5["conversions_1-5 ausentes no fct_cora_delivery_full\n→ Cora sem dados de conversão no gold\n→ Arquivo: gold/delivery/fct_cora_delivery_full.sql"]:::p2
    end

    subgraph P3["🟢 PRIORIDADE BAIXA — granularidade e rastreabilidade"]
        L6["strategyname perdido na maioria dos views\n→ Análise por estratégia impossível fora do Luckbet"]:::p3
        L7["teaserid MGID perdido na agregação\n→ Performance por criativo/teaser indisponível"]:::p3
        L8["creative_type e creative Siprocal perdidos\n→ Análise por formato/criativo indisponível"]:::p3
        L9["video_views IO Plan não mapeado\n→ Volume de vídeo planejado ausente"]:::p3
    end
```

| # | Lacuna | Camada perdida | Arquivos envolvidos | KPI afetado |
|---|---|---|---|---|
| L1 | `mediasmart_bid_supply` não chega no GOLD | STG → GOLD | `gold/ddl/fact_bid_supply.sql` (a criar) | Win rate, custo real de mídia, performance por publisher/exchange |
| L2 | `unit_price`, `impressions_cpm` não mapeados do IO plan | RAW → CORE | `core/migration/06_seed_io_plan_manual.sql` | CPM planejado, volume CPM previsto vs realizado |
| L3 | `video_*` ausentes no `fact_delivery` | STG → GOLD | `gold/ddl/fact_delivery.sql` | Taxa de conclusão de vídeo para Cora, Bet, Fintech |
| L4 | Conversões MGID com nomes diferentes | GOLD (nomenclatura) | Qualquer query que some `conversions_*` | Funil cross-platform conta só MediaSmart |
| L5 | `conversions_1-5` ausentes no `fct_cora_delivery_full` | STG → GOLD | `gold/delivery/fct_cora_delivery_full.sql` | Conversões Cora inexistentes no gold |
| L6 | `strategyname` perdido na agregação | STG → GOLD | `gold/ddl/fact_delivery.sql` | Análise por estratégia em clientes além de Luckbet |
| L7 | `teaserid` MGID perdido na agregação | STG → GOLD | Qualquer fact MGID | Análise de performance por criativo MGID |
| L8 | `creative_type`, `creative` Siprocal perdidos | STG → GOLD | `gold/ddl/fact_delivery.sql` | Análise de formato por criativo Siprocal |
| L9 | `video_views` do IO plan não mapeado | RAW → CORE | `core/migration/06_seed_io_plan_manual.sql` | Volume de vídeo previsto no planejamento |

---

## 10. Notas de Manutenção

- **Siprocal spend:** ausência é **da fonte** — a plataforma não expõe custo. Não é uma lacuna do pipeline, é uma limitação da integração. Ver `docs/api_capabilities.md`.
- **MediaSmart workaround jun/26:** `stg.mediasmart_delivery` usa `UNION ALL` com `raw.mediasmart_daily` para cobrir dados pós-2026-05-24. Remover quando o orchestrator do Shiro for corrigido. Issue `#9`.
- **fact_io_plan quebrada:** `gold.fact_io_plan` retorna zero linhas por chain morta (`raw.luckbet_io_plan_snapshot` dropada em 2026-05-26). Issue `#8`.
- **Siprocal desatualizado:** último dado é março/2026. Requer `scripts/etl/sync_sheet.py` manual.
