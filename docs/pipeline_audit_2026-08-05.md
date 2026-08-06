# Auditoria completa — gold/* e core/* — dependências no Admin UI do Shiro

> **Fase A — só leitura de código, sem acesso ao BigQuery ao vivo.** Fase B (confirmar
> ao vivo se os objetos abaixo ainda existem/rodam em produção, e o que consomem de
> fato) fica para depois que o acesso for destravado.
>
> Motivo desta auditoria: `docs/client_dashboard_map.md` (2026-08-05) já tinha
> encontrado, numa segunda leitura manual, que `fct_cora_delivery_full.sql` faz JOIN
> direto com `core.io_binding_registry_v4` (Admin UI do Shiro) — um achado que o grep
> pontual por `client_id` da Cora não pegou. Esta auditoria lê **todo arquivo `.sql`**
> em `gold/*` e `core/*` (não só `*/ddl/`) para não deixar passar mais nada assim.

**Escopo lido, arquivo inteiro, nesta auditoria:**

| Pasta | Arquivos |
|---|---|
| `core/ddl/` | 13 arquivos (todos) |
| `core/migration/` | 9 arquivos (01 a 09, todos) |
| `core/OWNERSHIP.yaml` | 1 |
| `gold/ddl/` | 8 arquivos ativos (`dim_advertiser`, `dim_campaign`, `fact_delivery`, `fact_delivery_by_device`, `fact_delivery_by_size`, `fact_delivery_creative`, `fact_io_plan`, `fact_pacing`) |
| `gold/ddl/_legacy/` | 8 arquivos (verificados por referência a objetos Shiro — nenhuma encontrada) |
| `gold/delivery/` | 6 arquivos (todos — pasta fora do padrão `*/ddl/`) |
| `gold/creative/` | 1 arquivo (`fct_luckbet_creative_daily.sql`) |
| `gold/dimensions/` | 1 arquivo (`dim_client_semantics.sql`) |
| `hub/ddl_historical_overrides.sql` | 1 (lido para fechar a cadeia de `core.historical_overrides_delivery`, sem mexer em `hub/`) |

**Total: 39 objetos SQL revisados linha a linha** (não contando os 3 seeds `.csv`, que
não são SQL e foram só inspecionados por tamanho).

Cruzado contra: `core/OWNERSHIP.yaml`, `docs/known_issues.md`, `docs/client_dashboard_map.md`,
`docs/_legacy/id_dependency_map.md`, `CHANGELOG.md`.

---

## (a) Objetos gold/core que dependem, direta ou indiretamente, do Admin UI do Shiro

### A1 — `gold/delivery/fct_cora_delivery_full.sql` → `core.io_binding_registry_v4` (Shiro) — DIRETO

Já documentado (comentário no próprio arquivo, `docs/client_dashboard_map.md`,
`CHANGELOG.md` linha 3203: *"ainda referencia `core.io_binding_registry_v4` (Admin UI
do Shiro) — viola a separação de responsabilidades definida em 2026-05-26 (...)
não deve ser expandida"*). Confirmado nesta leitura: a view faz **LEFT JOIN e INNER
JOIN diretos** em `core.io_binding_registry_v4` em 3 CTEs (`mediasmart_delivery`,
`mgid_siprocal_registered`, `mgid_siprocal_registered_delivery`).

**Status:** ativo no código, workaround conhecido e já sinalizado como "não expandir".
Não é achado novo — já estava rastreado.

### A2 — `gold/delivery/fct_luckbet_delivery_full.sql` → `core.io_binding_registry_v4` (Shiro) — DIRETO, **NÃO documentado em CHANGELOG/known_issues como violação**

Mesmo padrão do A1, mesma data de criação (2026-05-20, ver CHANGELOG linha 3200), mas
o CHANGELOG só chama atenção para o `fct_cora_delivery_full` como violação — não
menciona explicitamente que `fct_luckbet_delivery_full.sql` faz o mesmo JOIN. Na
leitura desta auditoria: a view referencia `core.io_binding_registry_v4` em pelo menos
3 pontos (CTE `mediasmart_siprocal_delivery`, CTE `luckbet_io_campaign_ids` — duas
subqueries UNION DISTINCT — e CTE `mgid_siprocal_io_delivery`).

**Achado novo desta auditoria:** o CHANGELOG documentou a violação só para a Cora,
mas o Luckbet tem exatamente a mesma dependência e nunca foi listado como tal.

**Status:** ativo no código. Mesma classificação de risco do A1 — deveria estar na
mesma nota de "workaround legado, não expandir".

### A3 — `gold/delivery/fct_newad_fintech_daily.sql` → `stg.io_lines_v4` (Shiro) — DIRETO

Já documentado em `docs/known_issues.md` item #4 e sinalizado como possível violação
em `docs/client_dashboard_map.md` (seção "Achado colateral", ponto 2). Confirmado
nesta leitura: 2 CTEs (`cora_campaigns`, `io_context`) fazem `FROM
adframework.stg.io_lines_v4` direto, filtrando por `newad_client_id =
'nwd_banco-cora_acfae3ab'`.

`stg.io_lines_v4` **não tem DDL neste repo** (busquei em todo `stg/ddl/*` e
`stg/ddl/_legacy/*` — não existe). Rastreado até a raiz via
`docs/_legacy/id_dependency_map.md` (linha 84, 105): `stg.io_lines_v4` é "propagado do
io_manager" — ou seja, é uma tabela/view do pipeline do Admin UI do Shiro, só que vive
no dataset `stg` (não `core`), por isso **não está coberta pelo `core/OWNERSHIP.yaml`**
apesar de ser do mesmo sistema.

**Status:** ativo no código, já sinalizado como pendência de decisão em
`client_dashboard_map.md` — não é achado novo, mas esta auditoria confirma a raiz
completa da cadeia (ver achado B1 abaixo).

### A4 — `gold/delivery/fct_newad_bet_daily.sql`, `fct_luckbet_delivery_daily.sql`, `fct_delivery_daily_mvp.sql` → `share.io_calc_daily_v4` (Shiro) — DIRETO, **achado novo desta auditoria**

Nenhum destes 3 arquivos havia sido investigado antes (não aparecem em
`docs/client_dashboard_map.md`, que só olhou os objetos com `client_id` da Cora no
nome/filtro). Todos os 3 fazem `FROM adframework.share.io_calc_daily_v4` direto:

- `fct_newad_bet_daily.sql` (CTE `delivery_ranked`) — filtra `newad_client_id =
  'nwd_luckbet_a485d6bc'`
- `fct_luckbet_delivery_daily.sql` (CTE `delivery_ranked`) — mesmo filtro
- `fct_delivery_daily_mvp.sql` (CTE `ranked`) — **sem filtro de client_id** — lê a
  tabela inteira, todos os clientes, exclui só 2 IDs conhecidos como fantasma
  (`nwd_luckbet_69e72f18`, `nwd_internal_newad`)

`share.io_calc_daily_v4` também **não tem DDL neste repo** — não existe pasta `share/`
no repositório inteiro. Rastreado via `docs/_legacy/id_dependency_map.md` (linhas
108, 158-161): é a última camada de uma cadeia `marts.io_delivery_daily_v4 →
marts.io_calc_daily_v4 → share.io_calc_daily_v4`, todas do lado Shiro
(`marts`/`core` do Admin UI), exposta ao pipeline via dataset `share`.

**Por que isso é mais sério que A1-A3:** `fct_delivery_daily_mvp.sql` não filtra por
client_id nenhum — **toda a view depende inteiramente de uma tabela do Shiro**, não é
um workaround pontual por cliente. Se essa view ainda está ativa em produção (não
confirmado nesta Fase A), qualquer consumidor dela (Power BI, hub) está 100% exposto a
mudanças no sistema do Shiro sem nenhum aviso.

### A5 — `gold/creative/fct_luckbet_creative_daily.sql` → `gold.fct_creative_daily` (sem dono claro) — INDIRETO, achado novo

Este arquivo lê de `adframework.gold.fct_creative_daily` — que **não tem DDL neste
repo** (busquei `CREATE.*fct_creative_daily` e `CREATE.*fact_creative_daily` em todo o
repositório — zero resultados). Diferente dos casos A3/A4, não há evidência de que
`fct_creative_daily` seja do Shiro (não aparece em `id_dependency_map.md` nem em
`OWNERSHIP.yaml`) — é simplesmente um objeto **sem fonte de verdade versionada**,
mesma categoria de risco que os "shadow objects" já documentados para
`core.campaign_format_map` e `core.dict_format` (`docs/known_issues.md`, resolvido em
2026-08-04 para essas duas, mas não resolvido para `fct_creative_daily`).

**Status:** requer decisão do Douglas — não sei se `fct_creative_daily` é: (1) um
objeto do próprio pipeline nunca commitado (mesmo padrão do V1 já resolvido), (2) algo
do Shiro sem o padrão de nome `_v2`/`_v4` que o alertaria, ou (3) morto/substituído.

### A6 — `stg.io_lines_v4` e `share.io_calc_daily_v4` não estão no `core/OWNERSHIP.yaml` — lacuna de cobertura do arquivo de referência

O `OWNERSHIP.yaml` documenta explicitamente que cobre apenas o dataset `core`
("Fonte única de... é do Admin UI do Shiro... para o dataset `core`"). Mas os achados
A3/A4 mostram que o mesmo sistema do Shiro expõe objetos em **`stg`** (`io_lines_v4`)
e **`share`** (`io_calc_daily_v4`, e possivelmente `newad_operational_daily`,
`platform_daily_detail`, `newad_revenue_daily` — ver achado B1) que sofrem do mesmo
risco de "nunca deveria ser referenciado no pipeline gold", mas ninguém checa isso
porque o arquivo de referência não olha para esses datasets.

**Sinalizado para decisão do Douglas:** ou expandir `OWNERSHIP.yaml` para cobrir
`stg`/`share` também, ou criar um arquivo irmão para esses datasets — mas isso é
mudança de infraestrutura de auditoria, não uma correção de dado, então não fiz
sozinho.

---

## (b) Lista completa das dependências rastreadas até a raiz (achado B1)

Usando `docs/_legacy/id_dependency_map.md` (documento que a própria auditoria
qualifica como "LEGADO — pré-rebuild 2026-06-16", mas cujas cadeias de lineage batem
exatamente com os nomes de objeto que os 6 arquivos gold ativos hoje (A1-A4) ainda
consomem — ver incongruência C1 abaixo):

```
Firestore io_manager (Shiro)
  → raw_newadframework.io_manager_v2 / io_line_bindings_v2   [Shiro, dataset core]
  → stg.io_lines_v4                                           [Shiro, dataset stg]
  → core.io_binding_registry_v4 / io_registry_v4              [Shiro, dataset core]
  → marts.io_delivery_daily_v4 → marts.io_calc_daily_v4        [Shiro, dataset marts — não existe nem como pasta neste repo]
  → share.io_calc_daily_v4                                     [Shiro, dataset share — idem]
  → share.newad_operational_daily, share.platform_daily_detail,
    share.newad_revenue_daily                                  [Shiro, dataset share]

  ↓ consumido diretamente por:
gold.fct_cora_delivery_full        (core.io_binding_registry_v4)       — A1
gold.fct_luckbet_delivery_full     (core.io_binding_registry_v4)       — A2
gold.fct_newad_fintech_daily       (stg.io_lines_v4)                   — A3
gold.fct_newad_bet_daily           (share.io_calc_daily_v4)            — A4
gold.fct_luckbet_delivery_daily    (share.io_calc_daily_v4)            — A4
gold.fct_delivery_daily_mvp        (share.io_calc_daily_v4, SEM filtro de cliente) — A4
```

Nenhum destes 6 objetos tem, em si, DDL do lado Shiro commitado neste repo (nem
deveria — pertence ao outro sistema) — mas isso significa que **este repo não tem
como validar em CI/lint se o schema dessas fontes mudou**, diferente de tudo que vem
de `stg.*_delivery`/`stg.*_campaigns` (que são do nosso pipeline, com DDL aqui).

**Não rastreado até a raiz nesta Fase A** (precisa de acesso ao BigQuery ao vivo):
`gold.fct_creative_daily` (achado A5) — não sei se ele próprio depende de algo do
Shiro, porque não tem DDL em lugar nenhum para eu ler.

---

## (c) Arquivos fora do padrão de pastas (`*/ddl/`)

| Arquivo | Por que está fora do padrão | Status |
|---|---|---|
| `gold/delivery/fct_cora_delivery_full.sql` | Workaround MVP por cliente, não DDL genérico | Ativo, sinalizado (A1) |
| `gold/delivery/fct_luckbet_delivery_full.sql` | Idem | Ativo, sinalizado (A2) |
| `gold/delivery/fct_delivery_daily_mvp.sql` | "Fixed version" temporária de `fact_delivery_daily` | Ativo, sinalizado (A4) |
| `gold/delivery/fct_newad_fintech_daily.sql` | View "MVP Demo" com nomes de cliente mascarados para uso comercial | Ativo, sinalizado (A3) |
| `gold/delivery/fct_newad_bet_daily.sql` | Idem — vertical Bet, nomes mascarados | Ativo, sinalizado (A4) |
| `gold/delivery/fct_luckbet_delivery_daily.sql` | Espelho "não mascarado" do fintech/bet daily, mesma fonte `io_calc_daily_v4` | Ativo, sinalizado (A4) |
| `gold/creative/fct_luckbet_creative_daily.sql` | Mesmo padrão MVP, mas em pasta própria `creative/` (nem segue a convenção de `gold/delivery/`) | Ativo, sinalizado (A5) |
| `gold/dimensions/dim_client_semantics.sql` | Dimensão auxiliar solta em pasta própria — não é workaround de risco, mas também não está em `gold/ddl/` | Ativo, sem dependência Shiro — comportamento normal, só a localização é atípica |

**Padrão identificado:** todo arquivo fora de `*/ddl/` neste levantamento é, sem
exceção, um workaround "MVP"/"Demo"/"Fixed version" — nenhum deles é um objeto comum
que só foi mal arquivado. Isso é consistente com a hipótese do pedido original: pasta
fora do padrão = sinal confiável de "isto merece escrutínio". As 3 exceções de
`gold/ddl/` que também tocam regra especial (`fact_io_plan`, `fact_pacing` com a
lógica SCD2) **não** contam como fora do padrão — elas estão no lugar certo, só têm
comentários extensos.

---

## (d) Outras incongruências encontradas no caminho

### C1 — `docs/_legacy/id_dependency_map.md` está marcado "pré-rebuild, tabelas dropadas, não usar" — mas descreve exatamente as cadeias que os arquivos A1-A4 ainda usam hoje

O cabeçalho do documento diz: *"Tabelas, views, schemas e colunas aqui descritos
**foram dropados e não existem mais no BigQuery**... não use como referência para
desenvolvimento novo."* Mas os nomes exatos que ele documenta (`io_binding_registry_v4`,
`stg.io_lines_v4`, `share.io_calc_daily_v4`, `share.platform_daily_detail`,
`share.newad_operational_daily`) são os mesmos que os 6 arquivos gold **ativos hoje**
(datados de 2026-05-12 no git, e sem nenhuma indicação de terem sido substituídos)
consomem. Ou o aviso "dropado, não existe mais" está errado para essas tabelas
específicas do Shiro (só os objetos do NOSSO pipeline pré-rebuild foram de fato
dropados), ou os 6 arquivos gold estão quebrados em produção sem ninguém ter
percebido — **não dá para saber qual dos dois sem acesso ao BigQuery (Fase B)**.

**Isso é o achado mais importante desta auditoria para efeito de decisão do Douglas:**
o "Nível 2 de teste" que está sendo construído não tem como proteger contra essa
ambiguidade específica — testar `apply_ddl.py` num dataset `_test` não revela se uma
fonte **externa** (do lado Shiro) mudou ou sumiu.

### C2 — `gold.fct_creative_daily` sem DDL em lugar nenhum (retomando A5)

Mesma categoria dos "shadow objects" já resolvidos em 2026-08-04 para
`campaign_format_map`/`dict_format`, mas ainda não resolvida para este. Diferença
importante: não sei se está no `core` ou é do Shiro — precisa de
`INFORMATION_SCHEMA.TABLES`/`VIEWS` ao vivo (Fase B) para eu classificar com
confiança, não é algo que dá pra resolver só lendo código.

### C3 — Nenhuma referência a `core.proposals`/`core.proposal_lines`/`core.io_manager_v2`/`core.io_line_bindings_v2`/`core.io_manager_enriched_v2`/`core.io_registry_v4`/`core.io_line_bindings_enriched_v2` em `gold/*` nem `core/*` (fora do próprio `OWNERSHIP.yaml` e `known_issues.md`)

Verificação negativa registrada por completude: destes 7 objetos do Shiro listados em
`OWNERSHIP.yaml`, só **`io_binding_registry_v4`** é de fato referenciado (achados A1/A2).
Os outros 6 não aparecem em nenhum `.sql` de `gold/*` ou `core/*` além dos próprios
arquivos de documentação/ownership. Ou seja, o "vazamento" de Shiro no pipeline gold
está concentrado em 2 objetos do dataset `core` (`io_binding_registry_v4`) + 2 objetos
fora do `core` que o `OWNERSHIP.yaml` não cobre (`stg.io_lines_v4`,
`share.io_calc_daily_v4`) — não é um problema espalhado por todo o Admin UI, é
localizado nesses 4 pontos específicos.

### C4 — `core/ddl/` e `core/migration/` em si: nenhum achado novo

Todos os 13 arquivos `core/ddl/` e 9 `core/migration/` foram lidos inteiros — são
consistentes com `OWNERSHIP.yaml`, sem referência a objetos Shiro, sem incongruência
de nome vs. realidade além do que já está documentado em `known_issues.md` (drift de
schema em `dict_format`/`campaign_format_map`, já resolvido 2026-08-04). O
versionamento SCD2 recente (`resolve_dict_format`, `resolve_dict_format_fallback`,
`resolve_platform_rule`) está bem documentado inline, com histórico de bug real
(não-determinismo de `ROW_NUMBER()` em CTE referenciada 3×) registrado no próprio
arquivo — sem sinal de dívida técnica nova aqui.

---

## Resumo para decisão do Douglas

1. **A2 (Luckbet) precisa da mesma nota de "não expandir" que a Cora (A1) já tem** —
   isso é uma correção de documentação trivial, não uma mudança de comportamento;
   posso pedir para o `docs` atualizar `CHANGELOG.md`/`known_issues.md` assim que você
   confirmar.
2. **A4 é o achado que muda o quadro de risco**: `fct_delivery_daily_mvp.sql` depende
   inteiramente de `share.io_calc_daily_v4` (Shiro), sem filtro de cliente — se essa
   view ainda está em produção, é uma exposição bem maior que os workarounds
   client-specific já conhecidos. **Preciso de Fase B (BigQuery ao vivo) para saber
   se essas 6 views (A1-A4) ainda existem/rodam, e quem as consome hoje** (Power BI?
   hub? nada?) antes de decidir o que fazer.
3. **C1 é o achado mais importante estruturalmente**: o doc que mapeia essas cadeias
   está marcado como obsoleto, mas as cadeias em si parecem vivas. Preciso de
   confirmação sua sobre se essas 4 tabelas do Shiro (`io_binding_registry_v4`,
   `io_lines_v4`, `io_calc_daily_v4`, `platform_daily_detail`) ainda existem no
   BigQuery hoje, e se sim, se ainda são alimentadas pelo sistema do Shiro.
4. **A5 (`gold.fct_creative_daily` sem DDL)** — mesma pendência do padrão já resolvido
   para `dict_format`/`campaign_format_map`; só falta aplicar o mesmo tratamento
   (sincronizar DDL com `INFORMATION_SCHEMA` ao vivo) quando o acesso for destravado.
5. **A6** — decisão de escopo: expandir `OWNERSHIP.yaml` para cobrir `stg`/`share`,
   ou não? Sem isso, um objeto novo do Shiro nesses datasets pode voltar a vazar para
   o gold sem ninguém notar (foi exatamente assim que A3/A4 escaparam do
   `OWNERSHIP.yaml` atual).

Nenhuma mudança de código, DDL ou dado foi feita nesta sessão — só leitura e este
relatório, conforme escopo pedido.
