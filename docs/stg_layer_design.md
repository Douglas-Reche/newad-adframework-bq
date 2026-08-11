# STG Layer Design — AdFramework

> **Manutenção:** Tier 1 (inventário de tabelas/schema — regenerar contra `INFORMATION_SCHEMA` quando desconfiar de desatualização) + Tier 2 (seção de racional/design — gatilho: nova tabela STG ou mudança de regra de resolução).

> Criado: 2026-06-24 · Banner de status corrigido 2026-08-10 (doc tocado por outro motivo — nova seção `fact_pacing_base` — e o banner "🟡 PLANO" divergia do corpo há muito tempo)
> Status: ✅ VALIDADO — T1-T7 MS+MGID e T1-T4 Siprocal criados e testados contra dado real em produção (2026-06-24); seção "Cross-plataforma" (`fact_pacing_base`) adicionada 2026-08-10, staging only
> Pré-requisito: `raw_layer_design.md` (RAW layer 100% validada em produção)

---

## Princípios gerais

- **STG = views sobre a RAW**, não tabelas materializadas. RAW já é o fato persistido; STG só normaliza/junta — recalcular é mais barato que duplicar storage e mais simples de manter (sem job de ingestão próprio).
- **Nomenclatura igual à RAW**, dataset diferente: `stg.ms_campaigns` espelha `raw.ms_campaigns`, mesma tabela conceitual, mesmo grain — só com os campos resolvidos/normalizados.
- **`ctr` sempre derivado aqui** (`SAFE_DIVIDE(clicks, impressions)`), nunca confiar no valor da fonte — decisão já registrada no `raw_layer_design.md`.
- **Toda resolução de FK que não veio na RAW acontece aqui** — é o motivo de existir a STG nesse design. Cada gap já documentado na RAW tem sua resolução abaixo.
- **`formato`/`goal_type` resolvidos aqui** via `core.dict_format` — nunca hardcoded em código.

---

## Investigação: por que a taxa de vínculo `platform_client_links` varia tanto por plataforma (2026-06-24)

Auditoria com dado real mostrou taxas de resolução muito diferentes:

| Plataforma | Resolução real | `link_type` usado |
|---|---|---|
| Siprocal | **11/11 = 100%** | `advertiser` (client_name parseado do nome da campanha) |
| MediaSmart | 13/21 = 62% | `eventid` (advertiser nativo) |
| MGID | 126/173 = 73% | `campaignid` (campanha individual) |

**Causa raiz identificada — não é falha de design, é diferença estrutural entre as fontes:**

- **MediaSmart e Siprocal já vinculam no nível certo (advertiser/cliente).** `ms_advertisers.event_id` é uma entidade estável — toda campanha (`ms_campaigns.client_id`) é FK nativa pra ela. Vincular **uma vez por advertiser** resolve automaticamente todas as campanhas passadas e futuras daquele advertiser. Mesma lógica pra Siprocal (`client_name` parseado do nome da campanha — cobre todas as campanhas que compartilham o mesmo segmento). Os gaps de 38%/0% nessas duas são **atraso operacional pontual** (advertiser/cliente novo, ainda não vinculado) — não um problema estrutural recorrente.

- **MGID é forçada a vincular por campanha individual porque não existe entidade "advertiser" exposta na API.** Já investigado exaustivamente no T1 MGID (`raw_layer_design.md`): `GET /v1/clients/{id}` só retorna financeiro; `advertiserName` é campo write-only (nunca retorna em nenhuma leitura, mesmo pedido explicitamente). Sem uma chave de advertiser nativa, cada campanha nova **precisa** de uma linha nova em `platform_client_links` — não tem como "herdar" de um vínculo de nível superior que não existe. É por isso que a MGID tem o maior volume de gaps (47 campanhas) e vai continuar acumulando atraso estruturalmente, não por falta de manutenção.

**Investigação adicional (mesma sessão):** testado o endpoint de campanha **individual** (`GET /campaigns/{id}`, diferente do endpoint de lista), inclusive pedindo `advertiserName` explicitamente via `fields=[]` — mesmo resultado: API aceita o parâmetro e descarta o campo silenciosamente. **Confirmado de forma exaustiva: não existe nenhuma forma de obter um ID de advertiser nativo da MGID.** Essa limitação é estrutural da API, não vai mudar com mais investigação.

### `stg.unresolved_client_links` — view de monitoramento ✅ criada e validada

Como não há automação possível pra MGID, a solução adotada é uma **view de monitoramento** (`stg/ddl/unresolved_client_links.sql`) que lista, pra cada plataforma, toda entidade nativa sem vínculo em `platform_client_links` — funciona como checklist contínuo pra quem mantém os vínculos.

**Coluna extra `suggested_client_id`:** fuzzy-match de texto entre o nome nativo (ou, no caso da MGID, o 1º segmento do `campaign_name` antes de `|`/`-`) e `core.dim_client.name`. **Não é vínculo automático** — só acelera a revisão manual. Guarda de tamanho mínimo (`LENGTH >= 4` + não-numérico) adicionada após detectar falso-positivo: campanhas com prefixo numérico de sequência (`"1 - PARDINI..."`, `"2 - PARDINI..."`) extraiam só o número como segmento, que coincidia por acaso com nomes de cliente contendo aquele dígito (ex: "2" bateu com "Lab**2**Lab").

**Resultado real (2026-06-24):** 55 linhas sem vínculo (8 MediaSmart + 47 MGID + 0 Siprocal). Sugestões corretas geradas para `Pardini`, `Banco Cora`, `Aperam`, `Senar`, `Pardini Telemedicina` (mesmo cliente do grupo Pardini, a confirmar). Os demais (`Cerpa`, `Mastercard`, `Cassino|7K`, `Chammas`, `Infinity Bet`, `Rino Imóveis`, `Boa Vista`, `Tralala`, `Parque das Camélias`, `Newad`) corretamente sem sugestão — são os 9 clientes confirmados como nunca cadastrados em `core.dim_client` (mais a conta interna `Newad`, que não é cliente real).

---

## Gaps herdados da RAW — resolução nesta camada

| Gap (documentado na RAW) | Resolução na STG |
|---|---|
| MGID não tem `client_id` em nenhuma tabela | `campaign_name → extração de advertiser_name → stg.mg_advertisers → core.platform_client_links → client_id` (ver seção MGID abaixo — resolvido em 1 ponto só, não repetido por T) |
| MGID não tem `campaign_id` em `mg_delivery*` (T5/T6/T7) | `creative_id → raw.mg_teasers.creative_id → .campaign_id` (join intermediário) — `client_id` NÃO resolvido aqui, só em `stg.mg_campaigns`/`stg.mg_advertisers` |
| Siprocal: tudo literal (`coluna_1`, `data` STRING, `campanha` bruto) | Parse completo nesta camada — ver seção Siprocal |
| MS: `ms_delivery*.creative_id` não bate 100% com `ms_creatives.creative_id` | Join `LEFT JOIN` mesmo assim — aceitar ~0,1-0,7% sem match (campanhas/criativos históricos fora do catálogo ativo, já mapeado) |
| MGID: sem `operating_system` em `mg_delivery_by_device` | Não resolvido — dado não existe nesse grain (ver `mgid_stats_by_os`, desativado, fora de escopo) |
| MGID: `mg_delivery_by_geo.region` é texto livre (cidade/estado misturado) | Mantido como texto — não fazer parse de país por agora (baixo volume de tráfego não-Brasil) |
| IO Plan: campo `estrategia` tem formato embutido | Parse via regex/lookup — ver seção IO Plan (pendência separada, fora do fluxo de delivery) |

---

## MediaSmart

### `stg.ms_advertisers` ✅ CRIADO E VALIDADO (2026-06-24)

Resultado real: 21 linhas, **13/21 (62%) com `client_id` resolvido** — bate exatamente com a auditoria. Campos `id` (sufixo curto, sem uso) e `sensitive_content` (100% vazio, sem valor de negócio) descartados por decisão explícita. DDL: `stg/ddl/ms_advertisers.sql`.

**Schema final** (resolve `client_id` de negócio aqui, mesmo princípio de `mg_advertisers`/`sp_clients` — ver diagrama da seção MGID):

| Campo STG | Fonte / Lógica |
|---|---|
| `event_id` | `event_id` (ID nativo MediaSmart, mantido — não é o `client_id` de negócio) |
| `client_name_native` | `name` |
| `category` | `iab_category` |
| `domain` | `domain` |
| `client_id` | join `core.platform_client_links` (`platform='mediasmart'`, `link_type='eventid'`) |
| `platform`, `raw_ingested_at` | passthrough |

### `stg.ms_campaigns` ← `raw.ms_campaigns`

**Parse de `formato`** do `campaign_name` (padrão `{CLIENTE}_{FORMATO}_{PAIS}_{PERIODO}`, 2º segmento) → join `core.dict_format(formato, platform='mediasmart')` → `goal_type`.

| Campo STG | Fonte / Lógica |
|---|---|
| `campaign_id` | `campaign_id` |
| `event_id` | `client_id` da RAW (na verdade é `event_id`, nativo — nome confuso na RAW, não renomear lá pra não quebrar o já validado) |
| `client_id` | **herdado** via join com `stg.ms_advertisers.event_id` (não resolvido de novo aqui — mesmo princípio "resolve uma vez só" do MGID) |
| `campaign_name` | `campaign_name` |
| `formato` | `SPLIT(campaign_name, '_')[1]` (com tratamento de variações: `RETARGET`/`RETARGETING`, etc. — mapear conforme aparecer) |
| `goal_type` | join `core.dict_format` |
| `start_date`/`end_date` | `started_at`/`finished_at` |
| `status` | `state` |

✅ **VALIDADO (2026-06-24):** posição fixa (2º segmento) só resolvia 11/14 — `CORA_CONTADIGITAL_RETARGETING_JUNHO26` tem segmento extra de "linha de produto" entre cliente e formato. Fix: busca em **qualquer** segmento + normalização de acento (`TRANSLATE`). Resultado: **14/14 campanhas, 12/14 com formato/goal_type** (2 esperados sem: `LUCKBET_APOSTADORES_MAIO` sem indicação no nome, `Teste-Newad` conta interna). `core.dict_format` criada nesta sessão (não existia — só uma tabela diferente, `core.campaign_format_map`, piloto manual incompleto e não relacionado). DDL: `stg/ddl/ms_campaigns.sql`.

### `stg.ms_creatives` ← `raw.ms_creatives` ✅ CRIADO E VALIDADO (2026-06-24)

Passthrough + `size` derivado. Sem `client_id` (princípio "resolve uma vez só").

| Campo STG | Fonte / Lógica |
|---|---|
| `creative_id, campaign_id, creative_name, status, url, thumbnail_url, creative_type, width, height` | passthrough |
| `size` | `CONCAT(CAST(width AS STRING), 'x', CAST(height AS STRING))` — testado: BQ já produz formato limpo sem `.0` |

**Resultado real: 201/201.** Criativos `native` (5) têm `width`/`height`=0 (sem dimensão fixa, esperado). DDL: `stg/ddl/ms_creatives.sql`.

### `stg.ms_delivery` ← `raw.ms_delivery` ✅ CRIADO E VALIDADO (2026-06-24)

Join com `ms_campaigns` (`client_id`/formato/goal_type). `ctr` derivado.

**Achado:** `raw.ms_delivery.client_id` é nome ambíguo — na verdade é o Event ID da MS (documentado no DDL original), não o `client_id` resolvido. Renomeado para `event_id` na STG.

| Campo STG | Fonte / Lógica |
|---|---|
| `date, campaign_id, creative_id` | passthrough |
| `event_id` | renomeado de `client_id` (raw) |
| `client_id, formato, goal_type` | via join `ms_campaigns` — denormalizado a pedido do usuário (não reabre a resolução, só `LEFT JOIN` de conveniência) |
| `impressions, clicks, conversions_1..5, video_*` | passthrough |
| `ctr` | `SAFE_DIVIDE(clicks, impressions)` |

**Resultado real:** 938/938. 937/938 com `client_id`/`formato` (1 campanha = `Teste-Newad`, conta interna sem vínculo). 932/938 com `ctr` (6 com `impressions=0`). 6/938 `creative_id` não batem com `stg.ms_creatives` (criativo removido do catálogo atual da API, entrega histórica ainda referencia — gap aceitável). DDL: `stg/ddl/ms_delivery.sql`.

### `stg.ms_delivery_by_geo` / `stg.ms_delivery_by_device` / `stg.ms_delivery_by_hour` ✅ CRIADOS E VALIDADOS (2026-06-24)

Mesma lógica de `stg.ms_delivery`, com a dimensão extra (`country+city` / `device_type+operating_system` / `hour`) passthrough. `raw.ms_delivery_by_*` já tem `campaign_id`/`event_id` nativos (sem join extra). **Resultado: 41.817/41.818, 6.152/6.153, 18.659/18.660 com `client_id`** (gap = `Teste-Newad`, conta interna).

---

## MGID

### Princípio de arquitetura — resolução de `client_id` em UM ponto só (star-schema)

`client_id` é resolvido **uma única vez**, na dimensão (`stg.mg_advertisers`), não repetido em cada T de delivery. Os fatos (`stg.mg_delivery*`) carregam só `campaign_id`/`creative_id` nativos — quem precisar de `client_id` junta com `stg.mg_campaigns`. Evita duplicar a mesma lógica de join em 4 lugares (T4-T7) e centraliza qualquer ajuste futuro de vínculo num só ponto.

```
stg.mg_advertisers   (NOVO — resolve client_id AQUI)
       ↑ join (advertiser_name extraído)
stg.mg_campaigns     (herda client_id, não resolve de novo)
       ↑ join (campaign_id nativo)
stg.mg_teasers       (passthrough)
       ↑ join (creative_id nativo)
stg.mg_delivery / by_geo / by_device / by_hour
       (só campaign_id/creative_id nativos — sem join com platform_client_links)
```

### `stg.mg_advertisers` ← `raw.mg_campaigns` ✅ CRIADO E VALIDADO (2026-06-24) — grain: 1 linha por advertiser extraído, deduplicado

**Resultado real (após 2 rodadas de correção e 5 clientes novos cadastrados):** 38/39 grupos (97,4%), **169/173 campanhas (97,7%)** em nível de campanha. Estratégia: herda `client_id` de **qualquer** campanha do grupo já vinculada (`MAX(client_id)` agrupado por `advertiser_name`) — zero conflitos encontrados. **Bug corrigido:** prefixo numérico (`"1 - PARDINI..."`, `"2 - PARDINI..."`) formava grupos falsos `"1"`/`"2"` — adicionado `REGEXP_CONTAINS(..., r'^[0-9]+$')` à mesma exceção do `Brand`/`New Ad`/`Push`. **Único grupo pendente:** `CassinoPix` (4 campanhas) — aguardando confirmação comercial se é o mesmo "Cassino 7K" (MS) ou cliente diferente. DDL: `stg/ddl/mg_advertisers.sql`.

**Por que existe:** a MGID não tem entidade "advertiser" na API (confirmado exaustivamente — `advertiserName` é write-only, nunca retorna em nenhuma leitura, testado em endpoint de lista e individual). O vínculo de cliente (`core.platform_client_links`) hoje é forçado a nível de **campanha individual** (`link_type='campaignid'`, 130 linhas) — taxa de resolução real 73% (126/173), e cada campanha nova exige uma linha de vínculo nova, sem poder herdar de nada.

**Mudança de estratégia:** extrair o nome do advertiser do `campaign_name` (texto livre, mas com padrão reconhecível na maioria dos casos) e vincular por esse **texto extraído e deduplicado** em vez de por `campaign_id`. Resultado testado contra as 173 campanhas reais: **40 valores distintos** (vs. 173 campanhas) — toda campanha nova de um advertiser já conhecido passa a resolver automaticamente, sem precisar de vínculo manual novo.

**Lógica de extração (testada e refinada contra dado real):**
1. Tentar 1º segmento de `campaign_name`, separando por `|` ou `-`
2. **Exceção:** se o 1º segmento for um prefixo genérico (`Brand`, `New Ad`/`NewAd`, `Push`) — usar o **2º segmento** em vez do 1º
3. Sem essa exceção, `"Brand | Amigo | Push | ..."` extraía `"Brand"` (53 campanhas erradas, 31% do total) em vez de `"Amigo"` (correto, 41 campanhas) — bug encontrado e corrigido durante o teste

**Variações que ainda exigem decisão comercial** (mesmo texto extraído, grafias diferentes — não resolvido automaticamente, fica para quem revisar o vínculo):

| Variações encontradas | Decisão pendente |
|---|---|
| `Laboratorio Pardini`, `Pardini Anatomia`, `PARDINI TELEMEDICINA`, `Pardini`, `Pardini Podcast` | Mesmo client_id (Grupo Pardini) ou sub-contas/linhas de serviço separadas? |
| `Dr Consulta` vs `Dr Consulta RJ` | Mesmo cliente ou unidade regional separada? |
| `APERAM` (caixa alta) vs `Aperam` | Mesma — só variação de capitalização, normalizar via `LOWER()` no join |

| Campo STG | Fonte / Lógica |
|---|---|
| `advertiser_name` | extraído de `campaign_name` (lógica acima) |
| `campaign_count` | `COUNT(*)` — visibilidade de volume por advertiser extraído |
| `first_campaign_id` | rastreabilidade — qual campanha originou esse advertiser |
| `client_id` | join `core.platform_client_links` (**novo** `link_type`, ex: `advertiser_name` — adicionado sem remover as 130 linhas `campaignid` existentes, tabela já é extensível por design) |

### `stg.mg_campaigns` ← `raw.mg_campaigns` + `stg.mg_advertisers` ✅ CRIADO E VALIDADO (2026-06-24)

**Formato derivado de `campaign_type`** (não do nome — `campaign_name` da MGID não tem padrão):

| `campaign_type` (raw) | `formato` (stg) |
|---|---|
| `push` | `Push` |
| `product` / `content` | `Native` |
| `rich_media` | `Native` (confirmado pelo usuário — variação de criativo, mesmo modelo CPC) |
| `search_feed` | `NULL` — baixo volume, avaliar quando aparecer |

| Campo STG | Fonte / Lógica |
|---|---|
| `campaign_id` | `campaign_id` |
| `advertiser_name` | extraído de `campaign_name` (mesma lógica de `stg.mg_advertisers`) |
| `client_id` | herdado via join com `stg.mg_advertisers` (não resolvido de novo aqui) |
| `campaign_name` | `campaign_name` |
| `formato` | derivado de `campaign_type` (tabela acima) |
| `goal_type` | join `core.dict_format` (`platform='mgid'`) |

**Resultado real:** 173/173 campanhas, **169/173 (97,7%) com client_id** (só `CassinoPix` pendente), **173/173 (100%) com formato/goal_type** após incluir `rich_media` no mapeamento (achado durante o teste — 13 campanhas ficaram sem formato na 1ª versão). DDL: `stg/ddl/mg_campaigns.sql`.

⚠️ **Gap operacional remanescente:** mesmo com a extração, advertisers nunca cadastrados em `core.dim_client` continuam com `client_id = NULL` até o comercial cadastrar/confirmar (`CassinoPix`). A mudança de estratégia resolve o problema de **escala** (campanha por campanha), não o de **cadastro ausente**.

### `stg.mg_teasers` ← `raw.mg_teasers` ✅ CRIADO E VALIDADO (2026-06-24)

Passthrough (`creative_id, campaign_id, creative_name, status, url, thumbnail_url, advert_text, call_to_action, width, height`). `size` = `'1280x720'` fixo (já vem fixo na RAW). **Resultado real: 167/167.** DDL: `stg/ddl/mg_teasers.sql`.

### `stg.mg_delivery` ← `raw.mg_delivery` + `mg_campaigns` ✅ CRIADO E VALIDADO (2026-06-24)

**Correção em relação ao design original:** `raw.mg_delivery` (T4) **já tem `campaign_id` nativo** — o join com `mg_teasers` para resolver `campaign_id` só é necessário no T5-T7 (onde o raw só tem `creative_id`), não aqui.

| Campo STG | Fonte / Lógica |
|---|---|
| `date, campaign_id, creative_id` | passthrough |
| `client_id, formato, goal_type` | via join `mg_campaigns` — denormalizado a pedido do usuário (não reabre a resolução) |
| `impressions, clicks, conversions_interest/decision/buy` | passthrough |
| `ctr` | `SAFE_DIVIDE(clicks, impressions)` |

**Resultado real:** 157/157, 100% com `client_id`/`formato`. 146/157 com `ctr` (11 com `impressions=0`). DDL: `stg/ddl/mg_delivery.sql`.

### `stg.mg_delivery_by_geo` / `stg.mg_delivery_by_device` / `stg.mg_delivery_by_hour` ✅ CRIADOS E VALIDADOS (2026-06-24)

`raw.mg_delivery_by_*` **só tem `creative_id`** (sem `campaign_id` nativo, diferente do T4) — precisa do join em cadeia via `mg_teasers` (`creative_id → campaign_id`) + `mg_campaigns` (`client_id`/formato/goal_type). Dimensão extra (`region` / `device_type` / `hour`) passthrough. **Sem `operating_system`** (não existe nesse grain). **Resultado: 800/800, 251/251, 1346/1346 — 100% nos três.**

---

## Siprocal

`client_id` resolvido em `stg.sp_clients`, denormalizado em `stg.sp_campaigns`/`stg.sp_delivery` via join (a pedido do usuário, 2026-06-24 — ver T4).

```
stg.sp_clients     (resolve client_id AQUI)
       ↑ join (client_name extraído)
stg.sp_campaigns / stg.sp_delivery   (herdam client_id via join)
```

Sem T5-T7 — a fonte (Google Sheets) não tem granularidade de geo/device/hora.

### `stg.sp_clients` ← `raw.sp_delivery` (NOVO — grain: 1 linha por client_name extraído, deduplicado)

**Já 100% resolvido** (`platform_client_links` para Siprocal: `link_type='advertiser'`, 11/11 — confirmado em produção, sem gap operacional, ver `project_platform_client_links_gaps.md`). Mais simples que `mg_advertisers`: sem ambiguidade de prefixo genérico, sem variação de grafia encontrada até agora.

| Campo STG | Fonte / Lógica |
|---|---|
| `client_name` | `SPLIT(campanha, '_')[OFFSET(1)]` (ex: `NEWAD_BANCOCORA_BR_FEV26` → `BANCOCORA`) |
| `campaign_count` | `COUNT(*)` por `client_name` — visibilidade de volume |
| `client_id` | join `core.platform_client_links` (`platform='siprocal'`, `link_type='advertiser'`) |

### `stg.sp_campaigns` ← `raw.sp_delivery` + `stg.sp_clients` ✅ CRIADO E VALIDADO (2026-06-24)

| Campo STG | Fonte / Lógica |
|---|---|
| `campaign_id` | `campanha` (já é a chave) |
| `client_name` | `SPLIT(campanha, '_')[OFFSET(1)]` |
| `client_id` | herdado via join com `stg.sp_clients` |
| `formato` | `'Push'` fixo |
| `goal_type` | join `core.dict_format` (`platform='siprocal'`) — sempre `CPC` |

**Resultado real: 37/37 campanhas, 100% com `client_id` e `goal_type`.** DDL: `stg/ddl/sp_campaigns.sql`.

### `stg.sp_delivery` ← `raw.sp_delivery` + `stg.sp_campaigns` ✅ CRIADO E VALIDADO (2026-06-24)

Toda a normalização que a RAW propositalmente não fez (RAW = dump literal, decisão de 22/06).

| Campo STG | Fonte / Lógica |
|---|---|
| `pi_externo` | `coluna_1` (renomeado — campo confirmado pelo usuário) |
| `date` | `PARSE_DATE('%d/%m/%Y', data)` |
| `campaign_id` | `campanha` (já é a chave — sem necessidade de normalizar mais) |
| `client_name` | `SPLIT(campanha, '_')[OFFSET(1)]` |
| `client_id, formato, goal_type` | via join `stg.sp_campaigns` — denormalizado a pedido do usuário (não reabre a resolução) |
| `criativo` | passthrough (texto livre, sem catálogo/FK na Siprocal) |
| `impressions, clicks` | `SAFE_CAST(... AS INT64)` |
| `ctr` | `SAFE_DIVIDE(clicks, impressions)` — **recalculado, não usa o `ctr` da RAW** (string BR `"1,82%"`, arredondada). Confirmado contra dado real: 10/1120 linhas têm diferença de precisão entre fonte (arredondada) e recalculado (exato) — recalculado é mais preciso. |

**Resultado real:** 1121/1121, 100% com `client_id`/`formato`. 1120/1121 com `ctr` (1 com `impressions=0`, fonte tinha `#DIV/0!` literal). DDL: `stg/ddl/sp_delivery.sql`.
| `goal_type` | join `core.dict_format('push', platform='siprocal')` |

**Sem `client_id` aqui** — quem precisar junta com `stg.sp_clients` pelo `client_name`.

⚠️ **Pendências já registradas na RAW:** 193/1121 linhas com `coluna_1 = "(vazio)"` (sem PI), 2 valores não-numéricos (`"CS - 012"`, `"NW0825"`) — investigar se afeta `client_name`/atribuição antes de fechar.

---

## Cross-plataforma (regras de negócio / pacing)

### `stg.fact_pacing_base` ← `gold.fact_io_plan` + `gold.fact_delivery` ✅ criada 2026-08-10 (parcial)

Materialização física (TABLE, não VIEW) do cruzamento planejado×realizado que antes vivia
como CTE inline (`pacing_base`, FULL OUTER JOIN) dentro de `gold/ddl/fact_pacing.sql`.
Grain: `client_id` + `day` + `formato` + `platform`.

| Campo | Tipo | Origem/lógica |
|---|---|---|
| client_id, day, formato, platform | STRING/DATE | chave de grain |
| planned_spend_daily, planned_impressions_daily, planned_clicks_daily, unit_price, goal_type | NUMERIC/FLOAT64/STRING | `gold.fact_io_plan`, agregado por dia antes do JOIN (CTE `io_agg`, evita duplicação quando o mesmo dia tem 2 `unit_price`/`goal_type`) |
| realized_impressions, realized_clicks, realized_conversions, investimento_realizado | FLOAT64 | `gold.fact_delivery` |

Não inclui as colunas `business_rule_*` — essas continuam calculadas dentro da própria
`gold.fact_pacing`, a partir de `core.client_business_rules`; `fact_pacing_base` é só
"planejado × realizado", sem regra de negócio aplicada.

Motivo de ser TABLE e não VIEW: quebrar a cadeia de `UNION ALL`/`FULL OUTER JOIN` que
impedia `gold.fact_pacing` chamar `core.resolve_client_business_rule()` diretamente
(correlated subquery não decorrelacionável em BigQuery) — ver `docs/core_layer_design.md`
(seção `client_business_rules`) e `docs/known_issues.md` (G9, resolvido) para o desvio do
ADR-0001 que motivou isso.

Populada via `stg/ddl/fact_pacing_base_refresh.sql` (`CREATE OR REPLACE TABLE ... AS
SELECT`, aplicável por `apply_ddl.py`). 🟡 **refresh manual sob demanda** — agendamento
automático (Cloud Scheduler ou equivalente) fica fora de escopo, pendência registrada.
Schema garantido só em `stg/ddl/fact_pacing_base.sql` — nunca popula/sobrescreve dado.

✅ validado em 2026-08-10, só em `douglas-bq-staging`.

---

## IO Plan (separado do fluxo de delivery)

`raw.io_plan_drive_snapshot` → `stg.io_plan` — parse do campo `estrategia` para extrair `formato` (regex/lookup, ex: `"Native - Performance"` → `native`). Pendência isolada, registrada desde 18/06, não bloqueia a STG de delivery.

---

## Sequência de implementação proposta

Mesma disciplina da RAW — implementar, testar contra dado real, validar antes de avançar:

1. **Catálogos primeiro** (sem dependência de delivery): `stg.ms_advertisers`, `stg.ms_campaigns` (testar parse de formato), `stg.ms_creatives`, `stg.mg_campaigns` (testar resolução de client_id), `stg.mg_teasers`
2. **Delivery base (T4 equivalente)**: `stg.ms_delivery`, `stg.mg_delivery` — validar joins e `ctr`
3. **Delivery por dimensão (T5/T6/T7 equivalente)**: os 6 restantes, mesma lógica de `stg.ms_delivery`/`stg.mg_delivery`
4. **Siprocal**: `stg.sp_delivery` — mais pesado por ser só agora que a normalização acontece
5. **IO Plan**: separado, sem pressa

---

## Pendências a decidir antes de implementar

- [ ] Confirmar mapeamento exato `campaign_type → formato` para MGID com o comercial (a tabela acima é minha inferência, não confirmada)
- [ ] Decidir se `client_id` nulo (MGID sem vínculo, 27%) deve aparecer como `NULL` na STG ou ser filtrado — afeta contagem de linhas em relatórios
- [ ] Confirmar se Siprocal precisa de uma tabela `platform_client_links`-equivalente, ou se `client_name` (texto) é suficiente para o gold
