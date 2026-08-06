# Mapa de objetos `gold.*` que alimentam o relatório do Cora

> **⚠️ BEST-EFFORT — NÃO É REGRA DE BLOQUEIO AINDA.**
> Este levantamento foi feito 100% a partir do código commitado neste repo e de
> consultas ao BigQuery ao vivo — **não temos acesso ao arquivo `.pbix` real do
> Power BI da Cora**, então não é possível confirmar com certeza absoluta quais
> tabelas/views o relatório de fato consome hoje (pode ter campos calculados,
> relacionamentos ou fontes adicionais que só existem dentro do `.pbix`).
> **Antes de usar esta lista para bloquear/gatilhar qualquer coisa em produção
> (ex: um gate de "não promover mudança em X sem revisão"), valide diretamente
> com o Douglas** — ele tem acesso ao arquivo real e pode confirmar/corrigir.
>
> Client_id de referência usado nesta investigação: `banco_cora_fe13d78a`
> (o mesmo usado em `hub/ddl_historical_overrides.sql` e em
> `core/ddl/advertiser_platform_rules.sql`). Ver seção **"Achado colateral"**
> abaixo — existe um SEGUNDO identificador de Cora no repo
> (`nwd_banco-cora_acfae3ab` / `nwd_banco-cora_a...`) usado em objetos
> diferentes, e não ficou claro nesta investigação se são a mesma entidade
> vista por dois sistemas ou coisas genuinamente distintas.

---

## Confirmado (evidência direta em código)

| Objeto | Evidência | Papel |
|---|---|---|
| `gold.vw_fact_delivery_reporting` | `hub/ddl_historical_overrides.sql` — `WHERE client_id = 'banco_cora_fe13d78a'` explícito nas duas pernas do `UNION ALL` | View "pública" de entrega — combina `gold.fact_delivery` (dado do pipeline padrão) com `core.historical_overrides_delivery` (override manual Jan-Jun/2026 da Cora) por trás de uma única view. Este é o objeto mais provável de ser a fonte direta do relatório, já que foi criado especificamente para a Cora ter uma série histórica contínua. |
| `core.historical_overrides_delivery` | Mesma origem acima — tabela alvo do override, filtrada por `client_id = 'banco_cora_fe13d78a'` na consulta | Dado histórico da Cora (Jan-Jun/2026) carregado manualmente porque o pipeline padrão não cobria esse período. Só relevante para a Cora hoje (fluxo fechado e pontual, conforme comentário no próprio arquivo). |
| `gold.fact_delivery` | Fonte de `vw_fact_delivery_reporting` (perna sem override, `day >= '2026-07-01'`) | View client-agnostic, grain client+day+campaign+category — alimenta a Cora só como um client_id entre outros. |
| `core.vw_platform_campaign_links` | Comentário no próprio DDL (`core/ddl/vw_platform_campaign_links.sql`): "Criada ao vivo no BigQuery em 2026-07-29 ... para resolver erro de schema no Power BI da Cora" | View de conveniência sobre `core.platform_client_links` (filtro `link_type='campaignid'`) — existe especificamente para o Power BI conseguir consumir sem quebrar de schema. Confirmado pelo próprio autor do commit que é consumida pelo Power BI da Cora (memória de sessão de auditoria 2026-07-29). |

## Provável, não confirmado

| Objeto | Por que é candidato | Por que não está confirmado |
|---|---|---|
| `gold.fact_pacing` | Grain client+day+category — é o objeto natural para qualquer aba de pacing/orçamento no relatório, e a Cora tem IO Plan cadastrado (Power BI conectado ao gold BQ, `investimento_realizado` já era discutido na sessão de 2026-07 conforme memória do projeto) | Nenhuma referência explícita a `client_id='banco_cora_fe13d78a'` encontrada no código para este objeto especificamente — é genérico como os demais fatos gold. |
| `gold.fact_io_plan` | Mesma lógica — fonte de `fact_pacing`, mesmo grain de plano | Idem — genérico, sem filtro de client_id no código. |
| `core.dim_client` / `core.platform_client_links` (tabela base, não só a view) | Prováveis fontes de dimensão (nome do cliente, mapeamento plataforma↔campanha) para qualquer relatório por cliente | Não encontrada referência direta ao Power BI da Cora especificamente; é inferência por papel arquitetural. |

## Achado colateral — investigar antes de fechar a lista

Durante a busca por `cora` no repo (não só pelo client_id exato), apareceram
objetos com um **client_id diferente** do usado acima:

- `gold/delivery/fct_cora_delivery_full.sql` — view nomeada explicitamente
  para a Cora, criada como *"MVP workaround for Cora delivery gap"*.
- `gold/delivery/fct_newad_fintech_daily.sql` — comentário: *"Estrutura
  idêntica à fct_newad_bet_daily, com dados da Cora"*. Filtra por
  `newad_client_id = 'nwd_banco-cora_acfae3ab'` (não `banco_cora_fe13d78a`).
- `gold/dimensions/dim_client_semantics.sql` — usa o mesmo id
  `nwd_banco-cora_acfae3ab` para mapear os campos de conversão da Cora.

**Dois pontos de atenção que não deram pra resolver só com o código:**

1. **Dois identificadores de Cora coexistem no repo** (`banco_cora_fe13d78a`
   vs `nwd_banco-cora_acfae3ab`). Podem ser o mesmo cliente visto por dois
   sistemas (ex: `newad_client_id` do Admin UI/aat_console vs `client_id`
   interno do pipeline gold — os dois convivem no projeto conforme
   `CLAUDE.md` da raiz), ou podem ser coisas genuinamente diferentes. Não
   confirmar isso antes de usar qualquer objeto do bloco "achado colateral"
   como parte da lista oficial.
2. **`fct_newad_fintech_daily.sql` lê de `stg.io_lines_v4`** — nome que
   bate com o padrão já documentado na memória do projeto como território
   exclusivo do Admin UI do Shiro ("views v4" — ver regra em
   `feedback_core_separation`, também repetida no `CLAUDE.md` deste repo
   como não referenciar objetos do Admin UI no pipeline gold). Se isso for
   de fato uma referência a um objeto do Admin UI dentro de uma view gold
   deste pipeline, é uma violação da separação já documentada — mas pode
   também ser um artefato de uma fase de MVP anterior à reestruturação
   (essas 3 views ficam fora de `gold/ddl/`, na pasta solta `gold/delivery/`
   e `gold/dimensions/`, o que sugere que podem não fazer parte do pipeline
   "oficial" versionado hoje). **Não mexi em nada disso — só sinalizando
   para o Douglas decidir se essas views ainda estão ativas, são lixo de
   MVP anterior, ou precisam de correção.**

## O que não foi possível verificar

- Se o `.pbix` da Cora consome os objetos acima diretamente ou através de
  alguma camada intermediária (export CSV, extrato manual, etc.).
- Se `gold/delivery/fct_cora_delivery_full.sql` e
  `gold/delivery/fct_newad_fintech_daily.sql` ainda são objetos vivos no
  BigQuery (existe DDL commitado, mas não confirmei se o `CREATE OR REPLACE`
  mais recente rodado em produção é este ou uma versão posterior/anterior).
- Qualquer relacionamento ou coluna calculada definida só dentro do Power BI
  (fora do alcance de uma investigação só de código/BQ).

---

*Levantamento feito em 2026-08-05, como parte da construção do "Nível 2 de
teste" (infraestrutura `_test` + `apply_ddl.py`) para o MVP de segurança do
go-live do Cora. Ver `scripts/deploy/apply_ddl.py` e
`core/ddl/schema_change_log.sql`.*
