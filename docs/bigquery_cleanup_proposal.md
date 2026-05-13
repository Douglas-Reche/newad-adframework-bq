# BigQuery — Proposta de Limpeza de Storage
**Projeto:** adframework  
**Data:** 2026-04-30  
**Elaborado por:** Douglas Reche  
**Para revisão:** Shiro · Alexandre

---

## Contexto

Foi realizada uma auditoria completa do projeto BigQuery `adframework`, cobrindo todos os **14 datasets** e **~120 tabelas/views**. O objetivo foi mapear redundâncias, identificar objetos obsoletos e propor uma redução segura de custo de storage.

O projeto ocupa atualmente **~2.576 MB**. Com a limpeza proposta, esse número cai para **~1.029 MB** — uma redução de **~60%** sem nenhum impacto operacional.

---

## O que foi encontrado

### Datasets ativos (não tocar)

| Dataset | Função | Storage |
|---------|--------|---------|
| `raw` | Ingestão diária das plataformas (MediaSmart, MGID, Siprocal) — ETL escreve aqui todo dia ~08h BRT | ~563 MB |
| `stg` | Views de staging (transformações sobre raw) | ~0 MB |
| `core` | Tabelas canônicas do IO Manager e bindings de campanha | ~0.2 MB |
| `marts` | Views analíticas intermediárias | ~0 MB |
| `share` | Views de consumo (dashboards, relatórios, AdOps) | ~0 MB |
| `gold` | Star schema para Power BI (dims + facts materializados) | ~9 MB |
| `pixel` | Rastreamento de eventos e atribuição | ~0.3 MB |
| `adtracking` | Eventos de tracking de anúncios | ~6.2 MB |
| `finops_billing` | Export de billing GCP — atualizado diariamente | ~1.061 MB |
| `analytics` | Schema reservado para analytics futuro (0 rows, manter) | ~0 MB |

---

## O que pode ser deletado com segurança

### Fase 1 — Backups antigos dentro de `raw` (~407 MB)

Três tabelas de backup criadas em fevereiro/2026 mais duas tabelas vazias. Nenhuma view ou script as referencia.

| Tabela | Tamanho | Motivo |
|--------|---------|--------|
| `raw.mediasmart_daily_legacy_20260227_065635` | 139,9 MB | Backup de fev/2026 — `raw.mediasmart_daily` já tem esses dados atualizados |
| `raw.mediasmart_daily_backup_20260227_111821` | 130,3 MB | Backup de fev/2026 — mesmo caso |
| `raw.mediasmart_daily_legacy_20260227_061441` | 129,6 MB | Backup de fev/2026 — mesmo caso |
| `raw.mediasmart_daily_creative` | 0 MB | 0 rows — nunca foi populada |
| `raw.mediasmart_daily_operational` | 0 MB | 0 rows — nunca foi populada |

**Subtotal: ~400 MB liberados**

---

### Fase 2 — Datasets `raw_*` órfãos (~747 MB)

Em **2026-04-21** foram criados 4 datasets como início de uma reestruturação da camada raw. A reestruturação não foi concluída. O ETL **nunca foi alterado** para escrever nesses datasets — ele continua escrevendo em `raw.*`. Como resultado:

- Os dados em `raw_*` estão **congelados em 2026-04-19** (10 dias atrás)
- `raw.*` tem dados de hoje (2026-04-30) e continua sendo atualizado
- Nenhuma view, job ou script referencia `raw_*`

| Dataset | Tabelas | Storage | Situação |
|---------|---------|---------|----------|
| `raw_mediasmart` | 11 | ~710 MB | Snapshot congelado — raw.mediasmart_daily está 10 dias à frente |
| `raw_mgid` | 6 | ~37 MB | Snapshot congelado — raw.mgid_daily está 10 dias à frente |
| `raw_siprocal` | 3 | ~0.1 MB | Idêntico ao raw existente |
| `raw_newadframework` | 5 | ~0 MB | Todas as 5 tabelas têm **0 rows** — nunca foram populadas |

**Subtotal: ~747 MB liberados**

> **Evidência de segurança:** `raw.mediasmart_daily` tem **638.685 rows** com `max_day = 2026-04-29`.  
> `raw_mediasmart.mediasmart_daily` tem **637.790 rows** com `max_day = 2026-04-19`.  
> Os dados de `raw_mediasmart` são um subconjunto estrito de `raw` — nada seria perdido.

---

## Resumo do impacto

| | Antes | Depois | Redução |
|-|-------|--------|---------|
| Storage total do projeto | ~2.576 MB | ~1.029 MB | **~1.547 MB (–60%)** |
| Custo estimado mensal¹ | ~$0,05/GB/mês × 2.5 GB ≈ $0,13 | ~$0,05 | Marginal neste volume |
| Datasets | 14 | 10 | –4 datasets |
| Risco operacional | — | **Zero** | Nenhuma view ou job referencia os objetos a deletar |

¹ BigQuery storage ativo: $0,02/GB/mês (primeira 10 GB gratuitas). O ganho real aqui é de clareza arquitetural e manutenção, não custo direto neste volume.

---

## Comandos para execução

> **Pré-requisito:** confirmar com o time antes de executar.  
> Sugestão: executar na ordem abaixo (Fase 1 primeiro, Fase 2 depois).

### Fase 1 — Deletar backups em `raw`

```sql
DROP TABLE IF EXISTS `adframework.raw.mediasmart_daily_legacy_20260227_065635`;
DROP TABLE IF EXISTS `adframework.raw.mediasmart_daily_backup_20260227_111821`;
DROP TABLE IF EXISTS `adframework.raw.mediasmart_daily_legacy_20260227_061441`;
DROP TABLE IF EXISTS `adframework.raw.mediasmart_daily_creative`;
DROP TABLE IF EXISTS `adframework.raw.mediasmart_daily_operational`;
```

### Fase 2 — Deletar datasets `raw_*` órfãos

```sql
DROP SCHEMA IF EXISTS `adframework.raw_mediasmart` CASCADE;
DROP SCHEMA IF EXISTS `adframework.raw_mgid` CASCADE;
DROP SCHEMA IF EXISTS `adframework.raw_siprocal` CASCADE;
DROP SCHEMA IF EXISTS `adframework.raw_newadframework` CASCADE;
```

---

## O que NÃO será alterado

- `raw.*` — ingestão ativa, ETL continua escrevendo aqui
- `stg.*`, `core.*`, `marts.*`, `share.*` — toda a pipeline analítica intacta
- `gold.*` — star schema do Power BI intacto
- `finops_billing` — export de billing GCP, não tocar
- `adtracking.*`, `pixel.*` — tracking e atribuição intactos

---

## Arquitetura atual (pós-limpeza)

```
Plataformas (MediaSmart / MGID / Siprocal)
        │
        ▼
   raw.*  (ingestão diária ~08h BRT)
        │
        ▼
   stg.*  (views de normalização)
        │
        ▼
   core.*  (IO Manager + bindings)
        │
        ▼
   marts.* (views analíticas)
        │
        ▼
   share.* (consumo: dashboards, AdOps, relatórios)
        │
        ▼
   gold.*  (star schema Power BI)
```

---

*Documento gerado em 2026-04-30. Para dúvidas: Douglas Reche.*
