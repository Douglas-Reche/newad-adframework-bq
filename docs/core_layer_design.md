# CORE Layer — Design

> **Manutenção:** Tier 1 (inventário — regenerar contra `INFORMATION_SCHEMA` quando
> desconfiar de desatualização) + Tier 2 (seção "Design e Racional" — gatilho: nova tabela
> `core` do pipeline, nova função `resolve_*`, ou mudança de regra de versionamento SCD2).

> Criado: 2026-08-09. RAW, STG e GOLD já tinham doc próprio (`raw_layer_design.md`,
> `stg_layer_design.md`, `gold_layer_design.md`) — CORE nunca teve, lacuna identificada no
> plano de reestruturação de documentação (item B9). Verificado ao vivo contra
> `adframework.core.INFORMATION_SCHEMA.TABLES`/`COLUMNS`/`ROUTINES` em 2026-08-09.

---

## Design e Racional

### O que é o dataset `core`

Diferente de RAW/STG (dado de plataforma, atualizado pelo ETL) e GOLD (agregação final
pro consumidor), `core` guarda **regra de negócio pequena, mantida manualmente** —
cadastro de cliente, vínculo plataforma↔cliente, tabelas de mapeamento/formato, e as
funções `resolve_*` que aplicam essas regras com versionamento por data. Nenhuma tabela
de `core` é escrita pelo ETL diário — todas mudam por ação manual (seed, correção pontual,
sync de um processo auxiliar como `sync_drive.py`).

**`core` também contém objetos de um sistema diferente — o Admin UI do Shiro** (ex:
`io_manager_v2`, `proposals`). Isso é documentado à parte, com a lista completa e o
critério de "nunca referenciar no pipeline gold", em `core/OWNERSHIP.yaml` — este doc
**não duplica essa lista**, só cobre os objetos `owner: pipeline`.

### Versionamento SCD2 nas tabelas de regra

`dict_format`, `campaign_format_map` e `advertiser_platform_rules` têm `effective_from`/
`effective_to` — decisão de 2026-08-04 (ver `docs/adr/0001-versionamento-scd2-regras-negocio-via-funcoes-resolve.md`)
para que uma correção de regra não reinterprete retroativamente o histórico já calculado.
Nenhuma dessas tabelas é lida por `UPDATE`/`JOIN` direto na GOLD — sempre através de uma
função `resolve_*(..., as_of_date)` que aplica o filtro de vigência (`effective_from <=
as_of_date AND (effective_to IS NULL OR as_of_date < effective_to)`).

### As 3 funções `resolve_*` em produção

| Função | Assinatura | O que resolve |
|---|---|---|
| `resolve_dict_format` | `(p_platform STRING, p_formato STRING, p_as_of_date DATE) → STRING` | `goal_type` vigente pra `(platform, formato)` na data `as_of_date`, lendo `core.dict_format` |
| `resolve_dict_format_fallback` | `(p_formato STRING, p_as_of_date DATE) → STRING` | Mesmo que acima, mas sem discriminar por `platform` — só retorna valor se **todas** as plataformas concordarem no mesmo `goal_type` pra aquele `formato` (`IF(COUNT(DISTINCT goal_type)=1, ...)`); usado como fallback quando o par exato `(platform, formato)` não está em `dict_format` |
| `resolve_platform_rule` | `(p_client_id STRING, p_platform_from STRING, p_formato STRING, p_as_of_date DATE) → STRING` | Remapeamento de plataforma por cliente vigente na data (ex: Push→`siprocal` pra Cora), lendo `core.advertiser_platform_rules` |

**Achado não-óbvio (confirmado ao vivo em 2026-08-09):** existe uma 4ª função,
`_resolve_test_simple(p_platform STRING) → STRING`, em produção — não documentada em
nenhum DDL commitado no repo (`grep` por `_resolve_test_simple` em `*.sql` não encontra
nada). Corpo: `SELECT ANY_VALUE(goal_type) FROM core.dict_format WHERE platform =
p_platform` — não filtra por `formato` nem por vigência (`as_of_date`), então não segue o
mesmo contrato SCD2 das outras 3. Não é referenciada por nenhuma view de `core`/`gold`
(confirmado via `INFORMATION_SCHEMA.VIEWS.view_definition LIKE '%_resolve_test_simple%'`
nos dois datasets — zero resultados). Ver `core/OWNERSHIP.yaml` para o registro completo e
a recomendação (não removida nesta sessão — decisão de produto pendente do Douglas).

### `client_reporting_source_config` + `resolve_reporting_source()` — staging_only

Generalização (por `client_id`) do mecanismo de override histórico, criada 2026-08-05.
**Existe só em `douglas-bq-staging`** — nunca promovida pra produção. Em produção, o
mesmo problema (substituir entrega real por dado retroativo pra um cliente/período) ainda
é resolvido pelo mecanismo antigo, hardcoded: `gold.vw_fact_delivery_reporting` faz
`UNION ALL` entre `gold.fact_delivery` e `core.historical_overrides_delivery`, com
`client_id='banco_cora_fe13d78a'` e a data de corte `2026-07-01` literais na definição da
view (confirmado via `INFORMATION_SCHEMA.VIEWS` ao vivo nos dois projetos, 2026-08-09).
Ver `docs/technical_dataflow.md` (Diagrama 2) para o desenho completo dessa divergência
staging×produção.

### `core.client_business_rules` + `resolve_client_business_rule()` — construído, testado só em staging

✅ construído em 2026-08-09/10 (banner anterior — "planejado, não construído" — obsoleto,
corrigido em 2026-08-10). Regra de negócio configurável por cliente (`client_id`
preenchido) ou geral (`client_id NULL`), mesmo padrão SCD2 de `dict_format`/
`advertiser_platform_rules`, com duas colunas extras: `rule_id` (chave própria por
LINHA/VERSÃO, `DEFAULT GENERATE_UUID()`) e `status` (`active`/`paused`, metadado de
histórico — diferencia pausa deliberada de substituição natural por versão nova; não usado
por `resolve_client_business_rule`). Primeiro `rule_type` real: `impression_cap_pct` (teto
de 20% de impressão diária Native/Push, confirmado por Rafael). DDL completo com
procedimento de INSERT/pausa/substituição: `core/ddl/client_business_rules.sql`.

`core.resolve_client_business_rule(p_client_id, p_rule_type, p_as_of_date)` foi reescrita
em 2026-08-10 (commit `88c09d6`) para fechar um desvio do ADR-0001 — `gold.fact_pacing`
reimplementava a resolução inline em vez de chamar a função, porque a implementação
original usava `ARRAY_AGG(...ORDER BY...LIMIT...)`, que nunca decorrelaciona numa SQL UDF
chamada de forma correlacionada em BigQuery (achado confirmado por teste isolado, não
documentado antes — só agregação simples tipo `MIN`/`MAX`/`ANY_VALUE` sem `ORDER BY`/
`LIMIT` decorrelaciona). A função agora usa um único `MAX()` sobre uma STRING codificada
(1 dígito de especificidade + 8 dígitos de data `AAAAMMDD` + `rule_params` serializado via
`TO_JSON_STRING`) — `MAX()` escolhe a linha certa por ordenação lexicográfica,
`SUBSTR`+`PARSE_JSON` reconstitui o payload. `gold/ddl/fact_pacing.sql` chama a função
diretamente, mesmo padrão das outras 3 `resolve_*`. Ver `docs/known_issues.md` (G9,
resolvido) e `docs/gold_layer_design.md` (seção `fact_pacing`) para o detalhe da
investigação.

✅ validado em 2026-08-10, só em `douglas-bq-staging` — chamada isolada + 8 cenários de
vigência/prioridade/pausa/fronteira de data + caso real
(`banco_cora_fe13d78a`/Native/2026-01-12). 🟡 **nada aplicado em produção ainda** —
promoção bloqueada até autorização explícita do Douglas (guarda-corpo registrado na MÃE de
Regras de Negócio no Notion).

---

## Inventário Atual (verificado ao vivo, `owner: pipeline`)

> Consulta de partida (regenerar, não editar de memória):
> ```sql
> SELECT table_name, column_name, data_type, ordinal_position
> FROM `adframework.core.INFORMATION_SCHEMA.COLUMNS`
> ORDER BY table_name, ordinal_position;
>
> SELECT routine_name, ddl FROM `adframework.core.INFORMATION_SCHEMA.ROUTINES`;
> ```
> Objetos `owner: shiro_admin_ui` (`io_manager_v2`, `proposals`, etc.) **não** estão
> listados abaixo — ver `core/OWNERSHIP.yaml` para a lista completa deles.

### `dim_client`
Grain: `client_id`. Cadastro de cliente — 36 linhas em produção (2026-08-09).

| Campo | Tipo | Origem/lógica |
|---|---|---|
| client_id | STRING | chave canônica, seed manual |
| slug | STRING | seed manual |
| name | STRING | seed manual |
| sector | STRING | seed manual |
| status | STRING | seed manual |
| created_at | DATE | seed manual |
| deactivated_at | DATE | seed manual |
| notes | STRING | seed manual |
| seed_loaded_at | TIMESTAMP | seed manual |
| parent_client_id | STRING | hierarquia pai-filho (ex: TecPar→Amigo) — consumida por `gold.dim_advertiser` pro rollup no Power BI |
| client_level | INT64 | nível na hierarquia |
| newad_account_id | STRING | coluna real em produção não presente no DDL commitado originalmente — sincronizada em 2026-08-06 (ver `known_issues.md` R5) |

Status: ✅ validado em 2026-08-09 (schema real).

### `platform_client_links`
Grain: `platform + link_type + link_value`. Vínculo plataforma→cliente — 183 linhas em
produção. Consumida por `gold.fact_delivery`/`dim_campaign` (via STG) para resolver
`client_id` a partir do identificador nativo de cada plataforma.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| platform | STRING | `mediasmart` / `mgid` / `siprocal` |
| link_type | STRING | `eventid` (MS advertiser) / `campaignid` (MGID) / `advertiser` (Siprocal, nome parseado) |
| link_value | STRING | identificador nativo da plataforma |
| client_id | STRING | FK para `dim_client` |
| status | STRING | `active` / `pending_confirmation` / `inactive` |
| notes | STRING | manual |
| created_at | DATE | manual |

Status: ✅ validado em 2026-08-09 (schema real).

### `campaign_format_map`
Grain: `platform + platform_campaign_id`. Mapeamento manual de formato por campanha —
usado quando o nome da campanha não permite derivar `formato` por parsing. 18 linhas em
produção. Versionado SCD2 (`effective_from`/`effective_to`, adicionado 2026-08-04).

| Campo | Tipo | Origem/lógica |
|---|---|---|
| platform | STRING | manual |
| platform_campaign_id | STRING | manual |
| client_id | STRING | manual |
| format | STRING | manual (Display/Native/Push/Retargeting/Video) |
| source | STRING | manual |
| notes | STRING | manual |
| created_at | TIMESTAMP | manual |
| updated_at | TIMESTAMP | manual |
| effective_from | DATE | SCD2 |
| effective_to | DATE | SCD2, `NULL` = vigente |

Status: ✅ validado em 2026-08-09 (schema real). Gap conhecido: TecPar (4 strategy IDs) e
outros clientes MS ainda sem entrada aqui — ver `known_issues.md` G3/G8.

### `dict_format`
Grain: `platform + formato` (versionado por vigência). Regra global `(platform, formato)
→ goal_type`, consumida por `resolve_dict_format()`/`resolve_dict_format_fallback()`. 8
linhas em produção.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| formato | STRING | manual |
| platform | STRING | manual |
| goal_type | STRING | manual |
| notes | STRING | manual |
| confirmed_by | STRING | manual |
| created_at | DATE | manual |
| effective_from | DATE | SCD2 |
| effective_to | DATE | SCD2, `NULL` = vigente |

Status: ✅ validado em 2026-08-09 (schema real).

### `advertiser_platform_rules`
Grain: `client_id + platform_from + formato` (versionado por vigência). Remapeamento de
plataforma por cliente (ex: Cora Push → `siprocal`), consumido por `resolve_platform_rule()`.
1 linha em produção hoje (regra da Cora).

| Campo | Tipo | Origem/lógica |
|---|---|---|
| client_id | STRING | manual |
| platform_from | STRING | manual |
| formato | STRING | manual |
| platform_to | STRING | manual |
| confirmed_at | DATE | manual |
| confirmed_by | STRING | manual |
| notes | STRING | manual |
| effective_from | DATE | SCD2 |
| effective_to | DATE | SCD2, `NULL` = vigente |

Status: ✅ validado em 2026-08-09 (schema real). Gap conhecido: Amigo provavelmente precisa
da mesma regra (Push→siprocal) e ainda não tem — ver `known_issues.md` G5.

### `historical_overrides_delivery`
Grain: `client_id + day + platform + formato`. Dado de entrega histórico carregado
manualmente quando a plataforma não tem o dado real (ex: Cora ago/25–jun/26). **Em
produção, ainda vive em `core`** (não migrado pra `stg`, apesar da migração já ter sido
feita e validada em staging — ver `known_issues.md` R2). 0 linhas em produção hoje
(2026-08-09) — o dado real de override da Cora foi carregado só em staging até o momento.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| client_id | STRING | `load_historical_override.py` |
| day | DATE | `load_historical_override.py`, normalizado de formato BR |
| platform | STRING | `load_historical_override.py` |
| formato | STRING | `load_historical_override.py`, normalizado (`video_instream`, etc.) |
| goal_type | STRING | `load_historical_override.py` |
| impressions | FLOAT64 | `load_historical_override.py` |
| clicks | FLOAT64 | `load_historical_override.py` |
| investimento | NUMERIC | `load_historical_override.py`, normalizado de formato BR ("1.234,56"→1234.56) |
| source_file | STRING | rastreabilidade da planilha de origem |
| loaded_by | STRING | rastreabilidade |
| loaded_at | TIMESTAMP | rastreabilidade |
| notes | STRING | manual |

Status: ✅ validado em 2026-08-09 (schema real). **Ver `docs/technical_dataflow.md` para o
desenho completo da divergência staging×produção neste mecanismo — não é só "onde a tabela
mora", o mecanismo de leitura (`vw_fact_delivery_reporting` vs. `resolve_reporting_source()`)
também diverge.**

### `io_plan_manual`
Grain: `client_id + flight_start + flight_end`. Plano de mídia (budget), sincronizado do
Google Drive via `sync_drive.py` — ver `docs/io_plan_domain.md`. 49 linhas em produção.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| client_id | STRING | `sync_drive.py`, via `CLIENT_MAP` |
| flight_start | DATE | parseado do label do voo na planilha |
| flight_end | DATE | idem |
| planned_impressions | INT64 | planilha |
| planned_clicks | INT64 | planilha |
| planned_spend_gross | NUMERIC | planilha |
| planned_spend_net | NUMERIC | planilha |
| plan_version | STRING | `'DRIVE-SYNC'` para sync automático |
| source_file | STRING | rastreabilidade |
| loaded_at | TIMESTAMP | rastreabilidade |

Status: ✅ validado em 2026-08-09 (schema real).

### `change_proposals`
Grain: `proposal_id`. Fila genérica de propostas de mudança (detectar → propor → aprovar
→ aplicar) — primeira consumidora: Siprocal (ver `CHANGELOG.md`, correção de ingestão
incremental). 0 linhas em produção hoje.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| proposal_id | STRING | gerado |
| target_dataset | STRING | dataset alvo da mudança proposta |
| target_table | STRING | tabela alvo |
| operation | STRING | tipo de operação proposta |
| key_fields | JSON | chave da linha afetada |
| old_values | JSON | valor antes |
| new_values | JSON | valor proposto |
| source | STRING | quem/o que detectou |
| status | STRING | fila de aprovação |
| detected_at | TIMESTAMP | — |
| proposed_by | STRING | — |
| resolved_by | STRING | — |
| resolved_at | TIMESTAMP | — |
| applied_at | TIMESTAMP | — |
| notes | STRING | — |

Status: ✅ validado em 2026-08-09 (schema real). **Não confundir com `core.proposals`
(owner: `shiro_admin_ui`, nome parecido, propósito diferente — ver `core/OWNERSHIP.yaml`).**

### `schema_change_log`
Grain: `change_id`. Log de auditoria de toda execução de `scripts/deploy/apply_ddl.py`
(test ou prod), incluindo `previous_definition`/`commit_hash` pra suportar `--rollback`.
1 linha em produção hoje.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| change_id | STRING | gerado por `apply_ddl.py` |
| object_dataset | STRING | preenchido por `apply_ddl.py` |
| object_name | STRING | preenchido por `apply_ddl.py` |
| change_summary | STRING | opcional, via flag |
| reason | STRING | opcional, via flag |
| requested_by | STRING | preenchido por `apply_ddl.py` |
| tested_at | TIMESTAMP | preenchido por `apply_ddl.py` |
| tested_env | STRING | `test` / `prod` |
| approved_by | STRING | manual, pós-fato |
| promoted_at | TIMESTAMP | manual, pós-fato |
| status | STRING | preenchido por `apply_ddl.py` |

Status: ✅ validado em 2026-08-09 (schema real).

### `vw_platform_campaign_links` (VIEW)
Grain: `client_id + platform + platform_campaign_id`. Recorte de `platform_client_links`
só com `link_type='campaignid'` (útil pra visão MGID, que vincula por campanha
individual — ver `docs/stg_layer_design.md`).

| Campo | Tipo | Origem/lógica |
|---|---|---|
| client_id | STRING | `core.platform_client_links` |
| platform | STRING | `core.platform_client_links` |
| platform_campaign_id | STRING | `core.platform_client_links.link_value` |
| link_type | STRING | `core.platform_client_links` |
| status | STRING | `core.platform_client_links` |
| notes | STRING | `core.platform_client_links` |
| created_at | DATE | `core.platform_client_links` |

Status: ✅ validado em 2026-08-09 (schema real, `view_definition` lido ao vivo).

### `vw_delivery_unattributed` (VIEW)
Grain: `day + platform`. Monitoramento — linhas de entrega (`stg.ms_delivery`/
`mg_delivery`/`sp_delivery`) sem `client_id` resolvido, agregadas por dia/plataforma.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| day | DATE | `date` das 3 STG de entrega |
| platform | STRING | literal por branch do `UNION ALL` |
| rows_unattributed | INT64 | `COUNT(*)` onde `client_id IS NULL` |
| impressions_lost | FLOAT64 | `SUM(impressions)` |
| clicks_lost | FLOAT64 | `SUM(clicks)` |

Status: ✅ validado em 2026-08-09 (schema real, `view_definition` lido ao vivo).

### `client_reporting_source_config` + `resolve_reporting_source` — status `staging_only`

Não existem em produção. Ver seção "Design e Racional" acima e `core/OWNERSHIP.yaml` para
o registro completo — não repetido aqui pra não duplicar fonte.
