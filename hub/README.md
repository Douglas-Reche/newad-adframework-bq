# AdFramework Data Hub

> **Manutenção:** Tier 3 — revisão quando a estrutura do painel Streamlit mudar.

Painel pessoal do pipeline BQ (`projeto adframework`). Mostra freshness das tabelas,
status inferido dos jobs de ingestao diaria, um tracker manual dos Power BI em
desenvolvimento, um navegador de schema/preview, um query runner, a fila de aprovacao de
propostas de mudanca, a carga generica de overrides historicos por cliente (upload de
arquivo local ou link do Google Sheets), a configuracao de overrides por cliente
(status/toggle sobre `core.client_reporting_source_config`) e a gestao de regras de
negocio por cliente (`core.client_business_rules`, staging). Nao depende de nenhum codigo
do repo do Shiro (`rshiro-newad/adframework`).

Tema visual (2026-08-10): cores e tipografia do Manual de Marca da NewAd
(`hub/.streamlit/config.toml` -- fundo claro, azul-marinho `#0C2443` como texto, roxo
`#6742F4` como cor primaria, paleta de graficos roxo/ciano/marinho/rosa, Montserrat via
`[[theme.fontFaces]]` nativo do Streamlit, sem CSS injetado). Checklist completo de
recomendacoes de design por aba (Bento Grid, badges condicionais, etc.) ainda pendente --
ver task Notion "Auditoria de UX/UI e Design do Hub".

## Farol permanente

Visivel ao abrir o hub, antes de clicar em qualquer aba (3 colunas logo acima das abas,
`hub/app.py` ~linhas 537-566). Reusa as mesmas funcoes/queries das abas de detalhe, sem
duplicar logica:

- **Saude do pipeline** -- `worst_status()` sobre `load_table_metadata()`, o pior status
  de freshness entre todas as camadas (mesma logica da aba Visao Geral BQ).
- **Propostas de Mudanca pendentes** -- `count_pending_proposals()`, contagem de
  `core.change_proposals WHERE status='pending'`.
- **Custo do mes corrente** -- `load_cost_current_month()`, mesma query da aba Custos,
  so muda a janela de data para o mes atual.

Decisao explicita do Douglas: sem resumo de Notion no farol.

## Exceção ao invariante read-only

A maioria das abas e 100% leitura, usando a SA principal (`douglas-data-hub-sa`, so
`bigquery.dataViewer` + `bigquery.jobUser` + `bigquery.resourceViewer`). Duas abas escrevem,
sempre via uma SA separada (`douglas-data-hub-writer-sa`) acessada por impersonation (sem
chave JSON) -- nenhuma outra aba/funcao do app tem acesso a essa credencial:

- **Ajustes de Dados Historicos** (aba renomeada, fluxo generico -- o antigo upload
  hardcoded so-Cora, `CORA_CLIENT_ID` fixo + janela Jan-Jun/2026, foi **removido** em
  2026-08-10, ver `docs/known_issues.md` S3 resolvido) -- escreve em
  `core.historical_overrides_delivery`/`stg.historical_overrides_delivery`. `dataEditor`
  escopado **so ao dataset `core`**. Fluxo: 1) upload -- arquivo local (`.xlsx`/`.csv`) ou
  link/ID de uma planilha Google Sheets (via `gspread`, credencial ADC, lista as abas pra
  escolher, sempre le valor calculado nunca formula) -- pousa como RAW literal em
  `raw.historical_uploads`; 2) comparacao "Planilha vs. Dado Real" contra
  `gold.fact_pacing` (corrigido de `fact_delivery` para `fact_pacing` em 2026-08-10 --
  quem de fato consome o override -- e ampliado para trazer todas as colunas relevantes:
  `planned_impressions_daily`, `planned_clicks_daily`, `planned_spend_daily`,
  `unit_price`, `investimento_realizado`, alem de impressions/clicks/conversions); 3)
  **Configuracao de Overrides por Cliente**: por `client_id`, mostra quantas linhas
  existem em `core.historical_overrides_delivery`, o range real (`MIN(day)`/`MAX(day)`,
  calculado ao vivo) e o status de `override_active`, com toggle liga/desliga que escreve
  em `core.client_reporting_source_config` (sempre versionado SCD2, fecha a linha anterior
  com `effective_to`, insere linha nova, nunca `UPDATE` do valor). Usa a mesma writer SA
  da aba (escopo `core`, sem binding de IAM novo). `core.client_reporting_source_config`
  segue existindo **só em `douglas-bq-staging`** — nunca promovida pra produção (ver
  `docs/core_layer_design.md`, seção `client_reporting_source_config`).
- **Propostas de Mudanca** -- fila generica sobre `core.change_proposals` (populada hoje
  pela reconciliacao incremental da Siprocal, `source='siprocal_diff'`). Aprovar sempre gera
  um **INSERT** (nunca UPDATE/DELETE) na tabela alvo indicada pela proposta (hoje sempre
  `raw.sp_delivery`) -- por isso a writer SA tambem tem `dataEditor` escopado **ao dataset
  `raw`**, alem de `core` (onde a propria fila de propostas e atualizada com o resultado da
  decisao). Chaves ambiguas (mais de uma linha batendo na mesma chave) nao podem ser
  aprovadas direto pela UI -- so rejeitar; correcao exige revisao manual fora do fluxo.

O padrao em ambas as abas: preview antes de qualquer coisa, checkbox de confirmacao
explicita antes de habilitar o botao que escreve de verdade. Nenhuma escrita acontece sem
essa confirmacao na UI.

- **Regras de Negocio** -- sobre `douglas-bq-staging.core.client_business_rules` (staging,
  nao producao -- promocao pra producao **bloqueada ate autorizacao explicita do
  Douglas**, guarda-corpo registrado na MAE da task no Notion). Listagem (cards por
  `rule_type`/escopo com a versao vigente + expander de historico substituida/pausada) via
  SA principal, com botoes **Editar datas** (ajusta `effective_from`/`effective_to` direto
  via UPDATE, sem passar pelo fluxo de pausa) e **Deletar** (DELETE definitivo, sem rastro
  de historico) por card e por linha do historico. Formulario de criacao de regra nova +
  fluxo de pausa (com motivo) via writer SA, mesmo padrao de preview+checkbox das outras
  abas de escrita. Construtor de regra por campo -- selecao explicita de 2 campos reais de
  `gold.fact_pacing` (campo a limitar + campo de referencia), no lugar do "Teto de
  Impressao (%)" abstrato inicial. **Simulador de Impacto** -- le dado real de
  `gold.fact_pacing` e calcula em memoria o efeito de uma regra antes de commitar (nao
  persiste nada); tem modo demonstracao (dado fabricado, seed fixa) como rede de seguranca
  de apresentacao. Testado via UI (validacoes, guard contra regra duplicada, fluxo de
  pausa) -- **a escrita real (INSERT/UPDATE) em BigQuery ainda nao foi confirmada
  ponta-a-ponta**, precisa de validacao rodando local com sessao autenticada propria.

## Rodar local

```bash
cd hub
pip install -r requirements.txt
gcloud auth application-default login   # se ainda nao tiver ADC configurado
streamlit run app.py
```

Abre em `http://localhost:8501`. Sem `HUB_PASSWORD` setada, roda sem pedir senha (so voce
tem acesso a maquina de qualquer forma).

## Deploy (Cloud Run proprio, acessivel de qualquer lugar/celular)

Servico separado dos 4 do Shiro -- `douglas-data-hub`, com service account propria e
permissao **somente leitura** de BigQuery (`roles/bigquery.dataViewer` + `roles/bigquery.jobUser`,
sem escrita em nada).

```bash
HUB_PASSWORD="escolha-uma-senha-forte" ./deploy.sh
```

Isso cria a service account (na primeira vez) e faz o build+deploy. No final imprime a URL
publica -- protegida por senha simples dentro do app (nao e IAM, e uma tela de login do
proprio Streamlit). Guarde a senha; ela nao fica no git.

### Trade-off de visibilidade

O servico Cloud Run fica dentro do projeto GCP `adframework` -- o mesmo projeto onde
rodam os servicos do Shiro. Isso significa: o **codigo** deste hub nunca sai do seu repo
privado (`newad-adframework-bq`), mas o **nome do servico** `douglas-data-hub` aparece
pra quem tiver acesso ao console GCP desse projeto (o Shiro tem). Se algum dia precisar de
isolamento total (nem o nome do servico visivel), a alternativa e um projeto GCP separado
com IAM cross-project pro BigQuery -- mais setup, avisar se quiser migrar pra isso.

## Atualizar dados manuais

- `jobs_config.yaml` -- mapa dos 11 jobs de ingestao. Atualizar quando o pipeline mudar
  (mesma fonte que a memoria `project_etl_daily_jobs`).
- `powerbi_status.yaml` -- status dos dashboards Power BI em construcao. Editar direto
  quando o status mudar.

## Redeploy

Deploy automatico via `.github/workflows/hub_deploy.yml`: qualquer push em `hub/**` para o
branch `master` dispara build+deploy no GitHub Actions (corrigido em 2026-08-10 -- o
workflow so escutava `main`, nunca disparou de verdade antes disso; todo deploy ate entao
foi manual). Requer os secrets `HUB_DEPLOY_SA_KEY`/`HUB_PASSWORD` configurados no GitHub
(Settings > Secrets > Actions) -- nao confirmado se ja estao la.

Deploy manual continua disponivel a qualquer momento (`./deploy.sh`), inclusive como
fallback de emergencia se o automatico falhar ou os secrets nao estiverem configurados.
