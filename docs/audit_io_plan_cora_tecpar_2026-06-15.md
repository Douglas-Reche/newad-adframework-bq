# Auditoria IO Plan — Cora & TecPar/AMIGO
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

*Documento criado em 2026-06-15. Retomar em 2026-06-16 a partir da seção 4.3 (próximos passos técnicos).*
