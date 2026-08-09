# CLAUDE.md — AdFramework BQ Pipeline

Instruções permanentes para sessões Claude Code neste repositório.
Carregado automaticamente em toda nova sessão.

> **⚠️ Repositório irmão no mesmo workspace VS Code:** `adframework` (produto AAT
> Console — pixel, atribuição, onboarding de cliente) é um repositório e domínio de
> produto **completamente diferente** deste, só compartilha o workspace por
> conveniência de navegação. Ele tem seu próprio `CLAUDE.md`
> (`adframework/CLAUDE.md`) com fases/módulos próprios. Se o trabalho migrar pra lá —
> mesmo no meio desta sessão — **leia aquele `CLAUDE.md` antes de agir**, não assuma
> que as regras deste arquivo se aplicam.

---

## Contexto

- **Repo:** `newad-adframework-bq` — SQL, DDLs, seeds, migrations, agents BigQuery
- **Projeto GCP (produção):** `adframework`
- **Pipeline:** RAW → STG → CORE → GOLD → Power BI
- **Maintainers:** Douglas Reche (escrita), Shiro (leitura via `rshiro-newad/adframework`)
- **Second brain:** Notion — contexto, decisões e estado de negócio

**Escopo do protocolo:** tudo definido neste arquivo vale para todo trabalho seu no
domínio AdFramework/BQ Governance, independente de em qual repositório físico o código
correspondente roda. Isso inclui trabalho de captação de API/conectores cujo código sobe
pra `main` do `rshiro-newad/adframework` (leitura ali é permitida pra confirmar fato
real; escrita nunca). **A documentação desse trabalho mora sempre aqui, em
`newad-adframework-bq/docs/`** — nunca duplicada ou criada no repositório do Shiro. O
critério de aplicação do protocolo é "é trabalho seu nesse domínio", não "o código está
fisicamente nesta pasta".

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

### Task selecionada é âncora do trabalho novo que ela gerar

Quando uma task existente do Notion é puxada pra trabalhar (passo 0), ela vira a âncora
de qualquer sub-passo descoberto durante a execução/investigação dela — nunca cria MÃE
nova nem task solta por padrão. Se os sub-passos forem uma sequência genuína (ver
critério acima), entram como filhos numerados da task selecionada. Só vira task/MÃE
separada se o trabalho descoberto for genuinamente desconectado do escopo original —
não relacionado à pergunta que a task original estava respondendo.

**Exemplo real (2026-08-04):** a task "Analisar resiliência e rastreabilidade da camada
Gold" revelou um problema real (regras de negócio sem versionamento, mudança retroage
sobre o histórico). A correção (5 passos: schema, backfill, atualizar views, documentar
procedimento, aplicar no desenho de `client_business_rules`) **não virou MÃE nova** —
entrou como sequência de sub-passos dentro da própria task original, porque é
consequência direta da mesma investigação, não um assunto desconectado.

**Não é regra rígida — confirmar quando parecer fora de contexto.** Se o usuário pedir
algo que pareça desconectado da task/MÃE em andamento, o orquestrador **confirma
explicitamente** se é uma interrupção intencional (ex: apagar um incêndio urgente) antes
de simplesmente encaixar dentro da task atual ou assumir task nova sem perguntar. Depois
de resolver a interrupção, retomar a task original de onde parou. Trabalho real às vezes
exige sair do fluxo planejado — a âncora de task ajuda a manter contexto claro, mas não
pode travar uma mudança de prioridade legítima.

**Sinalização ativa de desvio (o usuário tem TDAH — pedido explícito dele, 2026-08-05).**
Diferente da confirmação pontual acima (que é sobre pedir desconectado do contexto), isso é
uma vigilância mais proativa: se o usuário começar a pedir várias coisas em sequência que
se afastam progressivamente da task/MÃE em andamento (não um pedido isolado, mas uma deriva
ao longo de várias mensagens), o orquestrador **aponta isso explicitamente** — "isso parece
estar se afastando de X, é uma mudança de escopo legítima (achado novo, prioridade mudou) ou
é bom voltar pro que estávamos fazendo?" — em vez de simplesmente seguir cada pedido novo
sem comentar. A decisão final é sempre do usuário (ele confirma se é desvio real ou escopo
novo genuíno), o papel do orquestrador é só trazer a pergunta à tona, sem julgar sozinho nem
travar o pedido.

### Formato de relato ao usuário — sempre ancorado na MÃE

Todo resumo/atualização trazido pro chat (não só o relato completo de fim de macro
task — qualquer momento em que a sessão principal reporta progresso) segue esta
estrutura, pra manter usuário e orquestrador sempre alinhados sobre onde aquele
trabalho se encaixa:

- **Título maior:** a MÃE em que o trabalho está acontecendo agora.
- **Abaixo dela:** o que está sendo feito especificamente — pode ser a sub-task em
  andamento, uma resolução/decisão nova, um achado que vira outra sub-task dentro da
  mesma MÃE, ou um achado que sai do escopo original e vira outra MÃE pra depois (ver
  "Task selecionada é âncora" acima pra critério de quando é um vs. outro).

Não é burocracia pra cada frase — é pra qualquer momento em que o usuário precisa
entender "onde estamos" dentro da árvore de trabalho, especialmente ao trocar de
assunto ou retomar depois de uma pausa.

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
3. Docs técnicos (Camada 2) — atualizados via processo do `docs.md`, não à mão. Para
   todo doc **novo** criado na sessão, confirmar que ele tem o cabeçalho de manutenção
   no topo (`> **Manutenção:** Tier <N> — <gatilho de atualização>`, logo abaixo do
   título) — não basta o conteúdo estar correto, o gatilho de quando revisitar aquele
   doc de novo precisa estar visível dentro do próprio arquivo, não só na task Notion
   ou no plano de reestruturação
4. **git commit** — pedir confirmação ao usuário antes de commitar
5. **git push** — sempre na sequência do commit, mesmo passo, não ação separada pra
   lembrar depois (achado real 2026-08-06: 10 commits ficaram só locais por dias porque
   "commitar" e "publicar de verdade" foram tratados como coisas diferentes)
6. **Conferir se qualquer estado só-desta-sessão foi externalizado** — em especial a
   lista de tarefas pendentes (todo list), que é local e não sobrevive ao fim da sessão.
   Se sobrar item pendente que só existe nessa lista, ele precisa virar entrada na task
   Notion correspondente (Camada 1) antes de considerar o fechamento completo — senão
   ele simplesmente desaparece quando a sessão fecha.

### Sugerir encerramento proativamente, não só executar quando pedido

Ao chegar num **marco natural de pacote de trabalho** (mesmo critério já usado pra
chamar o `docs` — ver "Cadência de documentação em MÃE longa" acima) **e** a sessão já
estar longa (múltiplas compactações, vários dias de conversa, ou simplesmente um volume
grande de trabalho fechado), rodar o checklist acima e **propor explicitamente ao
usuário**: encerrar esta sessão agora e continuar numa nova, já que o registro em 2
camadas (Notion + Git) existe exatamente pra isso — sessão nova custando menos por turno,
sem herdar o histórico bruto.

**Por quê:** sessão longa sem nunca fechar o ciclo custa mais por turno (todo o histórico
é recarregado) e aumenta o risco de decisão importante nunca ser escrita antes de uma
compactação apagar o detalhe (aconteceu de verdade em 2026-08-05→06 — ver CHANGELOG). O
sistema de 2 camadas já deveria tornar a fronteira de sessão barata — mas isso só
funciona se o fechamento realmente acontecer, não fica implícito.

**Isto é sugestão, nunca decisão unilateral** — a IA não tem como encerrar a sessão
sozinha; propõe, explica o porquê, e a decisão de continuar ou abrir nova sessão é
sempre do usuário. Não insistir se ele preferir continuar na mesma sessão.

**Sempre junto com a sugestão, entregar o prompt de abertura pronto pra próxima
sessão** — não deixar o usuário ter que descobrir sozinho por onde começar. O prompt
deve apontar pra onde o checkpoint foi escrito (a task/MÃE Notion específica atualizada
no passo 6 do checklist acima), não repetir o conteúdo do checkpoint no próprio prompt —
a nova sessão lê de lá. Formato mínimo: qual repositório, qual `CLAUDE.md` ler, qual
task Notion tem o checkpoint completo, e uma linha dizendo "comece por aí".
