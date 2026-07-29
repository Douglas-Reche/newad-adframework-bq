# Auditoria de Consistência do Pipeline — 2026-07-29

> Escopo: ingestão (RAW) → STG → Gold, todas as origens (MediaSmart, MGID, Siprocal, IO Plan).
> Método: leitura de código/DDL real + `INFORMATION_SCHEMA` + queries ao vivo no BigQuery (`adframework` project) + comparação com os `docs/*.md` existentes.
> Esta auditoria é só levantamento — nenhuma correção foi aplicada. Achados priorizados por severidade.

---

## Sumário executivo

| Camada | Estado | Nota |
|---|---|---|
| Ingestão (RAW) | 🟡 Funcional, mas parte do código não está neste repo | Ver §5 |
| RAW → STG | 🟢 Paridade de linhas confirmada (100%) | Ver §2 |
| STG → Gold | 🟡 Lineage real diverge da documentação | Ver §1, §2 |
| Documentação | 🔴 5 docs de lineage centrais estão obsoletos (pré-rebuild) | Ver §3 |
| Deploy/CI da camada BQ | 🔴 Sem automação — commit ≠ deployado | Ver §4 |

---

## 1. Jobs de ingestão

| Origem | Mecanismo | Agendamento | Code path | Observabilidade |
|---|---|---|---|---|
| MediaSmart (delivery, geo, device, hour) | `orchestrator.py` (Cloud Run `adframework-etl`) | Cloud Scheduler diário, via Firestore job doc | `_run_mediasmart_normalized_delivery` | Firestore `last_status` |
| MGID (delivery, geo, device, hour) | idem | Cloud Scheduler diário | `_run_mgid_normalized_delivery` (corrigido 2026-07-03) | Firestore `last_status` |
| Siprocal (ativo) | idem | Cloud Scheduler 03:20 UTC | `_run_siprocal_daily`, WRITE_TRUNCATE | Firestore `last_status` |
| Siprocal (legado) | `scripts/siprocal/sync_sheet.py` neste repo | **Manual** | `try/except` só no HTTP request, sem retry | Nenhuma |
| IO Plan / Cora (Drive) | `scripts/io_plan/sync_drive.py` via Cloud Run `io-plan-admin` | **Manual** (botão `POST /sync`) | falha por arquivo é `log.warning` + `continue` | `_last_result` em memória — **perdido a cada restart** |
| Cora Sheets (legado) | `scripts/etl/cora_sheets_sync.py` + Apps Script | Diário 7h-8h | — | Marcado "LEGADO — não executar" mas ainda presente sem guarda de execução |

**Achados:**

- 🔴 **Alta** — `raw.siprocal_raw_sheet` está marcada para `DROP` desde 06/2026 (`known_issues.md` C1), mas o DDL ainda existe e `docs/pipeline_complete_map.md` descreve esse fluxo como se estivesse ativo. Confunde qualquer leitura futura do lineage.
- 🟠 **Média** — IO Plan/Cora sync não tem agendamento nem histórico persistido de execuções. Se ninguém clicar no botão, o plano fica desatualizado silenciosamente — sem alerta. Isso é coerente com o gap que você já vinha vendo (falta plano Jul 11-28/Ago).
- 🟡 **Baixa** — `scripts/siprocal/sync_sheet.py` (legado) segue no repo sem o mesmo banner de "não executar" que `cora_sheets_sync.py` tem.

---

## 2. Linhagem RAW → STG → Gold

Inventário real via `INFORMATION_SCHEMA` (`adframework.raw/stg/gold/core`), comparado com `column_lineage_map.md`, `pipeline_complete_map.md`, `gold_layer_design.md`, `gold_layer_build_plan.md`.

- 🟢 **Paridade RAW↔STG confirmada ao vivo**: `raw.ms_delivery` = `stg.ms_delivery` = 110.919 linhas; `raw.mg_delivery` = `stg.mg_delivery` = 2.627 linhas. STG não descarta linhas — resolve `client_id` via `LEFT JOIN`, mantendo `NULL` quando não resolve.
- 🔴 **Alta** — `gold/ddl/fact_delivery.sql` tem `WHERE client_id IS NOT NULL` no final, descartando **silenciosamente** toda entrega sem client_id resolvido, sem contador nem alerta. Ao vivo: **1.856 linhas / ~999K impressões** de `stg.ms_delivery` ficam de fora do `fact_delivery` por esse motivo — todas históricas (jan-abr/2025), não é sangria atual, mas o mecanismo de descarte silencioso é um risco estrutural (pode voltar a acontecer sem ninguém notar).
- 🟡 **Média** — `core.platform_client_links` tem 31 vínculos MGID e 1 MediaSmart ainda não resolvidos (`stg.unresolved_client_links`). Hoje nenhum tem volume de entrega (por isso `mg_delivery` mostra 0% NULL) — mas é risco latente: se uma dessas campanhas começar a entregar antes de ser vinculada, os dados dela desaparecem do Gold sem aviso.
- 🔴 **Alta** — **5 documentos de lineage centrais estão obsoletos**: `column_lineage_map.md`, `pipeline_complete_map.md`, `id_dependency_map.md`, `id_quality_issues.md`, `id_attribution_map.md` — todos marcados `⚠️ LEGADO — PRÉ-REBUILD 2026-06-16` no cabeçalho, mas descrevem tabelas que não existem mais (`stg.mediasmart_delivery`, `gold.fct_luckbet_delivery_daily`, `core.io_manager_v2` como fonte ativa). Risco real: alguém (inclusive eu, em auditoria futura) ler esses docs sem notar o aviso e tirar conclusão errada.
- 🟠 **Média** — `gold_layer_build_plan.md` (também parcialmente legado) descreve `fact_delivery` com grain incluindo `platform_campaign_id`+`category`; o DDL real usa `day+platform+client_id+formato+goal_type` — **sem granularidade de campanha individual**. Campanha só é rastreável via `fact_delivery_creative`, que é uma tabela separada e não alimenta `fact_pacing`.
- 🟡 **Média (não Alta — verificado)** — `core/ddl/dict_format.sql` documenta fórmula CPC como `(clicks × unit_price) / 1000`; `gold/ddl/fact_pacing.sql` implementa `clicks × unit_price` **sem dividir por 1000** — mas o comentário no próprio `fact_pacing.sql` confirma que essa é a fórmula certa, validada com o usuário em 2026-07-08. **Não é bug ativo, é doc desatualizada** (`dict_format.sql` não foi atualizado após a confirmação). Não afeta o dashboard da Cora hoje.
- 🔴 **Alta — objeto "shadow" fora do controle de versão** — `core.vw_platform_campaign_links` (criada hoje, ao vivo no BigQuery, para resolver o mismatch de schema do Power BI) **não existe em nenhum lugar do repo git** — não está em `core/ddl/`, não está documentada. Se alguém rodar um `DROP`/recriar schema sem saber que ela existe, quebra o Power BI silenciosamente. **Ação recomendada:** commitar o DDL dela em `core/ddl/vw_platform_campaign_links.sql` o quanto antes.

---

## 3. Drift de documentação vs. código

- 🔴 **Alta** — `docs/known_issues.md` não é editado desde **2026-07-08** (commit `7a1edcc`), mas **12 commits depois** (até hoje) mudaram exatamente as áreas dos issues G4/G5 (remap `tecpar_edfcc744 → amigo_db1c2f0c` em `stg/ddl/io_plan.sql` e em `scripts/io_plan/sync_drive.py`). **Verificado ao vivo:** `gold.fact_io_plan` hoje só retorna `amigo_db1c2f0c` (628.100 planejado vs. 256.823 realizado no período) — TecPar como client_id separado não existe mais nos dados. Ou seja, **G4/G5 provavelmente devem ser fechados ou reescritos**, mas isso precisa da sua confirmação de que o gap de budget (59%) é só "falta de plano cadastrado" (como você já sabia) e não um bug novo — pela auditoria, parece ser exatamente isso.
- 🟡 **Média** — `docs/INDEX.md` também está um passo atrás: registra "última validação 2026-06-16" para `known_issues.md`, que na verdade foi validado em 07-08.
- 🟡 **Média** — `docs/session_handoff_2026-06-18.md` descreve MGID/Siprocal como "T1 pendente" — hoje ambos estão com T1-T7/T4 completos. O handoff nunca foi marcado como superado, embora ainda seja referenciado como fonte.
- 🟢 Docs claramente marcados `📋 REBUILD`/`❌ LEGADO` no `INDEX.md` (`etl_expansion_plan.md`, `prod_audit_and_restructuring_plan.md`, `bq_restructuring_plan.md`) estão corretamente sinalizados — esses não enganam ninguém.

---

## 4. Gap estrutural: deploy da camada BQ não tem CI/CD

- 🔴 **Alta** — Não existe nenhum workflow de CI que aplique `raw/ddl`, `stg/ddl`, `gold/ddl`, `core/ddl` ao BigQuery. O único GitHub Action do repo é `cora_sheets_sync.yml` (sync de planilha, não deploy de schema). Isso significa: **um commit de SQL no repo não garante que o BigQuery reflete esse SQL** — alguém precisa rodar `bq query` manualmente. A prova está no próprio achado do item 2: `core.vw_platform_campaign_links` existe ao vivo, mas não no git — a via inversa (algo commitado mas nunca aplicado) é igualmente possível e mais perigosa, porque parece "documentado" sem estar em produção.

---

## 5. O que precisaria para trazer a ingestão para este repo

Hoje a ingestão (conectores MediaSmart/MGID/Siprocal, `orchestrator.py`, roteamento de jobs Firestore, `bigquery.py`) **não vive aqui** — vive no monorepo `adframework` (remote `rshiro-newad/adframework`), no módulo `adframework_python/`, deployado como Cloud Run `adframework-etl` via `.github/workflows/deploy-cloud-run.yml`. Você já tem commit access lá e vem corrigindo esse código diretamente (ex.: commits de hoje `0369b78`, `a9e89af`, `d971f42`). Este repo (`newad-adframework-bq`) hoje só tem DDL/SQL + scripts avulsos (IO Plan, Siprocal legado, Cora).

Duas rotas possíveis, com o que cada uma exige:

**A) Migrar o código de ingestão para cá (unificação total)**
- Mover `adframework_python/src/{orchestrator,bigquery,connectors/*}.py` + `main.py` + `requirements.txt` para este repo.
- Recriar o Dockerfile/config de deploy do Cloud Run `adframework-etl` apontando para este repo.
- Migrar o workflow do GitHub Actions (path-based trigger) para `newad-adframework-bq/.github/workflows/`.
- Migrar/replicar as credenciais (Secret Manager: chaves de API MediaSmart/MGID, service account do Siprocal Sheets) e permissões IAM da service account que hoje o Cloud Run usa.
- Migrar as referências aos Firestore job docs (11 docs mapeados) — nada muda no Firestore em si, só o código que os lê.
- Atualizar `CLAUDE.md` do monorepo `adframework` para remover a menção de que `adframework_python` cuida do ETL, já que passaria a viver só aqui.
- Risco: mistura código de aplicação (Python/Cloud Run) com um repo hoje 100% de warehouse (SQL/DDL) — foge do padrão dos outros 3 serviços do monorepo.

**B) Manter os repos separados, mas fechar os dois gaps que essa auditoria expôs (recomendado como primeiro passo, independente da decisão sobre A)**
- Adicionar CI neste repo que aplica `raw/stg/gold/core` DDL ao BigQuery a cada merge em `main` — fecha o gap do §4 (commit = deployado, sempre).
- Documentar aqui, em `docs/`, um mapa de "onde cada peça do pipeline mora" (Firestore job docs, Cloud Run `adframework-etl`, Cloud Run `io-plan-admin`, e as tabelas RAW que cada um alimenta) — sem duplicar código, só apontar.
- Padronizar o agendamento do IO Plan/Cora sync (hoje manual) via Cloud Scheduler, com histórico de execução persistido em BQ/Firestore em vez de memória.

Minha recomendação: comece pela rota B — ela resolve o risco real que a auditoria encontrou (drift entre repo e BigQuery, docs vs. código) sem o custo de migrar um serviço Cloud Run inteiro. A decisão de unificar tudo em um repo só (rota A) é arquitetural e vale uma conversa à parte, não uma correção de urgência.

---

## Achados por severidade (lista consolidada)

| # | Severidade | Achado | Seção |
|---|---|---|---|
| 1 | 🔴 Alta | `gold.fact_delivery` descarta linhas com `client_id NULL` sem contador/alerta | §2 |
| 2 | 🔴 Alta | 5 docs de lineage centrais obsoletos (pré-rebuild) ainda referenciáveis | §2 |
| 3 | 🔴 Alta | `core.vw_platform_campaign_links` existe ao vivo mas não está no git | §2 |
| 4 | 🔴 Alta | `known_issues.md` parado há 12 commits em área ativa (G4/G5 TecPar/Amigo) | §3 |
| 5 | 🔴 Alta | Sem CI/CD aplicando DDL ao BigQuery — commit ≠ deployado | §4 |
| 6 | 🟠 Média | IO Plan/Cora sync sem agendamento nem histórico persistido | §1 |
| 7 | 🟠 Média | Grain de `fact_delivery` real não tem campanha individual, diverge do design doc | §2 |
| 8 | 🟡 Média | 31 vínculos MGID + 1 MediaSmart não resolvidos (risco latente, sem impacto hoje) | §2 |
| 9 | 🟡 Média | `dict_format.sql` com fórmula CPC desatualizada (código está certo) | §2 |
| 10 | 🟡 Média | `INDEX.md` e `session_handoff` levemente desatualizados | §3 |
| 11 | 🟡 Baixa | `raw.siprocal_raw_sheet` deveria ter sido dropada, ainda documentada como ativa | §1 |
| 12 | 🟡 Baixa | Script Siprocal legado sem banner de "não executar" | §1 |

Nenhuma correção foi aplicada. Me diga quais desses você quer que eu resolva agora (por exemplo: commitar o DDL da `vw_platform_campaign_links` é rápido e de baixo risco) e quais ficam para depois da entrega da Cora.

---

## 6. Plataforma de management/ops (proposta — extensão do escopo, ainda não construída)

Adicionado a pedido do usuário em 2026-07-29, após revisão dos achados acima. Objetivo: um lugar único para (a) editar regras de negócio que hoje vivem "cruas" em SQL, com histórico; (b) ver o estado do pipeline sem escrever query; (c) disparar ações pontuais (ex.: forçar reingestão de um plano quando o comercial avisa de algo fora do padrão).

### 6.1 O que já existe e pode ser reaproveitado (não é greenfield)

- **`services/io-plan-admin`** (Cloud Run FastAPI, neste repo) já é o embrião do pilar de ações: expõe `POST /sync` para forçar a sincronização do IO Plan a partir do Drive. É a base natural para virar o "botão de forçar reingestão" que você pediu para as outras origens.
- **`scripts/sync_io_firestore_to_bq.py`** (no monorepo `adframework`, módulo `adframework_python`) já implementa o padrão "Firestore é fonte de verdade → sincroniza pro BigQuery" para o IO Manager. É o mesmo padrão que serve para regras de negócio versionadas — não precisa inventar arquitetura nova.
- **`orchestrator.py`** já aceita `force_from_date` via `params_json` do job Firestore (`_get_date_range()`), ou seja, o backend já sabe forçar uma janela específica de reingestão — falta só uma UI que chame isso.
- As regras de negócio já estão isoladas em tabelas `core.*` dedicadas — não estão misturadas com dados de entrega. Isso facilita expor exatamente essas tabelas numa UI sem tocar no resto do pipeline.

### 6.2 O problema concreto nas regras de negócio hoje

Inspecionei as duas tabelas centrais:

- **`core.dict_format`** (mapeia `platform + formato → goal_type`, usado para calcular `investimento_realizado`): é editada via `CREATE OR REPLACE TABLE` — **recria a tabela do zero a cada mudança**. O próprio DDL tem um aviso em maiúsculas para não rodar sem re-seed. **Não existe histórico de quem mudou o quê e quando** — só o que o git log mostra sobre o arquivo `.sql`, se alguém lembrar de commitar.
- **`core.advertiser_platform_rules`** (remapeamento de plataforma por anunciante, ex.: Push da Cora = Siprocal): já tem `confirmed_at`/`confirmed_by`/`notes` — ótima prática — mas o mecanismo de atualização é `DELETE FROM ... WHERE TRUE` seguido de `INSERT` com a lista inteira reescrita à mão no arquivo `.sql`. Qualquer erro de digitação numa linha derruba a regra de todos os outros clientes silenciosamente até o próximo `bq query` manual.

Isso confirma exatamente a dor que você descreveu: regra de negócio importante, mudança vinda do comercial, sem trilha visual nem histórico real, dependendo de alguém lembrar de editar SQL certo.

### 6.3 Os 3 pilares e o que cada um exige tecnicamente

**Pilar 1 — Regras de negócio versionadas**
- Coleção Firestore por tipo de regra (ex.: `business_rules/dict_format/entries/{platform}_{formato}`, `business_rules/advertiser_platform_rules/entries/{client_id}_{formato}`), cada doc guardando o valor atual **+ subcoleção `history`** com `{value_anterior, value_novo, changed_by, changed_at, motivo}`.
- Um Cloud Function/Cloud Run job (variante do `sync_io_firestore_to_bq.py` já existente) que materializa o estado atual do Firestore em `core.dict_format`/`core.advertiser_platform_rules` — substituindo o `CREATE OR REPLACE TABLE`/`DELETE+INSERT` manual.
- Efetivação **por data** (não só "valor atual"): se uma fórmula ou mapeamento muda, o `fact_pacing`/`fact_io_plan` de datas passadas não deveria ser recalculado com a regra nova — precisa de `effective_from` para preservar histórico correto em reprocessamentos.
- Tela CRUD simples: listar regras atuais, editar com formulário (não SQL), campo obrigatório de "motivo da mudança" (reaproveita o padrão que `advertiser_platform_rules` já pede em `notes`).

**Pilar 2 — Observabilidade**
- Uma tela que já resolve o achado #6 desta auditoria (IO Plan sync sem histórico persistido): última execução de cada job, sucesso/falha, linhas processadas — lido de Firestore (`last_status`, que os jobs de MediaSmart/MGID/Siprocal já escrevem) + `INFORMATION_SCHEMA.TABLE_STORAGE` do BigQuery (`last_modified_time`, contagem de linhas) para as tabelas RAW/STG/Gold.
- Um card de staleness por origem: "MediaSmart — última linha há 6h (esperado: diário)" — cálculo simples de `MAX(date)` por tabela RAW comparado à cadência esperada.
- Reaproveita a própria estrutura da §1 desta auditoria (semáforo por camada) como ponto de partida do dashboard.

**Pilar 3 — Ações/triggers**
- Estender `io-plan-admin` (ou criar um serviço irmão "ops-console") com botões que chamam:
  - `POST /jobs/{job_name}/run` no orchestrator (Cloud Run `adframework-etl`) com `force_from_date` — para MediaSmart/MGID/Siprocal.
  - O `/sync` que o IO Plan já tem.
- Cada ação precisa: confirmação antes de disparar (evitar clique acidental reprocessando meses de dado), log de quem disparou e quando (Firestore ou BQ), e um retorno visível do resultado (sucesso/linhas/erro) — hoje o `_last_result` do IO Plan se perde a cada restart; isso não pode se repetir na nova plataforma.

### 6.4 Sugestões adicionais (a partir do que conheço do projeto)

- **Aprovação em dois passos para regras com impacto financeiro**: `dict_format` e a fórmula de `investimento_realizado` afetam direto o número que vai pro cliente (ex.: o achado #9 de hoje, a fórmula de CPC). Sugiro que edição de regra por alguém do comercial fique em "pendente" até você (ops) aprovar — simples, mas evita repetir o susto de hoje em produção.
- **Fechar o gap de CI/CD (achado #5) usando a mesma plataforma**: já que ela vai materializar Firestore→BQ para regras de negócio, o mesmo mecanismo serve de base para o CI/CD de DDL sugerido na rota B do §5 — um "botão aplicar" ou pipeline automático que garante commit = deployado, e mostra a diferença entre o que está no git e o que está live (fechando também o problema do achado #3, a view shadow).
- **Alertas reaproveitando infraestrutura já planejada**: o `aat_console` já tem um webhook de alerta de ops planejado (`OPS_ALERT_WEBHOOK_URL`, hoje só faltando provisionar, conforme `docs/PROCESS.md` do outro projeto). Vale plugar os alertas de staleness/falha desta plataforma no mesmo canal em vez de criar um novo.
- **Acesso restrito a ops**: pelo padrão já usado no `aat_console` (Firebase Auth `nwd-aat` com guards `RequireOps`), a plataforma deveria nascer ops-only — comercial só teria acesso à tela de solicitar mudança de regra (pilar 1), não às ações de reingestão (pilar 3) nem ao dashboard técnico completo, se algum dia isso for exposto a mais gente.
- **Trilha de auditoria unificada**: como esta própria auditoria mostrou o custo de não ter histórico confiável (`known_issues.md` desatualizado, TecPar/Amigo remapeado sem nota), a plataforma deveria logar toda ação (mudança de regra, disparo de reingestão) num único lugar consultável — não espalhado entre Firestore, git commit message e memória de alguém.

### 6.5 Decisões em aberto antes de começar a construir

1. Estender `io-plan-admin` como base do "ops-console", ou criar um serviço novo?
2. Onde esse serviço deploya — neste repo (`newad-adframework-bq`) ou no monorepo `adframework`? Depende também da decisão do §5 (rota A vs. B).
3. Quais regras de negócio entram na v1 — só `dict_format` e `advertiser_platform_rules`, ou também `campaign_format_map`/`platform_client_links`?
4. Aprovação em dois passos (comercial propõe, ops aprova) é necessária desde o dia 1, ou pode vir depois?
5. Prioridade real: isso entra depois da entrega da Cora hoje, ou é a próxima frente de trabalho já nesta semana?

---

## 7. Plano de ação — corrigir os 12 achados sem quebrar o banco

Sequenciado por risco, não por severidade do achado. A lógica: primeiro tudo que é **só documentação/git** (risco zero — não toca no BigQuery), depois o que precisa de **verificação antes de decidir** (leitura, sem escrita), depois **mudanças aditivas** no BQ (criam objeto novo, não alteram nada existente), e só por último qualquer coisa **destrutiva ou que altera comportamento de objeto já em uso** — essas exigem seu OK explícito e um backup/reversão testada antes de rodar.

### Fase 0 — Documentação e git (risco: nenhum, não toca no BigQuery)

Pode rodar tudo de uma vez, sem impacto em nada que está no ar hoje.

| Achado | Ação |
|---|---|
| #2 — 5 docs de lineage obsoletos | Mover para `docs/archive/` ou renomear com prefixo `LEGADO_`; atualizar `docs/INDEX.md` apontando pro doc atual (`gold_layer_design.md`) |
| #7 — `gold_layer_build_plan.md` com grain antigo | Mesmo tratamento — marcar como legado, apontar pro DDL real como fonte de verdade |
| #9 — `dict_format.sql` com fórmula CPC desatualizada | Corrigir só o comentário (linha 15), sem tocar no `CREATE TABLE` |
| #10 — `INDEX.md`/`session_handoff` desatualizados | Atualizar datas de última validação |
| #11 — `raw.siprocal_raw_sheet` documentada como ativa | **Já verificado nesta sessão: a tabela não existe mais no BigQuery.** Só remover `raw/ddl/siprocal_raw_sheet.sql` e as menções em `README.md`/`pipeline_complete_map.md` — não precisa de `DROP`, já não há o que dropar |
| #12 — script Siprocal legado sem aviso | Adicionar banner "LEGADO — não executar" no topo de `scripts/siprocal/sync_sheet.py`, igual ao de `cora_sheets_sync.py` |
| #3 — `vw_platform_campaign_links` sem DDL commitado | Ler a definição atual direto do BigQuery (`SELECT view_definition FROM core.INFORMATION_SCHEMA.VIEWS`) e salvar em `core/ddl/vw_platform_campaign_links.sql` — só sincroniza o git com o que já está rodando, não muda nada no BQ |

### Fase 1 — Verificação antes de decidir (risco: nenhum — só leitura)

| Achado | Ação |
|---|---|
| #4 — `known_issues.md` G4/G5 desatualizados | **Já verificado nesta sessão:** `gold.fact_io_plan` hoje só retorna `amigo_db1c2f0c` (TecPar não existe mais como client_id separado); gap de 59% entre planejado e realizado é cobertura de plano ausente (Jul 11-28/Ago), não bug. Falta só sua confirmação de leitura pra eu fechar/reescrever G4-G8 com essa evidência |

### Fase 2 — Mudanças aditivas no BigQuery (risco: baixo — cria objeto novo, não altera nada existente)

Segura porque não mexe em nenhuma view/tabela que Power BI ou outro processo já consome — só adiciona visibilidade nova.

| Achado | Ação |
|---|---|
| #1 — `fact_delivery` descarta client_id NULL sem contador | Criar `core.vw_delivery_unattributed` (ou estender `stg.unresolved_client_links`) somando impressões/cliques perdidos por dia/plataforma — visão nova, `fact_delivery` continua exatamente como está |
| #8 — 31 vínculos MGID + 1 MediaSmart não resolvidos | Não é mudança de schema — é backlog de cadastro em `platform_client_links` via fluxo já existente (Setup, `aat_console`). Sugiro só marcar como item de trabalho, não uma correção técnica |

### Fase 3 — Infraestrutura (risco: médio — precisa de teste antes de automatizar)

Aqui mora o achado mais estrutural (#5) e o de agendamento (#6). Ambos mexem em *como* mudanças chegam no BigQuery, não nos dados em si — mas merecem cautela porque, uma vez automatizados, rodam sem você olhar.

| Achado | Ação | Como testar sem risco |
|---|---|---|
| #5 — sem CI/CD aplicando DDL | Criar GitHub Action que roda `bq query` para `.sql` alterados em `raw/stg/gold/core` no merge pra `main` | Começar com `workflow_dispatch` (trigger manual, você aperta o botão) por 1-2 semanas antes de automatizar no push. E separar em duas categorias: **views** (`CREATE OR REPLACE VIEW` — idempotente, seguro reaplicar) entram no CI liberado; **tabelas com `CREATE OR REPLACE TABLE`/`DELETE+INSERT`** (como `dict_format`, `advertiser_platform_rules`) ficam de fora do CI automático até virarem `MERGE` idempotente — senão o CI pode apagar dado sem querer |
| #6 — IO Plan/Cora sync sem agendamento nem histórico | Adicionar Cloud Scheduler chamando o `/sync` que já existe (não é endpoint novo, só automatiza o clique); trocar `_last_result` em memória por um registro em Firestore ou tabela BQ pequena (`ops.sync_history`) | `/sync` já roda manual hoje sem problema — agendar é só automatizar algo já testado. Persistir histórico é aditivo (tabela nova) |

### Fase 4 — Nada destrutivo pendente

Achado #11 (`siprocal_raw_sheet`) foi o único candidato a `DROP TABLE` desta auditoria — e a verificação mostrou que a tabela **já não existe**. Não há, hoje, nenhuma correção que exija apagar ou sobrescrever dado vivo no BigQuery. Se isso mudar (por exemplo, ao converter `dict_format`/`advertiser_platform_rules` pra `MERGE` na Fase 3), o procedimento mínimo antes de qualquer `DROP`/`CREATE OR REPLACE TABLE` em produção deve ser:

1. `CREATE TABLE ... AS SELECT * FROM ...` — snapshot da tabela atual com sufixo de data, antes de mexer.
2. Rodar a mudança fora do horário em que alguém pode estar olhando dashboard ao vivo (Power BI Import Mode ajuda aqui — não é DirectQuery, então uma `CREATE OR REPLACE VIEW` só afeta o próximo refresh, não quem já tem o relatório aberto).
3. Validar com `SELECT COUNT(*)`/`SELECT * LIMIT 10` antes de considerar concluído.

### Ordem sugerida de execução

```
Fase 0 (hoje ou amanhã, 1 sessão)  →  Fase 1 (precisa só do seu OK de leitura)
   →  Fase 2 (1 sessão)  →  Fase 3 (janela própria, com teste)
```

Nenhuma fase depende de dado ao vivo mudar — pode rodar Fase 0-2 tranquilamente ainda esta semana, inclusive depois da entrega da Cora hoje. Me diga por onde começar.

---

## 8. Padronização de nomenclatura — análise e proposta

Adicionado a pedido do usuário em 2026-07-29. Não existe um documento formal de padronização de nomes no repo (procuramos os dois — não achamos). Esta seção parte de evidência real do código: nome mal padronizado hoje já causa bugs de dado, não é só estética.

### 8.1 Onde nome inconsistente já quebra o pipeline (evidência, não opinião)

- **Nome de arquivo no Drive do IO Plan já causou contagem em dobro de verba.** O parser (`docs/io_plan_pipeline.md`) tem uma regra inteira (`PERSONAL_NAME_TOKENS = {"RAFA", "GESSIANE"}`) só para tentar adivinhar qual arquivo é o "oficial" quando várias pessoas salvam cópias com o próprio nome na mesma pasta. Antes do fix de 2026-06-14, isso já gerou **R$157.500 contado ao invés de R$78.750** pra Cora (dobrou o período 11 Mai–10 Jun).
- **Nome de aba fora do padrão faz o plano inteiro cair sem voo definido.** O parser só reconhece datas em abas com o padrão `DD MÊS A DD MÊS` (regex fixo). Abas com nome livre tipo `JAN-MAR 2026` ou `RESUMO` viram `flight_start/flight_end = NULL` — a linha entra na RAW mas **não entra no core** (fica de fora do plano sem erro visível). Impacta principalmente histórico de 2025 e o Plano NEWAD_CORA 2026 V2 (368 linhas, todas NULL).
- **Plataforma é detectada por substring no nome da estratégia — e "push" sozinho não basta.** `PLATFORM_RULES` mapeia `"push mgid"` → mgid, `"push siprocal"` → siprocal, mas só `"push"` (sem a plataforma no nome) → `platform = 'unknown'`. Foi exatamente esse buraco que gerou a regra manual em `core.advertiser_platform_rules` pro Push da Cora (achado já existente, confirmado 2026-07-08). Cada estratégia de Push nova, de qualquer cliente, cai em `unknown` até alguém notar e criar regra manual — se o nome da estratégia já viesse com a plataforma, o problema não existiria.
- **`core.campaign_format_map` (formato por campanha) é alimentado, entre outras formas, por parsing do `campaign_name`** (`source = 'campaign_name'`, confirmado no schema live do BigQuery) — ou seja, se quem cria a campanha no DSP não incluir um token reconhecível de formato (`Display`, `Native`, `Push`, `Retargeting`, `Video`) no nome, a classificação automática falha e o formato fica sem fonte confiável. Isso se conecta direto com o achado de 489 `goal_type` NULL (7% MediaSmart) já visto nesta auditoria.
- **Resolução de cliente na Siprocal é por texto livre.** `core/ddl/platform_client_links.sql` documenta: `siprocal → advertiser (texto livre UPPER+TRIM; frágil — monitorar mudanças de nome)`. Qualquer variação de grafia no nome do anunciante dentro da Siprocal quebra silenciosamente a atribuição — sem erro, só um novo `client_id = NULL` pendente de confirmação manual.

### 8.2 O que já funciona bem — modelo a replicar, não a mudar

`core.dim_client` já resolveu isso pra ID de cliente: `client_id = {slug}_{8hex}`, imutável, gerado num único lugar (`core/seeds/clients.csv`), `slug` sempre `lowercase a-z0-9_`. Qualquer padronização nova (campanha, arquivo, estratégia) deveria seguir o mesmo princípio: **um formato fixo, gerado/validado em um único lugar, nunca digitado livre em múltiplos sistemas**.

### 8.3 Proposta de convenção por domínio

| Domínio | Onde é usado | Problema hoje | Convenção proposta |
|---|---|---|---|
| **Nome de anunciante nas plataformas** (Siprocal principalmente) | Resolução de `client_id` | Texto livre, sem normalização | Usar exatamente `core.dim_client.name` como grafia oficial; qualquer variação no cadastro da plataforma deve ser corrigida na origem, não compensada via regra manual |
| **Nome de estratégia/campanha no DSP** (MediaSmart/MGID/Siprocal) | Detecção de `platform` (`PLATFORM_RULES`) e `format` (`campaign_format_map`) | Token de formato/plataforma opcional — "push" sozinho não resolve | Padrão obrigatório: `[CLIENTE] · [FORMATO] · [PLATAFORMA se ambíguo] · [complemento livre]`. Ex.: `Cora · Push · Siprocal · Reativação`. Formato sempre um de: Display, Native, Push, Retargeting, Video (os mesmos valores já usados em `campaign_format_map.format`) |
| **Arquivo do IO Plan no Drive** | Seleção do arquivo "oficial" pelo parser | Nomes pessoais (`RAFA`, `GESSIANE`) confundem com o oficial | Arquivo de trabalho pessoal nunca fica na pasta `PLANO/` final — só o oficial, sem nome de pessoa. Se precisar de rascunho, usar subpasta `RASCUNHOS/` (fora do escopo que o parser varre) |
| **Nome de aba (voo) na planilha** | `parse_flight_label` | Abas livres (`RESUMO`, `JAN-MAR 2026`) não geram data | Toda aba de voo segue exatamente `DD MÊS A DD MÊS` (ex.: `11 MAI A 10 JUN`); abas de apoio (resumo, indicadores) devem usar um dos nomes já ignorados pelo parser (`SKIP_SHEETS`) para não gerar linha órfã |

### 8.4 Achado extra desta análise: mais um objeto "shadow" no core

Ao investigar `campaign_format_map` descobri que, assim como `core.vw_platform_campaign_links` (achado #3), **`core.campaign_format_map` existe ao vivo no BigQuery mas não tem DDL commitado em `core/ddl/`**. Mesmo risco: ninguém sabe reproduzir o schema, e um `DROP` acidental não teria como ser revertido a partir do git. **Adicionar à Fase 0** do plano de ação (§7): ler o DDL live (`SELECT ddl FROM core.INFORMATION_SCHEMA.TABLES WHERE table_name='campaign_format_map'`) e commitar em `core/ddl/campaign_format_map.sql`.

### 8.5 Como isso entra no plano de ação (§7)

Padronização de nome **não é um fix técnico isolado** — é mudança de processo que depende do comercial adotar, então não cabe nas Fases 0-3 (que são só código/BigQuery). Proponho uma fase própria:

**Fase 2.5 — Padronização de nomenclatura (depende de adoção do comercial, não só de código)**
1. Documento formal com a tabela do §8.3 (esse vira a base da apresentação que você quer levar ao comercial)
2. Curto treinamento/alinhamento com quem cria campanha nos DSPs e quem organiza a pasta do Drive
3. Endurecer a leitura: hoje o parser *tenta adivinhar* (tokens de nome pessoal, regex de data) — depois que o padrão estiver adotado, trocar o "adivinha" por validação que **alerta** quando um arquivo/campanha foge do padrão, em vez de silenciosamente cair em `NULL`/`unknown`
4. Não é bloqueante para nada do §7 — pode rodar em paralelo, mas o ganho de qualidade de dado (menos `goal_type`/`platform` NULL) só aparece depois que a convenção pegar nas campanhas novas

Isso também vira a espinha dorsal da apresentação para o comercial que você pediu: mostrar a regra de negócio (§6.2 desta auditoria: `dict_format`, `advertiser_platform_rules`, `campaign_format_map`), o problema real que a falta de padrão já causou (§8.1) e a convenção proposta (§8.3) — com dado real do próprio pipeline de vocês, não teoria genérica.
