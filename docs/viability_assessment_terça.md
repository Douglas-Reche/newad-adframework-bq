# AdFramework — Avaliação de Viabilidade da Reestruturação
**Reunião:** Terça-feira, 2026-05-05  
**Elaborado por:** Douglas Reche  
**Presentes:** Shiro · Alexandre  
**Base:** Auditoria completa de BQ prod + repositório GitHub (`prod_audit_and_restructuring_plan.md`)

---

## Veredicto Geral

**O plano é tecnicamente viável.** Todas as SQLs das views V4 foram extraídas do BQ prod e confirmadas — não há nenhum objeto "perdido" que impeça a implementação. O repositório GitHub já tem CI/CD de staging configurado. A execução requer ~3 semanas de trabalho com equipe dedicada.

**Há 4 pré-requisitos que precisam ser decididos na reunião antes de começar.**

---

## O Que Foi Confirmado Como Viável

| Item | Status | Evidência |
|------|--------|-----------|
| SQL de todas as views V4 extraíveis do BQ prod | ✅ Confirmado | `INFORMATION_SCHEMA.VIEWS` consultado |
| CI/CD de staging já existe no repositório | ✅ Confirmado | `.github/workflows/deploy-cloud-run.yml` branch `staging` |
| Gold layer DDL documentado e correto | ✅ Confirmado | `docs/gold_layer_ddl.sql` |
| As 3 mudanças do `orchestrator.py` são cirúrgicas | ✅ Confirmado | Código lido linha a linha |
| `init_bq.py` pode ser reescrito em ~900 linhas | ✅ Confirmado | Escopo delimitado |
| ~1.147 MB deletáveis de prod sem risco | ✅ Confirmado | Auditoria detalhada |

---

## Achado Novo: Dependência Invertida no Pipeline V4

Durante a extração das SQLs, foi identificado que `marts.io_delivery_daily_v4` — a view central do pipeline — depende de **duas views na camada `share`**:

```
share.newad_operational_daily    ← combina MediaSmart + MGID + Siprocal
share.platform_campaign_catalog  ← catálogo de campanhas conhecidas
```

Isso é uma **inversão arquitetural**: a camada `marts` deveria ser a base da `share`, não o contrário. Em prod isso funciona porque as dependências circulares entre layers são permitidas pelo BigQuery. No staging limpo, a sequência de criação precisa respeitar essa dependência invertida — `share.*_operational_daily` e `share.*_campaign_catalog` precisam ser criadas **antes** de `marts.io_delivery_daily_v4`.

**Impacto no plano:** O `init_bq.py` reescrito precisa seguir a ordem exata:
```
raw → stg → core → share.newad_operational_daily + share.platform_campaign_catalog
→ marts.io_delivery_daily_v4 → marts.io_schedule_daily_v4 → share.restante → gold
```

Isso não é um bloqueador — é apenas uma ordem de criação que precisa ser respeitada.

---

## Os 4 Pré-Requisitos Para Decidir na Reunião

### 1. Quem cria o projeto GCP `adframework-stg`? (Bloqueador de Sprint 1)

Criar um projeto GCP requer acesso de **org admin** ou conta de faturamento ativa no Google Cloud. Se ninguém do time tem esse acesso, o projeto pode ser criado dentro da org existente do `adframework`.

**Opções:**
- A) Criar projeto novo `adframework-stg` (recomendado — isolamento total)
- B) Usar o próprio projeto `adframework` com datasets nomeados `stg_raw`, `stg_gold`, etc. (mais simples, menos isolado)

**Pergunta para a reunião:** Alexandre ou Shiro tem acesso de owner no GCP do adframework?

---

### 2. Como o ETL do staging vai se autenticar nas APIs? (Bloqueador de Sprint 2)

O ETL de staging precisa das credenciais do MediaSmart, MGID e Siprocal para buscar dados. Existem duas abordagens:

**Opção A — ETL duplo (recomendado durante validação):**
Staging usa as mesmas credenciais de API, mas escreve em `adframework-stg.raw.*`. Ambos ETLs rodam em paralelo. Custo: dobra as chamadas de API por ~3-5 dias de validação.

**Opção B — Copiar dados de prod para staging:**
Não roda ETL no staging. Usa `bq cp` para copiar os dados de `raw.*` de prod para staging. Mais simples, mas não testa o pipeline de ingestão.

**Pergunta para a reunião:** As APIs têm rate limit que impeça rodar duas vezes por dia?

---

### 3. Quem executa o trabalho de código? (Bloqueador de escopo)

A reestruturação envolve:
- Reescrever `init_bq.py` (~3.490 → ~900 linhas)
- 3 mudanças no `orchestrator.py`
- Adicionar step de init ao `deploy-cloud-run.yml`
- Extrair e incluir as SQLs das views V4 no repositório

**Estimativa por tarefa:**

| Tarefa | Esforço | Quem faz |
|--------|---------|---------|
| Reescrita do `init_bq.py` | 2-3 dias | Dev backend |
| Mudanças no `orchestrator.py` | 0.5 dia | Dev backend |
| Configurar projeto GCP staging | 0.5 dia | Alexandre/DevOps |
| Configurar Firestore staging | 1 dia | Dev backend |
| Validação dos pipelines | 3-5 dias | QA + AdOps |

**Total: ~8-10 dias de desenvolvimento + 3-5 dias de validação = ~3 semanas**

---

### 4. Limpeza de prod: antes ou depois do staging? (Decisão estratégica)

Temos dois caminhos possíveis:

**Caminho A — Limpar prod agora, staging depois:**
Executa os `DROP` statements de `bigquery_cleanup_proposal.md` ainda esta semana.  
Libera ~1.147 MB imediatamente. Staging fica para depois.  
Risco: baixo, mas prod continua com o Pipeline A quebrado.

**Caminho B — Staging primeiro, limpar prod no cutover:**
Constrói o staging limpo. Quando staging estiver validado e vira o novo prod, o projeto antigo é abandonado (ou deletado).  
Risco: mínimo — prod nunca é tocado durante a transição.

**Caminho C — Paralelo (recomendado):**
Limpeza de prod (apenas Fase 1: backups e raw_* órf­ãos) + construção do staging em paralelo.  
Os dois trabalhos são independentes — não se bloqueiam.

---

## Timeline Realista

```
Semana 1 (Sprint 0 + 1)
├── Seg/Ter: Decisões da reunião + criação do projeto GCP staging
├── Qua/Qui: Reescrita do init_bq.py com todas as views V4
└── Sex:     Execução do init_bq.py no staging — validar schema criado

Semana 2 (Sprint 2 + 3)
├── Seg/Ter: Mudanças no orchestrator.py + configuração do Firestore staging
├── Qua:     Push para branch staging → CI/CD faz deploy automático
├── Qui:     Primeiro ETL no staging — verificar dados em adframework-stg.raw.*
└── Sex:     Gold DDL no staging + verificar gold refresh automático

Semana 3 (Sprint 4 + 5)
├── Seg–Qua: ETL paralelo + comparação de métricas prod vs staging
├── Qui:     Power BI conectado no gold de staging — validar dashboards
└── Sex:     Go/no-go para cutover
```

**Cutover (Semana 4, dia 1):**
- Mover Cloud Scheduler para staging
- Confirmar paridade de dados
- Anunciar staging como novo prod

---

## O Que Pode Dar Errado e Como Mitigar

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| Workload Identity Federation para o novo projeto GCP exige configuração extra | Média | Usar Opção B de projeto (datasets separados no mesmo projeto) |
| `io_delivery_daily_v4` não produz os mesmos números no staging | Baixa | Comparar `SELECT COUNT(*), SUM(impressions)` por data entre prod e staging |
| Credenciais de API geram conflito com rate limit | Baixa | Usar `bq cp` para copiar dados raw de prod em vez de reingerir |
| Firestore staging não tem os jobs configurados corretamente | Média | Exportar `platform_reports` de prod via `gcloud firestore export` |
| Siprocal planilha não está acessível pela service account de staging | Alta | Compartilhar a planilha com `etl-stg-sa@adframework.iam.gserviceaccount.com` antes de começar |

---

## O Que Pode Ser Feito Antes da Reunião (Sprint 0)

As tarefas abaixo têm **risco zero** — apenas leitura de prod — e desbloqueiam Sprint 1 imediatamente:

- [x] SQLs das views V4 extraídas do BQ prod (`io_delivery_daily_v4`, `io_schedule_daily_v4`, `io_calc_daily_v4`, core views) — **FEITO**
- [ ] Extrair SQLs das views `share.newad_operational_daily` e `share.platform_campaign_catalog`
- [ ] Exportar lista de documentos do Firestore `platform_reports` (apenas estrutura, sem credenciais)
- [ ] Confirmar service accounts existentes: `etl-stg-sa@adframework.iam.gserviceaccount.com`

---

## Resumo para a Reunião

| Pergunta | Precisamos decidir |
|----------|--------------------|
| Novo projeto GCP ou datasets no mesmo projeto? | Alexandre / Shiro decidem |
| ETL duplo nas APIs ou copiar dados de prod? | Shiro valida rate limits |
| Quem escreve o código? | Definir responsável |
| Limpeza de prod agora ou junto com cutover? | Decisão estratégica |
| Siprocal: compartilhar planilha com staging service account? | Ação imediata |

**Se as 4 decisões acima forem tomadas na terça, o desenvolvimento pode começar na quarta.**

---

*Documento gerado em 2026-05-04. Para dúvidas: Douglas Reche.*
