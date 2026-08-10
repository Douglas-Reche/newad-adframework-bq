# RAW Layer Design — AdFramework

> **Manutenção:** Tier 1 (inventário de tabelas/schema — regenerar contra `INFORMATION_SCHEMA` quando desconfiar de desatualização) + Tier 2 (seção de racional/design — gatilho: nova tabela RAW ou decisão de captação que muda o design). Ver nota de manutenção do `gold_layer_design.md` para o mesmo princípio aplicado lá.

> Criado: 2026-06-18
> Status: ✅ ATUAL — T1–T7 fechados, validados em produção e jobs consolidados (2026-06-24).
> **Nota (2026-08-09):** produção tem 18 tabelas em `raw.*`, não 15 — as 3 tabelas extras
> (`mgid_stats_daily`, `mgid_stats_creative`, `ms_creative_daily`) têm schema confirmado ao
> vivo na seção "Schema real — 3 tabelas RAW novas" mais abaixo. Ainda sem STG/GOLD
> correspondente (gap de integração, não de documentação).
> Detalhes de implementação por plataforma (sketches históricos, superados por este doc): `_legacy/mediasmart_raw_sketch.md`, `_legacy/mgid_raw_sketch.md`, `_legacy/siprocal_raw_sketch.md`
> **Rebuild RAW encerrado em 2026-06-24** — `raw.*` tinha 15 tabelas (14 novas + `io_plan_drive_snapshot`) neste momento. 19 tabelas órfãs dropadas. Próxima camada: STG.
> **Auditoria de integridade + schema executada em 2026-06-24** — ver seção "Auditorias executadas" no final deste doc. Resultado: 14/14 tabelas íntegras (0 nulos em PK/FK, joins ≥99,3%) e 14/14 com schema real idêntico ao planejado (1 gap encontrado e corrigido em `ms_advertisers`).

---

## Princípios gerais

- **`client_id` na RAW = ID nativo da plataforma.** Mapeamento para `newad_client_id` acontece na gold via `core.platform_client_links`.
- **Tipos nativos.** RAW grava INT64, FLOAT64, DATE — sem `df.astype(str)` global.
- **Sanitização mínima na ingestão.** Só remove chars inválidos no BQ. Normalização semântica (snake_case, renomes) pertence à STG.
- **`campaign_name` normalizado na ingestão.** `raw_name.strip().upper()` antes de gravar — necessário para STG parsear `formato`.

---

## Mapa de Formatos (core.dict_format)

Tabela de lookup mantida no core. STG parseia `formato` do `campaign_name` → join com `core.dict_format` → traz `goal_type`. Extensível: novos formatos = nova linha.

**Confirmado pelo comercial em 2026-06-18:**

| Formato | Plataforma | Modelo (goal_type) |
|---|---|---|
| Display | MediaSmart | CPM |
| Vídeo | MediaSmart | CPM |
| Retargeting | MediaSmart | CPM |
| Native | MediaSmart / MGID | CPC |
| Push | MGID / Siprocal | CPC |
| App Install | *(futuro)* | CPI |
| Social | Meta / Google *(futuro)* | CPM |

**Padrão de nome de campanha:** `{CLIENTE}_{FORMATO}_{PAIS}_{PERIODO}` — ex: `CORA_NATIVE_BR_SET26`, `LUCKBET_PUSH_BR_OUT26`

---

## Tamanhos de imagem de criativo (internos — para dado analítico)

Confirmado pelo comercial em 2026-06-18. MS expõe largura e altura via API; MGID e Siprocal usam resolução padrão fixa:

| Plataforma | `width` | `height` | Fonte |
|---|---|---|---|
| MediaSmart | variável | variável | `GET /api/campaign/{id}/creatives` → campos nativos |
| MGID | 1280 | 720 | Fixo pelo comercial — API não expõe por criativo |
| Siprocal | 1280 | 720 | Fixo pelo comercial — sem catálogo de criativos |

**Decisão de implementação:** gravar `width` e `height` como colunas fixas na RAW para MGID e Siprocal (`1280` e `720` como INT64). STG pode derivar `size = width || 'x' || height`.

---

## Tratamento do campo `estrategia` no IO Plan

O campo `estrategia` nas planilhas de IO Plan contém o formato da campanha embutido (native, push, display, vídeo, etc.) junto com outras informações. **Esse campo precisará ser extraído em uma coluna separada** antes de ser usado na gold.

**Localização:** `raw.io_plan_drive_snapshot` → coluna `estrategia`
**Tratamento:** STG ou ingestão deve extrair `formato` do campo `estrategia` (regex ou lookup) e gravar em coluna separada `formato` antes do join com `core.dict_format`.

**Exemplo esperado:**
- `estrategia = "Native - Performance"` → `formato = "native"`
- `estrategia = "Push - Awareness"` → `formato = "push"`
- `estrategia = "Display CPM"` → `formato = "display"`

**Decisão pendente:** se o parse acontece na ingestão (mantém RAW fiel, STG recebe campo limpo) ou na STG (RAW é 100% fiel ao Drive, STG normaliza). Tendência: **na STG** — RAW deve ser fiel ao Drive.

---

## Hierarquia de entidades

```
client → campaign → creative → KPIs (delivery)
```

MS Strategy eliminada. O `formato` (native/video/push) vem do nome da campanha, não da strategy. Strategy = configuração operacional de bid/targeting — sem valor analítico autônomo.

---

## T1 — Clientes

**Grain:** 1 linha por cliente/advertiser
**Campos obrigatórios:** `client_id, client_name, category, platform`

| Plataforma | Tabela | `client_id` | Fonte |
|---|---|---|---|
| MediaSmart | `raw.ms_advertisers` | `event_id` | `GET /api/advertisers` — única chamada, full refresh |
| MGID | **eliminado — ver nota abaixo** | — | — |
| Siprocal | `raw.sp_clients` | `pi_externo` | Extraído do flat file Google Sheets |

### ⚠️ MGID: T1 `raw.mg_clients` eliminado — não existe fonte na API (confirmado empiricamente em 2026-06-18)

**Decisão revisada em 2026-06-18.** O design original (sessão de 18/06) assumia, só pela leitura da doc, que: (a) existiria uma lista de `client_ids` para iterar, um por advertiser; (b) o campo `advertiserName` (documentado como obrigatório na criação da campanha) também voltaria na leitura via `GET /v1/goodhits/clients/{id}/campaigns`. **Ambas as suposições foram testadas contra a API real e refutadas:**

- O `MgidConnector` (e a conta MGID da NewAd) usa um **único** `client_id` — a conta-agência, não uma lista de advertisers. Não existe endpoint de listagem de clientes na MGID.
- Busquei as 173 campanhas reais da conta (`GET /v1/goodhits/clients/{id}/campaigns`, sem filtro = "all properties" por padrão, segundo a doc) — `advertiserName` **não veio em nenhuma das 173**.
- Testei de novo pedindo explicitamente `fields=['id','name','advertiserName','category']` — a API aceitou o filtro (retornou `id`,`name`,`category` corretamente) mas **descartou `advertiserName` silenciosamente, sem erro**. Confirma que é uma limitação estrutural da API (campo write-only, não exposto em leitura), não um problema de configuração do job.
- `category` (campo que existe e volta corretamente) é a categoria temática da campanha (ex: "Home Improvement", "Casinos and Gambling") — **não é proxy confiável de cliente**: 132 de 173 campanhas (76%) retornaram `category = "Other services"`.

**Conclusão:** a MGID não modela "advertiser/cliente" como entidade própria na API. O único identificador de cliente confiável é o vínculo manual já mantido em `core.platform_client_links` (`campaignid → client_id NewAd`).

**Arquitetura resultante:** a dimensão "cliente" da MGID só existe a partir da **STG**, via join — não há tabela RAW de clientes para essa plataforma:

```
raw.mg_campaigns.id (campaign_id)
     → core.platform_client_links.link_value = campaign_id → .client_id
     → core.dim_client.client_id → .name, .sector
```

`core.dim_client` já tem os campos necessários (`client_id, name, sector` — confirmado no schema). Não é necessário criar nenhuma tabela intermediária.

**Gap operacional identificado:** das 173 campanhas ativas/recentes retornadas pela API em 18/06/2026, **47 (27%) ainda não têm vínculo em `core.platform_client_links`** — são campanhas de clientes já conhecidos (Cerpa, Pardini, Cassino Pix, Banco Cora, Amigo, Mastercard, Boa Vista) que faltou linkar. Isso é tarefa comercial/manual de preenchimento da tabela de vínculo, não um bloqueio técnico — mas até ser preenchido, essas 47 campanhas ficam "sem cliente" no join da STG.

### Siprocal — RAW literal, T1 resolvido na STG (decisão revisada em 2026-06-22)

**Mudança de princípio para Siprocal:** a RAW (`raw.sp_delivery`) passou a ser o **dump literal** da planilha Google Sheets — sem aliasing de header, sem renomeação semântica, sem cast de tipo. Motivo: o connector anterior aplicava aliasing já na ingestão (`pi_externo/pi → campaign_id`) e isso causava **perda silenciosa de dado** sempre que o header real não batia com o alias esperado — foi exatamente o que aconteceu (`campaign_id` veio vazio em 100% das linhas porque a coluna real da planilha se chama `"Coluna 1"`, não `pi_externo`).

**Header real confirmado:** `Coluna 1, Data, Campanha, Criativo, Impressions, Clicks, CTR`. `"Coluna 1"` **é** o `pi_externo` (confirmado pelo usuário) — só está com nome genérico na planilha. Todos os campos gravados como STRING (fidelidade à fonte); STG faz parse de data, cast numérico e parse de `%`.

**Filtro de sanidade (não é tratamento semântico):** linhas onde todas as colunas de dado exceto `ctr` estão vazias são descartadas na ingestão — a planilha tem uma fórmula de CTR arrastada ~4929 linhas além do dado real, gerando `#DIV/0!` sem mais nenhum valor.

**T1 Siprocal não terá tabela RAW própria** — mesma lógica do MGID: `client_name` é derivado na STG a partir do 2º segmento de `campanha` (ex: `NEWAD_BANCOCORA_BR_FEV26` → `BANCOCORA`). `pi_externo` (`coluna_1`) não é estável por cliente — muda por campanha/período — então não serve como chave de cliente, só de campanha/PI.

Detalhes completos da investigação em `CHANGELOG.md` (entrada 2026-06-22).

---

## T2 — Campanhas

**Grain:** 1 linha por campanha
**Campos obrigatórios:** `campaign_id, campaign_name, client_id (FK), start_date, end_date`

| Plataforma | Tabela | `campaign_id` | Fonte |
|---|---|---|---|
| MediaSmart | `raw.ms_campaigns` | `id` (nativo) | `GET /api/campaigns` (lista) → `GET /api/campaign/{id}` por ID com sleep 0.5s |
| MGID | `raw.mg_campaigns` | `id` (nativo) | `GET /v1/goodhits/clients/{id}/campaigns` por cliente |
| Siprocal | `raw.sp_campaigns` | Nome normalizado (`UPPER + espaços→_`) | Extraído do flat file Google Sheets |

**Regra de derivação no STG (não muda a RAW):**
- MS + MGID: STG parseia `formato` do `campaign_name` (ex: `CORA_NATIVE_SET26` → `formato = native`)
- Siprocal: `formato = push` fixo
- `goal_type` (CPM/CPC): STG consulta `core.dict_format` com `(formato, platform)`

**⚠️ Ao criar o job de T2:** mapear todos os `formato` possíveis contra nomes reais existentes. Registrar variações (ex: `RETARGET` vs `RETARGETING`). Nomes que não encaixarem → `formato = null` + log para revisão.

---

## T3 — Criativos ✅ VALIDADO EM PRODUÇÃO (2026-06-22)

**Resultado real:** `raw.ms_creatives` — 23 linhas; `raw.mg_teasers` — 167 linhas. Ambos confirmados contra API real, escopo magro mantido (sem stats/conversion/category — ver `CHANGELOG.md` entrada 2026-06-22 para a justificativa). `mediasmart_firstlevel_creatives` e `mgid_firstlevel_creatives` redirecionados para as novas tabelas.

**Grain:** 1 linha por criativo

| Campo | MS `ms_creatives` | MGID `mg_teasers` | Siprocal |
|---|---|---|---|
| `creative_id` | `id` (nativo) | `id` (nativo) | — |
| `creative_name` | `name` | `title` | label no delivery |
| `campaign_id` | `campaign_id` | `campaign_id` | — |
| `status` | `state` | `status` | — |
| `url` | `click_url` | `url` | — |
| `thumbnail_url` | `thumbnail_url` | `image_link` | — |
| `creative_type` | `type` (image/video/native/rich_media) | — | — |
| `size` | `width` + `height` (da API) | fixo pelo comercial | fixo pelo comercial |
| `advert_text` | **não existe na API** | `advert_text` | — |
| `call_to_action` | **não existe na API** | `call_to_action` | — |

**Fontes:**
- MS: `GET /api/campaign/{id}/creatives` por campanha
- MGID: `GET /v1/goodhits/clients/{clientId}/teasers` por cliente
- Siprocal: sem catálogo — `creative` é label de segmentação na delivery

---

## T4 — Delivery principal (fato base) ✅ VALIDADO EM PRODUÇÃO (2026-06-22)

**Resultado real:** `raw.ms_delivery` — 735 linhas (backfill 12-19/06); `raw.mg_delivery` — 133 linhas. Jobs novos (`mediasmart_daily:delivery_t4`, `mgid_daily:delivery_t4`) rodando em paralelo aos antigos — ainda não redirecionados, aguardando mais validação.

**✅ Gap de join MediaSmart RESOLVIDO (mesma sessão, 22/06):** `ms_delivery.creative_id` (`creativeid` da API, formato `cr-xxx`) não batia com a primeira versão de `ms_creatives` (que usava `/api/campaign/{id}/creatives`). Causa: a MediaSmart tem **dois conjuntos** de associação criativo↔campanha — um direto na campanha, outro dentro de cada `strategy` (`campaign.strategies[].creatives.campaign_creatives[]`). A entrega só referencia o segundo. T3 reconstruído para usar a fonte certa, com prefixo `cr-` adicionado ao `creative_id` gravado — join agora confirmado em 729/735 (99,2%). Detalhes completos em `CHANGELOG.md`. **MGID não teve esse problema** — `mg_delivery.creative_id` (`teaserId`) bate 100% com `mg_teasers.creative_id` desde o início.

**Grain:** `dia + client + campanha + creative`
**Nota:** este é o grain mais granular — by_campaign é redundante (GROUP BY resolve).

| Campo | MS `ms_delivery` | MGID `mg_delivery` | Siprocal `sp_delivery` |
|---|---|---|---|
| `date` | `day` | `day` | `date` |
| `client_id` | `event_id` | injetado na ingestão | `pi_externo` |
| `campaign_id` | `campaign_id` | `campaign_id` | nome normalizado |
| `creative_id` | `creative_id` | `teaser_id` | `creative` (label) |
| `impressions` | ✓ | ✓ | ✓ |
| `clicks` | ✓ | ✓ | ✓ |
| `ctr` | ✓ (derivado) | ✓ (derivado) | ✓ (derivado) |
| `conversions_1` | `conversions_1` | `conversions_interest` | — |
| `conversions_2` | `conversions_2` | `conversions_decision` | — |
| `conversions_3` | `conversions_3` | `conversions_buy` | — |
| `conversions_4` | `conversions_4` | — | — |
| `conversions_5` | `conversions_5` | — | — |
| `video_start` | ✓ | — | — |
| `video_25` | ✓ | — | — |
| `video_50` | ✓ | — | — |
| `video_75` | ✓ | — | — |
| `video_complete` | ✓ | — | — |

**CTR:** sempre recalcular no STG — `SAFE_DIVIDE(clicks, impressions)` — não confiar no valor da fonte.

---

## T5 — By Geo ✅ VALIDADO EM PRODUÇÃO (2026-06-22)

**Grain real (revisado após testes):** MS = T4 + country + city (sem region — não existe na API). MGID = day + creative + region (sem campaign_id — limite de 3 dimensões por chamada; sem country — region é texto livre, ver nota).

| Campo | MS | MGID | Siprocal |
|---|---|---|---|
| `country` | ✓ (código ISO3, ex: `BRA`) | ❌ não gravado | — |
| `region` | ❌ não existe na API (testado, rejeitado) | ✓ mas texto livre (`"São Paulo City"`, `"Texas State"` — mistura cidade/estado, não é só sigla) | — |
| `city` | ✓ (minúsculas) | — | — |
| `campaign_id` | ✓ | ❌ não gravado (resolvido via join `creative_id → mg_teasers → campaign_id` na STG) | — |

**MGID — limite de 3 dimensões por chamada (confirmado pela API):** `{"errors":{"dimensions":["This collection should contain 3 elements or less."]}}`. T4 já usa `day+campaignId+teaserId`; T5 precisa trocar `campaignId` por `region`, ficando `day+teaserId+region`. Decisão validada com o usuário: **não** criar duas tabelas separadas (by_country + by_region) — juntar elas na STG causaria fan-out (inflação de números), pois não compartilham uma chave de geografia comum.

**Resultado real:** `raw.ms_delivery_by_geo` — 32.447 linhas (confirma alta cardinalidade prevista). `raw.mg_delivery_by_geo` — 669 linhas, join 100% com `mg_teasers`.

**KPIs:** impressions, clicks, ctr (derivado), conversions_1..5 (MS) / conversions_interest/decision/buy (MGID).
**Atenção:** alta cardinalidade — MS requer timeout 60s.

---

## T6 — By Device + OS ✅ VALIDADO EM PRODUÇÃO (2026-06-24)

**Grain real (revisado após testes):** MS = T4 + device_type + operating_system (cabem juntos, sem limite de dimensões). MGID = day + creative + device_type apenas (**sem OS** — limite de 3 dimensões impede `day+entidade+device+os` juntos, independente de usar campaignId ou teaserId como entidade).

| Campo | MS | MGID | Siprocal |
|---|---|---|---|
| `device_type` | ✓ (`Desktop`, `Smartphone`, `Tablet`) | ✓ (`mobile`, `desktop`, `tablet`) | — |
| `operating_system` | ✓ (`linux`, `chrome os`, `macos`, `android`...) | ❌ não gravado (ver nota) | — |

**❌ Nota MGID revisada (a do design original estava errada):** "OS é dimensão separada — injetar junto com device" **não é possível**. Testado e confirmado: `day+teaserId+device+os` excede o limite de 3 dimensões por chamada, e não há combinação que caiba os 4. Decisão: ingerir só `device_type`; `operating_system` MGID fica fora até surgir necessidade real.

**Nomes de campo confirmados por teste (não assumir por analogia):** MGID usa `deviceType` (camelCase) — `device` (lowercase) é rejeitado. MS usa `os` (não `osfamily`).

**Resultado real:** `raw.ms_delivery_by_device` — 6.153 linhas. `raw.mg_delivery_by_device` — 251 linhas, join 100% com `mg_teasers`.

**KPIs:** impressions, clicks, ctr (derivado), conversions_1..5 (MS) / conversions_interest/decision/buy (MGID).

---

## T7 — By Hour ✅ VALIDADO EM PRODUÇÃO (2026-06-24)

**Grain:** T4 + hour (0–23 UTC). Único T que não bateu em nenhum limite novo — `day+teaserId+hour` cabe certinho nas 3 dimensões da MGID.

| Campo | MS | MGID | Siprocal |
|---|---|---|---|
| `hour` | ✓ (vem como string `"HH:00"`, parseado para INT64 na ingestão) | ✓ (já vem como inteiro nativo) | — |

**Resultado real:** `raw.ms_delivery_by_hour` — 18.660 linhas. `raw.mg_delivery_by_hour` — 1.346 linhas, join 100% com `mg_teasers`.

**KPIs:** impressions, clicks, ctr (derivado), conversions_1..5 (MS) / conversions_interest/decision/buy (MGID).
**⚠️ MS:** sem dados antes de 2026-05-28 — sem backfill possível para período anterior (não retestado nesta sessão).

---

## Breakdowns descartados

| Breakdown | Motivo |
|---|---|
| By Publisher / Widget | Campos muito diferentes entre MS e MGID, sem uso analítico definido. Jobs antigos (`mediasmart_delivery_by_publisher`, `mgid_stats_by_widget`) desabilitados e tabelas dropadas em 2026-06-24. |
| By Browser | Descartado. Job antigo (`mgid_stats_by_browser`) desabilitado e tabela dropada em 2026-06-24. |
| By Audience | MS exclusivo — DMP não utilizado atualmente |
| By Connection | MS exclusivo — descartado |
| Video Stats MGID | MGID exclusivo — baixa prioridade por agora |
| Quality by Source MGID | MGID exclusivo — baixa prioridade por agora |
| **Financeiro/Revenue (T8, novo)** | **Fora do escopo do projeto por agora (decisão de 2026-06-24).** Jobs antigos que capturavam isso (`mediasmart_revenue_daily` — `clientrevenue`; `mgid_stats_by_os` — `spent/revenue/profit/roas` + OS em nível de campanha; `mediasmart_creative_daily` — `source`/`convsource`, atribuição clique vs. impressão) foram desabilitados e as tabelas dropadas. Se o escopo financeiro voltar, T8 precisa ser desenhado do zero — T1-T7 nunca incluíram receita/custo. |

---

## Lista final de tabelas RAW

| T | MS | MGID | Siprocal |
|---|---|---|---|
| T1 | `raw.ms_advertisers` | **eliminado** — resolvido na STG via join (ver T1 acima) | **eliminado** — resolvido na STG a partir de `sp_delivery.campanha` |
| T2 | `raw.ms_campaigns` | `raw.mg_campaigns` ✅ validado 2026-06-22 | **eliminado** — `campanha` já é a chave em `sp_delivery` |
| T3 | `raw.ms_creatives` | `raw.mg_teasers` | — |
| T4 | `raw.ms_delivery` | `raw.mg_delivery` | `raw.sp_delivery` ✅ validado 2026-06-22 (RAW literal — ver nota Siprocal acima) |
| T5 | `raw.ms_delivery_by_geo` | `raw.mg_delivery_by_geo` | — |
| T6 | `raw.ms_delivery_by_device` | `raw.mg_delivery_by_device` | — |
| T7 | `raw.ms_delivery_by_hour` | `raw.mg_delivery_by_hour` | — |

**Nota Siprocal:** a planilha fonte (`raw_daily`) já é flat — um único `raw.sp_delivery` cobre o que seriam T1/T2/T4 em outras plataformas. Não há T2/T3 separados: `campanha` (literal) é tanto a chave de campanha quanto a fonte do nome do cliente, resolvida via parse na STG.

**Preservada do ciclo anterior:** `raw.io_plan_drive_snapshot` (dados de IO Plan do Google Drive — não vêm de API de plataforma).

---

## Estado do DROP

### 2026-06-18 — DROP inicial (reset completo pré-rebuild)

| Layer | Status |
|---|---|
| `raw.*` (exceto io_plan_drive_snapshot) | ✅ 30 tabelas dropadas |
| `stg.*` | ✅ 29 tabelas/views dropadas |
| `gold.*` | ✅ 8 tabelas/views dropadas |
| `core.*` | Intocado |

### 2026-06-24 — DROP final pós-rebuild (tabelas órfãs do schema antigo + fora de escopo)

19 tabelas dropadas: 12 substituídas pelas novas (T1-T7), 4 de breakdowns descartados (by_publisher/widget, by_browser), 3 fora de escopo (revenue/financeiro — ver seção "Breakdowns descartados" acima).

**Estado final de `raw.*`: 15 tabelas** — 14 novas (`ms_advertisers, ms_campaigns, ms_creatives, ms_delivery, ms_delivery_by_geo, ms_delivery_by_device, ms_delivery_by_hour, mg_campaigns, mg_teasers, mg_delivery, mg_delivery_by_geo, mg_delivery_by_device, mg_delivery_by_hour, sp_delivery`) + `io_plan_drive_snapshot` (preservada, sistema diferente). Detalhes completos em `CHANGELOG.md` (entrada 2026-06-24).

---

## Schema real — 3 tabelas RAW novas (confirmado ao vivo, 2026-08-09)

Produção tem **18 tabelas** em `raw.*`, não as 15 listadas na seção "Lista final de tabelas
RAW" acima. Achado de auditoria anterior apontava 3 tabelas fora deste doc — schema
confirmado ao vivo em 2026-08-09 via `INFORMATION_SCHEMA.COLUMNS`.

### `raw.mgid_stats_daily`
1.673 linhas, `MIN(day)=2025-10-01`, `MAX(day)=2026-02-20` (2026-08-09). Grain: `day +
campaignid`. **Todas as colunas são STRING** (inclusive `day`, `impressions`, `clicks`,
`spent`) — dump literal da API, sem type-casting na ingestão, mesmo padrão de `raw.sp_delivery`.

| Campo | Tipo |
|---|---|
| day, campaignid, adrequests, impressions, clicks, spent, cpc, ctr, conversionsbuy, conversionsinterest, conversionsdecision, revenue, profit, roas, platform, report_name, raw_ingested_at | STRING (todas) |

Status: 🟡 sem STG/GOLD correspondente — ver `docs/known_issues.md` para o gap de
integração (dado financeiro/stats de campanha MGID, escopo T8 nunca formalizado, ver seção
"Breakdowns descartados" acima).

### `raw.mgid_stats_creative`
4.183 linhas, `MIN(day)=2025-10-01`, `MAX(day)=2026-06-26` (2026-08-09). Grain: `day +
campaignid + teaserid`. Mesmo padrão all-STRING de `mgid_stats_daily`, mais a coluna `teaserid`.

| Campo | Tipo |
|---|---|
| day, campaignid, teaserid, adrequests, impressions, clicks, spent, cpc, ctr, conversionsbuy, conversionsinterest, conversionsdecision, revenue, profit, roas, platform, report_name, raw_ingested_at | STRING (todas) |

Status: 🟡 sem STG/GOLD correspondente — mesma observação de `mgid_stats_daily`.

### `raw.ms_creative_daily`
375 linhas, `MIN(day)=2026-07-08`, `MAX(day)=2026-08-08` (2026-08-09) — jamais tem cobertura
retroativa até 2025 como as outras, é ingestão recente. Grain: `day + event_id + creative_id`.
Diferente das 2 tabelas MGID acima, **já vem tipada** (`day` DATE, `impressions`/`clicks`/
`conversions_1..5` INT64) — schema nativo da API MediaSmart, sem passar por
`normalize_data()`/dump genérico.

| Campo | Tipo |
|---|---|
| day | DATE |
| event_id, creative_id, creative_type, controlid, strategyid, size, source, convsource, platform, raw_ingested_at | STRING |
| impressions, clicks, conversions_1, conversions_2, conversions_3, conversions_4, conversions_5 | INT64 |

Status: 🟡 sem STG/GOLD correspondente. Corresponde ao job de captura por criativo já visto
no `CHANGELOG.md` (`backfill_ms_creative_size.py`, working tree no momento desta consulta)
— dado existe, integração STG ainda não desenhada.

**Não usar os DDLs legados (`raw/ddl/mgid_stats_daily.sql`, `raw/ddl/mgid_stats_creative.sql`)
como referência de schema** — são da era pré-rebuild (anteriores ao DROP de 2026-06-18/24) e
não batem necessariamente com o schema real confirmado acima. `ms_creative_daily` segue sem
DDL commitado no repo (nem legado) — schema documentado aqui pela primeira vez, direto do
`INFORMATION_SCHEMA` ao vivo.

## `raw.mg_teasers` — queda de linhas (167→153), investigado mas não totalmente explicado

Confirmado ao vivo em 2026-08-09: `raw.mg_teasers` tem **153 linhas hoje**, todas com o
mesmo `raw_ingested_at = 2026-08-04` — a tabela é **WRITE_TRUNCATE** (snapshot completo a
cada ingestão, sem histórico acumulado), então não há como consultar o estado anterior
diretamente na própria tabela.

**Distribuição de `status` das 153 linhas atuais:**

| status | linhas |
|---|---|
| campaignBlocked | 107 |
| blocked | 40 |
| active | 5 |
| rejected | 1 |

52 `campaign_id` distintos entre as 153 linhas (`raw.mg_campaigns` tem 176 campanhas
cadastradas hoje). Só **5 de 153 teasers estão `active`** — a esmagadora maioria já está
bloqueada por algum motivo (`campaignBlocked`/`blocked`).

**Conclusão honesta — causa exata não confirmável:** como a tabela não retém histórico
(`WRITE_TRUNCATE` diário), não há como comparar teaser-a-teaser quais dos 167 originais
saíram da resposta da API entre 2026-06-22 e 2026-08-04. A distribuição de status observada
hoje (maioria bloqueada) é **consistente** com a hipótese de que a MGID deixa de retornar
teasers vinculados a campanhas que saem de circulação/são bloqueadas — mas isso é inferência
a partir do estado atual, não uma confirmação direta de que os ~14 teasers que sumiram eram
especificamente os que ficaram bloqueados. Não investigado mais a fundo por não haver dado
histórico para comparar. Se a diferença exata importar no futuro, só um novo bug-report à
MGID (ou logs de ingestão anteriores a 2026-08-04, se existirem fora do BigQuery) poderia
confirmar com certeza.

---

## Auditorias executadas (2026-06-24)

Antes de iniciar a STG, duas auditorias completas nas 14 tabelas novas — nenhuma assumida, tudo testado contra o BigQuery real.

### Auditoria 1 — Integridade de dado

| Verificação | Resultado |
|---|---|
| Contagem e atualização (`min_date`/`max_date`) | Todas as tabelas de entrega cobrindo `2026-06-12` a `2026-06-23` — cron diário confirmado rodando sozinho, sem intervenção manual |
| Nulos em campos-chave (PK/FK) | **0 nulos** em qualquer PK/FK, nas 14 tabelas |
| Integridade de join (FK → catálogo) | MGID: **100%** em todas as 4 tabelas de entrega → `mg_teasers`. MS: 99,3–100% (residual conhecido: campanhas/criativos históricos fora do catálogo ativo) |
| Duplicatas de PK | **0 duplicatas** nos 5 catálogos (`ms_advertisers`, `ms_campaigns`, `ms_creatives`, `mg_campaigns`, `mg_teasers`) |

### Auditoria 2 — Schema real vs. DDL documentada

Comparação campo a campo e tipo a tipo entre `raw/ddl/*.sql` e `bq.get_table().schema` real, nas 14 tabelas. Metodologia: extrair `(nome, tipo)` esperado de cada DDL, comparar contra o schema real, normalizando aliases de tipo do BigQuery (`FLOAT64`≡`FLOAT`, `INT64`≡`INTEGER`, `BOOL`≡`BOOLEAN` — mesmos tipos, nomenclatura SQL padrão vs. API legada).

**Resultado: 14/14 tabelas com schema real idêntico ao planejado**, após corrigir 1 gap encontrado:

- **`raw.ms_advertisers`** — faltavam `platform` e `raw_ingested_at` (existiam na DDL, não no BigQuery). Causa: primeira tabela criada na sessão (18/06), antes da disciplina de criação via DDL completa. `BigQueryService.load_data()` descarta colunas desconhecidas silenciosamente — por isso o gap nunca gerou erro. **Corrigido:** `ALTER TABLE ADD COLUMN IF NOT EXISTS` (preserva as 21 linhas) + reprocessamento. Validado: 21/21 com as duas colunas populadas, 0 nulos.
- 2 comentários de DDL desatualizados corrigidos (`ms_creatives.sql`, `ms_delivery.sql`) — descreviam fontes/gaps já resolvidos em sessões anteriores, sem afetar schema ou dado real.

Detalhes completos da investigação em `CHANGELOG.md` (entrada 2026-06-24, "Auditoria de schema RAW").
