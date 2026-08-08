# Pesquisa: Arquitetura de Documentação para Engenharia de Dados (2024-2026)

> Pesquisa feita via Gemini Deep Research em 2026-08-08, a partir do prompt em
> `docs/prompt_pesquisa_documentacao.md` (mesmo texto enviado ao usuário como
> artifact durante a sessão de staging/histórico). Resultado colado aqui como
> insumo pra uma sessão dedicada de aplicação — ainda não avaliado/aplicado.
>
> **Achado de qualidade a considerar antes de confiar cegamente:** a citação
> [8] (zippia.com/data-analyst-internship-lexington-ky-jobs) é uma página de
> vaga de emprego, sem relação com o tema — parece citação espúria da
> ferramenta. Ignorar essa referência específica. Também: pedimos exemplos
> reais **com link direto** (item 5 do prompt) e a pesquisa só deu nomes de
> projetos (Dagster, Meltano, Airbyte, dbt-core), sem link pra pasta de docs
> de cada um —完成 parcial desse item, pode valer pedir complemento.

---

## Arquitetura de Documentação para Engenharia de Dados: Padrões e Práticas (2024-2026)

A engenharia de dados contemporânea transitou de uma disciplina focada na mera escrita de scripts de extração para uma prática rigorosa de desenvolvimento de software, governada por princípios de DataOps, integração contínua e arquiteturas em camadas estruturadas. À medida que as condutas evoluíram, a documentação deixou de ser um artefato estático, gerado post-mortem, para se transformar numa entidade viva, orgânica e tratada inequivocamente como código. O paradigma "Docs-as-Code" pressupõe que a documentação técnica reside junto ao código-fonte, acompanha os ciclos de revisão por pares e serve a uma audiência dupla: engenheiros humanos e, crescentemente, agentes de inteligência artificial.

A complexidade de orquestrar dados através de arquiteturas como o modelo Medallion (RAW → STG → CORE → GOLD) no Google Cloud Platform, integrando variadas fontes externas e expondo resultados em aplicações interativas, impõe uma carga cognitiva substancial sobre as equipas técnicas. Quando equipas pequenas gerem infraestruturas em expansão para múltiplos clientes, a ausência de uma arquitetura documental rígida resulta em dependência crítica de indivíduos, degradação do conhecimento e incapacidade de escalar operações ou recuperar sistemas em caso de falhas. Este relatório disseca os padrões de mercado vigentes entre 2024 e 2026, oferecendo uma resposta estruturada e profunda sobre a organização de repositórios, a separação de domínios de negócio e tecnologia, e a otimização de interfaces para assistentes de programação sintéticos.

### 1. Tipos de Diagrama Padrão em Projetos de Engenharia de Dados

A compreensão sistémica de um pipeline de dados multifacetado exige representações visuais com diferentes níveis de abstração. O padrão da indústria dita que nenhum diagrama único é capaz de capturar simultaneamente a topologia da infraestrutura, o fluxo lógico da informação e os relacionamentos de entidades, forçando as equipas a adotarem uma taxonomia visual específica e compartimentada.

O Diagrama de Arquitetura (Architecture Diagram) estabelece a fundação da compreensão da infraestrutura física ou em nuvem. O seu propósito primário é mapear os serviços envolvidos, as fronteiras de rede, as políticas de identidade (IAM) e o isolamento de recursos. Num contexto que envolve projetos separados para ambientes de Staging e Produção no Google Cloud Platform, este diagrama deve demarcar claramente o isolamento perimetral entre os dois ambientes, detalhando como ferramentas externas, como o GitHub Actions ou aplicações Streamlit, transgridem ou respeitam essas fronteiras. A sua utilidade máxima ocorre durante auditorias de segurança, otimização de custos e resolução de problemas de latência de rede.

Em contraste com a visão infraestrutural, o Diagrama de Fluxo de Dados (Data Flow Diagram, ou DFD) ignora intencionalmente o hardware e os serviços de alojamento para se concentrar estritamente na movimentação, transformação e saída da informação do sistema. O DFD é o veículo ideal para explicar a mecânica da arquitetura Medallion. Ele ilustra a ingestão da camada RAW a partir de fontes como conectores MediaSmart ou planilhas Siprocal, demonstrando as transições de tipagem na camada STG, as modelagens lógicas na camada CORE e as agregações finais na camada GOLD. Adicionalmente, modelos especializados de DFD são frequentemente empregues na análise de governação e na modelagem de ameaças de segurança, como o modelo STRIDE, identificando classificações de dados (públicos, confidenciais) em cada etapa de transformação.

Para estabelecer uma ponte comunicacional entre engenheiros de dados e engenheiros de software, o Modelo C4 (C4 Model - Context, Containers, Components, Code) consolidou-se como a linguagem visual de eleição. Inspirado na cartografia, o modelo C4 funciona através de aproximações sucessivas. O nível de Contexto descreve o ecossistema externo; o nível de Contentores mapeia as aplicações independentes, contrapondo o frontend Streamlit ("Hub") ao Data Warehouse BigQuery; e o nível de Componentes detalha os módulos operacionais internos, como o orquestrador de execução ou os scripts lógicos de extração. Esta abordagem top-down previne a sobrecarga visual comum em diagramas que tentam demonstrar todas as engrenagens em simultâneo.

No nível estrutural dos dados estáticos, o Diagrama Entidade-Relacionamento (Entity-Relationship Diagram, ou ERD) preserva o seu valor histórico. O ERD detalha o esquema exato do banco de dados, incluindo tabelas, colunas, chaves primárias, restrições e cardinalidade. Numa arquitetura Medallion, a comunidade de engenharia convenciona que a criação de ERDs para a camada RAW é um antipadrão, dado que o esquema é inerentemente volátil e dependente de fornecedores externos. O ERD demonstra o seu verdadeiro valor nas camadas CORE e GOLD, onde os dados foram sanitizados e conformados a modelagens dimensionais (como esquemas em estrela) ou Data Vaults, exigindo rigor semântico.

Por último, o Diagrama de Linhagem de Dados (Data Lineage Graph) foca-se na rastreabilidade cronológica e dependencial ao nível granular de tabelas ou colunas. Este diagrama responde diretamente a incidentes de qualidade, permitindo que um analista rastreie uma anomalia numérica num dashboard final até à sua raiz exata num ficheiro carregado manualmente ou numa chamada de API truncada. Na prática da engenharia moderna, as representações de linhagem não são desenhadas manualmente; elas são computadas algoritmicamente a partir das dependências do código, constituindo o coração das operações de depuração (troubleshooting).

| Tipo de Diagrama | Foco Principal | Aplicabilidade no Contexto Medallion e GCP | Natureza da Manutenção |
|---|---|---|---|
| Diagrama de Arquitetura | Topologia de Nuvem e Serviços. | Mapear isolamento entre projetos de Staging e Produção e permissões de acesso ao BigQuery. | Manual / Gerado via Código de Infraestrutura (IaC). |
| Diagrama de Fluxo de Dados (DFD) | Trânsito e Transformação Lógica. | Representar a transição RAW → STG → CORE → GOLD e a tipologia de ingestão. | Manual / Atualizado em decisões de pipeline. |
| Modelo C4 | Relações Sistémicas e Hierarquia. | Explicar a interação entre o frontend interno em Streamlit e o backend de processamento. | Manual, focado na perspetiva de arquitetura de software. |
| Diagrama Entidade-Relacionamento | Esquemas Físicos e Cardinalidade. | Restrito às camadas CORE e GOLD para ilustrar modelagem dimensional (fatos e dimensões). | Gerado dinamicamente via inspeção de metadados do banco. |
| Diagrama de Linhagem | Rastreabilidade Causal e Impacto. | Debug diário e análise de impacto antes da alteração de colunas. | Puramente automatizado via ferramentas de orquestração. |

### 2. Ferramentas Contemporâneas para Criação e Manutenção Visual no Git

A manutenção de diagramas sempre representou uma fricção operacional substancial nas equipas de desenvolvimento. A prática legada de incluir imagens em formato binário (PNG, JPEG) ou arquivos proprietários no sistema de controlo de versão provou-se ineficaz. Um ficheiro binário impede a revisão assíncrona num Pull Request, uma vez que as plataformas Git não conseguem apresentar as diferenças ("diffs") lógicas de uma imagem, resultando invariavelmente na desatualização severa do diagrama em relação ao código efetivo. O mercado mitigou este problema através da adoção universal do paradigma de Diagramas como Código (Diagrams-as-Code).

O Mermaid.js estabeleceu-se como a ferramenta hegemónica para diagramas estruturais e de fluxo no interior de repositórios Git, impulsionado pelo suporte de renderização nativa em plataformas como GitHub e GitLab. A formulação de diagramas baseia-se numa sintaxe inspirada no formato Markdown, permitindo que os engenheiros construam fluxogramas complexos, diagramas de sequência, gráficos de Gantt e ERDs utilizando pura representação textual. Num processo de revisão de código, a adição de um novo conector de dados reflete-se na alteração de uma única linha de texto dentro do bloco Mermaid. A aplicação do Mermaid é, portanto, o padrão recomendado para a criação do Diagrama de Fluxo de Dados da arquitetura Medallion e para as representações C4 de alto nível, eliminando a necessidade de ferramentas externas de modelagem visual.

Para diagramação estritamente focada em infraestrutura de nuvem, a biblioteca Python "Diagrams" representa uma alternativa viável para desenhar a arquitetura GCP. Ao instanciar objetos no código Python, como instâncias do BigQuery ou baldes do Cloud Storage, a biblioteca compila uma representação visual. Embora traga as vantagens do versionamento de código, a biblioteca exige a compilação local da imagem resultante, inserindo uma pequena etapa adicional no ciclo de integração contínua (CI), o que a torna ligeiramente menos fluida que o Mermaid para visualizações puramente embutidas.

Quando a análise recai sobre a linhagem de dados, a renderização estática demonstra-se completamente inadequada. O padrão de mercado delega a geração do diagrama de linhagem a ferramentas nativas e dinâmicas que interpretam o próprio código de execução. Ferramentas de modelagem analítica deduzem o Grafo Acíclico Dirigido (DAG) inspecionando as referências embutidas nas declarações SQL ou scripts de transformação, criando interfaces visuais interativas sem qualquer esforço de desenho por parte do engenheiro. Esta funcionalidade automática garante que o gráfico documentado corresponda invariavelmente à realidade da execução, resolvendo em definitivo o problema da obsolescência documental.

### 3. Estrutura de Documentação Técnica: O Padrão-Ouro da Indústria

A arquitetura de repositórios adotada por equipas de alta performance subordina-se a uma hierarquia de intenção estrita. O código em si responde à pergunta "como a máquina executa a instrução", enquanto a documentação adjacente clarifica "o que o sistema representa", "por que as decisões foram tomadas" e "como mitigar crises operacionais". Projetos open-source servem como as principais bússolas para este padrão organizacional.

O documento README atua como a interface primária entre o repositório e o engenheiro humano, frequentemente comparado a uma "página de marketing" técnica. A estrutura de um README exemplar obedece ao princípio da pirâmide: o que o projeto faz, como configurá-lo, e como contribuir. Um erro persistente e amplamente documentado pela indústria é a tentativa de transformar o README num manual exaustivo. O seu escopo deve limitar-se à apresentação da proposta de valor, listagem sucinta das dependências ambientais, comandos vitais de inicialização e hiperligações para as profundezas da documentação. O indicador chave de desempenho de um bom README é o seu contributo para reduzir o tempo decorrido desde a clonagem do repositório até à execução do primeiro teste local com sucesso.

A rastreabilidade histórica do raciocínio arquitetural reside nos Registros de Decisão de Arquitetura (Architecture Decision Records, ou ADRs). Introduzidos metodologicamente por Michael Nygard em 2011, os ADRs resolvem a entropia informacional prevenindo que o conhecimento sobre compromissos tecnológicos evapore. As decisões de hoje parecerão artefactos misteriosos no futuro, exigindo que não apenas o veredito final, mas todo o contexto e as opções rejeitadas sejam formalizados. A indústria converge em torno do modelo Nygard e do formato derivado MADR (Markdown Any Decision Records), sendo este último preferido pela sua ênfase nas implicações estruturais.

A estrutura invariável de um ADR Nygard inclui cinco secções taxativas. O Título descreve a decisão num formato curto e nominal. O Status reflete o ciclo de vida do documento (Proposto, Aceito, Descontinuado, Substituído). O Contexto narra as restrições tecnológicas, organizacionais e temporais que motivaram a discussão, assegurando uma leitura neutra e desapaixonada. A Decisão enuncia a escolha concreta. Fundamentalmente, a secção de Consequências expõe os "trade-offs" inerentes à adoção tecnológica, listando o que se tornará mais fácil ou mais difícil no futuro. A disciplina dos ADRs dita que um registro "Aceito" é estritamente imutável; se uma nova tecnologia substituir a anterior, um novo ADR deve ser criado, promovendo a descontinuação explícita do registro obsoleto. A localização padrão no repositório é o diretório `/docs/adr/` ou `/docs/decisions/`.

Além dos ADRs, a arquitetura documental inclui guiões orientados à contingência, conhecidos como Runbooks operacionais. Estes documentos, geralmente encontrados em diretórios como `/docs/ops/`, são puramente utilitários. Concebidos para serem consultados em momentos de elevado stress técnico, os Runbooks catalogam matrizes de alertas comuns, estratégias de mitigação e passos literais para reinicialização segura de componentes paralisados (como falhas no conector MGID ou dessincronizações da tabela STG).

| Componente Documental | Audiência Primária | Objetivo Estruturante | Exemplo de Implementação e Localização |
|---|---|---|---|
| README.md | Engenheiros (Novatos). | Apresentação, instalação e navegação rápida (Princípio da Pirâmide). | Raiz do repositório. Ex: README.md. |
| ADRs | Equipa de Engenharia e Arquitetos. | Memória institucional de decisões, opções rejeitadas e consequências lógicas. | docs/adr/001-uso-de-bigquery.md. |
| Runbooks | Operadores e Equipa de Suporte. | Resolução de incidentes, mitigação sob pressão e procedimentos de reprocessamento manual. | docs/ops/media-smart-outage-runbook.md. |
| Dicionário de Dados | Analistas de Dados e Negócio. | Entendimento semântico e técnico dos atributos armazenados, linhagem de negócio. | Integrado diretamente ao catálogo de banco de dados. |

### 4. Integração Sistémica entre Ambientes de Wiki (Notion) e Controlo de Versão (Git)

A duplicação de conhecimento e a divergência inevitável entre repositórios de código e plataformas colaborativas como o Notion ou Confluence representam uma fricção clássica em equipas em expansão. O padrão da indústria para resolver esta fragmentação fundamenta-se num axioma organizacional conhecido como a Regra de Proximidade do Ciclo de Vida. Este princípio postula que a documentação deve residir o mais perto possível da entidade que governa o seu ritmo de mutação.

O repositório Git retém soberania absoluta sobre a realidade técnica do sistema. Todo o material explicativo que acompanha as alterações de infraestrutura, algoritmos de extração e a topologia Medallion é versionado com o código. Diagramas Mermaid, Registros de Decisões Arquiteturais, Guias de Operação e Runbooks dependem de revisões estruturadas por "Pull Requests", garantindo que um retrocesso (rollback) no código resulte também num retrocesso sincrônico na sua documentação técnica.

Inversamente, ferramentas de base de conhecimento como o Notion são reservadas, em exclusividade, para a cristalização das narrativas de negócio, domínios conceptuais e planeamento estratégico. Documentos como objetivos trimestrais, mapeamento do comportamento e necessidades de negócio dos clientes (Siprocal, MediaSmart), roteiros de produto (roadmaps) e atas de definição de regras operacionais habitam o Notion, pois o seu ciclo de alteração dita-se por fluxos executivos e comerciais, não por commits de código.

A sincronização harmónica entre estes dois universos é assegurada através de um padrão de "Hiperligação Direcional" (Directional Hyperlinking). O Notion desiste de tentar descrever esquemas técnicos de tabelas ou lógicas computacionais puras; em vez disso, integra links imutáveis apontando diretamente para os ficheiros Markdown ou manifestos no Git. De forma análoga, os comentários e descrições no repositório de código omitem longas explicações sobre dinâmicas de mercado, inserindo referências aos registos relacionais do Notion para quem deseje obter profundidade corporativa. Esta demarcação cria uma fronteira nítida que impede a deterioração da verdade documental.

### 5. Arquiteturas Documentais de Referência no Ecossistema Open-Source

A observação empírica de repositórios mantidos por líderes da indústria de engenharia de dados fornece gabaritos validados para a estruturação de diretórios e políticas documentais.

O orquestrador de ativos de dados Dagster (`dagster-io/dagster`) revela uma maturidade arquitetural centrada no ciclo de desenvolvimento, produção e observação. O repositório emprega uma arquitetura que não sobrecarrega o `README.md` com tutoriais operacionais complexos. A inteligência documental é delegada para um extenso ecossistema de documentação segmentado, abordando de maneira declarativa a construção de ativos de dados através de funções em Python, e mantendo fóruns estruturados para a progressão de especificações complexas.

No domínio da integração, o Meltano (`meltano/meltano`) demonstra como um motor puramente declarativo e focado no modelo "code-first" se documenta a si próprio. Com uma clara rejeição à necessidade de criar e manter pesadas lógicas operacionais separadas do código, a plataforma governa o ciclo de vida dos dados desde a ingestão à transformação, fazendo amplo uso de ficheiros de configuração `meltano.yml` que auto-documentam as dependências de orquestração.

Simultaneamente, a plataforma Airbyte (`airbytehq/airbyte`) exemplifica como gerir centenas de conectores independentes sem incorrer em caos documental. A sua abordagem estabelece templates automáticos, onde o desenvolvimento de qualquer novo conector inclui nativamente guiões unitários e um README padronizado isolado, reduzindo a complexidade necessária para validar e incorporar contribuições.

A excelência em documentação de transformações SQL está consubstanciada no `dbt-core`. O projeto solidificou a prática de integrar metadados técnicos nas camadas de definição do código fonte e propagar essas descrições até aos mecanismos finais de exibição.

**Nota do Claude:** pedimos links diretos pra cada exemplo (item 5 do prompt original) — a pesquisa só deu nomes de repositório, sem link. Vale pedir complemento numa sessão futura se for usar esses exemplos de perto.

### 6. Procedimentos Estruturados para Transferência de Conhecimento e Integração (Onboarding)

O desafio de incorporar rapidamente novos elementos numa equipa de dados – ou de transferir a manutenção de um pipeline – exige mais do que um repositório repleto de ADRs e esquemas técnicos. O mercado mitiga a sobrecarga cognitiva do recém-chegado através do conceito do "Guia do Dia 1" (Day 1 Guide ou Developer Journey), um documento que condensa os processos cronológicos essenciais.

Este guião é frequentemente posicionado de forma isolada, como `onboarding.md` ou `setup.md`, para não poluir o README principal. O protocolo dita uma divisão progressiva do foco operacional. No Dia 1, o enfoque restringe-se puramente aos bloqueios de acesso e preparação do ambiente de desenvolvimento. O documento detalha a obtenção das credenciais de nuvem, as políticas de identidade locais, a diferenciação taxativa entre os acessos de leitura necessários e os acessos de gravação estritos nos ambientes de Staging.

Uma prática altamente recomendada na engenharia de software contemporânea é a substituição de longas listas manuais de instalação de pacotes e ferramentas por automação. A presença de um script de arranque (geralmente um `Makefile` acompanhado pelo comando `make setup` ou um ficheiro `bootstrap.sh`) consolida a instalação das dependências da infraestrutura local. A métrica última de eficiência do processo de integração é medida no chamado "Tempo até o primeiro Pull Request" (Time-to-first-PR).

### 7. Formatos e Normas Ideais Aplicadas à Stack Tecnológica Específica

**GitHub/Markdown:** a incorporação de diagramas via código Mermaid no seio dos ficheiros `.md` apresenta o mais elevado retorno operacional — renderiza nativamente no GitHub, sem imagem externa.

**Notion:** a deterioração de uma plataforma de conhecimento como o Notion advém, tipicamente, da adoção irrestrita da criação encadeada de páginas simples. O modelo estrutural preferencial baseia-se na implementação intensiva das Bases de Dados Relacionais (Notion Databases) — épicos/features numa base, atas noutra, idiossincrasias de fontes externas (MediaSmart, Siprocal) noutra, com propriedades relacionais interligando tudo.

**Streamlit:** README exclusivo no subdiretório do painel, Type Hints (PEP 484) + Docstrings (PEP 257) nas rotinas centrais, segmentação em módulos (`ui_utils.py` vs `data_utils.py`) quando a lógica cresce.

**BigQuery:** a prática de dicionários remotos foi substituída por injeção direta de metadados na própria camada de dados. Se usar dbt, a diretiva `persist_docs` exporta descrições do `schema.yml` pra dentro do BigQuery. No GCP nativo, o Dataplex (Data Catalog) assume esse papel (scan automatizado, Entry Groups, Tags).

**IA (VS Code/Claude Code):** um agente de IA "não transporta sentido intuitivo sobre convenções ocultas". Padrão emergente de 2 camadas:
- `AGENTS.md` (padrão estabelecido em agosto de 2025, adoção ampla) — comandos universais/mecânicos, válidos pra qualquer assistente de IA (Copilot, Cursor, etc.).
- `CLAUDE.md` — específico do ecossistema Claude, roteamento de subagentes, skills, comportamento — já usamos isso, mas sem o `AGENTS.md` complementar.

Recomendação: ficheiros nucleares de instrução de IA devem ficar enxutos (a pesquisa cita uma faixa de 60-500 linhas como referência) — inchá-los com contexto de negócio dilui a diretiva tática.

| Ficheiro | Consumidor Prioritário | Conteúdo Padrão | Princípio Diretor |
|---|---|---|---|
| README.md | Engenheiro Humano | Justificação, proposta de valor, instalação limpa. | "Pirâmide de Informação": O quê → Como → Onde participar. |
| AGENTS.md | Múltiplas IAs Sintéticas | Comandos executáveis literais, zonas não-editáveis. | "Detetive Amnésico": operacionalizar sem preâmbulo. |
| CLAUDE.md | Ecossistema Claude | Delegação de subagentes, roteamento, restrições do modelo. | "Código Vivo": limpeza frequente, concisão. |

### 8. Governação de Promoção e Gestão do Ciclo de Vida: Staging vs. Produção

A transição de alterações validadas em staging pra produção exige rituais de governação documentada — o histórico cronológico de commits sozinho não é padrão adequado.

- **"Matriz de Estado Ambiental"** (`environments.md`) — o que vigora em cada ambiente, em que versão, quais conectores usam chave de teste vs. real.
- **"Documento do Processo de Lançamento"** (Release Process Doc / Environment Promotion Runbook) — roteiro mecânico: branch → teste local → PR → validação → promoção pro ambiente real. Elemento vital: plano de rollback explícito.
- **"Keep a Changelog"** — convenção global pra `CHANGELOG.md`, com SemVer/CalVer, auditando exatamente o que foi promovido, quando, sob qual decisão.

### 9. Sumário Diagnóstico — comparação contra o nosso cenário atual

| Componente | Nosso Cenário Hoje | Padrão de Mercado | Diagnóstico |
|---|---|---|---|
| Diagramas Arquiteturais e Fluxos | Intuição de incompletude, nada formal. | Mermaid embutido, DFD Medallion, C4. | **Lacuna crítica** — gerar diagramas de Staging vs. Prod + DFD Medallion + C4 nos docs de camada. |
| Registos de Decisão (ADR) | `docs/adr/` + Notion. | Regra de Proximidade + 5 seções Nygard. | **Alinhado** — só reforçar que Notion nunca vira registro técnico. |
| Catálogos/Semântica | `OWNERSHIP.yaml` (rastreabilidade superficial). | `persist_docs` (dbt) ou Dataplex. | **Lacuna moderada** — descrições nativas no BigQuery, `OWNERSHIP.yaml` só pra RBAC/controle de acesso. |
| IA (CLAUDE.md) | Só `CLAUDE.md`. | `AGENTS.md` (universal) + `CLAUDE.md` (Claude-específico). | **Desvio a corrigir** — separar comandos universais do comportamental Claude-específico. |
| Handover/Onboarding | Disperso, sem doc formal. | Guia do Dia 1, Matriz de Ambientes, Runbook de Promoção. | **Lacuna severa** — nenhum desses 3 existe formalmente ainda. |

---

**Fontes citadas pela pesquisa** (revisar antes de usar como referência formal — pelo menos uma citação, [8], parece espúria):
1. redreamality.com/blog/claude-md-agents-md-deep-dive
2. learn.microsoft.com/azure/well-architected/architect-role/design-diagrams
3-4, 6-7. Vários sobre ADR templates (github.com/architecture-decision-record, stackademic.com, arxiv.org/2604.27333)
8. ⚠️ zippia.com (site de vagas — parece citação errada, ignorar)
9. code.claude.com/docs/best-practices
