# Follow-up — Pesquisa de Arquitetura de Documentação (complemento à de 2026-08-08)

> Prompt para reenviar ao Gemini Deep Research. Complementa `docs/pesquisa_documentacao_2026-08-08.md`,
> cujo diagnóstico (seção 9) já apontou 5 gaps no nosso repositório. Este follow-up pede profundidade
> extra em 4 pontos que a primeira rodada deixou genéricos demais pra aplicar de verdade, mais um 5º
> ponto novo (o mais importante dos cinco): um método de **enxugamento**, já que a primeira rodada só
> ensinou a adicionar e isso fez o número de docs mestres saltar de forma desproporcional ao tamanho
> real da operação.

---

## Contexto (não mudou desde a pesquisa anterior)

Mantemos um pipeline de engenharia de dados em arquitetura Medallion (RAW → STG → CORE → GOLD) no
Google Cloud Platform / BigQuery, com um frontend interno em Streamlit ("Hub") para operação e
monitoramento. Fontes externas: conectores de APIs de mídia programática (MediaSmart, MGID) e uma
planilha Google Sheets (Siprocal). Não usamos dbt — a transformação é feita via scripts Python e SQL
DDL versionados diretamente no repositório.

**Staging e Produção são dois projetos GCP fisicamente separados**, não datasets diferentes dentro do
mesmo projeto: `adframework` é o projeto de produção (BigQuery + Firestore + Firebase ao vivo,
consumido pelo Hub e por clientes reais); `douglas-bq-staging` é o projeto de staging, criado para
validar o rebuild da pipeline (RAW→STG→CORE→GOLD) antes de promover para produção, com seu próprio
IAM isolado. Essa separação em nível de projeto (não de dataset) ainda não tem nenhum documento formal
descrevendo o que vigora em cada um, como promover mudanças de um para o outro, nem como evitar dados
de teste vazarem para produção ou vice-versa.

## O que mudou / o que precisamos agora

A pesquisa anterior respondeu bem "o que existe como padrão de mercado", mas ficou genérica demais
em 4 pontos específicos. Precisamos de respostas mais aplicadas antes de criar os arquivos de verdade.

### 1. Padrão de documentação em cenário multi-repositório com ownership assimétrico

Nosso caso real não é um repositório único de uma equipe única. Temos:
- `newad-adframework-bq` — repositório principal, onde eu (dono do pipeline) tenho escrita total.
- Um segundo repositório (`rshiro-newad/adframework`), mantido por outra pessoa, ao qual só tenho
  **acesso de leitura** para fins de análise — nunca escrevo lá.

Pergunta: qual é o padrão de mercado para arquitetura de documentação (ADRs, runbooks, `AGENTS.md`,
diagramas de arquitetura) quando dois repositórios compartilham o mesmo domínio de dados mas têm
fronteiras de escrita assimétricas? Especificamente:
- Um ADR que documenta uma decisão que afeta os dois repositórios deve viver em qual dos dois, e como
  o outro repositório referencia essa decisão sem duplicar o texto?
- Existe um padrão para "repositório satélite read-only" documentar sua própria relação de dependência
  com o repositório principal (ex: um `UPSTREAM.md` ou seção equivalente)?
- Como equipes evitam que o repositório sem permissão de escrita fique com documentação desatualizada
  em relação ao que o repositório principal decidiu?

### 2. Templates prontos, não só descrição conceitual

A pesquisa anterior descreveu bem o que cada artefato deve conter, mas não entregou um esqueleto
pronto para copiar e adaptar. Precisamos agora de templates completos e prontos para uso, aplicados
à nossa stack (GCP, BigQuery, Cloud Run, Cloud Scheduler, Streamlit, sem dbt), para:
- `AGENTS.md` — esqueleto completo com as seções que a indústria considera padrão em 2025-2026,
  com exemplo de conteúdo (comandos de build/test, convenções de commit, zonas não-editáveis).
- `environments.md` (Matriz de Estado Ambiental) — estrutura de tabela e campos recomendados para
  documentar o que vigora em Staging vs. Produção, no cenário específico de **dois projetos GCP
  separados** (`adframework` = produção, `douglas-bq-staging` = staging), incluindo: como nomear e
  versionar o que está em cada projeto, como registrar diferenças de IAM/credenciais entre os dois,
  e como o documento deve ser atualizado quando algo é promovido de staging para produção (quem
  edita, em qual momento do fluxo de PR/deploy).
- Runbook de Promoção de Ambiente (Staging → Produção) — estrutura de seções e nível de detalhe
  esperado, com exemplo de "plano de rollback explícito". Como o rollback funciona quando os dois
  ambientes são **projetos GCP diferentes** (não um simples `git revert` — pode envolver reverter
  uma DDL já aplicada em produção, ou um deploy de Cloud Run que já rodou contra o projeto errado)?
- Runbook operacional de incidente (ex: falha de um conector de API) — estrutura mínima esperada
  pela indústria (matriz de alertas, passos de mitigação, critério de "resolvido").

### 3. Aprofundamento no caminho GCP-nativo de catálogo de dados (sem dbt)

A pesquisa anterior mencionou `persist_docs` (dbt) e Dataplex/Data Catalog (GCP nativo) como as duas
opções, mas dedicou uma frase a cada. Como **não usamos dbt**, precisamos de profundidade real só no
caminho GCP nativo:
- Passo a passo prático de como usar o Dataplex (ou BigQuery `SET OPTIONS (description=...)` nativo)
  para documentar descrições de tabela e coluna diretamente no schema do BigQuery.
- Isso pode ser versionado como código (aplicado via script/CI a partir de um arquivo YAML/JSON no
  repositório), similar ao que o `persist_docs` do dbt faz? Qual é o padrão de mercado para isso sem
  dbt?
- Existe integração nativa entre Dataplex e ferramentas de linhagem de dados sem precisar adotar uma
  ferramenta de orquestração completa (Dagster, Airflow)? Nosso pipeline hoje é orquestrado por scripts
  Python simples, não por um orquestrador dedicado.

### 4. Recalibração de prioridade para equipe de 2 pessoas

A pesquisa anterior refletiu práticas de mercado pensadas para equipes de engenharia maiores. Nossa
realidade operacional é uma equipe de 2 pessoas (eu, dono do pipeline principal, e uma segunda pessoa
com acesso de leitura a um repositório satélite). Pergunta:
- Dos artefatos recomendados (diagrama C4, DFD Medallion, ADRs, runbooks, `AGENTS.md`,
  `environments.md`, changelog), quais têm relação custo/benefício favorável para uma equipe deste
  tamanho, e quais são tipicamente overkill até que a equipe cresça?
- Existe uma ordem de implementação recomendada pela indústria quando os recursos de tempo são
  escassos — ou seja, qual artefato tende a prevenir mais incidentes/retrabalho por unidade de esforço
  investido nesse estágio de maturidade?

### 5. Método de enxugamento — o que cortar/fundir, não só o que adicionar

Isso é o ponto mais importante deste follow-up e o motivo real de reabrir a pesquisa. A
primeira rodada só respondeu "o que falta" (diagnóstico da seção 9: diagramas, `AGENTS.md`,
catálogo semântico, handover/onboarding — todos ausentes) e nós aplicamos só esse lado,
criando documentos novos. Isso fez nosso número de "docs mestres" (documentos vivos, cada
um com dono e critério de atualização próprio) saltar de um punhado pra quase 20 — para uma
operação real de 1 pessoa (eu) com colaboração pontual de uma segunda pessoa num repositório
satélite separado. Isso parece desproporcional, mas eu não tenho um método confiável pra
decidir o que é excesso real vs. o que é estrutura genuinamente necessária.

**Já rodei uma auditoria interna própria antes deste follow-up — resultado real, não
hipótese:** dos ~19-20 documentos "mestres" (vivos, com dono e critério de atualização),
só achei **1 fusão real** (duas referências da mesma API de terceiro, uma completa e uma
"resumo" redundante). Ou seja, a contagem de documentos mestres em si não era o problema.
O inchaço real estava em outro lugar: um `CHANGELOG.md` de quase 4.000 linhas com entradas
de 4-6 parágrafos quando o formato definido era 1-3 linhas (narrativa de investigação
vazando pro lugar errado), ~15 arquivos órfãos que nunca passaram por um processo de
expurgo formal, e 2 seções narrativas dentro de um doc de domínio de negócio que deveriam
ter ido para a ferramenta de "segundo cérebro" (Notion) em vez do repositório técnico.

Pergunta: isso é um padrão conhecido — a "sensação de excesso" numa auditoria de
documentação pequena vir mais de **crescimento descontrolado de log/changelog e acúmulo de
órfãos sem expurgo** do que do número de documentos "mestres" em si? Qual é o
método/checklist que a indústria usa para **auditar um conjunto já existente de
documentação técnica e decidir o que consolidar, rebaixar ou eliminar**, especificamente
pensando em operações pequenas (1-3 pessoas)? Quero uma resposta prática o suficiente para
eu aplicar sozinho contra a nossa lista real de documentos, não só princípio abstrato.
Cubra pelo menos:
- Existe um número/faixa de referência de "quantos documentos vivos" uma equipe deste
  tamanho consegue manter atualizados na prática, antes que a documentação em si vire
  trabalho maior que o sistema que ela descreve?
- Critério prático para decidir "isso merece um arquivo próprio" vs. "isso deveria ser só
  uma seção dentro de outro documento já existente" — queremos um teste objetivo, não
  "depende do caso".
- Como identificar documentação duplicada de fato (dois arquivos cobrindo essencialmente o
  mesmo assunto com propósito ligeiramente diferente, ex: uma referência oficial completa de
  API de terceiro e um "resumo estruturado" da mesma API) vs. documentação legitimamente
  complementar que só parece redundante à primeira vista?
- Sinais de alerta ("code smells" de documentação) que indicam que um projeto pequeno
  copiou processo de equipe grande sem necessidade — o que checar primeiro numa varredura
  de redução?

---

**Nota:** ignorar qualquer citação de vaga de emprego ou fonte sem relação direta com engenharia de
dados/documentação técnica (problema identificado na rodada anterior, citação [8] de
`zippia.com`). Priorizar fontes de 2024-2026, com link direto sempre que possível — se citar exemplos
de repositórios open-source, incluir o link direto para a pasta/arquivo de documentação referenciado,
não apenas o nome do projeto.
