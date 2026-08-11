# Índice de Documentação — AdFramework BQ Pipeline

> **Manutenção:** Tier 1 — meta: deveria ser gerado a partir do estado real dos docs, hoje ainda mantido manualmente (nota honesta, não automatizado ainda).

> **✅ RAW + STG LAYERS ENCERRADAS — 2026-06-24 ✅**
> RAW: T1–T7 implementados, testados contra API real e validados em produção (MS + MGID). Jobs consolidados, 19 tabelas órfãs dropadas. `raw.*` final: **15 tabelas**.
> STG: T1-T7 (MS+MGID) e T1-T4 (Siprocal) criados, testados contra dado real e validados — `client_id`/`formato`/`goal_type` resolvidos e denormalizados nos fatos de entrega. 28 arquivos legados arquivados em `stg/ddl/_legacy/`.
> **Próxima camada:** Gold — agregações e modelagem dimensional final para consumo (Power BI, Admin UI).
> **Referência:** [`raw_layer_design.md`](raw_layer_design.md) — design oficial completo e validado da RAW layer.
> Docs legados (schema anterior a 18/06) seguem como referência histórica apenas, em `_legacy/`.
> [`_legacy/bq_restructuring_plan.md`](_legacy/bq_restructuring_plan.md) · [`_legacy/core_config_backup.md`](_legacy/core_config_backup.md) · [`../CHANGELOG.md`](../CHANGELOG.md)
>
> **Regra:** ao criar ou modificar qualquer doc, atualizar este índice com o novo status e data de validação.

---

## Status de cada documento

| Arquivo | Status | Última validação | Descrição |
|---|---|---|---|
| `../CHANGELOG.md` | ✅ ATUAL | 2026-06-18 | Histórico completo de decisões e mudanças — sempre atualizar |
| `../AGENTS.md` | ✅ ATUAL | 2026-08-09 | Comandos universais/mecânicos do repo (não específicos de Claude) — build/test/deploy, o que existe hoje. Cabeçalho de manutenção: Tier 3, revisão quando comando de build/test/deploy mudar |
| `../HANDOVER.md` | ✅ ATUAL | 2026-08-09 | Ponto de partida pra pessoa/sessão nova no repo — runbook operacional + mapa de acessos + como o projeto se conecta como um todo. Cabeçalho de manutenção: Tier 3, revisão quando processo de acesso/credencial mudar |
| `INDEX.md` | ✅ ATUAL | 2026-08-10 | Este arquivo |
| `gold_layer_design.md` | ✅ ATUAL | 2026-08-10 | Design da GOLD layer (grains, racional financeiro) + inventário verificado ao vivo das 9 views reais de `adframework.gold`. Seção `fact_pacing` atualizada 2026-08-10: fonte `stg.fact_pacing_base` (materializada) + chamada direta de `core.resolve_client_business_rule()` (fecha desvio do ADR-0001, ver `known_issues.md` G9) |
| `../core/OWNERSHIP.yaml` | ✅ ATUAL | 2026-08-10 | Fonte única de ownership dos objetos do dataset `core` (pipeline / Admin UI do Shiro / legado). 24 objetos (2 novos em 2026-08-10: `client_business_rules`, `resolve_client_business_rule`, ambos `status: staging_only`), auditado ao vivo contra `core.INFORMATION_SCHEMA.TABLES`/`ROUTINES` (2026-08-03, revalidado 2026-08-09). `_resolve_test_simple` confirmado ao vivo em 2026-08-09: existe só em produção, órfão, sem consumidor — recomendação de remoção registrada, decisão pendente do Douglas. `CLAUDE.md`, `.claude/agents/backend.md` e `.claude/agents/hub-frontend.md` referenciam este arquivo em vez de manter cópia própria da lista |
| `../hub/README.md` | ✅ ATUAL | 2026-08-10 | Documentação do painel Streamlit (Tier 3) — abas, exceção ao invariante read-only, deploy/redeploy, tema visual. Atualizado 2026-08-10: fluxo genérico de Ajustes de Dados Históricos (upload local + link Google Sheets), edição/deleção de regra de negócio, Simulador de Impacto, tema com Manual de Marca. Não estava listado neste índice até agora — adicionado |
| `_pending_purge.md` | ✅ ATUAL | 2026-08-03 | Fila central de arquivos flagueados como "análise pontual" aguardando expurgo semanal em lote — vazio no momento da criação |
| `plano_reestruturacao_documentacao.md` | ✅ ATUAL | 2026-08-08 | Plano consolidado de reestruturação de `docs/` (auditoria completa + pesquisa de mercado): Frente A (corrigir divergências), Frente B (docs novos com Tier de manutenção definido), Frente C (podar/consolidar). Aguardando aprovação do Douglas antes de qualquer execução |
| `raw_layer_design.md` | ✅ ATUAL | 2026-08-09 | **PONTO DE PARTIDA DO REBUILD** — design oficial da nova RAW layer: T1–T7, campos, grains, core.dict_format, tamanhos de imagem, IO Plan tratamentos. Schema das 3 tabelas extras (`mgid_stats_daily`/`mgid_stats_creative`/`ms_creative_daily`) confirmado ao vivo em 2026-08-09 — ainda sem STG/GOLD correspondente (gap de integração, não de documentação). Queda de linhas em `mg_teasers` (167→153) investigada, causa exata não confirmável (tabela é WRITE_TRUNCATE, sem histórico) |
| `core_layer_design.md` | ✅ ATUAL | 2026-08-10 | Design da CORE layer: narrativa (versionamento SCD2, funções `resolve_*`, divergência staging×produção do override histórico) + inventário verificado ao vivo dos objetos `owner: pipeline` (tabelas + views). `core.client_business_rules`/`resolve_client_business_rule()` atualizados 2026-08-10 — banner "planejado, não construído" corrigido (agora construído e testado em staging). Não duplica a lista de objetos `owner: shiro_admin_ui`, que continua só em `core/OWNERSHIP.yaml` |
| `technical_dataflow.md` | ✅ ATUAL | 2026-08-09 | Diagrama técnico — 2 Mermaid: (1) topologia C4 Nível 2 (GitHub, os 2 projetos GCP, Hub, Power BI, 3 APIs externas, Drive/IO Plan, upload manual de histórico) + (2) DFD Medallion com nomes reais RAW→STG→CORE→GOLD nos 2 projetos, incluindo a árvore de dado histórico e sua divergência staging×produção. Tabela "componente → implementação real" em cada diagrama. Manutenção híbrida (topologia Tier 2, DFD Tier 1) |
| `session_handoff_2026-06-18.md` | ✅ ATUAL | 2026-06-18 | **Handoff de sessão** — estado atual, próximos passos T1 MGID+Siprocal, regras de orquestração, pendências |
| `../raw/ddl/ms_advertisers.sql` | ✅ ATUAL | 2026-06-18 | DDL T1 MS — `raw.ms_advertisers` — 8 campos, WRITE_TRUNCATE |
| `../raw/ddl/mg_campaigns.sql` | ✅ ATUAL | 2026-06-22 | DDL T2 MGID — `raw.mg_campaigns` — validado em produção, 173 linhas, sem client_id |
| `../raw/ddl/sp_delivery.sql` | ✅ ATUAL | 2026-06-22 | DDL RAW literal Siprocal — `raw.sp_delivery` — validado, 1121 linhas, sem aliasing |
| `../raw/ddl/ms_campaigns.sql` | ✅ ATUAL | 2026-06-22 | DDL T2 MS — `raw.ms_campaigns` — validado, 14 linhas, campos numéricos nullable em FLOAT64 (não INT64) |
| `../raw/ddl/ms_creatives.sql` | ✅ ATUAL | 2026-06-22 | DDL T3 MS — `raw.ms_creatives` — validado, 23 linhas, escopo magro (sem advert_text/CTA, não existem na API) |
| `../raw/ddl/mg_teasers.sql` | ✅ ATUAL | 2026-06-22 | DDL T3 MGID — `raw.mg_teasers` — validado, 167 linhas, width/height fixos pelo comercial |
| `../raw/ddl/ms_delivery.sql` | ✅ ATUAL | 2026-06-22 | DDL T4 MS — `raw.ms_delivery` — validado, 735 linhas, **creative_id não faz join com ms_creatives (gap conhecido)** |
| `../raw/ddl/mg_delivery.sql` | ✅ ATUAL | 2026-06-22 | DDL T4 MGID — `raw.mg_delivery` — validado, 133 linhas, creative_id confirmado joinable |
| `../raw/ddl/ms_delivery_by_geo.sql` | ✅ ATUAL | 2026-06-22 | DDL T5 MS — `raw.ms_delivery_by_geo` — validado, 32.447 linhas, sem region (não existe na API) |
| `../raw/ddl/mg_delivery_by_geo.sql` | ✅ ATUAL | 2026-06-22 | DDL T5 MGID — `raw.mg_delivery_by_geo` — validado, 669 linhas, sem campaign_id/country (limite de 3 dims) |
| `../raw/ddl/ms_delivery_by_device.sql` | ✅ ATUAL | 2026-06-24 | DDL T6 MS — `raw.ms_delivery_by_device` — validado, 6.153 linhas, device+OS juntos |
| `../raw/ddl/mg_delivery_by_device.sql` | ✅ ATUAL | 2026-06-24 | DDL T6 MGID — `raw.mg_delivery_by_device` — validado, 251 linhas, só device (sem OS, limite de 3 dims) |
| `../raw/ddl/ms_delivery_by_hour.sql` | ✅ ATUAL | 2026-06-24 | DDL T7 MS — `raw.ms_delivery_by_hour` — validado, 18.660 linhas, hour parseado de string |
| `../raw/ddl/mg_delivery_by_hour.sql` | ✅ ATUAL | 2026-06-24 | DDL T7 MGID — `raw.mg_delivery_by_hour` — validado, 1.346 linhas, join 100% |
| `stg_layer_design.md` | ✅ ATUAL | 2026-08-10 | **STG LAYER ENCERRADA (dado de plataforma)** — T1-T7 MS+MGID e T1-T4 Siprocal criados, testados contra dado real e validados em produção. Nova seção "Cross-plataforma" adicionada 2026-08-10: `stg.fact_pacing_base` (materialização física planejado×realizado, staging only). Banner de topo corrigido 2026-08-10 (estava "🟡 PLANO", desatualizado — doc foi tocado por outro motivo e o banner foi corrigido junto) |
| `../stg/ddl/unresolved_client_links.sql` | ✅ ATUAL | 2026-06-24 | View de monitoramento — lista entidades sem vínculo em platform_client_links nas 3 plataformas, com sugestão de match |
| `../stg/ddl/sp_clients.sql` | ✅ ATUAL | 2026-06-24 | T1 STG Siprocal — `stg.sp_clients`, validado 11/11 (100%) resolvido |
| `../stg/ddl/ms_advertisers.sql` | ✅ ATUAL | 2026-06-24 | T1 STG MS — `stg.ms_advertisers`, validado 20/21 (95%) resolvido, campos `id`/`sensitive_content` descartados |
| `../stg/ddl/mg_advertisers.sql` | ✅ ATUAL | 2026-06-24 | T1 STG MGID — `stg.mg_advertisers`, validado 38/39 grupos (97,7% das campanhas) — só `CassinoPix` pendente de confirmação comercial |
| `../stg/ddl/ms_campaigns.sql` | ✅ ATUAL | 2026-06-24 | T2 STG MS — `stg.ms_campaigns`, validado 14/14, formato/goal_type 12/14 |
| `../stg/ddl/mg_campaigns.sql` | ✅ ATUAL | 2026-06-24 | T2 STG MGID — `stg.mg_campaigns`, validado 173/173, formato/goal_type 100% |
| `../stg/ddl/sp_campaigns.sql` | ✅ ATUAL | 2026-06-24 | T2 STG Siprocal — `stg.sp_campaigns`, validado 37/37 (100% em tudo) |
| `../stg/ddl/_legacy/` | 📦 HISTÓRICO | 2026-06-24 | 28 arquivos SQL do schema STG pré-rebuild (anterior ao DROP de 18/06) — não funcionam, preservados só como referência histórica |
| `../stg/ddl/ms_creatives.sql` | ✅ ATUAL | 2026-06-24 | T3 STG MS — `stg.ms_creatives`, validado 201/201 |
| `../stg/ddl/mg_teasers.sql` | ✅ ATUAL | 2026-06-24 | T3 STG MGID — `stg.mg_teasers`, validado 167/167 |
| `../stg/ddl/ms_delivery.sql` | ✅ ATUAL | 2026-06-24 | T4 STG MS — `stg.ms_delivery`, 938/938, `client_id` denormalizado, `event_id` renomeado |
| `../stg/ddl/mg_delivery.sql` | ✅ ATUAL | 2026-06-24 | T4 STG MGID — `stg.mg_delivery`, 157/157, `client_id` denormalizado |
| `../stg/ddl/sp_delivery.sql` | ✅ ATUAL | 2026-06-24 | T4 STG Siprocal — `stg.sp_delivery`, 1121/1121, parse completo de tipos, `ctr` recalculado |
| `../stg/ddl/ms_delivery_by_geo.sql` | ✅ ATUAL | 2026-06-24 | T5 STG MS — 41.817/41.818 com client_id |
| `../stg/ddl/ms_delivery_by_device.sql` | ✅ ATUAL | 2026-06-24 | T6 STG MS — 6.152/6.153 com client_id |
| `../stg/ddl/ms_delivery_by_hour.sql` | ✅ ATUAL | 2026-06-24 | T7 STG MS — 18.659/18.660 com client_id |
| `../stg/ddl/mg_delivery_by_geo.sql` | ✅ ATUAL | 2026-06-24 | T5 STG MGID — 800/800 (100%), join em cadeia via mg_teasers |
| `../stg/ddl/mg_delivery_by_device.sql` | ✅ ATUAL | 2026-06-24 | T6 STG MGID — 251/251 (100%) |
| `../stg/ddl/mg_delivery_by_hour.sql` | ✅ ATUAL | 2026-06-24 | T7 STG MGID — 1.346/1.346 (100%) |
| `../stg/ddl/io_plan.sql` | ✅ ATUAL | 2026-06-24 | STG IO Plan — `stg.io_plan`, dedup 295→125 (0 duplicatas confirmadas), formato 100%, platform 77%, sem goal_type (conceito de campanha, não de plano) |
| `_legacy/mediasmart_raw_sketch.md` | 📦 HISTÓRICO | 2026-08-09 | Análise API-first MediaSmart pré-implementação: endpoints, campos T1–T7. Superado por `raw_layer_design.md`. Movido para `_legacy/` em 2026-08-09 |
| `_legacy/mgid_raw_sketch.md` | 📦 HISTÓRICO | 2026-08-09 | Análise API-first MGID pré-implementação: endpoints, campos T1–T7, client_ids como lista fixa. Superado por `raw_layer_design.md`. Movido para `_legacy/` em 2026-08-09 |
| `_legacy/siprocal_raw_sketch.md` | 📦 HISTÓRICO | 2026-08-09 | Análise Siprocal (Google Sheets) pré-implementação: T1–T3, parse_period, campaign_id derivado. Já tinha banner de "superado" desde 2026-06-22 mas nunca tinha sido fisicamente movido — corrigido em 2026-08-09 |
| `_legacy/bq_restructuring_plan.md` | 📦 HISTÓRICO | 2026-08-09 | Contexto e motivação do rebuild de 2026-06-16 (já concluído) — problemas do schema antigo (normalize_data, all-STRING, patches acumulados). Movido para `_legacy/` em 2026-08-09 |
| `_legacy/core_config_backup.md` | 📦 HISTÓRICO | 2026-08-09 | Backup de segurança pré-DROP de junho/2026 das 3 tabelas core: 26 clientes, 155 vínculos de plataforma, 18 mapeamentos de formato. Não é doc de consulta ativa (ver `core/OWNERSHIP.yaml` para estado atual). Movido para `_legacy/` em 2026-08-09 |
| `api_capabilities.md` | ✅ ATUAL | 2026-08-09 | Inventário completo MediaSmart + MGID + Siprocal (APIs) — não depende de schema BQ. Cabeçalho de manutenção adicionado 2026-08-09 (Tier 2, gatilho: nova plataforma/API integrada) — arquivo tinha ficado fora do retrofit de cabeçalho anterior |
| `API_Doc_MediaSmart.md` | ✅ ATUAL | 2026-08-09 | **FONTE PRIMÁRIA** — documentação oficial MediaSmart API completa. Seção "Quick Reference pro ETL" fundida no topo em 2026-08-09 (conteúdo de `mediasmart_api_reference.md`, arquivo standalone removido para não duplicar fonte); documentação oficial verbatim segue abaixo. Consulta autoritativa. |
| `MGID_API_Doc.md` | ✅ ATUAL | 2026-06-11 | Documentação oficial MGID REST API — referência para implementação do ETL |
| `meta_ads_integration.md` | ✅ ATUAL | 2026-06-12 | Integração Meta Ads — credenciais, steps pendentes, schema proposto |
| `google_ads_integration.md` | ✅ ATUAL | 2026-06-12 | Integração Google Ads — guia completo de credenciais OAuth2, schema, GAQL |
| `known_issues.md` | ✅ ATUAL | 2026-08-09 | Doc mais vivo do repo — issues abertos e resolvidos do pipeline pós-rebuild, atualizado a cada sessão de trabalho. A4/A5/C1 (universo Shiro — `share.io_calc_daily_v4`, `stg.io_lines_v4`, `share.platform_daily_detail`, `share.newad_operational_daily`, 6 views gold workaround) fechados em 2026-08-09: confirmado ao vivo que nenhum desses objetos está ativo em produção hoje — só `core.io_binding_registry_v4` sobrevive, sem consumidor oficial. Seções históricas (G1/G2 do schema pré-2026-06-16) seguem preservadas como registro, não invalidam o restante. |
| `io_plan_domain.md` | ✅ ATUAL | 2026-08-08 | Doc único de domínio IO Plan — consolida `io_plan_pipeline.md` + `etl_expansion_plan.md` + `analise_plano_vs_delivery_cora_tecpar.md` + `audit_io_plan_cora_tecpar_2026-06-15.md` (Frente C, item C2). Pipeline/arquitetura, plano de expansão, lógica de pacing Cora/TecPar e auditoria de qualidade — lógica de negócio válida, nomes de tabela de delivery pré-rebuild sinalizados no corpo do doc |
| `environments.md` | ✅ ATUAL | 2026-08-09 | Matriz de Estado Ambiental — `adframework` (produção) vs. `douglas-bq-staging` (staging), o que vigora em cada projeto por camada, diferença de IAM/service accounts entre os dois. Construído a partir de `CHANGELOG.md` + `hub/deploy.sh`; bindings de IAM não reconfirmados ao vivo nesta sessão (auth `gcloud`/`bq` expirada) |
| `runbook_promocao_ambiente.md` | ✅ ATUAL | 2026-08-09 | Runbook de Promoção de Ambiente (staging → produção) — passos mecânicos via `apply_ddl.py` + plano de rollback explícito (`--rollback`, projeto errado, dado promovido incorretamente). Baseado no mecanismo real de teste em 2 níveis de `scripts/deploy/apply_ddl.py` |
| `architecture_overview.md` | ✅ ATUAL | 2026-08-09 | Diagrama executivo C4 Nível 2 (Containers), Mermaid — Ingestão (MediaSmart/MGID/Siprocal) → Transformação (BigQuery, um bloco só) → Consumo (Hub `douglas-data-hub`, Power BI). Zero jargão técnico/SQL, feito para apresentar a stakeholders não-técnicos. Item B7 do plano de reestruturação de documentação |
| `runbook_incidente_operacional.md` | ✅ ATUAL | 2026-08-09 | Runbook de Incidente Operacional — matriz sintoma → causa provável → ação para falhas de conector/ingestão (MediaSmart, MGID, Siprocal), construída a partir de incidentes reais já resolvidos em `known_issues.md`/`CHANGELOG.md`, não cenário genérico |

---

## Legenda de status

| Status | Significado |
|---|---|
| ✅ **ATUAL** | Reflete o estado real do pipeline hoje. Confiável para consulta e desenvolvimento. |
| 📋 **REBUILD** | Parcialmente válido — lógica de negócio correta, mas referências de schema de entrega precisam ser revisadas após o rebuild. Valide nomes de tabelas antes de usar. |
| ❌ **LEGADO** | Schema, tabelas ou views **foram dropados** no rebuild de 2026-06-16. Consulte apenas como referência histórica. **Não use para desenvolvimento.** |
| 📦 **HISTÓRICO** | Documento de época — descreve o estado em uma data específica. Valor como referência de decisões e evolução do projeto. |
| 🗑️ **PENDING_PURGE** | Análise pontual, valor já migrado (ou confirmado sem fato novo). Aguardando expurgo semanal em lote — ver `_pending_purge.md`. Nunca deletado sem confirmação explícita do usuário. |

---

## Docs prioritários para atualização

1. `pipeline_complete_map.md` — o maior e mais consultado, mas defasado das mudanças de jun/08
2. `client_registry.md` — substituir por referência ao `core/seeds/clients.csv` como fonte de verdade
3. ERDs — regenerar após estabilizar o schema gold

---

## Sobre `README.md` — por que não está na tabela acima

Decisão (2026-08-09): `README.md` da raiz **não** entra na tabela de status como os
demais docs, mesmo com docs de raiz agora entrando no índice com prefixo `../`
(`../CHANGELOG.md`, `../AGENTS.md`, `../HANDOVER.md`). `README.md` já tem tratamento
próprio definido como porta de entrada do projeto (arquitetura em 4 camadas + estado
atual em 1 parágrafo, formato definido em `docs.md` — "nunca vira changelog") — ele não
carrega status de validação/data como um doc técnico normal, é a página de entrada que
aponta para os demais, não um doc no mesmo sentido de schema/design/runbook. Adicioná-lo
à tabela como linha comum obrigaria a inventar uma data de "última validação" que não
tem sentido para um arquivo cujo conteúdo é deliberadamente estável e curto.

## Convenção para novos docs

- Nome em snake_case, sem datas no nome (a data fica no conteúdo e no CHANGELOG)
- Exceção: docs de auditoria pontual podem ter data no nome (`auditoria_shiro_2026-05-26.md`)
- Todo novo doc entra aqui com status `✅ ATUAL` e data de criação
- Quando um doc for superado por outro, marcar como `📦 HISTÓRICO` (não deletar)
