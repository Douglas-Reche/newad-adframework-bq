# Gold Layer — Plano de Build

---
> **⚠️ LEGADO — PRÉ-REBUILD 2026-06-16 ⚠️**
> Este documento descreve a pipeline **anterior ao reset completo de 2026-06-16**.
> Tabelas, views, schemas e colunas aqui descritos **foram dropados e não existem mais no BigQuery**.
> Mantenha para consulta histórica — **não use como referência para desenvolvimento novo.**
> Plano atual: [bq_restructuring_plan.md](bq_restructuring_plan.md) · [CHANGELOG.md](../CHANGELOG.md)
---

> Criado em: 2026-06-16
> Status: **✅ GOLD LAYER COMPLETA — todas as 5 tabelas deployadas em 2026-06-16**
> Contexto: migração do modelo Power BI Cora de Excel/tabelas provisórias para gold layer BQ unificado.

---

## Princípio fundamental

> **Tudo "financeiro" vem do IO Plan. Tudo "volume" vem da entrega real das plataformas.**

- `investimento_realizado` = `SUM(planned_spend_daily) WHERE report_date <= TODAY` — não é spend da plataforma
- `investimento_projetado` = `SUM(planned_spend_daily)` para o período completo do flight
- Impressões e cliques realizados = dados reais de MediaSmart, MGID, Siprocal
- CPM/CPC realizado = calculado: `invest_realizado / volume_realizado`

O dashboard do cliente **nunca mostra spend da plataforma diretamente.**

---

## Tabelas a construir (sequência de dependência)

```
1. gold.fact_io_plan  (fix + redeploy)
        ↓
2. gold.dim_campaign  (rebuild com category)
        ↓
3. gold.fact_delivery  (rebuild com category)
        ↓
4. gold.fact_pacing  (nova VIEW)
        ↓
5. gold.fact_delivery_by_device  (nova tabela)
```

---

## 1. `gold.fact_io_plan` — Fix + Redeploy

**Status:** ⚠️ deployada mas incompleta — falta `unit_price`

**Grain:** `client_id + report_date + plan_line_id`

**O que muda:** adicionar campo `unit_price` vindo de `stg.io_plan_drive`

**Por quê:** necessário para as medidas CPM Projetado (`MAX(unit_price) WHERE buy_model='CPM'`) e CPC Projetado (`MAX(unit_price) WHERE buy_model='CPC'`)

**Campos do DDL atual (já existem):**

| Campo | Tipo | Fonte | Uso no dashboard |
|---|---|---|---|
| `client_id` | STRING | stg.io_plan_drive | chave |
| `report_date` | DATE | GENERATE_DATE_ARRAY(flight_start, flight_end) | chave temporal |
| `plan_line_id` | STRING | MD5(client+folder+strategy) | chave de linha |
| `drive_folder` | STRING | stg.io_plan_drive | contexto |
| `strategy_name` | STRING | stg.io_plan_drive | label da estratégia |
| `category` | STRING | stg.io_plan_drive | DISPLAY/VIDEO/RETARGETING/NATIVE/PUSH |
| `platform` | STRING | stg.io_plan_drive | mediasmart/mgid/siprocal |
| `spend_type` | STRING | stg.io_plan_drive | gross/net |
| `buy_model` | STRING | stg.io_plan_drive | CPM/CPC/CPA — filtro para medidas CPM e CPC |
| `flight_start` | DATE | stg.io_plan_drive | início do voo |
| `flight_end` | DATE | stg.io_plan_drive | fim do voo |
| `flight_days` | INT64 | stg.io_plan_drive | total de dias do voo |
| `planned_spend_daily` | FLOAT64 | planned_spend / flight_days | **Investimento Realizado e Projetado** |
| `planned_impressions_daily` | FLOAT64 | planned_impressions / flight_days | **Impressões Projetadas** |
| `planned_clicks_daily` | FLOAT64 | planned_clicks / flight_days | **Cliques Projetados** |
| `planned_spend_flight` | FLOAT64 | monthly_spend total | total do voo |
| `planned_impressions_flight` | FLOAT64 | total do voo | |
| `planned_clicks_flight` | FLOAT64 | total do voo | |
| `source_file` | STRING | nome do xlsx | rastreabilidade |
| `snapshot_at` | TIMESTAMP | momento do sync | rastreabilidade |

**Campo a adicionar:**

| Campo | Tipo | Fonte | Uso |
|---|---|---|---|
| `unit_price` | FLOAT64 | `stg.io_plan_drive.unit_price` | **CPM Projetado / CPC Projetado** |

**Completado:** ☐

---

## 2. `gold.dim_campaign` — Rebuild com `category`

**Status:** ⚠️ DDL existe mas quebrado (referencia views legadas) e sem campo `category`

**Grain:** `platform + platform_campaign_id` (PK composta)

**Propósito:** dimensão de lookup que mapeia cada campanha → category, client_id, campaign_name

**Fontes por plataforma:**

| Plataforma | platform_campaign_id | Fonte do nome | Lógica de category |
|---|---|---|---|
| `mediasmart` | `ms_strategy_id` (strategyid) | `stg.ms_delivery.ms_strategy_name` | LIKE em ms_strategy_name: DISPLAY / VIDEO / RETARGETING |
| `mgid` | `mgid_campaign_id` (campaignid) | `stg.mgid_campaigns.mgid_campaign_name` | constante `'NATIVE'` (todos clientes atuais) |
| `siprocal` | `campaign_name` (ex: NEWAD_BANCOCORA_BR_JUN26) | próprio campo | constante `'PUSH'` |

**Correções em relação ao DDL atual:**
- MS: trocar `stg.mediasmart_delivery` (legado, não existe mais) por `stg.ms_delivery` (T6)
- Siprocal: trocar `d.campaign_id` (pi_externo, não confiável) por `d.campaign_name` — alinhado com `fact_delivery`

**Schema completo:**

| Campo | Tipo | Descrição |
|---|---|---|
| `platform` | STRING NOT NULL | mediasmart / mgid / siprocal |
| `platform_campaign_id` | STRING NOT NULL | ID ou nome que identifica a campanha |
| `platform_campaign_name` | STRING | Nome legível da campanha |
| `platform_advertiser_id` | STRING | ID do anunciante na plataforma |
| `client_id` | STRING | FK para dim_client |
| `category` | STRING | **NOVO** — DISPLAY/VIDEO/RETARGETING/NATIVE/PUSH/OTHER |

**Completado:** ☐

---

## 3. `gold.fact_delivery` — Rebuild com `category`

**Status:** ⚠️ DDL existe mas sem campo `category` e não executado em BQ

**Grain:** `day + client_id + platform + platform_campaign_id + category`

**Propósito:** entrega real das plataformas com categoria mapeada — base para métricas de volume

**Fontes por plataforma:**

| Plataforma | STG fonte | client_id | Spend? |
|---|---|---|---|
| `mediasmart` | `stg.ms_delivery` (T6) | via `stg.ms_clients` + `platform_client_links` | ❌ não incluir — não é apresentado ao cliente |
| `mgid` | `stg.mgid_delivery` (T3) | já resolvido na STG | ❌ não incluir |
| `siprocal` | `stg.siprocal_delivery` | já resolvido na STG | ❌ não existe na fonte |

**Schema:**

| Campo | Tipo | Descrição |
|---|---|---|
| `day` | DATE | data da entrega |
| `client_id` | STRING | cliente canônico |
| `platform` | STRING | mediasmart / mgid / siprocal |
| `platform_campaign_id` | STRING | ID/nome da campanha na plataforma |
| `platform_campaign_name` | STRING | nome legível via dim_campaign |
| `category` | STRING | **via JOIN dim_campaign** — DISPLAY/VIDEO/RETARGETING/NATIVE/PUSH |
| `impressions` | INT64 | impressões reais entregues |
| `clicks` | INT64 | cliques reais |
| `video_completions` | INT64 | completions de vídeo (MS apenas; NULL para MGID/Siprocal) |
| `conversions_1..5` | INT64 | conversões MS (NULL para MGID/Siprocal) |
| `mgid_conv_interest` | INT64 | conversões MGID (NULL para MS/Siprocal) |
| `mgid_conv_decision` | INT64 | idem |
| `mgid_conv_buy` | INT64 | idem |

**Nota:** sem colunas de spend — não é apresentado ao cliente (vem do IO Plan).

**Completado:** ☐

---

## 4. `gold.fact_pacing` — Nova VIEW

**Status:** ☐ a criar

**Grain:** `client_id + report_date + category`

**Propósito:** tabela principal do dashboard — une planejado (IO plan) com realizado (volume das plataformas)

**Lógica:**

```sql
-- Lado planejado: agregar fact_io_plan por client + day + category
-- Lado realizado: agregar fact_delivery por client + day + category
-- JOIN: FULL OUTER ON client_id + report_date + category
```

**Schema:**

| Campo | Tipo | Origem | Uso no dashboard |
|---|---|---|---|
| `client_id` | STRING | ambos | filtro cliente |
| `report_date` | DATE | ambos | eixo temporal |
| `category` | STRING | ambos | filtro estratégia (DISPLAY/NATIVE/PUSH/etc) |
| `platform` | STRING | fact_io_plan | filtro plataforma |
| `buy_model` | STRING | fact_io_plan | filtro CPM/CPC/CPA |
| `unit_price` | FLOAT64 | fact_io_plan | base para CPM/CPC projetado |
| `planned_spend_daily` | FLOAT64 | fact_io_plan | **Investimento Realizado** (filtrar até hoje) e **Projetado** (total) |
| `planned_impressions_daily` | FLOAT64 | fact_io_plan | Impressões Projetadas |
| `planned_clicks_daily` | FLOAT64 | fact_io_plan | Cliques Projetados |
| `actual_impressions` | INT64 | fact_delivery | Impressões Realizadas |
| `actual_clicks` | INT64 | fact_delivery | Cliques Realizados |
| `flight_start` | DATE | fact_io_plan | para cálculo de período no Power BI |
| `flight_end` | DATE | fact_io_plan | idem |
| `flight_days` | INT64 | fact_io_plan | idem |

**Medidas DAX derivadas no Power BI (não armazenadas):**

| Medida DAX | Fórmula |
|---|---|
| Investimento Realizado | `CALCULATE(SUM(planned_spend_daily), report_date <= TODAY())` |
| Investimento Projetado | `SUM(planned_spend_daily)` |
| CPM Realizado | `Invest Realizado / Impressões Realizadas × 1000` |
| CPM Projetado | `MAX(unit_price)` filtrado por `buy_model = 'CPM'` |
| CPC Realizado | `Invest Realizado / Cliques Realizados` |
| CPC Projetado | `MAX(unit_price)` filtrado por `buy_model = 'CPC'` |
| Pacing Invest % | `Invest Realizado / Invest Projetado` |
| Pacing Impressões % | `Impressões Realizadas / Impressões Projetadas` |
| Pacing Cliques % | `Cliques Realizados / Cliques Projetados` |
| CTR Realizado | `Cliques Realizados / Impressões Realizadas` |
| CTR Projetado | `Cliques Projetados / Impressões Projetadas` |

**Completado:** ☐

---

## 5. `gold.fact_delivery_by_device` — Nova tabela

**Status:** ☐ a criar

**Grain:** `day + client_id + platform + platform_campaign_id + category + device_type`

**Propósito:** breakdown de impressões e cliques por dispositivo — alimenta a pasta "Devices" do dashboard

**Fontes:**

| Plataforma | STG fonte | Disponível? |
|---|---|---|
| `mediasmart` | `stg.ms_delivery_by_device` (T9) | ✅ |
| `mgid` | `stg.mgid_delivery_by_device` | ✅ |
| `siprocal` | não existe | ❌ sem dado de device |

**Schema:**

| Campo | Tipo | Descrição |
|---|---|---|
| `day` | DATE | |
| `client_id` | STRING | |
| `platform` | STRING | mediasmart / mgid |
| `platform_campaign_id` | STRING | |
| `category` | STRING | via JOIN dim_campaign |
| `device_type` | STRING | mobile / desktop / tablet / ctv / etc |
| `impressions` | INT64 | |
| `clicks` | INT64 | |

**Completado:** ☐

---

## Checklist de execução

| # | Tabela | DDL arquivo | Status | Data |
|---|---|---|---|---|
| 1 | `gold.fact_io_plan` | `gold/ddl/fact_io_plan.sql` | ✅ deployada | 2026-06-16 |
| 2 | `gold.dim_campaign` | `gold/ddl/dim_campaign.sql` | ✅ deployada | 2026-06-16 |
| 3 | `gold.fact_delivery` | `gold/ddl/fact_delivery.sql` | ✅ deployada | 2026-06-16 |
| 4 | `gold.fact_pacing` | `gold/ddl/fact_pacing.sql` | ✅ deployada | 2026-06-16 |
| 5 | `gold.fact_delivery_by_device` | `gold/ddl/fact_delivery_by_device.sql` | ✅ deployada | 2026-06-16 |

---

## Mapeamento medidas DAX → Gold (referência rápida)

| Pasta DAX | Medida | Tabela Gold | Campo |
|---|---|---|---|
| Investimento | Realizado | `fact_pacing` | `SUM(planned_spend_daily) WHERE date <= TODAY` |
| Investimento | Projetado | `fact_pacing` | `SUM(planned_spend_daily)` |
| Entrega | Impressões | `fact_pacing` | `SUM(actual_impressions)` |
| Entrega | Impressões Projetadas | `fact_pacing` | `SUM(planned_impressions_daily)` |
| Entrega | Cliques | `fact_pacing` | `SUM(actual_clicks)` |
| Entrega | Cliques Projetados | `fact_pacing` | `SUM(planned_clicks_daily)` |
| Eficiência | CTR Realizado | `fact_pacing` | calculado |
| Eficiência | CTR CPM | `fact_pacing` | calculado, filtro `buy_model='CPM'` |
| CPM | CPM Projetado | `fact_pacing` | `MAX(unit_price)` + filtro |
| CPM | CPM Realizado | `fact_pacing` | calculado |
| CPC | CPC Projetado | `fact_pacing` | `MAX(unit_price)` + filtro |
| CPC | CPC Realizado | `fact_pacing` | calculado |
| Pacing | Invest % | `fact_pacing` | calculado |
| Pacing | Impressões % | `fact_pacing` | calculado |
| Pacing | Cliques % | `fact_pacing` | calculado |
| Pacing | CPM % | `fact_pacing` | calculado, filtro CPM |
| Pacing | CPC % | `fact_pacing` | calculado, filtro CPC |
| Devices | Impressões device | `fact_delivery_by_device` | `SUM(impressions)` GROUP BY device |
| Devices | Cliques device | `fact_delivery_by_device` | `SUM(clicks)` GROUP BY device |

---

## Decisões de arquitetura registradas

1. **Financeiro = IO Plan, Volume = Plataforma** — cliente nunca vê spend real da plataforma
2. **Grain fact_delivery:** `client + day + campaign + category` — campanha visível para drill-down, category para join com plan
3. **Grain fact_pacing:** `client + day + category` — nível de join entre plan e delivery; sem risco de duplicação do plano
4. **buy_model em fact_pacing:** vem do IO plan — permite filtrar medidas por CPM vs CPC sem tabelas separadas
5. **unit_price em fact_io_plan:** a ser adicionado (fix mínimo no DDL)
6. **Siprocal sem device:** não entra em fact_delivery_by_device
7. **Spend das plataformas:** não entra em nenhuma tabela gold de cliente — apenas para uso interno/analytics futuro
8. **category = "estratégia" na linguagem NewAd** — DISPLAY, VIDEO, RETARGETING, NATIVE, PUSH

---

*Próxima ação: step 1 — fix `unit_price` em `gold/ddl/fact_io_plan.sql` + redeploy*
