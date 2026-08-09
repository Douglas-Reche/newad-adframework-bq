# MediaSmart — RAW Layer Sketch

> 📦 **HISTÓRICO** — esboço de análise pré-implementação, superado pelo design oficial
> validado em `raw_layer_design.md`. Mantido como referência do raciocínio original de
> mapeamento campo a campo. Movido para `docs/_legacy/` em 2026-08-09.

> Status: ESBOÇO — não é plano oficial.
> Atualizado: 2026-06-18
> Metodologia: análise campo a campo de `API_Doc_MediaSmart.md` (4.601 linhas), sem herança do pipeline atual.
> Gold layer: desacoplado deste documento — será desenhado após análise equivalente de MGID e Siprocal.

---

## Estrutura geral

A API da MediaSmart entrega dois tipos de dado:

- **Catálogo** — quem existe na plataforma (advertisers, campaigns, strategies, creatives). Dado estático, muda raramente. Ingestão diária como snapshot.
- **Analytics** — o que foi entregue (impressões, cliques, custo, conversões...). Dado transacional, acumula todo dia. Ingestão diária incremental.

```
CATÁLOGO                        ANALYTICS
────────                        ─────────
T1. ms_advertisers              T4.  ms_delivery              ← fato base ✅ validado
T2. ms_campaigns ✅ validado     T5.  ms_delivery_by_geo
T3. ms_creatives ✅ validado     T6.  ms_delivery_by_device
   (ex-T3 ms_strategies          T7.  ms_delivery_by_publisher
    eliminada como tabela        T8.  ms_delivery_by_hour
    própria — ver nota acima)    T9.  ms_delivery_by_audience
                                T10. ms_delivery_by_connection
                                T11. ms_delivery_by_browser
                                T14. ms_revenue
                                T15. ms_unique_users
```

**Como as tabelas se conectam:**
- `T1.event_id` → chave de join com todas as tabelas de analytics (`event_id`)
- `T2.id` → chave de join com analytics (`campaign_id` / `controlid`)
- `T3.id` → chave de join com analytics (`strategy_id`)
- `T4.id` → chave de join com T6 (`creative_id`)
- O vínculo advertiser→campaign NÃO existe no endpoint de catálogo — só aparece nas tabelas de analytics via `event_id`

---

## CATÁLOGO

---

### T1 — `ms_advertisers`

**Endpoint:** `GET /api/advertisers`
**Grain:** 1 linha por advertiser (cliente: Cora, TecPar, Luckbet...)
**Ingestão:** diária ou sob demanda

> **Decisão de design (2026-06-18):** T1 de MediaSmart e MGID seguem schema unificado com os campos `client_id, client_name, category, platform`. Para MediaSmart, todos os campos vêm diretamente do endpoint `/api/advertisers`.

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `client_id` | STRING | `event_id` — ID técnico completo, chave de join com analytics | `newad_brazil-2ruu4won...` |
| `client_name` | STRING | Nome do cliente na plataforma | `Cora` |
| `category` | STRING | Categoria de mercado IAB | `IAB13` |
| `platform` | STRING | Identificador da plataforma | `mediasmart` |
| `event_id` | STRING | Mantido para compatibilidade de join com analytics | `newad_brazil-2ruu4won...` |
| `id` | STRING | Sufixo do event_id — ID curto | `2ruu4won...` |
| `domain` | STRING | Domínio do site do anunciante | `bancocora.com.br` |
| `sensitive_content` | BOOLEAN | Conteúdo sensível | `false` |

#### Código de ingestão planejado

```python
def ingest_ms_advertisers(api_client, bq_client):
    # único endpoint, retorna todos os advertisers da conta
    advertisers = api_client.get("/api/advertisers")

    rows = []
    for a in advertisers:
        rows.append({
            "client_id":         a["event_id"],       # ID nativo MS — mapeado para newad_client_id na gold
            "client_name":       a["name"],
            "category":          a.get("iab_category"),
            "platform":          "mediasmart",
            "event_id":          a["event_id"],        # mantido para join com tabelas de analytics
            "id":                a["id"],              # sufixo curto do event_id
            "domain":            a.get("domain"),
            "sensitive_content": a.get("sensitive_content"),
            "ingested_at":       datetime.utcnow().isoformat(),
        })

    # catálogo pequeno — full refresh diário
    bq_client.load_table("raw.ms_advertisers", rows, write_disposition="WRITE_TRUNCATE")
```

---

### T2 — `ms_campaigns` — ✅ VALIDADO EM PRODUÇÃO (2026-06-22)

**Endpoint:** `GET /api/campaign/:id` (corpo completo)
**Grain:** 1 linha por campanha
**Ingestão:** diária
**Nota:** `/api/campaigns` (sem ID) retorna só sumário — o corpo completo exige chamada individual por `:id`
**Resultado real:** 14 linhas, 14 `campaign_id` distintos, 100% com `client_id`. DDL: `raw/ddl/ms_campaigns.sql`. Connector: `fetch_campaigns_normalized()`. `goal`, `client_pricing` e `conversion_name_1-5` confirmados sempre vazios em produção — omitidos do schema final. Detalhes completos (incluindo 3 bugs de tipo numérico) em `CHANGELOG.md` (entrada 2026-06-22).

#### Campos de primeiro nível

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `id` | STRING | ID da campanha — PK | `ncfv7ti3k4y0zg0a...` |
| `name` | STRING | Nome | `CORA_CONTADIGITAL_MAIO26` |
| `description` | STRING | Descrição livre (não aparece na UI) | `null` |
| `state` | STRING | `active / inactive / deleted / preview / imported` | `active` |
| `type` | STRING | `generic / dooh / smart-tv / synchronized` | `generic` |
| `color` | STRING | Cor usada na UI | `#4CAF50` |
| `tags` | STRING→JSON | Labels para busca | `["video", "junho"]` |
| `tracking_tool` | STRING | `mediasmart / appsflyer / adjust / branch / kochava / SKAdNetwork` | `mediasmart` |
| `viewability_tracking_tool` | STRING | Ferramenta de viewability | `mediasmart viewability` |
| `cross_device` | BOOLEAN | Sincroniza Smart TV com outros devices do household | `false` |
| `ghost_placebo` | BOOLEAN | Usa Ghost Ads (grupo controle) | `false` |
| `placebo_percentage` | FLOAT | % do tráfego para o placebo | `10.0` |
| `placebo_hold_days` | INT | Dias de hold do placebo | `30` |
| `measure_viewability` | BOOLEAN | Mede viewability | `false` |
| `accept_googleadx_fee` | BOOLEAN | Aceita custo adicional Google AdX | `false` |
| `attribution_window_on_click` | INT | Janela de atribuição por clique (dias) | `7` |
| `attribution_window_on_impression` | INT | Janela de atribuição por impressão (dias) | `1` |
| `conversion_one_is_required` | BOOLEAN | Slots 2–5 só contam se slot 1 ocorreu antes | `false` |
| `supports_many_conversions_one` | BOOLEAN | Aceita mais de uma conversão 1 por usuário | `false` |
| `supports_many_conversions_other` | BOOLEAN | Aceita mais de uma conversão 2–5 por usuário | `false` |
| `count_reengagement_events` | BOOLEAN | Conta eventos de re-engajamento | `false` |
| `opportunity_window` | STRING | Janela Cross TV→Device: `thirty_seconds / five_minutes / one_hour / twelve_hours / one_day` | `null` |
| `bundle` | STRING | Bundle ID do app promovido | `com.example.app` |
| `empowered_by_liveramp` | BOOLEAN | Usa RampIDs para frequency cap e cross-screen | `false` |
| `last_enabled_at` | TIMESTAMP | Última vez que foi ativada | `2026-05-10` |
| `created_at` | TIMESTAMP | Data de criação | `2025-01-15` |
| `updated_at` | TIMESTAMP | Última atualização | `2026-06-09` |

#### Subcampo: `client_pricing`

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `client_pricing_model` | STRING | Modelo cobrado ao cliente: `cpm / cpc / cpa` | `cpm` |
| `client_pricing_value` | FLOAT | Valor por unidade | `10.0` |

#### Subcampo: `schedule`

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `started_at` | DATE | Data de início | `2025-08-01` |
| `finished_at` | DATE | Data de término | `2026-06-30` |
| `max_global_cost` | FLOAT | Budget total lifetime | `14559.0` |
| `max_daily_cost` | FLOAT | Budget máximo por dia | `80.0` |
| `max_global_impressions` | INT | Cap de impressões total | `4585000` |
| `max_daily_impressions` | INT | Cap de impressões por dia | `65000` |
| `max_global_clicks` | INT | Cap de cliques total | `5000` |
| `max_daily_clicks` | INT | Cap de cliques por dia | `500` |
| `delivered_cost` | FLOAT | Custo acumulado entregue até agora | `3280.50` |
| `daily_limits_type` | STRING | Pacing: `auto / manual` | `auto` |
| `uniform_distribution` | BOOLEAN | Distribui entrega uniformemente no dia | `true` |
| `one_click_per_user` | BOOLEAN | Para após um clique por usuário | `false` |
| `add_other_costs_to_limits` | BOOLEAN | Inclui outros custos no budget | `true` |
| `budget_limit_publisher` | FLOAT | % máximo do budget para um único publisher | `50.0` |
| `timezone` | STRING | Timezone da campanha | `America/Sao_Paulo` |
| `max_impressions_user` | INT | Frequency cap: lifetime por usuário | `50` |
| `max_impressions_user_day` | INT | Frequency cap: por dia por usuário | `10` |
| `max_impressions_user_hour` | INT | Frequency cap: por hora por usuário | `3` |
| `max_adviewed_user` | INT | Freq cap viewable: lifetime | `20` |
| `max_adviewed_user_day` | INT | Freq cap viewable: por dia | `5` |
| `timing` | STRING→JSON | Dayparting: horários e dias da semana | `[{monday:true, started_time_at:"09:00"...}]` |

#### Subcampo: `deals_and_pricing`

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `goal_cpm` | FLOAT | CPM inicial / bid base | `10.0` |
| `goal_cpc` | FLOAT | Meta de CPC | `0.30` |
| `goal_cpa` | FLOAT | Meta de CPA | `3.80` |
| `goal_cpv` | FLOAT | Meta de CPV | `10.0` |
| `goal_cpv_event` | STRING | Evento de vídeo para CPV: `videostart / videomidpoint / videocomplete` | `videocomplete` |
| `goal_type` | STRING | **Derivado:** goal ativo (`CPC / CPA / CPV / CPM`) | `CPC` |
| `goal_value` | FLOAT | **Derivado:** valor do goal ativo | `0.30` |
| `event_number_for_cpa` | INT | Slot de conversão sendo otimizado (1–5) | `1` |
| `deal_policy` | STRING | Modelo de compra: `off / plc / per` | `plc` |
| `deals` | STRING→JSON | Lista de deal IDs PMP/PG | `["deal_abc"]` |
| `exchange_breakdown` | BOOLEAN | Otimização por exchange em vez de global | `false` |

#### Subcampo: `conversion_names`

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `conversion_name_1` | STRING | Label do evento 1 | `Lead` |
| `conversion_name_2` | STRING | Label do evento 2 | `Purchase` |
| `conversion_name_3` | STRING | Label do evento 3 | `null` |
| `conversion_name_4` | STRING | Label do evento 4 | `null` |
| `conversion_name_5` | STRING | Label do evento 5 | `null` |

> `targeting` e `retargeting` preservados como JSON STRING — contêm 40+ sub-campos de segmentação (age, gender, countries, device_type, os, exchanges, dmp_audiences, geolist, etc.) que podem ser parseados quando necessário.

#### Código de ingestão planejado

```python
def ingest_ms_campaigns(api_client, bq_client):
    # passo 1: lista de IDs via endpoint sumário
    summaries = api_client.get("/api/campaigns")
    campaign_ids = [c["id"] for c in summaries]

    rows = []
    for cid in campaign_ids:
        # passo 2: corpo completo por ID
        c = api_client.get(f"/api/campaign/{cid}")
        sched   = c.get("schedule", {})
        pricing = c.get("client_pricing", {})
        deals   = c.get("deals_and_pricing", {})

        rows.append({
            # campos essenciais T2
            "campaign_id":          c["id"],
            "campaign_name":        c["name"],
            "client_id":            c.get("event_id"),   # FK → ms_advertisers.client_id
            "start_date":           sched.get("started_at"),
            "end_date":             sched.get("finished_at"),
            # configuração e budget
            "state":                c.get("state"),
            "type":                 c.get("type"),
            "max_daily_cost":       sched.get("max_daily_cost"),
            "max_global_cost":      sched.get("max_global_cost"),
            "max_daily_impressions":sched.get("max_daily_impressions"),
            "max_global_impressions":sched.get("max_global_impressions"),
            "delivered_cost":       sched.get("delivered_cost"),
            "client_pricing_model": pricing.get("client_pricing_model"),
            "client_pricing_value": pricing.get("client_pricing_value"),
            "goal_type":            deals.get("goal_type"),
            "goal_value":           deals.get("goal_value"),
            # conversões
            "conversion_name_1":    c.get("conversion_name_1"),
            "conversion_name_2":    c.get("conversion_name_2"),
            "conversion_name_3":    c.get("conversion_name_3"),
            "conversion_name_4":    c.get("conversion_name_4"),
            "conversion_name_5":    c.get("conversion_name_5"),
            # segmentação preservada como JSON
            "targeting":            json.dumps(c.get("targeting", {})),
            "created_at":           c.get("created_at"),
            "updated_at":           c.get("updated_at"),
            "ingested_at":          datetime.utcnow().isoformat(),
        })
        time.sleep(0.5)  # quota: 128 req/min — ver project_mediasmart_api_quotas

    # catálogo — full refresh diário
    bq_client.load_table("raw.ms_campaigns", rows, write_disposition="WRITE_TRUNCATE")
```

---

### T3 (ex-`ms_strategies`) — ❌ ELIMINADA conforme decisão de 2026-06-18

Strategy não é mais uma tabela RAW separada (decisão "Strategy MS eliminada — hierarquia final client→campaign→creative→KPIs"). **Porém, descoberta importante em 22/06:** as strategies ainda guardam, internamente, a associação criativo↔campanha real usada pela entrega (`creativeid`) — ver T3 `ms_creatives` abaixo. Não ingerimos strategy como entidade própria, mas o campo `strategies[]` do corpo da campanha É consultado para popular `ms_creatives`.

---

### T3 — `ms_creatives` — ✅ VALIDADO E CORRIGIDO EM PRODUÇÃO (2026-06-22)

**Endpoint CORRETO:** `GET /api/campaign/:id` (corpo completo) → itera `strategies[].creatives.campaign_creatives[]`

**Endpoint tentado primeiro e descartado:** `GET /api/campaign/:id/creatives` — retorna um conjunto *diferente* de associações criativo↔campanha (direto na campanha, não na strategy). Esse conjunto **não bate** com o `creativeid` usado pela API de analytics/entrega. Investigação completa em `CHANGELOG.md` (entrada 2026-06-22, "Gap de join resolvido").

**Grain:** 1 linha por associação criativo↔strategy
**Ingestão:** diária
**Resultado real:** 201 linhas (vs 23 com o endpoint errado). `creative_id` gravado com prefixo `cr-` adicionado deliberadamente para bater 1:1 com `raw.ms_delivery.creative_id`. Join confirmado: 729/735 (99,2%) das linhas de entrega.

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `id` (do campaign_creative, dentro da strategy) | STRING | PK — prefixado com `cr-` na ingestão | `cr-xr30qufssiwwczgotqfo4s316krqerfm` |
| `campaign_id` | STRING | Campanha vinculada (passado externamente — não vem no objeto) | `ncfv7ti3k4y0zg0a...` |
| `state` (no campaign_creative, não dentro de `creative`) | STRING | `active / inactive` | `active` |
| `creative.name` | STRING | Nome do arquivo — **dentro do objeto `creative` aninhado** | `CORA_DISPLAY_300x250` |
| `creative.type` | STRING | `image / video / native / rich_media / tag / audio` | `image` |
| `creative.width` | INT | Largura em pixels | `300` |
| `creative.height` | INT | Altura em pixels | `250` |
| `creative.thumbnail_url` | STRING | URL de preview | `https://d1bckj6a4vm1bg...` |
| `creative.click_url` | STRING | URL de destino do clique | `https://bancocora.com.br` |

**`impression_pixel` não existe como campo único** — existe `impression_urls` (array), tanto no `campaign_creative` quanto dentro de `creative`. **`advert_text`/`call_to_action` confirmados ausentes em qualquer nível** (já documentado, sem mudança).

---

## ANALYTICS

Todas as tabelas de analytics vêm de um único endpoint: `GET /api/analytics/custom-report`

O que muda entre elas é o conjunto de `drilldown` (dimensões) e `kpis` (métricas) passados na query. Mesma API, grains diferentes.

---

### T5 — `ms_delivery`

**Drilldown:** `day, eventid, controlid, strategyid, strategyname, convsource`
**Grain:** dia + advertiser + campanha + strategy + fonte de conversão
**Ingestão:** diária incremental

#### Dimensões

| Campo | Tipo | Exemplo |
|---|---|---|
| `day` | DATE | `2026-06-10` |
| `event_id` | STRING | `newad_brazil-2ruu4won...` |
| `campaign_id` | STRING | `ncfv7ti3k4y0zg0a...` |
| `strategy_id` | STRING | `errlanmxbhbi6pk0...` |
| `strategy_name` | STRING | `CPM` |
| `conversion_source` | STRING | `click / impression` |

#### KPIs — Entrega base

| Campo | Tipo | O que é |
|---|---|---|
| `impressions` | INT | Impressões servidas |
| `clicks` | INT | Cliques |
| `ctr` | FLOAT | Click-through rate |

#### KPIs — Bid funnel (leilão)

| Campo | Tipo | O que é |
|---|---|---|
| `offers` | INT | Bid requests recebidos (oportunidades de compra) |
| `bids` | INT | Bids enviados |
| `won` | INT | Lances vencidos |
| `bid_percent` | FLOAT | % bids / offers |
| `won_percent` | FLOAT | % won / bids |

#### KPIs — Financeiro

| Campo | Tipo | O que é |
|---|---|---|
| `media_cost` | FLOAT | O que o cliente paga (client_cost / final price) |
| `wonprice` | FLOAT | Spend bruto na exchange antes de markup |
| `usd_cost` | FLOAT | Custo em USD |
| `tech_fee` | FLOAT | Tech fee cobrada |
| `bid_price` | FLOAT | Custo total dos bids enviados |
| `auction_charge` | FLOAT | Custo de auction charge |
| `other_cost` | FLOAT | Outros custos |
| `partner_cost` | FLOAT | Custo do parceiro |
| `deal_charge` | FLOAT | Custo de deal |
| `margin` | FLOAT | Margem absoluta |
| `margin_percentage` | FLOAT | Margem % |
| `client_revenue` | FLOAT | Receita de evento de conversão |
| `converted_client_revenue` | FLOAT | Receita em moeda do cliente |

#### KPIs — Métricas de custo derivadas

| Campo | Tipo | O que é |
|---|---|---|
| `cpm` | FLOAT | CPM efetivo |
| `cpc` | FLOAT | CPC efetivo |
| `ecpm` | FLOAT | eCPM incluindo tech fee |
| `ecpc` | FLOAT | eCPC incluindo tech fee |

#### KPIs — Conversões (slots 1–5)

| Campo | Tipo | O que é |
|---|---|---|
| `conversions_1..5` | INT | Conversões por slot |
| `ms_conversions_1..5` | INT | Conversões modeladas pela plataforma (MS) |
| `cr_1..5` | FLOAT | Conversion rate por slot |
| `cpa_1..5` | FLOAT | CPA efetivo por slot |
| `ecpa_1..5` | FLOAT | eCPA incluindo tech fee |
| `time_to_conversion_1..5` | FLOAT | Tempo médio até conversão (segundos) |

#### KPIs — Conversões incrementais (ghost ads / uplift)

| Campo | Tipo | O que é |
|---|---|---|
| `incremental_conversions_1..5` | INT | Conversões incrementais por slot |
| `incremental_conversions_percent_1..5` | FLOAT | % de conversões que são incrementais |
| `uplift_1..5` | FLOAT | Uplift vs grupo controle |
| `cpi_1..5` | FLOAT | Custo por conversão incremental |
| `assisted_conversions_1..5` | INT | Conversões assistidas estimadas |
| `assisted_rate_1..5` | FLOAT | Taxa de assistência |

#### KPIs — Vídeo

| Campo | Tipo | O que é |
|---|---|---|
| `video_start` | INT | Vídeo iniciado |
| `video_25` | INT | 25% assistido |
| `video_50` | INT | 50% assistido |
| `video_75` | INT | 75% assistido |
| `video_complete` | INT | Vídeo completo |
| `video_views` | INT | Total de video views |
| `vr_start..vr_complete` | FLOAT | View rate em cada quartil |
| `cpv_start` | FLOAT | Custo por início de vídeo |
| `cpv_complete` | FLOAT | Custo por vídeo completo |

#### KPIs — Viewability / rendering

| Campo | Tipo | O que é |
|---|---|---|
| `ad_error` | INT | Erros de renderização |
| `ad_error_percent` | FLOAT | % de erros |
| `ad_loaded` | INT | Ads carregados com sucesso |
| `ad_loaded_percent` | FLOAT | % carregados |
| `ad_viewed` | INT | Viewable impressions |
| `ad_viewed_percent` | FLOAT | % viewable |

#### KPIs — Footfall (visitas físicas)

| Campo | Tipo | O que é |
|---|---|---|
| `estimated_visits` | INT | Visitas físicas estimadas |
| `attributed_visits` | INT | Visitas atribuídas à campanha |
| `organic_visits` | INT | Visitas orgânicas (grupo controle) |
| `incremental_visits` | INT | Visitas incrementais |
| `incremental_visit_percent` | FLOAT | % de visitas incrementais |
| `exposed_percent` | FLOAT | % de usuários expostos que visitaram |

#### KPIs — SKAdNetwork (iOS attribution)

| Campo | Tipo | O que é |
|---|---|---|
| `sk_installs` | INT | Installs via SKAdNetwork |
| `sk_events` | INT | Eventos pós-install via SKAd |

---

### T6 — `ms_delivery_by_creative`

**Drilldown adicional:** `creativeid, creativename, creativetype, size, source`
**Grain:** T5 + criativo + tipo + tamanho + app_vs_web

| Dimensão extra | Tipo | Exemplo |
|---|---|---|
| `creative_id` | STRING | `05xppxdxr3pjexbc...` |
| `creative_name` | STRING | `CORA_300x250_JAN26` |
| `creative_type` | STRING | `image / video / native / rich_media` |
| `size` | STRING | `300x250` |
| `app_vs_web` | STRING | `app / web` |

KPIs: todos de T5 exceto bid funnel (offers/bids/won não fazem sentido no grain de criativo)

---

### T7 — `ms_delivery_by_device`

**Drilldown adicional:** `devicetype, os, source`
**Grain:** T5 + tipo de device + OS + app_vs_web

| Dimensão extra | Tipo | Exemplo |
|---|---|---|
| `device_type` | STRING | `smartphone / tablet / desktop / connected_tv / other` |
| `operating_system` | STRING | `android / ios / windows / other` |
| `app_vs_web` | STRING | `app / web` |

KPIs: entrega base + financeiro + conversões + vídeo

---

### T8 — `ms_delivery_by_geo`

**Drilldown adicional:** `countrycode, georegion_areaid, georegion_areaname, city`
**Grain:** T5 + país + estado + cidade
**⚠️ Alta cardinalidade — timeout mínimo 60s**

| Dimensão extra | Tipo | Exemplo |
|---|---|---|
| `country` | STRING | `Brazil` |
| `area_id` | STRING | `BR-SP` |
| `area_name` | STRING | `São Paulo` |
| `city` | STRING | `Campinas` |

KPIs: entrega base + financeiro + conversões + vídeo

---

### T9 — `ms_delivery_by_publisher`

**Drilldown adicional:** `publishercompany, publisherid, publishername, publisherurl, exchange, tagid, deal, deal_name`
**Grain:** T5 + publisher + exchange + deal
**⚠️ Maior volume do pipeline**

| Dimensão extra | Tipo | Exemplo |
|---|---|---|
| `publisher_company` | STRING | `Google` |
| `publisher_id` | STRING | `pub_abc123` |
| `publisher_name` | STRING | `UOL` |
| `publisher_url` | STRING | `uol.com.br` |
| `ad_exchange` | STRING | `OpenX` |
| `tag_id` | STRING | `tag_xyz` |
| `deal` | STRING | `deal_abc` |
| `deal_name` | STRING | `Globo PMP Deal` |
| `auction_type` | STRING | `first_price / second_price` |
| `price_floor` | FLOAT | `0.50` |

KPIs: entrega base + financeiro (vídeo opcional)

---

### T10 — `ms_delivery_by_hour`

**Drilldown adicional:** `hour`
**Grain:** T5 + hora do dia
**⚠️ Dados disponíveis apenas a partir de 2026-05-28**

| Dimensão extra | Tipo | Exemplo |
|---|---|---|
| `hour` | INT | `14` (UTC, 0–23) |

KPIs: entrega base + conversões + vídeo

---

### T11 — `ms_delivery_by_audience`

**Drilldown adicional:** `audience_name, category`
**Grain:** T5 + segmento de audiência DMP

| Dimensão extra | Tipo | Exemplo |
|---|---|---|
| `audience_name` | STRING | `high_income_users` |
| `category` | STRING | `automobile` |

KPIs: entrega base + conversões

---

### T12 — `ms_delivery_by_connection`

**Drilldown adicional:** `extendedconnectiontype, carrier, isp`
**Grain:** T5 + tipo de conexão + operadora

| Dimensão extra | Tipo | Exemplo |
|---|---|---|
| `connection_type` | STRING | `wifi / cellular_3g / cellular_4g / cellular_5g` |
| `carrier` | STRING | `Claro / Vivo / TIM` |
| `isp` | STRING | `NET Virtua` |

KPIs: entrega base + conversões

---

### T13 — `ms_delivery_by_browser`

**Drilldown adicional:** `browser, osversion, userlanguage`
**Grain:** T5 + navegador + versão de OS + idioma

| Dimensão extra | Tipo | Exemplo |
|---|---|---|
| `browser` | STRING | `Chrome / Safari` |
| `os_version` | STRING | `Android 12 / iOS 17` |
| `user_language` | STRING | `pt-BR` |

KPIs: entrega base + conversões

---

### T14 — `ms_revenue`

**Drilldown adicional:** `revenuesource`
**Grain:** T5 + slot de receita (1–5)

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `revenue_source` | STRING | Qual slot gerou a receita: `1 / 2 / 3 / 4 / 5` | `1` |
| `client_revenue` | FLOAT | Valor do evento de conversão | `1250.00` |
| `converted_client_revenue` | FLOAT | Valor convertido para moeda do cliente | `1250.00` |

> Separado de T5 pois representa o valor monetário das conversões — grain diferente quando há múltiplos slots ativos.

---

### T15 — `ms_unique_users`

**Endpoint:** `GET /v2/analytics/unique-users?campaign=:id&kpi=impression`
**Grain:** campaign_id + período + kpi
**Nota:** requer iteração por campaign_id (1 call por campanha)

| Campo | Tipo | Exemplo |
|---|---|---|
| `campaign_id` | STRING | `ncfv7ti3k4y0zg0a...` |
| `date_from` | DATE | `2026-06-01` |
| `date_to` | DATE | `2026-06-10` |
| `kpi` | STRING | `impression / events1` |
| `unique_users` | INT | `45000` |
| `unique_households` | INT | `38000` |

---

## Drilldowns disponíveis na API mas sem tabela neste esboço

Existem na API, foram descartados por ora — podem ser adicionados se surgir necessidade:

| Variável | O que é |
|---|---|
| `make / model` | Fabricante e modelo do device (Samsung Galaxy S23, iPhone 14...) |
| `idtype` | Tipo de ID do dispositivo: GAID, IDFA, web cookie |
| `interstitial` | Se o ad foi exibido em formato interstitial |
| `nativesize` | Tamanho do native ad |
| `seat_id` | ID do seat na exchange |
| `adstxt` | Publisher com ou sem ads.txt válido |
| `placebo` | Creative real vs placebo (ghost ads) |
| `weathercontextname` | Condição climática no momento da impressão |
| `peer39context / peer39contextids` | Contexto semântico Peer39 |
| `hashouseholdid / hasmediasmartid / hasidl` | Flags de presença de IDs de identidade |
| `dayoftheweek / week / month` | Agregações de tempo (calculável via SQL) |
| Campos SKAdNetwork detalhados | `skappattribution, skcompatible, skeventnum, skreinstall, skview` |
