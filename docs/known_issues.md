# Problemas Conhecidos — AdFramework BigQuery

> **Manutenção:** Tier 2 — toda issue aberta ou fechada gera entrada aqui.

---
> **📋 REESTRUTURAÇÃO EM ANDAMENTO — 2026-06-16**
> Os issues listados abaixo referem-se à pipeline **anterior ao reset de 2026-06-16**.
> Issues G1/G2 são sobre tabelas que foram reconstruídas do zero — considere-os encerrados no contexto do rebuild.
> **Correção 2026-08-08: G3 NÃO está encerrado pelo rebuild** — é um gap de mapeamento de
> dado (`core.campaign_format_map` sem 4 strategy IDs do TecPar), não uma tabela que o
> rebuild reconstrói; a formulação anterior deste banner o incluía incorretamente no mesmo
> grupo de G1/G2. Ver entrada G3 na seção "⚠️ Aberto — Gold layer" abaixo — segue aberto
> (grep no repo pelos 4 strategy IDs não encontrou nenhum INSERT/seed que os tenha
> adicionado a `core.campaign_format_map`; reconfirmação ao vivo via BigQuery bloqueada
> nesta sessão — ver nota no rodapé do arquivo).
> Novos issues do rebuild serão documentados aqui conforme surgirem. Plano: [bq_restructuring_plan.md](bq_restructuring_plan.md)
---

> Última atualização: 2026-06-16 — Gold layer completa: G1 e G2 resolvidos durante execução; G3 aberto (TecPar MS strategies sem mapeamento de category). 5 tabelas gold deployadas.
> Autor: Douglas Reche

---

> ## ⚠️ SUPERADO — decisão de arquitetura `douglas-bq-staging` (2026-08-06, ~08h45)
> Todas as entradas abaixo que descrevem `raw`/`stg` como **"leitura cross-project"** de
> produção (R3, a seção "Paridade Staging x Produção validada", S1-S4) refletem o desenho
> da madrugada de 2026-08-05→06, **superado**. Decisão final fechada com o Douglas: o
> `douglas-bq-staging` é standalone de verdade — `raw` é **snapshot físico** das 18
> tabelas de `adframework.raw.*` via `bq cp` (único ponto de contato com produção),
> **atualizado por Cloud Scheduler diário** (mesmo padrão do `adframework-etl-daily` já
> existente, rodando logo depois que a ingestão de produção termina) — nunca por leitura
> ao vivo. Backend está fazendo o snapshot inicial manual agora; o agendamento automático
> em si é o próximo passo, mas a decisão já é "agendado desde já", não manual/opcional.
> `stg`,
> `core` e `gold` são **100% físicos e locais** em staging, aplicados a partir do mesmo
> `.sql` versionado no repo, lendo exclusivamente do `raw` local — **zero leitura
> cross-project** depois do snapshot. Motivo: não dava pra testar/auditar mudança nenhuma
> em `raw`/`stg` com segurança sob o desenho antigo (`apply_ddl.py --project` só
> redirecionava `core`/`gold`). Execução (fix do `apply_ddl.py`, `bq cp` das 18 tabelas,
> reaplicação completa de stg/core/gold) em andamento na manhã de 2026-08-06. Detalhe
> completo: `CHANGELOG.md`, entrada "2026-08-06 — Arquitetura standalone…" (topo do
> arquivo). Não editar as entradas históricas abaixo — ficam como registro do que foi
> tentado e por que mudou.

---

## ✅ Resolvidos em 2026-08-04

| # | Problema | Resolução |
|---|---|---|
| V1 | **`core/ddl/dict_format.sql` — drift de schema (shadow columns)** — colunas `notes`, `confirmed_by`, `created_at` já existiam ao vivo em `core.dict_format` no BigQuery mas não estavam no DDL commitado no git. Mesmo padrão de "objeto shadow" já documentado para `core.campaign_format_map` em `docs/audit_pipeline_consistency_2026-07-29.md` §8.4. Descoberto como achado paralelo durante o versionamento SCD2 das tabelas de regra de negócio (ver `CHANGELOG.md` 2026-08-04). | `core/ddl/dict_format.sql` sincronizado com o schema real (`INFORMATION_SCHEMA.COLUMNS`) — colunas `notes`/`confirmed_by`/`created_at` adicionadas ao DDL, junto com `effective_from`/`effective_to` (versionamento SCD2, passos 1-2 de 5 de "Analisar resiliência e rastreabilidade da camada Gold"). |

---

## ✅ Resolvidos em 2026-08-06

| # | Problema | Resolução |
|---|---|---|
| R1 | **Achado crítico #1 do teste ponta-a-ponta em `douglas-bq-staging`: `core.resolve_reporting_source` quebrava com "Correlated subqueries that reference other tables are not supported unless they can be de-correlated" no uso real (correlacionado por linha, dentro do `WHERE`, com `client_id`/`date` vindo de uma tabela externa — exatamente como `gold/ddl/fact_delivery.sql` chama a função). Funcionava isolada (client_id constante), mas não no caso de uso real. Causa raiz confirmada: a função tinha 2 CTEs (`vigente`, `range_real`, cada uma lendo uma tabela diferente) referenciadas por 3 subqueries escalares separadas no `SELECT` final — correlação de 2 níveis que o BigQuery não decorrelaciona automaticamente, diferente de `core.resolve_dict_format`/`core.resolve_platform_rule` (1 único `SELECT` flat, 1 nível). | Função reescrita em `core/ddl/resolve_reporting_source.sql` como um único `SELECT` flat, com as duas tabelas combinadas via `LEFT JOIN` no mesmo `FROM` e a decisão calculada via agregação (`LOGICAL_OR`/`MIN`/`MAX`) — mesmo padrão estrutural de `resolve_dict_format`, generalizado para 2 tabelas. Reproduzido o erro original em `douglas-bq-staging` (query correlacionada real contra `core.historical_overrides_delivery` como tabela externa), aplicada a correção via `apply_ddl.py --env=test --project=douglas-bq-staging`, e reconfirmado sem erro com 3 casos (cliente dentro do range de override, cliente fora do range, cliente sem nenhuma linha de override — todos resolvendo corretamente e nunca retornando `NULL`). Teste adicional simulando o UNION ALL completo de `fact_delivery.sql` (dado "de plataforma" fake vs. override real) confirmou substituição correta no range, sem duplicar nem perder linha. Ver `CHANGELOG.md` 2026-08-06 para as queries e resultados completos. |
| R2 | **Achado crítico #2 do teste ponta-a-ponta em `douglas-bq-staging`: dado normalizado de entrega (`historical_overrides_delivery`) estava em `core`, violando a convenção do resto do pipeline (dado normalizado vive em `stg` — `stg.ms_delivery`/`stg.mg_delivery`/`stg.sp_delivery` — `core` é só para tabela de regra/config pequena e mantida manualmente).** | Tabela movida para `stg.historical_overrides_delivery` (schema idêntico, incluindo `conversions`). `core/ddl/historical_overrides_delivery.sql` mantido como stub apontando para o novo local (não apagado sem rastro). Todas as referências atualizadas: `core/ddl/resolve_reporting_source.sql`, `gold/ddl/fact_delivery.sql` (4ª fonte do `UNION ALL`), `scripts/deploy/load_historical_override.py` (`TABLE_ID`), `hub/app.py` (`OVERRIDE_TABLE`). `core.client_reporting_source_config` **não mudou de lugar** — continua em `core` (é a tabela de regra/toggle, não dado de entrega). Migração testada ponta-a-ponta em `douglas-bq-staging`: tabela `stg.historical_overrides_delivery` criada, as 3 linhas de teste migradas de `core`, função `resolve_reporting_source` redeployada apontando para `stg`, e o fluxo completo (override substituindo dado real no range certo) reconfirmado funcionando após a migração. |
| R3 | ⚠️ **SUPERADO 2026-08-06 manhã — ver banner no topo do arquivo.** O fix descrito abaixo (raw/stg nunca trocam de projeto, sempre cross-project) foi o desenho da madrugada; a decisão final da manhã trocou `raw` para snapshot físico e `stg` para físico local — `swap_project()`/`PHYSICAL_DATASETS` está sendo revisado de novo pelo backend agora. ~~✅ RESOLVIDO 2026-08-06~~ — Achado #3 do mesmo relatório: bug real em `swap_project()` (`scripts/deploy/apply_ddl.py`), confirmado (não só suspeitado).** Trocava TODAS as ocorrências literais de `adframework.` pelo projeto alvo, inclusive referências a `stg.*`/`raw.*` que devem permanecer cross-project apontando pra produção mesmo quando o DDL é aplicado em `douglas-bq-staging` (evita duplicar ingestão). Reproduzido: aplicar `gold/ddl/fact_delivery.sql` com `--project douglas-bq-staging` gerava `` `douglas-bq-staging.stg.ms_delivery` `` (tabela inexistente) em vez de `` `adframework.stg.ms_delivery` ``. | Constante `PHYSICAL_DATASETS = {"core", "gold"}` adicionada no topo de `apply_ddl.py`; `swap_project()` reescrita para só trocar o project id em referências a esses 2 datasets — `raw`/`stg` nunca trocam de projeto, sempre leitura cross-project de `adframework`. Confirmado com `--dry-run` contra `gold/ddl/fact_delivery.sql` e `gold/ddl/fact_delivery_by_device.sql`: `stg.*` permanece `adframework.stg.*`, `core.*`/`gold.*` trocam corretamente para `douglas-bq-staging`. |
| R4 | ✅ **RESOLVIDO 2026-08-06 — Drift confirmado em `gold/ddl/dim_campaign.sql`: faltava `CAST(start_date/end_date AS DATE)` nos ramos MediaSmart/MGID do `UNION ALL`.** Descoberto ao tentar espelhar o gold em `douglas-bq-staging` (task "Ambientes Staging x Produção") — o arquivo commitado falhava com `Column 8 in UNION ALL has incompatible types: STRING, STRING, DATE` (`stg.ms_campaigns.start_date`/`end_date` são `STRING`; `stg.mg_campaigns` já é `DATE`). Comparado com `INFORMATION_SCHEMA.VIEWS.view_definition` da view AO VIVO em produção: o `CAST` já existia lá — mesmo padrão de "shadow object"/drift já documentado para `dict_format` (ver V1 acima), só que aqui é o inverso (prod está certo, o repo estava desatualizado). | `CAST(start_date AS DATE)`/`CAST(end_date AS DATE)` adicionados nos 2 primeiros ramos de `gold/ddl/dim_campaign.sql`, sincronizando com o texto real de produção. Aplicado e confirmado funcionando em `douglas-bq-staging`. |
| R5 | ✅ **RESOLVIDO 2026-08-06 (dado alinhado manualmente, achado sinalizado) — cópia de tabelas de regra (`core.dim_client`, `core.dict_format`) de produção para staging via `INSERT ... SELECT *` corrompeu dado por ordem de coluna divergente.** `core.dim_client` em produção tem uma coluna extra (`newad_account_id`, ordinal 12) não presente no `core/ddl/dim_client.sql` commitado (mesma classe de drift de V1/R4 — schema real diverge do arquivo). `core.dict_format` tem `formato`/`platform` em ordem trocada entre produção (`formato` primeiro) e o DDL commitado (`platform` primeiro) — como ambas colunas são `STRING`, o `SELECT *` posicional não deu erro de tipo, só **trocou os valores silenciosamente** (`platform='Display'` virou `formato='Display'` e vice-versa). Descoberto por conferência manual linha a linha antes de seguir para os testes de paridade — não teria sido pego só por contagem de linhas. | `core/ddl/dim_client.sql` do staging alterado (`ALTER TABLE ADD COLUMN newad_account_id`) e recarregado com `INSERT` por lista explícita de colunas (nunca `SELECT *` posicional entre projetos/schemas potencialmente divergentes). `core.dict_format` truncado e recarregado do mesmo jeito. Conferido linha a linha depois — dado agora idêntico a produção. **Ação recomendada, fora do escopo desta correção pontual**: sincronizar `core/ddl/dim_client.sql` commitado com o schema real (adicionar `newad_account_id`), mesmo tratamento já dado a `dict_format` em V1. |

**Pendente, fora de escopo desta correção**: falta de grão `platform` em `core.client_reporting_source_config` (achado #4 do mesmo relatório de teste, aguardando priorização do Douglas).

---

## ✅ Paridade Staging x Produção validada (2026-08-06, pré-reunião)

Objetivo: `douglas-bq-staging` mostrar exatamente os mesmos números que `adframework`
(produção) antes de qualquer teste de dado histórico. Resultado: **paridade 100%
confirmada** para os 2 objetos mais prováveis de irem pro Power BI hoje.

- **`gold.fact_delivery`** (agregado por `client_id, platform, formato` — SUM
  impressions/clicks/conversions): `EXCEPT DISTINCT` nos dois sentidos (prod↔staging)
  retornou **0 linhas divergentes**. Match exato, sem arredondamento.
- **`gold.fact_pacing`** (agregado por `client_id, platform, formato` — SUM
  realized_impressions/clicks/conversions/planned_spend_daily/investimento_realizado):
  `EXCEPT DISTINCT` bruto retornou 16 linhas "divergentes", mas inspeção linha a linha
  confirmou que é 100% ruído de ponto flutuante na soma de `investimento_realizado`
  (`FLOAT64`, não-associativo — ex: `107578.14744000002` vs `107578.14744`, diferença
  na 11ª casa decimal). Com `ROUND(..., 2)` (precisão de exibição do Power BI) em todas
  as colunas numéricas, o mesmo `EXCEPT DISTINCT` retornou **0 linhas** — paridade
  confirmada.
- Todas as 8 tabelas oficiais (`dim_advertiser`, `dim_campaign`, `fact_delivery`,
  `fact_delivery_by_device`, `fact_delivery_by_size`, `fact_delivery_creative`,
  `fact_io_plan`, `fact_pacing`) foram aplicadas em `douglas-bq-staging` via
  `apply_ddl.py --env=test --project=douglas-bq-staging`, texto idêntico ao repo
  (exceto R4, corrigido antes). Dependências `core` aplicadas junto: `dim_client`,
  `dict_format`, `advertiser_platform_rules`, `resolve_dict_format`,
  `resolve_dict_format_fallback`, `resolve_platform_rule`, `resolve_reporting_source`,
  `client_reporting_source_config` (já existia do teste anterior). Override de teste
  (`banco_cora_fe13d78a`) desligado via SCD2 (`override_active = FALSE`, linha antiga
  fechada com `effective_to`, nunca `UPDATE` in-place) antes da validação — dado
  sintético (`impressions` 999001+) permanece na tabela mas nunca é lido, confirmado
  pela paridade acima.
- **Exceção arquitetural aceita, não resolvida**: `gold/ddl/fact_delivery.sql` e
  `core/ddl/resolve_reporting_source.sql` referenciam `` `adframework.stg.historical_overrides_delivery` ``
  hardcoded (não segue o padrão `{project}.stg.*` de swap). Essa tabela **não existe em
  produção ainda** (produção roda a versão antiga de `fact_delivery.sql`, só 3 fontes,
  sem essa 4ª fonte — confirmado via `INFORMATION_SCHEMA.VIEWS.view_definition` ao vivo).
  Como `stg` nunca é fisicamente espelhado por projeto (ver R3), e não é permitido
  escrever em produção, os 2 arquivos foram aplicados em staging com uma cópia
  pontual (`scripts/deploy/` não alterado) apontando essa única referência para
  `douglas-bq-staging.stg.historical_overrides_delivery` (que já existe fisicamente
  ali, criado no teste anterior). Isso é seguro para a validação de hoje porque o
  `override_active = FALSE` faz a função sempre retornar `'platform'`, então a 4ª
  fonte contribui 0 linhas independente de qual tabela ela lê — mas é uma bandeira
  amarela: quando essa migração for promovida pra produção de verdade, `apply_ddl.py`
  vai precisar de um mecanismo explícito (ex: diretiva por tabela, não só por dataset)
  para lidar com tabelas `stg` mantidas manualmente (não-ETL) que ainda não existem
  em produção. Não implementado agora — fora do escopo desta validação pontual.
  **⚠️ SUPERADO 2026-08-06 manhã** (ver banner no topo do arquivo) — com `stg` físico
  local em staging, essa "bandeira amarela" deixa de existir por desenho: não há mais
  referência cross-project nenhuma a resolver.

---

## ⚠️ Aberto — Staging x Produção (2026-08-06)

| # | Problema | Impacto | Ação |
|---|---|---|---|
| S1 | **Branch protection não habilitada — `CODEOWNERS` (`newad-adframework-bq/CODEOWNERS` e `rshiro-newad/adframework`, só `connectors/siprocal.py`) sozinho não bloqueia merge.** Confirmado 2026-08-06: os arquivos existem e listam `@Douglas-Reche` como owner de `/raw/ /stg/ /core/ /gold/ /marts/ /share/ /scripts/deploy/ /hub/`, mas "Require a pull request before merging" + "Require review from Code Owners" não foram ligados no GitHub (Settings > Branches) em nenhum dos dois repos. | Qualquer commit direto na branch principal continua passando sem revisão — a proteção Tier B do desenho de staging existe só no papel até isso ser ligado. | Habilitar branch protection nos dois repos quando o Douglas confirmar que quer o fluxo de PR obrigatório em produção. |
| S2 | ✅ **RESOLVIDO 2026-08-06** — Teste ponta-a-ponta do staging (`douglas-bq-staging`) com caso real (histórico Cora) rodou e encontrou 2 achados críticos bloqueantes (bug de correlated subquery em `resolve_reporting_source` + tabela de dado em `core` em vez de `stg`) — ambos corrigidos, ver R1/R2 acima. Fluxo completo (override substituindo dado real no range certo via `fact_delivery.sql`) reconfirmado funcionando em staging depois das correções. Guardrails de custo (cota 10GB/dia, orçamento CAD$10/mês) e `apply_ddl.py --project`/`--rollback` seguem confirmados ao vivo. | — | 2 achados menores do mesmo teste seguem pendentes, fora de escopo desta correção (ver nota abaixo de R1/R2) — priorização do Douglas. |
| S3 | **Fluxo antigo de upload específico da Cora (`CORA_CLIENT_ID` fixo, janela Jan-Jun/2026, aba "Overrides Históricos" do hub) não foi generalizado junto com o redesenho de `client_reporting_source_config`.** O toggle novo (por cliente, SCD2) coexiste no hub com o upload hardcoded antigo, sem decisão de unificar. | Dois caminhos paralelos para o mesmo tipo de dado (histórico override) — risco de divergência se um cliente precisar do fluxo genérico mas alguém usar o antigo por hábito. | Decisão pendente do Douglas: migrar o upload da Cora para o fluxo genérico, ou manter os dois propositalmente (ex: upload = carga de dado, toggle = liga/desliga). |
| S4 | ✅ **RESOLVIDO 2026-08-06** — as 3 peças que faltavam (landing RAW no Hub, upload, normalização versionada por cliente) agora estão todas construídas. Peça de normalização fechou o ciclo: `scripts/deploy/normalize_historical_upload.py` (orquestrador) + `scripts/deploy/historical_mappings/<client_id>.py` (um arquivo Python por cliente, contrato `normalize(raw_rows) -> list[dict]`, ver `historical_mappings/__init__.py`) — busca de `raw.historical_uploads`/`historical_uploads_meta` em `douglas-bq-staging`, aplica o mapeamento do cliente (falha alto se não existir), valida contra `REQUIRED_COLUMNS` de `load_historical_override.py` (fonte única, não duplicada), gera CSV pro `load_historical_override.py` carregar. No caminho, corrigido bug real em `load_historical_override.py::build_rows()` (não específico de teste — bloquearia qualquer cliente real): coluna nullable vazia (`platform`/`goal_type`/`impressions`/`conversions`) chegava como `float('nan')` do pandas, que não é JSON válido pra API do BigQuery (`400 Bad Request`) — corrigido `NaN` → `None` antes do insert. **Teste ponta a ponta confirmado ao vivo** (upload_id `39a0d9be-1ca8-4d41-b774-cc30489d2286`, `client_id=teste_agente_backend_xyz`, query direta em `douglas-bq-staging.stg.historical_overrides_delivery`, 3 linhas): `"01/07/2026"` → `2026-07-01`, `"1.234,56"` → `1234.56`, `"Video Instream"` → `video_instream`, colunas ausentes na planilha origem → `NULL` (não inventa valor). | ~~Sem a peça (a), não existia RAW literal pra auditar/reprocessar, nem normalização versionada.~~ Ciclo completo raw → normalize → load funcionando e testado em staging. | Fechado. Próximo passo é operacional, não de ferramenta: aplicar o fluxo a um cliente real (Cora/TecPar) escrevendo o mapeamento `historical_mappings/<client_id>.py` correspondente. |

---

## ⚠️ Aberto — Gold layer

| # | Problema | Impacto | Ação |
|---|---|---|---|
| V2 | **`stg.ms_campaigns`, `stg.mg_campaigns`, `stg.sp_campaigns` — `goal_type` resolvido via `core.dict_format` sem coluna de data utilizável para o versionamento SCD2.** As 3 views resolvem `goal_type` em grain de campanha (1 linha por `campaign_id`), mas `sp_campaigns` não tem nenhuma coluna de data, e `ms`/`mg_campaigns` só têm `start_date` de campanha (não a data do dado reportado) — `MIN(start_date)` real (2024-02-16/2024-07-02) é anterior ao piso de backfill do pipeline (2025-01-01), então usar essa coluna como `as_of_date` quebraria campanhas antigas. Achado durante o passo 3/5 do versionamento SCD2 das tabelas de regra (`core.dict_format`, `core.campaign_format_map`, `core.advertiser_platform_rules` — ver `docs/adr/0001-versionamento-scd2-regras-negocio-via-funcoes-resolve.md` e `CHANGELOG.md` 2026-08-04). | `goal_type` nessas 3 views continua lido pelo estado atual da regra, não pela regra vigente na época do dado — mesma exposição que motivou o versionamento SCD2 (mudar uma regra reinterpreta retroativamente o goal_type histórico dessas campanhas). | Mover/duplicar o JOIN para dentro de `ms_delivery.sql`/`mg_delivery.sql`/`sp_delivery.sql` (que têm `date` real por linha), usando `core.resolve_dict_format(platform, formato, as_of_date)` — já pronta e em produção via `gold.fact_io_plan`. |
| G4 | ✅ **RESOLVIDO 2026-07-29** — **TecPar/Amigo — Display/Retargeting (MediaSmart) e Native/Push (MGID) com ZERO entrega apesar de R$284k planejado.** Causa confirmada: `client_id` do TecPar estava de fato separado do Amigo no raw; remap `tecpar_edfcc744 → amigo_db1c2f0c` aplicado em `stg/ddl/io_plan.sql` (commit `edb6bcf`, 2026-07-09) e `scripts/io_plan/sync_drive.py` `CLIENT_MAP` (commit `abbc3a6`). Verificado ao vivo em 2026-07-29 (auditoria de consistência): `gold.fact_delivery` para `amigo_db1c2f0c` agora mostra Display (23,7M impr), Retargeting (17,7M impr), Native (8,1M impr) e Push MGID (609K impr) — entrega que antes aparecia como zero. TecPar como `client_id` separado não existe mais nos dados. | ~~R$284k de budget planejado sem nenhuma entrega visível~~ — entrega agora visível e atribuída | Fechado. Nenhuma ação adicional. |
| G5 | ⚠️ **AINDA ABERTO (client_id atualizado 2026-07-29)** — **Amigo (ex-TecPar) — Push/unknown vs siprocal: mesmo padrão da Cora.** Verificado ao vivo: `gold.fact_io_plan` para `client_id='amigo_db1c2f0c'` ainda tem **R$135.000 planejados em `platform='unknown'`/Push** não vinculados à entrega real (Siprocal Push existe: 2,07M impressões, 303 linhas — mas o plano de R$16.800 siprocal/Push é separado do bloco unknown/Push de R$135k). O remap de client_id (G4) não resolveu isto — é uma correção diferente: falta regra em `core.advertiser_platform_rules` remapeando `platform='unknown'` → `siprocal` para Amigo, igual à regra já existente para Cora (`banco_cora_fe13d78a`, commit `c1c3935`, 2026-07-08). | R$135k de Push planejado sem correspondência com entrega Siprocal existente — pacing de Push subestimado para Amigo | Confirmar que o Push do Amigo roda na Siprocal (alta probabilidade, mesmo padrão da Cora). Se confirmado, adicionar linha em `core/ddl/advertiser_platform_rules.sql`: `('amigo_db1c2f0c', 'unknown', 'PUSH', 'siprocal', ...)`. |
| G6 | **Amigo — 138 linhas com formato NULL (MediaSmart jul→nov/2025)** — Campanhas MediaSmart do Amigo que entregaram nesse período não existem em `raw.ms_campaigns` (histórico deletado antes do ETL ser configurado para o cliente). `fact_delivery` resolve client_id mas não consegue mapear formato. | 12,6M impressões sem formato nem goal_type — invisíveis para análise por formato | Identificar os campaign_ids dessas 138 linhas no raw MS e inserir manualmente em `core.campaign_format_map` com o formato correto (Display/Retargeting). Ou aceitar como gap histórico irrecuperável. |
| G7 | **Amigo — sem IO Plan (100% sem budget)** — Amigo nunca teve budget cadastrado no pipeline. Todas as 1.059 linhas em `fact_pacing` têm `planned_spend=NULL`, `unit_price=NULL`, `investimento_realizado=NULL`. Amigo funciona apenas como monitoring (entrega existe, budget não). | Impossível calcular pacing, eficiência ou investimento realizado para Amigo | Cadastrar IO Plan de Amigo via `sync_drive.py` quando disponível. |
| G8 | **MS NULL formato residual (12.5%)** — Campanhas sem keyword de formato no nome: `LUCKBET_RETENCAO_` (84M imp), `7K`/`Cassino` (11M imp), `MRV_ONTARGET` (1.3M imp), `TECPAR_AMIGO_HBO/700` (2.9M imp), `PARDINI_POSCAST` (316k imp). Nomes genuinamente sem indicador de formato — parse de nome não resolve. | ~106M impressões sem formato nem goal_type; `investimento_realizado` NULL para essas linhas | Mapeamento manual por `campaign_id` em tabela auxiliar `core.campaign_format_map` (a criar), ou aceitar como gap. Confirmar com Shiro qual formato são essas campanhas. |
| G3 | **TecPar + outros clientes MS sem mapeamento em `core.campaign_format_map`** — TecPar tem 4 MS strategy IDs (`ry1h8hhlhf0znig3hxzlqutd6b79r9jo`, `htoerticevccicdmokurvgiz63gaceq6`, `j7xxmkmf46ghxst10lgcnxkxta0gitrj`, `4epumrvsxkwnmod4txxfmlex6zh7mkda`) não presentes no mapa. Na `gold.fact_delivery`, essas strategies ficam com `category = 'OTHER'` e não joinam com `gold.fact_io_plan` via `fact_pacing` (TecPar DISPLAY/RETARGETING/NATIVE têm plan mas sem delivery na pacing). | Pacing por category inoperante para TecPar MS | Adicionar os 4 strategy IDs de TecPar em `core.campaign_format_map` com o formato correto (DISPLAY / VIDEO / RETARGETING). Douglas confirma qual ID é qual estratégia. |
| A2 | ✅ **RESOLVIDO 2026-08-05 (noite) — `io_binding_registry_v4`/`io_manager` reconfirmado sem risco para a gold oficial.** `gold/delivery/fct_luckbet_delivery_full.sql` (e `fct_cora_delivery_full.sql`, A1) fazem JOIN direto em `core.io_binding_registry_v4` (Admin UI do Shiro) — mas durante a investigação de ownership de código de 2026-08-05 (noite, sub-task Notion `3b39d0f6-219e-8170-8e5b-c9ec1d923a72`) confirmou-se, por leitura completa das 8 views oficiais em `newad-adframework-bq/gold/ddl/` (`fact_delivery`, `fact_pacing`, `fact_io_plan`, etc.), que **nenhuma delas referencia `io_manager`/`io_binding_registry_v4`/qualquer objeto do Admin UI do Shiro**. A dependência existe só nos 2 arquivos "workaround" fora de `gold/ddl/` (`fct_cora_delivery_full.sql`, `fct_luckbet_delivery_full.sql`), já classificados como legado/morto, não parte do caminho de produção da gold. | ~~Risco de exposição a mudança silenciosa do sistema do Shiro~~ — gold oficial confirmada limpa; os 2 arquivos workaround continuam existindo no repo mas fora do fluxo ativo. | Fechado. Nenhuma view oficial da gold depende do Admin UI — não reabrir como achado ambíguo em auditorias futuras. Se algum dia `fct_cora_delivery_full.sql`/`fct_luckbet_delivery_full.sql` forem reativados, reavaliar. |
| A4 | **`fct_newad_bet_daily.sql`, `fct_luckbet_delivery_daily.sql`, `fct_delivery_daily_mvp.sql` → `share.io_calc_daily_v4` (Shiro), fora do `OWNERSHIP.yaml`.** Achado em `docs/pipeline_audit_2026-08-05.md`. `fct_delivery_daily_mvp.sql` não tem filtro de `client_id` nenhum — lê a tabela inteira. `share.io_calc_daily_v4` não tem DDL neste repo (dataset `share` não existe como pasta) e não está coberto pelo `core/OWNERSHIP.yaml` (que só cobre o dataset `core`). | Mais sério que A1/A2: se essas 3 views ainda estão ativas em produção, qualquer consumidor (Power BI, hub) está 100% exposto a mudanças no sistema do Shiro sem aviso — sem filtro de cliente em `fct_delivery_daily_mvp.sql`, é exposição de toda a base, não workaround pontual. | Requer Fase B (BigQuery ao vivo) para confirmar se as views ainda existem/rodam e quem as consome hoje, e decisão do Douglas sobre expandir `OWNERSHIP.yaml` para cobrir `stg`/`share`. Item ABERTO — aguardando Douglas (ver `docs/pipeline_audit_2026-08-05.md` §Resumo itens 2 e 5). **Tentativa de reconfirmação 2026-08-08 bloqueada** (BigQuery inacessível nesta sessão — ver nota em C1 abaixo); permanece ABERTO. |
| A5 | **`gold.fct_creative_daily` — objeto fantasma, sem DDL em lugar nenhum.** Achado em `docs/pipeline_audit_2026-08-05.md`: `gold/creative/fct_luckbet_creative_daily.sql` lê de `adframework.gold.fct_creative_daily`, mas não há `CREATE ... fct_creative_daily`/`fact_creative_daily` em nenhum `.sql` do repo. Diferente de A3/A4, não há evidência de que seja do Shiro (não aparece em `OWNERSHIP.yaml` nem em `id_dependency_map.md`) — mesma categoria de risco dos "shadow objects" já resolvidos em 2026-08-04 para `dict_format`/`campaign_format_map`. | Objeto sem fonte de verdade versionada — impossível confirmar schema/comportamento sem BigQuery ao vivo. | Requer Fase B: `INFORMATION_SCHEMA.TABLES`/`VIEWS` ao vivo para classificar se é objeto do próprio pipeline nunca commitado, objeto do Shiro sem padrão `_v2`/`_v4`, ou morto/substituído. Item ABERTO — aguardando Douglas (ver `docs/pipeline_audit_2026-08-05.md` §Resumo item 4). **Tentativa de reconfirmação 2026-08-08 bloqueada** (mesmo motivo — ver nota em C1 abaixo); permanece ABERTO. |
| A6 | **`core/OWNERSHIP.yaml` se declara escopado só ao dataset `core` — por isso os achados A3/A4 (`stg.io_lines_v4`, `share.io_calc_daily_v4`, objetos do Shiro fora do `core`) nunca foram vistos por nenhuma auditoria.** Achado em `docs/pipeline_audit_2026-08-05.md` (§A6). **Decisão do Douglas 2026-08-05: expandir o escopo declarado do arquivo para cobrir o projeto BigQuery `adframework` inteiro, não só o dataset `core`.** Decisão de escopo já tomada — não depende de Fase B. | Sem essa cobertura, um objeto novo do Shiro em `stg`/`share` (ou qualquer dataset fora de `core`) pode voltar a vazar para o gold sem ninguém notar — foi exatamente assim que A3/A4 escaparam da auditoria atual. | **Decisão tomada, implementação PENDENTE** — reescrever `core/OWNERSHIP.yaml` (escopo + adicionar as entradas já encontradas `stg.io_lines_v4`/`share.io_calc_daily_v4`, avaliar mover/renomear o arquivo) é trabalho do agente `backend`, não do `docs`. Aguardando o orquestrador despachar essa implementação. |
| C1 | **`docs/_legacy/id_dependency_map.md` marcado como "dropado, não usar" — mas descreve exatamente as cadeias que 6 views gold ativas hoje ainda consomem.** Achado em `docs/pipeline_audit_2026-08-05.md`: o cabeçalho do doc diz que as tabelas foram dropadas e não existem mais no BigQuery, mas os nomes exatos (`io_binding_registry_v4`, `stg.io_lines_v4`, `share.io_calc_daily_v4`, `share.platform_daily_detail`, `share.newad_operational_daily`) são os mesmos que `fct_cora_delivery_full.sql`, `fct_luckbet_delivery_full.sql`, `fct_newad_fintech_daily.sql`, `fct_newad_bet_daily.sql`, `fct_luckbet_delivery_daily.sql` e `fct_delivery_daily_mvp.sql` (datados de 2026-05-12, sem indicação de substituição) ainda usam hoje. | **Verificação urgente pendente** — sem acesso ao BigQuery ao vivo não dá para saber se o aviso do doc está errado para essas tabelas específicas do Shiro, ou se essas 6 views gold estão quebradas em produção agora sem ninguém ter percebido. | Fase B (BigQuery ao vivo) assim que Douglas destravar o acesso — confirmar existência/atividade das 4 tabelas Shiro citadas. Item ABERTO, marcado como verificação urgente, não resolvido (ver `docs/pipeline_audit_2026-08-05.md` §Resumo item 3). **Tentativa de reconfirmação 2026-08-08: bloqueada** — `bq`/`gcloud auth`/client Python via ADC pediram reautenticação interativa nesta sessão, não concluída. C1/A4/A5 **permanecem ABERTOS** — não movidos para "Resolvidos" como cogitado, por falta de reconfirmação ao vivo das 5 tabelas + 6 views do universo Shiro. Próxima sessão com acesso ao BigQuery: reconfirmar e, se confirmado, mover para `✅ Resolvidos`. |

## ✅ Resolvidos em 2026-06-16

| # | Problema | Resolução |
|---|---|---|
| G1 | **`gold.fact_io_plan` — campo `unit_price` ausente** | `s.unit_price` adicionado ao SELECT em `gold/ddl/fact_io_plan.sql` + redeploy. Verificado: unit_price = 3.9 para Cora PUSH. |
| G2 | **`gold/ddl/dim_campaign.sql` quebrado** — referenciava `stg.mediasmart_delivery` (legado), usava `campaign_id` para Siprocal, sem campo `category` | Rebuild completo: fontes corrigidas (`stg.ms_delivery`, `stg.mgid_campaigns`, `stg.siprocal_delivery`); category via JOIN `core.campaign_format_map` para MS, constantes para MGID/Siprocal; GROUP BY garante PK única. |

---

## 🗑️ Limpeza pendente (executar após STG Siprocal estabilizar)

| # | Tabela | Motivo | Ação |
|---|---|---|---|
| C1 | `raw.siprocal_raw_sheet` | Pipeline antigo (`sync_sheet.py`) — descontinuado em 2026-06-14 quando `SiproCalConnector` entrou em produção. Tabela vazia ou com dados legados, não usada por nenhum job atual. | `DROP TABLE adframework.raw.siprocal_raw_sheet` |
| C2 | `raw.siprocal_sheet_ext` | External Table auxiliar linkada direto na Google Sheet — usada só para inspeção ad-hoc. Não faz parte do pipeline. Pode ser recriada a qualquer momento se precisar inspecionar a sheet. | `DROP EXTERNAL TABLE adframework.raw.siprocal_sheet_ext` |

> **Quando executar:** após `stg.siprocal_delivery` e `gold.fact_delivery` Siprocal validados em produção (ver próximos passos do pipeline Siprocal).

---

## ✅ Resolvidos em 2026-06-15

| # | Problema | Resolução |
|---|---|---|
| MS1 | **`raw.mediasmart_daily` — `eventid` NULL desde 2026-06-11 (e no backfill Mai 25-26)** — `stg.ms_delivery` mostrava `ms_client_id = NULL` para todas as datas a partir de Jun/11. Causa raiz: `normalize_data()` em `base.py` converte headers da API para snake_case (`event_id`, `campaign_id`, `strategy_id`), mas `raw.mediasmart_daily` tem schema BQ com nomes antigos (`eventid`, `controlid`, `strategyid`) herdados do sistema do Shiro (aat-console). `load_data()` em `bigquery.py` dropa colunas do DataFrame não presentes no schema existente, então `event_id` era descartado e `eventid` ficava NULL. O bug existia desde que o Python ETL assumiu o carregamento (Shiro parou em Jun/11); o backfill de Mai 25-26 (issue D2) também foi afetado pelo mesmo motivo. | Fix: adicionado rename explícito em `_run_mediasmart_daily()` (orchestrator.py) ANTES de `bq.load_data()`: `df.rename(columns={"event_id":"eventid","campaign_id":"controlid","strategy_id":"strategyid","strategy_name":"strategyname"})`. Commit `842ab47`. Deploy revision `adframework-etl-00249-c4j` via tagged image (workaround: `gcloud builds submit --tag ... --dockerfile adframework_python/Dockerfile` + `gcloud run deploy --image` — o flow `--source .` gera imagens sem tag que Cloud Run não importa). Backfill: DELETE nas rows NULL + `force_from_date` → 34 rows Jun 11-15 + 204 rows Mai 25-Jun 15. STG resultado: ms_delivery 642.180 rows, 0 NULL client_id, max Jun 15. |
| MS2 | **Deploy `gcloud run deploy --source .` gerando imagens sem tag não importáveis** — revisões 00244 a 00247 falharam com `ContainerImageImportFailed`. Imagem buildada com sucesso no Artifact Registry mas sem tag (`TAGS: []`), Cloud Run não conseguia importar. | Workaround: usar `gcloud builds submit --tag <image>:<tag> --project <proj>` no diretório com Dockerfile, depois `gcloud run deploy --image <image>:<tag>`. Imagem tagueada importa normalmente. Causa raiz exata do comportamento `--source .` não investigada — pode ser bug do gcloud SDK local ou política do projeto. |
| SIP1 | **`raw.siprocal_delivery` — dados truncados em Jun/09 (1.078 rows, max Jun/09)** — filtro básico ativo na coluna C da Google Sheet (`Campanha`) ocultava ~27 linhas de Jun/10-14 via API `values.get()`. Service account ETL tem acesso Viewer; `values.get()` respeita filtros básicos para Viewers. | Fix: `SheetsClient.read_values()` trocado de `values.get()` para `spreadsheets.get(includeGridData=True)` — lê GridData raw, imune a qualquer filtro independente do nível de acesso. Commit `ff1f6f5`. Deploy revision `adframework-etl-00243-hg5`. Resultado: 1.105 rows / 2025-08-22 → 2026-06-14. |

**Estado STG pós-correções (2026-06-15):**

| Tabela | Rows | NULL client_id | Min date | Max date |
|---|---|---|---|---|
| `stg.ms_delivery` | 642.180 | **0** | 2025-08-01 | 2026-06-15 |
| `stg.mgid_delivery` | 2.344 | **0** | 2025-10-01 | 2026-06-14 |
| `stg.siprocal_delivery` | 1.105 | **0** | 2025-08-22 | 2026-06-14 |

---

## ✅ Resolvidos em 2026-06-12

| # | Problema | Resolução |
|---|---|---|
| S1 | **4 raw tables Grupo A com duplicatas do backfill** — `by_device` (3.52×), `by_os` (3.76×), `by_hour` (2×), `by_publisher` (1.36×). Causa: múltiplos triggers de backfill com WRITE_APPEND sobrescreveram o mesmo período. `by_geo` e `creative_daily` não foram afetadas. | `CREATE OR REPLACE TABLE ... AS SELECT DISTINCT * FROM ...` executado em produção 2026-06-12. Row counts pós-dedup: by_device 58.610, by_os 72.741, by_hour 2.715, by_publisher 7.198.762. Sanity check confirmado: by_device = by_os = by_geo = creative_daily = 233.093.873 impressões; gap vs ms_delivery = 0.029% (esperado). |
| B1 | **Backfill Grupo A incompleto — 4 de 6 jobs com API timeout** — `delivery_by_hour` (dados com range errado Mai 28+), `delivery_by_geo` (sem tabela), `creative_daily` (parcial Jan 1-20), `delivery_by_publisher` (parcial Jan 1-6). | Causa raiz: `REQUEST_TIMEOUT_SECONDS = 10` muito baixo para drilldowns de alta cardinalidade (geo, publisher). Fix: timeout aumentado para 60s + deploy revision `adframework-etl-00238-n4h`. Backfill executado via múltiplos triggers sequenciais com `force_from_date` atualizado incrementalmente. `delivery_by_geo` deduplicada com `SELECT DISTINCT *` após duplicação acidental. `delivery_by_hour` confirmado que MediaSmart não tem dados hourly antes de 2026-05-28 para as contas monitoradas. Todos os 6 `force_from_date` removidos do Firestore. |
| T1 | **`REQUEST_TIMEOUT_SECONDS = 10` — timeout insuficiente para drilldowns de alta cardinalidade** — `delivery_by_geo` (country+area+city) e `delivery_by_publisher` (company+url+exchange) geram relatórios grandes que excedem 10s. Manifestou-se como `HTTPSConnectionPool Read timed out` em todos os requests desses jobs. | `adframework_python/src/connectors/mediasmart.py` linha 16: `REQUEST_TIMEOUT_SECONDS = 10` → `60`. Commit `7bee5f9`. Deploy Cloud Run revision `adframework-etl-00238-n4h`. Jobs que completavam ok antes (device, os, hour) não foram afetados (baixa cardinalidade = API responde rápido). |

---

## ✅ Resolvidos em 2026-06-11

| # | Problema | Resolução |
|---|---|---|
| 16 | **MediaSmart Grupo A (6 tabelas) — dimensões sem labels** — `operating_system`, `device_type`, `country`, `city`, `publisher_company`, etc. ausentes nas 6 tabelas recém-criadas, impossibilitando STG. | Causa: tabelas pré-criadas por processo do Shiro com schema antigo (`eventid`/`controlid`); `bigquery.py:load_data` dropou colunas não reconhecidas. Fix: DROP nas 6 tabelas + re-trigger via ETL HTTP API. Tabelas recriadas com schema nativo da API (`event_id`, `campaign_id`, `operating_system`, etc.). Ver CHANGELOG 2026-06-11 sessão 2. |
| 15 | **MediaSmart conector — sleep insuficiente, risco de rate limit** — `time.sleep(0.15)` = 400 req/min, 3× acima do limite de 128. | Commit `4d1662f`: `RATE_LIMIT_DELAY` 0.3 → 0.6, sleeps 0.15/0.3 → 0.6. Deploy Cloud Run revision `adframework-etl-00237-v88`. |
| D1 | **`raw.mediasmart_campaigns` com 39× duplicação** — WRITE_APPEND acumulou 5.451 linhas para 140 IDs únicos. | Firestore `write_mode: WRITE_TRUNCATE` + dedup BQ: `CREATE OR REPLACE TABLE ... WHERE rn = 1`. Resultado: 140 linhas. |
| D2 | **`raw.mediasmart_daily` — gap 25–26/mai/2026** — transição entre job antigo e novo deixou 2 dias sem dados. | `force_from_date` implementado em `_get_date_range` (orchestrator.py, commit `4d1662f`). Job temporário `mediasmart_backfill_may2526` carregou 26 linhas (13/dia). |
| 9 | **`raw.mediasmart_delivery` parado em 2026-05-24** — entendimento incorreto de que era timeout do Shiro. | Investigação confirmou: tabela ativa é `raw.mediasmart_daily` (usa campo `table_name`, não `bq_destiny`). Sem ação necessária. |
| 7.2 | **Colunas extras ausentes em `raw.mediasmart_delivery`** — baseado em tabela legada (24 cols). | `raw.mediasmart_daily` (ativa) já tem 31 cols incluindo `creative_type`, `id_type`, `client_currency`, etc. |

## ✅ Resolvidos em 2026-06-08

| # | Problema | Resolução |
|---|---|---|
| R1 | **Amigo (`amigo_db1c2f0c`) com 39 links `pending_confirmation`** — 1 eventid MediaSmart + 38 campaignids MGID criados em 2026-05-26 nunca foram ativados, zerando a entrega de Amigo na gold. | `core/migration/05_activate_amigo_links.sql` rodado em prod — 39 linhas promovidas para `active`. Verificado: 40 links ativos totais (1 MS + 38 MGID + 1 Siprocal pré-existente). |
| R2 | **`gold.fact_delivery` com dados de MediaSmart parados em 2026-05-24** — ETL do orchestrator com timeout, 12 dias de gap. | `stg.mediasmart_delivery` atualizado para incluir `raw.mediasmart_daily` (tabela staging do orchestrator) como fonte complementar. `gold.fact_delivery` reconstruída em 2026-06-08 com dados até 2026-06-07. Root cause (timeout no orchestrator) ainda pendente — ver issue #8. |

---

---

## 0. Separação de responsabilidades no dataset `core`

**Contexto:** O dataset `core` no BigQuery contém tabelas de dois sistemas diferentes que coexistem durante a transição.

**Tabelas do NOSSO pipeline** (usar livremente):
- `core.dim_client` — cadastro de clientes
- `core.platform_client_links` — atribuição plataforma → cliente (usado em `gold.fact_delivery`)
- `core.campaign_format_map` — mapeamento formato de campanha (Display, Native, Push, Retargeting, Video)

**Tabelas do Admin UI do Shiro** (NÃO referenciar no pipeline gold):
- `core.io_manager_v2` — escrito pelo Admin UI via `adops/io_bq_sync.py`
- `core.io_line_bindings_v2` — escrito pelo Admin UI
- `core.proposals` / `core.proposal_lines` — módulo de planning do Admin UI
- `core.io_manager_enriched_v2`, `core.io_registry_v4`, `core.io_binding_registry_v4`, `core.io_line_bindings_enriched_v2` — views do sistema do Shiro

**Por que não conectar:** O `io_manager_v2.newad_client_id` usa formato `nwd_banco-cora_acfae3ab` (prefixo `nwd_` + hifens) enquanto o `dim_client.client_id` usa `banco_cora_fe13d78a` (sem prefixo, underscores). JOINs entre os dois sistemas nunca funcionam.

---

## 1. Duplicação de clientes Luckbet no sistema

**Impacto:** Qualquer soma de entrega na gold layer aparece duplicada para Luckbet.

**Causa raiz:**  
Existem dois `newad_client_id` para o mesmo cliente real (Luckbet):
- `nwd_luckbet_a485d6bc` — conta **canônica** (advertiser_id: `adv_b559ffdcbd`)
- `nwd_luckbet_69e72f18` — conta **legacy** (advertiser_id: `luckbet`)

Os mesmos campaign IDs físicos no MediaSmart estão vinculados a IOs de **ambos** os client IDs simultaneamente. Resultado: 23 dos 25 campaigns MediaSmart da Luckbet aparecem contados duas vezes.

**Solução necessária (Admin UI):**  
Desativar todos os IOs e bindings do `nwd_luckbet_69e72f18`. Manter apenas o `nwd_luckbet_a485d6bc` como conta ativa.

---

## 2. nwd_internal_newad aponta para conta MediaSmart da Luckbet

**Impacto:** Entrega da Luckbet aparece triplicada — sob `_69e72f18`, `_a485d6bc` e `nwd_internal_newad`.

**Causa raiz:**  
Em `platform_client_links`, o cliente `nwd_internal_newad` tem `link_value = newad_brazil-dzynxhmnrdg2ec0czgdiabqmwvy0qhgj` — que é **a mesma conta MediaSmart** da Luckbet canônica. Nenhuma campanha real pertence ao "NewAD Interno" — todas são Luckbet.

**Solução necessária (Admin UI / Firebase):**  
Corrigir o `link_value` do `nwd_internal_newad` para a conta MediaSmart correta da agência, ou desativar o link (`status = inactive`).

---

## 3. Dois campaign IDs MediaSmart sem IO (órfãos)

**Impacto:** Entrega real nunca aparece na gold layer.

| campaign_id | Impressões | Período |
|---|---|---|
| `35ey8fny8gizx3vfxwac4ft1xjitbfbe` | 5,47M | abr/26 |
| `toarsf57a3lky0xmw7w16m4e68iqt5xy` | 479k | set/25 |

**Causa raiz:**  
Campanhas ativas no MediaSmart que nunca foram vinculadas a nenhum IO no Admin UI.

**Solução necessária:** Criar ou retroativamente vincular a um IO no Admin UI.

---

## 4. Cora: histórico MediaSmart (ago/25–fev/26) fora da gold

**Impacto:** `fct_delivery_daily` e `fct_newad_fintech_daily` via `io_calc` só mostram dados da Cora a partir de março/26.

**Causa raiz:**  
Existe apenas um IO para Cora (`io_202603_nwd-banco-cora-acfae3ab_001`). O `io_calc_daily_v4` é schedule-driven — só gera linhas para datas cobertas pelo IO. Os dados de ago/25–fev/26 existem em `raw.mediasmart_daily_operational` mas nunca foram formalizados em um IO.

**Workaround aplicado:**  
`gold.fct_newad_fintech_daily` lê diretamente de `share.platform_daily_detail` + LEFT JOIN `stg.io_lines_v4` para capturar todos os meses.

**Solução definitiva:** Criar IOs retroativos para ago/25–fev/26 no Admin UI com os campaign IDs corretos.

---

## 5. Siprocal: atribuição por nome, não por ID

**Impacto:** Impossível distinguir campaigns Siprocal entre dois client IDs que compartilham o mesmo `link_value`.

**Causa raiz:**  
`platform_client_links` para Siprocal usa `link_value = 'luckbet'` tanto para `nwd_luckbet_69e72f18` quanto `nwd_luckbet_a485d6bc`. A tabela raw `siprocal_delivery` tem o campo `advertiser` como nome (ex: `NEWAD_LUCKBET_BR_XXX`), não um ID estruturado.

**Solução necessária:** Definir qual client ID é canônico para Siprocal e desativar o link do legacy.

---

## ✅ RESOLVIDO — 10. Siprocal: pipeline quebrado, dados parados em 2026-05-26

**Data identificado:** 2026-06-10  
**Data resolvido (definitivo):** 2026-06-14

**Causa raiz:**  
A tabela `raw.siprocal_daily_native` (fonte original do ETL job) foi deletada entre 01/06 e 05/06, provavelmente durante uma limpeza. O ETL job `siprocal_daily:Daily` continuou tentando ler dela e falhando com 404 todos os dias.

**Diagnóstico (2026-06-11):**
- Automação ETL **sempre existiu**: Cloud Scheduler `adframework-etl-daily` (05:00 UTC) → job `siprocal_daily:Daily`
- Job lia de `platform_endpoints/siprocal_ep_external_daily.path_template` = `external://bq/raw.siprocal_daily_native`
- `siprocal_daily_native` sumiu → 404 a partir de ~02/06. Não existe Cloud Run Job ou outro scheduler que a populava.

**Resolução parcial (2026-06-11):**
Criada `raw.siprocal_raw_sheet` como TABLE nativa BQ com 1.078 linhas. Pipeline provisório:
`sync_sheet.py → raw.siprocal_raw_sheet → ETL job → raw.siprocal_delivery`
Funcionou parcialmente (dados até 09/06), mas dependia de passo manual + 3 bugs bloqueavam Jun/10 e Jun/11.

**Resolução definitiva (2026-06-14) — SiproCalConnector:**

Pipeline inteiro substituído por conector direto `SiproCalConnector` (`src/connectors/siprocal.py`).
Elimina `sync_sheet.py`, `siprocal_raw_sheet` intermediário e qualquer dependência de ADC local.

4 bugs corrigidos em 2026-06-14:
1. Firestore `siprocal_daily_external`: `bq_project_id/dataset_id/table_id` eram `None` → adicionado `adframework/raw/siprocal_delivery`
2. Firestore `siprocal.secrets.sheet_range`: `Planilha1!A:G` (aba inexistente) → `raw_daily!A:G`
3. Python closure late-binding em `_get()` dentro do loop `for raw_row in values[1:]` → corrigido com `def _get(field, _row=raw_row)` (default arg captura valor atual)
4. Cloud Run não faz auto-deploy por push → deploy manual obrigatório após cada mudança

**Bug adicional descoberto e corrigido em 2026-06-15 — SheetsClient filtro básico:**

**Sintoma:** `raw.siprocal_delivery` travou em Jun/09 (1.078 rows) apesar de a sheet ter dados até Jun/14.
**Causa raiz:** `SheetsClient.read_values()` usava `values.get()` que respeita filtros básicos ativos quando a conta tem acesso **Viewer**. O service account `adframework-etl@adframework.iam.gserviceaccount.com` é Viewer na sheet. A equipe Siprocal ativou um filtro na coluna Campanha (C) que escondia ~27 linhas de Jun/10-14, tornando-as invisíveis para a API.

**Fix (commit `ff1f6f5`):** `SheetsClient.read_values()` trocou `values.get()` por `spreadsheets.get(includeGridData=True)`. O `includeGridData` lê o GridData raw da planilha, que não é afetado por filtros de qualquer tipo, independente do nível de acesso da conta.

```python
# ANTES (afetado por filtros básicos para Viewer accounts)
result = self.service.spreadsheets().values().get(spreadsheetId=..., range=...).execute()

# DEPOIS (imune a filtros)
response = self.service.spreadsheets().get(
    spreadsheetId=..., ranges=[range_name], includeGridData=True
).execute()
# extrai formattedValue de cada cell em response["sheets"][0]["data"][0]["rowData"]
```

**Arquitetura atual (funcionando desde 2026-06-15):**
```
Google Sheet raw_siprocal (aba raw_daily!A:G)
  └─ SheetsClient.read_values() → spreadsheets.get(includeGridData=True)
       └─ SiproCalConnector (src/connectors/siprocal.py)
            └─ orchestrator._run_siprocal_daily()
                 └─ raw.siprocal_delivery [WRITE_TRUNCATE — substitui tudo a cada run]
                      └─ stg.siprocal_delivery → gold.fact_delivery

Firestore:
  platform_reports/siprocal_daily_external  — schedule: 03:20 UTC
  platform_credentials/siprocal.secrets     — {spreadsheet_id, sheet_range: raw_daily!A:G}
```

**Nota de qualidade de dados:** 181 das 1.105 linhas têm `campaign_id = "(vazio)"` — campo PI Externo não preenchido pela Siprocal. Não bloqueia atribuição de cliente (usa campo `advertiser`/Campanha), mas é dado incompleto. Clientes afetados: AMIGOTECPAR, BANCOCORA, DRCONSULTA, PATIOMEDEIROS, SENAR, TECPAR.

**Estado atual (2026-06-15):**
- `raw.siprocal_delivery`: 1.105 linhas | 2025-08-22 → 2026-06-14 | `last_status: ok`
- Cloud Run revision: `adframework-etl-00243-hg5` (deploy manual 2026-06-15)
- Zero passos manuais necessários — pipeline 100% automático e imune a filtros da sheet

---

## 7. Filtros removidos da camada RAW — pendente revisão no STG

**Data:** 2026-06-03  
**Contexto:** Auditoria da camada raw identificou filtragens acontecendo antes/durante a ingestão, violando o princípio medallion (RAW = tudo sem filtro).

### 7.1 `mediasmart_revenue_daily` — rules removido

**Filtro que existia (removido em 2026-06-03):**
```json
"rules": "revenuesource=[event1,event2,event3,event4,event5,2,3,4,5]"
"from": "2026-03-06"
```

**O que esse filtro fazia:**
- Limitava os `revenuesource` aceitos — qualquer outro tipo de receita era descartado antes de chegar ao BQ
- Limitava o backfill a partir de 2026-03-06

**Pendente no STG:** `stg.mediasmart_revenue` precisa ser revisada para aplicar o filtro de `revenuesource` se necessário para análise (ex: excluir fontes irrelevantes para o negócio).

### 7.2 `mediasmart_daily_daily` — colunas extras na tabela ATIVA ✅ RESOLVIDO (2026-06-11)

**Investigação 2026-06-11 revelou que:**
- A tabela ativa é `raw.mediasmart_daily` (31 cols, desde 2026-05-25), NÃO `raw.mediasmart_delivery`
- `raw.mediasmart_daily` já inclui `creative_type`, `creative_id`, `id_type`, `mediasmart_id`, `nativesize`, `size`, `client_currency` — vindas do schema fixo da API
- Esses campos vêm vazios/NULL quando o drilldown não inclui dimensão de criativo
- `clientrevenue`, `convertedclientrevenue`, `client_cost` também já estão presentes (31 cols)

**Status:** as colunas "ausentes" já existem em `raw.mediasmart_daily`. O issue era baseado em
inspeção da tabela legada `raw.mediasmart_delivery` (24 cols). Sem ação necessária.

### 7.3 `raw.mediasmart_revenue` — colunas perdidas no merge

**Colunas que chegam no staging mas NÃO chegam ao final:**
`eventid`, `revenue_source` (renomeado para `revenuesource`), `conversion_source`

**Pendente:** Adicionar essas colunas ao schema de `raw.mediasmart_revenue` para não perder granularidade.

---

## ✅ RESOLVIDO — 8. `gold.fact_io_plan` — view quebrada, zero linhas

**Data identificado:** 2026-06-08  
**Data resolvido:** 2026-06-09

**Causa raiz:**
A view `gold.fact_io_plan` apontava para `raw.luckbet_io_plan_snapshot` (dropada). Toda query retornava 0 linhas.

**Resolução:**
Pipeline IO Plan completamente reconstruído (ver `docs/io_plan_pipeline.md`):
- `raw.io_plan_drive_snapshot` — nova tabela raw, particionada, grain estratégia × flight × cliente
- `core.io_plan_manual` — seed manual + sync Drive; grain flight × cliente
- `gold.fact_io_plan` — VIEW reconstruída com GENERATE_DATE_ARRAY (grain diário)
- `scripts/io_plan/sync_drive.py` — sync automático do Drive para o BQ
- `services/io-plan-admin/` — serviço Cloud Run com botões de sync on-demand

**Validado em BQ (2026-06-09):**
- `core.io_plan_manual`: 15 flights (Cora Jan-Ago + TecPar Jan-Jun)
- `gold.fact_io_plan`: 424 linhas diárias (243 Cora + 181 TecPar)
- Cora hoje: 194.520 imp/dia planejadas, R$2.540/dia gross, R$474/dia net ✓
- TecPar hoje: 132.269 imp/dia planejadas, R$423/dia gross ✓

---

## ✅ RESOLVIDO — 9. MediaSmart ETL — raw.mediasmart_delivery parado em 2026-05-24

**Data identificado:** ~2026-06-01 | **Data resolvido:** 2026-06-11 (investigação confirmou)

**Causa raiz (atualizada após investigação 2026-06-11):**
O job `mediasmart_daily_daily` NUNCA escreveu em `raw.mediasmart_delivery` após 2026-05-24 —
porque o orchestrator usa `table_name = "mediasmart_daily"` + `dataset_id = "raw"` como destino
real (não o campo `bq_destiny = "raw.mediasmart_delivery"` que é legado e ignorado).

`raw.mediasmart_daily` é a tabela ATIVA desde 2026-05-25 (criada com schema 31 cols quando a
API MediaSmart ampliou sua resposta). `raw.mediasmart_delivery` (24 cols) era o destino antigo.

**Estado atual (2026-06-11):**
- `raw.mediasmart_daily`: 170 linhas, 2026-05-25 → 2026-06-10, `last_status: ok`
- Job roda diariamente às 03:20 UTC via Cloud Scheduler
- `stg.mediasmart_delivery`: UNION de `raw.mediasmart_delivery` (histórico) + `raw.mediasmart_daily` (ativo) — cobertura completa ago/25 → hoje

**Nota:** o `bq_destiny` legado pode ser removido do Firestore para evitar confusão futura.
Ver `mediasmart_stg_design.md` seção "Descobertas sobre delivery vs daily".

---

---

## 11. platform_bindings_v3 — race condition entre dois processos (core_mvp)

**Identificado:** 2026-06-10 (auditoria Shiro)
**Impacto:** Bindings de plataforma podem ser sobrescritos silenciosamente.

**Causa raiz:**
`core_mvp.platform_bindings_v3` é escrita por **dois processos independentes**, ambos com `WRITE_TRUNCATE`:
- `POST /maintenance/sync-adops-mvp` → `adops_sync.sync_adops_to_bigquery()`
- `POST /maintenance/sync-governance-mvp` → `governance_sync.sync_governance_to_bigquery()`

O segundo a rodar substitui completamente o primeiro. Sem mecanismo de merge.

**Risco:** Se ambos rodarem em sequência (ex: deploy CI), um apaga o trabalho do outro.
**Solução necessária (Shiro):** Unificar num único processo ou usar `WRITE_APPEND` com deduplicação.

---

## ✅ RESOLVIDO — 12. raw.siprocal_daily_materialized — tabela órfã

**Identificado:** 2026-06-10 | **Resolvido:** 2026-06-11 (auditoria BQ confirmou: tabela não existe)

Auditoria de 11/06 listou todos os objetos `siprocal_*` no dataset `raw`: apenas `siprocal_delivery`, `siprocal_raw_sheet` e `siprocal_sheet_ext` existem. `siprocal_daily_materialized` não existe — sem risco de fonte paralela.

---

## ✅ RESOLVIDO — 13. Siprocal — ingestão automática quebrada

**Identificado:** 2026-06-10 | **Resolvido:** 2026-06-11

A automação ETL sempre existiu. O problema era a tabela fonte `siprocal_daily_native` deletada. Ver resolução do issue #10.

---

## 14. fact_io_plan — sem granularidade de plataforma (Power BI)

**Identificado:** 2026-06-10
**Impacto:** No Power BI não é possível filtrar/relacionar plano de investimento por plataforma ou campanha. Só funciona no nível cliente × data.

**Causa raiz:**
`core.io_plan_manual` agrega todas as estratégias num único flight por cliente (sem `platform`). `gold.fact_io_plan` herda esse grain, sem campo `platform`.
`gold.fact_delivery` tem `client_id + day + platform` — o JOIN só funciona no nível total do cliente.

**Solução proposta:** Adicionar coluna `platform` a `core.io_plan_manual` e mudar grain de `rebuild_core_for_client` para `client × flight × platform`. Requer: ALTER TABLE + update do script + re-sync dos dados DRIVE-SYNC existentes. DRIVE-SYNC rows ganham platform automaticamente (já existe em `raw.io_plan_drive_snapshot`). Rows manuais (Jan-Abr) ficam com `platform = NULL`.

---

## 15. MediaSmart conector — sleep insuficiente, risco de rate limit (iteração)

**Identificado:** 2026-06-11
**Impacto:** Jobs de iteração (creatives hoje, strategies_detail e unique_users futuros) podem receber rejeição temporária da API MediaSmart ao exceder 128 req/min.

**Causa raiz:**
```python
time.sleep(0.15)   # _fetch_mediasmart_creatives_iter → 400 req/min (3× acima do limite)
RATE_LIMIT_DELAY = 0.3  # fetch_json_paginated → 200 req/min (ainda acima)
```
Limite oficial da API: 128 req/min e 10 concurrent requests.

**Solução necessária (antes de criar Jobs 7 e 8):**
- `_fetch_mediasmart_creatives_iter`: alterar `time.sleep(0.15)` → `time.sleep(0.6)`
- `RATE_LIMIT_DELAY`: alterar `0.3` → `0.6`
- Com 0.6s entre calls = 100 req/min — margem segura de 22% abaixo do limite

**Escopo:**
- Jobs bulk (1–6, `/api/analytics/custom-report`): 1 call/dia cada — **sem risco, não precisam de ajuste**
- Jobs de iteração 7 (strategies_detail) e 8 (unique_users): ~140 calls cada — **aguardar fix antes de criar**
- Job de creatives (já em produção): também está em risco com 0.15s — corrigir junto

---

---

## ✅ RESOLVIDO — 16. MediaSmart Grupo A (6 tabelas) — dimensões sem labels de dimensão

**Data identificado:** 2026-06-11 (sessão 1) | **Data resolvido:** 2026-06-11 (sessão 2)

**Sintoma inicial:** `raw.mediasmart_delivery_by_os` ingerindo com granularidade correta (52 linhas vs 7 sem drilldown) mas sem coluna `operating_system` — impossível identificar qual linha é Android, iOS, etc.

**Investigação completa realizada (todos os paths confirmados):**
- ✅ `base.py:normalize_data` — apenas normalização BQ-safe, sem renomeação semântica
- ✅ `orchestrator.py:_run_mediasmart_daily` — sem schema enforcement ou adição de colunas
- ✅ `bigquery.py:load_data` — para tabelas EXISTENTES: dropa todas as colunas não presentes no schema BQ existente (linha chave: `dropped = [c for c in incoming_names if c not in existing_names]`)
- ✅ Código Shiro (Admin UI) — sem DDL pré-criado para as 6 tabelas Grupo A
- ✅ Firestore `iter_params`/`field_var` — metadados do Admin UI, ignorados pelo ETL pipeline
- ✅ API MediaSmart `custom-report` — **FLEXÍVEL** (não fixo), retorna headers human-readable conforme drilldown solicitado. Confirmado via test direto em 2026-06-10.
- ✅ `_resolve_bq_target()` — usa `table_name`+`dataset_id`, sem template de schema

**Root cause real:**
As 6 tabelas foram criadas ANTES pelo ETL do Shiro (`aat-console`) que usa um mapeamento inverso: `"Event ID"` → `eventid`, `"Campaign ID"` → `controlid`, `"Strategy ID"` → `strategyid`. Quando nosso ETL rodou e encontrou as tabelas existentes com schema antigo, `bigquery.py:load_data` jogou fora todas as colunas não reconhecidas (`event_id`, `campaign_id`, `operating_system`, etc.) — porque só mantém colunas que estão no schema BQ existente.

**Decisão de design (confirmada):**
Não adicionar dicionário de mapeamento ao ETL raw. `normalize_data` deve permanecer normalização pura. Mapeamento semântico pertence ao STG SQL. Ver CHANGELOG 2026-06-11 sessão 2 seção "Decisão de design".

**Resolução:**
1. DROP das 6 tabelas via BQ Python client
2. Re-trigger dos jobs via ETL HTTP API `POST /jobs/{job_name}/run` (endpoint descoberto nesta sessão)
3. Tabelas recriadas com schema nativo: `event_id`, `campaign_id`, `strategy_id`, `operating_system`, `device_type`, `country`, `area_name`, `city`, `publisher_company`, `publisher_url`, `ad_exchange`, `hour`, `creative_id`, `creative_type`, `size`, `app_vs_web` — todos confirmados nos schemas BQ

**Estado atual (2026-06-11):**
Todas as 6 STG (T7, T9, T10, by_os, by_hour, by_publisher) estão **DESBLOQUEADAS**.
Tabelas têm 1 dia de dados (2026-06-10). Backfill histórico de 2026 está pendente — ver `mediasmart_stg_design.md` seção "Plano de Backfill Grupo A".

---

## ✅ RESOLVIDO — M1. MGID raw tables com alta duplicação

**Resolvido em 2026-06-14.** Firestore `write_mode` alterado para `WRITE_TRUNCATE` em `mgid_firstlevel_campaigns` e `mgid_firstlevel_creatives`. Auditado em 2026-06-15: `raw.mgid_campaigns` = 173 rows / 173 IDs únicos (1.0×). `raw.mgid_creatives` = 165 rows. Sem duplicação.

---

## ✅ RESOLVIDO — M2. MGID `spent` sem dados

**Resolvido em 2026-06-14.** `raw.mgid_stats_daily` (Job A) criado via endpoint `statistics-reports` com métricas `spent`, `cpc`, `revenue`, `profit`, `roas`. `stg.mgid_revenue` (T8) em produção com 2.344 rows, período 2025-10-01 → hoje. Total spent histórico: R$157.271,98. `raw.mgid_delivery` (legacy) descontinuado como fonte de spent.

---

## M4. MGID — novas campanhas não vinculadas automaticamente ao `platform_client_links` 🔧 BACKLOG PÓS-ENTREGA

**Identificado:** 2026-06-15
**Impacto:** Cada novo flight MGID (mensal por cliente) cria um `campaignid` novo que não existe em `platform_client_links` → STG mostra `mgid_client_id IS NULL` → dados ficam como `unattributed` na gold até correção manual.

**Workaround atual (2026-06-15):** detecção e INSERT manuais via `C:\Temp\add_mgid_campaigns_jun2026.py`. Rodado manualmente após auditoria — 6 campanhas de jun/2026 adicionadas (Einstein, Senar ×2, Amigo, Stoquinho, Banco Cora). `stg.mgid_delivery` agora 100% atribuído.

**Solução planejada:** novo job Python no orchestrador `mgid_link_new_campaigns`, roda após `mgid_firstlevel_campaigns`:
1. Detecta campanhas em `raw.mgid_stats_daily` (últimos 7 dias) sem entrada em `platform_client_links`
2. Infere `client_id` pelo nome da campanha (CASE WHEN keyword map)
3. Insere como `pending_confirmation` (match confiante) ou `unresolved` (ambíguo)
4. Loga para revisão humana semanal

**Plataformas afetadas:** somente MGID (campaignid por flight). MediaSmart (eventid por advertiser) e Siprocal (advertiser string) mudam só ao onboarbar cliente novo — manual é suficiente.

**Pré-requisito:** coordenar com Shiro para adicionar job ao orchestrador, ou criar Cloud Scheduler independente.

---

## M3. `raw.mgid_stats_daily` com 1.95× duplicação no raw

**Identificado:** 2026-06-15 (auditoria)
**Impacto:** Baixo — `stg.mgid_delivery` (T3) e `stg.mgid_revenue` (T8) já aplicam `ROW_NUMBER() OVER (PARTITION BY day, campaignid ORDER BY raw_ingested_at DESC)` para dedup. STG entrega 2.344 rows únicos corretamente.

**Causa:** Job A usa `WRITE_APPEND` (comportamento correto para ingestão diária). O backfill foi executado em múltiplos triggers sobrepostos, acumulando ~2.222 linhas duplicadas.

| Tabela | Total rows | Grains únicos | Fator dup |
|---|---|---|---|
| `raw.mgid_stats_daily` | 4.566 | 2.344 | 1.95× |

**Ação:** Dedup pontual `SELECT DISTINCT *` reduz raw para 2.344 rows. Não urgente pois a STG já corrige. Executar junto com próxima janela de manutenção.
```sql
CREATE OR REPLACE TABLE `adframework.raw.mgid_stats_daily`
AS SELECT DISTINCT * FROM `adframework.raw.mgid_stats_daily`;
```

---

## 6. Conversões conv1–5 sem semântica nas views genéricas

**Impacto:** `fct_delivery_daily` e `fct_creative_daily` expõem `conversions1`–`conversions5` sem significado de negócio.

**Status:**  
Mapeamento criado em `gold.dim_client_semantics`. Luckbet confirmado por Shiro (29/04/2026). Cora, Einstein, TecPar ainda pendentes de confirmação comercial.

| Campo | Luckbet | Cora (pendente) |
|---|---|---|
| conversions1 | pageviews | pageviews |
| conversions2 | cadastros | leads |
| conversions3 | ftds | contas_abertas |
| conversions4 | depositos_recorrentes | ativacoes |
| conversions5 | inicio_cadastro | inicio_cadastro |
