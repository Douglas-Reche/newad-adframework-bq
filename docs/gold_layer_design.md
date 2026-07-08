# Gold Layer — Design (2026-06-24)

> Reconstrução pós-rebuild RAW+STG (2026-06-24). Reaproveita o princípio de negócio decidido em 16/06 (`project_gold_layer_design.md`), adaptado ao schema novo — `client_id`/`formato` já vêm resolvidos da STG, sem necessidade de re-derivar nada aqui.

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
