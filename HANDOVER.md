# HANDOVER.md — newad-adframework-bq

> **Manutenção:** Tier 3 — revisão quando processo de acesso/credencial mudar

Ponto de partida pra qualquer pessoa (ou sessão de IA) nova neste repositório. Runbook
operacional + mapa de acessos + "como isso tudo se conecta" — não repete o que já está
bem documentado em outro lugar, só aponta pra lá.

---

## O que é este projeto, em 1 parágrafo

Pipeline BigQuery Medallion (RAW → STG → CORE → GOLD) que consolida entrega publicitária
de 3 plataformas (MediaSmart, MGID, Siprocal) por cliente, alimentando Power BI. Mantido
por Douglas Reche (escrita); Shiro (`rshiro-newad/adframework`, código do ETL/orquestrador)
tem leitura aqui e é dono do sistema irmão (Admin UI de planejamento de mídia). Arquitetura
completa das 4 camadas, tabelas e views: **[`README.md`](README.md)**.

---

## Como este projeto se organiza como um todo

Duas coisas distintas, frequentemente confundidas por quem chega de fora:

1. **Arquitetura de dados** — schema, camadas, grains, pipeline de ingestão. Fonte de
   verdade: [`README.md`](README.md) (visão geral) + `docs/*_layer_design.md` (detalhe por
   camada) + `docs/INDEX.md` (índice de tudo em `docs/`).
2. **Arquitetura de decisão/documentação** — como o trabalho neste domínio é planejado,
   registrado e mantido em dia. Fonte de verdade: [`CLAUDE.md`](CLAUDE.md).

O sistema de documentação roda em **duas camadas, nunca uma só**:

- **Camada 1 (Notion)** — narrativa completa: raciocínio, alternativas descartadas,
  contexto de negócio, discussão. É onde uma decisão é *entendida*.
- **Camada 2 (este repositório Git)** — marcador técnico enxuto: schema, DDL,
  `CHANGELOG.md`, ADRs curtos. É onde o sistema é *operado* sem precisar de arqueologia.

Teste prático usado pra decidir onde algo vai: "se esse conteúdo sumisse, dá pra
entender/operar o sistema só com código+schema?" Se sim → só Notion. Se não → também
git. Ver `CLAUDE.md`, seção "Protocolo de registro — duas camadas", para o critério
completo.

**Quem escreve onde:** um único agente (`docs`, ver abaixo) é o dono de toda escrita em
`docs/*` e do Notio. Backend e hub-frontend nunca escrevem documentação diretamente —
sempre reportam pro orquestrador, que aciona o `docs`. Isso existe pra evitar que cada
agente documente do seu próprio jeito e os docs divergirem de estilo/estrutura.

---

## Onde cada agente atua

Definições completas em `~/.claude/agents/*.md` (globais, não versionadas neste repo).
Resumo de fronteira:

| Agente | Escopo | Nunca mexe em |
|---|---|---|
| `backend` | Conectores de plataforma, orquestração ETL (`adframework_python`, repo Shiro), DDLs de qualquer camada BQ (`raw/stg/core/gold/marts/share` aqui) | `hub/` (front-end), documentação (`docs/*`) |
| `hub-frontend` | Painel Streamlit `hub/` — abas, deploy (`hub/deploy.sh`), IAM das SAs do hub | `adframework_python`, qualquer DDL de pipeline, `docs/*` |
| `docs` | Única escrita em `docs/*`, `hub/README.md`, Notion (tasks + segundo cérebro de decisão) | Código — nunca implementa, só documenta o que já foi implementado |
| `historical-data-analyst` | Investigação de planilha histórica crua por cliente (`douglas-bq-staging.raw.historical_uploads` → `scripts/deploy/historical_mappings/<client_id>.py`) | Ingestão automática (`backend`), UI do hub (`hub-frontend`), produção |

Fluxo de documentação é sempre em 3 saltos: `backend`/`hub-frontend` terminam um pacote →
reportam pro orquestrador → orquestrador aciona `docs` → `docs` documenta e confirma de
volta. Nenhum agente pula direto pro `docs`. Detalhe completo: `CLAUDE.md`, seção "Fluxo de
documentação é sempre em 3 saltos, nunca pulado".

---

## Rodar do zero

1. **Autenticar no GCP:**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project adframework
   ```
2. **Confirmar acesso aos dois projetos GCP** (ver Matriz de Ambientes abaixo):
   `adframework` (produção) e `douglas-bq-staging` (staging).
3. **Ler `README.md`** pra entender a arquitetura de 4 camadas e o estado atual das
   tabelas/views.
4. **Ler `docs/known_issues.md`** — é o doc mais vivo do repo, tem os issues abertos que
   moldam decisões do dia a dia.
5. **Comandos mecânicos** (aplicar DDL, rodar o hub local, sync de planilhas): ver
   [`AGENTS.md`](AGENTS.md).
6. **Antes de qualquer trabalho substancial**: ler `CLAUDE.md` inteiro — define o
   protocolo de orquestração/Notion que toda sessão de trabalho real segue.

---

## Mapa de acessos (não segredos)

| Recurso | Onde | Quem tem acesso |
|---|---|---|
| Projeto GCP `adframework` (produção) | BigQuery + Firestore + Firebase Auth + Cloud Run ETL | Douglas (escrita), Shiro (leitura/análise) |
| Projeto GCP `douglas-bq-staging` | BigQuery standalone, ambiente de teste | Só Douglas |
| Projeto GCP `striped-bonfire-489318-t9` | Dashboard emergencial temporário — **nunca modificar** | N/A |
| Repositório `newad-adframework-bq` (este) | DDLs, scripts, docs, hub | Douglas (escrita) |
| Repositório `rshiro-newad/adframework` | Código ETL/orquestrador, Admin UI do Shiro | Shiro (escrita), Douglas (leitura) |
| Cloud Run `adframework-etl` | ETL de produção | Projeto `adframework` |
| Cloud Run `douglas-data-hub` | Painel Streamlit do Douglas | Projeto `adframework`, SAs próprias (ver `hub/deploy.sh`) |
| Notion (Camada 1) | Tasks, decisões, contexto de negócio | Douglas |
| `core/OWNERSHIP.yaml` | Fonte única de ownership dos objetos do dataset `core` (pipeline / Admin UI do Shiro / legado) | — |

Credenciais/segredos reais (senhas, chaves de SA, tokens) **não vivem neste documento nem
em nenhum arquivo do repositório** — ficam em variáveis de ambiente do Cloud Run, secrets
do GitHub Actions, ou Secret Manager. Ver `docs/environments.md` pra diferença de
IAM/service-accounts entre os dois projetos GCP.

---

## Runbooks operacionais

| Situação | Doc |
|---|---|
| Promover uma mudança de staging pra produção | `docs/runbook_promocao_ambiente.md` |
| Conector quebrado, job de ingestão não rodou, dado parado | `docs/runbook_incidente_operacional.md` |
| Entender diferença entre `adframework` e `douglas-bq-staging` | `docs/environments.md` |
| Auditar/atualizar documentação | `~/.claude/agents/docs.md` (protocolo do agente `docs`) |

---

## Mapa de Documentação — o que ler e quando

Ponteiro de navegação, não resumo — cada linha diz o que o doc é, quando ele é
atualizado (regra já definida em `~/.claude/agents/docs.md`) e, principalmente, quando
uma sessão nova (humana ou IA) deveria abri-lo **antes** de começar a mexer em algo,
não só depois que o problema já apareceu.

| Doc | O que é (1 frase) | Quando atualizar (Tier + gatilho) | Quando ler antes de executar tarefa |
|---|---|---|---|
| `README.md` | Porta de entrada — arquitetura em 4 camadas + estado atual em 1 parágrafo | Tier 3 — só quando a arquitetura de alto nível muda | Primeira vez no repo, ou pra confirmar em que camada/dataset uma tabela vive antes de tocar nela |
| `docs/INDEX.md` | Índice de todo `docs/` com status (ATUAL/LEGADO/HISTÓRICO) e data de validação | Tier 1 — gerado/atualizado a cada doc novo ou reclassificado | Antes de criar um doc novo (achar se já existe um que cobre o tema) ou de confiar em qualquer doc — checar se o status é ✅ ATUAL antes de usar como referência |
| `CHANGELOG.md` | Log cronológico terso de decisões e mudanças | Tier 2 — toda mudança real commitada | Pra reconstruir "o que mudou desde X" sem vasculhar `git log`; antes de assumir que um comportamento antigo ainda vale |
| `docs/known_issues.md` | Issues abertos/resolvidos do pipeline pós-rebuild | Tier 2 — a cada sessão de trabalho | **Sempre**, antes de investigar qualquer comportamento estranho de dado/pipeline — é o doc mais vivo do repo; provável que o gap já esteja catalogado |
| `docs/adr/NNNN-*.md` | Um por decisão arquitetural, formato MADR curto, imutável após aceito | Nunca editado — decisão que muda vira ADR novo (`Supersedes: NNNN`) | Antes de reverter ou questionar uma decisão arquitetural existente — checar se já existe ADR justificando o porquê antes de propor mudança |
| `docs/raw_layer_design.md` | Design da RAW layer — T1-T7, campos, grains, tamanhos de imagem, tratamentos do IO Plan | Tier 1 (inventário) + 2 (racional) — nova tabela/campo RAW ou gap resolvido | Antes de mexer em qualquer conector de ingestão (MediaSmart/MGID/Siprocal) ou tabela `raw.*` |
| `docs/stg_layer_design.md` | Design da STG layer — resolução de `client_id`/`formato`/`goal_type` por plataforma | Tier 1 + 2 — nova tabela STG ou mudança de regra de resolução | Antes de mexer em qualquer view/tabela `stg.*` ou investigar por que um registro não resolveu client_id |
| `docs/gold_layer_design.md` | Design da GOLD layer — grains, racional financeiro, inventário das views de `adframework.gold` | Tier 1 + 2 — nova view GOLD ou mudança de grain | Antes de criar/alterar qualquer view `gold.*` ou de explicar uma métrica pro Power BI/cliente |
| `docs/architecture_overview.md` | Diagrama executivo C4 Nível 2 (Mermaid) — Ingestão → Transformação → Consumo, sem jargão técnico | Tier 3 — só quando componente novo de sistema entra (novo conector, novo canal de consumo) | Antes de apresentar o projeto pra alguém não-técnico (chefia, stakeholder), ou pra dar contexto rápido de arquitetura sem entrar em detalhe de schema |
| `docs/core_layer_design.md` | **Não existe hoje** — lacuna nomeada (RAW/STG/GOLD têm doc, CORE não) | — | N/A até ser criado; se for criar tabela em `core`, ver `core/OWNERSHIP.yaml` primeiro |
| `docs/API_Doc_MediaSmart.md`, `docs/MGID_API_Doc.md` | Cópia/resumo da doc oficial de API de cada vendor | Tier 3 — quando a API do vendor muda | Antes de implementar/depurar qualquer chamada de API MediaSmart ou MGID — fonte primária, não confiar em memória de sessão anterior |
| `docs/mediasmart_api_reference.md` | Resumo estruturado da API MediaSmart pro ETL | Tier 3 | Referência rápida de campo/endpoint ao escrever código de ingestão MediaSmart (complementa o doc oficial acima) |
| `docs/api_capabilities.md` | Inventário do que cada API (MediaSmart/MGID/Siprocal) expõe — dimensões/métricas disponíveis vs. coletadas hoje | Tier 2 — sempre que uma plataforma/API nova for integrada ao pipeline (ex: Google Ads, Meta Ads) | Antes de propor captar um campo/dimensão novo — checar se a API já expõe ou se é gap confirmado |
| `docs/google_ads_integration.md`, `docs/meta_ads_integration.md` | Guias de integração pendente (credenciais OAuth2, schema proposto) | Tier 3 — enquanto a integração não for feita, atualizar a cada avanço de credencial/step | Antes de retomar o trabalho de integrar Google Ads ou Meta Ads — evita repetir steps de OAuth já feitos |
| `hub/README.md` | Documentação do painel Streamlit (`hub/`) | Tier 3 — nova aba ou mudança de deploy | Antes de mexer em qualquer aba do hub ou no `hub/deploy.sh` |
| `HANDOVER.md` (este arquivo) | Runbook operacional + mapa de acessos + como o projeto se conecta como um todo | Tier 3 — processo de acesso/credencial muda | Primeiro arquivo de qualquer sessão nova, antes do `README.md` |
| `core/OWNERSHIP.yaml` | Fonte única de ownership de objetos do dataset `core` (pipeline / Admin UI do Shiro / legado) | Tier 2 — objeto novo em `core` ou mudança de dono | Antes de criar, alterar ou dropar qualquer tabela/view em `core.*` — decide se você tem permissão de mexer nela |
| `AGENTS.md` | Comandos mecânicos do repo (build/test/deploy) pra qualquer IA | Tier 3 — comando de build/test/deploy muda | Antes de rodar qualquer comando de setup/deploy pela primeira vez numa sessão |
| `docs/environments.md` | Matriz `adframework` (produção) vs. `douglas-bq-staging` (staging) — IAM/SAs por camada | Tier 3 — diferença de IAM/ambiente muda | Antes de rodar qualquer coisa contra staging ou produção pela primeira vez, ou ao debugar erro de permissão |
| `docs/runbook_promocao_ambiente.md` | Runbook de promoção staging → produção via `apply_ddl.py` + rollback | Tier 3 — mecanismo de promoção muda | Antes de promover qualquer DDL de staging pra produção |
| `docs/runbook_incidente_operacional.md` | Matriz sintoma → causa provável → ação pra falha de conector/ingestão | Tier 3 — novo incidente real resolvido | Primeiro doc a abrir quando um job de ingestão falhou ou dado parou de chegar |
| `~/.claude/agents/docs.md` | Protocolo completo do agente `docs` (padrão de escrita, Notion, expurgo) | Fora do repo — mantido pelo próprio agente `docs` | Antes de pedir uma auditoria de documentação ou de decidir onde um registro novo deveria morar |

---

## Regras absolutas — nunca violar

Ver `CLAUDE.md`, seção "Regras absolutas", para a lista completa e atualizada (datasets
intocáveis, tabelas do Admin UI do Shiro, projeto emergencial, boundary do repo do Shiro).
Não duplicado aqui de propósito — evita a lista divergir entre dois arquivos.
