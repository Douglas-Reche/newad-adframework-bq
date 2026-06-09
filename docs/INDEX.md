# Índice de Documentação — AdFramework BQ Pipeline

> Última revisão: 2026-06-08
> **Regra:** ao criar ou modificar qualquer doc, atualizar este índice com o novo status e data de validação.

---

## Status de cada documento

| Arquivo | Status | Última validação | Descrição |
|---|---|---|---|
| `../CHANGELOG.md` | ✅ ATUAL | 2026-06-08 | Histórico completo de decisões e mudanças — sempre atualizar |
| `INDEX.md` | ✅ ATUAL | 2026-06-08 | Este arquivo |
| `known_issues.md` | ✅ ATUAL | 2026-06-08 | Issues abertas e resolvidas do pipeline |
| `api_capabilities.md` | ✅ ATUAL | 2026-06-08 | Inventário completo MediaSmart + MGID + Siprocal (APIs) |
| `etl_expansion_plan.md` | ✅ ATUAL | 2026-06-08 | Plano de expansão: device, geo, financeiro, criativo |
| `commercial_questions.md` | ✅ ATUAL | 2026-06-08 | Perguntas pendentes para área comercial |
| `pipeline_complete_map.md` | ⚠️ DESATUALIZADO | 2026-06-03 | Mapa detalhado do pipeline — válido até jun/03, precisa refletir fixes de jun/08 |
| `client_registry.md` | ⚠️ DESATUALIZADO | 2026-05-12 | Registro de clientes — fonte de verdade migrou para `core.dim_client` + `core/seeds/clients.csv` |
| `adframework_erd_mermaid.md` | ⚠️ DESATUALIZADO | 2026-05-13 | ERD gerado automaticamente — pode não refletir schema atual |
| `adframework_erd.dbml` | ⚠️ DESATUALIZADO | 2026-05-13 | ERD DBML — mesmo aviso |
| `id_quality_issues.md` | ⚠️ PARCIAL | 2026-05-12 | Análise de IDs — alguns issues resolvidos, outros ainda abertos |
| `id_dependency_map.md` | ⚠️ DESATUALIZADO | 2026-05-13 | Mapa de dependências RAW→GOLD — pode não refletir refatoração de mai/26 |
| `erd_attribution_chain.md` | ⚠️ DESATUALIZADO | 2026-05-13 | ERD focado na cadeia de atribuição — pré-refatoração |
| `erd_flow_overview.md` | ⚠️ DESATUALIZADO | 2026-05-13 | Overview de fluxo — pré-refatoração |
| `auditoria_shiro_2026-05-26.md` | 📦 HISTÓRICO | 2026-05-26 | Auditoria do repositório do Shiro feita em mai/26 — referência pontual |
| `bigquery_analysis.md` | 📦 HISTÓRICO | 2026-04-30 | Auditoria BQ completa de abr/26 — estado do BQ antes da refatoração |
| `bigquery_cleanup_proposal.md` | 📦 HISTÓRICO | 2026-04-30 | Proposta de limpeza de abr/26 — parcialmente executada em mai/26 |
| `prod_audit_and_restructuring_plan.md` | 📦 HISTÓRICO | 2026-04-30 | Plano de reestruturação de abr/26 — guia original da nova arquitetura |
| `gold_mvp_apresentacao.md` | 📦 HISTÓRICO | 2026-04-28 | Apresentação MVP gold de abr/26 — arquitetura evoluiu, manter como referência |
| `powerbi_plan.md` | 📦 HISTÓRICO | 2026-04-29 | Plano Power BI de abr/26 — nomes de tabelas defasados (fct_delivery_daily → fact_delivery) |
| `viability_assessment_terça.md` | 📦 HISTÓRICO | 2026-05-05 | Ata da reunião de viabilidade com Shiro + Alexandre |

---

## Legenda de status

| Status | Significado |
|---|---|
| ✅ **ATUAL** | Reflete o estado real do pipeline hoje. Confiável para consulta. |
| ⚠️ **DESATUALIZADO** | Existia antes da última refatoração. Pode ter informações corretas mas misturadas com coisas que já mudaram. Consultar com cautela. |
| ⚠️ **PARCIAL** | Parte do conteúdo está atual, parte está obsoleta — ler com atenção às datas internas. |
| 📦 **HISTÓRICO** | Documento de época — descreve o estado em uma data específica. Não reflete o presente mas tem valor como referência de decisões e evolução. |
| ❌ **DEPRECADO** | Substituído por outro doc. Não usar. |

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
