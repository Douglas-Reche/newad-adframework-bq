# AdFramework — Plano Completo Power BI
> Documento técnico de implementação | Projeto: `adframework` (GCP) | Atualizado: 2026-04-29

---

## Sumário

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Conexão BigQuery → Power BI](#2-conexão-bigquery--power-bi)
3. [Tabelas Gold — Inventário Completo](#3-tabelas-gold--inventário-completo)
4. [Modelo de Relacionamentos](#4-modelo-de-relacionamentos)
5. [Medidas DAX Completas](#5-medidas-dax-completas)
6. [Estrutura de Páginas — Dashboard](#6-estrutura-de-páginas--dashboard)
7. [Mapeamento KPI × Campo Gold](#7-mapeamento-kpi--campo-gold)
8. [Filtros e Segmentação por Cliente](#8-filtros-e-segmentação-por-cliente)
9. [Armadilhas e Cuidados Críticos](#9-armadilhas-e-cuidados-críticos)
10. [Métricas Ausentes — Limitações Conhecidas](#10-métricas-ausentes--limitações-conhecidas)
11. [Cronograma de Refresh](#11-cronograma-de-refresh)

---

## 1. Visão Geral da Arquitetura

```
BigQuery (adframework.gold)
│
├── dim_date          ─┐
├── dim_platform       │  Dimensões estáticas
├── dim_client         │  (baixa frequência de mudança)
├── dim_io_line        │
└── dim_creative      ─┘
│
├── fct_delivery_daily     ← delivery diário de todas as campanhas (multi-cliente)
├── fct_io_plan_daily      ← pacing planejado por IO line por dia
└── fct_luckbet_daily      ← delivery LuckBet com conversões mapeadas (ftds/cadastros)
```

**Modo de conexão obrigatório: Import Mode**
DirectQuery inviabiliza pacing acumulado com DAX e degrada performance.
O refresh incremental (Power BI Premium) pode ser configurado por partição de `date`.

---

## 2. Conexão BigQuery → Power BI

### Passo a Passo

**1. Obter Dados → Google BigQuery**
```
Project ID:  adframework
Dataset:     gold
Mode:        Import  ← obrigatório, nunca DirectQuery
```

**2. Credenciais**
- Conta Google com acesso ao projeto `adframework`
- Papel IAM mínimo: `BigQuery Data Viewer` + `BigQuery Job User`
- Autenticação via OAuth 2.0 (browser popup na primeira conexão)

**3. Selecionar todas as tabelas do dataset `gold`**

| Tabela BigQuery | Nome sugerido no Power BI | Refresh |
|----------------|--------------------------|---------|
| `gold.dim_date` | `dim_date` | Anual (adicionar datas futuras) |
| `gold.dim_platform` | `dim_platform` | Raramente (nova plataforma) |
| `gold.dim_client` | `dim_client` | Semanal |
| `gold.dim_io_line` | `dim_io_line` | Diário (após IO atualizado no Admin UI) |
| `gold.dim_creative` | `dim_creative` | Diário |
| `gold.fct_delivery_daily` | `fct_delivery_daily` | Diário (após ETL) |
| `gold.fct_io_plan_daily` | `fct_io_plan_daily` | Diário (após IO atualizado) |
| `gold.fct_luckbet_daily` | `fct_luckbet_daily` | Diário (após ETL) |

**4. Query customizada para `dim_io_line` (evitar budget_total no fato)**

No Power Query, ao importar `dim_io_line`, não é necessária query customizada — importar a tabela completa. O `budget_total` vive **apenas** em `dim_io_line`, nunca nas tabelas de fato.

---

## 3. Tabelas Gold — Inventário Completo

### 3.1 `gold.dim_date`
**Grain:** 1 linha por data | **1.215 linhas** | Agosto 2023 → Dezembro 2028

| Campo | Tipo | Uso |
|-------|------|-----|
| `date` | DATE | **Chave primária** — relacionar com todas as fatos |
| `date_id` | STRING | Formato YYYYMMDD (alternativo para slicers) |
| `year` | INT | Filtro de ano |
| `month_number` | INT | Filtro de mês (1–12) |
| `month_name` | STRING | Label PT/EN (ex: "April") |
| `month_name_short` | STRING | Ex: "Apr" |
| `day` | INT | Dia do mês |
| `weekday_name` | STRING | Ex: "Tuesday" |
| `weekday_number` | INT | 1=domingo, 7=sábado |
| `quarter` | INT | 1–4 |
| `year_quarter` | STRING | Ex: "2026-Q1" |
| `year_month` | STRING | Ex: "2026-03" — útil para slicer de mês |
| `week_start` | DATE | Início da semana (segunda-feira) |
| `month_start` | DATE | Primeiro dia do mês |
| `quarter_start` | DATE | Primeiro dia do trimestre |

### 3.2 `gold.dim_platform`
**Grain:** 1 linha por plataforma | **3 linhas**

| Campo | Tipo | Valores |
|-------|------|---------|
| `platform_id` | STRING | `mediasmart`, `mgid`, `siprocal` |
| `platform_name` | STRING | `MediaSmart`, `MGID`, `Siprocal` |

### 3.3 `gold.dim_client`
**Grain:** 1 linha por cliente NewAD | **8 linhas**

| Campo | Tipo | Uso |
|-------|------|-----|
| `newad_client_id` | STRING | **Chave primária** — filtro principal multi-cliente |
| `client_name` | STRING | Nome do anunciante/cliente |
| `advertiser_id` | STRING | ID interno do anunciante |

> **Uso chave:** `dim_client[newad_client_id]` é o pivô de filtragem entre clientes. Cada página do dashboard deve ter filtro de página vinculado a este campo.

### 3.4 `gold.dim_io_line`
**Grain:** 1 linha por IO line (combinação io_id + line_id) | **229 linhas**

| Campo | Tipo | Uso |
|-------|------|-----|
| `io_id` | STRING | FK para fatos (chave de relacionamento principal) |
| `line_id` | STRING | **Chave primária** — mais granular que io_id |
| `proposal_id` | STRING | Agrupamento por proposta comercial |
| `line_number` | STRING | Número da linha no IO (ex: "L1", "L2") |
| `line_name` | STRING | Descrição da linha (ex: "Awareness CPM") |
| `line_status` | STRING | Status operacional |
| `platform` | STRING | `mediasmart`, `mgid`, `siprocal` |
| `newad_client_id` | STRING | FK para dim_client |
| `advertiser_id` | STRING | FK para dim_advertiser |
| `advertiser_name` | STRING | Nome do anunciante |
| `campaign_name` | STRING | Nome da campanha |
| `campaign_type` | STRING | Tipo de campanha |
| `funnel` | STRING | Posição no funil (ex: "Awareness") |
| `objective` | STRING | Objetivo (ex: "Clique") |
| `buying_model` | STRING | `CPM`, `CPC`, `CPA`, `CPA_2_3_4` |
| `buying_value` | NUMERIC | Valor unitário do modelo de compra |
| `deliverable_metric` | STRING | Métrica de entrega contratada |
| `deliverable_volume` | NUMERIC | Volume contratado total |
| **`budget_total`** | NUMERIC | **Orçamento total da linha — USE AQUI, não nos fatos** |
| `platform_campaign_id` | STRING | ID da campanha na DSP |
| `start_date` | DATE | Início da linha |
| `end_date` | DATE | Fim da linha |
| `total_days` | INT | Duração em dias |
| `daily_budget_target` | NUMERIC | Budget diário alvo (budget_total / total_days) |
| `daily_volume_target` | NUMERIC | Volume diário alvo |
| `proposal_month` | STRING | Mês de referência da proposta (ex: "2026-03") |

### 3.5 `gold.dim_creative`
**Grain:** 1 linha por criativo × plataforma | **3.629 linhas**

| Campo | Tipo | Uso |
|-------|------|-----|
| `platform_id` | STRING | `mediasmart` ou `mgid` |
| `creative_id` | STRING | ID do criativo na DSP |
| `platform_campaign_id` | STRING | FK para campanha |
| `creative_type` | STRING | `banner`, `video`, `native` |
| `creative_name` | STRING | Nome do criativo |
| `image_url` | STRING | URL da imagem (para gallery views) |

### 3.6 `gold.fct_delivery_daily`
**Grain:** data × IO line × campanha DSP × plataforma | **4.420 linhas**
**Partição:** `date` | **Cluster:** `io_id, platform`
**Período:** Agosto 2025 → Abril 2026

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `date` | DATE | FK → dim_date |
| `io_id` | STRING | FK → dim_io_line |
| `line_id` | STRING | FK → dim_io_line (preferir esta) |
| `proposal_id` | STRING | FK → dim_io_line |
| `newad_client_id` | STRING | FK → dim_client |
| `platform` | STRING | FK → dim_platform |
| `platform_campaign_id` | STRING | ID da campanha na DSP |
| `proposal_month` | STRING | Mês de referência |
| `binding_scope` | STRING | Sempre `campaign` (filtro de deduplicação aplicado na construção) |
| `impressions` | INT | Impressões entregues |
| `clicks` | INT | Cliques |
| `video_start` | INT | Vídeos iniciados |
| `video_complete` | INT | Vídeos concluídos (100%) |
| `conversions1` | INT | Conv 1 = Pageview (pixel) |
| `conversions2` | INT | Conv 2 = **Cadastro** (LuckBet) |
| `conversions3` | INT | Conv 3 = **FTD** (First Time Deposit) |
| `conversions4` | INT | Conv 4 = **Depósito Recorrente** |
| `conversions5` | INT | Conv 5 = Início do Cadastro |
| **`cost_estimated`** | NUMERIC | **INVESTIMENTO** = buying_model × buying_value × volume |
| `dsp_revenue` | NUMERIC | Receita DSP (repasse MediaSmart → NewAD, informativo) |
| `buying_model` | STRING | Modelo de compra da linha |
| `gold_updated_at` | TIMESTAMP | Timestamp de atualização |

> **CRÍTICO:** `cost_estimated` = Investimento do cliente. `dsp_revenue` = repasse da DSP para a NewAD. São coisas diferentes. Não confundir.

### 3.7 `gold.fct_io_plan_daily`
**Grain:** data × IO line | **10.467 linhas**
**Partição:** `date` | **Cluster:** `io_id`
**Período:** Agosto 2025 → Maio 2026

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `date` | DATE | FK → dim_date |
| `io_id` | STRING | FK → dim_io_line |
| `line_id` | STRING | FK → dim_io_line (preferir esta) |
| `proposal_id` | STRING | FK |
| `newad_client_id` | STRING | FK → dim_client |
| `platform` | STRING | FK → dim_platform |
| `proposal_month` | STRING | Mês de referência |
| `planned_budget_daily` | NUMERIC | Budget planejado para o dia (budget_total / total_days) |
| `planned_budget_to_date` | NUMERIC | Budget planejado acumulado até a data |
| `planned_volume_total` | NUMERIC | Volume total contratado |
| `planned_volume_daily` | NUMERIC | Volume planejado para o dia |
| `planned_volume_to_date` | NUMERIC | Volume planejado acumulado |
| `active_days` | INT | Dias decorridos desde início da linha |
| `gold_updated_at` | TIMESTAMP | Timestamp de atualização |

> **CRÍTICO:** `budget_total` NÃO existe nesta tabela. Para "Projetado Total", usar `SUM(dim_io_line[budget_total])`. Para "Planejado Acumulado até hoje", usar `planned_budget_to_date` desta tabela.

### 3.8 `gold.fct_luckbet_daily`
**Grain:** data × campanha × estratégia × plataforma (LuckBet específico) | **8.065 linhas**
**Partição:** `date` | **Cluster:** `campaign_group, platform`
**Período:** Agosto 2025 → Abril 2026

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `date` | DATE | FK → dim_date |
| `proposal_month` | STRING | Mês de referência |
| `platform` | STRING | FK → dim_platform |
| `campaign_group` | STRING | Grupo de campanha LuckBet |
| `platform_campaign_id` | STRING | ID da campanha na DSP |
| `platform_campaign_name` | STRING | Nome da campanha |
| `strategy_id` | STRING | ID da estratégia |
| `strategy_name` | STRING | Nome da estratégia |
| `buying_model` | STRING | CPM, CPC, CPA |
| `format_name` | STRING | Formato do criativo |
| `target_device` | STRING | Dispositivo alvo |
| `creative_type` | STRING | Tipo de criativo |
| `io_id` | STRING | FK → dim_io_line (pode ser NULL) |
| `line_id` | STRING | FK → dim_io_line (pode ser NULL) |
| `newad_client_id` | STRING | FK → dim_client |
| `planned_investment` | NUMERIC | Investimento planejado **mensal** — NÃO SOMAR DIRETAMENTE |
| `planned_daily_investment` | NUMERIC | Investimento planejado diário |
| `impressions` | INT | Impressões entregues |
| `clicks` | INT | Cliques |
| `video_start` | INT | Vídeos iniciados |
| `video_complete` | INT | Vídeos concluídos |
| **`investment_delivered`** | NUMERIC | **Investimento real entregue** (= cost_estimated) |
| **`cadastros`** | INT | **Cadastros** (conv2 mapeada por Shiro 2026-04-29) |
| **`ftds`** | INT | **FTDs - First Time Deposits** (conv3) |
| **`depositos_recorrentes`** | INT | **Depósitos Recorrentes** (conv4) |
| `tx_ftd_cadastro` | NUMERIC | Taxa FTD/Cadastro |
| `tx_ftd_click` | NUMERIC | Taxa FTD/Click |
| `tx_deposito_ftd` | NUMERIC | Taxa Depósito/FTD |
| `dsp_revenue` | NUMERIC | Receita DSP (informativo) |
| `gold_updated_at` | TIMESTAMP | Timestamp de atualização |

> **ATENÇÃO `planned_investment`:** Este campo vem de `luckbet_sheet_strategy_daily` e repete o budget mensal em CADA linha de estratégia por dia. **Nunca usar SUM()** direto. Usar com LASTDATE ou FIRSTDATE para pegar o valor do mês, ou usar `planned_daily_investment` para somar por dia.

---

## 4. Modelo de Relacionamentos

### Diagrama

```
dim_date ──────────────────────────────────────────────
   │[date]                                              │
   │N:1                                                 │
   ↓                                                    ↓
fct_delivery_daily ─────────── fct_io_plan_daily   fct_luckbet_daily
   │[line_id] N:1                 │[line_id] N:1       │[line_id] N:1
   │                              │                    │
   ▼                              ▼                    ▼
dim_io_line ──────────────────────────────────────────
   │[newad_client_id] N:1    │[platform] N:1
   ▼                         ▼
dim_client              dim_platform
```

### Tabela de Relacionamentos

| Tabela Origem | Campo Origem | Tabela Destino | Campo Destino | Cardinalidade | Ativa? | Cross-filter |
|--------------|-------------|----------------|--------------|---------------|--------|-------------|
| `fct_delivery_daily` | `date` | `dim_date` | `date` | N:1 | ✅ Sim | Single |
| `fct_delivery_daily` | `line_id` | `dim_io_line` | `line_id` | N:1 | ✅ Sim | Single |
| `fct_delivery_daily` | `platform` | `dim_platform` | `platform_id` | N:1 | ✅ Sim | Single |
| `fct_delivery_daily` | `newad_client_id` | `dim_client` | `newad_client_id` | N:1 | ✅ Sim | Single |
| `fct_io_plan_daily` | `date` | `dim_date` | `date` | N:1 | ✅ Sim | Single |
| `fct_io_plan_daily` | `line_id` | `dim_io_line` | `line_id` | N:1 | ⚠️ Inativa* | Single |
| `fct_io_plan_daily` | `newad_client_id` | `dim_client` | `newad_client_id` | N:1 | ✅ Sim | Single |
| `fct_luckbet_daily` | `date` | `dim_date` | `date` | N:1 | ✅ Sim | Single |
| `fct_luckbet_daily` | `line_id` | `dim_io_line` | `line_id` | N:1 | ✅ Sim | Single |
| `fct_luckbet_daily` | `newad_client_id` | `dim_client` | `newad_client_id` | N:1 | ✅ Sim | Single |
| `fct_luckbet_daily` | `platform` | `dim_platform` | `platform_id` | N:1 | ✅ Sim | Single |
| `dim_io_line` | `platform` | `dim_platform` | `platform_id` | N:1 | ✅ Sim | Single |
| `dim_io_line` | `newad_client_id` | `dim_client` | `newad_client_id` | N:1 | ✅ Sim | Single |
| `dim_creative` | `platform_id` | `dim_platform` | `platform_id` | N:1 | ✅ Sim | Single |

> *`fct_io_plan_daily[line_id] → dim_io_line[line_id]` deve ser **inativa** para evitar ambiguidade de caminho com `fct_delivery_daily`. Ativar via `USERELATIONSHIP()` no DAX quando necessário.

### Por que `fct_io_plan_daily → dim_io_line` inativa?

Ambas `fct_delivery_daily` e `fct_io_plan_daily` se conectam a `dim_io_line`. Se ambas forem ativas e `dim_io_line` conecta a `dim_client`, o Power BI pode criar caminhos ambíguos. Deixar `fct_io_plan_daily → dim_io_line` inativa e ativar no DAX quando precisar de dados de plano filtrados por atributos de linha.

---

## 5. Medidas DAX Completas

Criar uma tabela auxiliar `_Medidas` no Power BI e adicionar as medidas abaixo.

### 5.1 Métricas Base de Delivery

```dax
Impressões =
SUM(fct_delivery_daily[impressions])

Cliques =
SUM(fct_delivery_daily[clicks])

Video Start =
SUM(fct_delivery_daily[video_start])

Video Complete =
SUM(fct_delivery_daily[video_complete])
```

### 5.2 Investimento (= cost_estimated)

```dax
Investimento =
SUM(fct_delivery_daily[cost_estimated])

Investimento LuckBet =
SUM(fct_luckbet_daily[investment_delivered])

Receita DSP =
SUM(fct_delivery_daily[dsp_revenue])
```

> `Investimento` é a métrica principal de custo ao cliente = buying_model × buying_value × volume entregue.
> `Receita DSP` = repasse da DSP para NewAD (informativo, não é "custo" do cliente).

### 5.3 Budget Planejado (Projetado)

```dax
Projetado Total =
CALCULATE(
    SUM(dim_io_line[budget_total])
)

Planejado Diário =
SUM(fct_io_plan_daily[planned_budget_daily])

Planejado Acumulado =
CALCULATE(
    MAX(fct_io_plan_daily[planned_budget_to_date]),
    USERELATIONSHIP(fct_io_plan_daily[line_id], dim_io_line[line_id]),
    LASTDATE(dim_date[date])
)

Planejado Acumulado LuckBet =
SUMX(
    SUMMARIZE(
        fct_luckbet_daily,
        fct_luckbet_daily[platform_campaign_id],
        fct_luckbet_daily[proposal_month]
    ),
    CALCULATE(
        MAX(fct_luckbet_daily[planned_daily_investment])
        * MAX(fct_luckbet_daily[date])
    )
)
```

> **ARMADILHA:** `dim_io_line[budget_total]` tem 1 linha por IO line. Ao filtrar por mês/data, o DAX pode filtrar fora algumas linhas. Para "Projetado Total de Março", filtrar pelo `proposal_month` em `dim_io_line`.

### 5.4 KPIs de Performance

```dax
CTR =
DIVIDE(
    SUM(fct_delivery_daily[clicks]),
    SUM(fct_delivery_daily[impressions])
)

CTR % =
FORMAT([CTR], "0.00%")

CPM Efetivo =
DIVIDE(
    [Investimento],
    SUM(fct_delivery_daily[impressions])
) * 1000

CPC Efetivo =
DIVIDE(
    [Investimento],
    SUM(fct_delivery_daily[clicks])
)

VTR (View-Through Rate) =
DIVIDE(
    SUM(fct_delivery_daily[video_complete]),
    SUM(fct_delivery_daily[video_start])
)

CPV (Custo por View) =
DIVIDE(
    [Investimento],
    SUM(fct_delivery_daily[video_start])
)

CPCV (Custo por View Completo) =
DIVIDE(
    [Investimento],
    SUM(fct_delivery_daily[video_complete])
)
```

### 5.5 Pacing

```dax
Pacing % =
DIVIDE(
    [Investimento],
    [Planejado Acumulado]
)

Pacing % Label =
VAR pct = [Pacing %]
RETURN FORMAT(pct, "0.0%")

Status Pacing =
VAR pct = [Pacing %]
RETURN
    SWITCH(
        TRUE(),
        ISBLANK(pct),            "–",
        pct >= 0.95 && pct <= 1.10, "✅ On Track",
        pct < 0.80,              "🔴 Under Pacing",
        pct < 0.95,              "🟡 Atenção",
        pct > 1.15,              "🔴 Over Pacing",
        "🟡 Atenção"
    )

Cor Pacing =
VAR pct = [Pacing %]
RETURN
    SWITCH(
        TRUE(),
        ISBLANK(pct),            "#808080",
        pct >= 0.95 && pct <= 1.10, "#28A745",
        pct < 0.80,              "#DC3545",
        pct < 0.95,              "#FFC107",
        pct > 1.15,              "#DC3545",
        "#FFC107"
    )

Saldo Orçamentário =
[Projetado Total] - [Investimento]

Dias Restantes =
DATEDIFF(
    MAX(fct_delivery_daily[date]),
    MAX(dim_io_line[end_date]),
    DAY
)

Burn Rate Diário Necessário =
DIVIDE(
    [Saldo Orçamentário],
    [Dias Restantes]
)
```

### 5.6 Conversões LuckBet

```dax
Cadastros =
SUM(fct_luckbet_daily[cadastros])

FTDs =
SUM(fct_luckbet_daily[ftds])

Depósitos Recorrentes =
SUM(fct_luckbet_daily[depositos_recorrentes])

Início Cadastro =
SUM(fct_delivery_daily[conversions5])

Cadastros (delivery) =
SUM(fct_delivery_daily[conversions2])

FTDs (delivery) =
SUM(fct_delivery_daily[conversions3])

Depósitos (delivery) =
SUM(fct_delivery_daily[conversions4])
```

> Preferir `fct_luckbet_daily` para dashboards LuckBet — mapeamento já está correto e validado.
> `fct_delivery_daily.conversions2/3/4` como alternativa para clientes sem tabela dedicada.

### 5.7 KPIs de Conversão LuckBet

```dax
CPL (Custo por Lead/Cadastro) =
DIVIDE(
    [Investimento LuckBet],
    [Cadastros]
)

CPA FTD (Custo por FTD) =
DIVIDE(
    [Investimento LuckBet],
    [FTDs]
)

CPA Depósito =
DIVIDE(
    [Investimento LuckBet],
    [Depósitos Recorrentes]
)

Taxa FTD/Cadastro =
DIVIDE(
    [FTDs],
    [Cadastros]
)

Taxa FTD/Click =
DIVIDE(
    [FTDs],
    SUM(fct_luckbet_daily[clicks])
)

Taxa Depósito/FTD =
DIVIDE(
    [Depósitos Recorrentes],
    [FTDs]
)

Cadastros por 1000 Impressões =
DIVIDE(
    [Cadastros],
    SUM(fct_luckbet_daily[impressions])
) * 1000

FTDs por 1000 Impressões =
DIVIDE(
    [FTDs],
    SUM(fct_luckbet_daily[impressions])
) * 1000
```

### 5.8 Medidas de Período

```dax
Mês Selecionado =
SELECTEDVALUE(dim_date[year_month], "Todos")

Período Label =
VAR dtMin = MIN(fct_delivery_daily[date])
VAR dtMax = MAX(fct_delivery_daily[date])
RETURN
    FORMAT(dtMin, "DD/MM") & " – " & FORMAT(dtMax, "DD/MM/YYYY")

Última Atualização =
FORMAT(
    CONVERT(MAX(fct_delivery_daily[gold_updated_at]), DATETIME),
    "DD/MM/YYYY HH:MM"
)
```

### 5.9 Campanhas e IO

```dax
Campanhas Ativas =
DISTINCTCOUNT(fct_delivery_daily[platform_campaign_id])

IO Lines Ativas =
DISTINCTCOUNT(fct_delivery_daily[line_id])

Campanhas Sem IO =
CALCULATE(
    DISTINCTCOUNT(fct_delivery_daily[platform_campaign_id]),
    ISBLANK(fct_delivery_daily[line_id])
)

Impressões Sem IO =
CALCULATE(
    SUM(fct_delivery_daily[impressions]),
    ISBLANK(fct_delivery_daily[line_id])
)

% Entrega Sem IO =
DIVIDE(
    [Impressões Sem IO],
    [Impressões]
)
```

### 5.10 Medidas Time Intelligence

```dax
Investimento MoM =
CALCULATE(
    [Investimento],
    DATEADD(dim_date[date], -1, MONTH)
)

Variação MoM % =
DIVIDE(
    [Investimento] - [Investimento MoM],
    [Investimento MoM]
)

Investimento MTD =
CALCULATE(
    [Investimento],
    DATESMTD(dim_date[date])
)

Investimento YTD =
CALCULATE(
    [Investimento],
    DATESYTD(dim_date[date])
)

Cadastros MoM =
CALCULATE(
    [Cadastros],
    DATEADD(dim_date[date], -1, MONTH)
)

FTDs MoM =
CALCULATE(
    [FTDs],
    DATEADD(dim_date[date], -1, MONTH)
)

Variação FTD MoM % =
DIVIDE(
    [FTDs] - [FTDs MoM],
    [FTDs MoM]
)
```

### 5.11 Top N e Ranking

```dax
Rank Campanha por Investimento =
RANKX(
    ALL(fct_luckbet_daily[platform_campaign_name]),
    [Investimento LuckBet]
)

Rank Criativo por CTR =
RANKX(
    ALL(dim_creative[creative_name]),
    [CTR]
)
```

### 5.12 Medidas para Pacing LuckBet (com planned_investment)

```dax
Investimento Planejado Mensal LuckBet =
CALCULATE(
    SUMX(
        SUMMARIZE(
            fct_luckbet_daily,
            fct_luckbet_daily[platform_campaign_id],
            fct_luckbet_daily[proposal_month]
        ),
        CALCULATE(MAX(fct_luckbet_daily[planned_investment]))
    )
)

Pacing LuckBet % =
DIVIDE(
    [Investimento LuckBet],
    [Investimento Planejado Mensal LuckBet]
)
```

> **CRÍTICO `planned_investment`:** Este campo repete o valor mensal em cada linha diária por campanha. Nunca usar `SUM(fct_luckbet_daily[planned_investment])`. Usar `MAX()` por `campaign_id + proposal_month` antes de somar entre campanhas.

---

## 6. Estrutura de Páginas — Dashboard

### Arquitetura Multi-Cliente

Cada página do dashboard é filtrada por um cliente específico. A filtragem ocorre via:
- Filtro de Página em `dim_client[newad_client_id]` = valor fixo do cliente
- OU slicer de cliente na página (para visão consolidada)

```
Página 0: Visão Geral (todos os clientes) — filtro de cliente como slicer
Página 1: LuckBet Dashboard Principal
Página 2: LuckBet — Análise por Campanha
Página 3: LuckBet — Criativos
Página 4: [Cliente X] — Dashboard Principal
Página 5: [Cliente Y] — Dashboard Principal
```

---

### Página 1: LuckBet — Dashboard Principal

**Fonte:** `fct_luckbet_daily` + `fct_io_plan_daily` + `dim_io_line`
**Filtro de Página:** `dim_client[newad_client_id]` = ID do LuckBet

**Seção 1 — Cabeçalho e KPI Cards**

| Card | Medida DAX | Formato |
|------|-----------|---------|
| Investimento | `[Investimento LuckBet]` | R$ #,##0.00 |
| Projetado | `[Projetado Total]` | R$ #,##0.00 |
| Pacing % | `[Pacing LuckBet %]` | 0.0% |
| Impressões | `[Impressões]` | #,##0 |
| CTR | `[CTR %]` | 0.00% |
| CPM Efetivo | `[CPM Efetivo]` | R$ 0.00 |

**Seção 2 — Conversões**

| Card | Medida DAX | Formato |
|------|-----------|---------|
| Cadastros | `[Cadastros]` | #,##0 |
| FTDs | `[FTDs]` | #,##0 |
| Depósitos Rec. | `[Depósitos Recorrentes]` | #,##0 |
| CPL | `[CPL (Custo por Lead/Cadastro)]` | R$ 0.00 |
| CPA FTD | `[CPA FTD (Custo por FTD)]` | R$ 0.00 |
| Taxa FTD/Cadastro | `[Taxa FTD/Cadastro]` | 0.0% |

**Seção 3 — Gráfico de Entrega Diária vs Planejado**

- Eixo X: `dim_date[date]`
- Linha 1 (azul): `[Investimento LuckBet]` acumulado
- Linha 2 (cinza): `[Planejado Acumulado]` acumulado
- Linha 3 (laranja): `[Pacing LuckBet %]` no eixo Y secundário

**Seção 4 — Breakdown por Campanha**

Tabela ou matriz:
- Linhas: `fct_luckbet_daily[platform_campaign_name]`
- Colunas: Investimento, Impressões, Cliques, CTR, Cadastros, FTDs, CPL, CPA FTD

**Seção 5 — Slicers**
- `dim_date[year_month]` (mês)
- `fct_luckbet_daily[campaign_group]` (grupo de campanha)
- `fct_luckbet_daily[platform]` (plataforma)
- `fct_luckbet_daily[buying_model]` (modelo de compra)

---

### Página 2: LuckBet — Análise por Campanha/Estratégia

**Fonte:** `fct_luckbet_daily`

**Componentes:**
- Tabela: campanha × estratégia × Investimento × Impressões × Cadastros × FTDs × CPL × CPA FTD
- Gráfico de barras: Top 10 campanhas por FTDs
- Gráfico de dispersão: CPL × FTDs (quadrante de eficiência)
- Trend de Taxa FTD/Cadastro por semana

---

### Página 3: LuckBet — Criativos

**Fonte:** `fct_luckbet_daily` + `dim_creative`

**Componentes:**
- Galeria de criativos com `dim_creative[image_url]`
- KPIs por criativo: Impressões, CTR, CPM, Video Complete (VTR)
- Filtro por formato (banner, vídeo)
- Filtro por dispositivo

---

### Página 4: Dashboard Multi-Cliente (Visão Geral)

**Fonte:** `fct_delivery_daily` + `dim_io_line` + `dim_client`

**Componentes:**
- Slicer: `dim_client[client_name]`
- Cards: Investimento Total, Campanhas Ativas, Impressões, CTR
- Tabela: cliente × Investimento × Projetado × Pacing %
- Gráfico: Investimento por plataforma (MediaSmart vs MGID vs Siprocal)

---

### Página 5: Pacing por IO Line (Operacional)

**Fonte:** `fct_delivery_daily` + `fct_io_plan_daily` + `dim_io_line`

**Componentes:**
- Tabela: IO line × Budget Total × Investimento Atual × Planejado Acumulado × Pacing % × Status
- Destaque condicional: vermelho (<80%), amarelo (80-95%), verde (95-110%), laranja (>110%)
- Gráfico de Gantt: datas de início/fim das linhas com delivery acumulado
- Filtro: `dim_client[client_name]`, `dim_date[year_month]`

---

## 7. Mapeamento KPI × Campo Gold

### Dashboard LuckBet Atual (referência) → Gold

| KPI no Dashboard | Tabela Gold | Campo | Observação |
|-----------------|-------------|-------|-----------|
| Investimento Entregue | `fct_luckbet_daily` | `investment_delivered` | = cost_estimated calculado |
| Investimento Planejado | `fct_luckbet_daily` | `planned_investment` | Mensal — não somar direto |
| Pacing % | DAX | `[Pacing LuckBet %]` | Entregue / Planejado |
| Impressões | `fct_luckbet_daily` | `impressions` | |
| Cliques | `fct_luckbet_daily` | `clicks` | |
| CTR | DAX | `[CTR]` | clicks / impressions |
| CPM Efetivo | DAX | `[CPM Efetivo]` | investment / impr × 1000 |
| Cadastros | `fct_luckbet_daily` | `cadastros` | conv2 mapeada |
| FTDs | `fct_luckbet_daily` | `ftds` | conv3 mapeada |
| Depósitos Rec. | `fct_luckbet_daily` | `depositos_recorrentes` | conv4 mapeada |
| CPL (Cadastro) | DAX | `[CPL]` | investment / cadastros |
| CPA FTD | DAX | `[CPA FTD]` | investment / ftds |
| Taxa FTD/Cadastro | `fct_luckbet_daily` | `tx_ftd_cadastro` | ou DAX ftds/cadastros |
| Taxa FTD/Click | `fct_luckbet_daily` | `tx_ftd_click` | ou DAX ftds/clicks |
| Taxa Dep/FTD | `fct_luckbet_daily` | `tx_deposito_ftd` | |
| Video Start | `fct_luckbet_daily` | `video_start` | |
| Video Complete | `fct_luckbet_daily` | `video_complete` | |
| VTR | DAX | `[VTR]` | video_complete/video_start |
| DSP Revenue | `fct_luckbet_daily` | `dsp_revenue` | repasse DSP, informativo |

### Mapeamento de Conversões (confirmado Shiro, 2026-04-29)

| Conv | Nome | Campo `fct_delivery_daily` | Campo `fct_luckbet_daily` |
|------|------|---------------------------|--------------------------|
| conv1 | Pageview | `conversions1` | — |
| conv2 | Cadastro | `conversions2` | `cadastros` |
| conv3 | FTD (First Time Deposit) | `conversions3` | `ftds` |
| conv4 | Depósito Recorrente | `conversions4` | `depositos_recorrentes` |
| conv5 | Início do Cadastro | `conversions5` | — |

---

## 8. Filtros e Segmentação por Cliente

### Estratégia de Multi-Cliente

O campo `newad_client_id` presente em `fct_delivery_daily`, `fct_io_plan_daily`, `fct_luckbet_daily` e `dim_io_line` é o pivot de filtragem.

**Para uma página dedicada a um cliente:**
1. Adicionar Filtro de Página em `dim_client[newad_client_id]` com o valor fixo do cliente
2. OU criar um slicer sincronizado entre páginas

**Para a LuckBet específicamente:**
- Usar `fct_luckbet_daily` que já é exclusivamente LuckBet
- Filtro adicional via `dim_client[newad_client_id]` para garantia

### Isolamento de Tabelas por Cliente

```dax
Investimento do Cliente Selecionado =
CALCULATE(
    [Investimento],
    FILTER(dim_client, dim_client[newad_client_id] = SELECTEDVALUE(dim_client[newad_client_id]))
)
```

---

## 9. Armadilhas e Cuidados Críticos

### ⚠️ A1: `budget_total` existe APENAS em `dim_io_line`

**Nunca:** `SUM(fct_io_plan_daily[budget_total])` — campo não existe nesta tabela.
**Correto:** `SUM(dim_io_line[budget_total])` com filtro adequado.

### ⚠️ A2: `planned_investment` em `fct_luckbet_daily` é repetido

Este campo vem da planilha e repete o budget mensal de cada campanha em TODAS as linhas diárias.
- `SUM(fct_luckbet_daily[planned_investment])` retorna valores 30×+ maiores que o real.
- **Solução:** Usar `MAX()` ou `FIRSTNONBLANK()` por `platform_campaign_id + proposal_month`.

### ⚠️ A3: Relacionamento `fct_io_plan_daily → dim_io_line` é inativo

Para cruzar dados de plano com atributos da IO line (ex: campaign_name, buying_model), usar:
```dax
Budget por Modelo =
CALCULATE(
    SUM(fct_io_plan_daily[planned_budget_daily]),
    USERELATIONSHIP(fct_io_plan_daily[line_id], dim_io_line[line_id])
)
```

### ⚠️ A4: `cost_estimated` vs `dsp_revenue` — papéis diferentes

| Campo | Quem paga | Direção | Uso |
|-------|-----------|---------|-----|
| `cost_estimated` | Cliente NewAD → NewAD | Custo do cliente | Investimento, CPM, CPC, CPA |
| `dsp_revenue` | DSP (MediaSmart) → NewAD | Receita NewAD | Informativo, análise de margem |

### ⚠️ A5: `binding_scope = 'campaign'` já filtrado no ETL

A tabela `fct_delivery_daily` já tem o filtro aplicado na construção — não há duplicação por linhas múltiplas de IO. O atributo `binding_scope` está na tabela mas sempre será `'campaign'`.

### ⚠️ A6: `fct_luckbet_daily[line_id]` pode ser NULL

Campanhas LuckBet sem IO registrado terão `line_id = NULL`. Isso não quebra o modelo, mas significa que `dim_io_line` não terá dados para filtrar para essas campanhas.

### ⚠️ A7: Datas futuras em `fct_io_plan_daily`

Esta tabela tem linhas até maio 2026 (fim das IO lines ativas). KPIs de entrega para datas futuras retornarão NULL / BLANK no `fct_delivery_daily`. Os cálculos de pacing para datas futuras mostrarão planejado mas delivery = 0 — isso é esperado.

---

## 10. Métricas Ausentes — Limitações Conhecidas

As seguintes métricas do dashboard LuckBet atual **não estão disponíveis** no Gold Layer atual:

| Métrica | Status | Fonte Potencial | Esforço |
|---------|--------|----------------|---------|
| Alcance (Reach) | ❌ Não disponível | API MediaSmart (campo separado) | Alto |
| Novos Usuários | ❌ Não disponível | Pixel dataset (muito pequeno) | Alto |
| Cidades / Estados | ❌ Não disponível | API MediaSmart geo-breakdown | Médio |
| Dispositivos breakdown | ⚠️ Parcial | `fct_luckbet_daily[target_device]` (planejado, não real) | Médio |
| Pós-Click / Pós-View | ⚠️ Muito limitado | `adtracking.raw_events` (135 rows — MVP) | Alto |
| Pageviews do site | ⚠️ Pixel MVP | `pixel.touchpoints` (135 rows — pouco dado) | Médio |
| Share of Voice | ❌ Não disponível | Dados de mercado externos | Muito Alto |
| Frequência | ❌ Não disponível | API MediaSmart (requer report especial) | Alto |

**Para adicionar breakdown de dispositivos:**
- Integrar `raw.mediasmart_daily` campo `device_type` no pipeline stg
- Adicionar ao `fct_delivery_daily` um campo `device_type` (requer re-criar a tabela)

---

## 11. Cronograma de Refresh

### Tabelas que mudam diariamente (após ETL)

```
Após ETL (Cloud Run) rodar — tipicamente 08h00 BRT:
  1. fct_delivery_daily     ← rebuild completo (particionado por date)
  2. fct_io_plan_daily      ← rebuild completo (se IO Manager atualizado)
  3. fct_luckbet_daily      ← rebuild completo

Após Admin UI atualizar IO:
  4. dim_io_line            ← rebuild (quando adicionar/editar IO)
  5. fct_io_plan_daily      ← rebuild (depende de dim_io_line)
```

### Tabelas de baixa frequência

```
Semanal:
  - dim_creative            ← quando add criativos nas plataformas

Mensal:
  - dim_client              ← quando add novo cliente

Anual:
  - dim_date                ← adicionar datas futuras

Raramente:
  - dim_platform            ← nova plataforma
```

### Schedule no Power BI Service

| Tabela | Frequência | Horário |
|--------|-----------|---------|
| `fct_delivery_daily` | Diário | 09:00 BRT |
| `fct_luckbet_daily` | Diário | 09:00 BRT |
| `fct_io_plan_daily` | Diário | 09:05 BRT |
| `dim_io_line` | Diário | 09:10 BRT |
| `dim_creative` | Semanal (segunda) | 09:00 BRT |
| `dim_client` | Semanal | 09:00 BRT |
| `dim_date` | Mensal | 01:00 BRT |
| `dim_platform` | Manual | — |

---

## Glossário

| Termo | Definição |
|-------|-----------|
| `io_id` | ID único de uma IO — gerado pelo Admin UI |
| `line_id` | ID de uma linha dentro de uma IO (mais granular) |
| `platform_campaign_id` | ID da campanha na DSP (MediaSmart/MGID) |
| `buying_model` | Modelo de compra: CPM, CPC, CPA, CPA_2_3_4 |
| `cost_estimated` | **Investimento do cliente** = volume × buying_value |
| `dsp_revenue` | Repasse DSP → NewAD (não é custo do cliente) |
| `pacing` | Ritmo: custo real ÷ planejado acumulado |
| `binding_scope` | Nível do vínculo IO: `campaign` (correto) ou `strategy` (duplica) |
| Gold Layer | `adframework.gold` — star schema físico para Power BI |
| FTD | First Time Deposit — primeira aposta real LuckBet |
| CPA | Custo por Ação (FTD ou Cadastro dependendo do contexto) |
| CPL | Custo por Lead (= custo por Cadastro) |

---

*Documento: AdFramework Power BI Plan | Versão: 2026-04-29 | douglas@newad.com.br*
