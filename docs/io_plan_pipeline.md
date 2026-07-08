# IO Plan Pipeline — Design e Histórico Completo

---
> **📋 REESTRUTURAÇÃO EM ANDAMENTO — 2026-06-16**
> O IO Plan em si (Drive → RAW → `gold.fact_io_plan`) é **independente** do rebuild de entrega e continua válido.
> Porém referências a tabelas de delivery (`stg.mediasmart_delivery`, etc.) neste documento são do schema antigo.
> Valide nomes de tabelas antes de usar em desenvolvimento. Plano: [bq_restructuring_plan.md](bq_restructuring_plan.md)
---

> Criado em: 2026-06-09 | Última atualização: 2026-06-24
> Status: **RAW ✅ (Drive sync ativo, 295 linhas) | STG ✅ (`stg.io_plan` recriada 2026-06-24 — substitui a `stg.io_plan_drive` antiga, arquivada em `stg/ddl/_legacy/`) | Gold ⚠️ (`gold.fact_io_plan` ainda referencia o schema antigo — revisar antes de usar)**

---

## Contexto e motivação

O IO Plan é a camada de **dados de planejamento comercial** da NewAd — distinto dos dados de entrega (MediaSmart, MGID, Siprocal). Ele responde perguntas como:

- Quanto planejamos gastar com esse cliente nesse mês?
- Quantas impressões estavam previstas para esse voo?
- O pacing real está acima ou abaixo do planejado?

A fonte são **planilhas Excel (.xlsx) mantidas pela equipe comercial** (Rafa, Gessiane) e armazenadas no Google Drive. Não existe API — é ingestão de arquivo.

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

## Arquitetura do pipeline

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
- ⚠️ **Bug aberto:** `python-multipart` ausente em `requirements.txt` → `POST /sync` retorna 500 ao tentar `await request.form()`

---

## Mapeamento Drive → client_id

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

### Dúvidas abertas (não mapeado ainda)

| Drive folder | Situação |
|---|---|
| `LABTOLAB PARDINI` | Pode ser `pardini_60395024`, `lab2lab_efb1cb34` ou ambos compartilhando pasta. Confirmar com Douglas. |
| `PHISALIA` | Sem correspondência em `dim_client`. Cliente não cadastrado ou inativo. |

### Pastas internas / sem cliente

`ADMIN`, `LOGOS NEWAD`, `MKT NEWAD`, `NEWAD`, `PLANILHAS`, `REPORTS`, `SIPROCAL`

### Pastas sem match em dim_client (provavelmente clientes históricos inativos)

`AGÊNCIA 18`, `ANA GAMING`, `CASSINO`, `CERPA`, `KOMUH`, `MASTERCARD`, `PI PARCEIROS`, `RINO`, `TRALALÁ`

---

## Regras de seleção de arquivo

O script percorre `CLIENT / ANO / MÊS / PLANO /` procurando `.xlsx`. Quando há múltiplos arquivos na mesma pasta PLANO:

### Regra 1 — Prioridade pelo nome (oficial vs pessoal)

Tokens de nomes pessoais definidos em `PERSONAL_NAME_TOKENS = {"RAFA", "GESSIANE"}`.

- Se existir pelo menos um arquivo **sem** token de pessoa → considera apenas os oficiais
- Se **só** existir arquivos com nome de pessoa → usa como fallback

### Regra 2 — Mais recente entre os candidatos

Entre os arquivos selecionados na Regra 1, pega **somente o mais recente** por `modifiedTime` do Drive.

**Motivação:** evita duplicação quando existem múltiplas versões (V2 e V3 na mesma pasta) ou mesmo arquivo renomeado de espaços para underlines.

```python
official = [f for f in xlsx_files if not _has_personal_name(f["name"])]
candidates = official if official else xlsx_files
xlsx_f = max(candidates, key=lambda f: f["modifiedTime"])
```

### Regra 3 — Skip por modifiedTime (dedup de sync)

Antes de baixar, compara `modifiedTime` do Drive com `MAX(snapshot_at)` da raw para aquele `source_file`. Se não foi modificado desde o último sync → skip.

---

## Parsing de arquivos Excel (.xlsx)

**Biblioteca:** `openpyxl` com `data_only=True`

### Estrutura esperada das planilhas

Cada aba representa um **voo** (flight period). O nome da aba ou célula A1 contém o label, ex:
- `PLANO 11 MAI A 10 JUN`
- `1º MAI A 10 MAI`
- `PLANO 11 JUN A 10 JUL`

Abas ignoradas (`SKIP_SHEETS`): `RESUMO`, `SUMMARY`, `SUGESTAO`, `SUGESTÃO`, `INDICADORES`, `TEMPLATE`, `COPIA`, `CÓPIA`, `COPY`

### Parsing do flight label → datas

```python
def parse_flight_label(label, default_year=2026):
    # Regex: r"(\d{1,2})\s+([A-Z]{3,})\s+A\s+(\d{1,2})\s+([A-Z]{3,})"
    # "PLANO 11 MAI A 10 JUN" → flight_start=2026-05-11, flight_end=2026-06-10
    # Sem padrão → retorna (None, None) → linha entra na raw mas não no core
```

### Mapeamento de colunas (header detection)

Primeira linha com ≥ 2 colunas reconhecíveis é o header.

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

### Detecção de spend_type (gross vs net)

Baseada no `unit_price` máximo das linhas com `impressions_cpm` preenchido:
- `max > 5.0` → `spend_type = 'gross'` (preços brutos, ex: R$10, R$12 CPM)
- `max ≤ 5.0` → `spend_type = 'net'` (preços líquidos de tabela, ex: R$1.00 CPM)

### Detecção de plataforma por nome de estratégia (`PLATFORM_RULES`)

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

---

## RAW Layer — `raw.io_plan_drive_snapshot`

**Write mode:** `WRITE_APPEND`
**DDL:** `raw/ddl/io_plan_drive_snapshot.sql`

### Schema

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

---

## STG Layer — `stg.io_plan` ✅ CRIADA E VALIDADA (2026-06-24)

Substitui a `stg.io_plan_drive` antiga (arquivada em `stg/ddl/_legacy/io_plan_drive.sql` — tinha um bug: forçava `Push` sempre = `siprocal`, contradito pelo dado real `"Push - MGID"`).

**Grain:** `(client_id, drive_folder, strategy_name, flight_start)`, dedup pelo snapshot mais recente (`ROW_NUMBER` por `snapshot_at DESC`). Filtra linhas sem `flight_start`/`flight_end`/`monthly_spend`.

**`formato`** extraído de `strategy_name` (texto livre da planilha) via busca de keyword — vocabulário igual ao de entrega (`Display/Video/Retargeting/Native/Push`) + `AppInstall` (exclusivo do plano). **Não reusa o campo `format` já existente na RAW** (esse vem da planilha em vocabulário diferente, ex: `"Banner IAB"`, `"Push Banner"` — preservado como `creative_format_label`).

**Sem `goal_type`** — decisão do usuário (2026-06-24): `goal_type` é conceito de campanha/entrega (`ms_campaigns`/`mg_campaigns`/`sp_campaigns`), não de planejamento. `core.dict_format` ganhou `AppInstall`→`CPI` (`platform='io_plan'`) mesmo assim, pra ficar disponível quando algum consumidor precisar cruzar plano com entrega.

**`platform`** corrigido em relação à RAW (sem mudar o parser `sync_drive.py`): `PLATFORM_RULES` procura substring exata `"push siprocal"`, que não bate com o dado real `"Push - App Targeting SIPROCAL"` (texto no meio) — 91/295 linhas caíam em `unknown`. Fix na STG: `contém 'SIPROCAL' → siprocal`, `contém 'MGID' → mgid`. Resolve 7/91. **Os outros 84 (`Push`/`AppInstall` genéricos) não têm sinal de plataforma no texto — limitação real do dado.**

**Resultado real:** dedup reduz 295→**125 linhas**. **125/125 (100%) com `formato`. 96/125 (77%) com `platform` resolvido.** DDL: `stg/ddl/io_plan.sql`.

**Confirmado nesta sessão:** RAW tem grupos com até 14 snapshots idênticos da mesma linha de plano (7 cópias por sync, 2 syncs) — bug do parser (L1, ver abaixo) ainda presente. STG mascara corretamente via dedup (0 duplicatas confirmadas no resultado final), mas o parser não foi corrigido na fonte.

⚠️ **`gold.fact_io_plan` ainda não foi atualizada** para consumir `stg.io_plan` — hoje deriva de `core.io_plan_manual`, que por sua vez ainda lê de `raw.io_plan_drive_snapshot` direto (não passa pela STG nova). Revisar a cadeia completa ao reconstruir o Gold.

---

## Core Layer — `core.io_plan_manual`

**Write mode:** DELETE por `client_id + plan_version='DRIVE-SYNC'` + INSERT
**Grain:** `client_id + flight_start + flight_end`

### Schema

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

### Lógica de rebuild

1. Remove todas as linhas `DRIVE-SYNC` do cliente
2. Lê a snapshot mais recente de cada `source_file` da raw (evita reprocessar syncs antigos)
3. Aplica `DISTINCT` para eliminar linhas idênticas quando o mesmo arquivo aparece em múltiplos meses do Drive
4. Agrega por `flight_start + flight_end + spend_type`
5. Pivota gross/net; impressões preferem a versão net quando disponível

### Origem de dados por cliente (exemplo Cora)

| plan_version | Origem | Período | Observação |
|---|---|---|---|
| `PLANO-JAN-MAR` | `Plano NEWAD CORA JAN-MAR 2026.xlsx` | Jan–Mar/26 | Só gross mensal; sem estratégia nem impressões |
| `PLANO-ABR-AJUSTADO` | `Plano NEWAD CORA ABR AJUSTADO 2026.xlsx` | Abr/26 | Tem impressões e clicks totais |
| `DRIVE-SYNC` | múltiplos arquivos Mai–Ago/26 | Mai–Ago/26 | Gerado pelo rebuild automático |

---

## Gold Layer — `gold.fact_io_plan`

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

---

## Auditoria Cora: CONSOLIDADO GERAL vs BQ (2026-06-14)

Sheet de relatório diário do Rafa (`spreadsheet_id: 1Y94CavDyMXnIy9sLyqcTP8yKdANiQ1j1RzZBzHi7YHk`, tab `CONSOLIDADO GERAL`) cruzada com `core.io_plan_manual`.

### Valores projetados na sheet (invest. projetado acumulado no mês)

| Mês | Invest Proj (R$) | Dias cobertos |
|---|---|---|
| Jan/26 | ~35.400 | 25 (começa dia 7) |
| Fev/26 | ~35.001 | 28 |
| Mar/26 | ~35.000 | 31 |
| Abr/26 | ~60.001 | 30 |
| Mai/26 | ~65.846 | 31 |
| Jun/26 | ~25.403 | 10 (até dia 10) |

### Comparação com core.io_plan_manual

| Voo (core) | planned_spend_gross | Status |
|---|---|---|
| Jan/26 | R$ 35.000 | ✅ bate |
| Fev/26 | R$ 35.000 | ✅ bate |
| Mar/26 | R$ 35.000 | ✅ bate |
| Abr/26 | R$ 60.000 | ✅ bate |
| 01–10 Mai | R$ 25.000 | ✅ bate |
| 11 Mai–10 Jun | R$ 157.500 | ❌ deveria ser R$ 78.750 — duplicação (ver L2) |
| 11 Jun–10 Jul | R$ 63.000 | ⚠️ a verificar após fix L2 |
| 11 Jul–10 Ago | R$ 94.500 | ⚠️ a verificar após fix L2 |

**Nota:** CONSOLIDADO GERAL não é o IO plan source — é o relatório de performance diária (real vs projetado) mantido manualmente. Os nomes de estratégia divergem (`DISPLAY` na sheet vs `Mídia Progrm. - Display` na raw) e os períodos não coincidem com meses calendário.

---

## Limitações conhecidas

### L1 — `flight_start/flight_end` NULL para arquivos sem padrão de data na aba

O parser só extrai datas quando a aba tem o padrão `DD MÊS A DD MÊS`. Planilhas com nomes de aba livres (`JAN-MAR 2026`, `RESUMO`) têm todas as linhas com NULL e **não entram no core**. Impacta principalmente o histórico de 2025 e o Plano NEWAD_CORA 2026 V2 (368 rows, todas NULL).

**Fix possível:** fallback usando `drive_folder` (`2026/JANEIRO` → Jan 1–31) para planilhas de mês único. Multi-mês exige cuidado.

### L1b — Duplicação de linhas por sync (raiz: parser itera abas sem filtrar pelo mês) — CONFIRMADO AINDA PRESENTE (2026-06-24)

`parse_xlsx` em `sync_drive.py` itera `wb.sheetnames` sem filtrar pela aba certa do `drive_folder` — duplica cada linha de estratégia por sync. Verificado nesta sessão: grupos com até **14 snapshots idênticos** da mesma linha (`client_id+drive_folder+strategy_name+flight_start`) — na prática **7 cópias por sync**, em 2 syncs (não 14 syncs genuínos). Mesmo `source_file`/`monthly_spend`/`impressions` em todas as cópias.

**Impacto:** `raw.io_plan_drive_snapshot` infla com lixo (295 linhas reais → não sabido quantas seriam sem duplicação). `stg.io_plan` mascara corretamente via dedup (`ROW_NUMBER` por snapshot mais recente — confirmado 0 duplicatas no resultado final), mas o parser não foi corrigido na fonte. Fix fica pendente — não bloqueia consumo via STG.

### L2 — Duplicação de valores quando há múltiplos arquivos para o mesmo período (RESOLVIDA PARCIALMENTE)

Antes de 2026-06-14, `find_plano_files` pegava todos os xlsx, incluindo RAFA + cópias renomeadas. O core somava todos, resultando em múltiplos do valor real (R$157.500 ao invés de R$78.750 para o período 11 Mai–10 Jun Cora).

Fix deployado em `ff9dfe2`: regra "mais recente por pasta". Próximo sync de Cora reconstruirá o core com valor correto.

### L3 — `spend_type` detection imprecisa para planilhas misto

Planilhas com linhas CPM e CPC na mesma aba: `max(unit_price_cpm)` pode misturar taxas de CPC em colunas de CPM. Resultado: `spend_type` pode ser classificado como `net` quando é `gross`.

### L4 — Sem breakdown de estratégia no core e gold (PARCIALMENTE RESOLVIDA — 2026-06-24)

`core.io_plan_manual` agrega todas as estratégias em uma linha por voo — ainda assim. Mas agora existe `stg.io_plan` com grain por estratégia (`formato`/`goal_type` incluídos) — para análise por formato (Display vs Native), consultar `stg.io_plan` em vez da raw direto. `core`/`gold` continuam agregados; decidir se vale a pena dar grain de estratégia a eles também ao reconstruir o Gold.

### L5 — `planned_spend_net` NULL para a maioria dos clientes

Populado apenas quando há arquivo com `unit_price ≤ R$5` (preço líquido). Maioria dos clientes só tem versão bruta.

### L6 — `POST /sync` retorna 500 no Cloud Run admin

`services/io-plan-admin/main.py` usa `await request.form()` mas `python-multipart` está ausente de `requirements.txt`. Sync precisa ser disparado via CLI.

---

## Mapa de arquivos

| Arquivo | Descrição |
|---|---|
| `scripts/io_plan/sync_drive.py` | Script principal: `CLIENT_MAP`, `PERSONAL_NAME_TOKENS`, `find_plano_files`, `parse_xlsx`, `rebuild_core_for_client` |
| `services/io-plan-admin/main.py` | Cloud Run FastAPI — `POST /sync` |
| `services/io-plan-admin/requirements.txt` | ⚠️ Falta `python-multipart` |
| `raw/ddl/io_plan_drive_snapshot.sql` | DDL canônico da tabela raw (21 campos) |
| `docs/io_plan_pipeline.md` | Este documento |

---

## Próximos passos

1. **Fix `python-multipart`** — adicionar a `services/io-plan-admin/requirements.txt` e redeployar.

2. **Primeiro sync dos 12 clientes novos** — rodar `python sync_drive.py` para popular raw + core de Aperam, Catálise, Daxx, Dooing, Einstein, Luckbet, Mopar, MRV, Ocupacional, Patio Medeiros, Stocco, 7K.

3. **Validar fix de duplicação (L2)** — após próximo sync de Cora, confirmar que `11 Mai–10 Jun` mostra R$78.750 no core.

4. **Resolver LABTOLAB PARDINI** — confirmar se é `pardini_60395024`, `lab2lab_efb1cb34` ou ambos.

5. **Cadastrar PHISALIA em dim_client** — quando houver clareza, adicionar ao dim_client e ao `CLIENT_MAP`.

6. **Fix flight_start NULL (L1)** — implementar fallback de data via `drive_folder` para planilhas sem padrão de data na aba.

7. **Avaliar breakdown de estratégia no core** — decidir se `core.io_plan_manual` deve ter grain `client_id + flight + strategy_name` para análise por plataforma no gold.
