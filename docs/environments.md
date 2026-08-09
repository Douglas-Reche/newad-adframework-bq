# Matriz de Estado Ambiental — newad-adframework-bq

> **Manutenção:** Tier 2 — atualizar a cada promoção staging→produção

> ✅ ATUAL | Criado 2026-08-09 | Confirmado contra `CHANGELOG.md` (entradas 2026-08-05→06) —
> não confirmado contra IAM ao vivo nesta sessão (sem acesso a `gcloud`/`bq`, ver nota no
> rodapé). Narrativa completa da decisão de arquitetura: Notion, página "Estudo: como
> funcionariam os dois ambientes", MÃE "🧱 [MÃE] Ambientes Staging x Produção (BigQuery)".

Dois projetos GCP fisicamente separados. Não são o mesmo projeto com datasets diferentes —
são contas de billing, IAM e recursos independentes.

---

## Os dois projetos

| | `adframework` (produção) | `douglas-bq-staging` (staging) |
|---|---|---|
| **Papel** | Único ambiente real — serve Power BI, hub em produção, todos os clientes ativos | Validar rebuild/mudança antes de promover; nunca serve dado real a cliente |
| **Billing** | Conta de produção | Conta própria (`Douglas_Reche_Teste_Stag`, moeda CAD) |
| **Guardrails de custo** | — | Cota de query 10GB/dia (`bigquery.googleapis.com/quota/query/usage`); orçamento CAD$10/mês com alertas em 50/90/100% |
| **BigQuery, Firestore, Firebase Auth** | Ao vivo, servindo produção | Só BigQuery — sem Firestore/Firebase próprio |
| **Cloud Run ETL** | `adframework-etl` (ingestão real) | Não roda — staging nunca reproduz ingestão, só consome o que produção já produziu |

---

## O que vigora em cada projeto, por camada

| Camada | Em `adframework` | Em `douglas-bq-staging` |
|---|---|---|
| `raw` | Física, populada pela ingestão real (conectores MediaSmart/MGID/Siprocal) | **Snapshot físico** das 18 tabelas de `adframework.raw.*` via `bq cp` — único ponto de contato com produção, atualizado por Cloud Scheduler diário (mesmo padrão do `adframework-etl-daily`), nunca leitura ao vivo |
| `stg` | Views, lidas do `raw` de produção | 100% físico e local, aplicado do mesmo `.sql` versionado no repo, lendo exclusivamente do `raw` local (snapshot) |
| `core` | Tabelas de regra/config reais | 100% físico e local — mesmo `.sql`, dado copiado pontualmente de produção quando necessário para teste (nunca via `SELECT *` posicional entre schemas divergentes, ver `docs/known_issues.md` R5) |
| `gold` | Views que servem Power BI/hub reais | 100% físico e local, espelha os objetos oficiais de produção pra teste de paridade |

**Zero leitura cross-project depois do snapshot de `raw`** — essa é a decisão final
(2026-08-06 manhã), que superou um desenho anterior de leitura cross-project ao vivo pra
`raw`/`stg`. Ver `CHANGELOG.md`, entrada "2026-08-06 (manhã) — Arquitetura standalone",
para o raciocínio completo.

---

## Diferença de IAM / service accounts entre os dois projetos

Confirmado via `hub/deploy.sh` (script fonte de verdade dos bindings) e `CHANGELOG.md`
(entradas 2026-08-06):

| Service Account | Papel | Bindings em `adframework` | Bindings em `douglas-bq-staging` |
|---|---|---|---|
| `douglas-data-hub-sa` (principal, roda o Cloud Run do hub) | Read-only | `roles/bigquery.dataViewer`, `roles/bigquery.jobUser`, `roles/bigquery.resourceViewer` (projeto inteiro) | `roles/bigquery.dataViewer` + `roles/bigquery.jobUser` (projeto inteiro) — adicionado 2026-08-06 tarde após 403 real em `raw.historical_uploads_meta` (a SA principal só tinha permissão em produção até então) |
| `douglas-data-hub-writer-sa` (escrita, via impersonation, nunca chave JSON) | Write, escopo dataset-a-dataset | `roles/bigquery.dataEditor` em `core` e `raw` (Propostas de Mudança) | `roles/bigquery.dataEditor` em `raw`, `stg`, `core` + `roles/bigquery.jobUser` no projeto inteiro (fluxo de override histórico por cliente, landing → normalização → override) |

**Princípio que não muda entre os dois ambientes:** a SA principal do hub nunca ganha
permissão de escrita, em nenhum projeto — qualquer escrita passa pela writer SA via
impersonation, com `dataEditor` escopado a dataset, nunca a projeto inteiro (exceto
`jobUser`, que não concede acesso a dado, só permissão de rodar job).

**Escritas do hub que tocam staging faturam contra o projeto de staging, não produção** —
decisão explícita de 2026-08-06 pra não exigir `roles/bigquery.jobUser` em produção só pra
viabilizar uma feature 100% de teste (`get_staging_writer_bq_client()` em `hub/app.py`).

---

## Quando/como este doc deve ser atualizado

Atualizar **a cada promoção staging → produção** que muda o que vigora em algum dos dois
projetos — não é opcional, é parte do runbook de promoção (`docs/runbook_promocao_ambiente.md`).
Especificamente:

- Novo objeto (`raw`/`stg`/`core`/`gold`) promovido de staging pra produção → confirmar se a
  tabela "O que vigora em cada projeto, por camada" ainda reflete a realidade.
- Novo binding de IAM/SA em qualquer um dos dois projetos → atualizar a tabela de IAM
  acima e sincronizar com o comentário correspondente em `hub/deploy.sh` (fonte de
  verdade do código; este doc é a leitura consolidada).
- Mudança de guardrail de custo (cota, orçamento) → atualizar a linha correspondente.

Dono da atualização: o agente `docs`, acionado pelo orquestrador conforme
"Fluxo de documentação é sempre em 3 saltos" (`CLAUDE.md`).

---

## Nota de confirmação

Esta versão foi escrita a partir de `CHANGELOG.md` (histórico de decisões já registrado,
2026-08-05→06) e `hub/deploy.sh` (bindings reais no código), sem acesso ao BigQuery/IAM ao
vivo nesta sessão (`gcloud`/`bq` com auth expirada). Os bindings documentados na tabela de
IAM refletem o que o `hub/deploy.sh` aplica quando rodado — não foi reconfirmado via
`gcloud projects get-iam-policy` ao vivo. Próxima sessão com acesso: reconfirmar contra o
estado real e atualizar esta nota.
