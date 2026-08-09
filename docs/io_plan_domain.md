# IO Plan — Domínio Completo (Pipeline, Expansão, Pacing, Auditoria)

> **Manutenção:** Tier 2 — gatilho: mudança de lógica de pacing/plano, novo cliente com particularidade de IO Plan, ou resolução do gap de nomes de tabela pré-rebuild citado abaixo.

> Consolida em um único doc: `io_plan_pipeline.md`, `etl_expansion_plan.md`,
> `analise_plano_vs_delivery_cora_tecpar.md`, `audit_io_plan_cora_tecpar_2026-06-15.md`
> (Frente C, item C2 do `plano_reestruturacao_documentacao.md`, aprovado por Douglas em 2026-08-08).
> Os 4 originais foram deletados — este arquivo é a fonte única do domínio IO Plan a partir de agora.

> Status: ✅ ATUAL como lógica de negócio. **Nomes de tabela de delivery (MediaSmart/MGID/Siprocal)
> citados nas seções de pacing e auditoria abaixo são do schema anterior ao rebuild de 2026-06-16**
> — revise contra `raw_layer_design.md`/`stg_layer_design.md` antes de reusar em desenvolvimento.
> O pipeline do IO Plan em si (Drive → RAW → Core → Gold) é **independente** do rebuild de entrega
> e continua válido como está descrito aqui.

---

## Sumário

1. [Contexto e motivação](#1-contexto-e-motivação)
2. [Arquitetura do pipeline](#2-arquitetura-do-pipeline)
3. [Mapeamento Drive → client_id](#3-mapeamento-drive--client_id)
4. [Regras de seleção e parsing de arquivos Excel](#4-regras-de-seleção-e-parsing-de-arquivos-excel)
5. [Camadas de dados (RAW / STG / Core / Gold)](#5-camadas-de-dados-raw--stg--core--gold)
6. [Limitações conhecidas do pipeline](#6-limitações-conhecidas-do-pipeline)
7. [Plano de expansão ETL — dimensões e métricas novas](#7-plano-de-expansão-etl--dimensões-e-métricas-novas)
8. [Pacing Cora/TecPar — mapeamento plano × delivery](#8-pacing-coratecpar--mapeamento-plano--delivery)
9. [Auditoria de qualidade Cora/TecPar (2026-06-15/16)](#9-auditoria-de-qualidade-coratecpar-2026-06-1516)
10. [Design futuro — linkage plano × campanha (V2, não implementado)](#10-design-futuro--linkage-plano--campanha-v2-não-implementado)
11. [Mapa de arquivos e próximos passos](#11-mapa-de-arquivos-e-próximos-passos)

---

## 1. Contexto e motivação

O IO Plan é a camada de **dados de planejamento comercial** da NewAd — distinto dos dados de
entrega (MediaSmart, MGID, Siprocal). Responde perguntas como:

- Quanto planejamos gastar com esse cliente nesse mês?
- Quantas impressões estavam previstas para esse voo?
- O pacing real está acima ou abaixo do planejado?

A fonte são **planilhas Excel (.xlsx) mantidas pela equipe comercial** (Rafa, Gessiane),
armazenadas no Google Drive. Não existe API — é ingestão de arquivo.

### Diferença fundamental em relação ao pipeline de entrega

| Aspecto | Pipeline de entrega (MS/MGID/Siprocal) | IO Plan |
|---|---|---|
| Fonte | APIs REST | Arquivos .xlsx no Drive |
| Grain | Dia + campanha + criativo | Voo (flight) + estratégia |
| Atualização | Diária automática | Quando o arquivo no Drive muda |
| Dados | Impressões/cliques/spend reais | Impressões/spend planejados |
| Orquestração | Cloud Run + Firestore jobs | Script Python standalone + Cloud Run admin |
| Trigger | Cloud Scheduler (diário) | Drive `modifiedTime` (mudança no arquivo) |

---

## 2. Arquitetura do pipeline

```
Google Drive
  pasta raiz: 0ACFCcMtN5j8EUk9PVA
  estrutura:  CLIENT / ANO / MÊS / PLANO / arquivo.xlsx
        │
        ▼  scripts/io_plan/sync_drive.py
           (OAuth Desktop local | Service Account no Cloud Run)
           Regra de seleção: arquivo oficial (sem nome de pessoa) mais recente
           Parsing: openpyxl — flight label → datas, header mapping, strategy rows
        │
        ▼  WRITE_APPEND + skip por modifiedTime
  adframework.raw.io_plan_drive_snapshot
  (strategy grain — uma linha por estratégia por voo por arquivo)
        │
        ▼  rebuild_core_for_client()  — DELETE + INSERT por client_id
  adframework.core.io_plan_manual
  (flight grain — uma linha por voo, gross + net separados, plan_version='DRIVE-SYNC')
        │
        ▼
  adframework.gold.fact_io_plan
  (day grain — explodido por dia de calendário dentro do voo)
```

**Serviço admin (Cloud Run):** `services/io-plan-admin/main.py`
- `POST /sync` → dispara `sync_drive.py` via subprocess
- Endpoint protegido por Bearer token
- ⚠️ Bug conhecido (ver L6 em §6): `python-multipart` ausente em `requirements.txt` →
  `POST /sync` retorna 500 ao tentar `await request.form()`

---

## 3. Mapeamento Drive → client_id

Auditado em 2026-06-14 cruzando pastas do Drive root com `core.dim_client`.

### Mapeamento confirmado (`CLIENT_MAP` em `sync_drive.py`)

| Drive folder | client_id | Notas |
|---|---|---|
| `7K` | `bet7k_b777ab9c` | |
| `APERAM` | `aperam_14d1f27e` | |
| `CATÁLISE` | `catalise_0b7d18d6` | |
| `CORA` | `banco_cora_fe13d78a` | |
| `DAXX` | `dax_agency_00000001` | |
| `DOOING` | `dooing_994db77e` | |
| `EINSTEIN` | `einstein_6b33a588` | |
| `LUCKBET` | `luckbet_bea15ebc` | |
| `MOPAR` | `mopar_a47949f4` | |
| `MRV` | `mrv_f19a2136` | |
| `OCUPACIONAL` | `ocupacional_98c851f5` | |
| `PATIO MEDEIROS` | `patio_medeiros_874a0358` | |
| `STOCCO` | `stocco_b712c66e` | |
| `TEC PAR` | `tecpar_edfcc744` | Amigo (`amigo_db1c2f0c`) é sub-cliente; vive dentro desta pasta |

### Dúvidas abertas (não mapeado ainda, ver também `project_io_plan_client_map` na memória)

| Drive folder | Situação |
|---|---|
| `LABTOLAB PARDINI` | Pode ser `pardini_60395024`, `lab2lab_efb1cb34` ou ambos compartilhando pasta. Confirmar com Douglas. |
| `PHISALIA` | Sem correspondência em `dim_client`. Cliente não cadastrado ou inativo. |

### Pastas internas / sem cliente

`ADMIN`, `LOGOS NEWAD`, `MKT NEWAD`, `NEWAD`, `PLANILHAS`, `REPORTS`, `SIPROCAL`

### Pastas sem match em dim_client (provavelmente clientes históricos inativos)

`AGÊNCIA 18`, `ANA GAMING`, `CASSINO`, `CERPA`, `KOMUH`, `MASTERCARD`, `PI PARCEIROS`, `RINO`, `TRALALÁ`

---

## 4. Regras de seleção e parsing de arquivos Excel

### 4.1 Regras de seleção de arquivo

Quando há múltiplos `.xlsx` na mesma pasta `PLANO`:

**Regra 1 — Prioridade pelo nome (oficial vs pessoal).** Tokens de nomes pessoais:
`PERSONAL_NAME_TOKENS = {"RAFA", "GESSIANE"}`. Se existir ao menos um arquivo sem token de
pessoa → considera só os oficiais; se só existir com nome de pessoa → usa como fallback.

**Regra 2 — Mais recente entre os candidatos.** Entre os selecionados na Regra 1, pega só o
mais recente por `modifiedTime` do Drive (evita duplicação entre versões V2/V3 ou arquivo
renomeado).

```python
official = [f for f in xlsx_files if not _has_personal_name(f["name"])]
candidates = official if official else xlsx_files
xlsx_f = max(candidates, key=lambda f: f["modifiedTime"])
```

**Regra 3 — Skip por modifiedTime (dedup de sync).** Antes de baixar, compara `modifiedTime`
do Drive com `MAX(snapshot_at)` da raw para aquele `source_file`. Sem mudança → skip.

### 4.2 Parsing de arquivos Excel (.xlsx)

**Biblioteca:** `openpyxl` com `data_only=True`.

Cada aba representa um **voo** (flight period). Nome da aba ou célula A1 contém o label, ex:
`PLANO 11 MAI A 10 JUN`, `1º MAI A 10 MAI`, `PLANO 11 JUN A 10 JUL`.

Abas ignoradas (`SKIP_SHEETS`): `RESUMO`, `SUMMARY`, `SUGESTAO`, `SUGESTÃO`, `SUGESTOES`,
`SUGESTÕES`, `INDICADORES`, `TEMPLATE`, `COPIA`, `CÓPIA`, `COPY` (ver §9.7.2 — `SUGESTÕES`
foi adicionado depois de causar rows extras na Cora 2026).

**Parsing do flight label → datas:**
```python
def parse_flight_label(label, default_year=2026):
    # Regex: r"(\d{1,2})\s+([A-Z]{3,})\s+A\s+(\d{1,2})\s+([A-Z]{3,})"
    # "PLANO 11 MAI A 10 JUN" → flight_start=2026-05-11, flight_end=2026-06-10
    # Sem padrão → retorna (None, None) → linha entra na raw mas não no core
```

**Mapeamento de colunas (header detection).** Primeira linha com ≥ 2 colunas reconhecíveis é
o header:

| Palavra-chave no header | Campo raw |
|---|---|
| `estrategia` | `strategy_name` |
| `dispositivo` | `device` |
| `formato` | `format` |
| `modelo` / `compra` | `buy_model` |
| `impressoes mensais` | `impressions_cpm` |
| `estimativa` | `impressions_est` |
| `visualizac` | `video_views` |
| `investimento` / `liquido` | `monthly_spend` |
| `valor` | `unit_price` |
| `ctr` | `ctr_approx` |
| `cliques mensais` / `cliques` | `clicks` |
| `alcance` | `reach` |

**Detecção de `spend_type` (gross vs net):** baseada no `unit_price` máximo das linhas com
`impressions_cpm` preenchido — `max > 5.0` → `gross` (preços brutos, ex: R$10, R$12 CPM);
`max ≤ 5.0` → `net` (preços líquidos de tabela, ex: R$1.00 CPM).

**Detecção de plataforma por nome de estratégia (`PLATFORM_RULES`):**

| Keyword (substring, case-insensitive) | platform |
|---|---|
| `retargeting` | `mediasmart` |
| `video ads` | `mediasmart` |
| `midia programatica` | `mediasmart` |
| `display` | `mediasmart` |
| `native ads` | `mgid` |
| `push mgid` | `mgid` |
| `push siprocal` | `siprocal` |
| `push apptargeting` | `unknown` |
| `push` | `unknown` |

Esse mapeamento por keyword tem limitação real de dado — ver §8 e §9 para o detalhamento
de quantas linhas ficam `unknown` na prática.

---

## 5. Camadas de dados (RAW / STG / Core / Gold)

### 5.1 RAW — `raw.io_plan_drive_snapshot`

**Write mode:** `WRITE_APPEND` · **DDL:** `raw/ddl/io_plan_drive_snapshot.sql`

| Campo | Tipo BQ | Descrição | Notas |
|---|---|---|---|
| `client_id` | STRING | ID canônico do cliente | via `CLIENT_MAP` |
| `drive_folder` | STRING | Caminho relativo no Drive | ex: `2026/MAIO` |
| `source_file` | STRING | Nome do arquivo .xlsx | base do skip-by-modifiedTime |
| `spend_type` | STRING | `'gross'` ou `'net'` | detectado pelo unit_price máximo das linhas CPM |
| `snapshot_at` | TIMESTAMP | Data/hora do sync | UTC |
| `flight_label` | STRING | Label do voo (texto da aba ou A1) | ex: `PLANO 11 MAI A 10 JUN` |
| `flight_start` | DATE | Início do voo | NULL se parser não encontrou padrão de data |
| `flight_end` | DATE | Fim do voo | NULL se parser não encontrou padrão de data |
| `strategy_name` | STRING | Nome da estratégia (texto livre) | ex: `Mídia Progrm. - Display` |
| `platform` | STRING | Plataforma detectada via `PLATFORM_RULES` | |
| `device` | STRING | Dispositivo | se disponível na planilha |
| `format` | STRING | Formato de criativo | se disponível na planilha |
| `buy_model` | STRING | Modelo de compra | `CPM`, `CPC`, `CPA`, `CPD` |
| `unit_price` | FLOAT64 | Preço unitário (R$/CPM ou R$/CPC) | |
| `impressions_cpm` | INT64 | Volume estimado em linhas CPM | |
| `impressions_est` | INT64 | Volume estimado em linhas CPC/Push | |
| `video_views` | INT64 | Views estimadas | |
| `monthly_spend` | FLOAT64 | Investimento planejado no período (R$) | |
| `ctr_approx` | FLOAT64 | CTR aproximado (%) | quando disponível |
| `clicks` | INT64 | Cliques planejados | quando disponível |
| `reach` | INT64 | Alcance planejado | quando disponível |

### 5.2 STG — `stg.io_plan` ✅ criada e validada (2026-06-24)

Substitui a `stg.io_plan_drive` antiga (arquivada em `stg/ddl/_legacy/io_plan_drive.sql` —
tinha um bug: forçava `Push` sempre = `siprocal`, contradito pelo dado real `"Push - MGID"`).

**Grain:** `(client_id, drive_folder, strategy_name, flight_start)`, dedup pelo snapshot mais
recente (`ROW_NUMBER` por `snapshot_at DESC`). Filtra linhas sem
`flight_start`/`flight_end`/`monthly_spend`.

**`formato`** extraído de `strategy_name` (texto livre da planilha) via busca de keyword —
vocabulário igual ao de entrega (`Display/Video/Retargeting/Native/Push`) + `AppInstall`
(exclusivo do plano). Não reusa o campo `format` já existente na RAW (vem em vocabulário
diferente, ex: `"Banner IAB"`, `"Push Banner"` — preservado como `creative_format_label`).

**Sem `goal_type`** — decisão do usuário (2026-06-24): `goal_type` é conceito de
campanha/entrega (`ms_campaigns`/`mg_campaigns`/`sp_campaigns`), não de planejamento.
`core.dict_format` ganhou `AppInstall`→`CPI` (`platform='io_plan'`) mesmo assim, para ficar
disponível quando algum consumidor precisar cruzar plano com entrega.

**`platform`** corrigido em relação à RAW (sem mudar o parser `sync_drive.py`):
`PLATFORM_RULES` procura substring exata `"push siprocal"`, que não bate com o dado real
`"Push - App Targeting SIPROCAL"` (texto no meio) — 91/295 linhas caíam em `unknown`. Fix na
STG: `contém 'SIPROCAL' → siprocal`, `contém 'MGID' → mgid`. Resolve 7/91. Os outros 84
(`Push`/`AppInstall` genéricos) não têm sinal de plataforma no texto — limitação real do dado.

**Resultado real:** dedup reduz 295→**125 linhas**. 125/125 (100%) com `formato`. 96/125
(77%) com `platform` resolvido. DDL: `stg/ddl/io_plan.sql`.

RAW tem grupos com até 14 snapshots idênticos da mesma linha de plano (7 cópias por sync, 2
syncs) — bug do parser (ver §9.7) confirmado ainda presente à época. STG mascara corretamente
via dedup (0 duplicatas confirmadas no resultado final), mas o parser não foi corrigido na
fonte antes do rebuild.

⚠️ Ao 2026-06-24, `gold.fact_io_plan` ainda não consumia `stg.io_plan` — derivava de
`core.io_plan_manual`, que por sua vez ainda lia de `raw.io_plan_drive_snapshot` direto (não
passa pela STG nova). Revisar a cadeia completa ao reconstruir o Gold.

### 5.3 Core — `core.io_plan_manual`

**Write mode:** DELETE por `client_id + plan_version='DRIVE-SYNC'` + INSERT
**Grain:** `client_id + flight_start + flight_end`

| Campo | Tipo BQ | Descrição |
|---|---|---|
| `client_id` | STRING | ID canônico do cliente |
| `flight_start` | DATE | Início do voo |
| `flight_end` | DATE | Fim do voo |
| `planned_impressions` | INTEGER | Total de impressões planejadas no voo (todas as estratégias) |
| `planned_clicks` | INTEGER | Total de cliques planejados |
| `planned_spend_gross` | NUMERIC | Investimento bruto planejado (R$) |
| `planned_spend_net` | NUMERIC | Investimento líquido planejado (R$) — NULL se não disponível |
| `plan_version` | STRING | `'DRIVE-SYNC'` ou versão manual |
| `source_file` | STRING | Arquivo(s) de origem (concatenados por `,`) |
| `loaded_at` | TIMESTAMP | Data/hora do último rebuild |

**Lógica de rebuild:**
1. Remove todas as linhas `DRIVE-SYNC` do cliente
2. Lê a snapshot mais recente de cada `source_file` da raw (evita reprocessar syncs antigos)
3. Aplica `DISTINCT` para eliminar linhas idênticas quando o mesmo arquivo aparece em
   múltiplos meses do Drive
4. Agrega por `flight_start + flight_end + spend_type`
5. Pivota gross/net; impressões preferem a versão net quando disponível

**Origem de dados por cliente (exemplo Cora):**

| plan_version | Origem | Período | Observação |
|---|---|---|---|
| `PLANO-JAN-MAR` | `Plano NEWAD CORA JAN-MAR 2026.xlsx` | Jan–Mar/26 | Só gross mensal; sem estratégia nem impressões |
| `PLANO-ABR-AJUSTADO` | `Plano NEWAD CORA ABR AJUSTADO 2026.xlsx` | Abr/26 | Tem impressões e clicks totais |
| `DRIVE-SYNC` | múltiplos arquivos Mai–Ago/26 | Mai–Ago/26 | Gerado pelo rebuild automático |

### 5.4 Gold — `gold.fact_io_plan`

**Grain:** `client_id + report_date` (um dia de calendário por linha)
**Lógica:** expande cada voo do core distribuindo planejamento linearmente (÷ dias do voo).

| Campo | Tipo | Descrição |
|---|---|---|
| `client_id` | STRING | |
| `report_date` | DATE | Cada dia dentro do voo |
| `planned_impressions_daily` | NUMERIC | `planned_impressions / dias_do_voo` |
| `planned_spend_gross_daily` | NUMERIC | `planned_spend_gross / dias_do_voo` |
| `planned_spend_net_daily` | NUMERIC | `planned_spend_net / dias_do_voo` |
| `flight_start` | DATE | Início do voo de origem |
| `flight_end` | DATE | Fim do voo de origem |
| `plan_version` | STRING | |

> Confirme contra `gold_layer_design.md` se esta view segue vigente com este grain — o doc
> original datava de 2026-06-24 e a Gold layer foi reconstruída depois disso (rebuild
> 2026-06-16 em diante).

---

## 6. Limitações conhecidas do pipeline

**L1 — `flight_start/flight_end` NULL para arquivos sem padrão de data na aba.** O parser só
extrai datas quando a aba tem o padrão `DD MÊS A DD MÊS`. Planilhas com nomes de aba livres
(`JAN-MAR 2026`, `RESUMO`) tinham todas as linhas com NULL e não entravam no core — **resolvido
pelo fallback via `drive_folder`, ver §9.7 Mudanças 4/7**.

**L1b — Duplicação de linhas por sync** (raiz: parser iterava abas sem filtrar pelo mês) —
confirmado presente em 2026-06-24: grupos com até 14 snapshots idênticos da mesma linha (7
cópias por sync, em 2 syncs). STG mascara via dedup, mas o parser não tinha sido corrigido na
fonte antes do reset de schema.

**L2 — Duplicação de valores quando há múltiplos arquivos para o mesmo período** (RESOLVIDA).
Antes de 2026-06-14, `find_plano_files` pegava todos os xlsx, incluindo RAFA + cópias
renomeadas — core somava todos (R$157.500 em vez de R$78.750 real para 11 Mai–10 Jun Cora).
Fix deployado em `ff9dfe2`: regra "mais recente por pasta".

**L3 — `spend_type` detection imprecisa para planilhas mistas.** Planilhas com linhas CPM e
CPC na mesma aba: `max(unit_price_cpm)` pode misturar taxas de CPC em colunas de CPM,
classificando `net` quando é `gross`.

**L4 — Sem breakdown de estratégia no core e gold** (PARCIALMENTE RESOLVIDA — 2026-06-24).
`core.io_plan_manual` agrega todas as estratégias em uma linha por voo. `stg.io_plan` já tem
grain por estratégia (`formato`/`goal_type` incluídos) — para análise por formato (Display vs
Native), consultar `stg.io_plan` em vez da raw direto. `core`/`gold` continuam agregados.

**L5 — `planned_spend_net` NULL para a maioria dos clientes.** Populado só quando há arquivo
com `unit_price ≤ R$5` (preço líquido). Maioria dos clientes só tem versão bruta.

**L6 — `POST /sync` retorna 500 no Cloud Run admin.** `services/io-plan-admin/main.py` usa
`await request.form()` mas `python-multipart` está ausente de `requirements.txt`. Sync precisa
ser disparado via CLI enquanto não corrigido.

---

## 7. Plano de expansão ETL — dimensões e métricas novas

> Criado em 2026-06-08, roadmap de intenção para o pipeline de **entrega** (MS/MGID), não o
> IO Plan em si. Nomes de tabela abaixo são do schema anterior ao rebuild — **os itens #4 e #5
> já foram implementados no rebuild** com nomes atualizados (`raw.ms_delivery_by_device`,
> `raw.mg_delivery_by_device`, `raw.ms_delivery_by_geo`, `raw.mg_delivery_by_geo`, mais
> `*_by_hour` que nem estava no escopo original) — confirmado contra `INDEX.md`/`raw_layer_design.md`,
> validados em produção 2026-06-24. Os demais itens (#1, #2, #3, #6, #7/#7b) não têm confirmação
> de status pós-rebuild — tratar como ainda abertos até verificar.

**Princípio de arquitetura:** cada novo grupo de dimensão vira um job separado com tabela raw
própria. Não adicionar dimensões ao job principal — multiplica linhas e piora timeout.

| # | O que | Plataforma | Esforço | Depende de | Status (à época) |
|---|---|---|---|---|---|
| 1 | Corrigir timeout job principal | MediaSmart | Alto | Shiro | 🔴 Em aberto |
| 2 | Adicionar métricas financeiras | MGID | Baixo — mesmo call | Shiro | 🟡 Planejado |
| 3 | Surfar criativos ao gold | MediaSmart | Baixo — dado já existe | Douglas | 🟡 Planejado |
| 4 | Job device breakdown | MS + MGID | Médio — job novo | Shiro | ✅ implementado no rebuild |
| 5 | Job geo breakdown | MS + MGID | Médio — job novo | Shiro | ✅ implementado no rebuild |
| 6 | Métricas avançadas (viewability, ROAS, CPA) | MGID | Baixo — mesmo call | Shiro | ⚪ Futuro |
| 7 | Negociar device/spend com Siprocal | Siprocal | Comercial | Decisão comercial | ⚪ Futuro |

### #1 — Corrigir timeout MediaSmart (job `mediasmart_daily_daily`)

**Problema:** chamada única com range longo → timeout da API.
**Solução proposta:** quebrar em janelas de 7 dias por request, iterar sequencialmente no
orchestrator — mesmo endpoint/schema, só muda o range.
**Workaround ativo (à época):** `stg.mediasmart_delivery` fazia UNION com `raw.mediasmart_daily`
para cobrir o gap.

### #2 — Métricas financeiras MGID (mesmo call, zero custo extra)

Adicionar ao job `mgid_daily_daily` existente: `spent, cpc, vCpm, viewability, roas`.

```sql
spent       FLOAT64,   -- investimento realizado
cpc         FLOAT64,   -- custo por clique
vcpm        FLOAT64,   -- CPM viewable
viewability FLOAT64,   -- % impressões viewable
roas        FLOAT64    -- retorno sobre investimento (se pixel com valor)
```

`spent` já havia sido backfillado parcialmente em 2026-06-03 — confirmar se já está no call
atual pós-rebuild ou se precisa ser readicionado.

### #3 — Surfar criativos MediaSmart ao gold (só pipeline, sem novo call)

Dado já existe em `raw.mediasmart_daily` (à época): `creative_type`, `creative_id`, `size`,
`nativesize`, `client_cost`, `video_start/25/50/75/completion`.

Proposta: adicionar campos a `stg.mediasmart_delivery` + criar `gold.dim_creative_mediasmart`
ou adicionar ao `gold.fact_delivery`. Tabela sugerida: `gold.fact_delivery_detail` com grain
`day + client_id + platform + strategy + creative_type + size`.

### #4/#5 — Device e geo breakdown (implementados no rebuild)

**MediaSmart (device):** endpoint `/api/analytics/custom-report`, drilldown
`day,eventid,strategyid,devicetype`, KPIs `impressions,clicks,wonprice`, janela recomendada 7
dias/chamada.

**MGID (device):** endpoint `/v1/goodhits/clients/{id}/statistics-reports`, dimensions
`day`, `campaignId`, `deviceType` (limite de 3), métricas `impressions`, `clicks`, `spent`,
paginação 1.000 linhas/página, range máximo 90 dias/chamada.

**MediaSmart (geo):** drilldown `day,eventid,strategyid,countrycode`.
**MGID (geo):** dimensions `day`, `campaignId`, `country`, mesmas restrições de paginação.

Tabelas gold propostas à época (`gold.fact_delivery_by_device`, `gold.fact_delivery_by_geo`,
grain `day + client_id + platform + device_type/country_code + impressions/clicks/spend`) —
conferir contra o design real pós-rebuild em `gold_layer_design.md`.

### #6 — Métricas avançadas MGID (viewability, ROAS, CPA)

Adicionar ao call de métricas do #2: `conversionsCostInterest`, `conversionsCostDecision`,
`conversionsCostBuy`, `conversionsRateInterest`, `conversionsRateDecision`,
`conversionsRateBuy`. Pré-requisito: cliente com pixel de conversão com valor monetário.

### #7b — Publisher breakdown MediaSmart (no radar — 2026-06-11)

Dado disponível na API — drilldown variables: `publishercompany`, `publisherurl`,
`publisherid`, `exchange`, `domain`. Job sugerido: `raw.mediasmart_delivery_by_publisher`,
drilldown `day,eventid,controlid,publishercompany,publisherurl,exchange`, KPIs
`impressions,clicks,wonprice`. Atenção: dado volumoso (centenas de publishers/campanha/dia) —
usar janela de 7 dias como no job de device. Gold resultante:
`gold.fact_delivery_by_publisher`.

### #7 — Siprocal — negociação comercial

Solicitar à Siprocal inclusão no export BQ: `spend` (custo por day+campaign_id), `device_type`
(desktop/mobile/tablet), `country_code`. Não é mudança técnica nossa — solicitação via
relacionamento comercial.

---

## 8. Pacing Cora/TecPar — mapeamento plano × delivery

> Análise feita em 2026-06-15 sobre o schema de delivery anterior ao reset de 2026-06-16. A
> **lógica de pacing (plano vs delivery) permanece válida como referência de negócio** — nomes
> de tabela/coluna de delivery citados abaixo precisam ser revisados contra o schema atual
> antes de implementar.

**Objetivo original:** conectar dados de plano (`stg.io_plan_drive`, hoje `stg.io_plan`) com
dados de entrega das 3 plataformas para construir a STG de pacing. Escopo RAW→STG; Gold e
dashboard viriam depois.

### 8.1 Cora (`banco_cora_fe13d78a`) — delivery por plataforma

**MediaSmart** — `ms_client_id = cora_2ruu4won`, 3 campanhas ativas Jan→Jun/26:

| ms_campaign_name | category | 2026 imp | 2026 clk |
|---|---|---|---|
| CORA_CONTADIGITAL_DISPLAY_JUNHO26 | DISPLAY | 4.051.370 | 7.591 |
| CORA_CONTADIGITAL_VIDEO_JUNHO26 | VIDEO | 4.260.116 | 18.079 |
| CORA_CONTADIGITAL_RETARGETING_JUNHO26 | RETARGETING | 5.863.986 | 10.311 |

Mapeamento category→campanha via `LIKE '%DISPLAY%'` / `'%VIDEO%'` / `'%RETARGETING%'` no nome.

**MGID** — `mgid_client_id = banco_cora_fe13d78a`, 7 campanhas (1 por período), todas NATIVE
(100%). Campanha `12437129` (Jun/Jul) tinha `mgid_client_id = NULL` na tabela de campanhas —
bug conhecido de registros MGID novos chegando sem client_id no RAW (join adicional via
`campaign_id IN (12437129)` necessário para essa).

**Siprocal** — `siprocal_client_id = banco_cora_fe13d78a`, 5 campanhas (1 por mês), todas
PUSH (100%).

### 8.2 TecPar (`tecpar_edfcc744`) — delivery por plataforma

**MediaSmart** — `ms_client_id = tec_par_oqdfn8xx`, 3 campanhas ativas: `AMIGO_DISPLAY_700_ABRIL26`,
`AMIGO_DISPLAY_JUNHO26` (ambas DISPLAY, ativas simultaneamente — precisa agrupamento),
`AMIGO_RETARGETING_JUNHO26` (RETARGETING). Nome "AMIGO_" reflete que o produto veiculado é da
marca Amigo (sub-cliente de TecPar) rodando na conta MS da TecPar — conta única
`tec_par_oqdfn8xx`, não existe `ms_client_id` separado para Amigo.

**MGID — gap crítico (não é bug de ingestão).** TecPar não tem nenhuma campanha em
`raw.mgid_campaigns`. Diagnóstico 2026-06-15: varredura completa das 47 campanhas MGID 2026 na
RAW deu zero resultado para TecPar; `stg.mgid_campaigns` resolve `mgid_client_id` via
`core.platform_client_links` e TecPar está ausente dessa tabela; o conector MGID ingere uma
única conta NewAd Brazil e campanhas TecPar não estão nela. Campanhas com `mgid_client_id NULL`
eram Einstein, Amigo/Brand, Senar, Stoquinho, Cora — nenhuma TecPar. Causa provável: TecPar
roda NATIVE em conta MGID separada (fora do conector) ou noutra plataforma de Native Ads não
integrada. Ações pendentes: confirmar com Shiro/operações se existe conta MGID própria da
TecPar, ou identificar a plataforma real de Native — sem resposta, pacing NATIVE de TecPar
fica NULL.

**Siprocal — split de client_id por período.** TecPar tem dois client_ids conforme o período:

| período | siprocal_client_id | advertiser_key | campanhas |
|---|---|---|---|
| Jan-Mar 2026 | `tecpar_edfcc744` | TECPAR | NEWAD_TECPAR_BR_JAN26/FEV26/MAR26 |
| Abr-Jun 2026 | `amigo_db1c2f0c` | AMIGOTECPAR | NEWAD_AMIGOTECPAR_BR_ABR26/MAI26/JUN26 |

A partir de Abril/2026 as campanhas Siprocal de TecPar passaram a rodar sob `amigo_db1c2f0c`
(Amigo é sub-cliente legítimo de TecPar, confirmado). Join necessário:
```sql
(siprocal_client_id = 'tecpar_edfcc744')
OR
(siprocal_client_id = 'amigo_db1c2f0c' AND advertiser_key = 'AMIGOTECPAR')
```

### 8.3 Mapa consolidado de linkage (status à época, 2026-06-15)

**Cora:** DISPLAY/VIDEO/RETARGETING (mediasmart) ✅ pronto · NATIVE (mgid) ✅ pronto com
ressalva Jun · PUSH (siprocal) ✅ pronto.

**TecPar:** DISPLAY/RETARGETING (mediasmart) ✅ pronto · NATIVE (mgid) ❌ bloqueado
(client_id desconhecido) · PUSH (siprocal) ⚠️ requer UNION/CASE pelo split acima.

### 8.4 Design STG proposto (até STG — gold ficaria depois)

**Próxima view especificada:** `stg.delivery_by_category` — unifica entrega das 3 plataformas
no grain `client_id × platform × category × day`, métricas `impressions`/`clicks`/`spend`
(SUM). Regras de fonte por cliente/plataforma reproduzem o §8.1/8.2 acima.

**Não criar até:** (1) resolver `mgid_client_id` de TecPar ou decidir entregar sem NATIVE; (2)
confirmar se TecPar DISPLAY do MS é só Amigo/sub-cliente ou inclui TecPar direto; (3) decidir
se a STG cobre só 2026 ou todo o histórico.

### 8.5 Issues abertos (à época da análise)

| # | issue | quem resolve | urgência |
|---|---|---|---|
| L1 | TecPar MGID client_id não encontrado no BQ | Shiro / verificar conector | alta |
| L2 | Cora MGID campanha Jun/Jul (12437129) com client_id = NULL | pipeline MGID fix | média |
| L3 | TecPar PUSH Siprocal split Jan-Mar vs Abr-Jun (dois client_ids) | tratar no join STG | alta |
| L4 | TecPar DISPLAY tem 2 campanhas MS simultâneas | agrupar por client+category | baixa |
| L5 | Cora FEVEREIRO 2026 iniciou 02-02 (não 02-01) | verificar se plano começa no dia 1 | baixa |

---

## 9. Auditoria de qualidade Cora/TecPar (2026-06-15/16)

> Registro do trabalho de auditoria e correção do parser `sync_drive.py` que antecedeu o
> rebuild de schema de 2026-06-16. Contém achados de dado real e mudanças de código
> efetivamente implementadas — preservado porque documenta bugs reais e suas correções, não
> apenas investigação especulativa.

### 9.1 Contexto e reset de 2026-06-15

A sessão de 2026-06-15 fez reset completo de `raw.io_plan_drive_snapshot` (DROP + CREATE +
re-sync `--force`) para eliminar acúmulo histórico de versões duplicadas. Regras de seleção
implementadas no commit `ff9dfe2`: ignora arquivos com token de pessoa (RAFA, GESSIANE) se
existir oficial; fallback para o mais recente com nome de pessoa se só houver esses; 1 arquivo
por pasta PLANO (mais recente por `modifiedTime`).

### 9.2 Achados Drive — Cora

12 arquivos encontrados por `find_plano_files`, cobrindo 2025 (8 arquivos históricos, um deles
`AGOSTO V2 RAFA` sem versão oficial) e 2026 (plano anual `CORA 2026 V2` com 69 estratégias +
arquivos mensais ABR e MAI-AGO). Problemas: (1) duplicação MAI-AGO/26 — dois Drive IDs
diferentes com conteúdo idêntico (`Plano NEWAD_CORA MAIO JUNHO JULHO V3` com espaços vs
`Plano_NEWAD_CORA_MAIO_JUNHO_JULHO_V3` com underscores), cada período aparecendo em dobro na
raw; (2) plano anual 2026 V2 sobrepõe os mesmos meses dos arquivos mensais ABR/MAI-AGO.

Total raw Cora pós-reset: 237 rows, 12 arquivos, 77% sem datas.

### 9.3 Achados Drive — TecPar/AMIGO

9 arquivos (1 skipped: PI da Siprocal, formato diferente, 0 rows parseados). Problemas: (1)
arquivo de JANEIRO copiado nas pastas FEVEREIRO e MARÇO/2026 (placeholder sem plano próprio);
(2) arquivo de JULHO/2025 copiado nas pastas AGOSTO e SETEMBRO/2025; (3) JUNHO/2026 só tinha
versão RAFA, sem oficial.

Total raw TecPar pós-reset: 35 rows, 7 arquivos, 100% sem datas. Anomalia de valor:
ABRIL/MAIO 2026 R$60.000/mês vs ~R$12.700/mês nos meses anteriores — verificado depois que
era replanejamento real de comercial, não bug.

### 9.4 Estratégias → plataforma (achados de vocabulário)

**Cora:** a maioria mapeia limpo (`Mídia Progarmática - Display` [sic, typo recorrente em
todos os clientes] → mediasmart, `Native Ads - Contextual` → mgid), mas ficam `unknown`:
`Push - APPTARGETING`, `Push`, `Push - Household Sync CTV`, `AppInstall - Download`,
`AppInstall - Abertura de Conta`, `APP INSTALL`, `Rich Media`, `CTV Household sync`,
`Whatsapp Marketing`.

**TecPar:** achado importante — a nomenclatura já inclui a plataforma no nome da estratégia em
alguns casos (`Push - App Targeting SIPROCAL` → siprocal explícito, `Push - MGID` → mgid
explícito), diferente de Cora. `Push - App Targeting` (sem sufixo) fica `unknown`.

### 9.5 Perguntas levantadas ao comercial (à época)

| # | Pergunta | Cliente | Impacto |
|---|---|---|---|
| 1 | Uma estratégia do plano = uma campanha na plataforma, ou pode haver várias? | Ambos | Alto — cardinalidade do join |
| 2 | Nomes de campanha nas plataformas seguem padrão relacionado ao IO plan? | Ambos | Alto |
| 3 | "Push" da Cora é MediaSmart ou Siprocal? E "Push - APPTARGETING"? | Cora | Médio |
| 4 | "AppInstall - Download/Abertura de Conta" — qual plataforma? | Cora | Médio |
| 5 | "Rich Media", "CTV Household sync", "Whatsapp Marketing" — qual vendor? | Cora | Baixo |
| 6 | Plano ABR/MAI 2026 do AMIGO/TecPar em R$60K — é replanejamento? | TecPar | Médio (✅ confirmado que sim) |
| 7 | Existe plano oficial de FEV/MAR para TecPar? | TecPar | Médio |

### 9.6 Descoberta crítica — padrão de abas trimestrais (sessão 2026-06-16)

Rafael confirmou o padrão geral dos arquivos xlsx da Cora: arquivos anuais/trimestrais têm 4
abas — `"JAN A MAR"`, `"ABR A JUN"`, `"JUL A SET"`, `"OUT A DEZ"` — cada pasta de mês usa
apenas a aba do trimestre correspondente, sem dia no label (datas derivadas do
`drive_folder`). O arquivo V3 é exceção: usa abas por intervalo com dias
(`"1 MAI A 10 MAI"`, `"11 MAI A 10 JUN"`) e já era lido corretamente.

**Bug raiz do parser (L1):** `parse_xlsx` (linha 257) iterava `wb.sheetnames` sem filtrar pelo
mês do `drive_folder` — para um arquivo com 4 abas trimestrais, concatenava as 4 e multiplicava
por 4 o número de rows. Evidência: `CORA 2026 V2` em `2026/JANEIRO` gerava 23 rows (4 abas ×
~6) em vez das 6 corretas da aba `"JAN A MAR"` — mesmo erro em FEV, MAR e nos arquivos
históricos de 2025.

### 9.7 Correções implementadas em `sync_drive.py`

**Mudança 1 — `import calendar`** (linha ~28): necessário para calcular o último dia do mês em
`_dates_from_drive_path`.

**Mudança 2 — `SKIP_SHEETS`** (linha ~104): adicionado `SUGESTOES`/`SUGESTÕES` — a Cora 2026
tem aba `"SUGESTÕES"` que não estava sendo ignorada.

**Mudança 3 — helper `_find_quarterly_tab`** (novo):
```python
def _find_quarterly_tab(wb, target_month: int) -> Optional[str]:
    """Acha aba 'PLANO JAN A MAR' / 'PLANO ABR A JUN' / 'PLANO JUL A DEZ' para o mês."""
    for name in wb.sheetnames:
        upper = _deaccent(name).upper().strip()
        m = re.search(r"\b([A-Z]{3})\s+A\s+([A-Z]{3})\b", upper)
        if m:
            s = MONTH_PT.get(m.group(1))
            e = MONTH_PT.get(m.group(2))
            if s and e and s <= target_month <= e:
                return name
    return None
```
O regex encontra o padrão em qualquer parte do nome da aba (não só no início) — necessário
porque os arquivos de 2026 têm o prefixo `"PLANO"` antes do intervalo.

**Mudança 4 — helper `_dates_from_drive_path`** (novo):
```python
def _dates_from_drive_path(drive_path: str):
    """'2026/JANEIRO' → (date(2026,1,1), date(2026,1,31))"""
    parts = (drive_path or "").upper().split("/")
    year = int(parts[0]) if parts[0].isdigit() else None
    month = MONTH_PT.get(_deaccent(parts[1]).upper()) if len(parts) > 1 else None
    if not year or not month:
        return None, None
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return start, end
```
Abas trimestrais não têm dia no nome, então `parse_flight_label` retornava `(None, None)` —
as datas corretas são sempre o primeiro/último dia do mês do `drive_folder`.

**Mudança 5 — `parse_xlsx`: seleção de aba e datas no loop principal.** Antes iterava
`wb.sheetnames` direto (datas sempre None para trimestrais). Depois: acha `quarterly_tab` via
Mudança 3; se achou, processa só essa aba com datas de `_dates_from_drive_path`; se não achou,
mantém o comportamento anterior (itera todas, parseia do nome da aba).

**Mudança 6 — filtro V3 por mês:**
```python
if target_month and flight_start and flight_start.month != target_month:
    continue
```
Arquivos multi-mês como o V3 (MAIO-JUL/26) têm abas para múltiplos meses — sem esse filtro a
pasta `2026/MAIO` ingeria todos os 5 períodos (MAI→AGO). Regra de negócio: pasta no Drive =
plano oficial daquele mês; cada pasta ingere só os períodos que **começam** no seu mês
(período que cruza meses pertence ao mês de início). Efeito colateral positivo: resolve
também o problema do V3 duplicado, já que cada arquivo passa a ler só o mês da sua pasta.

**Mudança 7 — fallback `drive_folder` para arquivos com aba única sem data** (TecPar):
```python
if flight_start is None and target_month:
    flight_start, flight_end = _dates_from_drive_path(drive_path)
```
Arquivos TecPar têm 1 aba com nome genérico sem datas (`"PLANO CUIABÁ"`, `"ABRIL"`, `"MAIO"`)
— sem esse fallback todas as linhas ficavam SEM_DATA. Regra de negócio confirmada (Douglas,
2026-06-16): **"Se está na pasta é o arquivo do mês"** — o nome da aba não importa, mesmo um
arquivo com aba chamada "MAIO" na pasta JUNHO usa datas de JUNHO. Seguro para Cora porque
V2 2026 entra pelo caminho `quarterly_tab` (nunca chega no fallback) e V3 já tem
`flight_start` populado pelo day-range.

### 9.8 Resultado das correções

**Cora 2026** — todos os meses com arquivo próprio corretos na raw pós-fix: JAN/FEV/MAR com
6 rows cada (R$35.000/mês), ABR com 6 rows (R$70.000), MAIO com 27 rows/5 períodos
(R$182.500, arquivo V3 espaços), JUNHO com 27 rows/5 períodos (mesmo V3, mas com underscores —
ainda duplicata de arquivo a resolver no Drive). Meses JUL–DEZ/26 cobertos pelos períodos do
V3 (até 2026-08-31); SET–DEZ/26 sem pasta ainda no Drive.

Confirmado pelo Douglas (2026-06-16): campo `PERÍODO` do xlsx mostrando `"30 dias"` = plano
para o mês completo; `flight_start`/`flight_end` = primeiro/último dia do mês do
`drive_folder`; R$35k/mês (JAN-MAR) e R$70k (ABR) são valores corretos de decisão comercial,
não erro de dado; linha `TOTAL` do xlsx não entra na raw (parser faz `break` ao ver "TOTAL"
em qualquer célula da linha).

**TecPar** — parser 100% resolvido, zero SEM_DATA pós-fix. Problemas restantes eram
organizacionais no Drive (arquivo errado nas pastas FEV/MAR/AGO/SET), não bugs de código.

### 9.9 Regra de negócio consolidada — "pasta Drive = plano oficial"

> "Pasta no Drive = plano oficial para aquele mês. Sem pasta = sem plano = sem dado."

Confirmado pelo Douglas em 2026-06-16 — o Drive é a fonte de verdade sobre quais meses têm
plano aprovado.

### 9.10 Decisão de arquitetura — camadas para cálculo diário

Decidido em 2026-06-16:

| Camada | Responsabilidade |
|---|---|
| RAW (parser) | Seleciona aba correta + popula `flight_start`/`flight_end` do `drive_folder` quando aba é trimestral |
| STG | Limpa, deduplica, filtra sobreposições (ex: V3 em MAIO → só períodos de MAIO), garante NOT NULL em datas |
| Gold (view) | `GENERATE_DATE_ARRAY(flight_start, flight_end)` → `daily_spend = monthly_spend / dias_do_período` |

O cálculo diário não vai para a STG — é view analítica no Gold. A STG expõe uma linha limpa
por estratégia × período.

### 9.11 Pendência conhecida — arquivos 2025 (não implementado)

Decisão tomada em 2026-06-16: **não implementar fix para 2025** naquele momento — prioridade
era entregar 2026 correto. Arquivos de 2025 usam convenção de abas diferente (nome de mês sem
intervalo, ex: `"PLANO ABRIL"`, `"PLANO JUN E JUL"`), que o parser trimestral não reconhece —
lê todas as abas, rows inflados (ex: `2025/ABRIL` com 40 rows em vez de ~5-6). Um terceiro
helper `_find_monthly_tab` foi especificado (não implementado) para reconhecer abas por nome
de mês, aceitar multi-mês (`"JUN E JUL"`), separadores variados (espaço/`|`/`E`/`&`/`a`), e
excluir abas com dígitos (day-range). A STG de 2026 deveria filtrar
`drive_folder LIKE '2026/%'` até esse fix estar pronto. **Status atual desconhecido** — não
confirmado se foi retomado após o rebuild de schema.

### 9.12 Problemas de organização do Drive (fora do código, ação comercial)

| Problema | Cliente | Ação necessária |
|---|---|---|
| Arquivo de JANEIRO copiado em FEV e MAR 2026 | TecPar | Remover cópias ou colocar planos corretos |
| Arquivo de JULHO 2025 copiado em AGO e SET | TecPar | Remover cópia de SET |
| 2 versões do arquivo MAI-JUL 2026 (espaços vs underscore) | Cora | Manter só 1 no Drive |
| Pastas FEV e MAR 2026 sem plano próprio | TecPar | Criar planos ou confirmar inexistência |

Nota de reestruturação registrada para revisão futura com o comercial: o Drive depende de
disciplina manual para colocar o arquivo certo na pasta certa — qualquer erro entra
silenciosamente na raw com datas erradas, sem validação automática. Opções discutidas: naming
convention obrigatória (`CLIENTE_AAAA_MM.xlsx`) com validação nome vs pasta; alerta quando
`source_file` não menciona o mês da pasta; formulário centralizado de upload.

---

## 10. Design futuro — linkage plano × campanha (V2, não implementado)

> Discutido em 2026-06-16. Registrado para desenho futuro, não implementado.

### 10.1 Problema que resolve

Hoje a Luckbet tem uma Google Sheet ("PIs") preenchida manualmente pela Gessiane
(`id | Mês | Cliente | Plataforma | Estratégia | Início | Fim | Investimento | id_Campanha`).
Replicar isso por cliente não escala.

### 10.2 Fluxo proposto

```
1. ETL roda (MediaSmart/MGID/Siprocal → BQ)
2. BQ detecta campaigns sem vínculo com linha do plano
3. Pipeline gera Google Form pré-preenchido com campanhas não vinculadas:
   client_id, plataforma, campaign_id, campaign_name, período ativo, spend no período
4. Comercial (Gessiane) preenche: qual linha do plano (plan_line_id) + % de split de verba
5. Respostas do Form → BQ → tabela bridge
6. Gold faz JOIN: io_plan × bridge × performance por campanha
```
Futuro: quando o Admin UI do Shiro estiver no ar, o Form é substituído pela interface própria.

### 10.3 Dependências a criar

| # | O que criar | Onde | Bloqueador? |
|---|---|---|---|
| 1 | `plan_line_id` estável por linha da raw | `raw.io_plan_drive_snapshot` | Sim |
| 2 | Lógica de ID estável (hash) no parser | `sync_drive.py` | Sim |
| 3 | Tabela bridge `core.io_plan_campaign_map` | BQ | Sim |
| 4 | Google Form com campos padronizados | Google Forms | Sim |
| 5 | Script de geração do Form | pipeline | Sim |
| 6 | Script de ingestão das respostas | pipeline | Sim |
| 7 | Lógica de split de verba | STG/Gold | — |

### 10.4 Complexidades identificadas

**Split de verba** (1 linha do plano → N campanhas): comercial define a % no momento do
mapeamento (ex: campanha A 70%/B 30% de uma linha de R$70k → R$49k/R$21k) — split armazenado
na bridge table.

**Siprocal — IDs não reais:** na planilha da Luckbet o ID Siprocal é `siprocal-pushapp`
(placeholder, não ID real da API) — join com performance real da Siprocal falharia, resolver
separadamente via lógica BQ. Não bloqueia o design do Form para as outras plataformas.

**Timing:** campanhas precisam existir nas plataformas antes do Form ser gerado (fluxo: plano
aprovado → Gessiane cria campanhas → ETL roda → Form gerado → Gessiane preenche).

**`plan_line_id` estável:** precisa sobreviver a re-ingestão (DROP+CREATE) — usar hash
determinístico `MD5(client_id || drive_folder || strategy_name)`.

### 10.5 Schema proposto: `core.io_plan_campaign_map`

```sql
CREATE TABLE core.io_plan_campaign_map (
  plan_line_id     STRING NOT NULL,  -- hash(client_id+drive_folder+strategy_name)
  client_id        STRING NOT NULL,
  platform         STRING NOT NULL,  -- mediasmart / mgid / siprocal
  campaign_id      STRING NOT NULL,  -- ID real da plataforma
  spend_pct        FLOAT64,          -- % do monthly_spend desta linha alocado a esta campanha
  valid_from       DATE,             -- início da validade deste mapeamento
  valid_to         DATE,             -- fim (NULL = ativo)
  filled_by        STRING,           -- quem preencheu (Gessiane / Rafa)
  filled_at        TIMESTAMP
);
```

### 10.6 Abordagem "gambiarra" usada para a entrega de 2026 (Cora)

Em vez de linkage campaign-level, usou-se **category-level** conforme mapeamento do Rafa na
planilha de performance:

| IO plan strategy_name | Categoria | Plataforma |
|---|---|---|
| Mídia Progarmática - Display | DISPLAY | mediasmart |
| Vídeo Ads | VIDEO | mediasmart |
| Retargeting Display - 1st party | RETARGETING | mediasmart |
| Retargeting Display - VIEW | RETARGETING | mediasmart |
| Native Ads - Contextual | NATIVE | mgid |
| Push - APPTARGETING | PUSH | siprocal |

Gold view: JOIN io_plan × performance agregada por categoria × período — sem exigir
campaign_ids individuais. Fonte cruzada: planilha do Rafa
(`spreadsheet_id: 1Y94CavDyMXnIy9sLyqcTP8yKdANiQ1j1RzZBzHi7YHk`), 12 abas de dashboard
plano vs realizado por dia, já agregada por categoria.

**Confirmado no BQ (2026-06-16)** que o vínculo por categoria é possível para Cora 2026 nas 3
plataformas sem mapeamento manual adicional: MediaSmart via keyword no `ms_campaign_name`
(DISPLAY/VIDEO/RETARGETING); MGID via `mgid_client_id = 'banco_cora_fe13d78a'` → todas NATIVE;
Siprocal via `client_id = 'banco_cora_fe13d78a'` → todas PUSH. Nota: as duas linhas de
Retargeting do IO plan mapeiam para a mesma campanha MediaSmart — somar ambas do lado do plano
antes de comparar com o total real da campanha RETARGETING.

---

## 11. Mapa de arquivos e próximos passos

### 11.1 Mapa de arquivos

| Arquivo | Descrição |
|---|---|
| `scripts/io_plan/sync_drive.py` | Script principal: `CLIENT_MAP`, `PERSONAL_NAME_TOKENS`, `find_plano_files`, `parse_xlsx`, `rebuild_core_for_client` |
| `services/io-plan-admin/main.py` | Cloud Run FastAPI — `POST /sync` |
| `services/io-plan-admin/requirements.txt` | ⚠️ Falta `python-multipart` (L6) |
| `raw/ddl/io_plan_drive_snapshot.sql` | DDL canônico da tabela raw (21 campos) |
| `stg/ddl/io_plan.sql` | DDL da STG atual |
| `docs/io_plan_domain.md` | Este documento |

### 11.2 Próximos passos consolidados (status desconhecido pós-rebuild — reconferir antes de agir)

1. Fix `python-multipart` em `services/io-plan-admin/requirements.txt` e redeploy (L6).
2. Primeiro sync completo dos 12 clientes novos (Aperam, Catálise, Daxx, Dooing, Einstein,
   Luckbet, Mopar, MRV, Ocupacional, Patio Medeiros, Stocco, 7K).
3. Resolver `LABTOLAB PARDINI` (`pardini_60395024`, `lab2lab_efb1cb34` ou ambos) e cadastrar
   `PHISALIA` em `dim_client` quando houver clareza.
4. Implementar `_find_monthly_tab` para corrigir parsing dos arquivos 2025 (§9.11).
5. Avaliar se `core.io_plan_manual`/`gold.fact_io_plan` devem ganhar grain de estratégia
   (hoje só `stg.io_plan` tem).
6. Retomar o design de linkage plano×campanha V2 (§10) quando houver bandwidth — hoje só
   especificado, não implementado.
7. Resolver o gap MGID de TecPar (§8.2) — depende de resposta de Shiro/operações sobre conta
   MGID própria ou plataforma alternativa de Native.
8. Revisar toda a cadeia RAW→STG→Core→Gold do IO Plan contra o schema pós-rebuild de
   2026-06-16 — nenhuma tabela de delivery (MS/MGID/Siprocal) citada nas seções de pacing e
   auditoria (§8, §9) foi reconfirmada depois do rebuild.
