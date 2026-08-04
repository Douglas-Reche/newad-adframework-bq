# CHANGELOG — AdFramework BQ Pipeline

> Registro cronológico de decisões, mudanças e evoluções arquiteturais.
> **Regra:** toda mudança relevante no pipeline, arquitetura ou decisão de negócio deve ser registrada aqui com data, motivo e arquivos tocados.
> Formato: mais recente no topo.

---

## 2026-08-04 — Sistema de documentação em 3 saltos + farol permanente no hub

**Autor:** Douglas Reche

### Resumo

Duas frentes: (1) formalização do fluxo de documentação Git+Notion (o próprio sistema
que gera este changelog), (2) farol de status permanente na tela principal do hub.
Narrativa completa em Notion — tasks "Sistema de Documentação em Duas Camadas (Git +
Notion)" e "Hub de Gerenciamento BigQuery (douglas-data-hub)".

### O que foi feito

1. **`core/OWNERSHIP.yaml` criado do zero** — fonte única de "essa tabela/view do
   dataset `core` é do pipeline / é do Admin UI do Shiro". 18 objetos (10 pipeline + 8
   Shiro), auditado ao vivo contra `core.INFORMATION_SCHEMA.TABLES`. `CLAUDE.md`,
   `backend.md` e `hub-frontend.md` agora apontam pra lá em vez de manter cópia própria
   da lista.
2. **`CLAUDE.md`** — fluxo de documentação em 3 saltos (agente especializado →
   orquestrador → agent `docs` → confirmação de volta; nenhum agente especializado chama
   `docs` direto), critério de pré-registro no Notion, critério MÃE vs. task única,
   cadência de checkpoint em MÃE longa, passo 0 do orquestrador (checar Notion por
   MÃEs/tasks abertas antes de começar), correção de auto-contradição na tabela de
   Regras Absolutas.
3. **`docs/_pending_purge.md` criado (vazio)** — processo de expurgo semanal: arquivo de
   "análise pontual" nunca é deletado na hora, é flagueado e só removido após revisão em
   lote confirmada pelo usuário no fim da semana.
4. **Farol permanente no hub** (`hub/app.py`, ~linhas 537-566) — 3 colunas visíveis sem
   clicar em nenhuma aba: saúde do pipeline (pior status entre camadas), contador de
   Propostas de Mudança pendentes (`core.change_proposals WHERE status='pending'`),
   custo do mês corrente. Sem resumo de Notion na tela (decisão do Douglas). Testado
   localmente (HTTP 200 + `py_compile`), sem redeploy.

### Arquivos alterados

- `core/OWNERSHIP.yaml` (novo), `docs/_pending_purge.md` (novo)
- `CLAUDE.md`, `.claude/agents/backend.md`, `.claude/agents/hub-frontend.md`, `.claude/agents/docs.md`
- `hub/app.py`, `hub/README.md`

### Pendências

Nenhum commit feito ainda — aguardando confirmação do usuário. Achado paralelo (não
aplicado, fora deste repo): lógica de retry/rate-limit duplicada entre os conectores
MediaSmart (8 ocorrências de `RATE_LIMIT_DELAY`/`MAX_RETRIES`/`time.sleep`) e MGID (13
ocorrências) em `adframework_python/src/connectors/` — repositório `adframework`
(monorepo aat_console), não `newad-adframework-bq`. Cada conector reimplementa o próprio
loop de retry em vez de compartilhar via `adframework_python/src/base.py`. Candidato a
refatoração futura, não urgente, não aplicado — registrado aqui só como nota cruzada
porque foi levantado na mesma sessão; não entra em `docs/known_issues.md` (que é
escopado à pipeline BigQuery deste repo).

---

## 2026-07-01 — Incidente encerrado: RAW MS restaurada, STG/Gold 100% operacional (todas as 3 plataformas)

**Autor:** Douglas Reche

### Resumo

Fix do incidente de 2026-06-30 concluído. Pipeline ETL MediaSmart operacional end-to-end.

### O que foi feito

1. **Credencial MS corrigida** — `MediasmartConnector({})` usa env vars `MEDIASMART_USERNAME/MEDIASMART_PASSWORD` do Cloud Run em vez do email do Shiro no Firestore (que retornava 401). Commit `d0cd1a7` em `rshiro-newad/adframework` → revisão 00282 deployada.

2. **RAW MS recriada com schema correto** — Tabelas `ms_advertisers`, `ms_campaigns`, `ms_creatives` dropadas e jobs disparados manualmente:
   - `mediasmart_firstlevel:advertisers` → 21 linhas, schema correto (event_id, name, iab_category, domain, sensitive_content, platform, raw_ingested_at)
   - `mediasmart_firstlevel:campaigns` → 13 linhas, schema correto (campaign_id, campaign_name, client_id, started_at, finished_at, platform, raw_ingested_at)
   - `mediasmart_firstlevel:creatives` → 193 linhas, schema correto (creative_id, creative_name, campaign_id, status, url, thumbnail_url, creative_type, width, height, platform, raw_ingested_at)

3. **STG MS views restauradas** — Substituídas as views dummy/interim pelas reais:
   - `stg.ms_advertisers`: agora usa `a.platform` e `CAST(a.raw_ingested_at AS TIMESTAMP)` das colunas reais da tabela
   - `stg.ms_campaigns`: extração de formato por busca em qualquer segmento do campaign_name + join stg.ms_advertisers para client_id
   - `stg.ms_creatives`: passthrough com coluna `size` concatenada

4. **Gold layer validado** — `gold.fact_delivery` com 3 plataformas:
   - mediasmart: 94 linhas, 2.6M impressões
   - mgid: 78 linhas, 804K impressões
   - siprocal: 757 linhas, 7.5M impressões
   - `gold.fact_pacing`: 132 linhas com `investimento_realizado` calculado

### Arquivos alterados

- `stg/ddl/ms_advertisers.sql` — versão final (sem hardcoded interim)
- `stg/ddl/ms_campaigns.sql` — versão real (não mais dummy)
- `stg/ddl/ms_creatives.sql` — versão real (não mais dummy)

---

## 2026-06-30 — Incidente: 4 tabelas RAW corrompidas por deploy desatualizado — causa raiz achada, push do fix pausado por alinhamento com Shiro

**Autor:** Douglas Reche

### Sintoma

Erro no Power BI ao consultar `stg.mg_advertisers`: `"Unrecognized name: campaign_id; Did you mean campaignType?"`.

### Diagnóstico

Auditoria de schema em todas as 15 tabelas `raw.*` revelou **4 corrompidas** (sobrescritas por `WRITE_TRUNCATE` com schema antigo, mesmo row count das corretas — ou seja, rodaram recentemente com código errado):

| Tabela | Schema real (errado) |
|---|---|
| `ms_campaigns` | `created_at, updated_at, color, description, state, tags, type` — nem é o schema antigo do MS, parece ainda mais velho |
| `ms_creatives` | `thumbnail_url, width, height` só |
| `mg_campaigns` | camelCase nativo MGID API (`id, campaignType, startDate...`) |
| `mg_teasers` | `url, status` só |

Intactas: `ms_advertisers`, `ms_delivery*` (T4-T7), `mg_delivery*` (T4-T7), `sp_delivery`, `io_plan_drive_snapshot` — exatamente as tabelas de **catálogo** (T2/T3 de MS e MGID) foram afetadas, não as de entrega.

### Causa raiz (achada via agente de investigação no código)

**Gap de deploy, não bug de código duplicado.** O fix que normaliza o schema (`fetch_campaigns_normalized()` em `mgid.py`, equivalentes em `mediasmart.py`) existe **só na árvore de trabalho local** do repo `rshiro-newad/adframework` — nunca foi commitado nem dado push. O Cloud Run de produção (`adframework-etl`) ainda roda o último commit real (`842ab47`, 15/06), que tem a versão antiga/sem normalização. O job agendado (`mgid_firstlevel_campaigns`, cron diário) rodou em 27/06 com esse código antigo e sobrescreveu (`WRITE_TRUNCATE`) as tabelas corretas que validamos ao longo desta sessão de rebuild.

### Tentativa de fix — pausada

Preparei commit só com os 4 arquivos de código relevantes (`mediasmart.py`, `mgid.py`, `siprocal.py`, `orchestrator.py`), explicitamente excluindo deleções/modificações de docs não relacionadas que apareceram no `git status` (não criadas por mim, fora de escopo).

**Achado que pausou o push:** o repositório `rshiro-newad/adframework` (origin) tem **19+ commits autênticos do Shiro** (conta `rshiro-newad`, fev-abr/2026) mexendo nos mesmos 3 arquivos (`mediasmart.py`, `mgid.py`, `orchestrator.py`), incluindo um `revert(etl): restore adframework_python to pre-restore baseline`. Confirmado via `git log --pretty=%an` que são commits genuínos do Shiro, não PRs antigos do Douglas. Dado esse nível de atividade concorrente real no mesmo arquivo de produção, **decisão: pausar o push até alinhar com o Shiro diretamente** — risco de colidir silenciosamente com trabalho dele sem conflito textual aparente.

**Também não foi possível restaurar localmente** (rodar os jobs com o código correto local contra a API real) — as credenciais (`MEDIASMART_USERNAME/PASSWORD`, `MGID_TOKEN/CLIENT_ID`) não estão configuradas neste ambiente (sem `.env`, sem env vars).

### Achado lateral — 2 jobs antigos ativos com dado financeiro fora de escopo

Auditoria completa dos 37 jobs do Firestore (`platform_reports`) encontrou `mgid_stats_creative` e `mgid_stats_daily` **ativos**, escrevendo métricas financeiras (`spent, revenue, profit, roas`) em tabelas antigas (`raw.mgid_stats_creative`, `raw.mgid_stats_daily`, fora do pipeline novo) — contraria a decisão de 16/06 ("financeiro fora de escopo, jobs antigos desabilitados"). **Desabilitados agora** (`enabled=False` no Firestore, reversível).

### Inventário completo de jobs (37 total)

- **Pipeline novo:** 22 jobs (14 ativos + 8 desabilitados intencionalmente — os `_t4/_t5/_t6/_t7` de teste, substituídos pelos jobs de produção consolidados em 22-24/06)
- **Antigo/fora de escopo:** 15 jobs (13 já desabilitados corretamente + 2 que acabamos de desabilitar nesta sessão)

### Regra nova registrada na memória

No repo `rshiro-newad/adframework`, só commitar código de verdade — nunca memória/docs/discussão/temporários. Ver `feedback_shiro_repo_boundary` na memória do projeto.

### Resolução parcial — fix da MGID isolado e enviado para produção

Investigação mais profunda (`git apply --3way` num worktree descartável a partir do `origin/main` real) revelou que o conflito não era uniforme: **o fix de `mg_campaigns`/`mg_teasers` (MGID) aplica limpo, zero conflito** — função isolada do resto. Já o fix de `ms_campaigns`/`ms_creatives` (MediaSmart) está entrelaçado na mesma função onde o Shiro construiu lógica própria de normalização de entrega (`relaxed_tokens`/`normalized_methods`, com fallback de credenciais via env vars) — precisa de reconciliação manual cuidadosa, não é um merge automático seguro.

**Ação tomada:** criado branch `fix/mg-campaigns-teasers-normalized-schema` a partir do `main` atual (via `git worktree`, sem tocar no branch de trabalho local), aplicado só `mgid.py` (limpo) + as 13 linhas isoladas do `orchestrator.py` que ativam `fetch_campaigns_normalized()`/`fetch_teasers_normalized()` pros targets `mg_campaigns`/`mg_teasers`. Verificado sintaxe Python válida. Commitado (`3dfddaa`) e **dado push direto pra `main`** (`562ccae..3dfddaa`, fast-forward limpo, confirmado no remoto) — autorizado explicitamente pelo usuário após confirmar que essa parte não conflita com nada do Shiro.

Isso deve disparar o redeploy automático do Cloud Run (`adframework-etl`) via GitHub Actions, restaurando `raw.mg_campaigns`/`raw.mg_teasers` com o schema correto no próximo job agendado (ou pode ser disparado manualmente assim que o deploy completar).

### Confirmação completa — deploy + restauração de dados, ponta a ponta

Deploy automático confirmado via `gcloud run revisions list` (`adframework-etl-00277-nmv`, criada 16:42, logo após o push). Jobs `mgid_firstlevel:campaigns`/`mgid_firstlevel:creatives` disparados manualmente via `POST /jobs/{job}/run` no serviço já redeployado.

**Achado durante a restauração — bug real em `bigquery.py` (não nosso, pré-existente):** `load_data()` mantém o schema existente da tabela quando ela já existe, **mesmo com `WRITE_TRUNCATE`** — só substitui o schema de verdade quando, por acidente, a lista de "colunas mantidas" fica vazia (zero sobreposição de nomes entre schema velho e novo), o que faz o filtro ser pulado e o dataframe completo ser usado. `mg_campaigns` corrigiu "por sorte" (schema velho 100% diferente do novo). `mg_teasers` não corrigiu na primeira tentativa — schema velho (`status, url`) tinha 2 nomes coincidentes com o schema novo, então o filtro normal entrou em ação e manteve só essas 2 colunas, descartando o resto.

**Fix:** `DROP TABLE raw.mg_teasers` + re-rodar o job — força `table_exists()=False`, cai no mesmo caminho que recriou `mg_campaigns` corretamente com schema novo via autodetect.

**Validação final (ponta a ponta):**
- `raw.mg_campaigns`: 173 linhas, schema completo correto (`campaign_id, campaign_name, status_name, campaign_type, start_date, end_date, platform, raw_ingested_at` + extras)
- `raw.mg_teasers`: 180 linhas, schema completo correto (`creative_id, creative_name, campaign_id, status, url, thumbnail_url, advert_text, call_to_action, width, height, platform, raw_ingested_at`)
- **`stg.mg_advertisers`** (a view que disparou o erro original no Power BI) — testada diretamente, responde normalmente, 39 linhas

### Pendências

- [ ] **`ms_campaigns`/`ms_creatives` (MediaSmart) continuam quebradas** — fix não enviado, precisa reconciliar manualmente com a lógica do Shiro (`relaxed_tokens` vs `normalized_methods`) antes de qualquer push
- [ ] Quando for fixar MediaSmart: checar primeiro se há sobreposição de nomes entre o schema velho de `ms_campaigns`/`ms_creatives` e o novo — se houver, vai precisar do mesmo `DROP TABLE` manual (o bug do `load_data()` se aplica igual lá)
- [ ] Revalidar `gold.dim_campaign`/`gold.fact_delivery` do lado MGID com os dados frescos (datas reais de `mg_campaigns` mudaram — `end_date` de Aperam por ex. ficou `2024-12-31`, conferir se isso é esperado)

---

## 2026-06-24 — Gold layer reconstruída (`dim_campaign`, `fact_delivery`, `fact_io_plan`, `fact_pacing`) — MVP pra apresentação Power BI

**Autor:** Douglas Reche

Reconstrução rápida pós-rebuild RAW+STG, sob prazo de apresentação MVP no Power BI. Reaproveita o princípio de negócio decidido em 16/06 (`project_gold_layer_design.md`): **"Tudo financeiro = IO Plan. Tudo volume = plataforma."** Ligação plano↔entrega por `client_id + formato + dia` (não por `campaign_id` — o plano nunca especifica campanha). Design completo em `docs/gold_layer_design.md`.

9 arquivos legados (`gold/ddl/_legacy/`) — schema pré-rebuild, referenciavam tabelas já dropadas.

**`gold.dim_campaign`** — UNION `ms_campaigns`+`mg_campaigns`+`sp_campaigns`. 224 campanhas (14 MS, 173 MGID, 37 Siprocal).

**`gold.fact_delivery`** — grain `client_id+day+platform+formato`, agregado (sem `campaign_id`/`creative_id`). UNION das 3 `*_delivery`. 929 linhas, 14 clientes, 2025-08-22→2026-06-24.

**`gold.fact_io_plan`** — expande `stg.io_plan` (grain=voo) em 1 linha por dia (`GENERATE_DATE_ARRAY`), `planned_spend/flight_days`. 3.326 linhas, 2 clientes (cobertura atual do sync do Drive — Cora + outro).

**`gold.fact_pacing`** — `FULL OUTER JOIN fact_io_plan` × `fact_delivery` por `client_id+day+formato`. **Validado contra dado real:** Banco Cora, dias recentes, planejado e realizado lado a lado por formato (Display/Retargeting/Video/Native). 3.972 linhas.

### Arquivos

- `gold/ddl/dim_campaign.sql`, `gold/ddl/fact_delivery.sql`, `gold/ddl/fact_io_plan.sql`, `gold/ddl/fact_pacing.sql`
- `docs/gold_layer_design.md` — design novo

### Achado e fix — TecPar/Amigo: `client_id` não bate entre plano e entrega

**Confirmado contra dado real:** plano do TecPar (`tecpar_edfcc744`) cobre `Display/Native/Push/Retargeting` (ago/25-jun/26). Entrega real está dividida: `tecpar_edfcc744` só tem `Push` (dez/25-mar/26); `Display/Native/Retargeting` (jun/26) + parte do `Push` (set/25-jun/26) estão sob `amigo_db1c2f0c`. `fact_pacing` não cruzava isso — TecPar aparecia com 888/968 dias "só planejado, sem entrega", enganoso.

**Esclarecimento do usuário:** não é um erro de vínculo — **o plano do TecPar é, na prática, inteiramente para o Amigo** (hoje 100% da entrega do TecPar É Amigo; TecPar pode ganhar outras sub-marcas no futuro, com planos próprios separados).

**Fix v1 aplicado em `gold/ddl/fact_pacing.sql`:** mapeamento `tecpar_edfcc744 → amigo_db1c2f0c` no lado do plano. Resultado parcial: `ambos` sobe de 80→144 dias, mas sobrou `tecpar_edfcc744` com 103 linhas "só entrega" sem par.

**Investigação do residual:** `raw.sp_campaigns` mostra que `tecpar_edfcc744`/`amigo_db1c2f0c` são **duas campanhas Siprocal genuinamente distintas** (não duplicata) — marca `"AMIGOTECPAR"` (set/25-jun/26) vinculada a `amigo_db1c2f0c`, e marca `"TECPAR"` pura (dez/25-mar/26) vinculada a `tecpar_edfcc744`. Ambas são entrega real da conta TecPar.

**Fix v2 (final):** `fact_pacing` agora soma a entrega das duas chaves (`delivery_mapped`/`delivery_summed`) antes do join com o plano (também mapeado pra `amigo_db1c2f0c`). **Resultado: `ambos` sobe de 144→224 dias.** `tecpar_edfcc744` não aparece mais como chave solta — tudo consolidado em `amigo_db1c2f0c` no `fact_pacing` (mantendo `dim_campaign`/`fact_delivery` com os dois `client_id` reais separados).

### Estado real do `gold.fact_pacing` (NÃO é 100% — checagem honesta pedida pelo usuário)

Só **Banco Cora** e **Amigo/TecPar** têm IO Plan sincronizado — os outros 11 clientes com entrega real (`Aperam, Luckbet, Senar, Pátio Medeiros, Dooing, Einstein, Dr. Consulta, Stoquinho, Stocco, Pardini, Catálise`) têm **zero linhas de plano**, então `fact_pacing` só mostra entrega pra eles, sem comparação com planejado. **Esperado** (sync do Drive ainda não cobre esses clientes), não é bug — mas não é "100% populado".

### Achado e fix — `formato` com capitalização inconsistente entre plataformas

Confirmado contra dado real: `stg.ms_campaigns.formato` preserva texto original do `campaign_name` (CAIXA ALTA, ex: `"DISPLAY"`, `"V�DEO"` com erro de acento), enquanto MGID/Siprocal/IO Plan usam Title Case (`"Display"`, `"Video"`). Sem normalizar, o Power BI trataria como categorias diferentes num slicer (`"DISPLAY"` ≠ `"Display"`). **Fix:** normalização (TRANSLATE accent-strip + CASE WHEN → Title Case fixo) aplicada em `gold.dim_campaign` e `gold.fact_delivery` (não na STG, que preserva o texto original por design). Resultado: só 6 categorias limpas em toda a Gold (`Display/Native/Push/Retargeting/Video/AppInstall`).

### Correção — `gold.fact_io_plan` tinha perdido `unit_price`/`buy_model`, necessários pra calcular `investimento_realizado` no Power BI

Usuário identificou: a fórmula de negócio (`CPM = impressions × unit_price / 1000`, `CPC = clicks × unit_price / 1000`) precisa do `unit_price` do plano — campo que existia em `stg.io_plan` mas foi descartado na agregação do `gold.fact_io_plan` original.

**Achado ao investigar a granularidade certa:** `client_id+formato+dia` sozinho tem **212 dias** com 2 `unit_price`/`buy_model` diferentes coexistindo (ex: TecPar `"Push - MGID"` R$0,35 vs `"Push - App Targeting SIPROCAL"` R$0,80, ambos rodando jan-mar/2026) — não é erro, são estratégias/plataformas genuinamente diferentes sob o mesmo `formato`. **Fix:** adicionar `platform` à granularidade (`client_id+report_date+formato+platform`) resolve quase todos os conflitos — só sobra `AppInstall` (`platform='unknown'`, sem sinal no texto, sem impacto porque não roda em entrega real ainda).

**`goal_type` via `core.dict_format`** (platform+formato → goal_type), não via `buy_model` da planilha (lembrete do usuário — `buy_model` vem frequentemente `None` pra `Push`, pouco confiável; `dict_format` é a regra de negócio já validada).

**`gold.fact_pacing` reconstruída** com o cálculo de `investimento_realizado` feito direto em SQL (precisa cruzar `unit_price`/`goal_type` do plano com `impressions`/`clicks` da entrega linha a linha — impossível via relacionamento simples no Power BI, já que são 2 fact tables sem join direto). **Sem o remapeamento TecPar→Amigo** desta vez — esse rollup fica pra hierarquia pai-filho do `gold.dim_advertiser` no Power BI (ver decisão abaixo), não mais hardcoded em SQL.

**Validado contra dado real:** CPC (Push, TecPar/Siprocal, R$0,80, 52 cliques) → `R$0,0416`. CPM (Display, Cora/MediaSmart, R$10, 20.207 impressões) → `R$202,07`. Ambos batem com a fórmula. 132 linhas com `investimento_realizado` calculado.

### Decisão de modelagem Power BI — hierarquia pai-filho em vez de remapeamento em SQL

Usuário questionou por que `fact_pacing` fazia `FULL OUTER JOIN` se vai usar medidas DAX no Power BI — confirmado: pra métricas simples (planejado, realizado bruto), o join em SQL não tem função, basta relacionar `fact_io_plan`/`fact_delivery` com `dim_advertiser`+uma dimensão de calendário no modelo do Power BI. O rollup TecPar→Amigo deve ser feito via hierarquia pai-filho (`dim_advertiser.parent_client_id`) e uma medida DAX com `FILTER`/`SELECTEDVALUE`, não hardcoded em SQL — evita fixar uma regra de negócio que pode mudar (TecPar pode ganhar outras sub-marcas no futuro). **Exceção:** `investimento_realizado` continua precisando do join em SQL (ver acima), por cruzar atributos de duas fact tables linha a linha — isso não é resolvível só com relacionamento.

### `gold.dim_advertiser` criada — filtro-mãe pros dashboards por cliente

Decisão: cada dashboard Power BI será específico de 1 cliente (1 arquivo pra Cora, 1 pra TecPar, etc.) — `dim_advertiser` é a dimensão que trava esse filtro e relaciona com todas as fact tables (`fact_pacing`/`fact_delivery`/`dim_campaign`) por `client_id`. Expõe a hierarquia já modelada em `core.dim_client` (`parent_client_id`/`client_level` — Amigo nível 2, filho do TecPar). **Separado de `core.dim_client` por design:** `core.*` é dataset de pipeline/Admin UI, `gold.*` é consumo BI — Power BI conecta só no `gold`, sem precisar de acesso ao `core`. 36 clientes, 0 órfãos confirmado contra `fact_pacing`/`fact_delivery`/`dim_campaign`.

### Pendências (pós-MVP)

- [ ] Mapeamento TecPar→Amigo é hardcoded (`CASE WHEN client_id = 'tecpar_edfcc744'`) — se TecPar ganhar sub-marcas novas no futuro, revisar essa lógica
- [ ] IO Plan só cobre 2/14 clientes ativos — sync do Drive precisa rodar pros outros 11+ pra `fact_pacing` ficar completo
- [ ] Avaliar materializar como TABLE se performance no Power BI exigir (hoje são VIEWs sobre VIEWs sobre VIEWs — várias camadas)

---

## 2026-06-24 — `stg.io_plan` criada — `formato`/`goal_type` extraídos de `strategy_name`, `core.dict_format` ganha `AppInstall`/CPI

**Autor:** Douglas Reche

IO Plan (planejamento de verba, Drive → RAW → STG → Gold) é pipeline independente do rebuild de entrega, mas precisava do mesmo tratamento de `formato`/`goal_type` que MS/MGID/Siprocal já têm — pra poder comparar planejado vs entregue pelo mesmo vocabulário.

### `core.dict_format` ganha `AppInstall` → `CPI`

`platform='io_plan'` (genérico) — AppInstall ainda não roda em nenhuma plataforma de entrega ativa (MS/MGID/Siprocal), só existe como estratégia de planejamento. Decisão do usuário.

### Achado — campo `format` que já existia na RAW não serve pro vocabulário de `dict_format`

`raw.io_plan_drive_snapshot.format` vem direto da planilha (`"Banner IAB"`, `"Vídeo"`, `"Push Banner"`) — vocabulário diferente do usado em entrega (`Display/Video/Retargeting/Native/Push`). Não dá pra reusar — `formato` precisou ser extraído de novo a partir de `strategy_name` (texto livre), igual ao que já fizemos pra `campaign_name` da MS.

**Extração testada contra os 295 valores reais:** busca por keyword (`native`, `video`/`vídeo`, `retargeting`, `display`, `push`, `appinstall`) no `strategy_name`. **295/295 (100%) resolvido.**

### Achado — bug de detecção de `platform` no `sync_drive.py` (não corrigido na RAW, corrigido na STG)

`PLATFORM_RULES` procura substring exata `"push siprocal"` — não bate com o dado real `"Push - App Targeting SIPROCAL"` (texto no meio). 91/295 linhas caíam em `platform='unknown'`. Corrigido na STG (sem tocar no parser RAW): regra adicional `contém 'SIPROCAL' → siprocal`, `contém 'MGID' → mgid`. Resolve 7/91. **Os outros 84 (`Push`/`AppInstall` genéricos) realmente não têm sinal de plataforma no texto da estratégia — limitação real do dado, não bug de regex.**

### `goal_type` join por `formato` apenas (não `formato+platform`)

Decisão: `goal_type` é o mesmo independente da plataforma pra cada `formato` já confirmado (`Native`=CPC em MS e MGID, `Push`=CPC em MGID e Siprocal) — então o join usa só `formato`, não trava na resolução de `platform` (que tem gaps próprios, ver acima).

### `stg.io_plan`

Grain: `(client_id, drive_folder, strategy_name, flight_start)`, dedup pelo snapshot mais recente (mesma lógica do arquivo legado `_legacy/io_plan_drive.sql`, mas **sem o bug que forçava `Push` sempre = `siprocal`** — esse arquivo tinha essa regra, contradita pelo dado real `"Push - MGID"`, 3 linhas).

**Resultado:** dedup reduz 295→**125 linhas** (múltiplos snapshots do mesmo voo/estratégia entre syncs — mantém só o mais recente). **125/125 (100%) com `formato`/`goal_type`. 96/125 (77%) com `platform` resolvido.**

### Arquivos

- `stg/ddl/io_plan.sql` — criado e validado
- `core.dict_format` — +1 linha (`AppInstall`/`io_plan`/`CPI`)

### Correção — `goal_type` removido do `stg.io_plan`

Decisão do usuário: `goal_type` é conceito de campanha/entrega (`ms_campaigns`/`mg_campaigns`/`sp_campaigns`), não de planejamento. `stg.io_plan` carrega só `formato` — sem join com `core.dict_format`.

### Achado — bug de duplicação confirmado na RAW (já registrado como pendência em 16/06)

Verificação explícita pedida pelo usuário: existem grupos com até **14 snapshots idênticos** da mesma linha de plano na `raw.io_plan_drive_snapshot` (ex: Banco Cora, `2025/ABRIL`, estratégia `"Push"`). Investigado: são **7 cópias idênticas por sync** (mesmo `source_file`, `monthly_spend`, `impressions`), em só 2 timestamps de sync (`2026-06-15 17:42:16` e `17:57:39`) — não 14 syncs genuínos no tempo. Confirma o bug já registrado em `project_io_plan_raw_state.md` (16/06): `parse_xlsx` em `sync_drive.py` itera todas as abas da planilha sem filtrar pela aba certa do mês, duplicando linhas por sync.

**Decisão:** não corrigir o parser nesta sessão — `stg.io_plan` já mascara corretamente via dedup (`ROW_NUMBER` por snapshot mais recente, confirmado **0 duplicatas na STG final**). Fix do parser RAW fica registrado como pendência (ver `docs/io_plan_pipeline.md` L1).

### Pendências

- [ ] 84 linhas (`Push`/`AppInstall` genéricos) sem `platform` — sem sinal no texto, exigiria contexto adicional (ex: cliente+período cruzado com delivery real) pra resolver
- [ ] L1 do `io_plan_pipeline.md` (parser duplica linhas por sync, iterando abas sem filtrar pelo mês) — confirmado ainda presente, mascarado pelo dedup da STG, não corrigido na fonte
- [ ] L1-data (planilhas sem padrão de data na aba) — fora de escopo desta sessão, não impactou as 295 linhas atuais (todas tinham `flight_start`/`flight_end` preenchidos)

---

## 2026-06-24 — T5-T7 da STG criados (`*_delivery_by_geo/device/hour`, MS + MGID)

**Autor:** Douglas Reche

Mesma lógica do T4, com dimensão extra passthrough por T (`country+city` / `device_type[+operating_system]` / `hour`). `client_id, formato, goal_type` denormalizados via join com `*_campaigns` (mesmo padrão do T4).

**MGID precisa do join em cadeia via `mg_teasers`** (`raw.mg_delivery_by_geo/device/hour` só tem `creative_id`, sem `campaign_id` nativo — diferente do T4, que já tinha `campaign_id`). Testado contra dado real antes de criar: **800/800, 251/251, 1346/1346 (100% nos três)**.

**MS já tem `campaign_id`/`event_id` nativos em todos os Ts** (sem join extra necessário) — mesmo padrão do T4.

### Resultado

| View | Total | `client_id` |
|---|---|---|
| `ms_delivery_by_geo` | 41.818 | 41.817 (1 = `Teste-Newad`, conta interna) |
| `ms_delivery_by_device` | 6.153 | 6.152 |
| `ms_delivery_by_hour` | 18.660 | 18.659 |
| `mg_delivery_by_geo` | 800 | 800 (100%) |
| `mg_delivery_by_device` | 251 | 251 (100%) |
| `mg_delivery_by_hour` | 1.346 | 1.346 (100%) |

### Arquivos

- `stg/ddl/ms_delivery_by_geo.sql`, `stg/ddl/ms_delivery_by_device.sql`, `stg/ddl/ms_delivery_by_hour.sql`
- `stg/ddl/mg_delivery_by_geo.sql`, `stg/ddl/mg_delivery_by_device.sql`, `stg/ddl/mg_delivery_by_hour.sql`

Com isso, **STG layer completa para MediaSmart e MGID (T1-T7)** e **Siprocal (T1-T4, sem granularidade extra na fonte)**.

---

## 2026-06-24 — T4 da STG criado (`ms_delivery`, `mg_delivery`, `sp_delivery`) — fatos diários, `client_id`/`formato`/`goal_type` denormalizados a pedido do usuário

**Autor:** Douglas Reche

### Decisão: quebrar o princípio "resolve uma vez só" pra `client_id` no T4

Design original (linhas anteriores deste changelog) estabeleceu que `client_id` ficaria resolvido só nas dimensões (T1/T2), sem repetir nos fatos de entrega (T4-T7) — evita duplicar lógica de join em 4 lugares. Nesta sessão, o usuário pediu explicitamente para trazer `client_id` em `stg.mg_delivery` e `stg.sp_delivery` (e já estava no plano original de `ms_delivery`). **Não é uma reabertura da resolução** — é puro `LEFT JOIN` com a dimensão já resolvida (`*_campaigns`), denormalização de conveniência pra evitar 2 hops em toda query de relatório.

### Achado — `raw.ms_delivery.client_id` é nome ambíguo

A coluna `client_id` em `raw.ms_delivery` na verdade contém o **Event ID** da MediaSmart (documentado no comentário do DDL original, `raw/ddl/ms_delivery.sql:24`), não o `client_id` resolvido (`core.dim_client`). Renomeado para `event_id` na STG, e o `client_id` real vem do join com `stg.ms_campaigns`.

### Achado — design original do MGID T4 estava errado sobre `campaign_id`

O design assumia que precisaria do join com `mg_teasers` pra resolver `campaign_id` em **todos** os Ts de delivery (T4-T7). Na prática, `raw.mg_delivery` (T4) **já tem `campaign_id` nativo** — o join via `mg_teasers` só é necessário no T5-T7 (onde o raw só tem `creative_id`). Corrigido no doc.

### Validação contra dado real

- **MS:** 6/938 (0,6%) `creative_id` na entrega não batem com `stg.ms_creatives` — confirmado que não existem mais em `raw.ms_creatives` (criativo rotacionado/removido do catálogo atual da API, mas a entrega histórica ainda referencia). Gap aceitável, `LEFT JOIN` preserva a linha.
- **`ctr` nulo** (MS: 6, MGID: 11, Siprocal: 1) — todos por `impressions=0` (divisão por zero). Siprocal inclusive tem o literal `#DIV/0!` na fonte, confirmando que é condição real dos dados, não bug introduzido.

### Implementação

**`stg.ms_delivery`** — grain `(date, campaign_id, creative_id)`. `event_id` renomeado de `client_id` (raw). `client_id, formato, goal_type` via join `ms_campaigns`. `ctr = SAFE_DIVIDE(clicks, impressions)`. **938/938, 937/938 com client_id/formato, 932/938 com ctr (gaps explicados acima).**

**`stg.mg_delivery`** — grain `(date, campaign_id, creative_id)`. `campaign_id` nativo (sem join `mg_teasers` — só necessário em T5-T7). `client_id, formato, goal_type` via join `mg_campaigns`. **157/157, 100% com client_id/formato, 146/157 com ctr (11 com impressions=0).**

**`stg.sp_delivery`** — grain `(date, campaign_id, criativo)`. Todo o parse de tipo acontece aqui (raw é dump literal STRING): `date` via `PARSE_DATE`, `impressions/clicks` via `SAFE_CAST INT64`. `ctr` **recalculado** (`clicks/impressions`), não parseado da string `"1,82%"` da fonte — corrigido após achar que tinha desviado de uma decisão já estabelecida no design original (RAW vem arredondada em 2 casas; confirmado contra dado real: 10/1120 linhas tinham diferença de precisão entre o valor da fonte e o recalculado). `client_id, formato, goal_type` via join `sp_campaigns`. **1121/1121, 100% com client_id/formato, 1120/1121 com ctr (1 com `#DIV/0!` na fonte).**

### Arquivos

- `stg/ddl/ms_delivery.sql`, `stg/ddl/mg_delivery.sql`, `stg/ddl/sp_delivery.sql` — criados e validados

---

## 2026-06-24 — T3 da STG criado (`ms_creatives`, `mg_teasers`)

**Autor:** Douglas Reche

T3 mais simples que T1/T2 — sem gap de identidade pra resolver, só passthrough + campo derivado. Sem `client_id` (princípio "resolve uma vez só" — quem precisar junta com `*_campaigns` pelo `campaign_id`).

**Achado pré-validação:** `CAST(FLOAT64 AS STRING)` no BigQuery já produz formato limpo sem `.0` quando não há fração (`120.0`→`"120"`) — testado contra dado real antes de assumir que precisaria de cast intermediário pra `INT64`. Criativos `native` (5 de 201) têm `width`/`height`=0 — esperado (native se adapta ao espaço, sem dimensão fixa), não é bug.

**`stg.ms_creatives`** — passthrough (`creative_id, campaign_id, creative_name, status, url, thumbnail_url, creative_type, width, height`) + `size` derivado (`CONCAT`). **201/201 validado.**

**`stg.mg_teasers`** — passthrough (`creative_id, campaign_id, creative_name, status, url, thumbnail_url, advert_text, call_to_action, width, height`) + `size='1280x720'` fixo (já fixo na RAW). **167/167 validado.**

### Arquivos

- `stg/ddl/ms_creatives.sql`, `stg/ddl/mg_teasers.sql` — criados e validados

---

## 2026-06-24 — T2 da STG criado (`ms_campaigns`, `mg_campaigns`, `sp_campaigns`) — `core.dict_format` criada + arquivos legados descobertos e arquivados

**Autor:** Douglas Reche

### Achado crítico — `stg/ddl/` não estava vazia (informação anterior incorreta)

Uma busca anterior (`Glob` com `path` relativo) retornou "nenhum arquivo encontrado" para `stg/ddl/*.sql`, levando à conclusão errada de que a pasta estava vazia (RAW rebuild "limpo"). Ao tentar criar `stg/ddl/ms_campaigns.sql` nesta sessão, o `Write` falhou com "arquivo já existe" — busca com caminho absoluto revelou **28 arquivos legados**, todos referenciando o schema anterior ao DROP de 18/06 (`raw.mediasmart_campaigns`, `raw.mediasmart_delivery`, `raw.mediasmart_daily`, `stg.ms_clients`, etc. — todos dropados, nenhum desses arquivos funcionaria se executado).

**Ação:** os 28 arquivos movidos para `stg/ddl/_legacy/` (com `README.md` explicando o contexto) — preserva histórico sem confundir com o schema vigente. Mantidos em `stg/ddl/`: os 4 arquivos criados nesta sessão (`ms_advertisers.sql`, `mg_advertisers.sql`, `sp_clients.sql`, `unresolved_client_links.sql`).

**Lição:** `Glob`/busca de arquivo com caminho relativo pode falhar silenciosamente sem erro — sempre confirmar com caminho absoluto antes de declarar "pasta vazia".

### `core.dict_format` criada — tabela que nunca existira de fato

Ao testar o T2, descobri que `core.dict_format` (referenciada desde o design original de 18/06 como lookup `formato × plataforma → goal_type`) **nunca foi criada** — só existia uma tabela diferente e não relacionada, `core.campaign_format_map` (18 linhas, piloto manual incompleto, só Banco Cora, criada em 03/06, anterior ao rebuild).

Discussão sobre se T2 realmente precisa de `goal_type` (classificação comercial) — confirmado pelo usuário: é regra de negócio já fechada com o comercial (mesma regra de 18/06), não uma incerteza. Criada `core.dict_format` com 7 linhas, valores em Title Case (`Display`, `Native`, `Push`, etc. — não caixa alta, mais legível; comparação no JOIN normalizada via `UPPER()` dos dois lados):

| formato | platform | goal_type |
|---|---|---|
| Display | mediasmart | CPM |
| Video | mediasmart | CPM |
| Retargeting | mediasmart | CPM |
| Native | mediasmart | CPC |
| Native | mgid | CPC |
| Push | mgid | CPC |
| Push | siprocal | CPC |

### Bug de parse `formato` na MS — posição não é fixa

Ao testar contra as 14 campanhas reais, `SPLIT(campaign_name,'_')[OFFSET(1)]` (2º segmento, padrão assumido `{CLIENTE}_{FORMATO}_{PAIS}_{PERIODO}`) extraiu `"CONTADIGITAL"` em vez de `"RETARGETING"` para `CORA_CONTADIGITAL_RETARGETING_JUNHO26` — a posição do formato **varia** (1 ou 2) dependendo de haver um segmento de "linha de produto" no meio (`CONTADIGITAL`, `POSGRADUACAO`).

**Fix:** buscar formato em **qualquer** segmento (não posição fixa), normalizando acentuação via `TRANSLATE()` (resolveu `EINSTEIN_POSGRADUACAO_VÍDEO_JUNHO26`, que falhava por "VÍDEO"≠"VIDEO"). Resultado: 12/14 campanhas resolvidas (de 11/14 com posição fixa). **2 sem formato, ambos esperados, não são bugs:** `LUCKBET_APOSTADORES_MAIO` (nome realmente não indica formato) e `Teste-Newad` (conta interna de teste).

### Bug de campo não mapeado na MGID — `campaign_type='rich_media'`

Primeira versão do `CASE WHEN` (campaign_type→formato) só tratava `push`/`product`/`content` — 13 campanhas com `campaign_type='rich_media'` (ex: Chammas, Pardini, Mopar) ficaram sem `formato`/`goal_type`. **Decisão do usuário:** tratar como `Native`/CPC (mesma classificação do product/content — variação de criativo dentro do mesmo modelo de cobrança). Resultado: **173/173 (100%)** com `formato`/`goal_type` na MGID.

### Implementação final

**`stg.ms_campaigns`** — herda `client_id` de `stg.ms_advertisers`; `formato` via busca em qualquer segmento + normalização de acento; `goal_type` via join `core.dict_format`. **14/14 campanhas, 13/14 com client_id, 12/14 com formato/goal_type.**

**`stg.mg_campaigns`** — herda `client_id` de `stg.mg_advertisers` (via `advertiser_name` extraído, mesma lógica do T1); `formato` derivado de `campaign_type` nativo (não parse de texto — `campaign_name` da MGID não tem padrão). **173/173 campanhas, 169/173 (97,7%) com client_id — só `CassinoPix` pendente —, 173/173 (100%) com formato/goal_type.**

**`stg.sp_campaigns`** — `campaign_id` = `campanha` (já é a chave); herda `client_id` de `stg.sp_clients`; `formato='Push'` fixo. **37/37 (100%) em tudo.**

### Arquivos

- `stg/ddl/ms_campaigns.sql`, `stg/ddl/mg_campaigns.sql`, `stg/ddl/sp_campaigns.sql` — criados e validados
- `stg/ddl/_legacy/` — 28 arquivos legados arquivados com `README.md`
- `core.dict_format` — tabela nova, 7 linhas

### Pendências

- [ ] `search_feed` (campaign_type MGID) — sem mapeamento de formato, baixo volume, avaliar quando aparecer
- [ ] `CassinoPix` (4 campanhas MGID) — ainda aguardando confirmação comercial (ver entrada anterior)

---

## 2026-06-24 — MS resolvido para 20/21 (95%) — 5 clientes novos cadastrados + bug de ambiguidade Pardini corrigido

**Autor:** Douglas Reche

### Contexto

Depois de criar `stg.ms_advertisers` (validado em 62%, 13/21), fui resolver os 8 gaps restantes um a um.

### Quick wins identificados e resolvidos

- **CALOR** → confirmado como duplicado/typo de **CALOI** na MediaSmart (mesmo domínio `www.caloi.com`, mesma categoria `IAB17-3`, `event_id` diferente). Vinculado ao mesmo `client_id` (`caloi_8ac28140`).
- **Pardini** → `client_id` já existia (`pardini_60395024`, usado por Siprocal/MGID), só faltava a linha de vínculo.

### Bug encontrado e corrigido: ambiguidade Pardini vs. Ocupacional não verificada antes de agir

Ao inserir o vínculo do Pardini, descobri que já existia uma linha **antiga** (`created_at: 2026-05-26`) pra esse mesmo `event_id`, deliberadamente deixada com `client_id = NULL, status = 'unresolved'`, com a nota: *"eventid compartilhado por Pardini e Ocupacional — aguardando esclarecimento"*. Não verifiquei histórico antes de inserir — fiquei com 2 linhas conflitantes pra mesma `link_value`. **Lição:** sempre checar se já existe uma linha (e seu motivo) antes de inserir vínculo novo em `platform_client_links`, mesmo quando a resposta "parece" óbvia.

**Resolução:** usuário confirmou que o `event_id` é de fato do Pardini (não Ocupacional) — linha antiga `unresolved` removida, mantida só a nova `active`.

**Pendência similar não resolvida:** CALOI original tem `status='pending_confirmation'` (não totalmente confirmado pelo comercial) — a linha do CALOR foi inserida como `active`, deveria ter o mesmo status do CALOI. Correção falhou por estar no streaming buffer do BigQuery (UPDATE/DELETE não suportado por ~90min após insert) — fica pendente de ajuste posterior.

### 5 clientes novos cadastrados oficialmente em `core.dim_client`

Confirmados pelo usuário como clientes reais. Um deles tinha ambiguidade de nome que precisou de confirmação: **"Trálálá"** (nome capturado com encoding quebrado na MediaSmart) tem domínio `loja.phisalia.com` — nome oficial confirmado pelo usuário: **Phisalia** (cliente já estava registrado como pendência na memória do projeto, "PHISALIA sem dim_client ainda" — gap fechado).

| client_id | name | sector |
|---|---|---|
| `cerpa_7315d130` | Cervejaria Cerpa | bebidas |
| `mastercard_ab2a13bc` | Mastercard | fintech |
| `parque_camelias_524ee5c2` | Parque das Camélias | unknown |
| `phisalia_2569c5d6` | Phisalia | unknown |
| `cassino_7k_393b3d2e` | Cassino 7K | apostas |

Todos com `client_level=1`, `parent_client_id=NULL`, `newad_account_id='newad_main'` (mesmo padrão dos clientes standalone existentes). `sector='unknown'` para os 2 sem classificação clara (mesmo padrão já usado em `senar_105bd174`/`fox_lux_55ed8992`).

Vínculos `platform_client_links` (MediaSmart, `link_type='eventid'`) criados para os 5.

### Resultado final

`stg.ms_advertisers`: **20/21 (95%)** resolvido. O único restante (`Newad`) é conta interna de teste, **intencionalmente sem vínculo** — não é gap real. MS está, na prática, 100% resolvido para clientes reais.

### Confirmação adicional do usuário

CALOR confirmado pelo usuário como sendo **a mesma entidade** de CALOI (não só hipótese de duplicado/typo). `client_id` do vínculo já está correto (`caloi_8ac28140`); só a nota textual segue desatualizada (ainda bloqueada pelo streaming buffer do BigQuery) — corrigir quando possível.

### Pendências

- [ ] Atualizar nota do vínculo CALOR (texto desatualizado, dado já está certo) quando o streaming buffer liberar
- [ ] Avaliar se as mesmas 5 marcas aparecem na MGID (ex: "Tralala", "Mastercard - Surpreenda", "Cervejaria Cerpa", "Parque das Camélias" já estavam na lista de 47 sem vínculo do MGID) e vincular lá também quando `stg.mg_advertisers` for criado
- [ ] Verificar se "Cassino\|7K" (MS) corresponde à mesma entidade de "CassinoPix" (MGID) antes de assumir — nomes parecidos mas não confirmados como o mesmo cliente

---

## 2026-06-24 — MGID sobe de 88,4% para 97,7% — bug de prefixo numérico corrigido + 5 clientes novos + CassinoPix pendente de confirmação comercial

**Autor:** Douglas Reche

### Bug adicional encontrado na extração — prefixo numérico

Verificação detalhada das 20 campanhas sem vínculo revelou que os grupos `"1"` (1 campanha) e `"2"` (1 campanha) eram **falsos** — vinham de `"1 - PARDINI PENSE LABORATORIALMENTE"` e `"2 - PARDINI PENSE LABORATORIALMENTE"` (numeração sequencial de variantes da mesma campanha Pardini, não um advertiser). A lógica de extração só tratava prefixos textuais genéricos (`Brand`/`New Ad`/`Push`), não numéricos.

**Fix:** adicionado `REGEXP_CONTAINS(parts[OFFSET(0)], r'^[0-9]+$')` à mesma condição de exceção — se o 1º segmento for puramente numérico, usa o 2º segmento. `"1"`/`"2"` desapareceram, substituídos corretamente por `"PARDINI PENSE LABORATORIALMENTE"` (2 campanhas, grupo único).

### Categorização final das 20 campanhas sem vínculo

Investigação campanha por campanha (não só por nome do grupo) antes de agir:

| Categoria | Grupos | Ação |
|---|---|---|
| Cliente já existe, só faltava vínculo | `PARDINI TELEMEDICINA`(3), `PARDINI PENSE LABORATORIALMENTE`(2), `APERAM`(1, variante de capitalização) | Vinculados a `pardini_60395024`/`aperam_14d1f27e` — sem ID novo |
| Cliente novo confirmado pelo usuário | `Rino Imoveis`(3), `Chammas`(3), `Boa Vista`(2), `Infinity Bet`(1), `São Martinho`(1) | 5 `client_id` novos criados em `core.dim_client` |
| Pendente confirmação comercial | `CassinoPix`(4) | **Não criado** — usuário pediu para registrar e confirmar com comercial antes (pode ser o mesmo "Cassino 7K" já criado na MS, ou cliente diferente) |

### 5 clientes novos cadastrados

| client_id | name | sector |
|---|---|---|
| `rino_imoveis_eebf5c60` | Rino Imoveis | imobiliario |
| `chammas_9f4f2339` | Chammas | unknown |
| `boa_vista_bce18edd` | Boa Vista | unknown |
| `infinity_bet_a0ec00f4` | Infinity Bet | apostas |
| `sao_martinho_a52ce862` | Sao Martinho | unknown |

Checagem de segurança aplicada antes de inserir (lição do incidente Pardini/Ocupacional) — confirmado vazio pra todos os `campaign_id` antes de criar vínculo.

### Resultado final

`stg.mg_advertisers`: **38/39 grupos (97,4%)**, **169/173 campanhas (97,7%)** resolvidas. Único grupo pendente: `CassinoPix` (4 campanhas) — aguardando confirmação comercial se é o mesmo cliente de "Cassino 7K" (MediaSmart) ou entidade separada.

### Pendências

- [ ] Confirmar com o comercial: `CassinoPix` (MGID) é o mesmo cliente de `Cassino 7K` (MS, `cassino_7k_393b3d2e`) ou diferente?

---

## 2026-06-24 — `stg.mg_advertisers` criado em produção — MGID sobe de 73% para 88,4% de resolução

**Autor:** Douglas Reche

### Contexto

Depois de fechar o MS (95%, 5 clientes novos cadastrados), criei o `stg.mg_advertisers` de fato — view planejada na entrada anterior, implementação e teste contra dado real nesta entrada.

### Estratégia de resolução — herdar de qualquer campanha já vinculada no grupo

Em vez de exigir vínculo novo por `advertiser_name` extraído, a view junta cada campanha individual com `core.platform_client_links` (pelas 130+ linhas `campaignid` já existentes) e agrupa por `advertiser_name` — se **qualquer** campanha do grupo já tiver vínculo individual, o grupo inteiro herda esse `client_id`. Testado: **25/40 grupos resolvidos automaticamente**, **zero conflitos** (nenhum grupo com 2 `client_id` diferentes — confirma que a extração agrupa corretamente o mesmo cliente real).

**Validação extra:** confirma que `Laboratorio Pardini`, `Pardini Anatomia`, `Pardini`, `Pardini Podcast` são todos o **mesmo cliente** (`pardini_60395024`) — pergunta que tinha ficado pendente na sessão anterior, respondida automaticamente pelos vínculos individuais já existentes.

### Aproveitamento dos clientes recém-cadastrados (MS) — 5 vínculos novos na MGID

Os 4 clientes criados no fechamento do MS (`Cerpa`, `Mastercard`, `Parque das Camélias`, `Phisalia`) também aparecem na MGID. Adicionei **1 vínculo de campanha representativo por grupo** (não por cliente todo) — suficiente pra resolver o grupo inteiro via a lógica de herança:

| Grupo MGID | `campaign_id` vinculado | `client_id` |
|---|---|---|
| Cervejaria Cerpa | `12106889` | `cerpa_7315d130` |
| Cerpa | `11873953` | `cerpa_7315d130` (mesmo cliente, grupo de extração separado) |
| Mastercard | `12311826` | `mastercard_ab2a13bc` |
| Parque das Camélias | `12121360` | `parque_camelias_524ee5c2` |
| Tralala | `12090393` | `phisalia_2569c5d6` (confirmado: "Tralala" é o mesmo nome informal usado nas duas plataformas pra Phisalia) |

**Checagem de segurança aplicada** (lição do incidente Pardini/Ocupacional, registrada na entrada anterior): consultei se já existia vínculo pra esses 5 `campaign_id` antes de inserir — confirmado vazio, inserção segura.

### Resultado

`stg.mg_advertisers`: **30/40 grupos (75%)** resolvidos, **153/173 campanhas (88,4%)** resolvidas em nível de campanha — subiu de 73% (126/173, vínculo por campanha individual) pra 88,4%, sem alterar nenhuma das 130 linhas antigas.

**10 grupos ainda sem vínculo (20 campanhas, não 38 — corrigido em 2026-06-24 após segunda verificação):** `CassinoPix`(4), `Rino Imoveis`(3), `Chammas`(3), `PARDINI TELEMEDICINA`(3), `Boa Vista`(2), `APERAM`(1, variante de capitalização de `Aperam`, já resolvido), `Infinity Bet`(1), `São Martinho`(1), e 2 campanhas com nome só numérico (`"1"`, `"2"` — provavelmente teste/erro de cadastro). **Verificação adicional confirmou:** soma exata 173 campanhas (153 resolvidas + 20 sem vínculo), zero campanhas em mais de 1 grupo, zero campanhas perdidas — números corretos, só o texto original tinha erro de soma.

### Pendências

- [ ] `PARDINI TELEMEDICINA` (3 campanhas) — forte indício de ser o mesmo `pardini_60395024` (mesma família de variantes já confirmadas), mas nenhuma campanha individual vinculada ainda — confirmar e linkar
- [ ] `CassinoPix` — ainda não confirmado se é a mesma entidade de `Cassino 7K` (MS, já cadastrado) — não assumir sem confirmação
- [ ] `Rino Imoveis`, `Chammas`, `Boa Vista`, `Infinity Bet` — clientes novos (dos 9 originais), ainda não cadastrados em `core.dim_client` nem na MS nem na MGID
- [ ] Investigar as 2 campanhas com nome puramente numérico (`"1"`, `"2"` — possível erro de cadastro/teste)

### Arquivos criados

- `stg/ddl/mg_advertisers.sql` (criado e validado em produção)

---

## 2026-06-24 — `stg.mg_advertisers` (extração de advertiser) + `stg.sp_clients` criados — princípio "resolve uma vez só"

**Autor:** Douglas Reche

### Contexto

Discussão sobre por que a MGID tem taxa de vínculo tão baixa (73%) levou a uma pergunta melhor: em vez de aceitar o vínculo por campanha (sempre vai crescer 1:1 com campanhas novas), por que não extrair o nome do advertiser do `campaign_name` e vincular por esse texto extraído — replicando o padrão já comprovado da MS (`eventid`) e Siprocal (`advertiser`)?

### Teste da extração — 173 campanhas → 40 valores distintos

Primeira tentativa (1º segmento de `campaign_name`, separado por `|`/`-`): **bug encontrado** — `"Brand | Amigo | Push | ..."` extraía `"Brand"` (53 campanhas, 31% do total) em vez de `"Amigo"` (correto). Mesmo problema com prefixo `"New Ad - ..."`.

**Fix:** se o 1º segmento for um prefixo genérico conhecido (`Brand`, `New Ad`/`NewAd`, `Push`), usar o 2º segmento. Resultado: `"Amigo"` passou a agrupar corretamente 41 campanhas, `"Boa Vista"` apareceu (2, antes escondido sob "New Ad"). **173 campanhas → 40 valores distintos** — toda campanha nova de advertiser já conhecido resolve automaticamente, sem vínculo manual novo.

**Variações de grafia remanescentes** (mesmo advertiser, texto diferente — decisão comercial, não resolvido automaticamente): `Laboratorio Pardini` / `Pardini Anatomia` / `PARDINI TELEMEDICINA` / `Pardini` / `Pardini Podcast`; `Dr Consulta` / `Dr Consulta RJ`; `APERAM` / `Aperam` (capitalização).

### Decisão de arquitetura: onde resolver `client_id`, e quantas vezes

Duas perguntas resolvidas:

1. **Isso quebra o uso atual de `platform_client_links`?** Não — `link_type` já é uma coluna extensível por design (`eventid`/`campaignid`/`advertiser` já convivem na mesma tabela). Adicionamos um novo `link_type` (`advertiser_name`) pra MGID, sem remover as 130 linhas `campaignid` existentes. Confirmado (busca no código): `platform_client_links` não tem nenhum consumidor externo hoje, só os comentários do nosso próprio código — seguro de estender.

2. **`client_id` é resolvido em cada T de delivery ou uma vez só?** **Uma vez só, na dimensão** — princípio star-schema padrão. `stg.mg_advertisers`/`stg.mg_campaigns` resolvem `client_id`; `stg.mg_delivery*` (T4-T7) carregam só `campaign_id`/`creative_id` nativos, sem repetir o join com `platform_client_links`. Evita duplicar a mesma lógica em 4 lugares — qualquer ajuste futuro de vínculo é feito num ponto só.

```
stg.mg_advertisers  (resolve client_id AQUI)
       ↑
stg.mg_campaigns    (herda, não resolve de novo)
       ↑
stg.mg_delivery / by_geo / by_device / by_hour  (só campaign_id/creative_id nativos)
```

Mesmo princípio aplicado à Siprocal (`stg.sp_clients` → `stg.sp_delivery`), embora lá já estivesse 100% resolvido — formaliza o padrão antes consistente só "dentro" do `sp_delivery`.

### Implementação

**`stg/ddl/mg_advertisers.sql`** (plano registrado em `stg_layer_design.md`, implementação ainda pendente de criação no BQ — fica para o próximo passo) — grain: 1 linha por `advertiser_name` extraído/deduplicado, com `campaign_count`, `first_campaign_id`, `client_id`.

**`stg/ddl/sp_clients.sql`** ✅ **criado e validado em produção:**
```sql
CREATE OR REPLACE VIEW `adframework.stg.sp_clients` AS
WITH extracted AS (
  SELECT SPLIT(campanha, '_')[OFFSET(1)] AS client_name
  FROM `adframework.raw.sp_delivery`
)
SELECT e.client_name, COUNT(*) AS campaign_count, pcl.client_id
FROM extracted e
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON pcl.link_value = e.client_name AND LOWER(pcl.platform) = 'siprocal'
GROUP BY e.client_name, pcl.client_id;
```
**Resultado:** 11/11 (100%) resolvidos — `AMIGOTECPAR, APERAM, BANCOCORA, CATALISE, DOOING, DRCONSULTA, LUCKBET, PARDINI, PATIOMEDEIROS, SENAR, TECPAR`, todos com `client_id` e `campaign_count` (volume real de linhas por cliente, de 3 a 313).

### Pendências

- [ ] Criar `stg.mg_advertisers` no BigQuery (DDL ainda só no plano, não implementado)
- [ ] Decidir as 3 variações de grafia pendentes (Pardini, Dr Consulta) com o comercial
- [ ] Adicionar as primeiras linhas de `link_type='advertiser_name'` em `platform_client_links` pra MGID
- [ ] T1 MS (`stg.ms_advertisers`) ainda com 2 decisões em aberto (campo `id`, tratamento de `sensitive_content`) — retomar

### Arquivos criados/atualizados

- `stg/ddl/sp_clients.sql` (criado e validado)
- `docs/stg_layer_design.md` (seção MGID reescrita com o princípio "resolve uma vez só"; seção Siprocal atualizada com `sp_clients`)

---

## 2026-06-24 — Árvore de vinculação client_id verificada + view de monitoramento `stg.unresolved_client_links`

**Autor:** Douglas Reche

### Contexto

Ao planejar o T1 da STG, fui verificar com dado real se `core.platform_client_links` cobre todas as entidades das 3 plataformas — e descobri que a taxa de resolução varia muito: **Siprocal 100%, MGID 73%, MediaSmart 62%**. Investigação completa do porquê, e desenho de um mecanismo de manutenção.

### Por que a taxa varia tanto

| Plataforma | `link_type` | Nível de vínculo | Taxa real |
|---|---|---|---|
| Siprocal | `advertiser` | Por cliente (texto parseado do nome da campanha) | **100% (11/11)** |
| MediaSmart | `eventid` | Por advertiser nativo (`ms_advertisers.event_id`) | 62% (13/21) |
| MGID | `campaignid` | Por campanha individual | 73% (126/173) |

**MediaSmart e Siprocal já vinculam no nível certo (advertiser/cliente)** — uma vez vinculado, toda campanha passada e futura daquele advertiser resolve automaticamente (FK nativa `ms_campaigns.client_id = event_id`, ou nome parseado compartilhado entre campanhas da Siprocal). Os gaps de 38%/0% são atraso operacional pontual — `Pardini` (MS) já tem `dim_client`, só faltou vincular essa conta específica.

**MGID é forçada ao nível de campanha porque não existe entidade "advertiser" na API.** Reconfirmado exaustivamente nesta sessão: testei o endpoint de campanha **individual** (`GET /v1/goodhits/clients/{id}/campaigns/{campaign_id}`, diferente do endpoint de lista já testado em sessão anterior), inclusive pedindo `advertiserName` explicitamente via `fields=['id','name','advertiserName','category']` — mesmo resultado: a API aceita o parâmetro mas descarta o campo silenciosamente, sem erro. **Não existe, em nenhuma forma testada, um ID de advertiser nativo na MGID.** Por isso cada campanha nova precisa de uma linha nova em `platform_client_links` — não há nível superior do qual herdar o vínculo.

### Achado: 9 clientes reais nunca cadastrados em `core.dim_client`

Cruzando os nomes nativos sem vínculo (MS + MGID) contra `core.dim_client`, confirmei que 9 clientes — `Cerpa`, `Mastercard`, `Parque das Camélias`, `Tralala`, `Cassino|7K`/`CassinoPix`, `Boa Vista`, `Chammas`, `Infinity Bet`, `Rino Imóveis` — **não têm nenhum registro em `core.dim_client`**, em nenhuma das duas plataformas onde aparecem. Não é falta de vínculo — é falta de cadastro completo (cliente nunca foi onboardado no `core`). `Newad` (MS) é conta interna de teste, não cliente real.

### Solução: `stg.unresolved_client_links` — view de monitoramento

Como a MGID não tem solução de automação possível (confirmado acima), a saída é uma **view de monitoramento** que lista, pra cada plataforma, toda entidade sem vínculo — funciona como checklist contínuo, sem necessidade de auditoria manual recorrente.

**`stg/ddl/unresolved_client_links.sql`:**
```sql
CREATE OR REPLACE VIEW `adframework.stg.unresolved_client_links` AS
WITH unresolved AS (
  -- MediaSmart: event_id sem vinculo
  SELECT 'mediasmart' AS platform, 'eventid' AS link_type_expected,
         a.event_id AS native_id, a.name AS native_name,
         NULL AS category_or_status, a.name AS name_for_match
  FROM `adframework.raw.ms_advertisers` a
  LEFT JOIN `adframework.core.platform_client_links` pcl
    ON pcl.link_value = a.event_id AND LOWER(pcl.platform) = 'mediasmart'
  WHERE pcl.client_id IS NULL
  UNION ALL
  -- MGID: campaign_id sem vinculo -- sem ID nativo de advertiser, usa 1o segmento do nome
  SELECT 'mgid' AS platform, 'campaignid' AS link_type_expected,
         mc.campaign_id AS native_id, mc.campaign_name AS native_name,
         mc.status_name AS category_or_status,
         TRIM(SPLIT(REPLACE(mc.campaign_name, '-', '|'), '|')[OFFSET(0)]) AS name_for_match
  FROM `adframework.raw.mg_campaigns` mc
  LEFT JOIN `adframework.core.platform_client_links` pcl
    ON pcl.link_value = mc.campaign_id AND LOWER(pcl.platform) = 'mgid'
  WHERE pcl.client_id IS NULL
  UNION ALL
  -- Siprocal: client_name parseado, sem vinculo
  SELECT 'siprocal' AS platform, 'advertiser' AS link_type_expected,
         client_name_parsed AS native_id, client_name_parsed AS native_name,
         NULL AS category_or_status, client_name_parsed AS name_for_match
  FROM (SELECT DISTINCT SPLIT(campanha, '_')[OFFSET(1)] AS client_name_parsed FROM `adframework.raw.sp_delivery`) sp
  LEFT JOIN `adframework.core.platform_client_links` pcl
    ON pcl.link_value = sp.client_name_parsed AND LOWER(pcl.platform) = 'siprocal'
  WHERE pcl.client_id IS NULL
)
SELECT u.platform, u.link_type_expected, u.native_id, u.native_name, u.category_or_status,
  (SELECT STRING_AGG(DISTINCT dc.client_id) FROM `adframework.core.dim_client` dc
   WHERE LENGTH(TRIM(u.name_for_match)) >= 4
     AND NOT REGEXP_CONTAINS(TRIM(u.name_for_match), r'^[0-9\s]+$')
     AND (LOWER(dc.name) LIKE CONCAT('%', LOWER(u.name_for_match), '%')
          OR LOWER(u.name_for_match) LIKE CONCAT('%', LOWER(dc.name), '%'))
  ) AS suggested_client_id
FROM unresolved u;
```

**Coluna `suggested_client_id`:** fuzzy-match de texto (não é vínculo automático, só sugestão pra acelerar revisão manual). Pra MGID, usa o 1º segmento do `campaign_name` (antes de `|`/`-`) como aproximação do advertiser.

**Bug encontrado e corrigido durante o teste:** primeira versão sugeriu `lab2lab_efb1cb34` pra campanha `"2 - PARDINI PENSE LABORATORIALMENTE"` — o split extraiu só o número `"2"` (prefixo de numeração sequencial, não nome de advertiser), que bateu por coincidência com "Lab**2**Lab". Corrigido com guarda `LENGTH(TRIM(...)) >= 4` + `NOT REGEXP_CONTAINS(..., r'^[0-9\s]+$')` (rejeita segmentos curtos ou puramente numéricos).

**Resultado validado:** 55 linhas sem vínculo (8 MediaSmart + 47 MGID + 0 Siprocal). Sugestões corretas para `Pardini`, `Banco Cora`, `Aperam`, `Senar`, `Pardini Telemedicina`. Sem sugestão (corretamente) para os 9 clientes não cadastrados + `Newad` (conta interna).

### Pendências

- [ ] Comercial: cadastrar os 9 clientes faltantes em `core.dim_client` + vincular em `platform_client_links`
- [ ] Comercial: completar vínculo de `Pardini` (MS) e das campanhas atrasadas de `Banco Cora`/`Amigo`/`Aperam` (MGID) — clientes já cadastrados, só falta a linha de vínculo
- [ ] Confirmar se "Pardini Telemedicina" é o mesmo client_id de "Pardini" ou uma conta separada do grupo
- [ ] Avaliar se vale promover a view para alerta automático (Slack/Notion) — discutido, não decidido nesta sessão

### Arquivos criados

- `stg/ddl/unresolved_client_links.sql`
- `docs/stg_layer_design.md` atualizado com a investigação completa

---

## 2026-06-24 — Auditoria de schema RAW (14 tabelas) + fix `ms_advertisers`

**Autor:** Douglas Reche

### Contexto

Antes de avançar pra STG, ao desenhar `stg.ms_advertisers` percebi que `raw.ms_advertisers` não tinha as colunas `platform`/`raw_ingested_at` que a DDL documentada (`raw/ddl/ms_advertisers.sql`) declarava. Isso disparou uma auditoria completa: comparar **schema real no BigQuery vs. DDL documentada**, campo a campo e tipo a tipo, nas 14 tabelas RAW.

### Metodologia

Script comparando `(nome, tipo)` de cada DDL contra `bq.get_table().schema` real. Primeira passada apontou "discrepância" em 13/14 tabelas — falso-positivo: o cliente Python do BigQuery retorna nomes de tipo legados (`FLOAT`, `INTEGER`, `BOOLEAN`) enquanto a DDL usa nomes SQL padrão (`FLOAT64`, `INT64`, `BOOL`) — são os mesmos tipos, só nomenclatura diferente. Normalizando os aliases, restou **1 discrepância real**.

### Resultado: 13/14 tabelas batem perfeitamente, 1 com gap real

**`raw.ms_advertisers` — faltavam `platform` e `raw_ingested_at`.** Causa: foi a primeira tabela criada na sessão (18/06), antes da disciplina de criação via DDL completa ter sido padronizada — o schema real ficou só com 6 dos 8 campos planejados. Como `BigQueryService.load_data()` descarta silenciosamente colunas desconhecidas em relação ao schema já existente, todo `WRITE_TRUNCATE` desde então vinha jogando fora essas duas colunas sem erro — o dado de negócio (`event_id, name, iab_category, domain, sensitive_content`) estava intacto.

**Fix:** `ALTER TABLE ... ADD COLUMN IF NOT EXISTS platform STRING, ADD COLUMN IF NOT EXISTS raw_ingested_at TIMESTAMP` (preserva as 21 linhas existentes) + reprocessamento do job (`mediasmart_firstlevel:advertisers`) pra popular as colunas novas. Validado: 21/21 linhas com `platform`/`raw_ingested_at` preenchidos, 0 nulos.

### Achado secundário — 2 comentários de DDL desatualizados (não afetam schema/dados)

- `raw/ddl/ms_creatives.sql` — cabeçalho ainda citava o endpoint antigo e incorreto (`/api/campaign/{id}/creatives`) como fonte; corrigido para descrever a fonte real (`strategies[].creatives.campaign_creatives[]`) e linkar a investigação do gap de join já resolvida
- `raw/ddl/ms_delivery.sql` — nota ainda dizia "join NÃO FUNCIONA"; corrigido para refletir a resolução (729/735, 99,2%) na mesma sessão de 22/06

### Resultado final

**14/14 tabelas RAW com schema real idêntico ao planejado e documentado.** Auditoria de integridade (executada antes desta, mesma sessão) já havia confirmado 0 nulos em PK/FK e joins ≥99,3% — combinado com esta auditoria de schema, a RAW está confirmada como íntegra e fiel ao design antes de qualquer trabalho de STG.

---

## 2026-06-24 — Plano da camada STG criado (`stg_layer_design.md`)

**Autor:** Douglas Reche

Auditoria completa da RAW executada antes de avançar (4 verificações: contagem/atualização, nulos em PK/FK, integridade de joins, duplicatas — 0 problemas em 14 tabelas). Com a RAW confirmada íntegra, criei `docs/stg_layer_design.md` consolidando todos os gaps e decisões já registrados no CHANGELOG ao longo da implementação RAW em um plano único de STG — mesma disciplina usada na RAW (princípios → mapeamento tabela a tabela → sequência de implementação → pendências).

**Decisões principais do plano:**
- STG = views sobre a RAW (não tabelas materializadas) — RAW já persiste o fato, recalcular é mais simples que duplicar storage
- Nomenclatura espelha a RAW (`stg.ms_campaigns`, `stg.mg_delivery`, etc.)
- `ctr` sempre derivado na STG, nunca confiar no valor de origem (já decidido na RAW)
- MGID: `client_id` resolvido via `campaign_id → core.platform_client_links → client_id`; `campaign_id` em `mg_delivery*` resolvido via `creative_id → mg_teasers → campaign_id` (join em cadeia)
- MGID: `formato` derivado de `campaign_type` (push/product/content), não do nome da campanha (que é texto livre na MGID, diferente da MS)
- Siprocal: toda a normalização que a RAW propositalmente não fez (decisão de 22/06) acontece aqui — parse de data, cast numérico, parse de `%`, derivação de `client_name`

**3 pendências que precisam de decisão antes de implementar:**
1. Mapeamento `campaign_type → formato` da MGID não está confirmado com o comercial — é inferência
2. Decidir se `client_id` nulo da MGID (27% das campanhas sem vínculo) aparece como `NULL` na STG ou é filtrado
3. Confirmar se Siprocal precisa de uma tabela de vínculo cliente equivalente ao `platform_client_links`, ou se `client_name` (texto) basta para o gold

### Arquivos criados

- `docs/stg_layer_design.md` — plano completo da STG

---

## 2026-06-24 — Consolidação de jobs + DROP final das 19 tabelas órfãs — rebuild T1-T7 encerrado

**Autor:** Douglas Reche

### Contexto

Com T1-T7 validados nas duas plataformas, revisei todos os jobs Firestore (`platform_reports`) para: (1) confirmar que os jobs de produção apontam pras tabelas novas (não só os jobs de teste `_t5`/`_t6`/`_t7` criados durante a validação), e (2) identificar e dropar as tabelas antigas órfãs.

### Achado — duplicação de jobs ativos para T5/T6/T7

Diferente do T4 (onde redirecionei o job de produção direto), para T5/T6/T7 eu tinha criado jobs **novos** (`mediasmart_delivery_by_geo_t5`, etc.) em paralelo aos jobs de produção antigos (`mediasmart_delivery_by_geo`, `mgid_stats_by_geo`, etc.) — e os dois ficaram **habilitados simultaneamente**. Os antigos continuavam recriando tabelas fantasma todos os dias.

**Fix:** redirecionei os 6 jobs de produção (3 MS + 3 MGID) para as tabelas novas e desabilitei os 6 jobs `_t5`/`_t6`/`_t7` temporários (agora redundantes):

| Job de produção | Redirecionado para | Job temporário desabilitado |
|---|---|---|
| `mediasmart_delivery_by_geo` | `ms_delivery_by_geo` | `mediasmart_delivery_by_geo_t5` |
| `mediasmart_delivery_by_device` | `ms_delivery_by_device` | `mediasmart_delivery_by_device_t6` |
| `mediasmart_delivery_by_hour` | `ms_delivery_by_hour` | `mediasmart_delivery_by_hour_t7` |
| `mgid_stats_by_geo` | `mg_delivery_by_geo` | `mgid_delivery_by_geo_t5` |
| `mgid_stats_by_device` | `mg_delivery_by_device` | `mgid_delivery_by_device_t6` |
| `mgid_stats_by_hour` | `mg_delivery_by_hour` | `mgid_delivery_by_hour_t7` |

Testados todos os 6 após o redirecionamento — `"No new dates to load"` em todos, confirmando que `get_max_date()` resolveu corretamente contra as tabelas novas (já populadas pelo backfill de teste).

### Decisões de escopo — 3 jobs ativos que não eram redundantes, mas saíram do escopo

Antes do DROP, encontrei 3 jobs ativos que **não tinham equivalente em nenhuma tabela nova** — não eram duplicação, capturavam dados genuinamente fora do escopo T1-T7:

- **`mediasmart_creative_daily`** — drilldown com `source` (exchange) e `convsource` (atribuição clique vs impressão), nenhum dos dois capturado pelas tabelas novas
- **`mediasmart_revenue_daily`** — métrica `clientrevenue` (financeiro) — T1-T7 nunca incluiu campos de receita/custo
- **`mgid_stats_by_os`** — `dimensions=day,campaignId,os` (OS no nível de campanha, que cabe nas 3 dimensões — diferente do nível de criativo que descartamos no T6) + métricas financeiras (`spent,revenue,profit,roas`)

**Decisão do usuário:** revenue/financeiro está fora do escopo do projeto por agora — os 3 jobs foram **desabilitados** (não substituídos por uma tabela nova). Se o escopo financeiro voltar no futuro, será um T8 novo, desenhado do zero.

**Nota sobre `convsource`:** não documentado em detalhe na doc oficial (só "Conversion source"). Confirmado pelos dados reais: valores observados são `"click"` e `"impression"` — é o modelo de atribuição da conversão (atribuída ao último clique vs. atribuída por visualização/view-through), conceito padrão de ad-tech.

### DROP final — 19 tabelas órfãs removidas

Double-check programático antes do DROP (4 verificações automatizadas): sem overlap entre lista de DROP e lista de tabelas mantidas; todas as 19 existem no BQ; nenhuma das 19 tinha job habilitado ainda apontando pra ela; todas as tabelas reais do dataset estavam classificadas em uma das duas listas (nenhuma esquecida).

**Dropadas (19):**
```
mediasmart_campaigns, mediasmart_daily, mediasmart_delivery_by_device,
mediasmart_delivery_by_geo, mediasmart_delivery_by_hour, mediasmart_delivery_by_os,
mediasmart_delivery_by_publisher, mgid_campaigns, mgid_creatives, mgid_daily,
mgid_stats_by_browser, mgid_stats_by_device, mgid_stats_by_geo, mgid_stats_by_hour,
mgid_stats_by_widget, siprocal_delivery, mediasmart_creative_daily,
mediasmart_revenue_daily, mgid_stats_by_os
```

**Preservadas (15):** `io_plan_drive_snapshot` (sistema diferente, Google Drive) + as 14 tabelas novas do rebuild (`ms_advertisers, ms_campaigns, ms_creatives, ms_delivery, ms_delivery_by_geo, ms_delivery_by_device, ms_delivery_by_hour, mg_campaigns, mg_teasers, mg_delivery, mg_delivery_by_geo, mg_delivery_by_device, mg_delivery_by_hour, sp_delivery`).

### Estado final de `raw.*`

15 tabelas — confirmado via `bq.list_tables()` após o DROP, bate exatamente com a lista esperada.

### Pendências

- [ ] T8 (financeiro/revenue) — desenho novo, do zero, se o escopo for retomado no futuro
- [ ] Revisar `mgid_stats_creative`/`mgid_stats_daily` (ainda ativos, baixo volume, sem classificação clara) — não tocados nesta sessão
- [ ] Seguir para a camada STG — boa parte dos joins/resoluções já está documentada ao longo do CHANGELOG (client_id MGID via platform_client_links, campaign_id via mg_teasers, formato via nome de campanha, etc.)

---

## 2026-06-24 — T7 by-hour implementado — sem novos limites, hora vem como string na MS

**Autor:** Douglas Reche

### Contexto

T7 (entrega por hora). Grain definido em `raw_layer_design.md`: `T4 + hour`. Diferente de T5/T6, esse T **não bateu em nenhum limite novo** — apenas 1 dimensão extra (`hour`), então MGID coube perfeitamente em `day+teaserId+hour` (3 dimensões, exatamente no limite).

### Achado — `hour` vem como string `"HH:00"` na MediaSmart, não inteiro

O design assumia `hour: 0-23 UTC` direto. Testando, a API retorna a coluna `"Hour"` como string formatada (`"00:00"`, `"23:00"`), não um inteiro. Extraído na ingestão: `df["hour"].astype(str).str.slice(0, 2).astype(int)`.

**MGID já retorna `hour` como inteiro nativo** (0-23) — sem parse necessário.

### Implementação

**DDLs** (particionadas por `date`, `hour` como INT64 — seguro porque é dimensão de agrupamento, sempre presente em toda linha, nunca nulo): `raw/ddl/ms_delivery_by_hour.sql`, `raw/ddl/mg_delivery_by_hour.sql` (sem `campaign_id`, mesmo padrão T5/T6 — resolvido via join com `mg_teasers` na STG).

**Connectors:**
- `connectors/mediasmart.py` → `fetch_delivery_by_hour_normalized(date)` — drilldown `day,eventid,controlid,creativeid,hour`, com parse de `hour`
- `connectors/mgid.py` → `fetch_delivery_by_hour_normalized(date)` — `dimensions=day,teaserId,hour`

**Dispatch:** mais duas entradas no dict `normalized_methods` (`ms_delivery_by_hour`, `mg_delivery_by_hour`).

**Jobs Firestore novos:** `mediasmart_delivery_by_hour_t7` (job `mediasmart_daily:delivery_by_hour_t7`), `mgid_delivery_by_hour_t7` (job `mgid_daily:delivery_by_hour_t7`) — backfill inicial `2026-06-12`.

### Resultado validado em produção

- `adframework-etl-00274-ntf`
- `ms_delivery_by_hour`: **18.660 linhas** — `hour` no range 0-23, 0 nulos. Join `creative_id` ↔ `ms_creatives`: 18.616/18.660 (99,76% — gap residual já conhecido de campanhas/criativos históricos)
- `mg_delivery_by_hour`: 1.346 linhas — `hour` 0-23, 0 nulos. Join `creative_id` ↔ `mg_teasers`: **100%**

### Pendências

- [ ] T8+ — verificar se os breakdowns restantes do design (`by_publisher`, `by_audience`, `by_connection`, `by_browser`) ainda fazem sentido ou foram descartados — checar `raw_layer_design.md` seção "Breakdowns descartados"

---

## 2026-06-24 — T6 by-device implementado — limite de 3 dimensões MGID impede device+OS juntos

**Autor:** Douglas Reche

### Contexto

T6 (entrega por device + OS). Grain definido em `raw_layer_design.md`: `T4 + device_type + operating_system`, com nota explícita: *"OS é dimensão separada na API [MGID] — injetar junto com device na mesma tabela."* Essa nota se mostrou impossível de cumprir.

### Descoberta — MGID nunca cabe device + OS juntos, independente da entidade usada

Diferente do T5 (onde trocar `campaignId` por `teaserId` resolvia o limite de 3 dimensões), aqui o problema é mais grave: `day + entidade + device + os` são **sempre 4 dimensões**, não importa se a entidade é `campaignId` ou `teaserId`. Testei `day+teaserId+device+os` — rejeitado (`400 Bad Request`). Não há combinação de 3 dimensões que inclua device E os ao mesmo tempo junto com day e uma entidade de atribuição.

**Decisão validada com o usuário:** ingerir só `device_type` por agora. `operating_system` fica de fora da MGID até surgir necessidade analítica real — não vale a pena criar uma tabela separada `mg_delivery_by_os` sem um caso de uso definido (e ainda assim ela nunca poderia ser combinada com `by_device` na STG sem risco de fan-out, mesma lógica do T5).

### Bug de nome de campo (mesma classe do `regioncode`/`creaid` do T5)

Testei dimensão `device` (lowercase, intuitivo) — API rejeitou: `{"errors":{"dimensions[1]":["The value you selected is not a valid choice."]}}`. Testei `deviceType` (camelCase, padrão já visto em `campaignId`/`teaserId`) — funcionou. Mais uma confirmação de que **nomes de dimensão da MGID exigem teste empírico, nunca assumir por analogia.**

### MS — sem limite de dimensões, mas nome de campo errado na primeira tentativa

Testei `osfamily` (assumido por analogia com `countrycode`) — erro genérico e confuso (`"Provided drilldown variable is wrong: regioncode"`, mencionando um campo que nem estava na chamada — sugere cache ou validação em cascata da API). Busquei a doc oficial: campo correto é `os` (sem sufixo). Com `day,eventid,controlid,creativeid,devicetype,os` (6 dimensões) funcionou sem problema — MediaSmart não tem limite de dimensões como a MGID.

### Implementação

**DDLs** (particionadas por `date`): `raw/ddl/ms_delivery_by_device.sql` (14 campos, device_type + operating_system juntos), `raw/ddl/mg_delivery_by_device.sql` (9 campos, só device_type, sem OS/campaign_id).

**Connectors:**
- `connectors/mediasmart.py` → `fetch_delivery_by_device_normalized(date)` — drilldown `day,eventid,controlid,creativeid,devicetype,os`
- `connectors/mgid.py` → `fetch_delivery_by_device_normalized(date)` — `dimensions=day,teaserId,deviceType`

**Dispatch:** estendido o dict `normalized_methods` em `_run_mediasmart_daily()`/`_run_mgid_daily()` com mais uma entrada cada (`ms_delivery_by_device`, `mg_delivery_by_device`) — sem alterar a estrutura do dispatch, só adicionar ao mapeamento.

**Jobs Firestore novos:** `mediasmart_delivery_by_device_t6` (job `mediasmart_daily:delivery_by_device_t6`), `mgid_delivery_by_device_t6` (job `mgid_daily:delivery_by_device_t6`) — backfill inicial `2026-06-12`.

### Resultado validado em produção

- `adframework-etl-00273-pmx`
- `ms_delivery_by_device`: **6.153 linhas** — `date`/`client_id` 100% populados
- `mg_delivery_by_device`: 251 linhas — join `creative_id` ↔ `mg_teasers` **100%**, `device_type` com 3 valores (`mobile`, `desktop`, `tablet`)

### Pendências

- [ ] `operating_system` MGID fica de fora até surgir necessidade real
- [ ] T7 (by hour) é o próximo T

---

## 2026-06-22 — T5 by-geo implementado — limite de 3 dimensões MGID e ausência de `region` na MS descobertos

**Autor:** Douglas Reche

### Contexto

T5 (entrega por geografia). Grain definido em `raw_layer_design.md`: `T4 + country + region + city`.

### Descoberta 1 — MGID aceita no máximo 3 dimensões por chamada

Testei `day+campaignId+teaserId+country` (4 dimensões) — API retornou erro estruturado:
```json
{"errors":{"dimensions":["This collection should contain 3 elements or less."]}}
```
Confirma um limite **rígido** já mencionado no sketch original, mas que eu não tinha verificado na prática até agora. T5 não cabe no grain completo (T4 + geo) numa única chamada.

**Decisão (validada com o usuário):** remover `campaignId` da chamada — `creative_id` (teaserId) já é FK para `raw.mg_teasers`, que tem `campaign_id` no catálogo. `campaign_id` é recuperado via JOIN na STG, não duplicado na RAW. Ficou: `day + teaserId + region` (3 dimensões, dentro do limite).

**Por que não duas tabelas separadas (by_country + by_region):** perguntei e descartei essa opção — juntar duas tabelas buscadas separadamente (uma por país, outra por região) na STG causaria **fan-out** (inflação de impressões/cliques), porque a junção só por dia+campanha multiplicaria linhas de uma tabela pelas da outra sem uma chave comum de geografia. Não é um join seguro.

### Descoberta 2 — `region` não existe na API da MediaSmart

Testei `regioncode` como dimensão de drilldown — API rejeitou: `"Provided drilldown variable is wrong: regioncode"`. Busquei a doc oficial (`API_Doc_MediaSmart.md`) — o dicionário de drilldown **não lista nenhum campo de região/estado**, só `countrycode` e `city`. O design original assumia `region: ✓ (BR-SP)` sem ter testado — não existe.

### Descoberta 3 — MGID `region` é texto livre, mistura cidade/estado, e não é 100% Brasil

Testando `day+teaserId+region`, os valores retornados foram texto livre como `"São Paulo City"`, `"Texas State"` — mistura granularidade de cidade e estado, e inclui tráfego fora do Brasil (residual/VPN, baixo volume). Confirma a observação que já estava registrada no sketch original ("verificar se region contém cidade"). `country` não foi gravado na RAW — fica pendência de parse/lookup na STG se necessário.

### Implementação

**DDLs** (particionadas por `date`): `raw/ddl/ms_delivery_by_geo.sql` (13 campos: `date, client_id, campaign_id, creative_id, country, city` + KPIs), `raw/ddl/mg_delivery_by_geo.sql` (8 campos: `date, creative_id, region` + KPIs — **sem `campaign_id` e sem `country`**, propositalmente).

**Connectors:**
- `connectors/mediasmart.py` → `fetch_delivery_by_geo_normalized(date)` — drilldown `day,eventid,controlid,creativeid,countrycode,city`
- `connectors/mgid.py` → `fetch_delivery_by_geo_normalized(date)` — `dimensions=day,teaserId,region`

**Dispatch — `orchestrator.py`:** generalizei o padrão `is_t4` (booleano único) para um dict `normalized_methods = {table_id: nome_do_método}`, permitindo múltiplos Ts normalizados por método sem if/elif crescendo a cada T novo. Aplicado em `_run_mediasmart_daily()` e `_run_mgid_daily()`.

**Jobs Firestore novos:** `mediasmart_delivery_by_geo_t5` (job `mediasmart_daily:delivery_by_geo_t5`), `mgid_delivery_by_geo_t5` (job `mgid_daily:delivery_by_geo_t5`) — backfill inicial `2026-06-12`.

### Resultado validado em produção

- `adframework-etl-00272-zlp`
- `ms_delivery_by_geo`: **32.447 linhas** (confirma o aviso de alta cardinalidade do design) — `date`/`client_id` 100% populados
- `mg_delivery_by_geo`: 669 linhas — join `creative_id` ↔ `mg_teasers` **100%**

### Pendências

- [ ] Resolver `country` na STG para MGID (via parse do texto livre de `region` ou aceitar ausência)
- [ ] T6 (by device/OS) é o próximo T — mesma disciplina de testar limites/campos antes de desenhar

---

## 2026-06-22 — Gap de join `ms_delivery` ↔ `ms_creatives` RESOLVIDO — T3 MS reconstruído

**Autor:** Douglas Reche

### Contexto

Logo após validar o T4 (entrada anterior), investiguei mais a fundo o gap de join `creative_id` reportado ali — em vez de aceitar como limitação permanente, fui atrás da causa raiz na API.

### Investigação que resolveu o gap

A doc oficial (`API_Doc_MediaSmart.md`, linha 2125) tem a pista: *":cid is a campaign creative identifier inside the campaign (not the creative identifier)"* — confirma que existem múltiplos IDs de associação criativo↔campanha, não só um.

Busquei o corpo completo de uma campanha (`GET /api/campaign/{id}`, não `/creatives`) e encontrei: cada campanha tem um array `strategies[]`, e **cada strategy tem seu próprio array `creatives.campaign_creatives[]`** — uma segunda lista de associações criativo↔campanha, **diferente** da lista que `/api/campaign/{id}/creatives` retorna.

**Teste decisivo:** o `id` de um item dentro de `strategies[].creatives.campaign_creatives[]` (ex: `xr30qufssiwwczgotqfo4s316krqerfm`) bate **exatamente** com o `creativeid` da entrega **menos o prefixo `cr-`** (`cr-xr30qufssiwwczgotqfo4s316krqerfm`). Confirmado cruzando todos os IDs de uma campanha real (Cora, 2 strategies, 12 campaign_creatives) — nenhum bate com o endpoint antigo, mas batem exatamente com o novo.

**Conclusão:** a MediaSmart tem **dois conjuntos independentes** de associação criativo↔campanha — um direto na campanha (`/api/campaign/{id}/creatives`) e outro dentro de cada strategy (`campaign.strategies[].creatives.campaign_creatives[]`). A entrega/analytics só referencia o **segundo** (nível strategy). O T3 original buscava do primeiro — por isso nunca batia.

### Fix — T3 `ms_creatives` reconstruído

**`connectors/mediasmart.py` → `fetch_creatives_normalized()` reescrito:**
- Antes: `GET /api/campaign/{id}/creatives` (lista direta de campanha)
- Agora: `GET /api/campaign/{id}` (corpo completo) → itera `strategies[].creatives.campaign_creatives[]`
- `creative_id` gravado com prefixo `cr-` **adicionado deliberadamente** (`f"cr-{cc['id']}"`), para bater 1:1 com `ms_delivery.creative_id` sem precisar de manipulação de string na STG
- Campos (`name, type, width, height, click_url, thumbnail_url`) agora lidos do objeto `creative` aninhado dentro de cada `campaign_creative` (estrutura diferente do endpoint antigo, que tinha esses campos no nível raiz)

**Resultado:** reprocessado — **201 linhas** (vs 23 antes; o endpoint antigo só capturava uma fração dos criativos reais). Join `ms_delivery.creative_id = ms_creatives.creative_id`: **729/735 (99,2%)** — antes do fix era **0/735 (0%)**.

**6 linhas remanescentes sem match:** 1 é a campanha histórica já conhecida (fora do catálogo `/api/campaigns` ativo — gap documentado anteriormente); 5 são de uma única campanha (`AMIGO_RETARGETING_JUNHO26`) — provavelmente criativos removidos da strategy depois de já terem gerado entrega histórica (staleness normal entre catálogo atual e histórico de delivery, não é bug).

### Arquivos atualizados

- `connectors/mediasmart.py` — `fetch_creatives_normalized()` reescrito
- `docs/raw_layer_design.md` — nota do gap de join atualizada de "❌ não resolvido" para "✅ resolvido"
- `docs/mediasmart_raw_sketch.md` — T3 atualizado com a fonte correta

### Pendências

- [ ] Investigar as 5 linhas da campanha `AMIGO_RETARGETING_JUNHO26` sem match (baixa prioridade, 0,7% do total)
- [ ] Avaliar se vale capturar também os criativos do endpoint antigo (`/api/campaign/{id}/creatives`) como um conjunto separado — pode ter uso para outra finalidade (ex: biblioteca de criativos não atribuídos a nenhuma strategy)

---

## 2026-06-22 — T4 `ms_delivery` + `mg_delivery` implementados — gap de join MS descoberto, MGID confirmado limpo

**Autor:** Douglas Reche

### Contexto

T4 (fato principal de entrega), o T mais crítico do rebuild. Grain definido em `raw_layer_design.md`: `dia + client + campanha + creative`.

### Investigação — drilldown correto (MS)

O job de produção atual (`mediasmart_daily_daily`) usa drilldown `day,eventid,controlid,strategyid,strategyname,convsource` — **nível de strategy**, não de creative. Isso contradiz a decisão já registrada em 18/06 ("Strategy eliminada — hierarquia final client→campaign→creative→KPIs"). Reconfirmei com o usuário: o `raw_layer_design.md` é a fonte autoritativa e define `creative_id` explicitamente no grain — segui o plano, não o job legado.

**Testei sem `drilldown` para entender o impacto:** a API ainda retorna por dia, mas **agrega tudo** (todos os clientes/campanhas somados num único número) — inviável para atribuição por cliente. Confirma que `drilldown` com no mínimo `eventid`+`controlid` é obrigatório.

### Descoberta crítica — gap de join `creative_id` na MediaSmart

Doc oficial (`API_Doc_MediaSmart.md`) lista **dois campos de drilldown distintos**:
- `creaid` → "Creative ID"
- `creativeid` → "Campaign Creative ID"

Testei `creaid` como drilldown — **API rejeitou** (`"Provided drilldown variable is wrong: creaid"`), mesmo documentado. Usei `creativeid` (aceito), mas o valor retornado (`cr-xr30qufssiwwczgotqfo4s316krqerfm`) **não bate** com nenhum `creative_id` de `raw.ms_creatives` (formato sem prefixo, ex: `ih41zmzgfdk4lqiovc52codeixppu16c`) — testado removendo o prefixo `cr-` também, sem match, para a mesma campanha.

**Conclusão:** `ms_delivery.creative_id` e `ms_creatives.creative_id` são **namespaces de ID diferentes** na API da MediaSmart. Gravado mesmo assim (grain do plano exige creative_id), mas **o join não funciona até investigação adicional** — gap documentado, não resolvido nesta sessão.

### MGID — creative_id confirmado limpo

Testei `dimensions[]=day&dimensions[]=campaignId&dimensions[]=teaserId` no `statistics-reports` — `teaserId` retornado (`27220800`, `27146451`...) bate **100%** com `raw.mg_teasers.creative_id` (mesmo namespace numérico). Sem gap na MGID.

### Implementação

**DDLs** (ambas particionadas por `date`): `raw/ddl/ms_delivery.sql` (16 campos), `raw/ddl/mg_delivery.sql` (9 campos, sem `client_id` — resolvido na STG via `platform_client_links`, mesmo padrão do T1/T2 MGID). `ctr` propositalmente omitido — é "derivado", recalculado na STG.

**Connectors:**
- `connectors/mediasmart.py` → `fetch_delivery_normalized(date)` — reusa `fetch_csv_url`/`csv_to_df` existentes, com drilldown `day,eventid,controlid,creativeid`
- `connectors/mgid.py` → `fetch_delivery_normalized(date)` — paginado, `dimensions=day,campaignId,teaserId`

**Dispatch — `orchestrator.py`:** branch `is_t4` dentro de `_run_mediasmart_daily()` e `_run_mgid_daily()` (não em `_run_generic_report()`, porque essas duas já têm a lógica de incremento por data via `_get_date_range()`/`get_max_date()`, reaproveitada). Job antigo (`mediasmart_daily`/`mgid_daily`) continua intocado quando `table_id` não é `ms_delivery`/`mg_delivery`.

**Jobs Firestore novos (não redirecionados ainda):** `mediasmart_delivery_t4` (job `mediasmart_daily:delivery_t4`) e `mgid_delivery_t4` (job `mgid_daily:delivery_t4`) — criados como jobs **separados** dos antigos `mediasmart_daily_daily`/`mgid_daily_daily`, com backfill inicial de `2026-06-12`. Decisão deliberada: validar a tabela nova em paralelo antes de redirecionar/desativar o job de produção, dado o risco maior de um fato incremental vs os catálogos já migrados.

### Bug encontrado e corrigido — `date`/`client_id` nulos

Primeira execução: `date` e `client_id` vieram `NULL` em 100% das 735 linhas. Causa: `fetch_delivery_normalized()` só renomeava as colunas de vídeo (`video_25_viewed→video_25`...), esqueceu de renomear `day→date` e `event_id→client_id` (nomes que o `normalize_data()` genérico produz a partir do CSV). Corrigido, tabela truncada e reprocessada — `0/735` nulos após o fix.

### Resultado validado em produção

- `adframework-etl-00270-x8n`
- `ms_delivery`: 735 linhas (backfill 12-19/06) — `campaign_id` confere 734/735 (99,9%) com `ms_campaigns`; 1 campanha histórica fora do catálogo ativo (não é bug)
- `mg_delivery`: 133 linhas — `creative_id` confere **100%** com `mg_teasers`

### Pendências

- [ ] Investigar gap `ms_delivery.creative_id` ↔ `ms_creatives.creative_id` — talvez exista endpoint/campo de mapeamento ainda não encontrado
- [ ] Decidir quando redirecionar `mediasmart_daily_daily`/`mgid_daily_daily` (produção) para as tabelas novas — aguardando mais alguns dias de validação em paralelo
- [ ] Backfill histórico completo (hoje só 12-19/06) — fazer depois de confirmar estabilidade
- [ ] T5 (by geo) é o próximo T

---

## 2026-06-22 — T3 MS `ms_creatives` + T3 MGID `mg_teasers` implementados — bug de `raw_ingested_at` nulo corrigido

**Autor:** Douglas Reche

### Contexto

T3 (criativos) para MS e MGID, seguindo o escopo **autoritativo de `raw_layer_design.md`** (não o esboço de 37 campos de `mgid_raw_sketch.md`, que incluía stats/conversion e nunca foi promovido a plano oficial). `raw_layer_design.md` define T3 com 10 campos conceituais por plataforma, sem KPIs de delivery nem categoria.

### Decisão de escopo — por que sem stats/conversion/category

`mgid_raw_sketch.md` (esboço, "não é plano oficial") tinha 37 campos para `mg_teasers`, incluindo `stat_clicks_total/today/yesterday`, `stat_shows_*`, `stat_spent_*`, `stat_ctr`, `conv_interest/decision/buying_*`. `raw_layer_design.md` (decisão conjunta, autoritativa) **não inclui nenhum desses** — optou por um T3 magro, puramente de catálogo. Motivo: esses campos são snapshot de KPI no momento da chamada — ficam desatualizados a cada `WRITE_TRUNCATE` e duplicam o que as tabelas de delivery (T4+) já trazem corretamente, com granularidade diária. `category` também foi excluída — é atributo de campanha (já em `mg_campaigns`), não de criativo.

### Validação contra API real

**MS — `GET /api/campaign/{id}/creatives`:** resposta real tem `id` (nível raiz) = ID da **associação** criativo↔campanha — diferente do `creative.id` aninhado (asset reutilizável, fora de escopo). Confirmado: `advert_text`/`call_to_action` realmente não existem em nenhum nível da resposta (nem em `creative.*`) — bate com o que `raw_layer_design.md` já registrava ("não existe na API").

**MGID — `GET /v1/goodhits/clients/{id}/teasers`:** campos reais em camelCase (`advertText`, `imageLink`, `callToAction`, `campaignId`), `status` é objeto `{code: "..."}` (extraído `status.code`). `width`/`height` não vêm da API — confirmado fixo pelo comercial (1280×720, decisão já registrada em 18/06).

### Implementação

**DDLs:** `raw/ddl/ms_creatives.sql` (10 campos), `raw/ddl/mg_teasers.sql` (12 campos, incluindo width/height fixos).

**Connectors:**
- `connectors/mediasmart.py` → `fetch_creatives_normalized(campaign_ids)` — itera por campanha, sleep 0.5s entre chamadas
- `connectors/mgid.py` → `fetch_teasers_normalized()` — paginado, com dedup por `seen_ids` (mesmo padrão de `fetch_teasers()` antigo — a paginação da MGID pode repetir itens)

**Dispatch — `orchestrator.py`:**
- MS: novo bloco `if "/api/creatives" in endpoint_path and target["table_id"] == "ms_creatives"` — busca `campaign_id` direto de `raw.ms_campaigns` (mais simples que a lógica legada `_fetch_mediasmart_creatives_iter`, que dependia de `raw.mediasmart_daily`)
- MGID: `if target["table_id"] == "mg_teasers": records = connector.fetch_teasers_normalized()`

### Bug encontrado — `raw_ingested_at` sempre NULL no branch MGID

Ao validar `mg_teasers`, percebi `raw_ingested_at` como `NaT` em 100% das linhas. Investigando, confirmei que **o mesmo bug já existia em `mg_campaigns`** (173/173 nulos) desde a implementação do T2 — passou despercebido porque a validação anterior não checou essa coluna especificamente.

**Causa raiz:** o branch `elif platform_id == "mgid":` em `_run_generic_report()` chama `bq.load_rows(records, write_mode=write_mode)` direto, sem nunca injetar `raw_ingested_at` — diferente dos branches dedicados de MS (`/api/advertisers`, `/api/campaigns`, `/api/creatives`), que sempre fazem `r["raw_ingested_at"] = ingested_at` manualmente antes do load.

**Fix:** adicionado ao final do branch MGID (afeta todos os sub-casos — campaigns, teasers, e o genérico):
```python
if not records:
    return {"status": "success", "rows_loaded": 0}
ingested_at = datetime.now(UTC).isoformat()
for r in records:
    r.setdefault("raw_ingested_at", ingested_at)
bq.load_rows(records, write_mode=write_mode)
loaded = len(records)
```
`setdefault` (não atribuição direta) para não sobrescrever caso algum método já tenha setado o campo individualmente.

**Re-execução:** `mgid_firstlevel:campaigns` e `mgid_firstlevel:creatives` rodados de novo após o fix — `mg_campaigns` e `mg_teasers` confirmados com 0 nulos em `raw_ingested_at`.

### Resultado validado em produção

- `adframework-etl-00268-kfx`
- `ms_creatives`: 23 linhas, 23 `creative_id` distintos, 100% com `campaign_id`
- `mg_teasers`: 167 linhas, 167 `creative_id` distintos, 100% com `campaign_id`, `raw_ingested_at` 100% populado

### Jobs Firestore redirecionados

- `mediasmart_firstlevel_creatives` → `ms_creatives` (era `mediasmart_creatives`)
- `mgid_firstlevel_creatives` → `mg_teasers` (era `mgid_creatives`)

**Total migrado até agora: 5 de 22 jobs antigos** (`ms_advertisers`, `ms_campaigns`, `ms_creatives`, `mg_campaigns`, `mg_teasers`).

### Pendências

- [ ] T1 Siprocal ainda resolvido só na STG (sem mudança) — nada pendente aqui
- [ ] T4 (delivery) é o próximo T — fato principal de entrega, MS+MGID+Siprocal
- [ ] Revisar se o bug de `raw_ingested_at` nulo afeta algum outro branch além do MGID (MediaSmart já injeta manualmente em todos os blocos dedicados — confirmado correto)

---

## 2026-06-22 — T2 MS `raw.ms_campaigns` implementado — 3 bugs de tipo descobertos e corrigidos

**Autor:** Douglas Reche

### Contexto

T2 MediaSmart, seguindo o design de `mediasmart_raw_sketch.md`. Antes de implementar, testei a API real (5 campanhas: Cora, Amigo, Stocco, Einstein) para confirmar quais campos do design realmente vêm populados — mesma disciplina adotada após os achados de MGID/Siprocal.

### Validação contra API real — campos confirmados vazios

Testando `GET /api/campaign/{id}` em 5 campanhas ativas reais, encontrei o mesmo padrão dos T1 MGID/Siprocal: campos documentados na API que nunca vêm populados na conta da NewAd:

| Campo do design original | Realidade (5/5 campanhas testadas) |
|---|---|
| `goal_cpm/cpc/cpa/cpv`, `goal_type`, `goal_value` | `goal: {}` — vazio em 100% |
| `client_pricing_model`, `client_pricing_value` | `client_pricing: {}` — vazio em 100% |
| `deals_and_pricing.cpa/cpc/cpm` | `null`/`{}`, `optimization_type: 'off'` em 100% |
| `conversion_name_1..5` | Campo real é `conversion_names` com chaves `events2-5` (sem `events1`!), sempre `""` |

**Conclusão:** a NewAd não usa o motor de bid/goal nativo da MediaSmart — pricing é negociado fora da plataforma. Campos omitidos do schema final.

**Campos confirmados ricos e populados:** `attribution_window_on_click/impression`, `tracking_tool`, `targeting`/`retargeting` (JSON), `desktop_allowed`, `minimal_cpm` (substituto real do `goal_cpm` sempre vazio), `premium_dashboard`, `sync_campaigns`, `use_custom_conversion_names` — vários não previstos no design original mas reais e úteis. `schedule.*` confirmado rico: `started_at, finished_at, max_daily/global_cost, max_daily/global_impressions, delivered_cost, daily_limits_type, uniform_distribution, timezone`.

**Achado extra:** existe um objeto `advertiser` aninhado dentro de cada campanha (duplicando T1) e um `advertiser_name` no nível raiz — não estavam no design original, mantidos por conveniência de debug.

### Bugs de tipo encontrados e corrigidos (3 ciclos de deploy)

**Bug 1 — `attribution_window_on_click` rejeitado como INT64:**
```
Could not convert value 'string_value: "30.0"' to integer. Field: attribution_window_on_click; Value: 30.0
```
**Causa raiz:** `BigQueryService.load_data()` (`src/bigquery.py`) converte a linha inteira via `pandas.DataFrame.astype(str)` antes de carregar. Quando uma coluna tem `None` misturado com inteiros em registros diferentes do mesmo batch, o pandas promove a coluna para `float64` — o valor `30` (int) se torna `"30.0"` (string) após o `astype(str)`. BigQuery aceita `"30.0"` em coluna `FLOAT64`, mas rejeita em `INT64` estrito.
**Fix:** todas as colunas inteiras nullable (`attribution_window_on_click/impression`, `max_daily_impressions`, `max_global_impressions`) foram declaradas como `FLOAT64` em vez de `INT64` no DDL — evita o conflito sem precisar alterar a infraestrutura compartilhada (`bigquery.py` é usado por todos os connectors).

**Bug 2 — `created_at` rejeitado como TIMESTAMP:**
```
Could not parse '2025-10-31' as a timestamp. Field: created_at; Value: 2025-10-31
```
**Causa raiz:** `created_at` vem da API só com data, sem componente de hora (`"2025-10-31"`) — TIMESTAMP exige `HH:MM[:SS]`.
**Fix:** `created_at` → `DATE` no schema.

**Bug 3 — `updated_at` (formato ISO com milissegundos):** por precaução, declarado como `STRING` em vez de `TIMESTAMP` — vem como `"2026-06-11T18:09:12.880Z"`, formato que pode não ser aceito de forma consistente pelo parser estrito de carga JSON do BQ. Cast para TIMESTAMP fica para a STG.

**Regra de processo adicionada:** colunas numéricas nullable que passam por `BigQueryService.load_data()` devem ser `FLOAT64`, nunca `INT64` — a conversão via pandas sempre arrisca essa promoção de tipo quando há `None` no batch.

### Implementação

**DDL:** `raw/ddl/ms_campaigns.sql` — 32 campos, incluindo `schedule.*` achatado e `targeting`/`retargeting` preservados como JSON STRING.

**Connector — `connectors/mediasmart.py` → `fetch_campaigns_normalized()`:** busca lista de IDs via `/api/campaigns`, depois corpo completo por `/api/campaign/{id}` com sleep 0.5s (quota 128 req/min). Helpers `_to_int()`/`_to_float()` adicionados para cast seguro (a API mistura tipos entre campanhas — mesmo padrão de inconsistência já visto no MGID).

**Dispatch — `orchestrator.py`:** novo bloco `if "/api/campaigns" in endpoint_path and target["table_id"] == "ms_campaigns"`, com o mesmo fallback de credenciais (Firestore → env vars) já usado em `/api/advertisers`. O job antigo (`endpoint_path` igual mas `table_id` diferente) continua intocado, caindo no branch genérico de sempre.

**Job Firestore redirecionado:** `mediasmart_firstlevel_campaigns` — `table_name`/`bq_destiny` alterados de `mediasmart_campaigns` (sumário, 14 rows, campos limitados) → `ms_campaigns` (corpo completo).

### Resultado validado em produção

`adframework-etl-00266-2cz` → job `mediasmart_firstlevel:campaigns` → `rows_loaded: 14`. Confirmado: 14 `campaign_id` distintos, 100% com `client_id` (FK real para `ms_advertisers.event_id`), datas/custos corretos (ex: Cora `started_at: 2025-08-01, finished_at: 2026-07-10, max_daily_cost: 40.0`).

### Pendências

- [ ] T3 MS (`ms_creatives`) e T3 MGID (`mg_teasers`) — próximos na sequência
- [ ] Avaliar se `minimal_cpm` deveria alimentar `core.dict_format`/gold como proxy de goal, já que `goal_cpm` nunca é populado

---

## 2026-06-22 — Siprocal: RAW literal substitui ingestão com aliasing — bug de dado perdido corrigido

**Autor:** Douglas Reche

### Contexto

Ao investigar o T1 Siprocal (`raw.sp_clients`), encontrei que `campaign_id` (mapeado de `pi_externo`/`pi`) vinha **vazio em 100% das 1121 linhas** da tabela `raw.siprocal_delivery` (schema antigo). Em vez de seguir o design original (que dependia desse campo), parei para investigar a causa raiz antes de desenhar qualquer T1.

### Decisão de arquitetura proposta pelo usuário e adotada

**RAW da Siprocal passa a ser o dump literal da planilha — 0% de tratamento.** Em vez do `SiproCalConnector` aplicar aliasing de headers (`_COLUMN_ALIASES`: `pi_externo/pi → campaign_id`, `campanha → advertiser`, etc.) já na ingestão, a RAW agora grava as colunas exatamente como vêm da planilha (nomes sanitizados só para nomenclatura BQ — minúsculas, sem acento, espaço→underscore). Toda renomeação semântica e derivação passa para a STG.

**Motivo da mudança:** o aliasing na ingestão causava **perda silenciosa de dado** sempre que o header real da planilha não batia com nenhum alias conhecido — sem erro, sem log, o campo só ficava vazio. Isso é exatamente o que aconteceu com `campaign_id`.

### Investigação — header real da planilha

Não tinha acesso direto à planilha (Sheets API bloqueada nas credenciais locais — ADC e `gcloud auth print-access-token` retornaram 403 `ACCESS_TOKEN_SCOPE_INSUFFICIENT`; a planilha só está compartilhada com a service account do Cloud Run). Adicionei um endpoint de debug temporário (`GET /debug/siprocal-headers` em `main.py`) que usa as credenciais do Cloud Run para ler o header bruto — removido do código depois de obter a resposta.

**Header real confirmado** (planilha `1HaGrxaU-nt3fvqxaJ1CSlABYJGNY28rhQC49dcGzLWs`, aba `raw_daily`):
```
Coluna 1, Data, Campanha, Criativo, Impressions, Clicks, CTR
```

**Achados:**
- **Não existe `pi_externo`/`pi`** como nome de coluna — por isso o alias nunca batia. **O usuário confirmou que `"Coluna 1"` É o `pi_externo`** — só está com nome genérico na planilha, não é erro de mapeamento do conector.
- **`CTR` existe na planilha mas nunca foi capturado** pelo schema de saída do connector antigo (`fetch_all_rows()`) — descartado silenciosamente, nem o alias map tentava mapear.
- **Discrepância aparente resolvida:** a leitura bruta retornou 6050 "linhas", mas só 1121 têm dado real. As outras ~4929 são resíduo de uma fórmula de CTR arrastada muito além dos dados reais na planilha, gerando `#DIV/0!` sem mais nenhum valor — não é bug de perda de dado, é characteristic do range lido (`includeGridData=True`, que já bypassa basic-filter row hiding, conforme fix de sessão anterior).

### Decisão sobre o filtro de linhas vazias

Perguntei ao usuário se a RAW deveria incluir essas ~4929 linhas-fantasma (100% literal) ou aplicar um filtro de sanidade. **Decisão: excluir** — linha é descartada se todas as colunas de dado (exceto `ctr`) estiverem vazias. Não é tratamento semântico, só evita lixo de fórmula residual da planilha.

### Implementação

**DDL:** `raw/ddl/sp_delivery.sql`
```sql
CREATE OR REPLACE TABLE `adframework.raw.sp_delivery`
(
  coluna_1 STRING, data STRING, campanha STRING, criativo STRING,
  impressions STRING, clicks STRING, ctr STRING,
  platform STRING, raw_ingested_at TIMESTAMP
);
```
Tudo STRING — fidelidade total à fonte, sem cast de tipo. Parse de data, cast numérico, parse de `%` no CTR: tudo fica para a STG.

**Connector — `connectors/siprocal.py` → `fetch_raw_rows()` (novo, paralelo ao `fetch_all_rows()` existente, que continua servindo jobs não migrados):**
```python
def fetch_raw_rows(self) -> List[Dict[str, Any]]:
    client = SheetsClient()
    values = client.read_values(self.spreadsheet_id, self.sheet_range)
    if not values or len(values) < 2:
        return []
    header = [_sanitize_header(h) for h in values[0]]
    rows: List[Dict[str, Any]] = []
    for raw_row in values[1:]:
        padded = list(raw_row) + [""] * (len(header) - len(raw_row))
        row = {header[i]: str(padded[i]).strip() for i in range(len(header))}
        data_cols = [v for k, v in row.items() if k != "ctr"]
        if not any(data_cols):
            continue
        rows.append(row)
    return rows
```
`_sanitize_header()` — lowercase, remove acento, `[^a-z0-9]+` → `_`. Sem qualquer lógica de alias/sinônimo.

**Dispatch — `orchestrator.py` → `_run_siprocal_daily()`:** decide pelo `table_id` resolvido (igual ao padrão já usado no MGID T2):
```python
is_literal = target["table_id"] == "sp_delivery"
rows = connector.fetch_raw_rows() if is_literal else connector.fetch_all_rows()
...
for row in rows:
    row["platform"] = "siprocal"
    if not is_literal:
        row["report_name"] = report_name
    row["raw_ingested_at"] = ingested_at
...
last_day = None if is_literal else max((r["day"] for r in rows if r.get("day")), default=None)
```
(`report_name` e `last_day` não existem no schema literal — guard adicionado para não quebrar o load.)

**Job Firestore redirecionado:** `siprocal_daily_external` — `table_name`, `bq_destiny`, `bq_table_id` alterados de `siprocal_delivery` → `sp_delivery`.

### Resultado validado em produção

`adframework-etl-00262-sth` → job `siprocal_daily:Daily` → `rows_loaded: 1121` (bate exatamente com o número de linhas reais identificado na investigação).

Distribuição de `coluna_1` (pi_externo) nas 1121 linhas: 26 valores distintos — majoritariamente numéricos (`10`, `38`, `31`...), um placeholder textual `"(vazio)"` (193 linhas sem PI preenchido) e dois valores não-numéricos (`"CS - 012"`, `"NW0825"`) — registrar como atenção para a STG.

### Pendências

- [ ] T1 Siprocal (`sp_clients`) ainda não fechado — decisão de design pendente: derivar client_name do 2º segmento de `campanha` (ex: `NEWAD_BANCOCORA_BR_FEV26` → `BANCOCORA`) na STG, mesma lógica já usada para MGID
- [ ] STG Siprocal: parse de `data` (dd/mm/yyyy → DATE), cast de `impressions`/`clicks` (STRING → INT64), parse de `ctr` (`"1,82%"` → FLOAT64), renomeação `coluna_1 → pi_externo`
- [ ] Investigar os 2 valores não-numéricos de `coluna_1` (`CS - 012`, `NW0825`) e as 193 linhas com `"(vazio)"` — provavelmente período sem PI cadastrado
- [ ] Avaliar se o mesmo padrão "RAW literal" deveria ser retroaplicado a campos não usados do MS/MGID já implementados (não é urgente — MS e MGID vêm de APIs JSON estruturadas, risco de mismatch de nome é bem menor que em planilha de Sheets)

---

## 2026-06-22 — T2 MGID `raw.mg_campaigns` implementado + descoberta de jobs antigos ainda ativos

**Autor:** Douglas Reche

### Descoberta: jobs do schema antigo continuam rodando após o DROP de 2026-06-18

Ao listar `raw.*` antes de seguir pro T1 Siprocal, encontrei tabelas do schema antigo que deveriam ter sido eliminadas no DROP, mas estavam sendo **recriadas diariamente** (`mediasmart_daily` modificada em 2026-06-22, mesma data desta sessão):

```
mediasmart_campaigns, mediasmart_creative_daily, mediasmart_daily, mediasmart_delivery_by_device,
mediasmart_delivery_by_geo, mediasmart_delivery_by_hour, mediasmart_delivery_by_os,
mediasmart_delivery_by_publisher, mediasmart_revenue_daily, mgid_campaigns, mgid_creatives,
mgid_daily, mgid_stats_by_browser, mgid_stats_by_device, mgid_stats_by_geo, mgid_stats_by_hour
```

**Causa raiz:** o Cloud Scheduler job `adframework-etl-daily` (`0 5 * * *` America/Sao_Paulo) chama `/scheduler/run-due`, que processa todos os docs `platform_reports` no Firestore com `enabled: true` — e **28 jobs antigos de mediasmart/mgid continuam habilitados**, apontando para nomes de tabela do schema anterior ao rebuild. O DROP de 18/06 apagou as tabelas, mas não desabilitou os jobs — então eles as recriam todo dia.

**Decisão de processo:** não vamos desabilitar tudo de uma vez. Conforme cada tabela nova (T1, T2, T3...) é criada e validada, o job Firestore correspondente é **redirecionado diretamente** para a nova tabela (mudança de `table_name`/`bq_destiny`), eliminando a tabela antiga de ser recriada. Jobs sem T novo equivalente ainda permanecem ativos até serem migrados.

### T2 MGID `raw.mg_campaigns` — implementado e validado

DDL: `raw/ddl/mg_campaigns.sql`. Schema final (confirmado contra as 173 campanhas reais da conta):

```sql
CREATE OR REPLACE TABLE `adframework.raw.mg_campaigns`
(
  campaign_id STRING, campaign_name STRING, status_id INT64, status_name STRING,
  status_reason STRING, category_id STRING, category_name STRING, campaign_type STRING,
  language_id INT64, start_date DATE, end_date DATE, when_add DATE,
  limit_type STRING, daily_limit FLOAT64, overall_limit FLOAT64, split_daily_limit_evenly BOOL,
  statistics_clicks INT64, statistics_wages FLOAT64,
  utm_source STRING, utm_campaign STRING, utm_medium STRING, utm_custom STRING,
  platform STRING, raw_ingested_at TIMESTAMP
);
```

**Sem `client_id`** — decisão já registrada na entrada de 18/06 (T1 MGID eliminado): vínculo de cliente é resolvido na STG via `core.platform_client_links`.

**Código de ingestão — `connectors/mgid.py` → `fetch_campaigns_normalized()`:**

```python
def fetch_campaigns_normalized(self) -> List[Dict[str, Any]]:
    limit = 100
    start = 1
    rows: List[Dict[str, Any]] = []
    while True:
        url = f"{self.API_BASE_URL}/goodhits/clients/{self.client_id}/campaigns?limit={limit}&start={start}"
        res = self._get_json(url)
        json_data = res.json() or {}
        page_rows = []
        for item_id, c in json_data.items():
            if not isinstance(c, dict):
                continue
            status = c.get("status") if isinstance(c.get("status"), dict) else {}
            category = c.get("category") if isinstance(c.get("category"), dict) else {}
            limits = c.get("limitsFilter") if isinstance(c.get("limitsFilter"), dict) else {}
            tracking = c.get("trackingOptions") if isinstance(c.get("trackingOptions"), dict) else {}
            statistics = c.get("statistics") if isinstance(c.get("statistics"), dict) else {}
            page_rows.append({
                "campaign_id": str(item_id), "campaign_name": c.get("name"),
                "status_id": status.get("id"), "status_name": status.get("name"), "status_reason": status.get("reason"),
                "category_id": category.get("id"), "category_name": category.get("name"),
                "campaign_type": c.get("campaignType"), "language_id": c.get("language"),
                "start_date": c.get("startDate") or None, "end_date": c.get("endDate") or None, "when_add": c.get("whenAdd") or None,
                "limit_type": limits.get("limitType"), "daily_limit": limits.get("dailyLimit"), "overall_limit": limits.get("overallLimit"),
                "split_daily_limit_evenly": bool(limits.get("splitDailyLimitEvenly")) if limits.get("splitDailyLimitEvenly") is not None else None,
                "statistics_clicks": statistics.get("clicks"), "statistics_wages": statistics.get("wages"),
                "utm_source": tracking.get("utm_source"), "utm_campaign": tracking.get("utm_campaign"),
                "utm_medium": tracking.get("utm_medium"), "utm_custom": tracking.get("utm_custom"),
                "platform": "mgid",
            })
        if not page_rows:
            break
        rows.extend(page_rows)
        if len(page_rows) < limit:
            break
        start += 1
        time.sleep(self.RATE_LIMIT_DELAY)
    return rows
```

**Nota:** mantive `fetch_campaigns()` (método antigo, que stringifica subcampos aninhados) intacto — ainda é usado por outros jobs não migrados. O novo método é separado, não uma substituição.

**Dispatch no orquestrador (`orchestrator.py`, dentro do bloco `elif platform_id == "mgid"`):**

```python
if "/campaigns" in endpoint_path:
    if target["table_id"] == "mg_campaigns":
        records = connector.fetch_campaigns_normalized()
    else:
        records = connector.fetch_campaigns()
```

Decide pelo `table_id` resolvido (`_resolve_bq_target()`), não pelo endpoint — assim o mesmo endpoint MGID serve tanto o job antigo (não migrado) quanto o novo, conforme o `table_name` configurado no Firestore.

**Bug corrigido antes do deploy:** primeira versão do dispatch usava `target["table_name"]`, mas `_resolve_bq_target()` retorna a chave `table_id`. Corrigido antes de testar.

**Job Firestore redirecionado:** `mgid_firstlevel_campaigns` — `table_name` e `bq_destiny` alterados de `mgid_campaigns` → `mg_campaigns`. A partir de agora esse job só escreve na tabela nova; `raw.mgid_campaigns` (antiga) para de ser recriada.

**Resultado:** `adframework-etl-00259-njz` → job `mgid_firstlevel:campaigns` → `rows_loaded: 173`. Validado contra a tabela: 173 linhas, 173 `campaign_id` distintos, campos tipados corretamente (datas, status, category, limites).

### Pendências

- [ ] Migrar os outros 27 jobs antigos (mediasmart_daily, mgid_daily, mgid_stats_by_*, etc.) conforme os Ts correspondentes forem criados
- [ ] Dropar `raw.mgid_campaigns` (antiga) quando o rebuild estiver mais avançado
- [ ] T1 Siprocal (`raw.sp_clients`) ainda pendente — próximo T1 a fechar

---

## 2026-06-18 — T1 MGID eliminado — validação empírica refuta design original

**Autor:** Douglas Reche

### Contexto

Ao iniciar a implementação de T1 MGID (`raw.mg_clients`), seguindo o design de `mgid_raw_sketch.md`, testei a API real antes de escrever qualquer DDL/código (lição aprendida do bug do T1 MS — ver entrada abaixo). O teste **refutou as duas suposições centrais** do design original.

### Suposições do design original (escritas só com leitura da doc, não testadas)

1. Existiria uma lista de `client_ids` da MGID — um por advertiser — mantida pelo orquestrador
2. `GET /v1/clients/{id}` + `GET /v1/goodhits/clients/{id}/campaigns` combinados trariam `client_name` (via `advertiserName`) e `category`

### Testes realizados contra a API real

**Teste 1 — `GET /v1/clients/{id}`:**
```
Returned answer:
{
   "id": "_client_api_id_",
   "timezone": "_client's_timezone_",
   "wallet": { "balance": ..., "credit": ..., "income": ..., "currency": "..." }
}
```
Confirmado na doc e na prática: só retorna dados financeiros. Nenhum nome/categoria.

**Teste 2 — conta MGID da NewAd é única.** Verifiquei o env var `MGID_CLIENT_ID` no Cloud Run (Secret Manager) — existe **um único** secret, não uma lista. O `MgidConnector` (`connectors/mgid.py`) já reflete isso: `self.client_id` é singular.

**Teste 3 — busquei as 173 campanhas reais da conta** (`GET /v1/goodhits/clients/{MGID_CLIENT_ID}/campaigns`, paginado, sem filtro de campos = "all properties" por padrão segundo a doc):
- `advertiserName` **não veio em nenhuma das 173** campanhas
- `category` veio em todas, mas 132/173 (76%) retornaram `"Other services"` — sem valor como proxy de cliente
- Nomes de campanha são texto livre sem padrão: `"APERAM - NEWAD"`, `"Chammas - Criativo 1"`, `"Cerpa - Push - Setembro - Campinas"`, `"Bet7k - Mar 07-31"`

**Teste 4 — pedido explícito do campo** via `fields=['id','name','advertiserName','category']` (sintaxe confirmada na doc: array literal, não `fields[]`):
- API aceitou o parâmetro e retornou exatamente `id`, `name`, `category` — mas **descartou `advertiserName` silenciosamente, sem erro**
- Conclui: `advertiserName` é campo **write-only** (obrigatório no POST de criação da campanha, nunca exposto em nenhuma forma de leitura). Não é bug de configuração do job existente — o orquestrador (`orchestrator.py:963-969`) já chama `fetch_campaigns()` da forma mais aberta possível, idêntica ao teste manual.

**Teste 5 — cruzamento com `core.platform_client_links`:**

| Métrica | Valor |
|---|---|
| Campanhas retornadas pela API (18/06/2026) | 173 |
| Já mapeadas em `platform_client_links` | 130 |
| Em comum (mapeadas e ainda ativas na API) | 126 |
| Na API mas **sem** vínculo de cliente | **47 (27%)** |
| Mapeadas mas não retornadas mais pela API (antigas) | 4 |

As 47 sem vínculo são clientes já conhecidos (Cerpa, Pardini, Cassino Pix, Banco Cora, Amigo, Mastercard, Boa Vista) — falta vincular essas campanhas específicas na tabela, não criar clientes novos.

### Decisão final

**`raw.mg_clients` não será criada.** A MGID não modela "advertiser/cliente" como entidade própria na API — o único identificador confiável é o vínculo manual já mantido em `core.platform_client_links`. A dimensão cliente passa a ser resolvida **na STG**, via join:

```
raw.mg_campaigns.id (campaign_id)
     → core.platform_client_links.link_value = campaign_id → .client_id
     → core.dim_client.client_id → .name, .sector
```

Verificado: `core.dim_client` já expõe `client_id, name, sector` — sem necessidade de tabela intermediária.

**Mesmo bug corrigido no T2:** o design de `mg_campaigns` também tinha um campo `advertiser_name` herdado da mesma suposição errada — removido do schema e do código de ingestão planejado. O loop `for client_id in client_ids` também foi corrigido para chamada única (`mgid_client_id` é singular, vem do env var).

### Lição de processo

A sessão de design original (2026-06-18, mais cedo) foi feita só lendo `MGID_API_Doc.md` campo a campo, sem testar contra a API ao vivo — funcionou para MediaSmart (T1 MS validado bateu com o design), mas a doc da MGID tem gaps reais (campo documentado só no contexto de criação, mas listado na tabela de T1/T2 como se viesse na leitura). **Regra adotada a partir de agora:** todo campo crítico (FK, chave de join) deve ser testado contra a API real antes de fechar o design de uma tabela, não só inferido da documentação.

### Arquivos atualizados

- `docs/raw_layer_design.md` — seção T1 reescrita com a investigação completa; T1 MGID removido da lista final de tabelas
- `docs/mgid_raw_sketch.md` — T1 marcado como eliminado com motivo; T2 corrigido (campo `advertiser_name` removido, código de ingestão usa `client_id` único)

### Pendências geradas

- [ ] Comercial: completar vínculo das 47 campanhas MGID sem `client_id` em `core.platform_client_links`
- [ ] Implementar `raw.mg_campaigns` (T2) — próximo passo, dados já confirmados via teste real
- [ ] Validar empiricamente T3 (`mg_teasers`) antes de fechar o design — mesma lição: não confiar só na doc

---

## 2026-06-18 — T1 MS `raw.ms_advertisers` — implementação, bugs e fix de ingestão

**Autor:** Douglas Reche

### Contexto

Primeira tabela T1 do rebuild RAW: `raw.ms_advertisers` — cadastro de advertisers MediaSmart (grain: 1 linha por conta, WRITE_TRUNCATE diário). Implementação, deploy, dois bugs encontrados em produção e corrigidos.

---

### DDL criado — `raw/ddl/ms_advertisers.sql`

```sql
CREATE OR REPLACE TABLE `adframework.raw.ms_advertisers`
(
  event_id          STRING,     -- ID nativo da plataforma: 'newad_brazil-{32chars}'
  id                STRING,     -- sufixo curto (32 chars)
  name              STRING,     -- nome do advertiser (cliente final)
  iab_category      STRING,     -- categoria IAB
  domain            STRING,     -- domínio do advertiser
  sensitive_content STRING,     -- flag de conteúdo sensível
  platform          STRING,     -- 'mediasmart' (injetado)
  raw_ingested_at   TIMESTAMP   -- timestamp da ingestão (injetado)
)
OPTIONS (description = 'T1 MS — WRITE_TRUNCATE diário.');
```

**Por que `event_id`?** A chave JOIN com `ms_delivery.event_id` usa o formato `newad_brazil-{32chars}`, não apenas o sufixo. `id` (sufixo curto) foi preservado para joins alternativos no STG.

---

### Firestore job config — `mediasmart_firstlevel_advertisers`

```json
{
  "platform_id":    "mediasmart",
  "update_type":    "firstlevel",
  "name":           "advertisers",
  "enabled":        true,
  "endpoint":       "/api/advertisers",
  "response_format": "json",
  "write_mode":     "WRITE_TRUNCATE",
  "bq_project_id":  "adframework",
  "dataset_id":     "raw",
  "table_name":     "ms_advertisers",
  "schedule_cron":  "0 4 * * *"
}
```

Job name: `mediasmart_firstlevel:advertisers`

---

### Bug 1 — Credencial Firestore obsoleta (HTTP 401)

**Problema:** `platform_credentials/mediasmart.secrets` no Firestore tem chaves `email`/`password` com senha desatualizada. O job em `/api/advertisers` tentava essas credenciais, recebia HTTP 401, e falhava.

**Fix:** Padrão try/except igual ao existente em `_run_generic_report()` — quando Firestore falha com 401 + "invalid"+"username" no body, faz fallback para env vars do Cloud Run (`MEDIASMART_USERNAME` / `MEDIASMART_PASSWORD`).

**Regra:** As credenciais válidas da MediaSmart vivem apenas nos env vars do Cloud Run (`MEDIASMART_USERNAME`, `MEDIASMART_PASSWORD`). O Firestore `platform_credentials/mediasmart.secrets` está desatualizado e só serve como tentativa primária — o código DEVE ter fallback para env vars. Este padrão deve ser replicado em todos os novos jobs MediaSmart.

**Código do fallback — `orchestrator.py` (bloco `/api/advertisers`):**

```python
if "/api/advertisers" in endpoint_path:
    try:
        connector = MediasmartConnector(connector_cfg)
        records = connector.fetch_advertisers()
    except Exception as exc:
        err = str(exc).lower()
        if connector_cfg.get("username") and "invalid" in err and "username" in err:
            has_env_fallback = bool(os.getenv("MEDIASMART_USERNAME") and os.getenv("MEDIASMART_PASSWORD"))
            if has_env_fallback:
                connector = MediasmartConnector({})  # força leitura das env vars
                records = connector.fetch_advertisers()
            else:
                raise
        else:
            raise
    if not records:
        return {"status": "success", "rows_loaded": 0}
    ingested_at = datetime.now(UTC).isoformat()
    for r in records:
        r["raw_ingested_at"] = ingested_at
    bq.load_rows(records, write_mode="WRITE_TRUNCATE")
    loaded = len(records)
    self._report_update(report, {
        "last_status": "ok",
        "last_rows_loaded": loaded,
        "last_run_at": datetime.now(UTC).isoformat(),
    })
    return {"status": "success", "rows_loaded": loaded}
```

**Nota:** `MediasmartConnector({})` funciona porque o `__init__` faz `os.getenv('MEDIASMART_USERNAME')` como fallback quando `config.get('username')` é vazio.

---

### Bug 2 — `rows_loaded: 0` — API retorna lista, código esperava dict

**Problema:** `fetch_advertisers()` na versão inicial assumia que a resposta de `/api/advertisers` era um `dict` keyed by `event_id`. Porém a API retorna uma **lista de objetos**, onde cada objeto tem o campo `event_id` dentro de si. O guard `if not isinstance(data, dict): return rows` causava retorno de lista vazia.

**Por que não foi detectado antes?** O primeiro run bem-sucedido (21 rows) usou o caminho de código antigo via `_normalize_records()`, que trata lista, dict e dict-com-"data". O novo `fetch_advertisers()` foi testado apenas após o deploy do fix do Bug 1, momento em que a autenticação já funcionava — revelando o Bug 2.

**Fix — `connectors/mediasmart.py` — `fetch_advertisers()`:**

```python
def fetch_advertisers(self) -> List[Dict[str, Any]]:
    url = f"{self.API_BASE_URL}/api/advertisers"
    data = self.fetch_json_url(url)
    rows: List[Dict[str, Any]] = []

    # Normaliza 3 formatos possíveis de resposta da API
    if isinstance(data, list):
        items = [(None, item) for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        if isinstance(data.get("data"), list):
            # wrapper {"data": [...]}
            items = [(None, item) for item in data["data"] if isinstance(item, dict)]
        else:
            # dict keyed by event_id — formato histórico
            items = [(k, v) for k, v in data.items() if isinstance(v, dict)]
    else:
        return rows

    for key, item in items:
        # key = dict key (quando resposta é dict keyed by event_id), ou None (lista)
        # event_id: usa o key se disponível (mais confiável), senão lê do objeto
        event_id = str(key or item.get("event_id") or item.get("eventId") or "")
        row: Dict[str, Any] = {
            "event_id":          event_id,
            "id":                str(item.get("id") or ""),
            "name":              str(item.get("name") or ""),
            "iab_category":      str(item.get("iab_category") or item.get("iabCategory") or ""),
            "domain":            str(item.get("domain") or ""),
            "sensitive_content": str(item.get("sensitive_content") or item.get("sensitiveContent") or ""),
            "platform":          "mediasmart",
        }
        rows.append(row)
    return rows
```

**Regra para todos os novos `fetch_*` methods:** nunca assumir formato fixo de resposta. Sempre normalizar as 3 variantes: lista direta, dict keyed, dict com wrapper `"data"`.

---

### Resultado final — T1 MS validada em produção

- Revisão Cloud Run: `adframework-etl-00253-2kx`
- Job: `mediasmart_firstlevel:advertisers` → `{"status": "success", "rows_loaded": 21}`
- Tabela: `adframework.raw.ms_advertisers` — 21 linhas (todos os advertisers ativos)
- Schedule: `0 4 * * *` (4h UTC diário)

### Arquivos modificados

- `raw/ddl/ms_advertisers.sql` **criado**
- `adframework_python/src/connectors/mediasmart.py` — `fetch_advertisers()` adicionado (normalização multi-formato)
- `adframework_python/src/orchestrator.py` — dispatch `/api/advertisers` + fallback env vars adicionados

---

## 2026-06-18 — RAW layer redesign API-first + DROP completo (raw/stg/gold)

**Autor:** Douglas Reche

### Contexto

Após o reset decidido em 2026-06-16, foi realizada uma sessão de redesign API-first completa da camada RAW. Cada plataforma foi analisada endpoint por endpoint para definir exatamente quais tabelas extrair, quais campos trazer e por quê. O resultado é um plano T1–T7 por plataforma com nomes padronizados e hierarquia clara.

### Decisões de arquitetura tomadas

**1. `client_id` na RAW = ID nativo da plataforma**
- MS: `event_id`; MGID: `client_id`; Siprocal: `pi_externo`
- Mapeamento para `newad_client_id` acontece na gold via tabela de vínculo
- Motivo: manter RAW fiel à fonte, evitar derivação prematura

**2. Strategy MS eliminada — hierarquia final: client → campaign → creative → KPIs**
- Strategy era confundida com "formato" (native/video/push), mas não é
- `formato` (ex: NATIVE, VIDEO, RETARGETING) vem do nome da campanha, não da strategy
- Strategy = configuração operacional (orçamento, targeting, goal settings) — sem valor analítico autônomo
- Commercial rule aprovada: uma campanha = uma strategy — T3 ms_strategies descartada

**3. `core.dict_format` — tabela de mapeamento formato × plataforma → goal_type**
- Lookup extensível: `(formato, plataforma) → goal_type` (CPM/CPC/CPI)
- STG parseia `formato` do `campaign_name` → join com `core.dict_format` → traz `goal_type`
- Não hardcoded no código — novos formatos = nova linha na tabela

**4. Padronização do `campaign_name` obrigatória na ingestão RAW**
- Padrão: `{CLIENTE}_{FORMATO}_{PAIS}_{PERIODO}` (ex: `CORA_NATIVE_BR_SET26`)
- Ingestão normaliza: `raw_name.strip().upper()` antes de gravar
- Siprocal: `formato = push` fixo, sem parsing

**5. Grain de entrega: `dia + client + campanha + creative` (igual nas 3 plataformas)**
- T4/T5 campaign-level e creative-level são redundantes — group by resolve
- Tabela única no grain mais granular (creative)

**6. Criativos (T3):**
- MS não tem `advert_text`/`call_to_action` — texto embutido no arquivo, não exposto pela API (confirmado em `API_Doc_MediaSmart.md`)
- MGID tem `advert_text`, `call_to_action` — campos de texto do teaser
- `size` para MGID e Siprocal = fixo pelo comercial (API não expõe)

### Tabela de plataformas × Ts planejadas

| T | MS | MGID | Siprocal |
|---|---|---|---|
| T1 | `ms_advertisers` | `mg_clients` | `sp_clients` |
| T2 | `ms_campaigns` | `mg_campaigns` | `sp_campaigns` |
| T3 | `ms_creatives` | `mg_teasers` | — |
| T4 | `ms_delivery` | `mg_delivery` | `sp_delivery` |
| T5 | `ms_delivery_by_geo` | `mg_delivery_by_geo` | — |
| T6 | `ms_delivery_by_device` | `mg_delivery_by_device` | — |
| T7 | `ms_delivery_by_hour` | `mg_delivery_by_hour` | — |

**Descartados:** by_publisher/widget (campos divergentes), by_browser (baixo valor), by_audience (DMP inativo), video_mgid e quality_by_source (baixa prioridade).

### DROP executado — estado final

| Dataset | Resultado |
|---|---|
| `raw.*` (exceto `io_plan_drive_snapshot`) | ✅ Dropado — 30 tabelas |
| `stg.*` | ✅ Dropado — 29 tabelas/views |
| `gold.*` | ✅ Dropado — 8 tabelas/views |
| `raw.io_plan_drive_snapshot` | ✅ Preservada — fonte do IO Plan Drive |
| `core.*` | ✅ Intocado |

**Por que `io_plan_drive_snapshot` foi preservada:** dados de IO Plan ingeridos do Google Drive — não vêm de API de plataforma. Seria impossível re-ingerir automaticamente.

### Docs criados/atualizados

- `docs/mediasmart_raw_sketch.md` **criado** — análise API-first completa da MediaSmart: T1–T7, campos confirmados, código de ingestão planejado para T1 e T2
- `docs/mgid_raw_sketch.md` **criado** — análise completa MGID: T1–T7, client_ids como lista fixa, ingestão T1 + T2 documentada
- `docs/siprocal_raw_sketch.md` **criado** — análise Siprocal (Google Sheets): T1–T3, parse_period helper, campaign_id = nome normalizado
- `docs/raw_layer_design.md` **criado** — design doc conjunto: decisões T a T, formato mapa, lista final de Ts
- `docs/INDEX.md` **atualizado** — novos docs adicionados, legado atualizado

---

## 2026-06-16 — Decisão: reset completo do BQ e rebuild from scratch

**Autor:** Douglas Reche

### Contexto

Após auditoria completa da pipeline usando Abril/2026 como período de referência (arquivo Rafael — Banco Cora), confirmou-se que **RAW = STG = GOLD sem perda de dados no pipeline**. No entanto, a auditoria expôs uma série de incongruências estruturais acumuladas desde a versão inicial que tornam a manutenção e evolução da pipeline insustentável.

### Problemas identificados

**1. `normalize_data()` aplicada na ingestão RAW (errado)**
- A função converte todos os headers para snake_case lowercase no momento da ingestão da API
- Causou o bug MS1: `Event ID` → `event_id` (DataFrame) × `eventid` (schema BQ) → **coluna dropada silenciosamente** → NULL em toda a coluna
- O patch aplicado (rename reversal no orchestrator, `_run_mediasmart_daily()`) é frágil e cria dependência oculta entre código e schema
- Normalização de colunas pertence à camada STG, não à RAW

**2. All-STRING na ingestão (`df.astype(str)` em `load_data()`)**
- Todos os valores gravados como STRING no BQ, independente do tipo original
- Impede queries numéricas diretas no RAW; todo audit precisou de `SAFE_CAST`
- Tipos nativos (INT64, FLOAT64, DATE) devem ser preservados desde a ingestão

**3. Schema enforcement silencioso**
- `load_data()` dropa colunas não previstas no schema sem logar erro — bugs invisíveis por design

**4. Arquitetura de patches acumulada**
- Rename reversal no orchestrator, WRITE_TRUNCATE no Siprocal sem justificativa documentada, STG com campos duplicados de versões anteriores
- Risco crescente de que mudanças futuras quebrem comportamentos não documentados

### Decisão tomada

**Dropar `raw`, `stg` e `gold` (datasets de pipeline) e reconstruir do zero** com design limpo:

- **RAW**: sanitização mínima de nomes de coluna (só remover chars inválidos no BQ); tipos nativos; sem snake_case; sem lowercase forçado
- **STG**: normalização completa (snake_case, joins com `core.platform_client_links`, resolução de `client_id`, casts de tipo)
- **GOLD**: grains definidos — `fact_delivery` (client+day+campaign+category), `fact_pacing` (client+day+category), `dim_campaign` com category

### Por que o risco é baixo

- Somente Douglas usa e gerencia a pipeline
- APIs têm histórico completo (Siprocal confirmado: 2025-08-22 → hoje; MS e MGID a confirmar)
- Dados do `core` (dim_client, platform_client_links, campaign_format_map) exportados antes do DROP → [docs/core_config_backup.md](docs/core_config_backup.md)
- Datasets protegidos (`pixel`, `adtracking`, `analytics`, `finops_billing`, tabelas do Admin UI Shiro) **não são tocados**

### Artefatos gerados

- `docs/core_config_backup.md` — export completo das 3 tabelas core (26 clientes, 155 vínculos, 18 mapeamentos) para re-seed
- `docs/bq_restructuring_plan.md` — plano detalhado de deleção, novos schemas RAW/STG/GOLD, sequência de execução em 9 fases, tabela de riscos

---

## 2026-06-16 — Gold layer: execução completa (5 tabelas deployadas)

**Autor:** Douglas Reche

### O que mudou

**1. `gold.fact_io_plan` — fix `unit_price` + redeploy**
- Campo `s.unit_price` adicionado ao SELECT do DDL `gold/ddl/fact_io_plan.sql`
- Necessário para medidas CPM Projetado e CPC Projetado no Power BI
- Verificado: `unit_price = 3.9` para Cora PUSH ✅

**2. `gold.dim_campaign` — rebuild completo**
- DDL `gold/ddl/dim_campaign.sql` reescrito do zero (DDL anterior referenciava `stg.mediasmart_delivery`, legado)
- Novo campo `category`: MS via JOIN `core.campaign_format_map` (mapeamento manual por strategy_id); MGID constante `'NATIVE'`; Siprocal constante `'PUSH'`
- Siprocal: `campaign_id` (pi_externo) → `campaign_name` como platform_campaign_id
- GROUP BY garante PK única (platform, platform_campaign_id): 532 linhas, 0 duplicatas
- Resultado: MS DISPLAY(2) + RETARGETING(2) + VIDEO(2) + OTHER(316); MGID NATIVE(173); Siprocal PUSH(37)

**3. `gold.fact_delivery` — rebuild com `category` (v3)**
- Campo `category` adicionado via LEFT JOIN `gold.dim_campaign` ON (platform, platform_campaign_id)
- Campo `spend` removido (financeiro vem do IO Plan, não da plataforma)
- Campo `video_completions` adicionado (MS apenas)
- MS: double-join obrigatório via `ms_clients + platform_client_links` para client_id canônico
  - `ms_delivery.ms_client_id` = intermediário (`cora_2ruu4won`) ≠ canônico (`banco_cora_fe13d78a`)
  - Sem o double-join, JOIN com `fact_io_plan` falharia
- Resultado: 14.260 linhas, 22 clientes; Cora DISPLAY/RETARGETING/VIDEO ✅; MGID NATIVE; Siprocal PUSH

**4. `gold.fact_pacing` — VIEW nova**
- DDL `gold/ddl/fact_pacing.sql` criado
- Grain: `client_id + report_date + category` (sem buy_model — evita duplicação de actual_impressions)
- Plan CTE: agrega `fact_io_plan` por (client, date, category)
- Delivery CTE: agrega `fact_delivery` por (client, date, category) — filtra `category IS NOT NULL`
- FULL OUTER JOIN: dias com plano mas sem entrega (e vice-versa) aparecem
- buy_model/unit_price NÃO estão aqui — CPM/CPC Projetado: usar `fact_io_plan` com filtro `buy_model`
- Verificado Cora: DISPLAY R$43k/4.9M impr ✅; RETARGETING R$70k/7.1M impr ✅; VIDEO R$54k/5.4M impr ✅

**5. `gold.fact_delivery_by_device` — tabela nova**
- DDL `gold/ddl/fact_delivery_by_device.sql` criado
- Grain: `day + client_id + platform + platform_campaign_id + category + device_type + app_vs_web`
- Fonte: `stg.ms_delivery_by_device` (T9) — MS apenas
- MGID: T13 é por widget (não por device) — sem dado de device disponível
- Siprocal: fonte não reporta device breakdown
- Resultado: 36.440 linhas, 9 clientes; Cora DISPLAY/RETARGETING/VIDEO por Smartphone/Desktop/Tablet ✅

**Limitações conhecidas:**
- `category = 'OTHER'` para MS strategies não mapeadas em `core.campaign_format_map` (TecPar + outros) — ver G3 em known_issues.md
- MGID e Siprocal sem dados em `fact_delivery_by_device`
- `buy_model`/`unit_price` em `fact_pacing` seria desejável mas causaria duplicação — solução: acessar `fact_io_plan` diretamente para essas medidas

**Docs atualizados:**
- `docs/gold_layer_build_plan.md` — checklist marcado como ✅ completo
- `docs/known_issues.md` — G1 e G2 resolvidos, G3 aberto (TecPar MS category mapping)
- `docs/INDEX.md` — status atualizado

---

## 2026-06-16 — Gold layer: design completo + plano de build

**Autor:** Douglas Reche

### O que mudou

**1. Decisões de arquitetura da Gold layer aprovadas**

Grain das tabelas principais definido e registrado:

| Tabela | Grain | Tipo |
|---|---|---|
| `gold.fact_delivery` | client_id + day + platform + platform_campaign_id + category | TABLE |
| `gold.dim_campaign` | platform + platform_campaign_id | TABLE (bridge) |
| `gold.fact_pacing` | client_id + day + category | VIEW |
| `gold.fact_delivery_by_device` | client_id + day + platform + platform_campaign_id + category + device_type | TABLE |

**2. Princípio financeiro confirmado por Douglas:**

> **Tudo financeiro = IO Plan. Tudo volume = plataforma.**

- `investimento_realizado` = `SUM(planned_spend_daily) WHERE report_date <= TODAY` — **não é spend da API**
- Elimina completamente o gap de spend MediaSmart pós 2026-05-16 e a ausência de spend no Siprocal
- `category` = "estratégia" na linguagem NewAd (DISPLAY, VIDEO, RETARGETING, NATIVE, PUSH)

**3. `category` no `fact_delivery` via `dim_campaign` (bridge):**

- MediaSmart: LIKE em `ms_strategy_name` → DISPLAY / VIDEO / RETARGETING
- MGID: constante `'NATIVE'` (todos clientes atuais são Native Ads)
- Siprocal: constante `'PUSH'`

**4. 28 medidas DAX do dashboard Cora mapeadas para Gold:**

Todas as medidas das pastas Investimento, Entrega, Eficiência, CPM, CPC, Pacing e Devices podem ser servidas pelas 5 tabelas gold planejadas — sem tabelas extras.

**5. Issue identificada: `unit_price` ausente em `gold.fact_io_plan`**

Campo `unit_price` existe em `stg.io_plan_drive` mas não foi incluído no DDL de `gold.fact_io_plan`. Necessário para medidas CPM Projetado e CPC Projetado. Fix pendente como Step 1 do build plan.

**6. `gold/ddl/dim_campaign.sql` identificado como quebrado:**

Arquivo DDL existente referencia `stg.mediasmart_delivery` (legado — não existe mais), usa `campaign_id` para Siprocal (errado — deve ser `campaign_name`), e não tem campo `category`. Rebuild necessário como Step 2.

**Docs criados/atualizados:**

- `docs/gold_layer_build_plan.md` **criado** — plano completo com 5 tabelas em sequência de dependência, schemas, mapeamento de 28 medidas DAX, decisões arquiteturais, checklist de execução
- Memory `project_gold_layer_design.md` criada
- `docs/known_issues.md` atualizado — issue G1 (unit_price) aberta

---

## 2026-06-15 — STG + Gold io_plan deployadas (Cora + TecPar 2026)

**Autor:** Douglas Reche

### O que mudou

**1. `stg.io_plan_drive` — VIEW deployada em BigQuery**

- DDL: `stg/ddl/io_plan_drive.sql` (criado Jun-15, deployado Jun-15 pós parser-fixes)
- Grain: 1 linha por (client_id, drive_folder, strategy_name, flight_start) — snapshot mais recente
- Dedup via `ROW_NUMBER() PARTITION BY (client_id, drive_folder, strategy_name, flight_start) ORDER BY snapshot_at DESC`
- Filtros: `flight_start IS NOT NULL AND flight_end IS NOT NULL AND monthly_spend IS NOT NULL AND YEAR >= 2026`
- Enriquecimentos: `plan_line_id` (MD5 estável), `category` (DISPLAY/VIDEO/RETARGETING/NATIVE/PUSH/OTHER), `flight_days`, `planned_impressions`
- Override PUSH → siprocal no campo platform

**2. `gold.fact_io_plan` — VIEW deployada em BigQuery**

- DDL: `gold/ddl/fact_io_plan.sql`
- Grain: 1 linha por (plan_line_id × dia) — explode `GENERATE_DATE_ARRAY(flight_start, flight_end)`
- Campos diários: `planned_spend_daily`, `planned_impressions_daily`, `planned_clicks_daily` (= total_flight / flight_days)
- Pronto para JOIN com `gold.fact_delivery` via client_id + report_date + category/platform

**3. Resultado verificado em BQ**

| Camada | Métrica | Valor |
|---|---|---|
| STG | Total rows | 67 |
| STG | NULL flight_start | 0 |
| STG | NULL planned_spend | 0 |
| Gold (Cora) | Linhas diárias | 1.085 |
| Gold (Cora) | Spend total spread | R$297.749 |
| Gold (TecPar) | Linhas diárias | 814 |
| Gold (TecPar) | Spend total spread | R$164.051 |

**Clientes no STG (com datas populadas):** Cora (JAN–JUN 2026) + TecPar (JAN–JUN 2026).
**Outros clientes** (Luckbet, Einstein, Aperam, Catalise): dados na raw mas `flight_start = NULL` — precisam de re-sync após fixes do parser de Jun-16.

**4. Issue não resolvível no código**

TecPar 2026/FEVEREIRO e 2026/MARÇO têm dados de JANEIRO (arquivo JAN copiado nas pastas pelo Drive). O STG inclui essas linhas (datas válidas). Fix requer reorganização do Drive pelo Rafa/Gessiane — ver `docs/audit_io_plan_cora_tecpar_2026-06-15.md`, seção 4.1.

**5. Docs atualizados**

- `docs/io_plan_pipeline.md`: status header atualizado para STG ✅ + Gold ✅

---

## 2026-06-15 — Siprocal SheetsClient fix + auditoria RAW MGID + 6 campanhas linkadas

**Autor:** Douglas Reche

### O que mudou

**1. SheetsClient — fix crítico: bypass filtros básicos (commit `ff1f6f5`)**

- **Bug:** `values.get()` respeita filtros básicos ativos em planilhas quando conta tem acesso Viewer. O service account ETL é Viewer na sheet Siprocal. Filtro ativo na coluna C (Campanha) escondia ~27 linhas de Jun/10-14 → ETL recebia apenas 1.078 rows (max Jun/09).
- **Fix:** `SheetsClient.read_values()` trocado para `spreadsheets.get(includeGridData=True)` → lê GridData raw, imune a filtros de qualquer tipo e qualquer nível de acesso.
- **Arquivo:** `adframework_python/src/sheets.py`
- **Resultado:** `raw.siprocal_delivery` agora tem 1.105 rows | 2025-08-22 → 2026-06-14 | max date correto
- **Deploy:** `adframework-etl-00243-hg5` (deploy manual via `gcloud run deploy --source`)

**2. Orchestrator — fix fallback de sheet_range (commit `ff1f6f5`)**

- Default hardcoded `"Planilha1!A:G"` em `_run_siprocal_daily()` substituído por `SiproCalConnector.DEFAULT_RANGE`
- Arquivo: `adframework_python/src/orchestrator.py`

**3. Auditoria RAW MGID — resultado completo**

| Tabela | Período | Rows | Situação |
|---|---|---|---|
| `raw.mgid_stats_daily` | out/2025 → hoje | 4.566 | 1.95× dup (STG corrige via ROW_NUMBER) |
| `raw.mgid_campaigns` | atual | 173 | 1.0× (WRITE_TRUNCATE) |
| `raw.mgid_creatives` | atual | 165 | 1.0× (WRITE_TRUNCATE) |
| Breakdowns (7 tabelas) | out/2025 → hoje | variado | 100% cobertura histórica backfill |

- 3 campaign_ids em `raw.mgid_stats_daily` sem metadata em `raw.mgid_campaigns` (campanha encerrada removida pelo WRITE_TRUNCATE) — não bloqueia STG
- 1 dia ausente no calendário MGID (não crítico)
- 0 bad casts em métricas numéricas

**4. 6 campanhas MGID jun/2026 adicionadas a `platform_client_links`**

| campaignid | client_id | Campanha |
|---|---|---|
| 12430495 | einstein_6b33a588 | Einstein Native Jun |
| 12430502 | senar_105bd174 | Senar Native Jun |
| 12430501 | senar_105bd174 | Senar Push Jun |
| 12430497 | amigo_db1c2f0c | Amigo Native Jun |
| 12432098 | stoquinho_56a6ee2a | Stoquinho Native Jun |
| 12437129 | banco_cora_fe13d78a | Banco Cora Native Jun/Jul |

- Script: `C:\Temp\add_mgid_campaigns_jun2026.py`
- `stg.mgid_delivery`: 100% atribuído (0 NULL client_id)

**5. Auditoria RAW Siprocal — resultado**

- 1.105 rows | 36 advertisers | 181 rows com `campaign_id = "(vazio)"` (PI Externo não preenchido pela Siprocal — não bloqueia atribuição)
- 1.0× dedup (WRITE_TRUNCATE garante limpeza)
- Max date: 2026-06-14

**6. Fix crítico: `raw.mediasmart_daily` eventid NULL desde Jun/11 (commit `842ab47`)**

- **Bug:** `normalize_data()` converte headers da API para snake_case (`event_id`, `campaign_id`, `strategy_id`). `raw.mediasmart_daily` tem schema BQ com nomes antigos (`eventid`, `controlid`, `strategyid`) do Shiro. `load_data()` descartava as colunas renomeadas → `eventid = NULL` → `stg.ms_delivery` sem atribuição desde Jun/11.
- **Root cause timeline:** Shiro (aat-console) parou de carregar essa tabela em ~Jun/11; Python ETL assumiu mas sempre teve esse bug — confirmado porque backfill Mai 25-26 (issue D2, Jun/11) também gerou rows NULL.
- **Fix:** `df.rename(columns={"event_id":"eventid","campaign_id":"controlid","strategy_id":"strategyid","strategy_name":"strategyname"})` em `_run_mediasmart_daily()` antes de `bq.load_data()`.
- **Deploy:** `adframework-etl-00249-c4j` via tagged image (`gcloud builds submit --tag` + `gcloud run deploy --image`) — workaround para `--source .` gerar imagens sem tag não importáveis pelo Cloud Run (revisões 00244-00247 todas falharam com `ContainerImageImportFailed`).
- **Backfill:** DELETE rows NULL Mai 25-26 (26 rows) + Jun 11-14 (28 rows) → reingesta com `force_from_date: 2026-05-25` (204 rows) e `force_from_date: 2026-06-11` (34 rows).

**7. Auditoria STG — resultado final pós-correções**

| Tabela | Rows | NULL client_id | Max date |
|---|---|---|---|
| `stg.ms_delivery` | 642.180 | **0** | 2026-06-15 |
| `stg.mgid_delivery` | 2.344 | **0** | 2026-06-14 |
| `stg.siprocal_delivery` | 1.105 | **0** | 2026-06-14 |

RAW → STG coeso e operacional para as 3 plataformas.

**Próximos passos:**
- Executar `gold/ddl/fact_delivery.sql` no BigQuery
- Validar Cora e TecPar end-to-end no gold

---

## 2026-06-15 — Gold fact_delivery v2 + ativação Stocco/DR Consulta + auditoria RAW MediaSmart

**Autor:** Douglas Reche

### O que mudou

**1. `gold.fact_delivery` reescrita (v2) — arquivo: `gold/ddl/fact_delivery.sql`**
- DDL antigo estava completamente quebrado após deploy das novas views STG:
  - MGID: colunas `d.campaignid`, `d.spent`, `d.conversionsinterest` não existem mais em `stg.mgid_delivery` (T3)
  - Siprocal: `d.advertiser`, `d.campaign_id` não existem mais na view redesenhada
  - MS: ainda usava `stg.mediasmart_delivery` (legacy) em vez de `stg.ms_delivery` (T6)
- Novo DDL corrigido:
  - MS: `stg.ms_delivery` (T6) + JOIN duplo `stg.ms_clients` → `platform_client_links` via `ms_event_id`
  - MGID: `stg.mgid_delivery` (T3) + `stg.mgid_revenue` (T8) — `client_id` já canônico na T3
  - Siprocal: `stg.siprocal_delivery` (redesenhada) — `siprocal_client_id` já canônico
- Particionado por `day`, clusterizado por `client_id, platform`
- MS revenue gap documentado: `raw.mediasmart_revenue` só vai até 2026-05-16 (sem `mediasmart_revenue_daily`)
- **Status:** DDL salvo, **ainda não executado no BigQuery**

**2. Stocco e DR Consulta ativados em `core.platform_client_links`**
- Causa do `pending_confirmation`: adicionados manualmente com status conservador aguardando confirmação comercial
- Confirmado: STGs NÃO filtram por `status` — ambos já estavam sendo atribuídos normalmente
- UPDATE executado: 8 rows afetadas (Stocco: 1 MS + 3 MGID; DR Consulta: 1 MS + 3 MGID)
- Todos os `platform_client_links` ativos para esses clientes agora

**3. Auditoria MediaSmart RAW (resultado)**

| Tabela | Período | Rows | Situação |
|---|---|---|---|
| `raw.mediasmart_delivery` (hist) | ago/2025 → mai/2024 | 155,391 | 14 event_ids, backfill completo |
| `raw.mediasmart_daily` (active) | mai/2025 → hoje | 15,497 | 5 event_ids ativos + 54 NULL |
| `raw.mediasmart_revenue` | ? → 2026-05-16 | 9,247 | GAP: sem `mediasmart_revenue_daily` |

- 0 gaps de datas na delivery (cobertura contínua)
- 1 event_id sem backfill (`pardini_60395024`) — cliente sem resposta, decisão comercial pendente
- 54 rows com `event_id IS NULL` em `mediasmart_daily` — investigar

**4. Docs atualizados**
- `docs/id_attribution_map.md`: contagens MS eventids atualizadas (12 ativos / 1 pending / 1 unresolved), status Stocco+DR Consulta+Amigo corrigidos
- `docs/known_issues.md`: M1 marcado como RESOLVIDO, M2 marcado como RESOLVIDO, M3 adicionado (mgid_stats_daily 1.95x dup no raw)

**Pendente:**
- Executar `gold/ddl/fact_delivery.sql` no BigQuery
- Investigar 54 NULL event_id em `mediasmart_daily`
- Decidir sobre Pardini MS eventid (comercial)
- Criar `mediasmart_revenue_daily` job para cobrir spend pós 2026-05-16

---

## 2026-06-14 — IO Plan sync: regra de seleção de arquivo e expansão de clientes

**Arquivo:** `scripts/io_plan/sync_drive.py`

### O que mudou

**1. Regra de seleção de arquivo por pasta PLANO (nova lógica):**
- Antes: preferia arquivo sem nome de pessoa; se só havia pessoais, pegava todos (causava duplicação)
- Agora: prefere arquivo sem nome de pessoa; entre os candidatos (oficiais ou pessoais como fallback), pega **sempre o mais recente** por `modifiedTime` do Drive
- Motivação: evita duplicar dados quando existem múltiplas versões ou cópias renomeadas na mesma pasta

**2. `CLIENT_MAP` expandido de 2 para 14 clientes:**

| Drive folder | client_id |
|---|---|
| `7K` | `bet7k_b777ab9c` |
| `APERAM` | `aperam_14d1f27e` |
| `CATÁLISE` | `catalise_0b7d18d6` |
| `CORA` | `banco_cora_fe13d78a` |
| `DAXX` | `dax_agency_00000001` |
| `DOOING` | `dooing_994db77e` |
| `EINSTEIN` | `einstein_6b33a588` |
| `LUCKBET` | `luckbet_bea15ebc` |
| `MOPAR` | `mopar_a47949f4` |
| `MRV` | `mrv_f19a2136` |
| `OCUPACIONAL` | `ocupacional_98c851f5` |
| `PATIO MEDEIROS` | `patio_medeiros_874a0358` |
| `STOCCO` | `stocco_b712c66e` |
| `TEC PAR` | `tecpar_edfcc744` |

**Dúvidas abertas (não mapeado ainda):**
- `LABTOLAB PARDINI` → Pardini (`pardini_60395024`) ou Lab2Lab (`lab2lab_efb1cb34`) ou ambos?
- `PHISALIA` → cliente sem correspondência em `dim_client`

---

## 2026-06-14 — Siprocal: redesign STG com padronização de campos e resolução de client_id ✅

**Autor:** Douglas Reche
**Commit:** `d952783`

### O que mudou

`stg.siprocal_delivery` redesenhada do zero seguindo o padrão de `stg.mgid_delivery` e `stg.ms_delivery`:

- **`siprocal_client_id` resolvido na STG** via LEFT JOIN com `core.platform_client_links` — 11/11 clientes atribuídos, 0 NULL
- **Grain corrigido:** `day + advertiser_key + creative` (antes documentado incorretamente como incluindo `campaign_id`)
- **Campos renomeados/adicionados:**
  - `advertiser` → `advertiser_key` (chave extraída via regex, ex: `LUCKBET`)
  - `campaign_id` → `pi_externo` (nome honesto — não é ID único, é referência comercial)
  - `campaign_name` preservado como o nome completo (`NEWAD_LUCKBET_BR_SET25`)
  - `ctr` adicionado: `SAFE_DIVIDE(clicks, impressions)`
- **Campos removidos:** `creative_type` (100% vazio na fonte), `report_name` (metadado interno)
- **WHERE clause mais estrita:** filtra `advertiser IS NOT NULL AND advertiser != ''`

### Auditoria RAW realizada antes do redesign

| Check | Resultado |
|---|---|
| Grain `day + advertiser + creative` | ✅ 100% único (0 duplicatas) |
| Nulls em campos principais | ✅ Zero |
| Advertiser seguem `NEWAD_{X}_BR_{Y}` | ✅ 1.093/1.093 rows |
| Impressions/clicks numéricos | ✅ sem exceções |
| `creative_type` | ⚠️ 100% vazio (removido da STG) |
| `campaign_id` (pi_externo) | ⚠️ 172 rows com `(vazio)`, não único por cliente |

### Resultado pós-deploy

| Métrica | Valor |
|---|---|
| Total linhas STG | 1.093 |
| `siprocal_client_id` resolvidos | 11/11 (100%) |
| Total impressions | 7.453.790 |
| Total clicks | 120.545 |

### Tabelas legacy marcadas para drop

`raw.siprocal_raw_sheet` (C1) e `raw.siprocal_sheet_ext` (C2) — documentadas em `known_issues.md`.
Executar após gold layer Siprocal validado.

### Arquivos tocados
- `stg/ddl/siprocal_delivery.sql` — DDL redesenhado
- `docs/siprocal_stg_design.md` — atualizado com novo schema, decisões e próximos passos
- `docs/known_issues.md` — C1/C2 adicionados (tabelas legacy para drop)

---

## 2026-06-14 — Siprocal: pipeline reescrito com SiproCalConnector + 4 bugs corrigidos ✅

**Autor:** Douglas Reche

### Problema
Pipeline Siprocal estava quebrado: `raw.siprocal_raw_sheet` (fonte do ETL job antigo) não existia mais.
A abordagem `sync_sheet.py → BQ intermediário → ETL job` dependia de ADC local com scope `spreadsheets`,
que o Google bloqueia para clientes CLI. Pipeline parado — dados só chegavam até 09/06.

### Solução: SiproCalConnector direto Google Sheets → BQ

`adframework_python/src/connectors/siprocal.py` — classe `SiproCalConnector`:
- Lê Google Sheet `raw_siprocal` aba `raw_daily!A:G` via `SheetsClient` (Sheets API v4)
- Suporta headers PT e EN via `_COLUMN_ALIASES` (data/day, campanha/advertiser, etc.)
- Normaliza datas `dd/mm/yyyy → yyyy-mm-dd` via regex
- Grava direto em `raw.siprocal_delivery` com WRITE_TRUNCATE (substitui tudo a cada run)

`adframework_python/src/orchestrator.py` — `_run_siprocal_daily()`:
- Dispatch via `platform_id == 'siprocal' AND update_type == 'daily'`
- Lê `spreadsheet_id` + `sheet_range` de `platform_credentials/siprocal.secrets`
- Atualiza `last_status`, `last_rows_loaded`, `last_loaded_date` no Firestore após cada run

### 4 bugs corrigidos

| # | Bug | Fix |
|---|---|---|
| 1 | Pipeline antigo quebrado (`sync_sheet.py` + ADC sem scope Sheets + tabela raw deletada) | Substituído inteiramente por `SiproCalConnector` |
| 2 | Firestore `siprocal_daily_external`: `bq_project_id / dataset_id / table_id` eram `None` | Adicionado `adframework` / `raw` / `siprocal_delivery` |
| 3 | Firestore `siprocal.secrets.sheet_range`: `Planilha1!A:G` (aba inexistente) | Corrigido para `raw_daily!A:G` |
| 4 | Python closure late-binding: `def _get(field)` dentro de `for raw_row in values[1:]` capturava `raw_row` por referência — últimas ~15 linhas liam o row errado | `def _get(field, _row=raw_row)` — default arg captura valor no momento da definição |

**Impacto do bug 4:** dados de 10/06 e 11/06 (PATIOMEDEIROS) estavam na sheet mas nunca chegavam ao BQ.

### Deploy
Cloud Run não faz auto-deploy por push de branch.
Deploy manual: `gcloud run deploy adframework-etl --source . --region=us-central1 --project=adframework`
Nova revisão: `adframework-etl-00240-8mw`

### Resultado pós-fix

| Campo | Valor |
|---|---|
| Linhas em `raw.siprocal_delivery` | 1.093 |
| Período | 2025-08-22 → 2026-06-11 |
| Anunciantes distintos | 36 |
| `last_status` Firestore | ok |
| Schedule | 03:20 UTC diário |
| Write mode | WRITE_TRUNCATE |

### Arquivos tocados
- `adframework_python/src/connectors/siprocal.py` — SiproCalConnector (novo)
- `adframework_python/src/orchestrator.py` — `_run_siprocal_daily` (novo método + dispatch)
- `raw/ddl/siprocal_delivery.sql` — pipeline description atualizada

---

## 2026-06-14 — MGID STG T8–T13b: todas as views de drilldown em produção ✅

**Autor:** Douglas Reche

### Contexto
Após os raw jobs A–G (statistics-reports API) terem sido aprovados em 2026-06-13, os DDLs STG
correspondentes foram criados e executados em produção. STG MGID agora está completa (T1–T13b).

### Tabelas STG criadas

| View | # | Grain | Raw table fonte | Financeiro |
|---|---|---|---|---|
| `stg.mgid_revenue` | T8 | day + campaign | `raw.mgid_stats_daily` (Job A) | ✅ spent, cpc, revenue, profit, roas |
| `stg.mgid_delivery_by_device` | T9 | day + campaign + device_type | `raw.mgid_stats_by_device` (Job C) | ✅ |
| `stg.mgid_delivery_by_geo` | T10 | day + campaign + region | `raw.mgid_stats_by_geo` (Job D) | ✅ |
| `stg.mgid_delivery_by_os` | T11 | day + campaign + os | `raw.mgid_stats_by_os` (Job E1) | ✅ |
| `stg.mgid_delivery_by_browser` | T11b | day + campaign + browser | `raw.mgid_stats_by_browser` (Job E2) | ✅ |
| `stg.mgid_delivery_by_hour` | T12 | day + campaign + hour | `raw.mgid_stats_by_hour` (Job F) | ✅ |
| `stg.mgid_delivery_by_widget` | T13 | day + campaign + widget_id | `raw.mgid_stats_by_widget` (Job G) | ✅ (sem conversões) |

### Padrão de implementação (igual para todos T9–T13)
- Dedup com `ROW_NUMBER() OVER (PARTITION BY grain ORDER BY raw_ingested_at DESC)`
- Python dict → JSON: `REPLACE(REPLACE(field, "'", '"'), 'None', 'null')` antes de `JSON_VALUE($.amount)`
- `roas` é STRING inteiro direto (não dict) — `SAFE_CAST AS FLOAT64` direto
- LEFT JOIN `core.platform_client_links` ON platform='mgid' AND link_type='campaignid'
- `source_table` = nome da raw table (rastreabilidade de origem)

### Decisões de design (T10 — geo)
- `raw.mgid_geo_regions` tem 0 linhas (job one-time nunca executado) — JOIN impossível
- `geo_level` derivado do sufixo do texto bruto da API (`City` → city, `Region` → region_aggregate, etc.)
- `country_code` não incluído — resolvido na próxima fase se necessário

### Decisões de design (T13 — widget)
- `widget_id` é ID numérico do placement (widgetid) — sem nome de publisher
- Sem conversões: API MGID não retorna conversões neste grain (mesmo padrão MS publisher)

### Arquivos tocados
- `stg/ddl/mgid_revenue.sql` (T8 — novo)
- `stg/ddl/mgid_delivery_by_device.sql` (T9 — novo)
- `stg/ddl/mgid_delivery_by_geo.sql` (T10 — novo)
- `stg/ddl/mgid_delivery_by_os.sql` (T11 — novo)
- `stg/ddl/mgid_delivery_by_browser.sql` (T11b — novo)
- `stg/ddl/mgid_delivery_by_hour.sql` (T12 — novo)
- `stg/ddl/mgid_delivery_by_widget.sql` (T13 — novo)

---

## 2026-06-13 (cont.) — Raw jobs MGID A–G: DDLs criados, Job A aprovado

**Autor:** Douglas Reche

### Criado
- `raw/ddl/mgid_stats_daily.sql` — Job A (day + campaignId + impressions + clicks + spent + cpc + ctr + conversions*)
- `raw/ddl/mgid_stats_creative.sql` — Job B (day + campaignId + teaserId + mesmas métricas)
- `raw/ddl/mgid_stats_by_device.sql` — Job C (day + campaignId + deviceType)
- `raw/ddl/mgid_stats_by_geo.sql` — Job D (day + campaignId + country + region) ⚠️ 4 dims excedem limite API de 3 — a resolver
- `raw/ddl/mgid_stats_by_os.sql` — Job E (day + campaignId + os + browser) ⚠️ mesma restrição
- `raw/ddl/mgid_stats_by_hour.sql` — Job F (day + campaignId + hour)
- `raw/ddl/mgid_stats_by_widget.sql` — Job G (day + campaignId + widgetId + impressions + clicks + spent)

### Alterado
- `adframework_python/src/connectors/mgid.py` — `fetch_daily_rows()`: serialização de dict/list após coleta de rows (necessário para `spent` e `cpc` que a API retorna como objetos `{'amount': '...', 'currency': 'USD'}`)

### Job G — aprovado 2026-06-14
- `raw/ddl/mgid_stats_by_widget.sql` — grain: day + campaignid + widgetid; métricas: impressions, clicks, spent (sem conversões) → T13
**Config Firestore:**
```json
{ "platform": "mgid", "type": "mgid_daily", "name": "mgid_stats_by_widget",
  "bq_dataset": "raw", "bq_table": "mgid_stats_by_widget", "write_mode": "WRITE_APPEND",
  "params_json": { "rules": "dimensions[]=day&dimensions[]=campaignId&dimensions[]=widgetId&metrics[]=impressions&metrics[]=clicks&metrics[]=spent", "limit": 1000 } }
```

### Job A — revenue adicionado 2026-06-14
- `raw/ddl/mgid_stats_daily.sql` atualizado: adicionados `revenue`, `profit`, `roas`
- Decisão: separação delivery vs revenue no STG (não no raw) — MGID não tem `revenuesource` (grain idêntico para todos os KPIs)
- T3 stg.mgid_delivery = delivery metrics; T8 stg.mgid_revenue = spent + cpc + revenue + profit + roas
- Config Firestore Job A atualizada:
```json
{ "params_json": { "rules": "dimensions[]=day&dimensions[]=campaignId&metrics[]=impressions&metrics[]=clicks&metrics[]=spent&metrics[]=cpc&metrics[]=ctr&metrics[]=revenue&metrics[]=profit&metrics[]=roas&metrics[]=conversionsInterest&metrics[]=conversionsDecision&metrics[]=conversionsBuy", "limit": 1000 } }
```

### ✅ Todos os raw jobs MGID aprovados (A, B, C, D, D-lookup, E1, E2, F, G)
DDLs raw criados. Próximo: executar DDLs no BQ + criar docs Firestore + dedup raw tables.

### Job F — aprovado 2026-06-14
- `raw/ddl/mgid_stats_by_hour.sql` — grain: day + campaignid + hour → T12
**Config Firestore:**
```json
{ "platform": "mgid", "type": "mgid_daily", "name": "mgid_stats_by_hour",
  "bq_dataset": "raw", "bq_table": "mgid_stats_by_hour", "write_mode": "WRITE_APPEND",
  "params_json": { "rules": "dimensions[]=day&dimensions[]=campaignId&dimensions[]=hour&metrics[]=impressions&metrics[]=clicks&metrics[]=spent&metrics[]=conversionsInterest&metrics[]=conversionsDecision&metrics[]=conversionsBuy", "limit": 1000 } }
```

### Jobs E1 + E2 — aprovados 2026-06-14
- OS e browser são atributos independentes — sem hierarquia, lookup não resolve (diferente do geo)
- `raw/ddl/mgid_stats_by_os.sql` — atualizado: removido browser; grain: day + campaignid + os → T11
- `raw/ddl/mgid_stats_by_browser.sql` — NOVO: grain: day + campaignid + browser → T11b
- STG terá duas tabelas independentes: stg.mgid_delivery_by_os (T11) e stg.mgid_delivery_by_browser (T11b)

**Config Firestore Job E1:**
```json
{ "platform": "mgid", "type": "mgid_daily", "name": "mgid_stats_by_os",
  "bq_dataset": "raw", "bq_table": "mgid_stats_by_os", "write_mode": "WRITE_APPEND",
  "params_json": { "rules": "dimensions[]=day&dimensions[]=campaignId&dimensions[]=os&metrics[]=impressions&metrics[]=clicks&metrics[]=spent&metrics[]=conversionsInterest&metrics[]=conversionsDecision&metrics[]=conversionsBuy", "limit": 1000 } }
```

**Config Firestore Job E2:**
```json
{ "platform": "mgid", "type": "mgid_daily", "name": "mgid_stats_by_browser",
  "bq_dataset": "raw", "bq_table": "mgid_stats_by_browser", "write_mode": "WRITE_APPEND",
  "params_json": { "rules": "dimensions[]=day&dimensions[]=campaignId&dimensions[]=browser&metrics[]=impressions&metrics[]=clicks&metrics[]=spent&metrics[]=conversionsInterest&metrics[]=conversionsDecision&metrics[]=conversionsBuy", "limit": 1000 } }
```

### Job D — aprovado 2026-06-14
- `raw/ddl/mgid_stats_by_geo.sql` — atualizado: removido `country` (API só retorna `region` com 3 dims); grain: day + campaignid + region
- `raw/ddl/mgid_geo_regions.sql` — NOVO: lookup global region_id → country_code + nomes
- Decisão: `/dictionaries/geo?type=countries` (sem filtro) → todos os países → `/dictionaries/geo?type=cities&countries[]=todos` → lookup completo independente de país ativo
- STG T10 fará JOIN raw.mgid_stats_by_geo + raw.mgid_geo_regions para entregar day + campaignId + country + region

**Config Firestore Job D:**
```json
{
  "platform": "mgid", "type": "mgid_daily", "name": "mgid_stats_by_geo",
  "bq_dataset": "raw", "bq_table": "mgid_stats_by_geo", "write_mode": "WRITE_APPEND",
  "params_json": {
    "rules": "dimensions[]=day&dimensions[]=campaignId&dimensions[]=region&metrics[]=impressions&metrics[]=clicks&metrics[]=spent&metrics[]=conversionsInterest&metrics[]=conversionsDecision&metrics[]=conversionsBuy",
    "limit": 1000
  }
}
```

### Job C — config Firestore aprovada
```json
{
  "platform": "mgid", "type": "mgid_daily", "name": "mgid_stats_by_device",
  "bq_dataset": "raw", "bq_table": "mgid_stats_by_device", "write_mode": "WRITE_APPEND",
  "params_json": {
    "rules": "dimensions[]=day&dimensions[]=campaignId&dimensions[]=deviceType&metrics[]=impressions&metrics[]=clicks&metrics[]=spent&metrics[]=conversionsInterest&metrics[]=conversionsDecision&metrics[]=conversionsBuy",
    "limit": 1000
  }
}
```

### Job B — config Firestore aprovada
```json
{
  "platform": "mgid", "type": "mgid_daily", "name": "mgid_stats_creative",
  "bq_dataset": "raw", "bq_table": "mgid_stats_creative", "write_mode": "WRITE_APPEND",
  "params_json": {
    "rules": "dimensions[]=day&dimensions[]=campaignId&dimensions[]=teaserId&metrics[]=impressions&metrics[]=clicks&metrics[]=spent&metrics[]=cpc&metrics[]=ctr&metrics[]=conversionsInterest&metrics[]=conversionsDecision&metrics[]=conversionsBuy",
    "limit": 1000
  }
}
```

### Job A — config Firestore aprovada
```json
{
  "platform": "mgid", "type": "mgid_daily", "name": "mgid_stats_daily",
  "bq_dataset": "raw", "bq_table": "mgid_stats_daily", "write_mode": "WRITE_APPEND",
  "params_json": {
    "rules": "dimensions[]=day&dimensions[]=campaignId&metrics[]=impressions&metrics[]=clicks&metrics[]=spent&metrics[]=cpc&metrics[]=ctr&metrics[]=conversionsInterest&metrics[]=conversionsDecision&metrics[]=conversionsBuy",
    "limit": 1000
  }
}
```

---

## 2026-06-13 — Análise de ingestão MGID + T1 atualizada + arquitetura gold definida 🏗️

**Autor:** Douglas Reche

### Novos achados

**1. Ingestão MGID confirmada como raw (sem filtros)**
- Leitura completa de `adframework_python/src/connectors/mgid.py` e `orchestrator.py`
- `fetch_campaigns()`: zero filtros por estado/data — ingere TODAS as campanhas da API
- Única transformação existente: `str(item[k])` converte campos nested (dict/list) para Python string repr — necessário porque BQ não aceita objetos sem schema definido; não é filtro de dados
- `fetch_teasers()` tem `seen_ids` set (dedup intra-run); `fetch_campaigns()` não precisa pois a API não pagina por id
- `_run_generic_report()` lê `write_mode` do Firestore do job (`str(report.get("write_mode") or "WRITE_APPEND")`) — é esta config que causa duplicação

**2. Causa da duplicação raw.mgid_campaigns (79.8×) confirmada**
- `write_mode=WRITE_APPEND` no Firestore doc do job `mgid_firstlevel_campaigns`
- Cada execução appenda TODAS as campanhas novamente — mesmo comportamento que `mediasmart_firstlevel_campaigns` tinha antes do fix (GRUPO D 2026-06-11)
- Fix: mudar para `WRITE_TRUNCATE` no Firestore + rodar dedup `SELECT DISTINCT *` uma vez
- Precedente MS: documentado em `mediasmart_stg_design.md` GRUPO D

**3. Análise completa de campos disponíveis na API MGID**
- Campaigns endpoint: confirmado que `language`, `trackingOptions` (utm_source/medium/campaign), `geoTargets` estão disponíveis na raw mas não estavam na STG T1
- Teasers endpoint: `reason_if_drop_karantin` (motivo de rejeição) não estava na T2
- Descartados intencionalmente: `domainsFilter`, `ipsFilter`, `widgetsFilterUid`, `sourceFilters` (blocklists operacionais), `targets/languageTargeting/browserTargeting` (targeting operacional, baixo valor analítico), `geoTargets` (array complexo, baixo ROI agora)
- `campaign_type` MGID (product/push/rich_media) não tem equivalente na MediaSmart — campo `type` MS era sempre "generic" (foi removido no design STG MS)

**4. Arquitetura gold definida**
- STG atual (stg.mediasmart_delivery, stg.mgid_delivery legada) e gold atual estão quebrados — o rebuild completo do STG é o caminho para o gold funcional
- Decisão: `client_id` será resolvido no STG (não no gold) — gold só agrega
- Novo `gold.fact_delivery` lerá de stg.ms_delivery (T6) + stg.mgid_delivery (T3 novo) sem JOINs em platform_client_links
- Novo `gold.dim_campaign` lerá de stg.ms_strategies (T4) + stg.mgid_campaigns (T1) — nomes reais de campanha do catálogo, não strategyname da delivery
- Assimetria de grain: MS usa strategyid como `platform_campaign_id`, MGID usa campaignid (sem nível de strategy)

### Alterações de código

| Arquivo | Tipo | Mudança |
|---|---|---|
| `stg/ddl/mgid_campaigns.sql` | ALTERADO | Adicionados: `language_id`, `utm_source`, `utm_medium`, `utm_campaign` (de `trackingOptions` JSON); `trackingOptions` adicionado ao CTE `campaigns_latest` com REPLACE para Python dict |

### Pendências geradas

| Item | Prioridade | Depende de |
|---|---|---|
| Mudar `write_mode` MGID campaigns+creatives para WRITE_TRUNCATE no Firestore | 🔴 Alta | Nada — pode fazer agora |
| Dedup `raw.mgid_campaigns` (`SELECT DISTINCT *`) | 🔴 Alta | — |
| Dedup `raw.mgid_creatives` (`SELECT DISTINCT *`) | 🔴 Alta | — |
| Executar DDLs T2–T4 em lote no BQ | 🔴 Alta | Após dedup |
| Reescrever `gold.fact_delivery` usando novos STGs | 🟡 Média | Após T3 MGID pronto |
| Reescrever `gold.dim_campaign` usando novos STGs | 🟡 Média | Após T1 MGID executado |

---

## 2026-06-12 — MGID STG T1–T4 planejados + análise de API para novos jobs 📋

**Autor:** Douglas Reche

### O que foi feito

Planejamento completo do pipeline STG MGID, seguindo os mesmos padrões do STG MediaSmart.
T1 executada em produção. T2–T4 com DDLs prontos aguardando execução em lote.
Análise completa do API doc MGID para mapear gaps e novos raw jobs possíveis.

### Tabelas STG criadas/planejadas

| Tabela | Grain | Status | Arquivo |
|---|---|---|---|
| `stg.mgid_campaigns` | 1 row/campanha | ✅ em produção | `stg/ddl/mgid_campaigns.sql` |
| `stg.mgid_creatives` | 1 row/criativo | DDL pronto | `stg/ddl/mgid_creatives.sql` |
| `stg.mgid_delivery` | day + campaign | DDL pronto | `stg/ddl/mgid_delivery.sql` |
| `stg.mgid_creative_delivery` | day + campaign + creative | DDL pronto | `stg/ddl/mgid_creative_delivery.sql` |

### Decisões de arquitetura

- Client linkage via `platform_client_links` direto (sem intermediário `event_id` como MS)
- Sem `updated_at` — API MGID não retorna timestamp de atualização
- Sem `strategy_id` — MGID não tem hierarquia de estratégia
- `spent` removido de T3/T4 — requer novo raw job via statistics-reports (T8 futuro)
- `creative_id` (teaserid) separado do T3 — pertence ao T4 (mesmo padrão T6/T7 MS)
- Todos os campos JSON em Python dict (single-quotes) — REPLACE necessário antes de JSON_VALUE
- Dedup por ROW_NUMBER: mgid_campaigns (79.8× dup), mgid_creatives (~26× dup)

### Alterações em tabelas MediaSmart existentes

| Arquivo | Mudança |
|---|---|
| `stg/ddl/ms_creatives.sql` (T5) | `thumbnail_url` → `image_url`; adicionado `ms_client_id` via JOIN stg.ms_campaigns; `name` → `creative_name` |

### Plano de novos raw jobs MGID (API statistics-reports)

| Job | Raw table | Dimensões | Prioridade |
|---|---|---|---|
| A | `raw.mgid_stats_daily` | day + campaignId | 🔴 Alta — resolve spent |
| B | `raw.mgid_stats_creative` | day + campaignId + teaserId | 🔴 Alta — resolve spent em T4 |
| C | `raw.mgid_stats_by_device` | day + campaignId + deviceType | 🟡 Média |
| D | `raw.mgid_stats_by_geo` | day + campaignId + country + region | 🟡 Média |
| E | `raw.mgid_stats_by_os` | day + campaignId + os + browser | 🟡 Média |
| F | `raw.mgid_stats_by_hour` | day + campaignId + hour | 🟡 Média |
| G | `raw.mgid_stats_by_widget` | day + campaignId + widgetId | 🟢 Baixa |

### Gaps confirmados vs MediaSmart (não disponíveis na API MGID)

`updated_at`, `strategy_id/name`, `conversion_source`, `app_vs_web`,
video quartis em drilldowns, `media_cost_brl`, geo nível cidade, `size` width/height em criativos.

### Próximos passos

1. Dedup raw tables: `mgid_campaigns` (79.8×) + `mgid_creatives` (~26×)
2. Executar DDLs T2–T4 em lote no BQ
3. Criar raw jobs A + B (statistics-reports com spent)
4. Criar DDLs T8 + T9–T13 após raw jobs
5. Gold `fact_delivery` — análise de alinhamento MS + MGID

### Arquivos tocados

`stg/ddl/mgid_campaigns.sql` (novo, em produção)
`stg/ddl/mgid_creatives.sql` (novo, aguarda execução)
`stg/ddl/mgid_delivery.sql` (substituiu versão legada, aguarda execução)
`stg/ddl/mgid_creative_delivery.sql` (novo, aguarda execução)
`stg/ddl/ms_creatives.sql` (atualizado — client_id + renomes)
`docs/mgid_stg_design.md` (novo — design doc completo)

---

## 2026-06-12 — Sanity check STG + dedup 4 raw tables Grupo A ✅

**Autor:** Douglas Reche

### Problema identificado

Sanity check comparou `SUM(impressions)` de cada drilldown STG vs `stg.ms_delivery` (período 2026).
4 raw tables tinham duplicatas por múltiplos triggers de backfill com WRITE_APPEND:

| Tabela | Antes (rows) | Fator dup | Depois (rows) |
|---|---|---|---|
| `raw.mediasmart_delivery_by_device` | 206.541 | 3.52× | 58.610 |
| `raw.mediasmart_delivery_by_os` | 273.799 | 3.76× | 72.741 |
| `raw.mediasmart_delivery_by_hour` | 5.430 | 2.00× | 2.715 |
| `raw.mediasmart_delivery_by_publisher` | 9.804.184 | 1.36× | 7.198.762 |
| `raw.mediasmart_delivery_by_geo` | 8.417.374 | ✅ limpa | 8.417.374 |
| `raw.mediasmart_creative_daily` | 394.347 | ✅ limpa | 394.347 |

### Fix aplicado

`CREATE OR REPLACE TABLE ... AS SELECT DISTINCT * FROM ...` em cada tabela afetada (BQ in-place).

### Resultado do sanity check (pós-dedup)

| View | Impressões | Status |
|---|---|---|
| `stg.ms_delivery_by_device` | 233.093.873 | ✅ |
| `stg.ms_delivery_by_os` | 233.093.873 | ✅ |
| `stg.ms_delivery_by_geo` | 233.093.873 | ✅ |
| `stg.ms_creative_delivery` | 233.093.873 | ✅ |
| `stg.ms_delivery` (2026) | 233.027.031 | ✅ δ = 0.029% (grains diferentes) |
| `stg.ms_delivery_by_publisher` | 199.546.530 | ✅ esperado — cobertura parcial publisher |
| `stg.ms_delivery_by_hour` (mai28+) | 4.160.659 | ✅ período menor |

### Arquivos tocados
- `docs/known_issues.md` — item S1 adicionado

---

## 2026-06-12 — STG MediaSmart T1-T13 — 12 views criadas em produção ✅

**Autor:** Douglas Reche | **Commit:** `8355d1c`

### Views criadas (todas em `adframework.stg`)

| View | # | Rows | Fonte RAW | Notas |
|---|---|---|---|---|
| `ms_clients` | T1 | 21 | `mediasmart_advertisers` | ms_client_id = slug(name)\_LEFT(id,8) |
| `ms_campaigns` | T3 | 115 | `mediasmart_campaigns` | ms_client_id via JOIN delivery→T1 |
| `ms_strategies` | T4 | 17 | JSON `strategies[]` em campaigns | UNNEST |
| `ms_creatives` | T5 | 4.434 | `mediasmart_creatives` | PK = `id` (não `creative_id`) |
| `ms_delivery` | T6 | 641.975 | UNION delivery+daily | ms_client_id via T1; substitui legada futuramente |
| `ms_creative_delivery` | T7 | 394.347 | `mediasmart_creative_daily` | KPIs por criativo; schema novo |
| `ms_revenue` | T8 | 9.247 | `mediasmart_revenue` | ms_client_id via T3 (sem eventid) |
| `ms_delivery_by_device` | T9 | 206.541 | `mediasmart_delivery_by_device` | |
| `ms_delivery_by_geo` | T10 | 8.417.374 | `mediasmart_delivery_by_geo` | |
| `ms_delivery_by_os` | T11 | 273.799 | `mediasmart_delivery_by_os` | |
| `ms_delivery_by_hour` | T12 | 5.430 | `mediasmart_delivery_by_hour` | dados a partir de 2026-05-28 |
| `ms_delivery_by_publisher` | T13 | 9.804.184 | `mediasmart_delivery_by_publisher` | |

### Drop map — views legadas

| View legada | Referenciada em | Substituta | Pode dropar quando |
|---|---|---|---|
| `stg.mediasmart_delivery` | `gold.fact_delivery` | `stg.ms_delivery` (T6) | Após gold migrar para T6 |
| `stg.mediasmart_revenue` | `gold.fact_delivery` | `stg.ms_revenue` (T8) | Após gold migrar para T8 |
| `stg.mediasmart_bid_supply` | não usada no gold | T14 (no radar) | Manter indefinidamente |
| `stg.mgid_delivery` | `gold.fact_delivery` | MGID STG (fase futura) | Manter até MGID STG |
| `stg.siprocal_delivery` | `gold.fact_delivery` | Siprocal STG (fase futura) | Manter até Siprocal STG |

### Achados na verificação do schema real vs DDL do repo

- `raw.mediasmart_advertisers`: tem `event_id` + `id` separados (não só `id`); sem `raw_ingested_at`. DDL corrigido.
- `raw.mediasmart_creatives`: PK real é `id` (sempre preenchido, 4.434 únicos); `creative_id` = NULL em 33.250 linhas.
- `raw.mediasmart_campaigns`: sem `raw_ingested_at`; dedup via `updated_at`.
- IDE linter mostra erros T-SQL falso-positivos em arquivos BigQuery Standard SQL — ignorar.

### Arquivos tocados
- `stg/ddl/ms_clients.sql` … `ms_delivery_by_publisher.sql` (12 arquivos novos)
- `raw/ddl/mediasmart_advertisers.sql` (schema corrigido)

---

## 2026-06-12 — MediaSmart: backfill 2026 Grupo A — CONCLUÍDO ✅ + fix timeout ETL 10s→60s

**Autor:** Douglas Reche | **Resultado:** todas as 6 tabelas RAW Grupo A com histórico completo 2026.

### Estado final

| Tabela | Rows | Período | Obs |
|---|---|---|---|
| `raw.mediasmart_delivery_by_device` | 206.541 | 2026-01-01 → 2026-06-11 | ✅ |
| `raw.mediasmart_delivery_by_os` | 273.799 | 2026-01-01 → 2026-06-11 | ✅ |
| `raw.mediasmart_delivery_by_hour` | 5.430 | 2026-05-28 → 2026-06-11 | ✅ — sem dados no MS antes de Mai/28 |
| `raw.mediasmart_delivery_by_geo` | 8.417.374 | 2026-01-01 → 2026-06-11 | ✅ — dedup necessário (ver abaixo) |
| `raw.mediasmart_creative_daily` | 394.347 | 2026-01-01 → 2026-06-11 | ✅ |
| `raw.mediasmart_delivery_by_publisher` | 9.804.184 | 2026-01-01 → 2026-06-11 | ✅ |

### Fix: REQUEST_TIMEOUT_SECONDS 10s → 60s

Drilldowns de alta cardinalidade (`geo`: country+area+city, `publisher`: company+url+exchange) geravam relatórios na API que excediam o timeout de 10s. Fix: `adframework_python/src/connectors/mediasmart.py` linha 16 — `REQUEST_TIMEOUT_SECONDS = 60`. Commit `7bee5f9`. Deploy: Cloud Run revision `adframework-etl-00238-n4h`.

### Problemas enfrentados durante o backfill

1. **Cloud Run timeout (30 min)**: tabelas de alto volume (`geo`, `publisher`) precisaram de múltiplos triggers sequenciais — o ETL carrega dia a dia e 162 dias de geo levam ~43 min. Estratégia: atualizar `force_from_date` no Firestore a cada parada e retrigger.

2. **Duplicatas em delivery_by_geo**: segundo trigger com `force_from_date=2026-04-14` sobrepôs dados do primeiro trigger (Jan-Apr 13). Detectadas via `COUNT(*) vs COUNT(DISTINCT combos)`. Fix: `CREATE OR REPLACE TABLE ... AS SELECT DISTINCT *` → deduplication bem-sucedida.

3. **HTTP 503 MediaSmart**: servidor da MediaSmart retornou `Login failed: HTTP 503 - Under maintenance` durante publisher backfill. Transiente — retrigger após 30s resolveu.

4. **delivery_by_hour sem dados antes de Mai/28**: confirmado que MediaSmart não tem dados hourly antes de 2026-05-28 para as contas monitoradas. Dados corretos e completos para o período disponível.

### Arquivos tocados
- `adframework_python/src/connectors/mediasmart.py` ← timeout 10→60s (commit 7bee5f9)
- Firestore `platform_reports`: todos os `force_from_date` removidos de 6 docs
- `raw.mediasmart_delivery_by_geo` ← deduplicada com `SELECT DISTINCT *`
- `docs/known_issues.md` ← B1 + T1 movidos para Resolvidos; detalhe de causa raiz e fix (commit 6227da7)
- `docs/mediasmart_stg_design.md` ← backfill section: resultado real, volume comparativo, lições aprendidas; caminhos: `REQUEST_TIMEOUT_SECONDS` e `RATE_LIMIT_DELAY` com commits de ref (commit 6227da7)
- `docs/INDEX.md` ← datas e descrições atualizadas (commit 6227da7)

---

## 2026-06-12 — MediaSmart: backfill 2026 Grupo A — estado, problemas de API timeout e Firestore corrigidos

**Autor:** Douglas Reche | **Contexto:** executar backfill desde 2026-01-01 das 6 tabelas Grupo A criadas na sessão anterior. ETL disparado via HTTP API sequencialmente.

### Estado do backfill ao final da sessão 2026-06-12

| Tabela | Linhas BQ | Intervalo | Status | Ação pendente |
|---|---|---|---|---|
| `mediasmart_delivery_by_device` | 196.653 | 2026-01-01 → 2026-06-11 | ✅ COMPLETO | Nenhuma |
| `mediasmart_delivery_by_os` | 190.169 | 2026-01-01 → 2026-06-11 | ✅ COMPLETO | Nenhuma |
| `mediasmart_delivery_by_hour` | DROPPED | — | ❌ RESET | Retrigger após API recover |
| `mediasmart_delivery_by_geo` | sem tabela | — | ❌ API timeout | Retrigger após API recover |
| `mediasmart_creative_daily` | 42.531 | 2026-01-01 → 2026-01-20 | ⚠️ PARCIAL | Retrigger — continuará de Jan 21 |
| `mediasmart_delivery_by_publisher` | 117.867 | 2026-01-01 → 2026-01-06 | ⚠️ PARCIAL | Retrigger — continuará de Jan 7 |

### Problemas encontrados

**1. API MediaSmart — timeouts em cascata às ~12:17 UTC**

Todos os 4 jobs que falharam apresentaram o mesmo erro: `HTTPSConnectionPool(host='api.mediasmart.io', port=443): Read timed out. (read timeout=10)`. A API ficou lenta nesse horário. Os jobs `device` e `os` completaram antes (~12:18-12:19). Os jobs `hour`, `geo`, `creative`, `publisher` foram atingidos pelo timeout.

**2. delivery_by_hour — dados parciais com intervalo errado**

Quando o backfill do `hour` foi disparado, tinha data de início errada (carregou Mai 28-Jun 11 em vez de Jan 1-Jun 11). Causa: o `force_from_date=2026-01-01` estava correto no Firestore, mas o job pode ter encontrado a tabela já existente com dados históricos (de um trigger anterior ao DROP), e o `_get_date_range` usou max_date+1 em vez de force_from_date. Tabela dropada ao final da sessão para garantir reload limpo.

**3. force_from_date deixado em todos os docs — risco de duplicata**

Os jobs `device` e `os`, após completar, tinham `force_from_date=2026-01-01` ainda ativo no Firestore. Se o cron diário fosse rodar, recarregaria desde Jan 1 e duplicaria todo o histórico. Corrigido ao final da sessão.

### Correções aplicadas ao final desta sessão (Firestore + BQ)

```
Ação executada                                Estado após ação
─────────────────────────────────────────────────────────────
remove force_from_date → device               next cron carrega de max_date+1
remove force_from_date → os                  next cron carrega de max_date+1
force_from_date 2026-01-01 → 2026-01-21 → creative_daily   continua de Jan 21 sem duplicar
force_from_date 2026-01-01 → 2026-01-07 → publisher         continua de Jan 7 sem duplicar
force_from_date mantido 2026-01-01 → hour    tabela foi dropada, reload completo
force_from_date mantido 2026-01-01 → geo     sem tabela, reload completo
DROP raw.mediasmart_delivery_by_hour          removida para garantir schema correto no reload
```

### Próximos passos — quando MediaSmart API estiver estável

1. **Verificar API com request teste** (ver seção "Como testar API" em `mediasmart_stg_design.md`)
2. **Retrigger os 4 jobs** via HTTP API:
   ```
   TOKEN=$(gcloud auth print-identity-token)
   BASE=https://adframework-etl-911847757485.us-central1.run.app

   # menor volume primeiro — respeitar rate limit 128 req/min
   curl -s -X POST "$BASE/jobs/mediasmart_daily%3Adelivery_by_hour/run" -H "Authorization: Bearer $TOKEN"
   curl -s -X POST "$BASE/jobs/mediasmart_daily%3Adelivery_by_geo/run" -H "Authorization: Bearer $TOKEN"
   curl -s -X POST "$BASE/jobs/mediasmart_daily%3Acreative_daily/run" -H "Authorization: Bearer $TOKEN"
   curl -s -X POST "$BASE/jobs/mediasmart_daily%3Adelivery_by_publisher/run" -H "Authorization: Bearer $TOKEN"
   ```
3. **Verificar BQ após cada job** (row count + date range)
4. **Verificar schema de delivery_by_hour** após reload: `event_id`, `campaign_id`, `strategy_id`, `hour`, `final_price`, `media_cost__brl` presentes
5. **Após todos completos:** confirmar que `force_from_date` foi removido de todos os 6 docs no Firestore

### Arquivos tocados
- `CHANGELOG.md` ← este
- Firestore `platform_reports`: `params_json.force_from_date` atualizado para 4 docs
- `raw.mediasmart_delivery_by_hour` ← DROPPED (será recriado no próximo trigger)

---

## 2026-06-11 (sessão 2) — MediaSmart: correção de schema das 6 tabelas RAW Grupo A + investigação de ingestão

**Autor:** Douglas Reche | **Contexto:** investigação de `delivery_by_os` sem coluna `os` → revelou problema sistêmico de schema em todas as 6 tabelas Grupo A → diagnóstico, fix e verificação completa.

### Problema identificado e resolvido

**Sintoma inicial:** `raw.mediasmart_delivery_by_os` ingerindo dados (52 linhas/dia, granularidade correta) mas sem coluna `operating_system` — impossível saber qual OS corresponde a cada linha.

**Investigação (todos os paths verificados):**
- ✅ Código ETL `base.py` `normalize_data` — sem column mapping, apenas normalização BQ-safe
- ✅ Código ETL `orchestrator.py` `_run_mediasmart_daily` — sem schema enforcement
- ✅ Código ETL `bigquery.py` `load_data` — para tabelas EXISTENTES: mantém só colunas do schema existente
- ✅ Código Shiro (Admin UI `rshiro-newad/adframework`) — sem DDL pré-criado para as 6 tabelas
- ✅ Firestore `iter_params`/`field_var` — metadados do Admin UI, ignorados pelo ETL
- ✅ API MediaSmart — endpoint `/api/analytics/custom-report` é **FLEXÍVEL** (não fixo), retorna headers human-readable por drilldown
- ✅ API confirmada via test direto (2026-06-10): `"Event ID"` → `event_id`, `"Operating system"` → `operating_system`, `"Device type"` → `device_type`, etc.

**Root cause real:**
As 6 tabelas tinham sido criadas previamente por outro processo (ETL Shiro `aat-console`) que usa um **dicionário de mapeamento inverso**: `"Event ID"` → `eventid`, `"Campaign ID"` → `controlid`, `"Strategy ID"` → `strategyid`. Quando nosso ETL rodou pela primeira vez e encontrou as tabelas existentes, `bigquery.py:load_data` chamou o caminho "EXISTENTE" → dropped todas as colunas que não estavam no schema antigo (`event_id`, `operating_system`, `device_type`, etc.). Resultado: dimensões ingeridas com granularidade correta mas labels completamente perdidas.

**Fix executado:**
1. Todas as 6 tabelas dropadas via BQ Python client
2. Jobs re-trigados via ETL HTTP API `POST /jobs/{job_name}/run` (endpoint descoberto nesta sessão)
3. Tabelas recriadas do zero pelo ETL com schema nativo da API após `normalize_data`

**ETL HTTP API — endpoint descoberto (não estava documentado):**
```
Base URL: https://adframework-etl-911847757485.us-central1.run.app
GET  /jobs                      → lista todos os jobs enabled
POST /jobs/{job_name}/run       → dispara job específico (síncrono, Cloud Run-safe)
POST /run-all                   → dispara todos os jobs enabled
POST /scheduler/run-due         → dispara jobs cujo schedule_cron é due agora

Formato job_name: {platform_id}_{update_type}:{name}
Exemplos:
  mediasmart_daily:delivery_by_device
  mediasmart_daily:creative_daily
  mediasmart_firstlevel:campaigns
  mgid_daily:daily
  siprocal_daily:Daily

Autenticação: Bearer token (gcloud auth print-identity-token)
```

### Schemas verificados (tabelas recriadas com nomes nativos da API)

| Tabela | Cols | IDs | Dimensão | KPIs | Financeiro |
|---|---|---|---|---|---|
| `mediasmart_delivery_by_device` | 21 | `event_id, campaign_id, strategy_id` | `device_type, app_vs_web` | impressions…conv5 + video | `final_price, media_cost__brl` |
| `mediasmart_delivery_by_geo` | 22 | `event_id, campaign_id, strategy_id` | `country, area_name, city` | impressions…conv5 + video | `final_price, media_cost__brl` |
| `mediasmart_delivery_by_os` | 20 | `event_id, campaign_id, strategy_id` | `operating_system` | impressions…conv5 + video | `final_price, media_cost__brl` |
| `mediasmart_delivery_by_hour` | 20 | `event_id, campaign_id, strategy_id` | `hour` | impressions…conv5 + video | `final_price, media_cost__brl` |
| `mediasmart_delivery_by_publisher` | 12 | `event_id, campaign_id, strategy_id` | `publisher_company, publisher_url, ad_exchange` | impressions, clicks | `final_price, media_cost__brl` |
| `mediasmart_creative_daily` | 23 | `event_id, campaign_id, strategy_id` | `creative_id, creative_type, size, app_vs_web` | impressions…conv5 + video | `final_price, media_cost__brl` |

### Mapeamento completo API → BQ (confirmado por test direto 2026-06-10)

```
Drilldown param → API CSV header    → normalize_data (base.py) → BQ column
day             → "Day"              → day
eventid         → "Event ID"         → event_id
controlid       → "Campaign ID"      → campaign_id
strategyid      → "Strategy ID"      → strategy_id
strategyname    → "Strategy"         → strategy
convsource      → "Conversion source"→ conversion_source
devicetype      → "Device type"      → device_type
os              → "Operating system" → operating_system
source          → "App vs. Web"      → app_vs_web
countrycode     → "Country"          → country
georegion_areaname → "Area Name"     → area_name
city            → "City"             → city
publishercompany→ "Publisher Company"→ publisher_company
publisherurl    → "Publisher URL"    → publisher_url
exchange        → "Ad Exchange"      → ad_exchange
hour            → "Hour"             → hour
creativeid      → "Creative ID"      → creative_id
creativetype    → "Creative Type"    → creative_type
size            → "Size"             → size

KPIs (API header → BQ):
clientrevenue   → "Event revenue"    → event_revenue
convertedclientrevenue → "Final Price" → final_price
client_cost     → "Media Cost - BRL" → media_cost__brl   ← nota: double underscore (espaço + hífen)
```

### Decisão de design documentada

**Princípio: NO mapping dictionary no ETL raw layer.**

O `normalize_data` em `base.py` faz apenas normalização BQ-safe (lowercase, spaces→_, remove chars especiais). NÃO faz renomeação semântica. Motivação:

> "pois se adicionarmos no dicionário toda vez que tivermos um novo temos que mudar novamente não?" — Douglas, 2026-06-11

Com mapping dict: cada nova dimensão da API requer mudança de código. Com normalize puro: nova dimensão aparece automaticamente no RAW com nome derivado do header da API. O STG SQL é onde aplicamos renomeação semântica explícita via SELECT col AS alias.

Shiro fez o mapeamento no ETL dele provavelmente para padronizar todas as plataformas em uma nomenclatura comum — mas o lugar correto é o STG layer, não o RAW.

### Inconsistência de nomes entre fontes RAW (importante para STG)

| Tabela RAW | ID columns | Origem |
|---|---|---|
| `raw.mediasmart_delivery` | `eventid, controlid, strategyid, strategyname` | Schema antigo (Shiro mapping) |
| `raw.mediasmart_daily` | `eventid, controlid, strategyid, strategyname` | Schema antigo (Shiro/aat-console ainda popula) |
| `raw.mediasmart_delivery_by_*` | `event_id, campaign_id, strategy_id` | Schema novo (normalize_data puro) |
| `raw.mediasmart_creative_daily` | `event_id, campaign_id, strategy_id, creative_id` | Schema novo (normalize_data puro) |

**Impacto no STG:** T6 (`stg.ms_delivery`) usa `controlid`/`strategyid` das fontes antigas. T7/T9/T10/os/hour/publisher usam `campaign_id`/`strategy_id` das fontes novas. Ambos são o mesmo valor — nomes diferentes, mesma chave.

### Repositório e caminhos dos arquivos-chave

```
Repo: rshiro-newad/adframework  (local: c:\Users\dougl\OneDrive\Área de Trabalho\NEWAD PROJECT\DATASETS\adframework)
Branch ativa: chore/machine-restore-org

Arquivos do ETL Python:
  adframework_python/src/base.py           → normalize_data (normalização BQ-safe, sem mapping)
  adframework_python/src/connectors/mediasmart.py → RATE_LIMIT_DELAY=0.6, fetch_data, _build_url
  adframework_python/src/bigquery.py       → load_data (lógica NEW vs EXISTING table + column drop)
  adframework_python/src/orchestrator.py   → _resolve_bq_target, _get_date_range, _run_mediasmart_daily
  adframework_python/main.py               → FastAPI routes: /jobs, /jobs/{job_name}/run, /run-all

GCP:
  Cloud Run service: adframework-etl-911847757485.us-central1.run.app
  Firestore collection: platform_reports (doc_id = mediasmart_delivery_by_device etc.)
  BigQuery: adframework.raw.mediasmart_delivery_by_*  adframework.raw.mediasmart_creative_daily
```

### Linhas de dados carregadas após fix (2026-06-10 only — backfill pendente)

| Job | Linhas D-1 (2026-06-10) |
|---|---|
| `mediasmart_daily:delivery_by_device` | 31 |
| `mediasmart_daily:delivery_by_geo` | 728 |
| `mediasmart_daily:delivery_by_os` | 51 |
| `mediasmart_daily:delivery_by_hour` | 107 |
| `mediasmart_daily:delivery_by_publisher` | 9.820 |
| `mediasmart_daily:creative_daily` | 606 |

### Próximos passos documentados (backfill + STG)

Ver seção "Plano de Backfill Grupo A" em `mediasmart_stg_design.md`.

### Arquivos tocados (este repo — newad-adframework-bq)
- `docs/known_issues.md` ← issue #16 marcada como ✅ resolvida
- `docs/mediasmart_stg_design.md` ← Group A atualizado, schemas corretos, colnames, backfill plan
- `docs/CHANGELOG.md` ← este

---

## 2026-06-11 — MediaSmart: 6 novos jobs RAW, fixes Grupo D, rate limit fix, backfill

**Autor:** Douglas Reche | **Contexto:** expansão da ingestão MediaSmart — novos drilldowns e correções estruturais

### O que mudou

**1. Grupo A — 6 jobs bulk criados no Firestore e testados via Cloud Run**

| Job (Firestore doc id) | Tabela RAW | Drilldown principal | Schedule | Linhas D-1 |
|---|---|---|---|---|
| `mediasmart_creative_daily` | `raw.mediasmart_creative_daily` | creativeid, creativetype, size, source | 03:30 UTC | 12 |
| `mediasmart_delivery_by_device` | `raw.mediasmart_delivery_by_device` | devicetype, source | 03:35 UTC | 12 |
| `mediasmart_delivery_by_geo` | `raw.mediasmart_delivery_by_geo` | countrycode, georegion_areaname, city | 03:40 UTC | 739 |
| `mediasmart_delivery_by_publisher` | `raw.mediasmart_delivery_by_publisher` | publishercompany, publisherurl, exchange | 03:45 UTC | 10.735 |
| `mediasmart_delivery_by_os` | `raw.mediasmart_delivery_by_os` | os | 03:50 UTC | 52 |
| `mediasmart_delivery_by_hour` | `raw.mediasmart_delivery_by_hour` | hour | 03:55 UTC | 147 |

Todos usam `endpoint_id: mediasmart_ep_api-analytics-custom-report`, `update_type: daily`.
`convsource` adicionado ao drilldown de cada job (não é KPI — confirmado em produção com erro 400).
Schema do CSV é fixo (31 colunas) independente do drilldown — o drilldown controla granularidade.

**2. Grupo B — Rate limit fix (pré-requisito para Jobs 7-8)**

Commit `4d1662f` em `rshiro-newad/adframework`, branch `chore/machine-restore-org`:
- `adframework_python/src/connectors/mediasmart.py` — `RATE_LIMIT_DELAY` 0.3 → 0.6
- `adframework_python/src/orchestrator.py` — `time.sleep(0.3/0.15)` → 0.6 nos loops de iteração
- Deployado em Cloud Run revision `adframework-etl-00237-v88`

**3. Grupo D — Fixes em jobs existentes**

- `mediasmart_firstlevel_advertisers` → Firestore `write_mode: WRITE_TRUNCATE`
- `mediasmart_firstlevel_creatives` → Firestore `write_mode: WRITE_TRUNCATE`
- `mediasmart_firstlevel_campaigns` → Firestore `write_mode: WRITE_TRUNCATE` + BQ dedup: `CREATE OR REPLACE TABLE raw.mediasmart_campaigns ... WHERE rn = 1` (5.451 → 140 linhas)
- Gap 25–26/mai/2026 em `raw.mediasmart_daily` → `force_from_date` implementado em `_get_date_range` (orchestrator.py, mesmo commit `4d1662f`), job temporário `mediasmart_backfill_may2526` rodado e deletado, 26 linhas carregadas

**4. Descobertas documentadas**

- `convsource` é dimensão de drilldown, não KPI (API retorna 400 se colocado em `kpis`)
- `/api/analytics/custom-report` retorna schema fixo de 31 colunas; drilldown afeta agrupamento, não schema
- `os` como drilldown gera granularidade (52 linhas vs 7 do job principal) mas coluna `os` não aparece no CSV fixo — pendente investigar nome correto
- `force_from_date` em `params_json` permite backfills pontuais em qualquer job `update_type: daily`

**Arquivos tocados (este repo):**
- `docs/mediasmart_stg_design.md` ← atualizado (jobs 1-6 como ✅, Grupo D como ✅, pré-req B como ✅)
- `docs/known_issues.md` ← atualizado (issues 15, D1, D2 como resolvidas)
- `docs/INDEX.md` ← atualizado
- `CHANGELOG.md` ← este

**Arquivos tocados (repo `rshiro-newad/adframework`, commit `4d1662f`):**
- `adframework_python/src/connectors/mediasmart.py`
- `adframework_python/src/orchestrator.py`

---

## 2026-06-11 — Mapa de atribuição de IDs RAW→client_id + auditoria de cobertura

**Autor:** Douglas Reche | **Contexto:** auditoria de IDs antes de expandir o GOLD

### O que mudou

**1. `docs/id_attribution_map.md` — criado**
- Mapa completo da cadeia de atribuição para cada plataforma (MediaSmart, MGID, Siprocal, IO Plan)
- Tabela de cobertura de vínculos para os 26 clientes em `dim_client`
- Problemas identificados:
  - `ocupacional_98c851f5` sem nenhum vínculo em `platform_client_links` (100% unattributed)
  - `eventid` MediaSmart compartilhado Pardini/Ocupacional com `client_id` NULL (unresolved)
  - `fact_delivery.sql` usando `strategyid` em vez de `controlid` como `platform_campaign_id` para MediaSmart
  - 44 MGID campaignids ainda em `pending_confirmation`
- Lista priorizada de ações: 3 imediatas (A1-A3), 4 aguardando comercial (B1-B4), 4 contínuas (C1-C4)

**Arquivos tocados:**
- `docs/id_attribution_map.md` ← novo
- `docs/INDEX.md` ← atualizado
- `CHANGELOG.md` ← atualizado

---

## 2026-06-11 — Mapa de linhagem de colunas RAW→GOLD

**Autor:** Douglas Reche | **Contexto:** auditoria de cobertura de colunas — suspeita de perda de informações entre camadas

### O que mudou

**1. `docs/column_lineage_map.md` — criado**
- **Problema:** não havia documentação rastreando quais colunas do RAW sobrevivem até o GOLD. Suspeita de perda de métricas antes dos KPIs.
- **Conteúdo:** diagrama de arquitetura em camadas, cadeia de atribuição de cliente, tabelas de linhagem por plataforma (MediaSmart delivery/revenue/bid_supply, MGID, Siprocal, IO Plan), matriz de cobertura de métricas por view GOLD, e resumo priorizado de 9 lacunas identificadas.
- **Lacunas críticas documentadas:**
  - `mediasmart_bid_supply` inteiro fica órfão na STG (win rate, media cost, publisher performance nunca chegam no GOLD)
  - `unit_price` e `impressions_cpm` do IO plan não mapeados (CPM planejado impossível)
  - `video_*` ausentes no `fact_delivery` principal (Cora e Fintech sem métricas de vídeo)
  - Conversões MGID em colunas separadas (`mgid_conv_*`) — funis cross-platform somam só MediaSmart
  - `conversions_1-5` ausentes no `fct_cora_delivery_full`

**Arquivos tocados:**
- `docs/column_lineage_map.md` ← novo
- `docs/INDEX.md` ← atualizado
- `CHANGELOG.md` ← atualizado

---

## 2026-06-08 — Ativação de links Amigo + workaround MediaSmart + auditoria de APIs

**Autor:** Douglas Reche | **Contexto:** sprint de entrega dashboard Cora/TecPar (prazo 2026-06-11)

### O que mudou

**1. `core.platform_client_links` — 39 links Amigo ativados**
- **Problema:** `amigo_db1c2f0c` tinha 39 vínculos em `pending_confirmation` desde 2026-05-26 (1 eventid MediaSmart + 38 campaignids MGID). Toda entrega de Amigo aparecia como `unattributed` na gold.
- **Decisão:** Amigo é sub-cliente legítimo de TecPar (relação pai-filho confirmada por Douglas), não um erro de atribuição. Confirmação comercial já tinha acontecido do lado do Shiro. Os vínculos ficaram travados por falta de sincronização.
- **Ação:** `core/migration/05_activate_amigo_links.sql` — UPDATE de 39 linhas para `status = 'active'`.
- **Resultado:** `amigo_db1c2f0c` agora tem 40 links ativos (1 MS + 38 MGID + 1 Siprocal).

**2. `stg.mediasmart_delivery` — workaround para gap de dados**
- **Problema:** Job `mediasmart_daily_daily` no orchestrator (Shiro) com timeout desde ~01/jun/26. `raw.mediasmart_delivery` parado em 2026-05-24. `raw.mediasmart_daily` (staging intermediário do mesmo job) continua sendo alimentado.
- **Decisão:** Aplicar workaround na STG enquanto root cause é resolvido no orchestrator.
- **Ação:** `stg/ddl/mediasmart_delivery.sql` atualizado — adicionado `UNION ALL` com `raw.mediasmart_daily` filtrando datas > 2026-05-24. Comentário no SQL indica que este branch deve ser removido quando o orchestrator for corrigido.
- **Resultado:** `stg.mediasmart_delivery` agora cobre até 2026-06-07.

**3. `gold.fact_delivery` — reconstruída**
- **Ação:** `gold/ddl/fact_delivery.sql` executado em prod. Absorveu os dois fixes acima.
- **Resultado:** Cora e Amigo aparecem no gold com dados até 2026-06-07. TecPar hierarchy correta (Amigo level 2, TecPar level 1).

**4. Auditoria de APIs — MediaSmart e MGID**
- **Ação:** OpenAPI spec do MediaSmart (github.com/mediasmart/api-reference) e docs MGID analisados.
- **Resultado:** documentado em `docs/api_capabilities.md` e `docs/etl_expansion_plan.md`.

**Arquivos tocados:**
- `core/migration/05_activate_amigo_links.sql` ← novo
- `stg/ddl/mediasmart_delivery.sql` ← alterado
- `docs/known_issues.md` ← atualizado
- `docs/api_capabilities.md` ← novo
- `docs/etl_expansion_plan.md` ← novo
- `docs/commercial_questions.md` ← novo
- `CHANGELOG.md` ← novo
- `docs/INDEX.md` ← novo

**Issues abertas geradas:**
- `#8` `gold.fact_io_plan` — view quebrada, zero linhas (chain morta via `raw.luckbet_io_plan_snapshot` dropada)
- `#9` MediaSmart ETL timeout — root cause aberta no orchestrator (Shiro)

---

## 2026-06-03 — Gold layer unificada + pipeline health + conversions mapping

**Autor:** Douglas Reche

### O que mudou

**1. `gold.fact_delivery` — criada (substituindo views fragmentadas)**
- **Problema:** gold tinha views separadas por cliente (`fct_cora_delivery_full`, `fct_luckbet_delivery_full`) sem modelo unificado. Power BI conectava a múltiplas fontes inconsistentes.
- **Decisão:** criar tabela materializada única `gold.fact_delivery` com grain `day + client_id + platform + platform_campaign_id`, cobrindo MediaSmart + MGID + Siprocal. Revenue MediaSmart agora joinado DEPOIS da agregação de delivery para evitar multiplicação por número de eventids.
- **Arquivo:** `gold/ddl/fact_delivery.sql`

**2. `gold.dim_campaign` — criada**
- **Arquivo:** `gold/ddl/dim_campaign.sql`

**3. `gold.dim_conversion_mapping` — criada**
- Mapeamento de conv_1-5 por cliente para labels de negócio. Luckbet mapeado. Outros clientes pendentes de confirmação comercial.
- **Arquivo:** `gold/ddl/dim_conversion_mapping.sql` + `core/seeds/conversion_mapping.csv`

**4. `gold.pipeline_health` — view de monitoramento**
- **Arquivo:** `gold/ddl/pipeline_health.sql`

**5. `docs/pipeline_complete_map.md` — mapeamento completo do pipeline**
- 1.300+ linhas documentando cada tabela, grain, fonte, período e issues abertas.

**Arquivos tocados:**
- `gold/ddl/fact_delivery.sql` ← novo
- `gold/ddl/dim_campaign.sql` ← novo
- `gold/ddl/dim_conversion_mapping.sql` ← novo
- `gold/ddl/pipeline_health.sql` ← novo
- `core/seeds/conversion_mapping.csv` ← novo
- `docs/pipeline_complete_map.md` ← novo
- `docs/known_issues.md` ← atualizado

---

## 2026-05-26 — RAW + STG rebuild: sistema canônico de IDs de cliente

**Commit:** `7ac505c` | **Autor:** Douglas Reche

### O que mudou e por quê

**Decisão central:** Adotar `{slug}_{hash8}` como formato canônico de `client_id` (ex: `banco_cora_fe13d78a`). O formato anterior do Shiro (`nwd_{slug-com-hifens}_{hash8}`) continua existindo no Admin UI mas nunca é usado no pipeline ETL. JOINs diretos entre os dois sistemas são impossíveis por design.

**1. `core.dim_client` + `core.platform_client_links` — criadas**
- `dim_client`: tabela de clientes com hierarquia pai-filho (`parent_client_id`, `client_level`), slugs imutáveis, seed via CSV.
- `platform_client_links`: mapeamento `(platform, link_type, link_value)` → `client_id` com campo de status (`active`/`pending_confirmation`/`unresolved`).
- **Arquivos:** `core/ddl/dim_client.sql`, `core/seeds/clients.csv`, `core/migration/01_load_dim_client.sql`

**2. Raw DDLs formalizados para todas as plataformas**
- `raw.mediasmart_delivery` — grain: day+eventid+controlid+strategyid+convsource
- `raw.mediasmart_revenue` — grain: day+controlid+strategyid+revenuesource
- `raw.mediasmart_bid_supply` — dados de leilão horário
- `raw.mgid_delivery` — grain: day+campaignid+(teaserId opcional)
- `raw.siprocal_delivery` — grain: day+advertiser+campaign_id+creative_type+creative
- + DDLs de dimensões: mediasmart_advertisers, campaigns, creatives; mgid_campaigns, creatives
- **Decisão:** RAW = dado bruto, sem filtro, sem transformação. Todo filtro vai para STG.

**3. STG views normalizadas**
- Typing (SAFE_CAST), limpeza de nulos, padronização de nomes de campo.
- `stg.mediasmart_delivery`, `stg.mediasmart_revenue`, `stg.mediasmart_bid_supply`, `stg.mgid_delivery`, `stg.siprocal_delivery`

**4. Migração de limpeza**
- `raw/migration/01_create_canonical_tables.sql` — cria estrutura canônica
- `raw/migration/02_drop_legacy_and_orphans.sql` — dropa tabelas órfãs (incluindo `raw.luckbet_io_plan_snapshot` ← causa da quebra futura de `gold.fact_io_plan`)

**Arquivos tocados:** ver commit `7ac505c` — 22 arquivos alterados/criados.

---

## 2026-05-21 — ETL Cora via Google Sheets → BigQuery

**Commits:** `b2c96e9`, `f26b69b` | **Autor:** Douglas Reche

### O que mudou e por quê

**Problema:** Cora precisava de dados de delivery históricos (ago/25–fev/26) que nunca foram formalizados em um IO no Admin UI. A pipeline padrão não capturava esses dados.

**Decisão:** workaround operacional — exportar dados de device, regiões e consolidado geral da plataforma MediaSmart para Google Sheets, e sincronizar para BQ via script Python com autenticação gcloud.

**Arquivos criados:**
- `scripts/etl/cora_sheets_sync.py` — sync principal (Cloud Run/GitHub Actions)
- `scripts/etl/cora_sheets_sync_local.py` — versão local com token gcloud
- `scripts/etl/apps_script_trigger.js` — trigger Google Workspace
- `.github/workflows/cora_sheets_sync.yml` — CI/CD GitHub Actions

**Limitação conhecida:** solução manual, não escalável. Depende de export manual para Sheets.

---

## 2026-05-20 — Gold MVP: workarounds Cora gap + Luckbet duplication

**Commits:** `c2c933a`, `7c4d182`, `3df2b43` | **Autor:** Douglas Reche

### O que mudou e por quê

**Problema #1 — Cora:** pipeline padrão mostrava apenas ~823K impressões para Cora porque o único IO (mar/26) cobria só março. Dados de ago/25–fev/26 existiam no raw mas nunca chegavam ao gold.

**Problema #2 — Luckbet:** entrega duplicada — mesmo delivery aparecia contado 2× por causa de dois `client_id` para o mesmo cliente (`nwd_luckbet_a485d6bc` canônico + `nwd_luckbet_69e72f18` legacy).

**Decisão:** criar views MVP específicas por cliente com lógica de atribuição explícita, como ponte até a pipeline canônica ficar pronta.

**Arquivos criados:**
- `gold/delivery/fct_cora_delivery_full.sql` — 3 paths de atribuição (MediaSmart via eventid, MGID/Siprocal registrados via io_binding_registry_v4, MGID/Siprocal não-registrados via hardcode)
- `gold/delivery/fct_luckbet_delivery_full.sql` — entrega Luckbet sem duplicação
- `gold/delivery/fct_delivery_daily_mvp.sql` — view unificada temporária

**Nota arquitetural:** `fct_cora_delivery_full.sql` ainda referencia `core.io_binding_registry_v4` (Admin UI do Shiro) — viola a separação de responsabilidades definida em 2026-05-26. Esta view é um workaround legado e **não deve ser expandida**.

---

## 2026-05-12/13 — Auditoria completa, ERD e sistema de IDs

**Commits:** `8d84e24` a `117987e` | **Autor:** Douglas Reche

### O que mudou e por quê

**Contexto:** Primeiro commit no repositório GitHub. Projeto já existia no BigQuery (desde ~2025) mas sem versionamento de código.

**O que foi documentado:**
- `docs/bigquery_analysis.md` (gerado 2026-04-30) — inventário dos 14 datasets, 97 tabelas, 116 views. Identificação dos dois pipelines paralelos em produção.
- `docs/known_issues.md` — problemas conhecidos: Luckbet duplicada, Cora sem histórico, Siprocal sem ID estruturado, etc.
- `docs/gold_mvp_apresentacao.md` — análise da gold layer MVP, star schema inicial.
- ERD completo: `docs/adframework_erd.dbml` (164 tabelas, 116 relacionamentos), `docs/adframework_erd_mermaid.md`
- `docs/id_quality_issues.md`, `docs/id_dependency_map.md` — análise de qualidade de IDs e dependências RAW→GOLD

**Descobertas críticas documentadas:**
- **Dois pipelines paralelos em produção:** Pipeline A (legado, `init_bq.py`, quebrado) + Pipeline B (V4, Admin UI Shiro, ativo)
- `marts.fact_delivery_daily_v2` nunca foi criado em prod — 14 funções Python definidas mas nunca chamadas no `main()`
- `share.*` inteiro quebrado como consequência

---

## 2026-05-04/05 — Reunião de viabilidade: decisão de construir nova pipeline

**Doc:** `docs/viability_assessment_terça.md` | **Presentes:** Douglas, Shiro, Alexandre

### Decisão tomada

Construir a nova pipeline ETL canônica (RAW→STG→CORE→GOLD) em paralelo ao sistema legado, sem quebrar o Admin UI do Shiro. A reestruturação do BQ é viável em ~3 semanas.

**Pré-requisitos definidos na reunião:**
1. Nova pipeline ETL escreve APENAS em `raw.*`, `stg.*`, `core.*`, `gold.*` (datasets do Douglas)
2. Admin UI do Shiro continua escrevendo em `core.io_manager_v2` e derivados — nunca referenciar no pipeline gold
3. `gold.fact_io_plan` será reconstruída usando dados do IO plan do Shiro como fonte
4. Manter `raw.*` como único ponto de verdade (dropar raw_mediasmart, raw_mgid, raw_siprocal)

**Achado arquitetural:** `marts.io_delivery_daily_v4` (view central do pipeline V4 do Shiro) depende de `share.newad_operational_daily` — inversão arquitetural que funciona em prod mas precisa ser respeitada na ordem de criação no staging.

---

## 2026-04-28/30 — Gold Layer MVP inicial + auditoria BQ

**Docs:** `docs/gold_mvp_apresentacao.md`, `docs/bigquery_analysis.md`, `docs/prod_audit_and_restructuring_plan.md`

### O que foi feito

**Contexto:** primeiro esforço de criar uma gold layer utilizável para Power BI. O BQ tinha ~50 views encadeadas sem materialização física tornando queries de BI impossíveis.

**Arquitetura gold MVP definida:**
- Star schema: `fact_delivery_daily` + `dim_client` + `dim_date` + `dim_platform` + `dim_io_line`
- Grain: `date × IO line × platform`
- Modo Power BI: Import (não DirectQuery — pacing acumulado com DAX inviabiliza DirectQuery)
- `gold.fact_io_plan` planejada para conter dados de planejamento (investimento previsto, impressões previstas, cliques previstos)

**Estado identificado do BQ (2026-04-30):** 14 datasets, ~2.576 MB total, raw_mediasmart/raw_mgid/raw_siprocal congelados desde 2026-04-21 (reestruturação iniciada e abandonada).

---

## ~2025-08 — Início da operação: dados MediaSmart entram no BQ

**Não versionado** — reconstruído a partir de datas de dados no BQ

- Primeiros dados de `raw.mediasmart_delivery`: 2025-08-01
- Pipeline operacional: MediaSmart → `raw.mediasmart_daily` → processamento manual
- MGID: dados desde 2025-09-30
- Siprocal: dados desde 2025-08-22
- Sistema de IDs nessa época: baseado no Admin UI do Shiro (`nwd_*` format)
