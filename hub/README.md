# AdFramework Data Hub

Painel pessoal do pipeline BQ (`projeto adframework`). Mostra freshness das tabelas,
status inferido dos jobs de ingestao diaria, um tracker manual dos Power BI em
desenvolvimento, um navegador de schema/preview, um query runner, a fila de aprovacao de
propostas de mudanca e a carga de overrides historicos da Cora. Nao depende de nenhum
codigo do repo do Shiro (`rshiro-newad/adframework`).

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

- **Overrides Historicos (Cora)** -- escreve em `core.historical_overrides_delivery`.
  `dataEditor` escopado **so ao dataset `core`**.
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

O fluxo de Overrides e fechado e pontual -- carrega a planilha legada da Cora para
Jan-Jun/2026 apenas. Decisao explicita: **nao vira pratica recorrente para outros
clientes/periodos**. A UI aplica guarda-corpo (`validate_override_scope`) que rejeita
qualquer linha fora dessa janela.

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

Rodar `./deploy.sh` de novo a qualquer momento aplica o codigo/config atual. Nao ha CI --
e deploy manual, sob seu controle.
