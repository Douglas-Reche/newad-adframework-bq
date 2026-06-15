# MediaSmart API Reference

> Criado em: 2026-06-11
> Tipo: **Resumo estruturado para uso no ETL** — não é a documentação completa
> Fonte primária: `API_Doc_MediaSmart.md` (documentação oficial completa, 4.601 linhas)
> Status: ✅ ATUAL — cobre analytics, drilldowns, KPIs, management; incompleto em seções de Publisher Lists, Geolists, Deals

---

> **Para consultas completas use `API_Doc_MediaSmart.md`.** Este arquivo é um guia rápido para desenvolvimento do ETL.

---

## Servidores

| Ambiente | URL |
|---|---|
| Produção | `https://api.mediasmart.io` |
| Teste | `http://apitest.mediasmart.io` |

---

## Rotas públicas

### `GET /status`
Verifica se o servidor está online. Não requer autenticação.

---

## Autenticação

Todas as rotas privadas começam com `/api/...` e requerem header `Authorization: <token>`.

### `POST /login`

| Campo | Tipo | Descrição |
|---|---|---|
| `username` | string | Usuário |
| `password` | string | Senha |

**Resposta:**
```json
{
  "token": "<auth_token>",
  "expired_at": "<iso_date>",
  "username": "<login_username>",
  "email": "<your_email_address>",
  "organization": { "name": "...", "currency": "eur|gbr|usd" }
}
```

---

## Dictionary

### `GET /api/dictionary`
Retorna dicionário principal com constantes: countries, iab_categories, publisher_categories, exchanges, kpis, creative_sizes, currencies, drilldown, daystats_kpis, display_position, goal_kpis, operating_systems, etc.

### `GET /api/dictionary/countries`
Mapa `{código: "Nome"}` de todos os países disponíveis.

### `GET /api/dictionary/regions`
| Param | Tipo | Descrição |
|---|---|---|
| `countries` | list (opcional) | Ex: `?countries=ESP,FRA` |

### `GET /api/dictionary/cities`
| Param | Tipo | Descrição |
|---|---|---|
| `countries` | list (opcional) | |
| `regions` | list (opcional) | Ex: `?regions=ESP:GA,FRA:P` |

### `GET /api/dictionary/mosaic`
Profiles Mosaic por países.

### `GET /api/dictionary/audiences`
Audiências disponíveis no DMP da conta. Retorna `{audience_code: device_count}`.

---

## Analytics

### `GET /api/analytics/summary/:kpi`
Timeline da evolução das campanhas na última semana. `:kpi` = `wonprice | cpm | cpc | cpa1..cpa5`

**Params opcionais:** `campaigns=id1,id2,id3`

---

### `GET /api/analytics/summary/limits/:kpi`
Status de limites recentes das campanhas. `:kpi` = `wonprice | impressions | clicks`

Retorna: `{expected: {...}, observed: {...}, global: {...}}`

---

### `GET /api/analytics/summary/goals/:kpi`
Resumo de pricing goals (expected vs observed). `:kpi` = `cpm | cpv | cpc | cpa1..cpa5`

---

### `GET /api/analytics/drilldown/:variable`

Drilldown de uma única variável. Todas as variáveis disponíveis:

| Variável | Descrição |
|---|---|
| `abtag` | Strategy Name (historical) |
| `advertiser` | Advertiser Domain |
| `advertiserdescription` | Advertiser Name |
| `agegroup` | Age |
| `browser` | Browser |
| `campaign` | Campaign |
| `campaignname` | Campaign Name (historical) |
| `carrier` | Mobile operator |
| `city` | City |
| `controlid` | **Campaign ID** |
| `convsource` | Conversion source |
| `countrycode` | Country |
| `creativeid` | Campaign Creative ID |
| `creativename` | Creative Name (historical) |
| `creativetype` | Creative Type |
| `day` | Day |
| `dayoftheweek` | Day of the week |
| `deal` | Deal |
| `devicetype` | Device type |
| `domain` | Publisher Domain |
| `exchange` | Ad Exchange |
| `gender` | Gender |
| `hour` | Hour |
| `iabcategory` | IAB Category |
| `iabsubcategory` | IAB Subcategory |
| `idtype` | ID Type |
| `interstitial` | Interstitial |
| `isp` | ISP |
| `month` | Month |
| `nativesize` | Native Size |
| `os` | Operating system |
| `osversion` | Operating system version |
| `publishercompany` | Publisher Company |
| `publisherid` | Publisher ID |
| `publisherkeyword` | Publisher Keyword |
| `publishername` | Publisher Name |
| `publisherurl` | Publisher URL |
| `size` | Size |
| `source` | App vs. Web |
| `strategyid` | **Strategy ID** |
| `strategyname` | **Strategy Name** |
| `userlanguage` | Language |
| `week` | Week |
| *(+ outros: adsquareconfigid, adstxt, app_bundle, apprating, auctiontype, audience_name, bundleid, category, client_currency, costsource, creaid, creative, deal_name, dmv, dnt, extendedconnectiontype, extendeddevicetype, filtertype, georegion_areaid, georegion_areaname, hashouseholdid, hasidl, hasmaxawareness, hasmediasmartid, iab_categories, identitysolution, locationtype, make, model, organization, organizationid, peer39context, peer39contextids, placebo, pricefloor, revenuesource, seat_id, simcountrycode, skappattribution, skcompatible, skeventnum, skreinstall, skview, tagid, trackingtool, weathercontextname)* | |

**Params:**

| Campo | Obrig. | Tipo | Exemplo |
|---|---|---|---|
| `from` | sim | date | `from=2015-02-23` |
| `to` | sim | date | `to=2015-02-23` |
| `kpis` | sim | list | `kpis=cpm,cpc` |
| `limit` | não | number | `limit=50` (padrão: 25) |
| `rules` | não | list | `rules=countrycode=[ESP,FRA];os=[android]` |
| `raw` | não | boolean | `raw=true` |

---

### `GET /api/analytics/custom-report`
**Endpoint principal do nosso ETL.** Relatório completo por período com drilldown.

**Params:**

| Campo | Obrig. | Tipo | Exemplo |
|---|---|---|---|
| `from` | sim | date | `from=2015-02-23` |
| `to` | sim | date | `to=2015-02-23` |
| `drilldown` | sim | list | `drilldown=exchange,os` |
| `kpis` | não | list | `kpis=impressions,clicks` |
| `format` | não | string | `excel` ou `csv` (padrão) |
| `rules` | não | list | `rules=countrycode=[ESP,FRA];os=[android]` |
| `raw` | não | boolean | `raw=true` |

**Variáveis de drilldown disponíveis:** mesmas do `/api/analytics/drilldown/:variable` (ver acima), com adição de `eventid` (Event ID / Advertiser ID).

**KPIs disponíveis (lista completa):**

| KPI | Descrição |
|---|---|
| `impressions` | Impressões |
| `clicks` | Cliques |
| `wonprice` | Media Cost (spend) |
| `client_cost` | Final Price (custo ao cliente) |
| `clientrevenue` | Event revenue |
| `cpm` | CPM |
| `cpc` | CPC |
| `cpa1..cpa5` | CPA por slot de conversão |
| `events1..events5` | Conversões 1-5 |
| `msevents1..msevents5` | MS Conversions 1-5 |
| `cr1..cr5` | CR 1-5 |
| `videostart` | Video start |
| `videofirstquartile` | Video 25% viewed |
| `videomidpoint` | Video 50% viewed |
| `videothirdquartile` | Video 75% viewed |
| `videocomplete` | Video complete |
| `views` | Video views |
| `vr_start..vr_complete` | Video view rates |
| `bids` | Bids |
| `offers` | Bid offers |
| `won` | Won |
| `bidpercent` | Bid % |
| `wonpercent` | Won % |
| `techfee` | Tech fee |
| `ecpm..ecpa5` | eCPM/eCPC/eCPA (inclui tech fee) |
| `margin` | Margin |
| `margin_percentage` | Margin % |
| `timeToConversion1..5` | Tempo até conversão (segundos) |
| `assistedConversions1..5` | Estimated Assisted Conversions |
| `assistedRate1..5` | Estimated Assisted Rate |
| `incremental_conversions_1..5` | Incremental Conversions |
| `uplift_1..5` | Uplift |
| `cpi1..cpi5` | CPI (Cost Per Incremental Conversion) |
| `estimated_visits` | Estimated visits |
| `attributed_visits` | Attributed visits |
| `aderror` | Ad Error |
| `adloaded` | Ad Loaded |
| `adviewed` | Ad Viewed |
| `skinstalls` | SKAdNetwork installs |
| `skevents` | SK post-install events |
| *(+ usdcost, convertedadsquarecost, convertedothercost, adsquarecost, auctioncharge, convertedpartnercost, cimpressions, dealcharge, impressionstotal, cpvcomplete, cpvstart, bidprice, othercost, partnercost, convertedclientrevenue, convertedclientrevenue, exposed_percent, uplift, organic_visits, incremental_visits, incremental_visit_percent, aderrorpercent, adloadedpercent, adviewedpercent)* | |

**Exemplo:**
```bash
curl 'https://api.mediasmart.io/api/analytics/custom-report?from=2015-10-13&to=2015-10-14&drilldown=day,exchange,os&kpis=impressions,clicks' -H 'Authorization: <token>'
```

---

### `GET /api/analytics/kpi/:kpi`
Evolução de um KPI na última semana. **Params opcionais:** `campaigns=a,b,c`

---

## Analytics > Campaign

### `GET /api/campaign/:id/analytics/summary`
Resumo simples de como uma campanha está performando hoje vs ontem.

### `GET /api/campaign/:id/analytics/overview`
Overview da campanha (retorna CSV).

### `GET /api/campaign/:id/analytics/kpi/:kpi`
Versão por campanha de `/api/analytics/kpi/:kpi`.

### `GET /api/campaign/:id/analytics/drilldown/:variable`
Versão por campanha de `/api/analytics/drilldown/:variable`.

### `GET /api/campaign/:id/analytics/report`
Versão por campanha de `/api/analytics/custom-report`.

---

## Analytics > Availability

### `GET /api/analytics/availability/drilldown/:variable`
Estimativa de bid offers disponíveis por variável.

**Vars disponíveis:** agegroup, auctiontype, audio, carrier, countrycode, day, dayoftheweek, devicetype, display, dmv, dnt, exchange, extendedconnectiontype, gender, geoAccuracy, hasidl, hasmaxawareness, hour, iabcategory, iabsubcategory, idfv, idtype, image, interstitial, isp, javascript, lastfix, locationtype, make, maxVast, maxduration, minVast, minduration, model, native, nativesize, omid, omidver, os, osversion, pricefloor, richmedia, simcountry, size, skcompatible, tagid, typeofconsent, userlanguage, video, videoposition, videorewarded, vpaidVer, zeotap

**Params:** `from` (obrig.), `to` (obrig.), `rules` (opcional)

### `GET /api/analytics/availability/summary`
Estimativa total de bid offers disponíveis + timeline.
**Params:** `from`, `to`, `rules`

---

## Analytics > Publishers

### `GET /api/analytics/publishers/drilldown/:variable`
Drilldown por variável de publishers.

**Vars disponíveis:** agegroup, auctiontype, audio, bundleid, carrier, connectiontype, consent, countrycode, day, dayoftheweek, devicetype, display, dmv, dnt, domain, exchange, extendedconnectiontype, gender, geoAccuracy, hasidl, hasmaxawareness, hour, iabcategory, iabsubcategory, idfv, idtype, image, interstitial, isp, javascript, lastfix, locationtype, make, maxVast, maxduration, minVast, minduration, model, native, nativesize, omid, omidver, os, osversion, pricefloor, publisher, publishercompany, publisherid, publisherkeyword, publishername, publisherurl, richmedia, simcountry, size, skcompatible, tagid, typeofconsent, userlanguage, video, videoposition, videorewarded, vpaidVer, zeotap

### `GET /api/analytics/publishers`
Lista de publishers disponíveis com filtros opcionais.
**Params:** `from`, `to`, `rules`, `limit`, `offset`

---

## Analytics > Real time (Daystats)

### `GET /api/analytics/daystats`
Drilldown quase em tempo real de todos os KPIs.

**Params:**

| Campo | Obrig. | Descrição |
|---|---|---|
| `drilldown` | sim | Variável para drilldown |
| `from` | não | Data inicial |
| `to` | não | Data final |
| `kpis` | não | KPIs a obter |
| `campaign` | não | Fixar uma campanha |
| `exchange` | não | Fixar um AdExchange |
| `keyword` | não | Fixar valor por prefixo |

**KPIs disponíveis:** adloaded, adviewed, aderror, admarkupsize, bidprice, clientrevenue, prebids, bids, bidpercent, won, wonpercent, bidcost, serverscost, datacost, bcpm, bcpc, bcpa..bcpa5, impressions, clicks, qclicks, gclicks, ctr, qctr, convs1..5, tconv1..5, videostart..videocomplete, views, vr_start..vr_complete, skinstall, skevent

**Vars de drilldown (amostra):** campaign, day, exchange, k:age, k:cat, k:gender, k:operator, k:os, p:ab (Strategy), p:areaid, p:browser, p:city, p:connectiontype, p:creativename, p:creativetype, p:deal, p:devicetype, p:eventid, p:exacthour, p:geo, p:hour, p:idtype, p:isp, p:language, p:make, p:model, p:native, p:os, p:placebo, p:pub, p:size, p:tag, p:type (App vs Web)

### `GET /api/analytics/daystats-report`
Versão CSV do daystats. Mesmos params do daystats.

---

## Advertiser Management

### `GET /api/advertisers`
Retorna todos os advertisers da organização.

**Objeto retornado:**
```json
{
  "event_id": "mediasmart-xxt70yvxx1qfgglzxduqx7idqeo571we",
  "domain": "test.com",
  "iab_category": "IAB8",
  "id": "xxt70yvxx1qfgglzxduqx7idqeo571we",
  "name": "Test advertiser",
  "sensitive_content": false
}
```

> **Nota:** `id` = sufixo após `mediasmart-` do `event_id`. Na nossa tabela `raw.mediasmart_advertisers`, o campo `event_id` tem o prefixo completo `mediasmart-...` (ou `newad_brazil-...` para nosso account).

### `POST /api/advertiser`
Cria novo advertiser.

| Campo | Obrig. | Tipo | Descrição |
|---|---|---|---|
| `name` | sim | string | Nome |
| `domain` | sim | string | Domínio do advertiser |
| `iab_category` | sim | string | Categoria IAB |
| `advertiser_domain` | sim | string | Domínio do advertiser |

> ⚠️ **Nota de truncamento:** A documentação foi cortada aqui (~50k chars). As seções seguintes podem estar incompletas: POST /api/advertiser (continua), Campaign Management (GET/POST/PATCH /api/campaigns, /api/campaign/:id), Strategy Management (se existir endpoint dedicado), Creative Management (/api/creatives), e outros endpoints de management.

---

## Notas de uso para nosso ETL

### Endpoint principal de analytics
```
GET /api/analytics/custom-report
  ?from=YYYY-MM-DD
  &to=YYYY-MM-DD
  &drilldown=day,eventid,controlid,strategyid,...
  &kpis=impressions,clicks,wonprice,client_cost,...
  &format=csv
  &raw=true
```

### Para identificar advertiser→campaign
O campo `eventid` está disponível como variável de drilldown em `/api/analytics/custom-report`.
**Não está disponível** no endpoint de listagem de campanhas (`/api/campaigns`).
O vínculo só existe nos relatórios de analytics.

### Estratégias (strategies)

**O que são:** Uma strategy É uma campanha filho. Internamente são objetos Campaign com `parent.id` preenchido.
Conforme documentação oficial (API_Doc_MediaSmart.md): *"A strategy is a campaign, but linked to another campaign that is considered as a parent."*

**Endpoints:**
- `GET /api/campaign/:id/strategies` — lista resumos das strategies de uma campanha pai (retorna `id`, `name`, `parent.id`, `color`)
- `GET /api/campaign/:strategy_id` — corpo completo da strategy (targeting, deals_and_pricing, schedule — herda do pai se não sobrescrito)
- `POST /api/campaign/:id/strategy` — cria strategy (campos: `name`, `state`, `cost_percentage`)

**O que temos no raw hoje:** `id`, `name`, `parent.id`, `parent.name`, `state` (da array `strategies[]` das campanhas pai)

**O que PODERÍAMOS buscar (não implementado):** Chamar `GET /api/campaign/:strategy_id` para cada strategy para obter targeting, `deals_and_pricing.cpm/cpc/cpa`, `schedule.max_daily_cost`. Dependeria de job adicional no ETL.

**Variáveis de drilldown disponíveis:** `strategyid`, `strategyname`, `abtag` (nome histórico da strategy)

### Criativo via analytics
Para obter delivery por criativo, usar `drilldown` com `creativeid` ou `creativetype` ou `size` no custom-report.
