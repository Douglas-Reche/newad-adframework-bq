# Índice de Documentação — AdFramework BQ Pipeline

> **✅ RAW + STG LAYERS ENCERRADAS — 2026-06-24 ✅**
> RAW: T1–T7 implementados, testados contra API real e validados em produção (MS + MGID). Jobs consolidados, 19 tabelas órfãs dropadas. `raw.*` final: **15 tabelas**.
> STG: T1-T7 (MS+MGID) e T1-T4 (Siprocal) criados, testados contra dado real e validados — `client_id`/`formato`/`goal_type` resolvidos e denormalizados nos fatos de entrega. 28 arquivos legados arquivados em `stg/ddl/_legacy/`.
> **Próxima camada:** Gold — agregações e modelagem dimensional final para consumo (Power BI, Admin UI).
> **Referência:** [`raw_layer_design.md`](raw_layer_design.md) — design oficial completo e validado da RAW layer.
> Docs legados (schema anterior a 18/06) seguem como referência histórica apenas.
> [`bq_restructuring_plan.md`](bq_restructuring_plan.md) · [`core_config_backup.md`](core_config_backup.md) · [`../CHANGELOG.md`](../CHANGELOG.md)
>
> **Regra:** ao criar ou modificar qualquer doc, atualizar este índice com o novo status e data de validação.

---

## Status de cada documento

| Arquivo | Status | Última validação | Descrição |
|---|---|---|---|
| `../CHANGELOG.md` | ✅ ATUAL | 2026-06-18 | Histórico completo de decisões e mudanças — sempre atualizar |
| `INDEX.md` | ✅ ATUAL | 2026-06-18 | Este arquivo |
| `raw_layer_design.md` | ✅ ATUAL | 2026-06-18 | **PONTO DE PARTIDA DO REBUILD** — design oficial da nova RAW layer: T1–T7, campos, grains, core.dict_format, tamanhos de imagem, IO Plan tratamentos |
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
| `stg_layer_design.md` | ✅ ATUAL | 2026-06-24 | **STG LAYER ENCERRADA** — T1-T7 MS+MGID e T1-T4 Siprocal criados, testados contra dado real e validados em produção |
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
| `mediasmart_raw_sketch.md` | ✅ ATUAL | 2026-06-18 | Análise API-first MediaSmart: todos os endpoints, campos T1–T7, código de ingestão planejado |
| `mgid_raw_sketch.md` | ✅ ATUAL | 2026-06-18 | Análise API-first MGID: endpoints, campos T1–T7, client_ids como lista fixa |
| `siprocal_raw_sketch.md` | ✅ ATUAL | 2026-06-18 | Análise Siprocal (Google Sheets): T1–T3, parse_period, campaign_id derivado |
| `bq_restructuring_plan.md` | ✅ ATUAL | 2026-06-16 | Contexto e motivação do rebuild — problemas do schema antigo (normalize_data, all-STRING, patches acumulados) |
| `core_config_backup.md` | ✅ ATUAL | 2026-06-16 | Backup das 3 tabelas core antes do DROP: 26 clientes, 155 vínculos de plataforma, 18 mapeamentos de formato — usar para re-seed |
| `api_capabilities.md` | ✅ ATUAL | 2026-06-08 | Inventário completo MediaSmart + MGID + Siprocal (APIs) — não depende de schema BQ |
| `API_Doc_MediaSmart.md` | ✅ ATUAL | 2026-06-11 | **FONTE PRIMÁRIA** — documentação oficial MediaSmart API completa (4.601 linhas). Consulta autoritativa. |
| `MGID_API_Doc.md` | ✅ ATUAL | 2026-06-11 | Documentação oficial MGID REST API — referência para implementação do ETL |
| `mediasmart_api_reference.md` | ✅ ATUAL | 2026-06-11 | Resumo estruturado da API MediaSmart para uso no ETL |
| `meta_ads_integration.md` | ✅ ATUAL | 2026-06-12 | Integração Meta Ads — credenciais, steps pendentes, schema proposto |
| `google_ads_integration.md` | ✅ ATUAL | 2026-06-12 | Integração Google Ads — guia completo de credenciais OAuth2, schema, GAQL |
| `commercial_questions.md` | ✅ ATUAL | 2026-06-08 | Perguntas pendentes para área comercial |
| `known_issues.md` | 📋 REBUILD | 2026-06-16 | Issues G1/G2/G3 são do schema antigo — encerrados pelo rebuild. Novos issues do rebuild serão documentados aqui. |
| `io_plan_pipeline.md` | 📋 REBUILD | 2026-06-15 | IO Plan (Drive→RAW→Gold) é independente do rebuild de entrega e continua válido — refs de delivery precisam ser revisadas |
| `etl_expansion_plan.md` | 📋 REBUILD | 2026-06-08 | Roadmap de expansão ainda válido como intenção — nomes de tabelas precisarão ser atualizados após rebuild |
| `analise_plano_vs_delivery_cora_tecpar.md` | 📋 REBUILD | 2026-06-15 | Lógica de pacing válida como referência de negócio — nomes de tabelas do schema antigo |
| `audit_io_plan_cora_tecpar_2026-06-15.md` | 📋 REBUILD | 2026-06-15 | IO Plan válido; parte de delivery refere ao schema antigo — valide antes de usar |
| `mediasmart_stg_design.md` | ❌ LEGADO | 2026-06-12 | Design STG MediaSmart do schema antigo — **tabelas dropadas** |
| `mgid_stg_design.md` | ❌ LEGADO | 2026-06-14 | Design STG MGID do schema antigo — **tabelas dropadas** |
| `siprocal_stg_design.md` | ❌ LEGADO | 2026-06-14 | Design STG Siprocal do schema antigo — **tabelas dropadas** |
| `_legacy/gold_layer_build_plan.md` | ❌ LEGADO | 2026-06-16 | Gold layer do schema antigo — **tabelas dropadas**. Movido para `_legacy/` em 2026-07-29 (auditoria de consistência) |
| `_legacy/column_lineage_map.md` | ❌ LEGADO | 2026-06-11 | Linhagem de colunas do schema antigo — não reflete o novo design. Movido para `_legacy/` em 2026-07-29 |
| `_legacy/id_attribution_map.md` | ❌ LEGADO | 2026-06-15 | Mapa de atribuição de IDs do schema antigo. Movido para `_legacy/` em 2026-07-29 |
| `_legacy/pipeline_complete_map.md` | ❌ LEGADO | 2026-06-03 | Mapa completo do pipeline antigo — inclui `raw.siprocal_raw_sheet`, tabela que **já não existe** no BigQuery. Movido para `_legacy/` em 2026-07-29 |
| `client_registry.md` | ❌ LEGADO | 2026-05-12 | IDs no formato `nwd_` (antigo) — fonte de verdade atual: `core.dim_client` e `core_config_backup.md` |
| `adframework_erd_mermaid.md` | ❌ LEGADO | 2026-05-13 | ERD do schema antigo |
| `_legacy/id_quality_issues.md` | ❌ LEGADO | 2026-05-12 | Análise de IDs do schema antigo. Movido para `_legacy/` em 2026-07-29 |
| `_legacy/id_dependency_map.md` | ❌ LEGADO | 2026-05-13 | Mapa de dependências do schema antigo. Movido para `_legacy/` em 2026-07-29 |
| `erd_attribution_chain.md` | ❌ LEGADO | 2026-05-13 | Attribution chain do schema antigo (usa views do Shiro) |
| `erd_flow_overview.md` | ❌ LEGADO | 2026-05-13 | Flow overview do schema antigo |
| `powerbi_plan.md` | ❌ LEGADO | 2026-04-29 | Plano Power BI com nomes de tabelas do schema antigo |
| `auditoria_shiro_2026-05-26.md` | ❌ LEGADO | 2026-05-26 | Auditoria com Shiro — schema antigo, views do Admin UI |
| `bigquery_analysis.md` | ❌ LEGADO | 2026-04-30 | Auditoria BQ abr/26 — estado antes do rebuild |
| `bigquery_cleanup_proposal.md` | ❌ LEGADO | 2026-04-30 | Proposta de limpeza abr/26 — superada pelo DROP total |
| `prod_audit_and_restructuring_plan.md` | ❌ LEGADO | 2026-04-30 | Plano de reestruturação abr/26 — superado pelo rebuild de jun/16 |
| `gold_mvp_apresentacao.md` | ❌ LEGADO | 2026-04-28 | Apresentação MVP gold abr/26 — arquitetura superada |
| `viability_assessment_terça.md` | ❌ LEGADO | 2026-05-05 | Ata reunião viabilidade mai/26 — contexto histórico |

---

## Legenda de status

| Status | Significado |
|---|---|
| ✅ **ATUAL** | Reflete o estado real do pipeline hoje. Confiável para consulta e desenvolvimento. |
| 📋 **REBUILD** | Parcialmente válido — lógica de negócio correta, mas referências de schema de entrega precisam ser revisadas após o rebuild. Valide nomes de tabelas antes de usar. |
| ❌ **LEGADO** | Schema, tabelas ou views **foram dropados** no rebuild de 2026-06-16. Consulte apenas como referência histórica. **Não use para desenvolvimento.** |
| 📦 **HISTÓRICO** | Documento de época — descreve o estado em uma data específica. Valor como referência de decisões e evolução do projeto. |

---

## Docs prioritários para atualização

1. `pipeline_complete_map.md` — o maior e mais consultado, mas defasado das mudanças de jun/08
2. `client_registry.md` — substituir por referência ao `core/seeds/clients.csv` como fonte de verdade
3. ERDs — regenerar após estabilizar o schema gold

---

## Convenção para novos docs

- Nome em snake_case, sem datas no nome (a data fica no conteúdo e no CHANGELOG)
- Exceção: docs de auditoria pontual podem ter data no nome (`auditoria_shiro_2026-05-26.md`)
- Todo novo doc entra aqui com status `✅ ATUAL` e data de criação
- Quando um doc for superado por outro, marcar como `📦 HISTÓRICO` (não deletar)
