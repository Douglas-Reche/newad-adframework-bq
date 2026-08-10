# Gold Layer — Design (2026-06-24)

> **Manutenção:** Tier 1 (seção "Inventário Atual" — gerada a partir de consulta ao vivo no `INFORMATION_SCHEMA`, nunca editada de memória) + Tier 2 (seção "Design e Racional" — escrita à mão, gatilho: nova view gold ou mudança de grain/trade-off financeiro).

> Reconstrução pós-rebuild RAW+STG (2026-06-24). Reaproveita o princípio de negócio decidido em 16/06 (`project_gold_layer_design.md`), adaptado ao schema novo — `client_id`/`formato` já vêm resolvidos da STG, sem necessidade de re-derivar nada aqui.

> **Nota de manutenção (2026-08-08):** este doc tem duas seções. "Design e Racional" (abaixo) é a narrativa mantida à mão — grains, trade-offs, por que as coisas são como são. "Inventário Atual" (fim do arquivo) é gerado a partir de consulta ao vivo no `INFORMATION_SCHEMA` do BigQuery, não editado de memória. Uma auditoria de docs em 2026-08-08 encontrou que esta seção de design só cobria 5 das 9 views reais de `adframework.gold` — o inventário no fim do arquivo corrige isso e é o que deve ser regenerado (não editado à mão) na próxima vez que alguém desconfiar que está desatualizado.

## Design e Racional

## Princípio financeiro fundamental (decidido 2026-06-16, mantido)

> **Tudo financeiro = IO Plan. Tudo volume = plataforma.**

- `investimento_realizado` (atualizado 2026-06-24, fórmula confirmada pelo usuário) = volume real × `unit_price` do plano:
  - `CPM`: `(impressions_realizadas × unit_price) / 1000`
  - `CPC`: `(clicks_realizadas × unit_price) / 1000`
  - **Não** é spend real da API (MS/MGID/Siprocal não expõem custo, fora de escopo do rebuild RAW) — é uma estimativa via preço negociado do plano aplicado ao volume real entregue.
- `investimento_projetado` = `SUM(planned_spend_daily)` do voo completo
- Cliente nunca vê spend real da plataforma — só o estimado via plano

## Ligação plano ↔ entrega: por `client_id + formato + platform + dia`, NÃO por `campaign_id`

O IO Plan (`stg.io_plan`) nunca especifica qual campanha — só cliente + estratégia (`formato`) + período (voo). A ligação correta é `client_id + formato + platform + dia-dentro-do-voo` (`platform` adicionado em 2026-06-24, ver achado abaixo). Se houver N campanhas do mesmo `formato`/`platform` rodando no mesmo dia pro mesmo cliente, a entrega é agregada **antes** do join — evita duplicar o planejado (mesmo risco já identificado em 16/06).

## Tabelas (todas VIEW por agora — migrar pra TABLE materializada só se performance exigir)

| Tabela | Grain | Fonte |
|---|---|---|
| `gold.dim_campaign` | `platform + campaign_id` | UNION `stg.ms_campaigns` + `stg.mg_campaigns` + `stg.sp_campaigns` |
| `gold.fact_delivery` | `client_id + day + platform + formato` | UNION `stg.ms_delivery` + `stg.mg_delivery` + `stg.sp_delivery`, agregado (sem `campaign_id`/`creative_id` no grain) |
| `gold.fact_io_plan` | `client_id + report_date + formato + platform` | `stg.io_plan` expandido por dia (`GENERATE_DATE_ARRAY`), com `unit_price` passthrough e `goal_type` via `core.dict_format` |
| `gold.fact_pacing` | `client_id + day + formato + platform` | `fact_io_plan FULL OUTER JOIN fact_delivery`, com `investimento_realizado` calculado (`CPM`/`CPC` × `unit_price`) |
| `gold.dim_advertiser` | `client_id` | View sobre `core.dim_client` — relacionamento + hierarquia pai-filho (`parent_client_id`) pro Power BI |

### Por que `platform` entra na granularidade do plano (não só `formato`)

Confirmado contra dado real (2026-06-24): `client_id+formato+dia` sozinho tem casos reais de 2 `unit_price` diferentes coexistindo (estratégias diferentes, plataformas diferentes, mesmo `formato`) — ex. TecPar `Push-MGID` (R$0,35) vs `Push-Siprocal` (R$0,80) simultâneos. Adicionar `platform` resolve isso (só sobra `AppInstall`, sem entrega real, sem impacto).

### Modelagem no Power BI — relacionamento + DAX, não join pré-computado (com 1 exceção)

`fact_io_plan` e `fact_delivery` se relacionam via `dim_advertiser` (com hierarquia pai-filho `parent_client_id` pro rollup TecPar→Amigo) e uma dimensão de calendário — **sem** join direto entre as duas fact tables pra métricas simples. **Excepcionalmente**, `investimento_realizado` continua precisando de SQL (`gold.fact_pacing`) porque cruza `unit_price`/`goal_type` (plano) com `impressions`/`clicks` (entrega) linha a linha — não é resolvível só com relacionamento de modelo.

### Por que `fact_io_plan` e `fact_pacing` coexistem (não é duplicação)

- **`fact_io_plan`** = planejado puro, com `client_id` real (sem nenhum remapeamento) — calendário de planejamento, útil pra uma aba "Plano de Mídia" do dashboard sem precisar de join com entrega.
- **`fact_pacing`** = `fact_io_plan` + `fact_delivery` cruzados, com `investimento_realizado` calculado — produto final pronto pra comparação planejado×realizado. `client_id` também real aqui (rollup TecPar→Amigo é responsabilidade do Power BI via hierarquia, não da SQL).
- Mesma lógica de `dim_campaign` coexistir com `fact_delivery` — uma é a fonte/dimensão, outra é o produto de consumo.

## Sequência de build

1. `gold.dim_campaign` — mais simples, sem agregação
2. `gold.fact_delivery` — UNION + agregação por dia/formato
3. `gold.fact_io_plan` — expansão por dia (a parte nova/complexa)
4. `gold.fact_pacing` — join final, testar contra dado real antes de fechar

## Notas

- `gold.dim_campaign`/`fact_delivery` antigos (schema pré-rebuild) — substituídos, não reaproveitar lógica de `docs/gold_layer_build_plan.md` (LEGADO)
- `core.dict_format` entra na Gold via `gold.fact_io_plan` (join `platform+formato → goal_type`, com fallback só por `formato`) — usado pra calcular `investimento_realizado` em `fact_pacing`. `goal_type` das `*_campaigns` da STG continua resolvido lá independentemente (não duplicado, fontes diferentes pro mesmo conceito)

---

## Inventário Atual (verificado ao vivo)

> **Verificado em 2026-08-08** contra `adframework.gold` via `INFORMATION_SCHEMA.COLUMNS`, `INFORMATION_SCHEMA.VIEWS` e `INFORMATION_SCHEMA.TABLE_OPTIONS` (projeto `adframework`, dataset `gold`). São **9 views reais** hoje — a seção "Design e Racional" acima documentou só as 5 originais do rebuild de 06/24; as 4 que faltavam (`fact_delivery_by_device`, `fact_delivery_by_size`, `fact_delivery_creative`, `vw_fact_delivery_reporting`) foram adicionadas depois e nunca chegaram a este doc até agora.
>
> **Nenhuma das 9 views tem `description` aplicada no BQ hoje** (nem a nível de tabela via `TABLE_OPTIONS`, nem a nível de coluna) — não havia nada para reaproveitar. As descrições abaixo foram escritas a partir da leitura do `view_definition` real de cada uma (`INFORMATION_SCHEMA.VIEWS`), não de suposição.
>
> **Regenerar esta seção, não editar de memória**, na próxima vez que houver dúvida se está desatualizada. Query de partida:
> ```sql
> SELECT table_name, column_name, data_type, ordinal_position
> FROM `adframework.gold.INFORMATION_SCHEMA.COLUMNS`
> ORDER BY table_name, ordinal_position;
>
> SELECT table_name, view_definition
> FROM `adframework.gold.INFORMATION_SCHEMA.VIEWS`;
> ```
> (Esse projeto de BQ não expõe `description` em `COLUMN_FIELD_PATHS`/`COLUMNS` nesta versão — para conferir descrição de campo, usar `bq show --format=json adframework:gold.<view>`.)

### `dim_advertiser`
Grain: `client_id`. View sobre `core.dim_client` — hierarquia pai-filho (`parent_client_id`) pro rollup no Power BI (ex. TecPar→Amigo).

| Campo | Tipo | Origem/lógica |
|---|---|---|
| client_id | STRING | `core.dim_client` |
| name | STRING | `core.dim_client` |
| sector | STRING | `core.dim_client` |
| status | STRING | `core.dim_client` |
| parent_client_id | STRING | `core.dim_client` — hierarquia pai-filho |
| client_level | INT64 | `core.dim_client` |

Status: ✅ validado em 2026-08-08 (schema real).

### `dim_campaign`
Grain: `platform + campaign_id`. UNION de `stg.ms_campaigns` + `stg.mg_campaigns` + `stg.sp_campaigns`, sem agregação.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| platform | STRING | literal por branch do UNION (`mediasmart`/`mgid`/`siprocal`) |
| campaign_id | STRING | STG por plataforma |
| client_id | STRING | STG por plataforma (já resolvido) |
| campaign_name | STRING | STG por plataforma |
| formato | STRING | STG por plataforma |
| goal_type | STRING | STG por plataforma (via `core.dict_format`, resolvido na STG) |
| status | STRING | STG por plataforma |
| start_date | DATE | STG por plataforma |
| end_date | DATE | STG por plataforma |

Status: ✅ validado em 2026-08-08 (schema real).

### `fact_delivery`
Grain: `client_id + day + platform + formato`. UNION de `stg.ms_delivery` + `stg.mg_delivery` + `stg.sp_delivery`, agregado (sem `campaign_id`/`creative_id`).

| Campo | Tipo | Origem/lógica |
|---|---|---|
| day | DATE | `date` renomeado por plataforma na STG |
| platform | STRING | literal por branch do UNION |
| client_id | STRING | STG (denormalizado) |
| formato | STRING | STG |
| goal_type | STRING | STG |
| impressions | FLOAT64 | `SUM(impressions)` |
| clicks | FLOAT64 | `SUM(clicks)` |
| conversions | FLOAT64 | `SUM()` das colunas de conversão por plataforma (MS: `conversions_1..5`; MGID: `conversions_interest+decision+buy`; Siprocal: idem padrão) |

Status: ✅ validado em 2026-08-08 (schema real).

**CTR não é materializado no Gold** — confirmado em 2026-08-09 via `INFORMATION_SCHEMA.VIEWS`
de `gold`/`core`/`marts`/`share` (projeto `adframework`), zero ocorrências da coluna `ctr`. O
cálculo (`SAFE_DIVIDE(clicks, impressions)`) existe só na STG (`stg.ms_delivery`,
`stg.sp_delivery`, `stg.mg_delivery`); `fact_delivery` não projeta essa coluna no `UNION ALL`.
Mais provável que o CTR consumido hoje seja uma measure DAX no Power BI
(`SUM(clicks)/SUM(impressions)`) lendo direto de `fact_delivery`/`fact_pacing` —
**não confirmado**, o `.pbix` não está neste repositório. Ver: task Notion
[Investigar onde CTR é calculado](https://app.notion.com/p/3b89d0f6219e81648307d0501424fcdd).

### `fact_delivery_by_device` — não coberta na versão anterior deste doc
Grain: `client_id + day + platform + formato + device_type (+ operating_system)`. UNION de `stg.ms_delivery_by_device` + `stg.mg_delivery_by_device`, agregado.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| day | DATE | `date` |
| platform | STRING | literal (`mediasmart`/`mgid`) |
| client_id | STRING | STG |
| formato | STRING | STG |
| goal_type | STRING | STG |
| device_type | STRING | STG |
| operating_system | STRING | só MediaSmart tem — MGID vem `NULL` (limite de 3 dimensões na API MGID, mesmo caveat já registrado no `raw_layer_design.md` para T6) |
| impressions | FLOAT64 | `SUM(impressions)` |
| clicks | FLOAT64 | `SUM(clicks)` |
| conversions | FLOAT64 | `SUM()` por plataforma (mesmo padrão de `fact_delivery`) |

Status: ✅ validado em 2026-08-08 (schema real, criada e populada em produção — sem DDL correspondente commitado em `gold/ddl/`, ver "Gaps de DDL" abaixo).

### `fact_delivery_by_size` — não coberta na versão anterior deste doc
Grain: `client_id + day + platform + formato + size`. MediaSmart faz `LEFT JOIN` com `raw.ms_creatives` para derivar `size` (`width x height` do criativo); MGID não tem dimensão física mensurável (formato nativo) e sempre recebe `'sem_dimensao'`.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| day | DATE | `date` |
| platform | STRING | literal (`mediasmart`/`mgid`) |
| client_id | STRING | STG |
| formato | STRING | STG |
| goal_type | STRING | STG |
| size | STRING | MS: `CONCAT(width, 'x', height)` de `raw.ms_creatives`, com `'sem_dimensao'` para `NATIVE`/`PUSH` ou quando width/height ausente/zero; MGID: sempre `'sem_dimensao'` — MGID é 100% nativo, sem dimensão IAB mensurável |
| impressions | FLOAT64 | `SUM(impressions)` |
| clicks | FLOAT64 | `SUM(clicks)` |
| conversions | FLOAT64 | `SUM()` por plataforma |

Status: ✅ validado em 2026-08-08 (schema real; DDL commitado em `gold/ddl/fact_delivery_by_size.sql`, commit `2b7855c`).

### `fact_delivery_creative` — não coberta na versão anterior deste doc
Grain: `client_id + day + platform + formato + creative_id`. UNION de MS (`stg.ms_delivery` + `raw.ms_creatives`), MGID (`stg.mg_delivery` + `raw.mg_teasers`) e Siprocal (`stg.sp_delivery`, sem ID estruturado — usa o próprio nome do criativo como id/nome/label).

| Campo | Tipo | Origem/lógica |
|---|---|---|
| day | DATE | `date` |
| platform | STRING | literal (`mediasmart`/`mgid`/`siprocal`) |
| client_id | STRING | STG |
| formato | STRING | STG |
| goal_type | STRING | STG |
| creative_id | STRING | STG (`d.creative_id`); Siprocal usa a coluna `criativo` (texto livre, sem ID estruturado — não confundir com creative_id numérico das outras plataformas) |
| creative_name | STRING | `raw.ms_creatives`/`raw.mg_teasers` via `LEFT JOIN`; Siprocal repete `criativo` |
| creative_label | STRING | `COALESCE(creative_name, creative_id)` — nunca vazio, cai pro ID quando não há nome |
| impressions | FLOAT64 | `SUM(impressions)` |
| clicks | FLOAT64 | `SUM(clicks)` |
| conversions | FLOAT64 | `SUM()` por plataforma; Siprocal sempre `0` (sem breakdown de conversão por criativo na fonte) |

Status: ✅ validado em 2026-08-08 (schema real, criada e populada em produção — sem DDL correspondente commitado em `gold/ddl/`, ver "Gaps de DDL" abaixo).

### `fact_io_plan`
Grain: `client_id + report_date + formato + platform`. `stg.io_plan` expandido por dia (`GENERATE_DATE_ARRAY`), com `unit_price` passthrough e `goal_type` via `core.dict_format`.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| client_id | STRING | `stg.io_plan` |
| report_date | DATE | expansão diária do voo (`GENERATE_DATE_ARRAY`) |
| formato | STRING | `stg.io_plan` |
| platform | STRING | `stg.io_plan` (adicionado 2026-06-24 na granularidade — ver "Por que `platform` entra na granularidade do plano" acima) |
| unit_price | NUMERIC | `stg.io_plan`, passthrough |
| goal_type | STRING | `core.dict_format` (join `platform+formato`, fallback só por `formato`) |
| planned_spend_daily | NUMERIC | `stg.io_plan` |
| planned_impressions_daily | FLOAT64 | `stg.io_plan` |
| planned_clicks_daily | FLOAT64 | `stg.io_plan` |

Status: ✅ validado em 2026-08-08 (schema real).

### `fact_pacing`
Grain: `client_id + day + formato + platform`. `fact_io_plan FULL OUTER JOIN fact_delivery`, com `investimento_realizado` calculado.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| client_id | STRING | `fact_io_plan`/`fact_delivery` |
| day | DATE | `fact_io_plan.report_date` / `fact_delivery.day` |
| formato | STRING | `fact_io_plan`/`fact_delivery` |
| platform | STRING | `fact_io_plan`/`fact_delivery` |
| planned_spend_daily | NUMERIC | `fact_io_plan` |
| planned_impressions_daily | FLOAT64 | `fact_io_plan` |
| planned_clicks_daily | FLOAT64 | `fact_io_plan` |
| unit_price | NUMERIC | `fact_io_plan` |
| goal_type | STRING | `fact_io_plan` |
| realized_impressions | FLOAT64 | `fact_delivery.impressions` |
| realized_clicks | FLOAT64 | `fact_delivery.clicks` |
| realized_conversions | FLOAT64 | `fact_delivery.conversions` |
| investimento_realizado | FLOAT64 | calculado: `CPM` → `(realized_impressions × unit_price) / 1000`; `CPC` → `(realized_clicks × unit_price) / 1000` — ver "Princípio financeiro fundamental" acima |

Status: ✅ validado em 2026-08-08 (schema real).

### `vw_fact_delivery_reporting` — não coberta na versão anterior deste doc
Grain: igual `fact_delivery` (`client_id + day + platform + formato`). **View de apresentação** que substitui, por override, os dias de `banco_cora_fe13d78a` anteriores a `2026-07-01` pelo valor de `core.historical_overrides_delivery` — mecanismo genérico de override histórico por cliente (ver `core/ddl/historical_overrides_delivery.sql`, `core/ddl/resolve_reporting_source.sql`, commit `98b8f50`). Fora do intervalo/cliente do override, é um passthrough puro de `fact_delivery`.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| client_id | STRING | `fact_delivery` ou `core.historical_overrides_delivery` |
| day | DATE | idem |
| platform | STRING | idem |
| formato | STRING | idem |
| goal_type | STRING | idem |
| impressions | FLOAT64 | idem |
| clicks | FLOAT64 | idem |
| conversions | FLOAT64 | `fact_delivery.conversions`; sempre `NULL` para as linhas vindas do override histórico (a fonte da Cora pré-07/2026 não tem conversão confiável) |

Regra do override, embutida na `WHERE`: exclui de `fact_delivery` linhas onde `client_id = 'banco_cora_fe13d78a' AND day < '2026-07-01'` e as substitui pelas equivalentes de `core.historical_overrides_delivery` — é a view "pronta para consumo" (Power BI deve ler daqui, não de `fact_delivery` direto, para clientes com override ativo).

Status: ✅ validado em 2026-08-08 (schema real, criada e populada em produção — sem DDL correspondente commitado em `gold/ddl/`, ver "Gaps de DDL" abaixo).

### Gaps de DDL — corrigido em 2026-08-08

Esta seção originalmente (auditoria de docs, mesma data) reportou 3 views em produção sem DDL correspondente no repo: `fact_delivery_by_device`, `fact_delivery_creative`, `vw_fact_delivery_reporting`. **Achado impreciso, corrigido na sequência**: `fact_delivery_by_device.sql` e `fact_delivery_creative.sql` já estavam commitados desde 2026-07-08 (commits `ab08e73` e `faa1b87`) — a auditoria comparou contra uma listagem desatualizada de `gold/ddl/`, não contra o estado real do diretório. Só `vw_fact_delivery_reporting` estava genuinamente ausente.

Estado real agora: **as 9 views têm DDL commitado em `gold/ddl/`** — `vw_fact_delivery_reporting.sql` criado nesta correção, com `view_definition` confirmada via `INFORMATION_SCHEMA.VIEWS` contra as 3 views (`fact_delivery_by_device`, `fact_delivery_creative`, `vw_fact_delivery_reporting`) antes de decidir o que faltava de fato. Nenhuma referencia objeto do universo Admin UI/Shiro (`io_manager_v2`, `io_line_bindings_v2`, `proposals`, `proposal_lines`, sufixo `_v4`) — todas as 3 usam exclusivamente `raw.*`/`stg.*`/`gold.fact_delivery`/`core.historical_overrides_delivery`. YAML irmão de descrição (Opção B, ver `scripts/docs/sync_gold_descriptions.py`) criado para as 3 junto com o `.sql`.
