# MediaSmart STG Layer — Design e Plano de Implementação

> Criado em: 2026-06-11 | Última atualização: 2026-06-12
> Status: STG design T1–T13 fechado; **GRUPO A backfill 2026 concluído ✅** (2026-06-12); MGID e Siprocal são os próximos

---

## Contexto e motivação

A camada `raw` da MediaSmart possui múltiplas tabelas de catálogo e entrega que hoje
não têm relação explícita entre si no nosso pipeline. O objetivo desta reestruturação
é criar uma camada `stg` MediaSmart com modelo dimensional claro, que sirva de base
para o gold e para o `platform_client_links`.

### Limitação crítica da API MediaSmart

**O endpoint `/api/campaigns` NÃO retorna o `event_id` do advertiser.**
O vínculo advertiser → campanha só existe nos relatórios de entrega analytics.
Isso foi verificado tanto no código ETL (`orchestrator.py`) quanto na documentação
oficial da API (https://documentation.mediasmart.io). Todos os campos da resposta
da API são armazenados — não há filtragem no ETL. A ausência de `event_id` nas
colunas de `raw.mediasmart_campaigns` é uma limitação da API, não do pipeline.

---

## Hierarquia de IDs na MediaSmart

```
Advertiser  →  raw.mediasmart_advertisers.event_id  (= ms_event_id em stg.ms_clients)
                └── raw.mediasmart_campaigns.id  (= controlid na delivery = ms_campaign_id)
                     ├── raw.mediasmart_campaigns.strategies[].id  (= strategyid = ms_strategy_id)
                     └── raw.mediasmart_creatives.campaign_id
                          └── raw.mediasmart_creatives.id  (= creativeid = ms_creative_id)

Vínculo advertiser → campaign:
  ÚNICO SOURCE: raw.mediasmart_daily (ativo, 2026-05-25→hoje) + raw.mediasmart_delivery (histórico até 2026-05-24)
  Ambas retornam eventid + controlid na mesma linha — UNION sem overlap para cobertura completa
```

### Regra de FK nas tabelas fato (✅ DECISÃO FECHADA)

Todas as tabelas fato (T6, T7, T8, T9...) usam `ms_client_id` como FK para `stg.ms_clients` — não `ms_event_id`.

**Por quê:** consistência com as tabelas dimensionais (T3 usa `ms_client_id`). O `ms_client_id` é a chave legível do nosso sistema; `ms_event_id` é o ID técnico da plataforma.

**Como resolver na transformação STG:**
```sql
JOIN stg.ms_clients c ON delivery.eventid = c.ms_event_id
-- 1 eventid → 1 ms_client_id (sem duplicação — ms_clients é deduplicada)
```

**Risco:** `eventid` sem match em `ms_clients` → `ms_client_id = NULL`. Tratado com `LEFT JOIN` + monitoramento de NULLs. Não é risco de duplicação.

---

## Problema de duplicatas na RAW

Ambas as tabelas de catálogo têm duplicatas por `update_type: firstlevel` usar
`WRITE_APPEND` em vez de MERGE/TRUNCATE no Firestore:

| Tabela | Rows totais | IDs únicos | Fator duplicação |
|---|---|---|---|
| `raw.mediasmart_advertisers` | 42 | 21 | 2× |
| `raw.mediasmart_campaigns` | 5.451 | 140 | ~39× |

**Fix pendente:** adicionar `write_mode: WRITE_TRUNCATE` (ou lógica MERGE) nos
documentos Firestore `mediasmart_firstlevel_advertisers` e
`mediasmart_firstlevel_campaigns`.

> ⚠️ Para campaigns, TRUNCATE é arriscado: campanhas deletadas da plataforma
> podem desaparecer da API. Preferir MERGE (insert se novo, update se existe,
> nunca deletar).

---

## Tabelas planejadas para STG

### Tabela 1 — `stg.ms_clients`

**Fonte:** `raw.mediasmart_advertisers` (deduplicado com QUALIFY ROW_NUMBER)

**Decisão de design:** `ms_client_id` é um ID legível gerado por nós,
combinando `slug(name)` + `_` + `id` (truncado). O `ms_event_id` é o ID
técnico de vinculação usado nas queries de JOIN com a delivery.

| Coluna | Tipo | Origem | Exemplo | Notas |
|---|---|---|---|---|
| `ms_client_id` | STRING | gerado: `slug(name)_id[:8]` | `cora_2ruu4won` | ID legível nosso |
| `ms_event_id` | STRING | `event_id` | `newad_brazil-2ruu4won...` | JOIN com delivery.eventid |
| `ms_client_name` | STRING | `name` | `Cora` | Nome oficial na plataforma |
| `domain` | STRING | `domain` | `bancocora.com.br` | |
| `iab_category` | STRING | `iab_category` | `IAB13` | |
| `sensitive_content` | BOOLEAN | `sensitive_content` | `false` | |

---

### Tabela 2 — ELIMINADA

**Decisão:** a bridge `ms_client_campaigns` foi eliminada após verificação.
Nenhuma campanha aparece com mais de um `eventid` na delivery — relação é
estritamente `N:1` (muitas campanhas para um único cliente). Bridge table
é padrão para `N:N`; para `N:1` o correto é FK direto na tabela filha.
`ms_client_id` e `ms_event_id` foram absorvidos pela Tabela 3.

---

### Tabela 3 — `stg.ms_campaigns` ✅ FECHADA

**Fonte:** `raw.mediasmart_campaigns` (MERGE — nunca deletar para preservar histórico)

**Decisões de design:**
- `ms_client_id` e `ms_event_id` incorporados diretamente (FK da relação N:1 com clientes)
- `schedule` parseado de JSON para colunas tipadas
- `is_active` removido — 100% redundante com `state` (confirmado nos dados)
- `type` removido — único valor em todo o account: `generic`
- `goal` removido — único valor em todo o account: `{}` (JSON vazio)

| Coluna | Tipo | Origem | Exemplo | Notas |
|---|---|---|---|---|
| `ms_campaign_id` | STRING | `id` | `ncfv7ti3k4y0zg0a...` | PK — mesmo que controlid na delivery |
| `ms_client_id` | STRING | derivado via delivery → stg.ms_clients | `cora_2ruu4won` | FK legível para ms_clients |
| `ms_event_id` | STRING | `delivery.eventid` | `newad_brazil-2ruu4won...` | FK técnica para JOINs diretos |
| `ms_campaign_name` | STRING | `name` | `CORA_CONTADIGITAL_DISPLAY_MAIO26` | |
| `state` | STRING | `state` | `active` / `inactive` | |
| `started_at` | DATE | `JSON_VALUE(schedule, '$.started_at')` | `2025-08-01` | |
| `finished_at` | DATE | `JSON_VALUE(schedule, '$.finished_at')` | `2026-06-10` | |
| `max_daily_cost` | FLOAT | `JSON_VALUE(schedule, '$.max_daily_cost')` | `80.0` | Budget diário |
| `max_global_cost` | FLOAT | `JSON_VALUE(schedule, '$.max_global_cost')` | `14559.0` | Budget total |
| `max_global_impressions` | INT | `JSON_VALUE(schedule, '$.max_global_impressions')` | `4585000` | Cap de impressões |
| `created_at` | TIMESTAMP | `created_at` | `2025-01-15` | |
| `updated_at` | TIMESTAMP | `updated_at` | `2026-06-09` | |

---

---

### Tabela 4 — `stg.ms_strategies` ✅ FECHADA

**Fonte:** JSON `strategies[]` de `raw.mediasmart_campaigns` (UNNEST após deduplicação)

**O que é uma strategy na MediaSmart:**
Uma strategy equivale a um **line item / ad group** em outros DSPs. É a camada entre
campanha e criativo que define bid, targeting, budget allocation e modelo de compra
(CPM vs CPC). O campo `name` é livre — alguns accounts nomeiam pelo modelo de compra
("CPM", "CPC"), outros pelo tema/promoção ("TORNEIOS ESTADUAIS", "BLACKJACK").
Na delivery, `strategyid` identifica qual strategy gerou cada impressão.

**Relação:** 1 campanha → N strategies (1 a 15 strategies por campanha nos dados reais)

**Estrutura JSON na raw:**
```json
{
  "id": "errlanmxbhbi6pk0v1oexsi18qqhdjwi",
  "name": "Strategy 1",
  "parent": { "id": "ncfv7ti3k4y0zg0azyvgpyyyilrhqjkr", "name": "CORA_CONTADIGITAL_JANEIRO_DISPLAY" },
  "state": "active"
}
```

| Coluna | Tipo | Origem | Exemplo | Notas |
|---|---|---|---|---|
| `ms_strategy_id` | STRING | `JSON_VALUE(s, '$.id')` | `errlanmxbhbi6pk0v1o...` | PK — mesmo que `strategyid` na delivery |
| `ms_campaign_id` | STRING | `JSON_VALUE(s, '$.parent.id')` | `ncfv7ti3k4y0zg0az...` | FK para `stg.ms_campaigns.ms_campaign_id` |
| `ms_strategy_name` | STRING | `JSON_VALUE(s, '$.name')` | `CPM` / `TORNEIOS ESTADUAIS` | Nome livre definido pelo usuário |
| `state` | STRING | `JSON_VALUE(s, '$.state')` | `active` | Apenas `active` nas campaigns; histórico de inativas via delivery |
| `updated_at` | TIMESTAMP | `c.updated_at` (da campanha pai) | `2026-06-09` | Herda timestamp da última atualização da campanha |

---

#### O que temos HOJE na raw (sem nenhum novo job)

Dentro de `raw.mediasmart_campaigns`, cada campanha tem um campo `strategies` — um array JSON com **resumo** de cada strategy:

```json
{
  "id": "errlanmxbhbi6pk0v1oexsi18qqhdjwi",
  "name": "CPM",
  "parent": { "id": "ncfv7ti3k4y0zg0azyvgpyyyilrhqjkr", "name": "CORA_CONTADIGITAL_JANEIRO_DISPLAY" },
  "state": "active"
}
```

Campos disponíveis hoje: `id`, `name`, `parent.id`, `parent.name`, `state`  
**Não disponível hoje:** modelo de compra, targeting, budget, `cost_percentage`

Além disso, `raw.mediasmart_delivery` tem `strategyid` e `strategyname` por linha de entrega — o que já permite análise de performance por strategy via JOIN.

---

#### O que poderíamos trazer com ingestão futura

A documentação oficial confirma: uma strategy É uma campanha filho. Via `GET /api/campaign/:strategy_id` conseguimos o corpo completo da strategy, igual ao de uma campanha. Campos disponíveis:

| Campo da API | Coluna no STG | Valor que traz |
|---|---|---|
| `deals_and_pricing.cpm` | `bid_cpm` | Preço por mil impressões definido na strategy |
| `deals_and_pricing.cpc` | `bid_cpc` | Preço por clique definido na strategy |
| `deals_and_pricing.deal_policy` | `deal_policy` | `fixed` / `margin` / etc |
| `schedule.max_daily_cost` | `max_daily_cost` | Budget diário alocado para esta strategy |
| `schedule.max_global_cost` | `max_global_cost` | Budget total da strategy |
| `cost_percentage` | `cost_percentage` | % do budget da campanha pai que vai para esta strategy |
| `targeting.device_type` | `targeting_device` | Ex: `smartphone`, `tablet`, `desktop` |
| `targeting.countries` | `targeting_countries` | Lista de países alvo |
| `targeting.os` | `targeting_os` | Ex: `android`, `ios` |
| `schedule.timing` | `targeting_daypart` | Horários/dias ativos (dayparting) |

**Job necessário:**
```
bq_destiny:  raw.mediasmart_strategies_detail
endpoint:    GET /api/campaign/:strategy_id  (um call por strategy_id)
trigger:     após cada run de mediasmart_firstlevel_campaigns
modo:        iterar sobre todos strategy_id extraídos de campaigns.strategies[]
write_mode:  MERGE (upsert por strategy_id)
```

> **Nota:** este job exige lógica de iteração por ID, diferente dos jobs de analytics que são bulk.
> O ETL atual (`orchestrator.py`) já tem padrão similar para buscar creatives por campaign_id.

---

#### Decisão de escopo

- **Fase atual (V1):** fechar a Tabela 4 com os campos disponíveis hoje (`id`, `name`, `parent.id`, `state`)
- **Fase futura:** criar `raw.mediasmart_strategies_detail` e expandir `stg.ms_strategies` com os campos de bid, targeting e budget acima

---

**Implementação proposta (escopo atual, sem novo job):**
```sql
SELECT DISTINCT
  JSON_VALUE(s, '$.id')          AS ms_strategy_id,
  JSON_VALUE(s, '$.parent.id')   AS ms_campaign_id,
  JSON_VALUE(s, '$.name')        AS ms_strategy_name,
  JSON_VALUE(s, '$.state')       AS state,
  c.updated_at
FROM (
  SELECT id, strategies, updated_at,
    ROW_NUMBER() OVER (PARTITION BY id ORDER BY updated_at DESC) AS rn
  FROM adframework.raw.mediasmart_campaigns
  WHERE strategies IS NOT NULL AND strategies != '[]'
) c, UNNEST(JSON_QUERY_ARRAY(strategies)) AS s
WHERE c.rn = 1
```

---

### Tabela 5 — `stg.ms_creatives` ✅ FECHADA

**Fonte:** `raw.mediasmart_creatives` (deduplicado com QUALIFY ROW_NUMBER)

**Contexto dos dados observados:**
- 34.438 linhas totais / 4.434 IDs únicos → fator ~7.8× de duplicação (mesmo problema WRITE_APPEND)
- Muitas linhas têm `campaign_id = NULL` e `creative` JSON = NULL (criativos sem vínculo de campanha ativo)
- Somente ~1.188 rows têm `id = creative_id` com o JSON `creative` completo (criativo vinculado)
- O campo `id` é o PK real; `creative_id` quando preenchido é igual ao `id` (redundante)
- O campo `creative` JSON contém dimensões (`height`, `width`) e metadata adicional

| Coluna | Tipo | Origem | Exemplo | Notas |
|---|---|---|---|---|
| `ms_creative_id` | STRING | `id` | `05xppxdxr3pjexbc...` | PK — mesmo que `creative_id` na delivery |
| `ms_campaign_id` | STRING | `campaign_id` | `yy3qpcyut4aua3pd...` | FK para `stg.ms_campaigns` — NULL quando criativo não está vinculado |
| `ms_creative_name` | STRING | `name` | `DRCONSULTA_DISPLAY_300x600` | Nome do arquivo/criativo |
| `creative_type` | STRING | `type` | `image` / `video` / `native` / `rich_media` | Tipo de criativo |
| `size_width` | INT | `JSON_VALUE(creative, '$.creative.width')` | `300` | NULL quando JSON não disponível |
| `size_height` | INT | `JSON_VALUE(creative, '$.creative.height')` | `600` | NULL quando JSON não disponível |
| `thumbnail_url` | STRING | `thumbnail_url` | `https://d1bckj6a4vm1bg...` | URL de preview do criativo |
| `updated_at` | TIMESTAMP | `updated_at` | `2026-01-15` | |

**Nota:** `creative_id` e `campaign` (colunas da raw) não são incluídos no STG — são redundantes
com `id` e `campaign_id` respectivamente.

---

### Tabela 6 — `stg.ms_delivery` ✅ FECHADA

**Fontes:** UNION de `raw.mediasmart_delivery` (histórico: ago/2025–mai/2026) + `raw.mediasmart_daily` (ativo: mai/2026–hoje)

**Decisões de design:**
- Colunas financeiras (`client_cost`, `clientrevenue`, `convertedclientrevenue`) **removidas** — valores NULL em 100% das linhas nas duas fontes; financeiro será tratado via `raw revenue` separadamente
- `source_table` incluído para rastreabilidade de origem
- `raw_ingested_at` excluído do STG (metadado interno da ingestão)
- `platform` e `report_name` excluídos (valores constantes, sem valor analítico)
- `ms_client_id` resolvido via JOIN `eventid → stg.ms_clients.ms_event_id` (Opção B — FK consistente)
- `ms_strategy_name` desnormalizado para evitar JOIN extra no gold

**Nota técnica:** `raw_ingested_at` é TIMESTAMP em `delivery` e STRING em `daily` — usar `SAFE_CAST(raw_ingested_at AS TIMESTAMP)` na `daily` ao fazer o UNION.

**Gap de dados:** 25–26/mai/2026 ausentes na transição entre os dois jobs — preencher via reingesta retroativa.

| Coluna | Tipo | Origem | Notas |
|---|---|---|---|
| `day` | DATE | `day` | |
| `ms_client_id` | STRING | JOIN `eventid → stg.ms_clients` | FK cliente (Opção B) |
| `ms_campaign_id` | STRING | `controlid` | FK campanha |
| `ms_strategy_id` | STRING | `strategyid` | FK strategy |
| `ms_strategy_name` | STRING | `strategyname` | Desnormalizado |
| `impressions` | INT | `CAST(impressions AS INT64)` | |
| `clicks` | INT | `CAST(clicks AS INT64)` | |
| `video_start` | INT | `CAST(video_start AS INT64)` | |
| `video_25` | INT | `CAST(video_25_viewed AS INT64)` | |
| `video_50` | INT | `CAST(video_50_viewed AS INT64)` | |
| `video_75` | INT | `CAST(video_75_viewed AS INT64)` | |
| `video_complete` | INT | `CAST(video_completion AS INT64)` | |
| `conversions_1` | INT | `CAST(conversions_1 AS INT64)` | |
| `conversions_2` | INT | `CAST(conversions_2 AS INT64)` | |
| `conversions_3` | INT | `CAST(conversions_3 AS INT64)` | |
| `conversions_4` | INT | `CAST(conversions_4 AS INT64)` | |
| `conversions_5` | INT | `CAST(conversions_5 AS INT64)` | |
| `conversion_source` | STRING | `conversion_source` | |
| `source_table` | STRING | literal `'delivery'` ou `'daily'` | Rastreabilidade |

---

### Tabela 7 — `stg.ms_creative_delivery` ✅ FECHADA

**Fonte:** `raw.mediasmart_creative_daily` ✅ job operacional desde 2026-06-11

**Decisões de design:**
- Traz o conjunto **completo de KPIs** — é o único lugar no pipeline com performance no nível de criativo
- `creative_type` e `size` desnormalizados direto da API — evita JOIN com `stg.ms_creatives` para análises simples
- `ms_client_id` via JOIN `event_id → stg.ms_clients.ms_event_id` (Opção B)
- Financeiro incluído: `final_price` e `media_cost__brl` disponíveis na fonte (confirmado em produção)

**Atenção de nomenclatura (RAW usa nomes novos):**
Esta tabela fonte usa schema novo (normalize_data puro): `event_id`, `campaign_id`, `strategy_id`, `creative_id`, `creative_type`. Diferente de T6 que usa `eventid`/`controlid`/`strategyid`.

**Cadeia de IDs:**
```
ms_client_id   → stg.ms_clients.ms_client_id    (via JOIN event_id → ms_event_id)
ms_campaign_id → stg.ms_campaigns.ms_campaign_id (campaign_id é o mesmo valor de controlid)
ms_strategy_id → stg.ms_strategies.ms_strategy_id
ms_creative_id → stg.ms_creatives.ms_creative_id
```

| Coluna STG | Tipo | Coluna RAW (raw.mediasmart_creative_daily) | Notas |
|---|---|---|---|
| `day` | DATE | `day` | |
| `ms_client_id` | STRING | JOIN `event_id → stg.ms_clients.ms_event_id` | |
| `ms_campaign_id` | STRING | `campaign_id` | mesma chave que `controlid` nas tabelas antigas |
| `ms_strategy_id` | STRING | `strategy_id` | mesma chave que `strategyid` nas tabelas antigas |
| `ms_creative_id` | STRING | `creative_id` | |
| `creative_type` | STRING | `creative_type` | desnormalizado — ex: `image`, `video`, `native` |
| `size` | STRING | `size` | ex: `300x250` |
| `app_vs_web` | STRING | `app_vs_web` | `app` ou `web` |
| `impressions` | INT | `CAST(impressions AS INT64)` | |
| `clicks` | INT | `CAST(clicks AS INT64)` | |
| `video_start` | INT | `CAST(video_start AS INT64)` | nome novo vs `videostart` nas tabelas antigas |
| `video_25` | INT | `CAST(video_25_viewed AS INT64)` | |
| `video_50` | INT | `CAST(video_50_viewed AS INT64)` | |
| `video_75` | INT | `CAST(video_75_viewed AS INT64)` | |
| `video_complete` | INT | `CAST(video_completion AS INT64)` | |
| `conversions_1` | INT | `CAST(conversions_1 AS INT64)` | |
| `conversions_2` | INT | `CAST(conversions_2 AS INT64)` | |
| `conversions_3` | INT | `CAST(conversions_3 AS INT64)` | |
| `conversions_4` | INT | `CAST(conversions_4 AS INT64)` | |
| `conversions_5` | INT | `CAST(conversions_5 AS INT64)` | |
| `conversion_source` | STRING | `conversion_source` | |
| `final_price` | FLOAT | `SAFE_CAST(final_price AS FLOAT64)` | convertedclientrevenue da API |
| `media_cost_brl` | FLOAT | `SAFE_CAST(media_cost__brl AS FLOAT64)` | client_cost da API — double underscore na raw |

---

### Tabela 8 — `stg.ms_revenue` ✅ FECHADA

**Fontes:** UNION de `raw.mediasmart_revenue` (histórico, sem eventid) + `raw.mediasmart_revenue_daily` (ativo, com eventid)

**Decisões de design:**
- `ms_client_id` resolvido via COALESCE: caminho direto `eventid → stg.ms_clients` OU fallback `controlid → stg.ms_campaigns → ms_client_id`
- Fallback não cria duplicação nem erro — `stg.ms_campaigns` tem 1 row por `ms_campaign_id`; histórico é fixo, linhas novas já têm eventid
- `revenue_source` normalizado: `REGEXP_EXTRACT(revenuesource, r'[0-9]+')` → `'1'`…`'5'` (harmoniza `event3` da tabela antiga com `3` da nova)
- `conversion_source` NULL no histórico — aceito, dado não existia no job antigo

> ⚠️ **TODO (jobs futuros):** ao criar novos jobs de ingestão da API MediaSmart, estudar quais KPIs financeiros adicionais conseguimos trazer — ex: `wonprice` (media cost), `convertedclientrevenue`, `techfee`, `margin`. Ver lista completa em `API_Doc_MediaSmart.md` seção KPIs.

| Coluna | Tipo | Origem | Notas |
|---|---|---|---|
| `day` | DATE | `day` | |
| `ms_client_id` | STRING | `COALESCE(via eventid, via controlid→campaigns)` | Fallback para histórico sem eventid |
| `ms_campaign_id` | STRING | `controlid` | FK campanha |
| `ms_strategy_id` | STRING | `strategyid` | FK strategy |
| `revenue_source` | STRING | `REGEXP_EXTRACT(revenuesource, r'[0-9]+')` | `'1'`–`'5'` — mapeia para conversions_1–5 |
| `conversion_source` | STRING | `conversion_source` | `click`/`impression` — NULL no histórico |
| `clientrevenue` | FLOAT | `SAFE_CAST(clientrevenue AS FLOAT64)` | Valor monetário do evento |
| `source_table` | STRING | `'revenue'` ou `'revenue_daily'` | Rastreabilidade |

---

### Tabela 9 — `stg.ms_delivery_by_device` ✅ FECHADA

**Fonte:** `raw.mediasmart_delivery_by_device` ✅ job operacional desde 2026-06-11
**Granularidade:** `day + ms_client_id + ms_campaign_id + ms_strategy_id + device_type + app_vs_web`

**Atenção de nomenclatura:** fonte usa schema novo (`event_id`, `campaign_id`, `strategy_id`).

| Coluna STG | Tipo | Coluna RAW | Notas |
|---|---|---|---|
| `day` | DATE | `day` | |
| `ms_client_id` | STRING | JOIN `event_id → stg.ms_clients.ms_event_id` | |
| `ms_campaign_id` | STRING | `campaign_id` | |
| `ms_strategy_id` | STRING | `strategy_id` | |
| `device_type` | STRING | `device_type` | ex: `smartphone`, `tablet`, `desktop` |
| `app_vs_web` | STRING | `app_vs_web` | ex: `app`, `web` |
| `impressions` | INT | `CAST(impressions AS INT64)` | |
| `clicks` | INT | `CAST(clicks AS INT64)` | |
| `video_start` | INT | `CAST(video_start AS INT64)` | |
| `video_25` | INT | `CAST(video_25_viewed AS INT64)` | |
| `video_50` | INT | `CAST(video_50_viewed AS INT64)` | |
| `video_75` | INT | `CAST(video_75_viewed AS INT64)` | |
| `video_complete` | INT | `CAST(video_completion AS INT64)` | |
| `conversions_1`…`conversions_5` | INT | `CAST(conversions_1..5 AS INT64)` | |
| `conversion_source` | STRING | `conversion_source` | |
| `final_price` | FLOAT | `SAFE_CAST(final_price AS FLOAT64)` | |
| `media_cost_brl` | FLOAT | `SAFE_CAST(media_cost__brl AS FLOAT64)` | |

---

### Tabela 10 — `stg.ms_delivery_by_geo` ✅ FECHADA

**Fonte:** `raw.mediasmart_delivery_by_geo` ✅ job operacional desde 2026-06-11
**Granularidade:** `day + ms_client_id + ms_campaign_id + ms_strategy_id + country + area_name + city`

**Atenção de nomenclatura:**
- drilldown `countrycode` → API `"Country"` → BQ `country` (não `country_code`)
- drilldown `georegion_areaname` → API `"Area Name"` → BQ `area_name` (não `georegion_areaname`)

| Coluna STG | Tipo | Coluna RAW | Notas |
|---|---|---|---|
| `day` | DATE | `day` | |
| `ms_client_id` | STRING | JOIN `event_id → stg.ms_clients.ms_event_id` | |
| `ms_campaign_id` | STRING | `campaign_id` | |
| `ms_strategy_id` | STRING | `strategy_id` | |
| `country` | STRING | `country` | ex: `Brazil` |
| `area_name` | STRING | `area_name` | ex: `São Paulo` — estado/região |
| `city` | STRING | `city` | ex: `Campinas` |
| `impressions` | INT | `CAST(impressions AS INT64)` | |
| `clicks` | INT | `CAST(clicks AS INT64)` | |
| `video_start` | INT | `CAST(video_start AS INT64)` | |
| `video_25` | INT | `CAST(video_25_viewed AS INT64)` | |
| `video_50` | INT | `CAST(video_50_viewed AS INT64)` | |
| `video_75` | INT | `CAST(video_75_viewed AS INT64)` | |
| `video_complete` | INT | `CAST(video_completion AS INT64)` | |
| `conversions_1`…`conversions_5` | INT | | |
| `conversion_source` | STRING | `conversion_source` | |
| `final_price` | FLOAT | `SAFE_CAST(final_price AS FLOAT64)` | |
| `media_cost_brl` | FLOAT | `SAFE_CAST(media_cost__brl AS FLOAT64)` | |

---

### Tabela 11 — `stg.ms_delivery_by_os` ✅ FECHADA

**Fonte:** `raw.mediasmart_delivery_by_os` ✅ job operacional desde 2026-06-11
**Granularidade:** `day + ms_client_id + ms_campaign_id + ms_strategy_id + operating_system`

| Coluna STG | Tipo | Coluna RAW | Notas |
|---|---|---|---|
| `day` | DATE | `day` | |
| `ms_client_id` | STRING | JOIN `event_id → stg.ms_clients.ms_event_id` | |
| `ms_campaign_id` | STRING | `campaign_id` | |
| `ms_strategy_id` | STRING | `strategy_id` | |
| `operating_system` | STRING | `operating_system` | ex: `android`, `ios`, `windows`, `other` |
| `impressions` | INT | `CAST(impressions AS INT64)` | |
| `clicks` | INT | `CAST(clicks AS INT64)` | |
| `video_start` | INT | `CAST(video_start AS INT64)` | |
| `video_25` | INT | `CAST(video_25_viewed AS INT64)` | |
| `video_50` | INT | `CAST(video_50_viewed AS INT64)` | |
| `video_75` | INT | `CAST(video_75_viewed AS INT64)` | |
| `video_complete` | INT | `CAST(video_completion AS INT64)` | |
| `conversions_1`…`conversions_5` | INT | | |
| `conversion_source` | STRING | `conversion_source` | |
| `final_price` | FLOAT | `SAFE_CAST(final_price AS FLOAT64)` | |
| `media_cost_brl` | FLOAT | `SAFE_CAST(media_cost__brl AS FLOAT64)` | |

---

### Tabela 12 — `stg.ms_delivery_by_hour` ✅ FECHADA

**Fonte:** `raw.mediasmart_delivery_by_hour` ✅ job operacional desde 2026-06-11
**Granularidade:** `day + ms_client_id + ms_campaign_id + ms_strategy_id + hour`
**Uso principal:** identificar horários de pico de entrega — daypart analysis

| Coluna STG | Tipo | Coluna RAW | Notas |
|---|---|---|---|
| `day` | DATE | `day` | |
| `ms_client_id` | STRING | JOIN `event_id → stg.ms_clients.ms_event_id` | |
| `ms_campaign_id` | STRING | `campaign_id` | |
| `ms_strategy_id` | STRING | `strategy_id` | |
| `hour` | INT | `CAST(hour AS INT64)` | 0–23 em UTC |
| `impressions` | INT | `CAST(impressions AS INT64)` | |
| `clicks` | INT | `CAST(clicks AS INT64)` | |
| `video_start` | INT | `CAST(video_start AS INT64)` | |
| `video_25` | INT | `CAST(video_25_viewed AS INT64)` | |
| `video_50` | INT | `CAST(video_50_viewed AS INT64)` | |
| `video_75` | INT | `CAST(video_75_viewed AS INT64)` | |
| `video_complete` | INT | `CAST(video_completion AS INT64)` | |
| `conversions_1`…`conversions_5` | INT | | |
| `conversion_source` | STRING | `conversion_source` | |
| `final_price` | FLOAT | `SAFE_CAST(final_price AS FLOAT64)` | |
| `media_cost_brl` | FLOAT | `SAFE_CAST(media_cost__brl AS FLOAT64)` | |

---

### Tabela 13 — `stg.ms_delivery_by_publisher` ✅ FECHADA

**Fonte:** `raw.mediasmart_delivery_by_publisher` ✅ job operacional desde 2026-06-11
**Granularidade:** `day + ms_client_id + ms_campaign_id + strategy_id + publisher_company + publisher_url + ad_exchange`
**Nota:** sem KPIs de vídeo (o job não os solicita — publisher analysis raramente precisa de vídeo)

| Coluna STG | Tipo | Coluna RAW | Notas |
|---|---|---|---|
| `day` | DATE | `day` | |
| `ms_client_id` | STRING | JOIN `event_id → stg.ms_clients.ms_event_id` | |
| `ms_campaign_id` | STRING | `campaign_id` | |
| `ms_strategy_id` | STRING | `strategy_id` | |
| `publisher_company` | STRING | `publisher_company` | empresa dona do inventory |
| `publisher_url` | STRING | `publisher_url` | URL do site/app específico |
| `ad_exchange` | STRING | `ad_exchange` | SSP/exchange — ex: `OpenX`, `Pubmatic` |
| `impressions` | INT | `CAST(impressions AS INT64)` | |
| `clicks` | INT | `CAST(clicks AS INT64)` | |
| `conversion_source` | STRING | `conversion_source` | |
| `final_price` | FLOAT | `SAFE_CAST(final_price AS FLOAT64)` | |
| `media_cost_brl` | FLOAT | `SAFE_CAST(media_cost__brl AS FLOAT64)` | |

---

### Tabelas restantes — A definir em sequência

| # | Tabela | Tipo | Fonte RAW | Status |
|---|---|---|---|---|
| 14 | `stg.ms_bid_supply` | Fato publisher/leilão | `raw.mediasmart_bid_supply` *(já existe)* | No radar — demanda futura |

#### Descobertas sobre delivery vs daily (investigação 2026-06-11)

| Tabela | Range | Linhas | Colunas | Status |
|---|---|---|---|---|
| `raw.mediasmart_delivery` | 2025-08-01 → 2026-05-24 | 641.798 | 24 | Job **morto** — só histórico. Falta `creative_type`, `creative_id`, `id_type`, `mediasmart_id`, `nativesize`, `size`, `client_currency` |
| `raw.mediasmart_daily` | 2026-05-25 → hoje | 170+ | 31 | Job **ativo** — criado 2026-05-28 quando API passou a retornar 31 colunas |

**Campo `bq_destiny` vs `table_name` no Firestore:**
- `mediasmart_daily_daily.bq_destiny = "raw.mediasmart_delivery"` — campo LEGADO, ignorado pelo orchestrator
- `mediasmart_daily_daily.table_name = "mediasmart_daily"` + `dataset_id = "raw"` — o que o orchestrator usa
- `_resolve_bq_target()` prioriza `table_name` + `dataset_id`; só cai no `bq_destiny` se esses campos estiverem vazios
- Confirmado: `last_status: ok`, `last_loaded_date: 2026-06-10` — job rodando corretamente

**Origem dos 31 cols de `raw.mediasmart_daily`:**
- A API `/api/analytics/custom-report` é FLEXÍVEL — retorna headers conforme o drilldown solicitado
- `raw.mediasmart_daily` tem 31 cols porque o job `mediasmart_daily_daily` usa um drilldown largo que inclui `eventid,controlid,strategyid,strategyname,convsource` + KPIs financeiros
- Os campos `creative_type`, `creative_id`, etc. aparecem no schema porque Shiro's `aat-console` populou a tabela com um template de schema que os inclui — vêm como NULL para linhas sem drilldown de criativo
- `platform`, `report_name`, `raw_ingested_at` também vêm direto da API (NÃO são adicionados pelo ETL Python)
- **Os nomes das colunas em `raw.mediasmart_daily` são os ANTIGOS** (`eventid`, `controlid`, `strategyid`) porque o Shiro's `aat-console` aplica um mapeamento inverso antes de carregar. Isso é diferente das 6 novas tabelas do Grupo A que usam os nomes normalizados nativos da API.
- Confirmado via código: `_run_mediasmart_daily()` não faz nenhuma adição de colunas entre `fetch_data()` e `bq.load_data()`

- **Zero overlap** entre as duas tabelas — UNION direto sem risco de duplicação
- **Gap de 25-26/mai/2026** preenchido via `force_from_date` (commit `4d1662f`) — ver Grupo D
- `mediasmart_daily` tem coluna `creative_id` mas vem **sempre vazia** em delivery diária — drilldown sem `creativeid` retorna NULL no campo fixo da API
- **Decisão:** NÃO adicionar `creativeid` ao drilldown da `mediasmart_daily` — criar job separado `mediasmart_creative_daily` (Opção B)

---

## Novos jobs RAW a criar no Firestore

> Atualizado 2026-06-12 (sessão 3) — **BACKFILL GRUPO A CONCLUÍDO.** Todas as 6 tabelas com histórico completo jan–jun/2026.
> API confirmada sem custo adicional por chamada (incluída no contrato DSP).
>
> ✅ **PROBLEMA #16 RESOLVIDO (2026-06-11 sessão 2):**
> Root cause: tabelas pré-existiam com schema antigo (Shiro `aat-console`); `bigquery.py:load_data`
> dropava colunas novas ao encontrar schema existente. Fix: DROP das 6 tabelas + re-trigger via ETL
> HTTP API. Tabelas recriadas com schema nativo da API após `normalize_data`.
> Todas as STG T7/T9/T10/by_os/by_hour/by_publisher estão DESBLOQUEADAS.
>
> ✅ **FIX REQUEST_TIMEOUT_SECONDS (2026-06-12 sessão 3):**
> `REQUEST_TIMEOUT_SECONDS = 10` → `60` em `mediasmart.py:16`. Commit `7bee5f9`.
> Drilldowns de alta cardinalidade (geo: country+area+city; publisher: company+url+exchange) precisam de >10s
> para a API gerar o relatório — com 10s, todos os requests dos jobs de geo e publisher falhavam com timeout.
> Revisão deployada: `adframework-etl-00238-n4h`.
>
> **ETL HTTP API (documentada):**
> `POST /jobs/{job_name}/run` — trigger síncrono. Format: `{platform_id}_{update_type}:{doc_name}`
> Exemplos: `mediasmart_daily:delivery_by_os`, `mediasmart_daily:creative_daily`
> Auth: Bearer token (`gcloud auth print-identity-token`)
>
> ✅ **BACKFILL CONCLUÍDO (2026-06-12):** Ver seção "Plano de Backfill Grupo A" para resultado, row counts reais e lições aprendidas.

### GRUPO A — Jobs bulk (`/api/analytics/custom-report`) — ✅ OPERACIONAIS E CORRIGIDOS (2026-06-11)

**Nota de arquitetura:** a API `/api/analytics/custom-report` é FLEXÍVEL — retorna headers human-readable
conforme o `drilldown` solicitado. `normalize_data` em `base.py` converte para BQ-safe (lowercase, spaces→_).
**NÃO há dicionário de mapeamento no ETL.** Mapeamento semântico é feito no STG SQL.

**Mapeamento drilldown param → BQ column (confirmado em produção):**
```
eventid → event_id       controlid → campaign_id    strategyid → strategy_id
devicetype → device_type   source → app_vs_web      os → operating_system
countrycode → country    georegion_areaname → area_name    city → city
publishercompany → publisher_company   publisherurl → publisher_url   exchange → ad_exchange
hour → hour    creativeid → creative_id    creativetype → creative_type    size → size
convsource → conversion_source
KPIs financeiros: clientrevenue → event_revenue  |  convertedclientrevenue → final_price  |  client_cost → media_cost__brl
```

### Job 1 — `mediasmart_creative_daily` ✅ OPERACIONAL
```
firestore_doc:  mediasmart_creative_daily  (collection: platform_reports)
tabela BQ:      raw.mediasmart_creative_daily  (adframework)
endpoint:       /api/analytics/custom-report
drilldown:      day,eventid,controlid,strategyid,creativeid,creativetype,size,source,convsource
kpis:           impressions,clicks,
                videostart,videofirstquartile,videomidpoint,videothirdquartile,videocomplete,
                events1,events2,events3,events4,events5
update_type:    daily
schedule:       03:30 UTC diário
linhas D-1:     606 (2026-06-10)

schema BQ atual (23 cols):
  day, event_id, campaign_id, strategy_id,
  creative_id, creative_type, size, app_vs_web,
  conversion_source,
  impressions, clicks,
  video_start, video_25_viewed, video_50_viewed, video_75_viewed, video_completion,
  conversions_1..5,
  final_price, media_cost__brl
```

### Job 2 — `mediasmart_delivery_by_device` ✅ OPERACIONAL
```
firestore_doc:  mediasmart_delivery_by_device  (collection: platform_reports)
tabela BQ:      raw.mediasmart_delivery_by_device  (adframework)
endpoint:       /api/analytics/custom-report
drilldown:      day,eventid,controlid,strategyid,devicetype,source,convsource
kpis:           impressions,clicks,
                videostart,videofirstquartile,videomidpoint,videothirdquartile,videocomplete,
                events1,events2,events3,events4,events5
update_type:    daily
schedule:       03:35 UTC diário
linhas D-1:     31 (2026-06-10)

schema BQ atual (21 cols):
  day, event_id, campaign_id, strategy_id,
  device_type, app_vs_web,
  conversion_source,
  impressions, clicks,
  video_start, video_25_viewed, video_50_viewed, video_75_viewed, video_completion,
  conversions_1..5,
  final_price, media_cost__brl
```

### Job 3 — `mediasmart_delivery_by_geo` ✅ OPERACIONAL
```
firestore_doc:  mediasmart_delivery_by_geo  (collection: platform_reports)
tabela BQ:      raw.mediasmart_delivery_by_geo  (adframework)
endpoint:       /api/analytics/custom-report
drilldown:      day,eventid,controlid,strategyid,countrycode,georegion_areaname,city,convsource
kpis:           impressions,clicks,
                videostart,videofirstquartile,videomidpoint,videothirdquartile,videocomplete,
                events1,events2,events3,events4,events5
update_type:    daily
schedule:       03:40 UTC diário
linhas D-1:     728 (2026-06-10)

schema BQ atual (22 cols):
  day, event_id, campaign_id, strategy_id,
  country, area_name, city,          ← nota: countrycode→country, georegion_areaname→area_name
  conversion_source,
  impressions, clicks,
  video_start, video_25_viewed, video_50_viewed, video_75_viewed, video_completion,
  conversions_1..5,
  final_price, media_cost__brl
```

### Job 4 — `mediasmart_delivery_by_publisher` ✅ OPERACIONAL
```
firestore_doc:  mediasmart_delivery_by_publisher  (collection: platform_reports)
tabela BQ:      raw.mediasmart_delivery_by_publisher  (adframework)
endpoint:       /api/analytics/custom-report
drilldown:      day,eventid,controlid,strategyid,publishercompany,publisherurl,exchange,convsource
kpis:           impressions,clicks
update_type:    daily
schedule:       03:45 UTC diário
linhas D-1:     9.820 (2026-06-10)

schema BQ atual (12 cols):
  day, event_id, campaign_id, strategy_id,
  publisher_company, publisher_url, ad_exchange,
  conversion_source,
  impressions, clicks,
  final_price, media_cost__brl
nota: sem KPIs de vídeo — publisher job só tem impressions+clicks (sem video drilldown)
```

### Job 5 — `mediasmart_delivery_by_os` ✅ OPERACIONAL
```
firestore_doc:  mediasmart_delivery_by_os  (collection: platform_reports)
tabela BQ:      raw.mediasmart_delivery_by_os  (adframework)
endpoint:       /api/analytics/custom-report
drilldown:      day,eventid,controlid,strategyid,os,convsource
kpis:           impressions,clicks,
                videostart,videofirstquartile,videomidpoint,videothirdquartile,videocomplete,
                events1,events2,events3,events4,events5
update_type:    daily
schedule:       03:50 UTC diário
linhas D-1:     51 (2026-06-10)

schema BQ atual (20 cols):
  day, event_id, campaign_id, strategy_id,
  operating_system,                  ← drilldown param 'os' → API header "Operating system" → operating_system
  conversion_source,
  impressions, clicks,
  video_start, video_25_viewed, video_50_viewed, video_75_viewed, video_completion,
  conversions_1..5,
  final_price, media_cost__brl
```

### Job 6 — `mediasmart_delivery_by_hour` ✅ OPERACIONAL
```
firestore_doc:  mediasmart_delivery_by_hour  (collection: platform_reports)
tabela BQ:      raw.mediasmart_delivery_by_hour  (adframework)
endpoint:       /api/analytics/custom-report
drilldown:      day,eventid,controlid,strategyid,hour,convsource
kpis:           impressions,clicks,
                videostart,videofirstquartile,videomidpoint,videothirdquartile,videocomplete,
                events1,events2,events3,events4,events5
update_type:    daily
schedule:       03:55 UTC diário
linhas D-1:     107 (2026-06-10)
volume anual:   ~38k linhas/ano — manejável

schema BQ atual (20 cols):
  day, event_id, campaign_id, strategy_id,
  hour,                              ← '0'..'23' — hora do dia em UTC
  conversion_source,
  impressions, clicks,
  video_start, video_25_viewed, video_50_viewed, video_75_viewed, video_completion,
  conversions_1..5,
  final_price, media_cost__brl
```

---

### GRUPO B — Jobs de iteração por ID (requerem implementação custom no orquestrador)

> ✅ **PRÉ-REQUISITO CONCLUÍDO (2026-06-11, commit `4d1662f`):**
> `time.sleep(0.15)` → `0.6` em `_fetch_mediasmart_creatives_iter` (orchestrator.py:787)
> `time.sleep(0.3)` → `0.6` no loop daily (orchestrator.py:542)
> `RATE_LIMIT_DELAY = 0.3` → `0.6` (mediasmart.py:15)
> Deployado em Cloud Run revision `adframework-etl-00237-v88`.
> Ver `known_issues.md` item #15 (resolvido).

### Job 7 — `mediasmart_strategies_detail`
```
bq_destiny:  raw.mediasmart_strategies_detail
endpoint:    GET /api/campaign/:strategy_id  (1 call por strategy_id, ~140 calls/run)
trigger:     após cada run de mediasmart_firstlevel_campaigns
campos:      strategy_id, bid_cpm, bid_cpc, deal_policy, max_daily_cost,
             max_global_cost, cost_percentage, targeting_device,
             targeting_countries, targeting_os, targeting_daypart
write_mode:  MERGE por strategy_id
padrão:      idêntico ao _fetch_mediasmart_creatives_iter (já existe no orquestrador)
sleep:       0.6s entre calls (obrigatório — ver pré-requisito acima)
desbloqueia: segregação CPM vs CPC nas análises
```

### Job 8 — `mediasmart_unique_users`
```
bq_destiny:  raw.mediasmart_unique_users
endpoint:    GET /v2/analytics/unique-users?campaign=:id&kpi=impression (1 call por campaign)
trigger:     diário, iterando sobre campaign_ids ativos (~140 calls/dia)
campos:      campaign_id, date_from, date_to, kpi, unique_users, unique_households
write_mode:  MERGE por (campaign_id, date_from, date_to, kpi)
padrão:      idêntico ao _fetch_mediasmart_creatives_iter
sleep:       0.6s entre calls (obrigatório — ver pré-requisito acima)
desbloqueia: reach analysis — usuários únicos atingidos por campanha
```

---

### GRUPO C — Ação de STG design (sem job novo)

### Ação 9 — `conversion_names` → `stg.ms_campaigns`
```
origem:  JSON_VALUE(raw.mediasmart_campaigns.conversion_names, '$.events2') etc.
colunas: conversion_name_2, conversion_name_3, conversion_name_4, conversion_name_5
impacto: conversions anônimas (events2–5) viram labels legíveis ("Purchase", "Lead"…)
custo:   zero — dado já está na raw; apenas ajuste na transformação STG
```

---

### GRUPO D — Fixes em jobs existentes ✅ APLICADOS (2026-06-11)

| Job | Fix | Status | Detalhe |
|---|---|---|---|
| `mediasmart_firstlevel_campaigns` | WRITE_APPEND → WRITE_TRUNCATE | ✅ | Firestore `write_mode: WRITE_TRUNCATE`. BQ deduplicado: 5.451 → 140 linhas via `CREATE OR REPLACE TABLE ... WHERE rn = 1` |
| `mediasmart_firstlevel_advertisers` | WRITE_APPEND → WRITE_TRUNCATE | ✅ | Firestore `write_mode: WRITE_TRUNCATE` |
| `mediasmart_firstlevel_creatives` | WRITE_APPEND → WRITE_TRUNCATE | ✅ | Firestore `write_mode: WRITE_TRUNCATE` |
| `mediasmart_daily` — gap 25–26/mai/2026 | Backfill retroativo | ✅ | `force_from_date` implementado em `_get_date_range` (orchestrator.py). Job temporário `mediasmart_backfill_may2526` rodou e foi deletado. 26 linhas carregadas (13/dia). |

**Nota sobre campaigns:** decidido usar WRITE_TRUNCATE em vez de MERGE por simplicidade — a STG já desduplicada por ROW_NUMBER(). O risco de perder campanhas deletadas é baixo (plataforma raramente deleta; histórico de entrega preservado em `raw.mediasmart_delivery`). Implementação de MERGE verdadeiro fica como melhoria futura no ETL expansion.

**`force_from_date`:** parâmetro novo em `params_json` de qualquer job `update_type: daily`. Quando presente, ignora o max(day) do BQ e força o start_date para a data especificada. Útil para backfills pontuais sem criar nova tabela. Commit `4d1662f`.

---

### No radar — Footfall (quando houver campanhas com geolist/footfall targeting)
```
GET /v2/analytics/top-pois       — visitas físicas por POI
GET /v2/analytics/distance-time  — distância e tempo entre impressão e conversão
```

---

---

## Plano de Backfill Grupo A — ✅ EXECUTADO E CONCLUÍDO (2026-06-12)

**Contexto:** Após o fix de schema (2026-06-11), as 6 tabelas tinham apenas 1 dia de dados (2026-06-10).
Backfill executado em 2026-06-12 via múltiplos triggers sequenciais com `force_from_date` incrementado.

### Resultado final do backfill

| Tabela BQ | Linhas totais | Período | Observações |
|---|---|---|---|
| `raw.mediasmart_delivery_by_device` | 206.541 | 2026-01-01 → 2026-06-11 | ✅ Completo |
| `raw.mediasmart_delivery_by_os` | 273.799 | 2026-01-01 → 2026-06-11 | ✅ Completo |
| `raw.mediasmart_delivery_by_hour` | 5.430 | **2026-05-28 → 2026-06-11** | ✅ Completo — sem dados hourly antes de mai/28 na API |
| `raw.mediasmart_delivery_by_geo` | 8.417.374 | 2026-01-01 → 2026-06-11 | ✅ Completo (deduplicado) |
| `raw.mediasmart_creative_daily` | 394.347 | 2026-01-01 → 2026-06-11 | ✅ Completo |
| `raw.mediasmart_delivery_by_publisher` | 9.804.184 | 2026-01-01 → 2026-06-11 | ✅ Completo |

**Estado Firestore pós-backfill (verificado 2026-06-12):**
Todos os 6 jobs com `enabled=True`, `force_from_date=NONE`, `last_status=ok`, crons operacionais.

### Como executar o backfill

O mecanismo é `force_from_date` dentro de `params_json` no Firestore. Quando presente, sobrescreve
o `max(day)` do BQ e força o `start_date` para a data indicada.

**Passo 1 — Setar force_from_date via Python (executar local com credenciais GCP):**
```python
from google.cloud import firestore
import json

db = firestore.Client(project='adframework')

BACKFILL_FROM = '2026-01-01'   # início do ano, pega todo 2026

jobs = [
    'mediasmart_creative_daily',
    'mediasmart_delivery_by_device',
    'mediasmart_delivery_by_geo',
    'mediasmart_delivery_by_hour',
    'mediasmart_delivery_by_os',
    'mediasmart_delivery_by_publisher',
]

for doc_id in jobs:
    ref = db.collection('platform_reports').document(doc_id)
    doc = ref.get().to_dict() or {}
    params = doc.get('params_json') or {}
    params['force_from_date'] = BACKFILL_FROM
    ref.update({'params_json': params})
    print(f'Set {doc_id}: force_from_date={BACKFILL_FROM}')
```

**Passo 2 — Disparar os jobs via ETL HTTP API:**
```python
import subprocess, json, urllib.request, urllib.error

token = subprocess.check_output('gcloud auth print-identity-token', shell=True).decode().strip()
base = 'https://adframework-etl-911847757485.us-central1.run.app'
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

jobs_to_run = [
    'mediasmart_daily:delivery_by_device',
    'mediasmart_daily:delivery_by_geo',
    'mediasmart_daily:delivery_by_os',
    'mediasmart_daily:delivery_by_hour',
    'mediasmart_daily:delivery_by_publisher',
    'mediasmart_daily:creative_daily',
]

for j in jobs_to_run:
    encoded = j.replace(':', '%3A')
    url = f'{base}/jobs/{encoded}/run'
    req = urllib.request.Request(url, data=b'{}', headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read())
            print(f'OK  {j}: rows={body.get("result",{}).get("rows_loaded","?")}')
    except Exception as ex:
        print(f'ERR {j}: {ex}')
```

> ⚠️ **Atenção Cloud Run timeout (30 min / 1800s):** backfill de 5+ meses pode exceder o limite.
> Se o cliente sofrer timeout (`Invoke-WebRequest: The operation has timed out`), o Cloud Run **continua rodando** —
> a resposta se perde mas os dados continuam sendo carregados. Verificar progresso via `last_loaded_date`
> no Firestore após alguns minutos **antes** de setar um novo `force_from_date` para evitar duplicação.
> Drilldowns de alta cardinalidade (geo, publisher) requerem múltiplos triggers sequenciais (ver Lições abaixo).

**Passo 3 — Remover force_from_date após backfill concluído:**
```python
# Verificar primeiro se last_loaded_date chegou perto do presente
for doc_id in jobs:
    ref = db.collection('platform_reports').document(doc_id)
    doc = ref.get().to_dict() or {}
    params = doc.get('params_json') or {}
    params.pop('force_from_date', None)
    ref.update({'params_json': params})
    print(f'Cleaned {doc_id}: last_loaded={doc.get("last_loaded_date")}')
```

### Volume real do backfill vs estimado

| Tabela | Linhas/dia D-1 (est.) | Total estimado | **Total real** | Diferença |
|---|---|---|---|---|
| `mediasmart_creative_daily` | ~606 | ~97k | **394.347** | Volume real ~4× maior (mais criativos por estratégia do que D-1) |
| `mediasmart_delivery_by_device` | ~31 | ~5k | **206.541** | Volume real ~40× maior (base de dados mais longa + variação) |
| `mediasmart_delivery_by_geo` | ~728 | ~116k | **8.417.374** | ~73× maior — geo é o maior volume do pipeline raw |
| `mediasmart_delivery_by_os` | ~51 | ~8k | **273.799** | ~34× maior |
| `mediasmart_delivery_by_hour` | ~107 | ~17k | **5.430** | Dados só a partir de 2026-05-28 — sem dados hourly anteriores na API |
| `mediasmart_delivery_by_publisher` | ~9.820 | ~1.57M | **9.804.184** | ~6× maior — publisher é o 2º maior volume |

> **Lição:** as estimativas de D-1 refletem apenas a campaña mais recente; o histórico acumula muito mais dados.

### Lições aprendidas do backfill (para futuras plataformas)

1. **REQUEST_TIMEOUT_SECONDS mínimo 60s** para qualquer job de alta cardinalidade.
   Drilldowns com 3+ dimensões (geo: country+area+city; publisher: company+url+exchange) levam >10s
   para a MediaSmart API gerar o relatório CSV. Com 10s o timeout acontece **antes** de começar a receber dados.

2. **Cloud Run 30-min timeout + múltiplos triggers:**
   - Backfill de geo (~8.4M rows) requereu ~8 triggers; publisher (~9.8M) requereu ~10 triggers
   - Após timeout no cliente, verificar `last_loaded_date` no Firestore para ver até onde o Cloud Run chegou
   - **CRÍTICO:** o Cloud Run continua rodando após o timeout do cliente — sempre confirmar `max_day` real no BQ antes de setar o próximo `force_from_date`
   - Fórmula segura: `force_from_date = max_day_atual + 1 dia`

3. **Deduplicação em caso de overlap:**
   Se dois triggers carregarem o mesmo período, deduplicar com:
   ```sql
   CREATE OR REPLACE TABLE `adframework.raw.<tabela>` AS
   SELECT DISTINCT * FROM `adframework.raw.<tabela>`;
   ```
   Funciona apenas para **duplicatas exatas** (toda a linha idêntica). Confirmar com:
   ```sql
   SELECT COUNT(*) AS total,
          COUNT(DISTINCT CONCAT(day,'|',event_id,'|',campaign_id,'|',strategy_id)) AS unique_keys
   FROM `adframework.raw.<tabela>`
   WHERE day = 'YYYY-MM-DD';
   -- total / unique_keys = fator de duplicação
   ```

4. **HTTP 503 "Login failed: Under maintenance"** — erro transiente da MediaSmart.
   Aguardar 30 segundos e re-triggrar. Não é problema de credenciais.

5. **delivery_by_hour sem dados antes de 2026-05-28:**
   A MediaSmart não tem analytics hourly para contas monitoradas antes dessa data.
   A API retorna resultado vazio para qualquer período anterior — sem erro, só sem dados.
   Range correto: 2026-05-28 → hoje. Não tentar backfill de jan→mai27.

### Nota sobre creative_id nas tabelas que "faltam"

`raw.mediasmart_daily` (T6 source) tem coluna `creative_id` mas está **sempre NULL** — o job diário
não inclui `creativeid` no drilldown por decisão intencional (ver seção "Descobertas delivery vs daily").

O `creative_id` completo para análise histórica virá de `raw.mediasmart_creative_daily` após o backfill.
Para jan–jun/2026, o backfill do `mediasmart_daily:creative_daily` populará `creative_id` em todos os dias
onde houve impressão de criativo — cobrindo o histórico que a `raw.mediasmart_daily` não tem.

### Próximos passos após backfill ✅ (CONCLUÍDO — itens a executar)

1. ✅ ~~Executar backfill~~ — concluído 2026-06-12
2. Implementar as DDLs das STG (T7–T13) em BigQuery
3. Verificar que soma de impressões por device bate com total de `stg.ms_delivery` (sanity check)
4. Verificar que `creative_id` populado no backfill bate com IDs em `stg.ms_creatives`
5. Integrar `stg.ms_delivery_by_publisher` com análise de inventory (publishers com maior spend vs delivery)
6. Considerar futura grande ingestão para popular `creative_id` histórico nas tabelas que o têm NULL

---

## Caminhos de repositório e arquivos-chave do ETL

```
Repo ETL (código Python):
  rshiro-newad/adframework
  Local: c:\Users\dougl\OneDrive\Área de Trabalho\NEWAD PROJECT\DATASETS\adframework
  Branch ativa: chore/machine-restore-org

Arquivos críticos para ingestão MediaSmart:
  adframework_python/src/base.py
    └─ normalize_data(): normalização BQ-safe (lowercase, spaces→_, remove non-alphanum)
       NÃO fazer mapping semântico aqui — apenas normalização

  adframework_python/src/connectors/mediasmart.py
    └─ RATE_LIMIT_DELAY = 0.6       (commit 4d1662f — era 0.3; 100 req/min = 22% abaixo do limite 128/min)
    └─ REQUEST_TIMEOUT_SECONDS = 60 (commit 7bee5f9 — era 10; drilldowns geo/publisher precisam >10s de geração)
    └─ fetch_data(): GET → CSV → pd.read_csv → normalize_data
    └─ _build_url(): monta URL com drilldown, kpis, format=csv, rules, raw=true

  adframework_python/src/bigquery.py
    └─ load_data(): lógica CRÍTICA para criação/atualização de tabelas:
       - Tabela NOVA: cria schema a partir de TODAS as colunas do DataFrame
       - Tabela EXISTENTE: dropa colunas do DataFrame não presentes no schema BQ
         → por isso tabelas pré-existentes com schema errado causam perda de colunas

  adframework_python/src/orchestrator.py
    └─ _resolve_bq_target(): usa table_name+dataset_id (ignora bq_destiny legado)
    └─ _get_date_range(): lê force_from_date de params_json; fallback para max(day) do BQ
    └─ _run_mediasmart_daily(): loop diário de ingestão
    └─ run_job(): entry point chamado pela HTTP API
    └─ run_all(), run_due_jobs(): bulk triggers

  adframework_python/main.py
    └─ FastAPI routes:
       GET  /jobs                  → lista jobs (platform_reports enabled)
       POST /jobs/{job_name}/run   → dispara job síncrono
       POST /run-all               → dispara todos
       POST /scheduler/run-due     → dispara jobs com schedule_cron due

GCP:
  Cloud Run service:  https://adframework-etl-911847757485.us-central1.run.app
  Cloud Scheduler:    adframework-etl-daily (05:00 UTC → /scheduler/run-due)
  Firestore DB:       adframework → platform_reports (docs = jobs config)
  BigQuery:           adframework.raw.* (tabelas de ingestão)
  Secret Manager:     mediasmart_username, mediasmart_password

Repo docs (este repo):
  newad-adframework-bq
  Local: c:\Users\dougl\newad-adframework-bq
  Arquivos relevantes:
    docs/mediasmart_stg_design.md   ← este arquivo
    docs/known_issues.md            ← problemas identificados e resoluções
    docs/API_Doc_MediaSmart.md      ← documentação oficial da API (4.601 linhas)
    docs/mediasmart_api_reference.md← resumo dos endpoints para o ETL
    CHANGELOG.md                    ← histórico cronológico de todas as mudanças
```

---

## Princípio de design para novas árvores

**As tabelas MediaSmart servem de referência para MGID e futuras plataformas.**
A estrutura de IDs e hierarquia definida aqui (client → campaign → strategy → creative)
deve guiar como estruturar device, geo e publisher nas outras plataformas.

MGID seguirá o mesmo padrão:
- `stg.mgid_campaigns` — dimensão de campanhas
- `stg.mgid_delivery` — fato principal
- `stg.mgid_delivery_by_device` — device
- `stg.mgid_delivery_by_geo` — geo

Siprocal é mais simples (sem catálogo próprio):
- `stg.siprocal_delivery` — fato único

---

## Relação com platform_client_links

Após as tabelas STG estarem definidas, o fluxo de atribuição será:

```
stg.ms_clients.ms_client_id  →  platform_client_links.platform_client_id
stg.ms_clients.ms_event_id   →  JOIN com stg.ms_client_campaigns.ms_event_id
                              →  JOIN com raw.mediasmart_delivery.eventid
```

O `platform_client_links` usará `ms_event_id` como chave de vinculação técnica
e `ms_client_id` como identificador legível que aparece nos relatórios.

---

## Notas de implementação

- Deduplicação: usar `QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY updated_at DESC) = 1`
- Geração do `ms_client_id`: `LOWER(REGEXP_REPLACE(name, r'[^a-zA-Z0-9]', '_')) || '_' || LEFT(id, 8)`
- Estratégia MERGE para campaigns: `MERGE ON ms_campaign_id WHEN MATCHED → UPDATE, WHEN NOT MATCHED → INSERT`
- Nunca usar `WRITE_TRUNCATE` em campaigns — risco de perder histórico de campanhas deletadas da plataforma
