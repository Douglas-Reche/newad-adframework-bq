# MGID — RAW Layer Sketch

> Status: ESBOÇO — não é plano oficial.
> Criado em: 2026-06-18
> Metodologia: análise campo a campo de `MGID_API_Doc.md` (3.546 linhas), sem herança do pipeline atual.
> Gold layer: desacoplado deste documento — será desenhado após análise equivalente de Siprocal.

---

## O que é a MGID

MGID é uma rede de publicidade nativa (native advertising). Diferente da MediaSmart (DSP/RTB), a MGID não tem leilão em tempo real — o modelo é CPC direto, com distribuição em widgets de publishers parceiros.

Conceitos-chave da MGID:
- **Teaser** = criativo (título + imagem + texto + link)
- **Widget** = espaço de exibição dentro de um publisher (o equivalente ao "placement" no MS)
- **Source** = publisher/site onde o widget está hospedado
- **Conversão tem 3 estágios fixos:** `interest` → `decision` → `buy` (não são slots numéricos como no MS)
- Não há advertiser separado — o nível mais alto é o **client** (a conta da agência)

---

## Estrutura geral

```
CATÁLOGO                        ANALYTICS
────────                        ─────────
T1. mg_clients                  T4.  mg_delivery              ← fato base (principal ETL)
T2. mg_campaigns                T5.  mg_delivery_by_geo
T3. mg_teasers                  T6.  mg_delivery_by_device
                                T7.  mg_delivery_by_os
                                T8.  mg_delivery_by_browser
                                T9.  mg_delivery_by_hour
                                T10. mg_delivery_by_widget
                                T11. mg_delivery_video
                                T12. mg_quality_by_source
```

**Como as tabelas se conectam:**
- `T2.id` → chave de join com todas analytics (`campaign_id`)
- `T3.id` → chave de join com T4+ quando teaser é dimensão (`teaser_id`)
- MGID não tem `event_id` — o vínculo client→campaign está implícito no `client_id` usado na chamada

---

## CATÁLOGO

---

### T1 — `mg_clients` — ❌ ELIMINADO (testado e refutado em 2026-06-18)

**Status original deste documento (ESBOÇO, não testado):** previa combinar `GET /v1/clients/{clientId}` + `GET /v1/goodhits/clients/{clientId}/campaigns`, com `client_ids` como lista fixa mantida pelo orquestrador, e `advertiserName`/`category_name` da campanha mais recente.

**O que a validação contra a API real mostrou:**
- `GET /v1/clients/{id}` retorna **só** `id, timezone, wallet` (financeiro) — nenhum dado de nome/categoria.
- A conta MGID da NewAd é **única** (`MGID_CLIENT_ID`) — não existe lista de `client_ids` por advertiser; a nota da linha 19 deste mesmo doc ("não há advertiser separado — o nível mais alto é o client/conta da agência") já indicava isso, mas o T1 original foi escrito inconsistente com essa observação.
- Busca real de 173 campanhas via `GET /v1/goodhits/clients/{id}/campaigns` (sem filtro, e depois com `fields=['advertiserName']` explícito): `advertiserName` **nunca veio**, mesmo sendo aceito como parâmetro válido. É campo write-only (obrigatório no POST de criação, ausente em qualquer leitura).
- `category` existe e retorna corretamente, mas é a categoria temática da campanha (IAB-like), não o cliente — 76% das campanhas reais vieram com `category = "Other services"`.

**Decisão final:** `raw.mg_clients` não existe. A dimensão cliente da MGID é resolvida **na STG**, via:
```
raw.mg_campaigns.id → core.platform_client_links.link_value (campaignid) → .client_id → core.dim_client.name/sector
```
`core.dim_client` já expõe `client_id, name, sector` — sem necessidade de tabela intermediária.

**Gap operacional:** 47 de 173 campanhas ativas (27%) ainda sem vínculo em `platform_client_links` — pendência comercial, não técnica.

Ver decisão completa em `raw_layer_design.md` (seção T1) e `CHANGELOG.md` (entrada 2026-06-18).

---

### T2 — `mg_campaigns` — ✅ VALIDADO EM PRODUÇÃO (2026-06-22)

**Endpoint:** `GET /v1/goodhits/clients/{MGID_CLIENT_ID}/campaigns` — conta única, sem loop de client_ids
**Grain:** 1 linha por campanha
**Ingestão:** diária
**Resultado real:** 173 linhas, 173 `campaign_id` distintos. DDL: `raw/ddl/mg_campaigns.sql`. Connector: `fetch_campaigns_normalized()`. Detalhes completos em `CHANGELOG.md` (entrada 2026-06-22).

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `id` | STRING | ID da campanha — PK | `78901` |
| `name` | STRING | Nome da campanha | `CORA_NATIVA_JUNHO26` |
| `campaign_type` | STRING | `product / content / push / search_feed` | `product` |
| `language` | INT | ID do idioma da campanha | `8` (Português) |
| `status_id` | INT | Código do status (ver tabela abaixo) | `6` |
| `status_name` | STRING | Descrição do status | `Unlimited and active` |
| `status_reason` | STRING | Razão do status atual | `null` |
| `category_id` | STRING | ID da categoria de conteúdo | `152` |
| `category_name` | STRING | Nome da categoria | `Financial Assistance` |
| `start_date` | DATE | Data de início | `2026-01-01` |
| `end_date` | DATE | Data de término (null = sem fim) | `null` |
| `when_add` | TIMESTAMP | Data de criação da campanha | `2025-12-15` |
| `sources_optimization` | BOOLEAN | Usa Sources Optimization | `false` |
| `search_feed_provider_id` | INT | ID do provedor de search feed (só search_feed) | `null` |
| `keyword` | STRING | Palavra-chave (só search_feed) | `null` |
| `statistics_clicks` | INT | Cliques totais acumulados hoje | `1250` |
| `statistics_wages` | FLOAT | Gasto acumulado hoje | `87.50` |

**Subcampo: `limitsFilter` (orçamento e limites)**

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `limit_type` | STRING | Tipo de limite: `clicks_limits / budget_limits` | `budget_limits` |
| `daily_limit` | FLOAT | Limite diário | `50.00` |
| `overall_limit` | FLOAT | Limite total da campanha | `1500.00` |
| `split_daily_limit_evenly` | BOOLEAN | Distribui tráfego diário uniformemente | `true` |

**Subcampo: `trackingOptions` (UTM)**

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `utm_source` | STRING | UTM source configurado | `mgid` |
| `utm_campaign` | STRING | UTM campaign | `cora_nativa_jun26` |
| `utm_medium` | STRING | UTM medium | `cpc` |
| `utm_custom` | STRING | Tags customizadas com macros | `{widget_id}_{teaser_id}` |

**Subcampo: `domainsFilter` (bloqueio de domínios)**

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `domains_filter_type` | STRING | `off / except / only` | `except` |
| `domains_blocked` | STRING→JSON | Lista de domínios bloqueados | `["spam.com"]` |

**Subcampo: `widgetsFilterUid` (bloqueio de widgets)**

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `widgets_filter_type` | STRING | `off / except / only` | `off` |
| `widgets_blocked` | STRING→JSON | Map widget_uid → subid bloqueado | `{"1234567": []}` |

**Subcampo: `targets` (geo targeting)**

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `geo_enabled` | BOOLEAN | Geo targeting ativo | `true` |
| `geo_countries` | STRING→JSON | Países alvo | `["BR"]` |
| `geo_cities` | STRING→JSON | Cidades alvo (IDs) | `["2"]` |

**Subcampo: `browserTargeting` / `targets` (OS e browsers)**

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `os_targets` | STRING→JSON | OS alvos | `["android10mobile", "ios17mobile"]` |
| `browser_targets` | STRING→JSON | Browsers alvo | `["chrome", "safari"]` |
| `language_targets` | STRING→JSON | IDs de idiomas alvo | `[8, 1]` |

**Tabela de status:**

| status_id | Descrição |
|---|---|
| 1 | Blocked (end date reached) |
| 2 | Reached total budget |
| 3 | Reached total clicks |
| 4 | Blocked by manager |
| 5 | Negative balance |
| 6 | Unlimited and active |
| 7 | Active (daily limit not reached) |
| 8 | Active (yesterday hit daily limit) |
| 9 | Daily budget limit reached |
| 10 | Daily clicks limit reached |
| 11 | Paused (time schedule) |
| 12 | Stopped (client delayed) |
| 13 | Stopped by manager |
| 14 | Deleted |
| 15 | Rejected |
| 19 | Stopped (creativity violation) |

#### Código de ingestão — revisado em 2026-06-18 após validação contra API real

**Correções vs. versão original:** (1) `client_id` é único (conta NewAd, env var) — não há lista para iterar; (2) `advertiser_name` removido — confirmado que a API nunca retorna esse campo em leitura, mesmo pedido explicitamente via `fields=[]`. `client_id` (FK para o cliente real) só é resolvido depois, na STG, via `core.platform_client_links`.

```python
def ingest_mg_campaigns(api_client, bq_client, mgid_client_id: str):
    # mgid_client_id = conta única da NewAd (env var MGID_CLIENT_ID) — não é loop
    campaigns = api_client.get(f"/v1/goodhits/clients/{mgid_client_id}/campaigns")

    rows = []
    for c in campaigns:
        limits = c.get("limitsFilter", {})
        rows.append({
            "campaign_id":    str(c["id"]),
            "campaign_name":  c["name"],
            "start_date":     c.get("start_date"),
            "end_date":       c.get("end_date"),
            "status_id":      c.get("status_id"),
            "status_name":    c.get("status_name"),
            "campaign_type":  c.get("campaign_type"),
            "category_name":  c.get("category_name"),
            # budget
            "limit_type":     limits.get("limit_type"),
            "daily_limit":    limits.get("daily_limit"),
            "overall_limit":  limits.get("overall_limit"),
            "split_daily_limit_evenly": limits.get("split_daily_limit_evenly"),
            # timestamps
            "when_add":       c.get("when_add"),
            "ingested_at":    datetime.utcnow().isoformat(),
        })

    # catálogo — full refresh diário
    bq_client.load_table("raw.mg_campaigns", rows, write_disposition="WRITE_TRUNCATE")
```

---

### T3 — `mg_teasers`

**Endpoint:** `GET /v1/goodhits/clients/{clientId}/teasers[/{teaserId}]`
**Grain:** 1 linha por teaser (criativo)
**Ingestão:** diária

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `id` | STRING | ID do teaser — PK | `987654` |
| `campaign_id` | STRING | Campanha vinculada | `78901` |
| `title` | STRING | Título do teaser | `Conta digital sem taxa` |
| `advert_text` | STRING | Texto descritivo | `Abra sua conta em 5 min` |
| `url` | STRING | URL de destino | `https://bancocora.com.br` |
| `image_link` | STRING | URL da imagem | `https://img.mgid.com/...` |
| `crop_left` | INT | Recorte da imagem à esquerda | `0` |
| `crop_top` | INT | Recorte da imagem no topo | `0` |
| `crop_width` | INT | Largura do recorte | `600` |
| `category_id` | STRING | ID da categoria do teaser | `152` |
| `category_name` | STRING | Nome da categoria | `Financial Assistance` |
| `status` | STRING | `onModeration / rejected / active / new / goodPerformance / badPerformance / blocked / campaignBlocked` | `active` |
| `rejection_reason` | STRING | Razão de rejeição (se status=rejected) | `null` |
| `price_of_click` | FLOAT | CPC padrão configurado | `0.30` |
| `price_by_geo` | STRING→JSON | CPC por grupo geográfico | `[{"locationId":"br","priceOfClick":"0.30"}]` |
| `whether_show_good_price` | BOOLEAN | Exibe preço do produto | `false` |
| `good_price` | FLOAT | Preço do produto | `null` |
| `good_old_price` | FLOAT | Preço antigo do produto | `null` |
| `currency_id` | INT | Moeda do preço do produto | `null` |
| `call_to_action` | STRING | CTA configurado | `null` |
| `stat_clicks_total` | INT | Cliques totais históricos | `12500` |
| `stat_clicks_today` | INT | Cliques hoje | `87` |
| `stat_clicks_yesterday` | INT | Cliques ontem | `103` |
| `stat_shows_total` | INT | Exibições totais (impressões) | `890000` |
| `stat_shows_today` | INT | Exibições hoje | `6200` |
| `stat_shows_yesterday` | INT | Exibições ontem | `7400` |
| `stat_spent_total` | FLOAT | Gasto total histórico | `3750.00` |
| `stat_spent_today` | FLOAT | Gasto hoje | `26.10` |
| `stat_spent_yesterday` | FLOAT | Gasto ontem | `30.90` |
| `stat_ctr` | FLOAT | CTR geral | `0.00140` |
| `conv_interest_all` | INT | Conversões interest (total) | `230` |
| `conv_decision_all` | INT | Conversões decision (total) | `85` |
| `conv_buying_all` | INT | Conversões buy (total) | `42` |
| `conv_interest_yesterday` | INT | Conversões interest ontem | `12` |
| `conv_decision_yesterday` | INT | Conversões decision ontem | `5` |
| `conv_buying_yesterday` | INT | Conversões buy ontem | `2` |

---

## ANALYTICS

O endpoint principal de analytics da MGID é:
`GET /v1/goodhits/clients/{clientId}/statistics-reports`

Permite até **3 dimensões por chamada** e retorna as métricas selecionadas. Max 90 dias por range. As tabelas abaixo representam chamadas com diferentes combinações de dimensões.

---

### T4 — `mg_delivery` (fato base)

**Endpoint:** `GET /v1/goodhits/clients/{clientId}/statistics-reports`
**Dimensões:** `day, campaignId, campaignName, campaignType, teaserId`
**Grain:** dia + campanha + teaser
**Ingestão:** diária incremental
**⚠️ Limite da API: max 90 dias por request — backfill em blocos de 90 dias**

#### Dimensões

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `day` | DATE | Data | `2026-06-10` |
| `campaign_id` | STRING | ID da campanha | `78901` |
| `campaign_name` | STRING | Nome da campanha | `CORA_NATIVA_JUNHO26` |
| `campaign_type` | STRING | `product / content / push / search_feed` | `product` |
| `teaser_id` | STRING | ID do teaser | `987654` |

#### KPIs — Entrega base

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `ad_requests` | INT | Solicitações de anúncio recebidas | `850000` |
| `impressions` | INT | Impressões servidas | `12500` |
| `clicks` | INT | Cliques | `87` |
| `ctr` | FLOAT | Click-through rate | `0.00696` |
| `viewability` | FLOAT | Taxa de viewability (% de impressões visíveis) | `72.5` |

#### KPIs — Financeiro

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `spent` | FLOAT | Gasto (custo do cliente) | `26.10` |
| `cpc` | FLOAT | CPC efetivo | `0.30` |
| `cpc_without_data_fee` | FLOAT | CPC sem taxa de dados | `0.28` |
| `vcpm` | FLOAT | vCPM (CPM visível) | `2.09` |
| `vctr` | FLOAT | vCTR (CTR visível) | `0.00960` |
| `epc` | FLOAT | Earn per click (receita / cliques) | `0.15` |

#### KPIs — Conversões (3 estágios MGID)

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `conversions_interest` | INT | Conversões no estágio Interest | `45` |
| `conversions_decision` | INT | Conversões no estágio Decision | `18` |
| `conversions_buy` | INT | Conversões no estágio Buy | `9` |
| `conversion_rate_interest` | FLOAT | Taxa de conversão Interest | `0.517` |
| `conversion_rate_decision` | FLOAT | Taxa de conversão Decision | `0.207` |
| `conversion_rate_buy` | FLOAT | Taxa de conversão Buy | `0.103` |
| `conversion_cost_interest` | FLOAT | CPA no estágio Interest | `0.58` |
| `conversion_cost_decision` | FLOAT | CPA no estágio Decision | `1.45` |
| `conversion_cost_buy` | FLOAT | CPA no estágio Buy | `2.90` |

#### KPIs — Receita e rentabilidade

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `revenue` | FLOAT | Receita gerada (valor dos eventos de conversão) | `135.00` |
| `profit` | FLOAT | Lucro = revenue - spent | `108.90` |
| `roas` | FLOAT | Return on ad spend (revenue / spent) | `5.17` |

---

### T5 — `mg_delivery_by_geo`

**Dimensões:** `day, campaignId, country, region`
**Grain:** T4 + país + região
**⚠️ Alta cardinalidade — paginar se necessário**

| Dimensão extra | Tipo | O que é | Exemplo |
|---|---|---|---|
| `country` | STRING | Código ISO do país | `BR` |
| `region` | STRING | Código da região/estado | `SP` |

KPIs: todos de T4

---

### T6 — `mg_delivery_by_device`

**Dimensões:** `day, campaignId, deviceType`
**Grain:** T4 + tipo de device

| Dimensão extra | Tipo | O que é | Exemplo |
|---|---|---|---|
| `device_type` | STRING | `desktop / mobile / tablet / smarttv` | `mobile` |

KPIs: todos de T4

---

### T7 — `mg_delivery_by_os`

**Dimensões:** `day, campaignId, os`
**Grain:** T4 + sistema operacional

| Dimensão extra | Tipo | O que é | Exemplo |
|---|---|---|---|
| `operating_system` | STRING | Código do OS (ver lista na API) | `android10mobile` |

KPIs: entrega base + financeiro + conversões

---

### T8 — `mg_delivery_by_browser`

**Dimensões:** `day, campaignId, browser`
**Grain:** T4 + navegador

| Dimensão extra | Tipo | O que é | Exemplo |
|---|---|---|---|
| `browser` | STRING | `chrome / safari / firefox / edge / operamini / ...` | `chrome` |

KPIs: entrega base + financeiro + conversões

---

### T9 — `mg_delivery_by_hour`

**Dimensões:** `day, campaignId, hour`
**Grain:** T4 + hora do dia

| Dimensão extra | Tipo | O que é | Exemplo |
|---|---|---|---|
| `hour` | INT | Hora do dia 0–23 | `14` |

KPIs: entrega base + financeiro + conversões

---

### T10 — `mg_delivery_by_widget`

**Dimensões:** `day, campaignId, widgetId, source`
**Grain:** T4 + widget + source (publisher)
**⚠️ Maior volume do pipeline MGID**

| Dimensão extra | Tipo | O que é | Exemplo |
|---|---|---|---|
| `widget_id` | STRING | ID do widget (placement) | `1234567` |
| `source` | STRING | Domínio/nome do publisher | `terra.com.br` |

KPIs: todos de T4

---

### T11 — `mg_delivery_video`

**Endpoint:** `GET /v1/goodhits/clients/{clientId}/campaigns-video-stat`
**Grain:** período + campaign_id
**Nota:** endpoint separado, só retorna dados de campanhas de vídeo
**⚠️ Retorna por período, não por dia — precisamos iterar dia a dia**

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `day` | DATE | Data | `2026-06-10` |
| `campaign_id` | STRING | ID da campanha | `78901` |
| `impressions` | INT | Impressões de vídeo | `5000` |
| `viewability` | FLOAT | Taxa de viewability | `68.0` |
| `first_quartile` | INT | Views completaram 25% | `4200` |
| `midpoint` | INT | Views completaram 50% | `3800` |
| `third_quartile` | INT | Views completaram 75% | `3400` |
| `complete` | INT | Vídeos completos | `2900` |
| `completion_rate` | FLOAT | Taxa de conclusão | `0.58` |
| `clicks` | INT | Cliques em vídeo | `45` |
| `ctr` | FLOAT | CTR do vídeo | `0.0009` |
| `spent` | FLOAT | Gasto | `25.00` |
| `cpm` | FLOAT | CPM do vídeo | `5.00` |

---

### T12 — `mg_quality_by_source`

**Endpoint:** `GET /v1/goodhits/campaigns/{campaignId}/quality-analysis-sources/`
**Grain:** campaign_id + período + source_id
**Nota:** endpoint separado de análise de qualidade por fonte — tem dados de CPC otimizado e qualityFactor não disponíveis no `statistics-reports`

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `campaign_id` | STRING | ID da campanha | `78901` |
| `date_from` | DATE | Início do período | `2026-06-01` |
| `date_to` | DATE | Fim do período | `2026-06-10` |
| `source_name` | STRING | Nome/domínio da fonte | `terra.com.br` |
| `source_id` | INT | ID numérico da fonte | `100001` |
| `clicks` | INT | Cliques da fonte | `87` |
| `ad_requests` | INT | Solicitações | `850000` |
| `impressions` | INT | Impressões | `12500` |
| `viewability` | FLOAT | Viewability % | `72.5` |
| `spent` | FLOAT | Gasto | `26.10` |
| `data_fee` | FLOAT | Taxa de dados cobrada | `1.20` |
| `cpc` | FLOAT | CPC com data fee | `0.30` |
| `cpc_without_data_fee` | FLOAT | CPC sem data fee | `0.28` |
| `ctr` | FLOAT | CTR | `0.00696` |
| `cpm` | FLOAT | CPM | `2.09` |
| `vcpm` | FLOAT | vCPM | `2.88` |
| `vctr` | FLOAT | vCTR | `0.00960` |
| `etr` | FLOAT | Estimated turn rate | `0.85` |
| `win_rate` | FLOAT | % requests ganhos | `96.22` |
| `epc` | FLOAT | Earn per click | `0.15` |
| `revenue` | FLOAT | Receita da fonte | `135.00` |
| `profit` | FLOAT | Lucro | `108.90` |
| `roas` | FLOAT | ROAS | `5.17` |
| `conversions_interest` | INT | Conversões Interest | `45` |
| `conversions_decision` | INT | Conversões Decision | `18` |
| `conversions_buy` | INT | Conversões Buy | `9` |
| `conversion_rate_interest` | FLOAT | Taxa Interest | `0.517` |
| `conversion_rate_decision` | FLOAT | Taxa Decision | `0.207` |
| `conversion_rate_buy` | FLOAT | Taxa Buy | `0.103` |
| `conversion_cost_interest` | FLOAT | CPA Interest | `0.58` |
| `conversion_cost_decision` | FLOAT | CPA Decision | `1.45` |
| `conversion_cost_buy` | FLOAT | CPA Buy | `2.90` |
| `quality_factor` | FLOAT | Fator de qualidade atual da fonte | `1.30` |
| `previous_quality_factor` | FLOAT | Fator de qualidade anterior | `0.11` |
| `quality_factor_updated_at` | TIMESTAMP | Quando foi atualizado | `2024-11-01 01:56:01` |
| `is_blocked` | BOOLEAN | Fonte está bloqueada | `false` |
| `toggle` | BOOLEAN | Toggle de habilitação | `true` |
| `can_change_toggle` | BOOLEAN | Permissão para mudar toggle | `true` |

---

## Diferenças críticas MGID vs MediaSmart

| Aspecto | MGID | MediaSmart |
|---|---|---|
| Modelo de compra | CPC direto, native ad | RTB/leilão, display/video |
| Bid funnel | Não existe | offers → bids → won |
| Criativos | Teaser (título + imagem + texto) | display, video, native, rich media |
| Publishers | Widget ID + source (domínio) | publisher + exchange + deal |
| Conversões | 3 estágios: interest/decision/buy | 5 slots numéricos: events1-5 |
| Hierarquia | client → campaign → teaser | advertiser → campaign → strategy → creative |
| "Strategy" | Não existe | Sim (line item filho da campaign) |
| Granular report | Max 3 dimensões, 90 dias | Sem limite declarado de dimensões |
| Video | Endpoint separado | Dentro do custom-report |
| Quality/source | Endpoint separado c/ qualityFactor | Dentro do custom-report (publisher table) |

---

## Dimensões disponíveis no `statistics-reports` não cobertas por tabela dedicada

| Dimensão | O que é | Quando faria sentido |
|---|---|---|
| `month` | Agrupamento por mês | Calculável via SQL |
| `week` | Agrupamento por semana | Calculável via SQL |
| `teaserId` sem campaignId | Teaser isolado sem campanha pai | T4 já traz o par |

---

## Métricas disponíveis no `statistics-reports` — todas inclusas no T4

Todas as métricas disponíveis no endpoint foram mapeadas em T4:
`adRequests, clicks, impressions, viewability, spent, cpc, cpcWithoutDataFee, ctr, epc, vCtr, vCpm, revenue, profit, roas, conversionsInterest, conversionsDecision, conversionsBuy, conversionsRateInterest, conversionsRateDecision, conversionsRateBuy, conversionsCostInterest, conversionsCostDecision, conversionsCostBuy`

---

## Endpoints disponíveis mas fora do escopo deste sketch

| Endpoint | O que é | Por que fora |
|---|---|---|
| `GET /v1/goodhits/campaigns/{id}/statistics?type=byClicksDetailed` | Log individual de cada clique (ip, referer, time, price) | Muito granular, sem uso para dashboard |
| `GET /v1/goodhits/campaigns/{id}/quality-analysis/{uid}` | Análise por widget específico | Coberto pelo T12 (por source) |
| `GET /v1/goodhits/campaigns/{id}/conversions` | Configuração de conversão | Metadado de configuração, não dado de entrega |
| `GET /v1/clients/{id}/sources-blocklist` | Blocklist de fontes da conta | Config operacional |
| Publisher API (`/v2/pub/account/...`) | API do lado publisher | Não somos publisher |
| Agency API (`/v1/agencies/...`) | Gestão de agência e saldos | Financeiro, não entrega |

---

## Pendências

- [ ] Confirmar se teasers em campanhas antigas ainda retornam via API (sem paginação)
- [ ] Avaliar volume de T12 (quality_by_source) — pode ser grande por campanha com muitas fontes
- [ ] Confirmar granularidade de `statistics-reports`: retorna dia a dia com `day` como dimensão?
- [ ] Testar se `teaserId` como dimensão no `statistics-reports` funciona sem `campaignId`
- [ ] Confirmar se `cpc_without_data_fee` aparece nos nossos dados (relevante se usarmos data targeting)
- [ ] Snapshot com campanhas de Cora/TecPar/Luckbet para validar quais KPIs são não-null
