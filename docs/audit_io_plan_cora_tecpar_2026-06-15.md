# Auditoria IO Plan — Cora & TecPar/AMIGO

---
> **📋 REESTRUTURAÇÃO EM ANDAMENTO — 2026-06-16**
> Auditoria feita sobre o estado do BQ em 2026-06-15, um dia antes do reset.
> A parte de IO Plan (`raw.io_plan_drive_snapshot`, `gold.fact_io_plan`) permanece válida.
> A parte de delivery referencias tabelas antigas — valide antes de usar. Plano: [bq_restructuring_plan.md](bq_restructuring_plan.md)
---
**Data:** 2026-06-15  
**Objetivo:** Registrar o estado atual da ingestão de planos no Drive e na raw BQ, documentar problemas encontrados e planejar a conexão plano → campanha por cliente.

---

## Contexto

O pipeline de planos percorre `CLIENT/ANO/MES/PLANO/` no Google Drive e ingere arquivos `.xlsx` de cada pasta em `raw.io_plan_drive_snapshot`. A sessão de 2026-06-15 fez um **reset completo** da tabela (DROP + CREATE + re-sync `--force`) para eliminar acúmulo histórico de versões duplicadas.

Regras de seleção implementadas (commit `ff9dfe2`):
- Por pasta PLANO: ignora arquivos com token de pessoa (RAFA, GESSIANE) se existir arquivo oficial
- Fallback: se só houver arquivo com nome de pessoa, pega o mais recente
- Entre múltiplos candidatos: sempre só **1 arquivo por pasta** (mais recente por `modifiedTime`)

---

## 1. CORA (`banco_cora_fe13d78a`)

### 1.1 Drive — Estrutura e Achados

**Arquivos encontrados por `find_plano_files`: 12**

| Drive path | Arquivo | Período inferido | Tipo |
|---|---|---|---|
| 2025/FEV | `Plano NEWAD_CORA_17FEV2025_V2.xlsx` | Fev 2025 | Histórico 2025 |
| 2025/MAI | `Plano NEWAD_CORA_13MAIO25_V4.xlsx` | Mai 2025 | Histórico 2025 |
| 2025/MAI v2 | `Plano NEWAD_CORA_30MAIO25_V4.xlsx` | Mai 2025 | Histórico 2025 |
| 2025/JUL | `Plano NEWAD_CORA_02JUL25.xlsx` | Jul 2025 | Histórico 2025 |
| 2025/AGO | `Plano NEWAD RAFA_CORA AGOSTO V2_06AGO25.xlsx` | Ago 2025 | Histórico RAFA (sem oficial) |
| 2025/SET | `Plano NEWAD_CORA SETEMBRO_29AGO25_APROVADO.xlsx` | Set 2025 | Histórico 2025 |
| 2025/SET-DEZ | `Plano NEWAD_CORA BONIF OUT&NOV_15SET25_APROVADO.xlsx` | Out-Nov 2025 | Histórico bonificação |
| 2025/OUT-DEZ | `Plano NEWAD_CORA BONIF OUT NOV DEZ_31OUT25.xlsx` | Out-Dez 2025 | Histórico bonificação |
| 2026/JAN-DEZ | `Plano NEWAD_CORA 2026 V2_05 01 26_APROVADOS_06 01 26.xlsx` | **Plano anual 2026** | 69 estratégias, todos os meses |
| 2026/ABR | `Plano NEWAD_CORA ABRIL_APROVADOS_31 03 26.xlsx` | Abr 2026 | Official ✅ |
| 2026/MAI-AGO (v1) | `Plano NEWAD_CORA MAIO JUNHO JULHO V3_08 05 26.xlsx` | Mai-Ago 2026 | Official, mod 2026-05-11 |
| 2026/MAI-AGO (v2) | `Plano_NEWAD_CORA_MAIO_JUNHO_JULHO_V3_08_05_26.xlsx` | Mai-Ago 2026 | **⚠️ MESMO conteúdo, nome com underscores, mod 2026-06-11** |

**Problemas no Drive — Cora:**

1. **Duplicação MAI-AGO 2026**: dois arquivos com conteúdo idêntico em pastas diferentes — `Plano NEWAD_CORA MAIO JUNHO JULHO V3` (espaços) e `Plano_NEWAD_CORA_MAIO_JUNHO_JULHO_V3` (underscores). São Drive IDs diferentes por isso ambos passam pelo `seen_file_ids`. Cada período (Mai1-10, Mai11-Jun10, Jun11-Jul10, Jul11-Ago10, Ago11-31) aparece **em dobro** na raw.

2. **Plano anual 2026 V2 cobre os mesmos meses**: o arquivo de jan-dez 2026 (69 estratégias, R$1.065M total) cobre o mesmo período que os arquivos mensais de ABR e MAI-AGO. Isso cria sobreposição de dados para 2026.

3. **8 arquivos históricos de 2025 ainda no Drive**: cada um em sua própria pasta de mês, todos ingeridos. São dados legítimos mas ocupam espaço e distorcem totais se não filtrados por período.

4. **Agosto 2025 só tem RAFA**: sem arquivo oficial para AGO 2025.

### 1.2 BQ Raw — Estado Atual

**Tabela `raw.io_plan_drive_snapshot` — Cora após re-sync:**

| Arquivo | Período (parsed) | Estratégias | Spend | Status |
|---|---|---|---|---|
| `Plano NEWAD_CORA MAIO JUNHO JULHO V3` | 2026-05-01→05-10 | 6 | R$12.500 | ✅ |
| `Plano_NEWAD_CORA_MAIO_JUNHO_JULHO_V3` | 2026-05-01→05-10 | 6 | R$12.500 | ⚠️ duplicata |
| `Plano NEWAD_CORA MAIO JUNHO JULHO V3` | 2026-05-11→06-10 | 5 | R$78.750 | ✅ |
| `Plano_NEWAD_CORA_MAIO_JUNHO_JULHO_V3` | 2026-05-11→06-10 | 5 | R$78.750 | ⚠️ duplicata |
| `Plano NEWAD_CORA MAIO JUNHO JULHO V3` | 2026-06-11→07-10 | 5 | R$31.500 | ✅ |
| `Plano_NEWAD_CORA_MAIO_JUNHO_JULHO_V3` | 2026-06-11→07-10 | 5 | R$31.500 | ⚠️ duplicata |
| `Plano NEWAD_CORA MAIO JUNHO JULHO V3` | 2026-07-11→08-10 | 5 | R$47.250 | ✅ |
| `Plano_NEWAD_CORA_MAIO_JUNHO_JULHO_V3` | 2026-07-11→08-10 | 5 | R$47.250 | ⚠️ duplicata |
| `Plano NEWAD_CORA MAIO JUNHO JULHO V3` | 2026-08-11→08-31 | 6 | R$12.500 | ✅ |
| `Plano_NEWAD_CORA_MAIO_JUNHO_JULHO_V3` | 2026-08-11→08-31 | 6 | R$12.500 | ⚠️ duplicata |
| `Plano NEWAD_CORA ABRIL` | SEM DATA | 12 | R$130.000 | ⚠️ sem datas |
| `Plano NEWAD_CORA 2026 V2` | SEM DATA | 69 | R$1.065.000 | ⚠️ sem datas, sobreposição |
| `BONIF OUT&NOV (Set25)` | SEM DATA | 5 | R$60.000 | Histórico |
| `BONIF OUT NOV DEZ (Out25)` | SEM DATA | 5 | R$60.000 | Histórico |
| `CORA SETEMBRO (Ago25)` | SEM DATA | 6 | R$118.001 | Histórico |
| `CORA_02JUL25` | SEM DATA | 7 | R$105.620 | Histórico |
| `CORA_13MAIO25_V4` | SEM DATA | 20 | R$350.000 | Histórico |
| `CORA_17FEV2025_V2` | SEM DATA | 40 | R$450.000 | Histórico |
| `CORA_30MAIO25_V4` | SEM DATA | 13 | R$200.000 | Histórico |
| `CORA AGOSTO V2 RAFA` | SEM DATA | 6 | R$29.574 | Histórico RAFA |

**Total raw Cora: 237 rows, 12 arquivos, 77% sem datas**

**Dados confiáveis para uso imediato (Cora):**
- Mai 1-10: R$12.500 (único arquivo → usar apenas 1 das 2 versões)
- Mai 11-Jun 10: R$78.750 ✅ (valor correto — anteriormente estava R$157.500 por bug)
- Jun 11-Jul 10: R$31.500
- Jul 11-Ago 10: R$47.250
- Ago 11-31: R$12.500

**Dados que precisam de ação antes de usar:**
- ABR 2026: R$130.000 — arquivo no Drive mas datas não parseadas (flight_start = NULL)
- Plano anual 2026 V2: 69 estratégias cobrindo jan-dez — sobreposição com mensais

### 1.3 Estratégias Cora → Mapeamento de Plataforma

| strategy_name | Platform detectada | Observação |
|---|---|---|
| Mídia Progarmática - Display | mediasmart | typo "Progarmática" (recorrente em todos os clientes) |
| Mídia Progarmática - Display - On target | mediasmart | |
| Retargeting Display | mediasmart | |
| Retargeting Display - 1st party | mediasmart | |
| Retargeting Display - VIEW | mediasmart | |
| Vídeo Ads | mediasmart | |
| Native Ads - Contextual | mgid | |
| Push - APPTARGETING | **unknown** | ⚠️ pode ser MediaSmart ou Siprocal |
| Push | **unknown** | ⚠️ idem |
| Push - Household Sync CTV | **unknown** | ⚠️ idem |
| AppInstall - Download | **unknown** | ⚠️ plataforma não identificada |
| AppInstall - Abertura de Conta | **unknown** | ⚠️ plataforma não identificada |
| APP INSTALL | **unknown** | ⚠️ plataforma não identificada |
| Rich Media | **unknown** | ⚠️ plataforma não identificada |
| CTV Household sync | **unknown** | ⚠️ plataforma não identificada |
| Whatsapp Marketing | **unknown** | ⚠️ plataforma não identificada |

---

## 2. TECPAR / AMIGO (`tecpar_edfcc744`)

### 2.1 Drive — Estrutura e Achados

**Arquivos encontrados por `find_plano_files`: 9 (1 skipped = Siprocal PI)**

| Drive path | Arquivo | Período correto? | Tipo |
|---|---|---|---|
| 2025/AGOSTO | `Plano NEWAD_AMIGOCUIABÁ_30_JULHO25_APROVADO_8JUL25.xlsx` | ❌ arquivo de JULHO na pasta AGO | Official |
| 2025/SETEMBRO | `Plano NEWAD_AMIGOCUIABÁ_30_JULHO25_APROVADO_8JUL25 (1).xlsx` | ❌ arquivo de JULHO na pasta SET (cópia) | Official |
| 2025/NOVEMBRO | `PI_Siprocal_NewAd_TECPAR AMIGO NOVEMBRO_29OUT25.xlsx` | — | **Siprocal PI** (skipped, 0 rows parseados) |
| 2026/JANEIRO | `Plano NEWAD RAFA_AMIGOCUIABÁ_JANEIRO_APROVADO_30 12 25.xlsx` | ✅ Jan 2026 | RAFA (sem oficial) |
| 2026/FEVEREIRO | `NEWAD RAFA_AMIGOCUIABÁ_JANEIRO_APROVADO_30 12 25.xlsx` | ❌ **arquivo de JAN na pasta FEV** | RAFA (cópia de JAN) |
| 2026/MARÇO | `Plano NEWAD RAFA_AMIGOCUIABÁ_JANEIRO_APROVADO_30 12 25.xlsx` | ❌ **arquivo de JAN na pasta MAR** | RAFA (cópia de JAN) |
| 2026/ABRIL | `Plano NEWAD_AMIGOCUIABÁ ABRIL 2026_31 03 25.xlsx` | ✅ Abr 2026 | Official |
| 2026/MAIO | `Plano NEWAD_AMIGOCUIABÁ MAIO 2026_27 04 26.xlsx` | ✅ Mai 2026 | Official |
| 2026/JUNHO | `Plano NEWAD RAFA_AMIGOCUIABÁ JUNHO 2026_29 05 25.xlsx` | ✅ Jun 2026 | RAFA (sem oficial) |

**Problemas no Drive — TecPar/AMIGO:**

1. **Arquivo de JANEIRO copiado nas pastas FEVEREIRO e MARÇO**: o plano de JANEIRO está em 3 pastas diferentes (JAN, FEV, MAR de 2026). FEV e MAR não têm planos próprios — alguém copiou o arquivo de JAN como placeholder.

2. **Arquivo de JULHO 2025 copiado nas pastas AGOSTO e SETEMBRO 2025**: o mesmo arquivo está em 2 pastas de meses errados. A cópia em SET tem "(1)" no nome.

3. **FEVEREIRO e MARÇO 2026 sem plano próprio**: as pastas têm o arquivo de JAN copiado. Não existe plano real de FEV e MAR no Drive.

4. **JUNHO 2026 só tem RAFA**: sem arquivo oficial para JUNHO.

5. **Arquivo Siprocal PI em NOVEMBRO 2025**: formato completamente diferente do IO plan padrão — não foi parseado (0 rows). Siprocal tem formato próprio de PI (Proposta de Inserção).

### 2.2 BQ Raw — Estado Atual

**Tabela `raw.io_plan_drive_snapshot` — TecPar após re-sync:**

| drive_path | Arquivo | Spend | Estratégias | Problema |
|---|---|---|---|---|
| 2025/AGOSTO | JULHO plan | R$60.000 | 4 | ❌ arquivo errado na pasta |
| 2025/SETEMBRO | JULHO plan (1) | R$60.000 | 4 | ❌ duplicata em pasta errada |
| 2026/JANEIRO | RAFA JANEIRO | R$10.450 | 5 | ✅ período correto, RAFA |
| 2026/FEVEREIRO | RAFA JANEIRO (cópia) | R$10.450 | 5 | ❌ JAN em FEV — dados de JAN repetidos |
| 2026/MARÇO | RAFA JANEIRO (cópia) | R$10.450 | 5 | ❌ JAN em MAR — dados de JAN repetidos |
| 2026/ABRIL | Official ABRIL | R$60.000 | 4 | ✅ período correto ⚠️ valor alto vs histórico |
| 2026/MAIO | Official MAIO | R$60.000 | 4 | ✅ período correto ⚠️ valor alto vs histórico |
| 2026/JUNHO | RAFA JUNHO | R$12.700 | 4 | ✅ período correto, RAFA |

**Total raw TecPar: 35 rows, 7 arquivos, 100% sem datas**

**Anomalia de valor — ABRIL/MAIO**: R$60.000/mês vs ~R$12.700/mês nos meses anteriores. O core STANDARD (carga manual anterior) tinha R$12.700 para ABR. Os arquivos oficiais do Drive mostram R$60.000. **Verificar com comercial se houve replanejamento para ABR/MAI 2026.**

**Dados confiáveis para uso imediato (TecPar):**
- JUNHO 2026: R$12.700, 4 estratégias — período correto ✅
- ABRIL/MAIO 2026: R$60.000 — período correto, mas valor a confirmar ⚠️

**Dados descartáveis (contaminam se não filtrados):**
- FEV e MAR 2026: são cópias do plano de JAN — não representam FEV/MAR reais
- AGO e SET 2025: arquivo de JUL em pasta errada — período errado

### 2.3 Estratégias TecPar → Mapeamento de Plataforma

| strategy_name | Platform detectada | Observação |
|---|---|---|
| Mídia Progarmática - Display - On target | mediasmart | |
| Retargeting Display | mediasmart | |
| Native Ads - Contextual | mgid | |
| Push - App Targeting SIPROCAL | **siprocal** ✅ | Nome já identifica a plataforma explicitamente |
| Push - App Targeting | **unknown** | ⚠️ sem identificador de plataforma |
| Push - MGID | **mgid** ✅ | Nome já identifica a plataforma explicitamente |

**Achado importante**: estratégias de TecPar/AMIGO usam convenção de nomeclatura que inclui a plataforma no nome ("Push - MGID", "Push - App Targeting SIPROCAL"). Isso é uma **pista para o linkage plano → campanha**.

---

## 3. Análise de Linkage Plano → Campanha

### 3.1 O Problema

A raw tem `strategy_name` (ex: "Native Ads - Contextual") mas não tem `campaign_id` nem `campaign_name` da plataforma. Para cruzar plano vs realizado precisamos saber **qual campanha no MediaSmart/MGID/Siprocal corresponde a qual estratégia do plano**.

### 3.2 O Que Já Temos

**PLATFORM_RULES (já implementado no código):** mapeia `strategy_name` → plataforma por palavras-chave:
- "Native" → mgid
- "Display", "Retargeting", "Vídeo" → mediasmart
- Restante → unknown

**Convenção de nome implícita (achado desta sessão):**
- TecPar: "Push - App Targeting SIPROCAL", "Push - MGID" → plataforma no próprio nome
- Isso pode ser uma convenção do Rafa que pode ser extendida/padronizada

### 3.3 O Que Falta para Linkage

**Nível 1 — Plataforma** (resolvido parcialmente pelo PLATFORM_RULES):
- Saber qual das 3 plataformas (MediaSmart/MGID/Siprocal) cada estratégia usa ✅ para as principais
- Ainda unknown: Push, AppInstall, Rich Media, CTV, WhatsApp (Cora)

**Nível 2 — Campanha específica** (requer ação):
- Saber qual `campaign_id` no MediaSmart corresponde a "Retargeting Display - 1st party" da Cora no período Mai-Jun 2026
- Este mapeamento **não existe ainda em nenhuma tabela**

### 3.4 Abordagens Possíveis

| Abordagem | Como | Esforço | Precisão |
|---|---|---|---|
| **A) Mapeamento manual** | Comercial preenche tabela: strategy → campaign_id | Alto (comercial) | Alto |
| **B) Fuzzy match por nome** | Compara strategy_name vs campaign_name com regex/similarity | Médio (eng) | Médio — risco de falso positivo |
| **C) Match por budget+período** | Compara planned_spend vs actual_spend por plataforma+cliente+período | Médio (eng) | Baixo — ambíguo se vários formatos no mesmo mês |
| **D) Naming convention** | Padronizar nomes de campanha na plataforma para incluir código do IO | Alto (operacional) | Alto — mas exige disciplina de operação |
| **E) Combinação B+C** | Usar nome como hint primário + budget como validação | Alto (eng) | Médio-Alto |

**Recomendação:** começar com **B + validação manual**:
1. Eng cria a lógica de fuzzy match strategy_name vs campaign_name por cliente+período
2. Comercial/operações valida ou corrige os matches
3. Resultado vira tabela `core.io_plan_campaign_map` (client_id, strategy_name, campaign_id, platform, valid_from, valid_to)

### 3.5 Perguntas para o Comercial

Para avançar no linkage, precisamos responder:

| # | Pergunta | Cliente | Impacto |
|---|---|---|---|
| 1 | Uma estratégia do plano = uma campanha na plataforma? Ou pode haver múltiplas campanhas por estratégia? | Ambos | Alto — define a cardinalidade do join |
| 2 | Os nomes de campanha nas plataformas (MediaSmart, MGID) seguem algum padrão relacionado ao IO plan? | Ambos | Alto |
| 3 | "Push" da Cora é MediaSmart ou Siprocal? E "Push - APPTARGETING"? | Cora | Médio |
| 4 | "AppInstall - Download/Abertura de Conta" da Cora — qual plataforma? (não é nenhuma das 3?) | Cora | Médio |
| 5 | "Rich Media", "CTV Household sync", "Whatsapp Marketing" — qual vendor? | Cora | Baixo (pós v1) |
| 6 | O plano ABR/MAI 2026 do AMIGO/TecPar tem R$60K — é replanejamento? | TecPar | Médio |
| 7 | Existe algum mês de 2026 para TecPar com plano oficial (FEV, MAR)? | TecPar | Médio |

---

## 4. Pendências Técnicas Identificadas

### 4.1 Drive — Problemas que requerem ação no Drive (não no código)

| Problema | Cliente | Ação necessária | Responsável |
|---|---|---|---|
| Arquivo de JANEIRO copiado em FEV e MAR 2026 | TecPar | Remover cópias ou colocar planos corretos | Rafa/Gessiane |
| Arquivo de JULHO 2025 copiado em AGO e SET | TecPar | Remover cópia de SET (manter AGO?) | Rafa/Gessiane |
| 2 versões do arquivo MAI-JUL 2026 (espaços vs underscore) | Cora | Manter só 1 no Drive — deletar o duplicado | Rafa/Gessiane |
| Pastas FEV e MAR 2026 sem plano próprio | TecPar | Criar planos ou confirmar que não existem | Comercial |

### 4.2 Código — Melhorias pendentes

| # | Problema | Impacto | Prioridade |
|---|---|---|---|
| L1 | `flight_start = NULL` em todos exceto Cora MAI-AGO 2026 | Core fica sem datas para a maioria | Alta |
| L2 | 2 arquivos com mesmo conteúdo diferentes IDs (Cora MAI-JUL) | Raw duplicada para Cora MAI-AGO | Alta |
| L3 | Arquivo errado na pasta (TecPar FEV/MAR) — não detectável por código | JAN data em linhas com drive_path=FEV e MAR | Média — requer fix no Drive |
| L4 | Plano anual 2026 V2 sobrepõe planos mensais de ABR/MAI/JUL | Totais inflados se não filtrar | Média |
| L5 | `drive_folder` disponível no schema — pode ser usado como fallback de data | L1 fix possível para mês/ano | Alta — fix viável |

### 4.3 Próximos passos técnicos (por ordem de prioridade)

1. **Fix L1** — Implementar fallback de data via `drive_folder` (ex: "2026/MAIO" → flight_start=2026-05-01, flight_end=2026-05-31)
2. **Fix L2** — Detectar duplicatas de conteúdo: se dois arquivos de mesma pasta têm o mesmo conteúdo (mesmo número de estratégias e mesmos valores), manter só 1
3. **Tabela `core.io_plan_campaign_map`** — criar estrutura para mapeamento manual strategy → campaign_id
4. **STG io_plan** — criar view STG que une raw com dedup e enrichment de datas, expondo só os dados corretos
5. **Gold io_plan** — integrar plano vs realizado com a campaign_map como bridge

---

## 5. Estado Atual da Raw após Reset (2026-06-15)

```
raw.io_plan_drive_snapshot — resumo pós re-sync
Cliente               Arquivos   Rows   Sem data   Spend total
aperam_14d1f27e          1         5     100%      R$66.667
banco_cora_fe13d78a     12       237      77%      R$2.933.195
catalise_0b7d18d6        1         1     100%      R$15.000
einstein_6b33a588        4        14     100%      R$92.950
luckbet_bea15ebc         3        80     100%      R$4.703.405
tecpar_edfcc744          7        35     100%      R$284.050
TOTAL                   28       372
```

**O que está limpo e usável agora:**
- Luckbet: 3 períodos (Set/Out 2025 + Ano 2026), valores coerentes, sem duplicação
- Cora MAI–AGO 2026: datas parseadas, valores corretos (**mas duplicados** por 2 arquivos com mesmo conteúdo)
- TecPar ABR/MAI/JUN 2026: 1 arquivo por mês, valores a confirmar com comercial

**O que ainda bloqueia uso pleno:**
- Todos os demais: `flight_start = NULL` → sem período → não conectável ao gold
- TecPar FEV/MAR: dados de JAN repetidos em pastas erradas
- Cora: plano anual V2 sobrepõe os mensais

---

---

## 6. Sessão 2026-06-16 — Análise xlsx mês a mês e plano de correção do parser

### 6.1 Descoberta crítica: padrão de abas trimestrais (Cora)

Rafael confirmou o padrão geral para **todos** os arquivos xlsx da Cora:

> Arquivos anuais/trimestrais têm 4 abas: **"JAN A MAR"**, **"ABR A JUN"**, **"JUL A SET"**, **"OUT A DEZ"**  
> Para cada pasta de mês, usa-se apenas a aba do trimestre correspondente.  
> O período da aba **não tem número de dia** — as datas devem ser derivadas do `drive_folder`.

**Regra de seleção de aba:**
| drive_folder mês | Aba a usar |
|---|---|
| Janeiro, Fevereiro, Março | "JAN A MAR" |
| Abril, Maio, Junho | "ABR A JUN" |
| Julho, Agosto, Setembro | "JUL A SET" |
| Outubro, Novembro, Dezembro | "OUT A DEZ" |

**Arquivo V3 (exceção):** `Plano NEWAD_CORA MAIO JUNHO JULHO V3` usa abas por **intervalo de datas com dias** (`"1 MAI A 10 MAI"`, `"11 MAI A 10 JUN"`, etc.). O parser atual já lê essas abas corretamente e já popula `flight_start`/`flight_end`.

### 6.2 Bug do parser identificado (L1 — raiz)

**Função `parse_xlsx` (linha 257):** itera `wb.sheetnames` sem filtrar pelo mês do `drive_folder`. Para um arquivo com 4 abas trimestrais, concatena todas as 4 → **multiplica por 4 o número de rows**.

Evidência:
- `CORA 2026 V2` em 2026/JANEIRO → 23 rows na raw (4 abas × ~6 rows)
- Correto: 6 rows da aba "JAN A MAR"
- O mesmo erro afeta JAN, FEV, MAR (23 rows cada), e os arquivos históricos de 2025

### 6.3 Estado completo da raw Cora por pasta (2026-06-16)

| drive_folder | rows raw | arquivo | problema |
|---|---|---|---|
| 2025/ABRIL | 40 | Plano NEWAD_CORA_17FEV2025_V2.xlsx | ❌ todas as 4 abas (~10 cada) |
| 2025/MAIO | 20 | Plano NEWAD_CORA_13MAIO25_V4.xlsx | ❌ múltiplas abas |
| 2025/JUNHO | 13 | Plano NEWAD_CORA_30MAIO25_V4.xlsx | ❌ múltiplas abas |
| 2025/JULHO | 7 | Plano NEWAD_CORA_02JUL25.xlsx | ⚠️ a verificar |
| 2025/AGOSTO | 6 | Plano NEWAD RAFA_CORA AGOSTO V2 | ✅ provavelmente correto |
| 2025/SETEMBRO | 6 | Plano NEWAD_CORA SETEMBRO_29AGO25 | ✅ provavelmente correto |
| 2025/OUTUBRO | 5 | Plano NEWAD_CORA BONIF Out&Nov | ✅ BONIF |
| 2025/NOVEMBRO | 5 | Plano NEWAD_CORA BONIF OUT NOV DEZ | ✅ BONIF |
| 2026/JANEIRO | 23 | Plano NEWAD_CORA 2026 V2 | ❌ deve ser 6 |
| 2026/FEVEREIRO | 23 | Plano NEWAD_CORA 2026 V2 (mesmo) | ❌ deve ser 6 |
| 2026/MARÇO | 23 | Plano NEWAD_CORA 2026 V2 (mesmo) | ❌ deve ser 6 |
| 2026/ABRIL | 12 | Plano NEWAD_CORA ABRIL_APROVADOS | ❓ a verificar ao abrir o arquivo |
| 2026/MAIO | 27 (5 períodos) | Plano NEWAD...V3 (espaços) | ✅ abas por data — correto na raw |
| 2026/JUNHO | 27 (5 períodos) | Plano_NEWAD...V3 (underscores) | ⚠️ arquivo duplicado no Drive |

**Janeiro confirmado por Rafael:** 6 estratégias na aba "JAN A MAR":
`Mídia Progarmática - Display`, `Vídeo Ads`, `Native Ads - Contextual`, `Push - APPTARGETING`, `Retargeting Display - 1st party`, `Retargeting Display - VIEW`

### 6.4 Plano de correção do parser (sync_drive.py)

**Duas mudanças necessárias em `parse_xlsx`:**

**1. Seleção da aba correta por mês (novo helper `_find_quarterly_tab`)**
```python
def _find_quarterly_tab(wb, target_month: int) -> Optional[str]:
    for name in wb.sheetnames:
        upper = _deaccent(name).upper().strip()
        m = re.match(r'^([A-Z]{3})\s+A\s+([A-Z]{3})$', upper)
        if m:
            s = MONTH_PT.get(m.group(1))
            e = MONTH_PT.get(m.group(2))
            if s and e and s <= target_month <= e:
                return name
    return None
```
- Se encontrar aba trimestral para o mês → processa só essa aba
- Se não encontrar (arquivo V3 com abas por data) → comportamento atual (itera todas)

**2. Derivação de datas do drive_folder (novo helper `_dates_from_drive_path`)**
```python
import calendar

def _dates_from_drive_path(drive_path: str):
    parts = drive_path.upper().split("/")
    year = int(parts[0]) if parts[0].isdigit() else None
    month = MONTH_PT.get(parts[1]) if len(parts) > 1 else None
    if not year or not month:
        return None, None
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return start, end
```
- Para abas trimestrais: flight_start = 1º dia do mês do drive_folder
- Para abas por data (V3): mantém datas já parseadas do nome da aba

**Lógica resultante em `parse_xlsx`:**
```
1. Extrai target_month de drive_path
2. Tenta achar aba trimestral: _find_quarterly_tab(wb, target_month)
3. SE achou:
   → sheets_to_process = [quarterly_tab]
   → flight_start, flight_end = _dates_from_drive_path(drive_path)
4. SE não achou:
   → sheets_to_process = wb.sheetnames (comportamento atual)
   → datas continuam sendo parseadas do nome da aba
```

### 6.5 Decisão de arquitetura: camadas para cálculo diário

Discutido e decidido em 2026-06-16:

| Camada | Responsabilidade |
|---|---|
| **RAW (parser)** | Selecionar aba correta + popular flight_start/flight_end do drive_folder quando aba é trimestral |
| **STG** | Limpar, deduplicar, filtrar sobreposições (ex: V3 em MAIO → só períodos de MAIO), garantir NOT NULL em datas |
| **Gold (view)** | `GENERATE_DATE_ARRAY(flight_start, flight_end)` → daily_spend = monthly_spend / dias_do_período |

O cálculo diário **não vai para a STG** — é view analítica no Gold. A STG expõe uma linha limpa por estratégia × período.

### 6.6 O que a correção trimestral resolve vs o que sobra

**Resolve:**
- ✅ JAN/FEV/MAR 2026: 23 → 6 rows cada
- ✅ 2025/ABRIL: 40 → ~10 rows (lê só "ABR A JUN")
- ✅ 2025/MAIO: 20 → ~5 rows
- ✅ 2025/JUNHO: 13 → ~5-7 rows
- ✅ Todas as datas NULL de arquivos trimestrais → populadas do drive_folder

**Não resolve (requer ações complementares):**
- ⚠️ V3 duplicado no Drive (MAIO espaços + JUNHO underscore): requer limpeza no Drive por Rafa
- ❓ 2026/ABRIL: estrutura de abas ainda não confirmada (precisa abrir o arquivo)
- ❓ 2025/JULHO (7 rows): a verificar
- ⚠️ STG precisa filtrar V3 por mês relevante (ex: na pasta MAIO, mostrar só períodos de MAIO)

---

---

## 7. Estado Cora 2026 pós-fix (2026-06-16) — ENTREGA

### 7.1 Resultado da correção do parser (2026)

Todos os meses de 2026 com arquivo próprio estão corretos na raw:

| drive_folder | rows | datas | spend | arquivo | status |
|---|---|---|---|---|---|
| 2026/JANEIRO | 6 | 2026-01-01→01-31 | R$35.000 | CORA 2026 V2 | ✅ |
| 2026/FEVEREIRO | 6 | 2026-02-01→02-28 | R$35.000 | CORA 2026 V2 | ✅ |
| 2026/MARÇO | 6 | 2026-03-01→03-31 | R$35.000 | CORA 2026 V2 | ✅ |
| 2026/ABRIL | 6 | 2026-04-01→04-30 | R$70.000 | CORA ABRIL | ✅ |
| 2026/MAIO | 27 (5 períodos) | MAI-01→AGO-31 | R$182.500 | V3 (espaços) | ✅ raw correta |
| 2026/JUNHO | 27 (5 períodos) | MAI-01→AGO-31 | R$182.500 | V3 (underscores) | ⚠️ duplicata do V3 |

Meses JUL–DEZ 2026: cobertos pelos períodos do arquivo V3 (que vai até 2026-08-31). SET–DEZ 2026 não têm arquivo no Drive ainda.

### 7.2 Regra de negócio estabelecida — Pasta Drive = plano oficial

> **"Pasta no Drive = plano oficial para aquele mês. Sem pasta = sem plano = sem dado."**

Confirmado pelo Douglas em 2026-06-16. O Drive é a fonte de verdade sobre quais meses têm plano aprovado. Não há pasta → não há ingestão → não há dado naquele mês.

**Para arquivos multi-período (ex: V3 MAI-JUL):**
- Lê **apenas as abas cujo `flight_start` cai no mesmo mês do `drive_folder`**
- `2026/MAIO` → abas onde `flight_start.month == 5` → `"1 MAI A 10 MAI"` + `"11 MAI A 10 JUN"` (2 períodos)
- `2026/JUNHO` → abas onde `flight_start.month == 6` → `"11 JUN A 10 JUL"` (1 período)
- Períodos de JUL e AGO do V3: **ignorados** até que pasta JULHO/AGOSTO seja criada no Drive
- Quando Rafa criar a pasta → pipeline pega automaticamente

**Efeito colateral positivo:** resolve o problema do V3 duplicado — cada arquivo lê só o mês da sua pasta, sem sobreposição.

### 7.3 Validação dos valores de spend

Confirmado pelo Douglas em 2026-06-16:

- O campo `PERÍODO` nos arquivos xlsx mostra `"30 dias"` = o plano é para o mês completo
- `flight_start` = primeiro dia do mês (derivado do drive_folder), `flight_end` = último dia do mês ✅
- R$35k/mês para JAN–MAR e R$70k para ABR são corretos — decisão comercial de budget diferente, não erro de dado
- A linha de TOTAL do xlsx **não entra** na raw — o parser faz `break` quando vê "TOTAL" em qualquer célula da linha

### 7.4 O que falta antes de re-sincronizar Cora 2026

| # | Item | Onde | Status |
|---|---|---|---|
| 1 | Filtro V3 no parser: só lê abas onde `flight_start.month == drive_folder month` | `sync_drive.py` `parse_xlsx` | ✅ implementado |
| 2 | Re-sync Cora `--force` após fix | CLI | ✅ executado |
| 3 | Verificar resultado: MAIO=11 rows, JUNHO=5 rows | BQ | ✅ verificado |

### 7.5 Alterações de código implementadas (sync_drive.py)

Todas as mudanças estão no arquivo `scripts/io_plan/sync_drive.py`.

#### Mudança 1 — Import `calendar` (linha ~28)
```python
import calendar
```
**Por quê:** necessário para calcular o último dia do mês em `_dates_from_drive_path`.

#### Mudança 2 — `SKIP_SHEETS` (linha ~104)
```python
# Antes:
SKIP_SHEETS = {"RESUMO", "SUMMARY", "SUGESTAO", "SUGESTÃO", "INDICADORES", ...}
# Depois:
SKIP_SHEETS = {"RESUMO", "SUMMARY", "SUGESTAO", "SUGESTOES", "SUGESTÃO", "SUGESTÕES", "INDICADORES", ...}
```
**Por quê:** arquivos da Cora 2026 têm aba `"SUGESTÕES"` que não estava sendo ignorada.

#### Mudança 3 — Helper `_find_quarterly_tab` (novo, após `_month_num`)
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
**Por quê:** os arquivos de 2026 (ex: CORA 2026 V2) têm 3 abas trimestrais com prefixo "PLANO" e o parser antes lia todas as abas → 23 rows em vez de 6. O regex `\b([A-Z]{3})\s+A\s+([A-Z]{3})\b` encontra o padrão em qualquer parte do nome da aba, não só no início. "PLANO JUL A DEZ" cobre meses 7–12 com um único tab.

#### Mudança 4 — Helper `_dates_from_drive_path` (novo, após `_find_quarterly_tab`)
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
**Por quê:** abas trimestrais não têm número de dia no nome (ex: "PLANO JAN A MAR") então `parse_flight_label` retornava `(None, None)`. As datas corretas são sempre o primeiro e último dia do mês do `drive_folder`.

#### Mudança 5 — `parse_xlsx`: seleção de aba e datas (loop principal)
```python
# Antes: iterava wb.sheetnames direto
for sheet_name in wb.sheetnames:
    ...
    flight_start, flight_end = parse_flight_label(...)  # sempre None para trimestrais

# Depois:
target_month = MONTH_PT.get(_deaccent(path_parts[1]).upper()) if len(path_parts) > 1 else None
quarterly_tab = _find_quarterly_tab(wb, target_month) if target_month else None
quarterly_dates = _dates_from_drive_path(drive_path) if quarterly_tab else (None, None)
sheets_to_process = [quarterly_tab] if quarterly_tab else wb.sheetnames

for sheet_name in sheets_to_process:
    if quarterly_tab:
        flight_label = sheet_name
        flight_start, flight_end = quarterly_dates   # datas do drive_folder
    else:
        # lógica existente de parse do nome da aba
        ...
```
**Por quê:** garante que só a aba do trimestre correto é lida, e que as datas venham do `drive_folder` quando a aba não tem dígitos.

#### Mudança 6 — Filtro V3: `flight_start.month == target_month`
```python
# Adicionado após parse das datas no bloco else (abas day-range):
if target_month and flight_start and flight_start.month != target_month:
    continue
```
**Por quê:** arquivos multi-mês como o V3 (MAIO-JUL 2026) têm abas para múltiplos meses (`"1 MAI A 10 MAI"`, `"11 MAI A 10 JUN"`, `"11 JUN A 10 JUL"`, etc.). Sem esse filtro, a pasta `2026/MAIO` ingeria todos os 5 períodos (MAI→AGO) em vez de apenas os que começam em MAIO. Regra de negócio: **pasta no Drive = plano oficial para aquele mês** — cada pasta ingere só os períodos que começam no seu mês. Períodos que cruzam meses (ex: `"11 MAI A 10 JUN"`) pertencem ao mês de início.

**Estado esperado pós-fix:**

| drive_folder | rows esperados | spend | fonte |
|---|---|---|---|
| 2026/JANEIRO | 6 | R$35k | V2 anual — aba "PLANO JAN A MAR" |
| 2026/FEVEREIRO | 6 | R$35k | V2 anual — aba "PLANO JAN A MAR" |
| 2026/MARÇO | 6 | R$35k | V2 anual — aba "PLANO JAN A MAR" |
| 2026/ABRIL | 6 | R$70k | CORA ABRIL — aba "PLANO ABR A JUN" |
| 2026/MAIO | ~11 | ? | V3: "1 MAI A 10 MAI" (6) + "11 MAI A 10 JUN" (5) |
| 2026/JUNHO | ~5 | ? | V3 underscore: "11 JUN A 10 JUL" |
| 2026/JUL–DEZ | 0 | — | Sem pasta no Drive ainda |

---

## 8. Análise 2025 — PENDENTE (retomar após entrega) ⚠️

> Esta seção registra os achados sobre os arquivos históricos de 2025.  
> **Ação futura:** revisar com o comercial/Rafa para confirmar se os dados de 2025 devem ser ajustados no Drive ou ignorados no pipeline.  
> **Não bloqueia a entrega 2026.**

### 8.1 Estrutura de abas dos arquivos 2025 (diferente de 2026)

Os arquivos de **2025 usam convenção de abas diferente dos de 2026**:

| Tipo | Exemplo de arquivo | Abas |
|---|---|---|
| **2026 (trimestral)** | CORA 2026 V2 | "PLANO JAN A MAR", "PLANO ABR A JUN", "PLANO JUL A DEZ" |
| **2025 (por mês/período nomeado)** | CORA_17FEV2025_V2 | "PLANO FEVEREIRO", "PLANO MARÇO", "PLANO ABRIL", "PLANO MAIO", "PLANO JUN E JUL", "PLANO AGO \| SET \| OUT", "PLANO NOV a DEZ" |
| **2025 V4 (parcial)** | CORA_13MAIO25_V4 | "PLANO MAIO", "PLANO JUN E JUL", "PLANO AGO a DEZ" |

O parser atual **não reconhece o padrão "PLANO ABRIL"** (sem range "A") → lê todas as abas → rows inflados.

### 8.2 Estado atual da raw 2025 (com problemas)

| drive_folder | rows raw | esperado | arquivo | problema |
|---|---|---|---|---|
| 2025/ABRIL | 40 | ~5-6 | CORA_17FEV2025_V2.xlsx | ❌ lê 7 abas × ~5-6 rows cada |
| 2025/MAIO | 20 | ~5 | CORA_13MAIO25_V4.xlsx | ❌ lê 3 abas × ~5-7 rows |
| 2025/JUNHO | 7 | 7 | CORA_30MAIO25_V4.xlsx | ✅ fix trimestral funcionou (tinha "PLANO ABR A JUN") |
| 2025/JULHO | 7 | ? | CORA_02JUL25.xlsx | ⚠️ sem data; conta pode estar correta |
| 2025/AGOSTO | 6 | ? | RAFA CORA AGOSTO V2 | ⚠️ sem data; conta pode estar correta |
| 2025/SETEMBRO | 6 | ? | CORA SETEMBRO_29AGO25 | ⚠️ sem data; pode estar correto |
| 2025/OUTUBRO | 5 | 5 | BONIF Out&Nov | ✅ bonificação |
| 2025/NOVEMBRO | 5 | 5 | BONIF OUT NOV DEZ | ✅ bonificação |

### 8.3 Fix necessário para 2025 (não implementado)

Precisamos de um terceiro helper `_find_monthly_tab(wb, target_month)` que:
1. Procura abas com o **nome do mês** no título (ex: "PLANO ABRIL" → mês 4)
2. Aceita abas multi-mês como "PLANO JUN E JUL" → meses 6 e 7
3. Aceita separadores variados: espaço, `|`, `E`, `&`, `a`
4. **Exclui** abas com dígitos (day-range tabs como "1 MAI A 10 MAI")
5. Preferencia aba de mês único sobre aba multi-mês quando ambas batem

```python
def _find_monthly_tab(wb, target_month: int) -> Optional[str]:
    exact = None
    multi = None
    for name in wb.sheetnames:
        upper = _deaccent(name).upper().strip()
        if re.search(r'\d', upper):  # skip day-range tabs
            continue
        tokens = re.findall(r'[A-Z]+', upper)
        months_in_tab = [_month_num(t) for t in tokens if _month_num(t)]
        if target_month in months_in_tab:
            if len(months_in_tab) == 1:
                exact = name
            elif multi is None:
                multi = name
    return exact or multi
```

E ajustar `parse_xlsx` para tentar na ordem: `_find_quarterly_tab` → `_find_monthly_tab` → day-range (V3) → tudo.

### 8.4 Perguntas para o comercial / Rafa sobre 2025

Antes de implementar o fix para 2025, confirmar:

| # | Pergunta | Impacto |
|---|---|---|
| 1 | Os dados de 2025 devem entrar no dashboard? Se sim, desde qual mês? | Define scope do fix |
| 2 | O arquivo `CORA_17FEV2025_V2.xlsx` cobre FEV→DEZ 2025 numa só planilha — é o plano anual de 2025? | Confirma que cada aba = 1 mês/período |
| 3 | `CORA_13MAIO25_V4.xlsx` tem só MAI, JUN-JUL, AGO-DEZ — isso é uma versão revisada do V2 de 2025? | Define precedência entre arquivos |
| 4 | Julho 2025 tem `CORA_02JUL25.xlsx` com 7 rows — é o plano completo de julho? | Validação de contagem |
| 5 | Agosto 2025 só tem arquivo do Rafa (`CORA AGOSTO V2 RAFA`) — existe versão oficial? | Confirmar se RAFA é fallback ou erro |

### 8.5 Decisão tomada em 2026-06-16

**Não implementar fix para 2025 agora.** Prioridade é entregar 2026 correto. Os dados de 2025 na raw têm rows inflados e sem datas — não devem ser usados até revisão com comercial. A STG de 2026 deve filtrar apenas `drive_folder LIKE '2026/%'` até o fix de 2025 estar pronto.

---

---

## 9. TecPar/AMIGO — Fix de datas e estado final RAW (2026-06-16)

### 9.1 Estrutura de abas TecPar (descoberta)

Todos os arquivos TecPar têm **exatamente 1 aba** com nome genérico — sem intervalo de datas no nome. O parser não conseguia parsear `flight_start`/`flight_end` → 100% SEM_DATA antes do fix.

| drive_folder | aba encontrada | arquivo | observação |
|---|---|---|---|
| 2025/AGOSTO | `'PLANO R$ 60k CUIABÁ'` | JULHO25 | arquivo de JULHO na pasta AGO |
| 2025/SETEMBRO | `'PLANO R$ 60k CUIABÁ'` | JULHO25 (1) | cópia de JULHO em SET |
| 2026/JANEIRO | `'PLANO CUIABÁ'` | RAFA_JANEIRO | ✅ mês correto |
| 2026/FEVEREIRO | `'PLANO CUIABÁ'` | RAFA_JANEIRO (cópia) | arquivo JAN em pasta FEV |
| 2026/MARÇO | `'PLANO CUIABÁ'` | RAFA_JANEIRO (cópia) | arquivo JAN em pasta MAR |
| 2026/ABRIL | `'ABRIL'` | AMIGOCUIABÁ ABRIL 2026 | ✅ |
| 2026/MAIO | `'MAIO'` | AMIGOCUIABÁ MAIO 2026 | ✅ |
| 2026/JUNHO | `'MAIO'` | RAFA JUNHO 2026 | ✅ aba chamada "MAIO" mas pasta é JUNHO |

### 9.2 Fix implementado — Mudança 7 (fallback drive_folder)

```python
# Em parse_xlsx, no bloco else (após filtro V3), antes de processar o cabeçalho:
if flight_start is None and target_month:
    flight_start, flight_end = _dates_from_drive_path(drive_path)
```

**Por quê:** arquivos TecPar têm 1 aba com nome genérico sem datas (ex: "PLANO CUIABÁ", "ABRIL", "MAIO"). `_find_quarterly_tab` retorna None, `parse_flight_label` retorna None → sem esse fallback todas as linhas ficam SEM_DATA.

**Regra de negócio confirmada (Douglas, 2026-06-16):**
> "Se está na pasta é o arquivo do mês."

O nome da aba não importa — a pasta no Drive é a fonte de verdade do mês. Mesmo o arquivo com aba chamada "MAIO" na pasta JUNHO → datas de JUNHO.

Esta mudança é **segura para a Cora** porque:
- Cora V2 2026: entra pelo caminho `quarterly_tab` → nunca chega no fallback
- Cora V3: `flight_start` é populado pelo day-range → condição `flight_start is None` é False

### 9.3 Estado raw TecPar pós-fix

| drive_folder | rows | datas | spend | arquivo | status |
|---|---|---|---|---|---|
| 2025/AGOSTO | 4 | 2025-08-01→08-31 | R$60.000 | JULHO file | ⚠️ arquivo errado na pasta |
| 2025/SETEMBRO | 4 | 2025-09-01→09-30 | R$60.000 | JULHO file (cópia) | ⚠️ arquivo errado na pasta |
| 2026/JANEIRO | 5 | 2026-01-01→01-31 | R$10.450 | RAFA JANEIRO | ✅ |
| 2026/FEVEREIRO | 5 | 2026-02-01→02-28 | R$10.450 | JAN copiado em FEV | ⚠️ Drive errado |
| 2026/MARÇO | 5 | 2026-03-01→03-31 | R$10.450 | JAN copiado em MAR | ⚠️ Drive errado |
| 2026/ABRIL | 4 | 2026-04-01→04-30 | R$60.000 | ABRIL 2026 | ✅ |
| 2026/MAIO | 4 | 2026-05-01→05-31 | R$60.000 | MAIO 2026 | ✅ |
| 2026/JUNHO | 4 | 2026-06-01→06-30 | R$12.700 | RAFA JUNHO 2026 | ✅ |

**Parser: 100% resolvido — zero SEM_DATA.**

Os problemas restantes são organizacionais no Drive (arquivos errados nas pastas) — não são bugs de código.

### 9.4 Nota para reestruturação com o comercial (pós-entrega)

> "Anote para quando criarmos o plano com o comercial: reestruturar a forma como alimentamos o plano no Drive."

**Ponto identificado:** o Drive hoje depende de disciplina manual para colocar o arquivo certo na pasta certa. Qualquer erro (copiar JAN em FEV, colocar JULHO em AGO) entra silenciosamente na raw com datas erradas — não há validação automática.

**Opções de reestruturação a discutir com o comercial:**
1. Definir naming convention obrigatória para arquivos (ex: `CLIENTE_AAAA_MM.xlsx`) → parser valida nome vs pasta
2. Pipeline emite alerta quando `source_file` não menciona o mês da pasta
3. Planilha centralizada de upload (formulário Drive) para garantir que cada mês tem exatamente 1 arquivo correto

---

## 10. Status de fechamento RAW — Cora e TecPar (2026-06-16)

| Cliente | RAW 2026 | Datas | Pendência |
|---|---|---|---|
| **Cora** (`banco_cora_fe13d78a`) | ✅ fechado | ✅ 100% populadas (2026) | Drive: remover V3 duplicado (underscores vs espaços) |
| **TecPar** (`tecpar_edfcc744`) | ✅ fechado | ✅ 100% populadas | Drive: organização (JAN em FEV/MAR, JULHO em AGO/SET) |

**Próximo passo: STG io_plan para Cora 2026 e TecPar 2026.**

---

---

## 11. Design: Pipeline de Linkage Plano → Campanha (V2 — pós-entrega)

> Discutido em 2026-06-16. **Não implementar agora.** Registrado para desenho futuro.

### 11.1 Problema que o design resolve

Hoje a Luckbet tem uma Google Sheet ("PIs") preenchida manualmente pela Gessiane com:
`id | Mês | Cliente | Plataforma | Estratégia | Início | Fim | Investimento | id_Campanha`

Para cada novo cliente isso exigiria uma nova sheet idêntica — processo não escala, vira bagunça, sem padrão de armazenamento.

### 11.2 Fluxo proposto

```
1. ETL roda (MediaSmart/MGID/Siprocal → BQ)
2. BQ detecta campaigns sem vínculo com linha do plano
3. Pipeline gera Google Form pré-preenchido com campanhas não vinculadas:
   - client_id, plataforma, campaign_id, campaign_name, período ativo, spend no período
4. Comercial (Gessiane) preenche para cada campanha:
   - Qual linha do plano (via plan_line_id)
   - % de divisão de verba (se 1 linha do plano → N campanhas)
5. Respostas do Form → BQ → tabela bridge
6. Gold faz JOIN: io_plan × bridge × performance por campanha
```

**Futuro:** quando o Admin UI do Shiro estiver no ar, o Form é substituído pela interface própria.

### 11.3 O que precisamos criar (dependências)

| # | O que criar | Onde | Bloqueador? |
|---|---|---|---|
| 1 | **`plan_line_id` estável** por linha da raw | `raw.io_plan_drive_snapshot` | Sim — o Form precisa referenciar algo |
| 2 | **Lógica de ID estável** no parser | `sync_drive.py` | Sim — hash de `(client_id, drive_folder, strategy_name)` resistente a re-sync |
| 3 | **Tabela bridge** `core.io_plan_campaign_map` | BQ | Sim — destino das respostas do Form |
| 4 | **Google Form** com campos padronizados | Google Forms | Sim — canal de input do comercial |
| 5 | **Script de geração do Form** | pipeline | Sim — detecta não vinculadas e gera o Form |
| 6 | **Script de ingestão das respostas** | pipeline | Sim — Form responses → BQ |
| 7 | **Lógica de split de verba** | STG/Gold | Define como dividir monthly_spend entre N campanhas |

### 11.4 Complexidades identificadas

**Split de verba (1 linha do plano → N campanhas):**
- Quem define a % de divisão? → Comercial define no momento do mapeamento
- Se campanha A recebe 70% e B 30% de uma linha de R$70k → cada uma recebe R$49k e R$21k de "plano"
- Esse split precisa ser armazenado na bridge table

**Siprocal — IDs não reais:**
- Na planilha da Luckbet o ID da Siprocal é `siprocal-pushapp` (placeholder, não ID real da API)
- JOIN com performance da Siprocal vai falhar — resolver separadamente via lógica BQ
- Não bloqueia o design do Form para as outras plataformas

**Timing:**
- Campanhas precisam existir nas plataformas ANTES do Form ser gerado
- Fluxo: plano aprovado → Gessiane cria campanhas → ETL roda → Form gerado → Gessiane preenche
- Se Form for gerado antes das campanhas existirem → lista vazia (OK, só gerar depois)

**`plan_line_id` estável:**
- Precisa ser o mesmo se a raw for re-ingerida (DROP+CREATE)
- Usar hash determinístico: `MD5(client_id || drive_folder || strategy_name)`
- Isso garante que o mesmo plano sempre tem o mesmo ID mesmo após reset

### 11.5 Schema proposto: `core.io_plan_campaign_map`

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

### 11.6 Abordagem gambiarra para entrega de 2026 (Cora)

Em vez de campaign-level linkage, usar **category-level** conforme mapeamento do Rafa na planilha de performance:

| IO plan strategy_name | Categoria | Plataforma |
|---|---|---|
| Mídia Progarmática - Display | DISPLAY | mediasmart |
| Vídeo Ads | VIDEO | mediasmart |
| Retargeting Display - 1st party | RETARGETING | mediasmart |
| Retargeting Display - VIEW | RETARGETING | mediasmart |
| Native Ads - Contextual | NATIVE | mgid |
| Push - APPTARGETING | PUSH | siprocal |

Gold view: JOIN io_plan × performance agregada por categoria × período. Não requer campaign_ids individuais.

**Planilha do Rafa analisada (2026-06-16):**
`https://docs.google.com/spreadsheets/d/1Y94CavDyMXnIy9sLyqcTP8yKdANiQ1j1RzZBzHi7YHk`

12 abas de dashboard plano vs realizado por dia. Estratégias mapeadas: DISPLAY, VIDEO, RETARGETING, NATIVE, PUSH. Performance já agregada por categoria — não há campaign_ids individuais. Projetado = daily spread do monthly_spend do IO plan.

### 11.7 Confirmação do vínculo plano→campanha no BQ (2026-06-16)

Verificado diretamente no BQ que o vínculo é possível para Cora 2026 nas 3 plataformas sem necessidade de mapeamento manual adicional:

**MediaSmart — 3 campanhas persistentes (jan→jun 2026):**

| ms_campaign_id | ms_campaign_name | categoria |
|---|---|---|
| `ncfv7ti3k4y0zg0azyvgpyyyilrhqj` | CORA_CONTADIGITAL_DISPLAY_JUNHO26 | DISPLAY |
| `ivec3mwjoav72l3yqy2blwjqqfpauc` | CORA_CONTADIGITAL_VIDEO_JUNHO26 | VIDEO |
| `f1asxj7pfx5ufhed8tdro4rd6udvk0` | CORA_CONTADIGITAL_RETARGETING_JUNHO26 | RETARGETING |

**MGID — campanhas mensais por período:**

| mgid_campaign_id | nome | período |
|---|---|---|
| 12368531 | Banco Cora \| Native \| Mar | mar/26 |
| 12400006 | Banco Cora \| Native \| Abril 01-30 | abr/26 |
| 12414810 | Banco Cora \| Native \| Maio 01-10 | 01-10/mai |
| 12414814 | Banco Cora \| Native \| Maio/Jun 11/05-11/06 | 11mai-11jun |
| 12437129 | Banco Cora \| Native \| Jun/Jul 11/06-10/07 | 11jun-10jul |

Todas NATIVE → "Native Ads - Contextual" no IO plan.

**Siprocal — uma campanha por mês:**
`NEWAD_BANCOCORA_BR_{MES}{ANO}` — jan/fev/mar/abr/mai-jun 2026. `client_id = banco_cora_fe13d78a` direto.
Todas PUSH → "Push - APPTARGETING" no IO plan.

**Mapeamento strategy_name → categoria (gambiarra Cora):**

| IO plan strategy_name | categoria | plataforma |
|---|---|---|
| Mídia Progarmática - Display | DISPLAY | mediasmart |
| Vídeo Ads | VIDEO | mediasmart |
| Retargeting Display - 1st party | RETARGETING | mediasmart |
| Retargeting Display - VIEW | RETARGETING | mediasmart |
| Native Ads - Contextual | NATIVE | mgid |
| Push - APPTARGETING | PUSH | siprocal |

**Nota:** as duas linhas de Retargeting do IO plan mapeiam para a MESMA campanha MediaSmart.
Para o gold, somar ambas no lado do plano e comparar com o total da campanha RETARGETING.

**Método de identificação por plataforma:**
- MediaSmart: keyword no `ms_campaign_name` (DISPLAY / VIDEO / RETARGETING)
- MGID: `mgid_client_id = 'banco_cora_fe13d78a'` → todas são NATIVE
- Siprocal: `client_id = 'banco_cora_fe13d78a'` → todas são PUSH

---

*Última atualização: 2026-06-16. RAW Cora + TecPar fechados. Pendente STG + fix 2025 Cora (pós-entrega).*
