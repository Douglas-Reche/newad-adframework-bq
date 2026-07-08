# Análise: Plano vs Delivery — Cora e TecPar 2026

---
> **📋 REESTRUTURAÇÃO EM ANDAMENTO — 2026-06-16**
> Esta análise foi feita sobre o schema de delivery **anterior ao reset de 2026-06-16**.
> A lógica de pacing (plano vs delivery) permanece válida como referência de negócio.
> Os nomes de tabelas e colunas precisarão ser revisados após o rebuild. Plano: [bq_restructuring_plan.md](bq_restructuring_plan.md)
---

**Data da análise:** 2026-06-15  
**Objetivo:** Mapear como conectar os dados de plano de IO (`stg.io_plan_drive`) com os dados de entrega das plataformas (MediaSmart, MGID, Siprocal) para construir a camada STG de pacing.  
**Escopo:** RAW → STG apenas. Gold e dashboard vêm depois.

---

## 1. Estado do Pipeline (RAW → STG)

### 1.1 `raw.io_plan_drive_snapshot`

| cliente | meses 2026 na RAW | obs |
|---|---|---|
| banco_cora_fe13d78a | Jan, Fev, Mar, Abr, Mai, Jun | completo |
| tecpar_edfcc744 | Jan, Fev, Mar, Abr, Mai, Jun | completo |

Bug corrigido em 2026-06-15: `get_last_sync` verificava só por `source_file`, ignorando `drive_folder`. Mesmo arquivo em JANEIRO/FEVEREIRO/MARÇO era ingerido apenas uma vez. Fix: adicionar `drive_folder` ao critério de dedup da função.

### 1.2 `stg.io_plan_drive`

Grain: 1 linha por `(client_id, drive_folder, strategy_name, flight_start)` — snapshot mais recente.

**Cora 2026** — 40 linhas:

| category | platform | flights | planned_spend total |
|---|---|---|---|
| DISPLAY | mediasmart | Jan→Jul/10 (7 linhas) | R$ 43.324 |
| VIDEO | mediasmart | Jan→Jul/10 (7 linhas) | R$ 54.349 |
| RETARGETING | mediasmart | Jan→Jul/10 (12 linhas*) | R$ 70.110 |
| NATIVE | mgid | Jan→Jul/10 (7 linhas) | R$ 81.133 |
| PUSH | siprocal | Jan→Jul/10 (7 linhas) | R$ 48.836 |

> *RETARGETING tem 12 linhas porque "Retargeting Display - 1st party" e "Retargeting Display - VIEW" são dois `strategy_name` distintos no xlsx — ambos mapeiam para RETARGETING/mediasmart e o spend deve ser somado.

**TecPar 2026** — 26 linhas:

| category | platform | flights | planned_spend total |
|---|---|---|---|
| DISPLAY | mediasmart | Jan→Jun (6 linhas) | R$ 41.100 |
| RETARGETING | mediasmart | Jan→Jun (6 linhas) | R$ 41.100 |
| NATIVE | mgid | Jan→Jun (6 linhas) | R$ 39.550 |
| PUSH | siprocal | Jan→Jun (9 linhas*) | R$ 42.300 |

> *PUSH 9 linhas porque alguns meses têm mais de uma estratégia de push no plano.

---

## 2. Análise Cora — Delivery por Plataforma

### 2.1 MediaSmart

- **ms_client_id**: `cora_2ruu4won`
- **Campanhas 2026** (3 campanhas ativas Jan→Jun):

| ms_campaign_name | ms_campaign_id (primeiros 8) | category | 2026 imp | 2026 clk |
|---|---|---|---|---|
| CORA_CONTADIGITAL_DISPLAY_JUNHO26 | ncfv7ti3 | DISPLAY | 4.051.370 | 7.591 |
| CORA_CONTADIGITAL_VIDEO_JUNHO26 | ivec3mwj | VIDEO | 4.260.116 | 18.079 |
| CORA_CONTADIGITAL_RETARGETING_JUNHO26 | f1asxj7p | RETARGETING | 5.863.986 | 10.311 |

- **Cobertura**: Jan/01/2026 → Jun/10/2026
- **Regra de join STG**: `ms_client_id = 'cora_2ruu4won'`
- **Mapeamento category → campanha**:
  - DISPLAY → `ms_campaign_name LIKE '%DISPLAY%'`
  - VIDEO → `ms_campaign_name LIKE '%VIDEO%'`
  - RETARGETING → `ms_campaign_name LIKE '%RETARGETING%'`

### 2.2 MGID

- **mgid_client_id**: `banco_cora_fe13d78a`
- **Campanhas 2026** (7 campanhas, 1 por período):

| mgid_campaign_name | campaign_id | período | imp | clk |
|---|---|---|---|---|
| Banco Cora \| NewAd \| Native \| 01/01-31/01 - Janeiro | 12326714 | 2026-01-09 → 02-01 | 1.089.397 | 4.015 |
| Banco Cora \| NewAd \| Native \| 01/02-28/02 - Fev | 12339730 | 2026-02-01 → 02-27 | 816.589 | 3.204 |
| Banco Cora \| NewAd \| Native \| 01/03-31/03 - Mar | 12368531 | 2026-03-02 → 04-01 | 810.929 | 3.208 |
| Banco Cora \| NewAd \| Native \| Abril 01-30/04 | 12400006 | 2026-04-01 → 04-29 | 1.481.708 | 5.850 |
| Banco Cora \| NewAd \| Native \| Maio 01-10/05 | 12414810 | 2026-05-01 → 05-11 | 167.296 | 976 |
| Banco Cora \| NewAd \| Native \| Maio/Jun 11/05-11/06 | 12414814 | 2026-05-12 → 06-11 | 539.462 | 6.071 |
| Banco Cora \| NewAd \| Native \| Jun/Julho 11/06-10/07 | 12437129 | 2026-06-11 → (ativo) | 17.583 | ~  |

- **Atenção**: campanha 12437129 (Jun/Jul) tem `mgid_client_id = NULL` na tabela de campanhas — bug já conhecido (novos registros MGID Jun/2026 chegam sem client_id no RAW).
- **Regra de join STG**: `mgid_client_id = 'banco_cora_fe13d78a'` para campanhas até Mai; JOIN via `mgid_campaign_id IN (12437129)` para a campanha ativa de Jun/Jul.
- **Mapeamento category**: todas as campanhas MGID da Cora = NATIVE (100%).

### 2.3 Siprocal

- **siprocal_client_id**: `banco_cora_fe13d78a`
- **Campanhas 2026** (5 campanhas, 1 por mês):

| campaign_name | advertiser_key | período | imp | clk |
|---|---|---|---|---|
| NEWAD_BANCOCORA_BR_JAN26 | BANCOCORA | 2026-01-09 → 01-31 | 144.374 | 1.948 |
| NEWAD_BANCOCORA_BR_FEV26 | BANCOCORA | 2026-02-02 → 02-28 | 113.172 | 1.776 |
| NEWAD_BANCOCORA_BR_MAR26 | BANCOCORA | 2026-03-04 → 03-31 | 101.304 | 1.452 |
| NEWAD_BANCOCORA_BR_ABR26 | BANCOCORA | 2026-04-02 → 04-30 | 129.096 | 2.765 |
| NEWAD_BANCOCORA_BR_MAI26 | BANCOCORA | 2026-05-04 → 06-09 | 402.617 | 5.340 |

- **Regra de join STG**: `siprocal_client_id = 'banco_cora_fe13d78a'`
- **Mapeamento category**: todas as campanhas Siprocal da Cora = PUSH (100%).

---

## 3. Análise TecPar — Delivery por Plataforma

### 3.1 MediaSmart

- **ms_client_id**: `tec_par_oqdfn8xx`
- **Campanhas 2026** (3 campanhas ativas):

| ms_campaign_name | ms_campaign_id (primeiros 8) | category | 2026 imp | 2026 clk |
|---|---|---|---|---|
| AMIGO_DISPLAY_700_ABRIL26 | 54ajzyrq | DISPLAY | 3.412.679 | ? |
| AMIGO_DISPLAY_JUNHO26 | 2lbuykb9 | DISPLAY | 4.749.913 | ? |
| AMIGO_RETARGETING_JUNHO26 | ihkq77od | RETARGETING | 7.502.489 | ? |

> **Atenção**: O nome das campanhas TecPar no MS começa com "AMIGO_" — isso reflete que o produto veiculado é da marca Amigo (sub-cliente da TecPar) rodando na conta MS da TecPar. Não confundir com o `ms_client_id` de Amigo (que não existe separado). A conta MS é única: `tec_par_oqdfn8xx`.

- **DISPLAY** tem 2 campanhas ativas simultaneamente (ABRIL26 e JUNHO26) — precisará de agrupamento.
- **Regra de join STG**: `ms_client_id = 'tec_par_oqdfn8xx'`
- **Mapeamento category → campanha**:
  - DISPLAY → `ms_campaign_name LIKE '%DISPLAY%'`
  - RETARGETING → `ms_campaign_name LIKE '%RETARGETING%'`

### 3.2 MGID — ⚠️ GAP CRÍTICO (não é bug de ingestão)

**TecPar não tem nenhuma campanha em `raw.mgid_campaigns`.**

Diagnóstico realizado em 2026-06-15:
- Varredura completa de todos os 47 nomes de campanhas MGID 2026 na RAW: zero resultado para TecPar
- A `stg.mgid_campaigns` resolve `mgid_client_id` via `core.platform_client_links` (mapeamento manual campaign_id → client_id) — TecPar ausente dessa tabela
- O conector MGID ingere uma única conta NewAd Brazil; campanhas TecPar não estão nessa conta
- Campanhas com `mgid_client_id = NULL` são: Einstein, Amigo/Brand, Senar, Stoquinho, Cora — nenhuma é TecPar

**Causa provável**: TecPar roda NATIVE em uma conta MGID separada (fora do conector atual) ou usa outra plataforma de Native Ads que não está integrada ao pipeline.

**Ações necessárias — verificar com Shiro/operações:**
1. TecPar tem conta MGID? Se sim, qual account ID? Adicionar ao conector.
2. Ou o NATIVE do TecPar roda em outra plataforma? Qual?
3. Sem resposta, pacing de NATIVE para TecPar ficará `NULL` no dashboard — informar ao comercial.

### 3.3 Siprocal — Atenção: split de client_id por período

TecPar no Siprocal tem **dois client_ids diferentes** dependendo do período:

| período | siprocal_client_id | advertiser_key | campanhas | imp | clk |
|---|---|---|---|---|---|
| Jan-Mar 2026 | `tecpar_edfcc744` | TECPAR | NEWAD_TECPAR_BR_JAN26/FEV26/MAR26 | 426.114 | 5.627 |
| Abr-Jun 2026 | `amigo_db1c2f0c` | AMIGOTECPAR | NEWAD_AMIGOTECPAR_BR_ABR26/MAI26/JUN26 | 715.824 | 11.761 |

**Contexto**: A partir de Abril/2026, as campanhas Siprocal de TecPar passaram a rodar sob `amigo_db1c2f0c` com `advertiser_key = 'AMIGOTECPAR'`. Amigo é sub-cliente legítimo de TecPar (confirmado).

**Regra de join STG para TecPar PUSH**:
```sql
(siprocal_client_id = 'tecpar_edfcc744')
OR
(siprocal_client_id = 'amigo_db1c2f0c' AND advertiser_key = 'AMIGOTECPAR')
```

---

## 4. Mapa Consolidado de Linkage

### Cora (`banco_cora_fe13d78a`)

| category | platform | join key delivery | status |
|---|---|---|---|
| DISPLAY | mediasmart | `ms_client_id = 'cora_2ruu4won' AND ms_campaign_name LIKE '%DISPLAY%'` | ✅ pronto |
| VIDEO | mediasmart | `ms_client_id = 'cora_2ruu4won' AND ms_campaign_name LIKE '%VIDEO%'` | ✅ pronto |
| RETARGETING | mediasmart | `ms_client_id = 'cora_2ruu4won' AND ms_campaign_name LIKE '%RETARGETING%'` | ✅ pronto |
| NATIVE | mgid | `mgid_client_id = 'banco_cora_fe13d78a'` (+ JOIN via campaign_id para Jun/Jul) | ✅ pronto (c/ ressalva Jun) |
| PUSH | siprocal | `siprocal_client_id = 'banco_cora_fe13d78a'` | ✅ pronto |

### TecPar (`tecpar_edfcc744`)

| category | platform | join key delivery | status |
|---|---|---|---|
| DISPLAY | mediasmart | `ms_client_id = 'tec_par_oqdfn8xx' AND ms_campaign_name LIKE '%DISPLAY%'` | ✅ pronto |
| RETARGETING | mediasmart | `ms_client_id = 'tec_par_oqdfn8xx' AND ms_campaign_name LIKE '%RETARGETING%'` | ✅ pronto |
| NATIVE | mgid | **DESCONHECIDO** — mgid_client_id TecPar não encontrado no BQ | ❌ bloqueado |
| PUSH | siprocal | `(siprocal_client_id = 'tecpar_edfcc744') OR (siprocal_client_id = 'amigo_db1c2f0c' AND advertiser_key = 'AMIGOTECPAR')` | ⚠️ requer UNION/CASE |

---

## 5. Design STG Proposto (apenas até STG — gold fica depois)

### 5.1 `stg.io_plan_drive` (já existe)

Já criada. Fornece: `client_id, plan_line_id, drive_folder, strategy_name, category, platform, flight_start, flight_end, planned_spend, planned_impressions, planned_clicks`.

### 5.2 Próxima view: `stg.delivery_by_category`

**Objetivo**: unificar os dados de entrega das 3 plataformas em um grain comum:
`client_id × category × day` — com métricas de impressões, cliques e investimento real.

**Fontes e regras por plataforma/cliente:**

```
MediaSmart:
  Cora    → ms_client_id = 'cora_2ruu4won'     + category via ms_campaign_name (DISPLAY/VIDEO/RETARGETING)
  TecPar  → ms_client_id = 'tec_par_oqdfn8xx'  + category via ms_campaign_name (DISPLAY/RETARGETING)

MGID:
  Cora    → mgid_client_id = 'banco_cora_fe13d78a'  → category = 'NATIVE'
  TecPar  → ❌ client_id desconhecido — BLOQUEADO

Siprocal:
  Cora    → siprocal_client_id = 'banco_cora_fe13d78a'  → category = 'PUSH'
  TecPar  → siprocal_client_id IN ('tecpar_edfcc744')
             OR (siprocal_client_id = 'amigo_db1c2f0c' AND advertiser_key = 'AMIGOTECPAR')
             → category = 'PUSH'
```

**Grain final da view**: `client_id × platform × category × day`

**Métricas**:
- `impressions` (SUM)
- `clicks` (SUM)
- `spend` (SUM — quando disponível; MS tem spend, MGID e Siprocal nem sempre)

### 5.3 Não criar ainda

A view `stg.delivery_by_category` está **especificada mas não deve ser criada** até:
1. Resolver o `mgid_client_id` de TecPar (ou decidir entregar sem NATIVE de TecPar).
2. Confirmar se o TecPar DISPLAY do MS é mesmo só para Amigo/sub-cliente ou inclui TecPar diretamente.
3. Decidir se a STG vai cobrir apenas 2026 ou todo o histórico disponível.

---

## 6. Issues Abertos

| # | issue | quem resolve | urgência |
|---|---|---|---|
| L1 | TecPar MGID client_id não encontrado no BQ | Shiro / verificar conector | alta |
| L2 | Cora MGID campanha Jun/Jul (id 12437129) com client_id = NULL | pipeline MGID fix | média |
| L3 | TecPar PUSH Siprocal split Jan-Mar vs Abr-Jun (dois client_ids) | tratar no join STG | alta |
| L4 | TecPar DISPLAY tem 2 campanhas MS simultâneas (ABRIL26 + JUNHO26) | agrupar por client+category | baixa |
| L5 | Cora FEVEREIRO 2026 iniciou 2026-02-02 (não 2026-02-01) | verificar se plano começa no dia 1 | baixa |
