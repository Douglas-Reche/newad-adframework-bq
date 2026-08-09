---
status: aceito
last_verified: 2026-08-04
---

# 0001 — Versionamento SCD2 das tabelas de regra via funções `core.resolve_*` centralizadas

> **Manutenção:** Imutável após aceito — decisão superada vira novo ADR que referencia este.

**Status:** Aceito
**Data:** 2026-08-04

## Contexto

As tabelas de regra de negócio do `core` (`core.dict_format`, `core.campaign_format_map`,
`core.advertiser_platform_rules`) eram joinadas pelas views STG/gold sempre pelo estado
**atual** da regra, sem filtro de data. Como toda a camada gold é `CREATE OR REPLACE VIEW`
(nada materializado), mudar uma regra hoje reinterpretava silenciosamente todo o histórico
já reportado — não havia como reproduzir "o que o dashboard mostrava em março" usando a
regra vigente em março. Achado original e investigação completa: task Notion "Analisar
resiliência e rastreabilidade da camada Gold".

## Decisão

Adotar o padrão SCD2 (`effective_from`/`effective_to`) nas 3 tabelas de regra, e em vez de
repetir o JOIN versionado em cada view que precisa da regra, centralizar a lógica em 3
funções SQL reutilizáveis:

- `core.resolve_dict_format(platform, formato, as_of_date)`
- `core.resolve_dict_format_fallback(formato, as_of_date)`
- `core.resolve_platform_rule(client_id, platform_from, formato, as_of_date)`

Motivo duplo: (1) a primeira tentativa de fazer o JOIN versionado inline numa view, via
`ROW_NUMBER() OVER()` numa CTE multi-referenciada, causou um bug real de não-determinismo
do BigQuery (ver Consequências) e foi revertida antes de ir pra produção; (2) views futuras
que precisem da mesma regra só chamam a função em vez de reimplementar o JOIN — reduz risco
de gap de cobertura (foi assim que a limitação registrada em `docs/known_issues.md` V2 foi
descoberta).

## Alternativas consideradas

**JOIN versionado inline em cada view consumidora (rejeitada):** primeira tentativa de
implementação, direto em `gold/ddl/fact_io_plan.sql`, usando uma CTE com
`ROW_NUMBER() OVER()` (sem `ORDER BY`) referenciada 3 vezes na mesma query para resolver a
chave versionada. Causou um bug real de não-determinismo do BigQuery — CTEs
multi-referenciadas não têm materialização única garantida, o que inflou a contagem de
linhas de 5.101 para 5.925 mantendo a mesma soma total (sintoma característico de linhas mal
agrupadas, não mal contadas). Revertida antes de qualquer coisa ir pra produção. Rejeitada
por dois motivos: (1) o bug em si, e (2) mesmo corrigido, essa abordagem obrigaria
reimplementar o mesmo JOIN em toda view futura que precisasse de qualquer uma das 3 regras —
foi essa repetição, aliás, que expôs a limitação das 3 views de dimensão
(`known_issues.md` V2) só depois de já ter sido escrita uma vez.

Manter o JOIN sem versionamento (status quo) também era tecnicamente uma alternativa, mas
não é uma opção real considerada — é o próprio problema que motivou a investigação (task
Notion "Analisar resiliência e rastreabilidade da camada Gold").

## Consequências

`gold/ddl/fact_io_plan.sql` foi reescrito para usar `core.resolve_platform_rule` em vez de
JOIN direto. Swap feito ao vivo na view real, validado com `EXCEPT DISTINCT` nos dois
sentidos + agregados (COUNT, SUM spend/impressions/clicks, COUNTIF goal_type NULL)
idênticos à baseline (2 execuções `--nouse_cache`, tolerância de 6 casas decimais).

Três limitações reais do BigQuery foram confirmadas empiricamente no processo, relevantes
para qualquer função `resolve_*` futura:

- `LIMIT 1` dentro de subquery de SQL UDF não decorrelaciona corretamente — usar agregação
  (`MIN`/`MAX`) em vez.
- `ANY_VALUE()` é não-determinístico entre execuções — mesma razão, usar `MIN`/`MAX`.
- Comparação exata de `FLOAT64` falha por ruído de ponto flutuante distribuído do
  BigQuery (não é bug de lógica) — usar `ROUND(..., N)` em comparações de regressão.

**Limitação conhecida, não corrigida por este ADR:** `stg.ms_campaigns`, `stg.mg_campaigns`,
`stg.sp_campaigns` resolvem `goal_type` via `core.dict_format` em grain de campanha (1 linha
por `campaign_id`), sem coluna de data utilizável para o filtro de versionamento —
`sp_campaigns` não tem nenhuma coluna de data, e `start_date` em `ms`/`mg_campaigns` é
anterior ao piso de backfill do pipeline. Ver `docs/known_issues.md` V2. Correção fica para
trabalho futuro: mover/duplicar o JOIN (via `core.resolve_dict_format`, já pronta) para
dentro de `ms_delivery.sql`/`mg_delivery.sql`/`sp_delivery.sql`, que têm `date` real por
linha.

Ver: task Notion "Analisar resiliência e rastreabilidade da camada Gold" (narrativa completa
da investigação e decisão). Ver: `CHANGELOG.md` 2026-08-04.
