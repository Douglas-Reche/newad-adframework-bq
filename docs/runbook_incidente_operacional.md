# Runbook de Incidente Operacional — pipeline de ingestão

> **Manutenção:** Tier 2 — toda vez que um incidente novo revelar um passo não documentado

> ✅ ATUAL | Criado 2026-08-09 | Matriz construída a partir de incidentes reais já
> resolvidos em `docs/known_issues.md` e `CHANGELOG.md` — não é cenário genérico. Cada
> linha referencia o issue original pra quem quiser o diagnóstico completo.

Sintoma → causa provável → ação, pra quando um conector de plataforma falha ou um job de
ingestão não roda. Ordenado por como o sintoma normalmente aparece primeiro (dado parado,
não erro explícito — a maioria destes incidentes foi descoberta por gap de data, não por
alerta).

---

## Como confirmar que há um incidente

Antes de qualquer diagnóstico específico, confirmar o sintoma:

```sql
-- Última data de cada tabela raw ativa
SELECT table_id, TIMESTAMP_MILLIS(last_modified_time) AS last_modified
FROM `adframework.raw.__TABLES__`
ORDER BY last_modified_time DESC;
```

Ou via o hub (`hub/app.py`, aba de freshness) — é a superfície feita exatamente pra isso.

---

## Matriz sintoma → causa provável → ação

| Sintoma | Causa provável | Ação | Referência |
|---|---|---|---|
| Tabela raw parada há mais de 1 dia, sem erro visível | Job usa `table_name`+`dataset_id` do orchestrator como destino real — não confiar no campo `bq_destiny` do Firestore, que pode estar desatualizado/legado e ser ignorado silenciosamente pelo código | Confirmar qual é o destino real lendo o código do orchestrator (`adframework_python`, repo Shiro), não só o Firestore | `known_issues.md` #9 |
| `HTTPSConnectionPool Read timed out` em jobs de drilldown de alta cardinalidade (geo, publisher) | `REQUEST_TIMEOUT_SECONDS` baixo demais pra volume de resposta da API MediaSmart | Aumentar timeout no conector (`adframework_python/src/connectors/mediasmart.py`), redeploy, re-trigger do job via `POST /jobs/{job_name}/run` | `known_issues.md` T1, B1 |
| Rejeição/erro 429 da API MediaSmart em job de iteração (creatives, strategies_detail) | `time.sleep()`/`RATE_LIMIT_DELAY` abaixo do limite oficial (128 req/min, 10 concurrent) | Ajustar o sleep pra manter margem de segurança (ex: 0.6s = 100 req/min, ~22% de folga) antes de criar jobs novos de iteração | `known_issues.md` #15 |
| `client_id` NULL em massa numa tabela STG de uma plataforma específica | `normalize_data()` renomeia headers da API pra snake_case, mas a tabela BQ existente tem schema com nomes antigos (herdados de sistema anterior) — `load_data()` dropa silenciosamente colunas não reconhecidas no schema existente | Confirmar via `INFORMATION_SCHEMA.COLUMNS` se o schema da tabela bate com o que a API envia hoje; se não bater, ou fazer rename explícito antes do load, ou (se a tabela é nova) `DROP` + recriar com schema nativo | `known_issues.md` #16, MS1 |
| Dado da Google Sheet (Siprocal) truncado numa data específica, sem erro | Filtro básico ativo na planilha esconde linhas de contas com acesso Viewer — `values.get()` respeita o filtro | Trocar a leitura pra `spreadsheets.get(includeGridData=True)` (imune a filtro, já é o método em produção desde 2026-06-15 — se reaparecer, confirmar que não houve regressão pro método antigo) | `known_issues.md` SIP1 |
| `gcloud run deploy --source .` falha com `ContainerImageImportFailed` | Imagem buildada sem tag — Cloud Run não importa imagem sem tag do Artifact Registry | Usar `gcloud builds submit --tag <image>:<tag>` seguido de `gcloud run deploy --image <image>:<tag>` em vez de `--source .` direto | `known_issues.md` MS2 |
| Tabela raw com contagem de linhas muito acima do esperado (duplicação) | Múltiplos triggers de backfill sobrepostos com `WRITE_APPEND`, ou `write_mode` errado no Firestore (`WRITE_APPEND` onde deveria ser `WRITE_TRUNCATE` para tabela de catálogo) | Confirmar grain esperado, then `CREATE OR REPLACE TABLE ... AS SELECT DISTINCT * FROM ...` pra dedup pontual; corrigir `write_mode` no Firestore se for tabela de catálogo (firstlevel) | `known_issues.md` S1 (backfill), D1, M1, M3 |
| Novas campanhas de uma plataforma aparecem como `unattributed`/client_id NULL na gold | Campanha nova (novo `campaignid`/`eventid`) ainda não tem entrada em `core.platform_client_links` — vínculo é manual, não automático | INSERT manual em `core.platform_client_links` após confirmar o cliente correto (checar antes de inserir — nunca sobrescrever sem `SELECT` prévio); `stg.unresolved_client_links` monitora candidatos | `known_issues.md` M4 |
| Função `resolve_*` em `core` quebra com "Correlated subqueries... not supported" no uso real (dentro de view gold), mas funciona isolada | Função usa múltiplas CTEs referenciadas por subqueries escalares separadas — correlação de 2+ níveis que o BigQuery não decorrelacioniza automaticamente | Reescrever como um único `SELECT` flat com `LEFT JOIN` + agregação (`LOGICAL_OR`/`MIN`/`MAX`), mesmo padrão de `resolve_dict_format`/`resolve_platform_rule` | `CHANGELOG.md` 2026-08-06, R1 |
| Cópia de tabela de regra (`core.dim_client`, `core.dict_format`) entre projetos corrompe valores silenciosamente (sem erro) | `INSERT ... SELECT *` posicional entre schemas com colunas em ordem diferente — mesmo tipo (`STRING`) não gera erro, só troca valores de coluna | Nunca copiar tabela `core.*` entre projetos com `SELECT *` — sempre `INSERT` por lista explícita de colunas; conferir linha a linha após qualquer cópia cross-project | `known_issues.md` R5 |
| `403 Access Denied` num projeto GCP ao usar uma função nova do hub | SA usada pela função (principal read-only vs. writer) não tem binding no projeto de destino — bindings são por SA × projeto × dataset, não herdados | Confirmar qual `get_*_bq_client()` a função usa, checar bindings correspondentes em `hub/deploy.sh`, aplicar o binding faltante (dataset-scoped, nunca projeto inteiro pra escrita) | `CHANGELOG.md` 2026-08-06 (tarde), "SA principal do Hub sem leitura em staging" |
| Pacing/entrega de um cliente mostra R$ planejado sem entrega correspondente numa plataforma | `platform='unknown'` não remapeado pra plataforma real em `core.advertiser_platform_rules` para aquele cliente específico | Confirmar em qual plataforma a entrega realmente roda (ex: Push geralmente é Siprocal), adicionar regra em `core/ddl/advertiser_platform_rules.sql` | `known_issues.md` G5 |

---

## Quando o diagnóstico não bate com nenhuma linha acima

1. Confirmar se é um sintoma **novo** (não documentado) ou uma **regressão** de um issue já
   resolvido acima — reler a entrada correspondente em `known_issues.md`/`CHANGELOG.md`
   antes de investigar do zero.
2. Investigar seguindo o padrão de "causa raiz confirmada, não suposição" (ver
   `~/.claude/agents/backend.md`) — ler o código real do conector/orchestrator, confirmar
   contra `INFORMATION_SCHEMA`/Firestore ao vivo, nunca assumir.
3. Depois de resolvido, adicionar a entrada nova em `docs/known_issues.md` (formato já
   estabelecido: `# | Problema | Impacto | Ação` + seção `✅ Resolvidos em <data>`) —
   trabalho do agente `docs`, acionado pelo orquestrador.
4. Se o incidente revelar um padrão novo e recorrente, considerar adicionar uma linha
   nova a este runbook.
