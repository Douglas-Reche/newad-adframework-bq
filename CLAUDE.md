# CLAUDE.md — AdFramework BQ Pipeline

Instruções permanentes para sessões Claude Code neste repositório.
Carregado automaticamente em toda nova sessão.

---

## Contexto

- **Repo:** `newad-adframework-bq` — SQL, DDLs, seeds, migrations, agents BigQuery
- **Projeto GCP (produção):** `adframework`
- **Pipeline:** RAW → STG → CORE → GOLD → Power BI
- **Maintainers:** Douglas Reche (escrita), Shiro (leitura via `rshiro-newad/adframework`)
- **Second brain:** Notion — contexto, decisões e estado de negócio

---

## Regras absolutas — nunca violar

| O que | Regra |
|---|---|
| Datasets `pixel`, `adtracking`, `analytics`, `finops_billing` | **Intocáveis** — serviços externos, nunca modificar |
| Tabelas do Admin UI do Shiro (lista completa em `core/OWNERSHIP.yaml`) | **Nunca referenciar no pipeline gold.** `core/OWNERSHIP.yaml` é a fonte única — não copiar/manter essa lista em mais de um arquivo; `backend.md`, `hub-frontend.md` e este documento todos apontam pra lá |
| Projeto `striped-bonfire-489318-t9` | **Nunca modificar** — dashboard emergencial temporário |
| Repo `rshiro-newad/adframework` | **Somente leitura** — analisar, nunca modificar |

---

## Protocolo de relato de subagentes/background tasks

Quando um subagente ou tarefa em background termina, o relato completo vai pro usuário
**no momento em que a notificação chega** — nunca só resumido silenciosamente num
todo/memória. O relato inclui: o que o agente fez de fato, o que encontrou/construiu,
ressalvas que ele mesmo levantou, e referências de arquivo.

**Memória (mecanismo de recall entre sessões) nunca é a fonte de verdade do que foi
comunicado ao usuário** — é só continuidade interna. Se algo existe comprimido na memória
mas nunca foi dito ao usuário em texto completo, trate como **não confirmado** e recheque
antes de assumir que é verdade.

**Por quê:** caso real (2026-08-03, investigação Siprocal) — um achado sobre "impressões
visíveis" nas APIs MGID/MediaSmart foi comprimido na memória como "confirmado" e a tarefa
marcada concluída sem o achado real ter sido apresentado a Douglas em texto completo. Ao
reconferir o código diretamente, o campo não existia em nenhum dos dois conectores — a
compressão silenciosa tinha criado um estado "concluído" falso. Tarefa revertida pra
pendente.

**Conexão obrigatória com o Notion (Camada 1):** todo relato completo de subagente/
background (acima) **também** vira uma entrada datada na task correspondente do Notion —
não é opcional, não é "resumir depois", é o mesmo conteúdo, no momento em que chega. Só
depois que um fato técnico estabiliza (schema confirmado, decisão fechada) é que ele
também recebe o marcador enxuto no doc técnico (Camada 2, ver seção seguinte). Três
destinos diferentes pra três momentos da mesma informação — nenhum deles opcional:
`chat (relato completo) → task Notion (entrada incremental) → doc técnico (marcador final)`.

**Fluxo de documentação é sempre em 3 saltos, nunca pulado:** backend/hub-frontend
terminam uma macro task → reportam pro **orquestrador** (nunca chamam `docs` diretamente,
mesmo pra mudança 100% interna ao próprio escopo deles) → o orquestrador chama `docs` com
o relato completo → o `docs` documenta (Notion + git conforme a camada) e **avisa o
orquestrador que terminou**. O orquestrador só considera a macro task encerrada depois
dessa confirmação de volta. Isso evita duas tasks Notion duplicadas quando um trabalho
cruza backend+hub e cada lado não sabe o que o outro já registrou.

---

## Fluxo de trabalho da sessão principal (orquestrador)

Toda sessão que orquestra trabalho (a sessão principal, não um dos agentes
especializados chamado por ela) segue esta ordem — não é opcional pra pacotes de
trabalho reais (planejamento de um dia, um projeto, uma feature); não precisa aplicar a
pergunta pontual isolada:

0. **Checar o Notion por MÃEs/tasks abertas relacionadas antes de começar** — obrigatório
   no início de qualquer sessão de trabalho real, não só quando "parece que já existe
   algo". Sem esse passo, uma sessão nova (que não viu o que a sessão de ontem fez) pode
   criar uma MÃE duplicada pra um trabalho já em andamento (ex: "Integrar Google Ads" já
   aberta, sessão nova cria "Integração Google Ads" de novo sem saber). Se achar uma MÃE
   relacionada, ela ganha prioridade — continue nela em vez de criar nova.
1. **Definir escopo primeiro** — discutir com o usuário o que precisa ser feito, rodar as
   análises necessárias, antes de construir qualquer coisa.
2. **Antes de começar a construção**, com o escopo já fechado, **chamar o agent `docs`**
   pra registrar o plano como task(s) no Notion — agrupadas, classificadas, com nomes
   compreensíveis pra quem não é técnico, já estruturadas como MÃE + sub-tasks quando
   fizer sentido (ver "Convenção de criação de tasks" em `docs.md`). Isso acontece **antes**
   da execução, não depois — é o que faz o Kanban/Timeline refletirem o planejado, não só
   o já feito.
3. **Durante a execução**, a sessão principal mantém controle interno do que está sendo
   feito (todo list) — não é opcional, é o que possibilita o passo 4 sem depender de
   memória.
4. **Ao final de um pacote de trabalho** (não precisa ser fim de sessão — pode ser um
   marco natural no meio dela), **chamar o agent `docs` de novo** pra documentar tudo que
   foi feito de fato: Camada 2 (docs técnicos) + Camada 1 (Notion, atualizando as tasks
   criadas no passo 2 com o resultado real — não criar tasks novas pra trabalho que já
   tinha task do passo 2, atualizar a existente).

### Critério de pré-registro no Notion

Conta como "pacote de trabalho real" (passa pelo fluxo de 4 passos acima) se **qualquer**
destes for verdade: toca mais de 1 arquivo, muda comportamento observável do sistema (não
só refactor interno), ou o usuário vai perguntar sobre isso depois. Senão, é "pergunta
pontual" — isenta do pré-registro, mas ainda entra no relato normal ao final se relevante.

### MÃE vs. task única

Vira MÃE quando o trabalho tem múltiplos entregáveis independentes que fazem sentido
sozinhos (ex: "Integrar Google Ads" → sub-tasks como "mapear schema da API", "definir
client_id mapping", "desenhar conector", "testar contra sandbox") — cada sub-task é algo
que alguém de fora entenderia como um passo reconhecível, não um passo artificial só pra
ter hierarquia. Se o trabalho é uma coisa só sem partes separáveis, fica task única, sem
forçar sub-divisão.

### Cadência de documentação em MÃE longa

Não espera todas as sub-tasks fecharem pra chamar o `docs` pela primeira vez. Chama a cada
**checkpoint natural** — um cluster de sub-tasks concluídas que já forma um resultado
coerente e reportável (mesmo critério do "pré-registro" acima) — não um número fixo de
sub-tasks, porque isso varia por natureza do trabalho. O `docs` registra "o que está
pronto até agora + o que está em andamento" na task MÃE, e o ciclo se repete até a MÃE
inteira fechar.

---

## Pesquisa externa — priorizar Gemini antes de gastar token Claude

Quando a tarefa exigir pesquisa na internet (boas práticas, documentação de API de
terceiro, benchmark, "como outros times resolvem X") — qualquer coisa que **não** dependa
de acesso vivo a este BigQuery/Firestore/repositório/Notion — a IA ofereça ao usuário um
prompt pronto pra colar no Gemini (que ele já tem disponível, com token mais barato/menos
limitado) em vez de gastar o orçamento do Claude rodando a pesquisa. O prompt deve incluir
contexto suficiente pro Gemini responder sem acesso a esta conversa, e instrução de
formato de saída (estruturado, com fonte) pra facilitar reintegrar a resposta.

**Não delega pro Gemini:** leitura/escrita de código do projeto, DDL, Notion, ou qualquer
coisa que exija as ferramentas/credenciais que só existem aqui (BigQuery, Firestore, git
deste repo, Notion MCP).

---

## Protocolo de registro — duas camadas

**Camada 1 — Notion (tasks), mantida pelo agent `docs`:** todo trabalho definido (plano
grande ou task pequena) vira uma task no Notion, com data de início/fim. As
resoluções/decisões são atualizadas **dentro da task** conforme o trabalho avança — é
aqui que mora o detalhe semântico: raciocínio, porquê, discussão, alternativas
consideradas, nuances de decisão. Consulte essa camada pra reconstruir o histórico
completo de uma decisão.

**Camada 2 — GitHub/repositório, mantida pelo agent `docs`:** documentação técnica e
estrutural — schema, arquitetura, comportamento do sistema. Deliberadamente **sem** o
detalhe narrativo/semântico da discussão — isso fica só na Camada 1.

**Critério pra decidir o que entra em cada camada** (não é caso-a-caso, é uma regra):
não é uma divisão por **tópico** ("isso é técnico" vs. "isso é de negócio") — é uma
divisão por **profundidade**. Toda decisão que muda o sistema ganha as duas coisas ao
mesmo tempo:
- Um marcador técnico **enxuto** no git (ex: ADR curto — Contexto/Decisão/Consequências
  em um parágrafo, ou entrada no `CHANGELOG.md`) — o suficiente pra entender **o quê**
  mudou e onde, sem o porquê completo.
- A **narrativa completa** na task correspondente do Notion — discussão, alternativas,
  contexto de negócio, processo de decisão. O marcador do git linka pra lá.

**Teste prático:** "se esse conteúdo sumisse, dá pra entender/operar o sistema só com
código+schema?" Se sim, é semântico/narrativo → só Notion. Se não — se é informação
necessária pra operar o sistema sem arqueologia — é técnico → git (mesmo que resumido).

### O que vai só pro git
- DDL, migrations, seeds/CSVs de referência, scripts SQL de auditoria, agentes Python
- Documentação técnica de API e design de camada (schema, grain, comportamento)
- `CHANGELOG.md` — obrigatório em toda sessão com decisão relevante
- `docs/INDEX.md` — mantido pelo processo definido em `docs.md` (não editar à mão fora
  desse processo; a meta é o índice ser derivado do estado real dos docs, não mantido
  manualmente entrada por entrada — ver "docs mestres" em `docs.md`)

**Formato CHANGELOG:**
```
## YYYY-MM-DD — {título}
{1-3 linhas: o que foi feito e por quê}
```

### O que vai só pro Notion
- Discussão/raciocínio completo por trás de uma decisão
- Contexto de cliente (prazos, pedidos, histórico comercial)
- IO Plans e contexto de entrega
- Perguntas pendentes para área comercial

### O que vai pros dois (marcador técnico enxuto + narrativa completa linkada)
- Toda decisão arquitetural relevante (ADR curto no git ↔ task completa no Notion)
- Novo cliente → seed no git + task no Notion
- Novo link plataforma → cliente → seed no git + task no Notion

---

## Checklist de fim de sessão

Executar nesta ordem antes de encerrar:

1. `CHANGELOG.md` — entry com data e resumo das decisões
2. **Conferir** (não é o único ponto de atualização — ver protocolo de relato acima) que
   toda task Notion tocada na sessão está com a narrativa completa até o momento
3. Docs técnicos (Camada 2) — atualizados via processo do `docs.md`, não à mão
4. **git commit** — pedir confirmação ao usuário antes de commitar
