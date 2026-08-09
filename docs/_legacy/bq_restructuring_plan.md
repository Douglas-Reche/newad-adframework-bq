# Plano de Deleção e Reestruturação do BigQuery — adframework

> 📦 **HISTÓRICO** — contexto e motivação do rebuild de 2026-06-16, já concluído
> (RAW/STG/GOLD reconstruídas, validadas em produção — ver `raw_layer_design.md`,
> `stg_layer_design.md`, `gold_layer_design.md`). Mantido como referência de decisão,
> não como plano ativo. Movido para `docs/_legacy/` em 2026-08-09.

> Criado: 2026-06-16
> Contexto: auditoria de Abril/2026 confirmou RAW=STG=GOLD sem perda de dados, mas arquitetura acumulou patches técnicos (rename reversal MS, all-STRING, normalize_data na ingestão) que precisam ser resolvidos na origem.
> Decisão: dropar layers de pipeline e reconstruir do zero com design limpo.

---

## 0. Restrições absolutas — NUNCA tocar

| Dataset | Motivo |
|---|---|
| `pixel` | Serviço externo de tracking — fora do nosso controle |
| `adtracking` | Serviço externo de tracking — fora do nosso controle |
| `analytics` | Serviço externo Analytics — fora do nosso controle |
| `finops_billing` | Billing externo — fora do nosso controle |
| `core.io_manager_v2` | Admin UI do Shiro — nunca referenciar |
| `core.io_line_bindings_v2` | Admin UI do Shiro |
| `core.proposals` | Admin UI do Shiro |
| `core.proposal_lines` | Admin UI do Shiro |
| Views `*_v4` | Admin UI do Shiro |

**As tabelas `core.dim_client`, `core.platform_client_links`, `core.campaign_format_map` são nossas e serão re-seedadas.**

---

## 1. O que está sendo dropado e por quê

| Layer | Dataset | Motivo da deleção |
|---|---|---|
| RAW | `raw.mediasmart_delivery` | All-STRING; normalize_data() aplicado na ingestão (snake_case); schema acumulou patches |
| RAW | `raw.mgid_delivery` | All-STRING; normalize_data() aplicado; granularidade teaser-level confirmada mas mal documentada |
| RAW | `raw.siprocal_delivery` | All-STRING; normalize_data() aplicado; WRITE_TRUNCATE já limpo mas schema inconsistente |
| STG | `stg.mediasmart_delivery` | Schema derivado do RAW antigo |
| STG | `stg.mgid_delivery` | Schema derivado do RAW antigo |
| STG | `stg.siprocal_delivery` | Schema derivado do RAW antigo |
| GOLD | `gold.fact_delivery` | Schema derivado das STGs antigas |
| GOLD | `gold.fact_pacing` | Schema derivado das STGs antigas |
| GOLD | `gold.dim_campaign` | Schema derivado das STGs antigas |

---

## 2. Diagnóstico dos problemas que motivaram o rebuild

### 2.1 `normalize_data()` aplicado no RAW (errado)
- Converte todos os headers para snake_case lowercase na ingestão
- Causa: coluna `Event ID` → `event_id` no DataFrame, mas schema BQ tinha `eventid` → **coluna dropada silenciosamente** → MS1 bug
- Patch aplicado: rename reversal no orchestrator (`event_id` → `eventid`, etc.) — frágil e confuso
- **Solução**: normalize_data() só roda na STG; RAW recebe headers com sanitização mínima apenas

### 2.2 All-STRING no RAW (errado)
- `load_data()` faz `df.astype(str)` antes de gravar → tudo STRING no BQ
- Impede queries numéricas diretas no RAW; precisava de SAFE_CAST em todo audit
- **Solução**: RAW grava tipos nativos (INT64 para impressions/clicks, FLOAT64 para cost, DATE para day/date, STRING para IDs e nomes)

### 2.3 Schema enforcement silencioso
- `load_data()` dropa colunas que não estão no schema BQ sem erro — bugs invisíveis
- **Solução**: no novo design, schema RAW é permissivo (aceita colunas extras como JSON ou colunas adicionais), ou loga warnings explícitos

### 2.4 MGID granularidade teaser-level
- RAW MGID tem granularidade `day + teaserId + campaignId` (widget level)
- Rafael usa granularidade de campanha (ad level) → MGID NATIVE aparecia com +102% de impressions
- **Não é bug de pipeline** — é diferença de fonte. RAW correto mantém granularidade original.
- **Documentar** na STG: MGID impressions = widget impressions (não comparáveis direto com Rafael)

---

## 3. Nova arquitetura — princípios

| Layer | Responsabilidade | Tratamentos permitidos |
|---|---|---|
| **RAW** | Espelho fiel da API | Sanitização mínima de nomes de coluna (só remover chars inválidos no BQ); tipos nativos; sem snake_case; sem lowercase forçado |
| **STG** | Padronização | Renomear colunas para padrão snake_case; joins com `core.platform_client_links`; adicionar `client_id`; cast de tipos; filtros de linhas inválidas |
| **GOLD** | Modelagem analítica | Joins entre plataformas; grains definidos; métricas consolidadas; pronto para Power BI |

---

## 4. Novos schemas RAW

### `raw.mediasmart_delivery`
> Headers como vêm da API CSV, apenas chars inválidos removidos (espaços→`_`, sem lowercase)

| Coluna | Tipo | Origem API |
|---|---|---|
| `EventID` | STRING | `Event ID` |
| `ControlID` | STRING | `Control ID` |
| `StrategyID` | STRING | `Strategy ID` |
| `StrategyName` | STRING | `Strategy Name` |
| `Date` | DATE | `Date` |
| `Impressions` | INT64 | `Impressions` |
| `Clicks` | INT64 | `Clicks` |
| `Spend` | FLOAT64 | `Spend` |
| `platform` | STRING | Adicionado pelo orchestrator |
| `raw_ingested_at` | TIMESTAMP | Adicionado pelo orchestrator |

### `raw.mgid_delivery`
> Headers do JSON da API, sanitização mínima

| Coluna | Tipo | Origem API |
|---|---|---|
| `day` | DATE | `day` |
| `campaignId` | STRING | `campaignId` |
| `teaserId` | STRING | `teaserId` (granularidade widget) |
| `impressions` | INT64 | `impressions` |
| `clicks` | INT64 | `clicks` |
| `spent` | FLOAT64 | `spent` |
| `platform` | STRING | Adicionado pelo orchestrator |
| `raw_ingested_at` | TIMESTAMP | Adicionado pelo orchestrator |

### `raw.siprocal_delivery`
> Headers da API Siprocal

| Coluna | Tipo | Origem API |
|---|---|---|
| `day` | DATE | `day` |
| `advertiser` | STRING | `advertiser` |
| `campaign_id` | STRING | `campaign_id` |
| `impressions` | INT64 | `impressions` |
| `clicks` | INT64 | `clicks` |
| `cost` | FLOAT64 | `cost` |
| `platform` | STRING | Adicionado pelo orchestrator |
| `raw_ingested_at` | TIMESTAMP | Adicionado pelo orchestrator |

---

## 5. Novos schemas STG

> STG é onde normalizamos: snake_case, joins com core, tipos corretos, client_id resolvido.

### `stg.mediasmart_delivery`
```sql
CREATE OR REPLACE TABLE `adframework.stg.mediasmart_delivery` (
  day               DATE,
  client_id         STRING,   -- JOIN core.platform_client_links ON eventid
  event_id          STRING,   -- = raw.EventID
  control_id        STRING,   -- = raw.ControlID
  strategy_id       STRING,
  strategy_name     STRING,
  impressions       INT64,
  clicks            INT64,
  spend             FLOAT64,
  stg_loaded_at     TIMESTAMP
);
```

### `stg.mgid_delivery`
```sql
CREATE OR REPLACE TABLE `adframework.stg.mgid_delivery` (
  day               DATE,
  client_id         STRING,   -- JOIN core.platform_client_links ON campaignId
  campaign_id       STRING,   -- = raw.campaignId
  teaser_id         STRING,   -- = raw.teaserId (mantém granularidade original)
  impressions       INT64,
  clicks            INT64,
  spend             FLOAT64,
  stg_loaded_at     TIMESTAMP
);
```

### `stg.siprocal_delivery`
```sql
CREATE OR REPLACE TABLE `adframework.stg.siprocal_delivery` (
  day               DATE,
  client_id         STRING,   -- JOIN core.platform_client_links ON advertiser
  advertiser        STRING,
  campaign_id       STRING,
  impressions       INT64,
  clicks            INT64,
  cost              FLOAT64,
  stg_loaded_at     TIMESTAMP
);
```

---

## 6. GOLD — grains aprovados (2026-06-16)

### `gold.dim_campaign`
> Uma linha por `(client_id, platform, platform_campaign_id)`. Category vem do `campaign_format_map`.

```sql
CREATE OR REPLACE TABLE `adframework.gold.dim_campaign` (
  client_id             STRING,
  platform              STRING,
  platform_campaign_id  STRING,   -- eventid / campaignId / advertiser
  campaign_name         STRING,   -- strategy_name (MS) ou NULL (MGID/Siprocal)
  category              STRING,   -- UPPER(format) de campaign_format_map; fallback por plataforma
  PRIMARY KEY (client_id, platform, platform_campaign_id) NOT ENFORCED
);
```

**Regra de category por plataforma:**
- MediaSmart: `campaign_format_map.format` por `platform_campaign_id` (controlid/strategyid)
- MGID: `campaign_format_map.format` por `campaign_id`; fallback = `'NATIVE'`
- Siprocal: `campaign_format_map.format` por `campaign_id`; fallback = `'PUSH'`

### `gold.fact_delivery`
> Grain: `(client_id, day, platform_campaign_id, platform, category)`

```sql
CREATE OR REPLACE TABLE `adframework.gold.fact_delivery` (
  day                   DATE,
  client_id             STRING,
  platform              STRING,
  platform_campaign_id  STRING,
  category              STRING,   -- de dim_campaign
  impressions           INT64,
  clicks                INT64,
  cost                  FLOAT64,
  gold_loaded_at        TIMESTAMP
)
PARTITION BY day
CLUSTER BY client_id, platform;
```

### `gold.fact_pacing`
> Grain: `(client_id, day, category)` — agregado cross-platform por formato

```sql
CREATE OR REPLACE TABLE `adframework.gold.fact_pacing` (
  day                   DATE,
  client_id             STRING,
  category              STRING,
  impressions           INT64,
  clicks                INT64,
  cost                  FLOAT64,
  gold_loaded_at        TIMESTAMP
)
PARTITION BY day
CLUSTER BY client_id;
```

---

## 7. Sequência de execução

### Fase 1 — Backup e preparação
- [x] Exportar `core.dim_client`, `core.platform_client_links`, `core.campaign_format_map` → [core_config_backup.md](core_config_backup.md)
- [ ] Confirmar que API MediaSmart tem histórico completo (>= Aug 2025)
- [ ] Confirmar que API MGID tem histórico completo
- [ ] Confirmar que API Siprocal tem histórico completo (já confirmado: 2025-08-22 → 2026-06-11)

### Fase 2 — DROP (ordem segura)
```sql
-- GOLD primeiro (depende de STG)
DROP TABLE IF EXISTS `adframework.gold.fact_delivery`;
DROP TABLE IF EXISTS `adframework.gold.fact_pacing`;
DROP TABLE IF EXISTS `adframework.gold.dim_campaign`;

-- STG depois (depende de RAW)
DROP TABLE IF EXISTS `adframework.stg.mediasmart_delivery`;
DROP TABLE IF EXISTS `adframework.stg.mgid_delivery`;
DROP TABLE IF EXISTS `adframework.stg.siprocal_delivery`;

-- RAW por último
DROP TABLE IF EXISTS `adframework.raw.mediasmart_delivery`;
DROP TABLE IF EXISTS `adframework.raw.mgid_delivery`;
DROP TABLE IF EXISTS `adframework.raw.siprocal_delivery`;
```

### Fase 3 — Alterações de código no pipeline
- [ ] Remover `normalize_data()` da ingestão RAW (ou mover para STG apenas)
- [ ] Remover rename reversal do `_run_mediasmart_daily()` no orchestrator
- [ ] Remover `df.astype(str)` do `load_data()` — ou criar modo `typed=True`
- [ ] Atualizar DDL das tabelas RAW com tipos nativos
- [ ] Atualizar configs Firestore para apontar para novos targets (se mudou nome de dataset)

### Fase 4 — Re-seed core
```sql
-- Apenas se as tabelas core foram dropadas (normalmente não precisam ser)
-- Usar o INSERT gerado em core_config_backup.md
```

### Fase 5 — Criação das tabelas RAW com novo schema
- [ ] Executar DDL do novo `raw.mediasmart_delivery`
- [ ] Executar DDL do novo `raw.mgid_delivery`
- [ ] Executar DDL do novo `raw.siprocal_delivery`

### Fase 6 — Backfill RAW (reingesta histórico)
- [ ] Siprocal: backfill 2025-08-22 → hoje
- [ ] MediaSmart: backfill desde início das campanhas ativas
- [ ] MGID: backfill desde início das campanhas ativas

### Fase 7 — Build STG
- [ ] Executar DDL das novas tabelas STG
- [ ] Rodar jobs STG para todo o período histórico

### Fase 8 — Build GOLD
- [ ] Executar DDL do `gold.dim_campaign`
- [ ] Popular `gold.dim_campaign` a partir de STG + `campaign_format_map`
- [ ] Executar DDL de `gold.fact_delivery`
- [ ] Popular `gold.fact_delivery` a partir das STGs
- [ ] Executar DDL de `gold.fact_pacing`
- [ ] Popular `gold.fact_pacing` via agregação de `fact_delivery`

### Fase 9 — Validação
- [ ] Replicar audit de Abril/2026 (referência: Rafael's spreadsheet)
- [ ] Verificar totais por category para Banco Cora:
  - DISPLAY: ~968K impr, ~1.9K clicks, ~R$9.7K
  - RETARGETING: ~1.6M impr, ~3.2K clicks, ~R$19.3K
  - VIDEO: ~900K impr, ~6.8K clicks, ~R$10.8K
  - NATIVE: ~730K impr (MGID, atenção: widget impressions)
  - PUSH: ~128K impr (Siprocal, ~idêntico à referência)
- [ ] Confirmar Power BI conectado ao novo schema

---

## 8. Riscos e mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| API sem histórico suficiente | Baixa | Já confirmado que Siprocal tem histórico completo; confirmar MS e MGID antes do DROP |
| Power BI quebrado durante rebuild | Média | Fazer rebuild em horário de baixo uso; avisar Shiro se dashboard emergencial for afetado |
| `campaign_format_map` desatualizada após rebuild | Baixa | Usar `core_config_backup.md` como fonte de re-seed |
| Jobs Firestore apontando para tabelas droppadas | Média | Atualizar configs Firestore antes de rodar os jobs novos |
| Clientes `pending_confirmation` gerando dados órfãos | Baixa | Status `pending_confirmation` na `platform_client_links` já documenta esses casos |

---

## 9. Referência rápida — campos de join por plataforma

| Plataforma | Campo RAW | Campo `platform_client_links` | Campo na STG |
|---|---|---|---|
| MediaSmart | `EventID` | `link_value` (platform=mediasmart) | `event_id` |
| MGID | `campaignId` | `link_value` (platform=mgid) | `campaign_id` |
| Siprocal | `advertiser` | `link_value` (platform=siprocal) | `advertiser` |
