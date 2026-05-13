# Mapa de Dependência de IDs — raw → gold

> Gerado em 2026-05-13 | Fonte: INFORMATION_SCHEMA + análise de código rshiro-newad/adframework
> Colunas verificadas: 995 em 7 datasets

---

## Como ler este documento

Cada seção mostra **um conceito de ID** e como seu nome muda à medida que sobe pelas camadas.
Os JOINs entre seções (ex: `advertiser_platform_id` = `link_value`) são os pontos onde dados podem ser perdidos silenciosamente.

---

## 1. Campaign ID — identifica a campanha no DSP

| Camada | Tabela | Coluna | Observação |
|---|---|---|---|
| **raw** | `mediasmart_daily` | `controlid` | Sem underscore — nome interno MS |
| **raw** | `mgid_daily` | `campaignid` | Sem underscore — `normalize_data()` aplica lowercase sem underscore |
| **raw** | `siprocal_daily_materialized` | `campaign_id` | Com underscore |
| **raw** | `mediasmart_revenue_daily` | `controlid` + `campaign_id` | ⚠️ Duas colunas para o mesmo conceito na mesma tabela |
| **raw** | `mediasmart_daily_legacy_*` | `campaign_id` + `controlid` | ⚠️ Tabelas legacy têm AMBAS as variantes |
| **stg** | `mediasmart_daily`, `mgid_daily`, `siprocal_daily` | `platform_campaign_id` | Primeiro nome unificado |
| **core** | `io_manager_v2`, `io_line_bindings_v2` | `platform_campaign_id` | Digitado manualmente no Admin UI — sem validação |
| **marts / share / gold** | todos | `platform_campaign_id` | Estável daqui em diante |

**⚠️ Problema:** Raw tem 3 nomes diferentes para o mesmo conceito: `controlid` (MS), `campaignid` (MGID), `campaign_id` (Siprocal). A STG unifica. Se o CAST ou JOIN falhar silenciosamente em qualquer transição, a delivery desaparece sem erro.

---

## 2. Advertiser / Account ID — identifica a conta do anunciante no DSP (chave de atribuição de cliente)

Este é o **JOIN mais crítico do sistema**. É aqui que delivery encontra cliente.

| Camada | Tabela | Coluna | Observação |
|---|---|---|---|
| **raw** | `mediasmart_daily` | `eventid` | Sem underscore |
| **raw** | `mediasmart_bid_supply_daily` | `event_id` + `eventid` | ⚠️ Ambos na mesma tabela |
| **raw** | `mediasmart_revenue_daily` | `event_id` + `eventid` | ⚠️ Ambos aqui também |
| **raw** | `mediasmart_daily_legacy_*` | `event_id` + `eventid` + `campaign_id` | 3 variantes nas tabelas legacy |
| **stg** | `mediasmart_daily` | `event_id` | Com underscore |
| **stg** | `mediasmart_operational_v2` | `advertiser_platform_id` | Renomeado novamente |
| **share** | `newad_operational_daily`, `platform_daily_detail` | `advertiser_platform_id` | Nome estável no share |
| **core** | `platform_client_links` | `link_value` | ⚠️ Nome completamente diferente — é aqui que `advertiser_platform_id` se junta a `newad_client_id` |

**JOIN crítico:**
```
share.platform_daily_detail.advertiser_platform_id
  = core.platform_client_links.link_value
  → core.platform_client_links.newad_client_id
```
Se os valores não baterem exatamente (case, espaço, formato), o cliente desaparece da gold sem erro.

---

## 3. Strategy ID — identifica a estratégia/ad set dentro da campanha (somente MediaSmart)

| Camada | Tabela | Coluna | Observação |
|---|---|---|---|
| **raw** | `mediasmart_daily` | `strategyid` | Sem underscore |
| **raw** | `mediasmart_bid_supply_daily` | `strategyid` + `strategy_id` | ⚠️ Ambos na mesma tabela |
| **stg** | `mediasmart_daily` | `strategy_id` | Com underscore |
| **stg** | `mediasmart_operational_v2` | `platform_strategy_id` | Renomeado |
| **share / gold** | `platform_daily_detail`, `fct_delivery_daily` | `platform_strategy_id` | Estável |
| **share** | `luckbet_*`, `report_daily_*` | `strategy_id` | ⚠️ Nome antigo ainda em uso — inconsistência interna no share |

---

## 4. Client ID — identifica o anunciante dentro do NewAD (gerado pelo Admin UI)

| Camada | Tabela | Coluna | Observação |
|---|---|---|---|
| **Firestore** | `platform_clients/{id}` | document ID | Origem — gerado por `_gen_platform_client_id()` |
| **raw_newadframework** | `platform_client_links`, `io_line_bindings_v2`, `io_manager_v2` | `newad_client_id` | Sync manual Firestore → BQ |
| **stg** | `io_lines_v4` | `newad_client_id` | Propagado do io_manager |
| **core / marts / share / gold** | todos | `newad_client_id` | Estável — mas chega APENAS via IO binding |

**⚠️ Problema fundamental:** `newad_client_id` **nunca aparece nas tabelas de delivery** (`mediasmart_daily`, `platform_daily_detail`, `newad_operational_daily`). Ele só chega à gold via:

```
delivery (platform_campaign_id)
  JOIN io_line_bindings (platform_campaign_id → line_id)
  JOIN io_lines (line_id → newad_client_id)
```

Se não existe IO binding para aquela campaign, a delivery não tem `newad_client_id` e fica invisível na gold.

---

## 5. IO ID / Line ID / Binding ID — identificam o plano de mídia (Admin UI)

| Camada | Tabela | Coluna | Observação |
|---|---|---|---|
| **Firestore** | `io_manager/{line_id}` | document ID | Origem — determinístico: `io_{slug(io_number)}` |
| **raw_newadframework** | `io_manager_v2`, `io_line_bindings_v2` | `io_id`, `line_id`, `binding_id` | Sync manual |
| **stg** | `io_lines_v4` | `io_id`, `line_id` | |
| **core** | `io_binding_registry_v4`, `io_registry_v4` | `io_id`, `line_id`, `binding_id` | Versão v4 (mais recente) |
| **core** | `io_manager`, `io_manager_enriched`, `io_manager_legacy_cache` | `io_id`, `line_id` | ⚠️ 3 versões legadas ainda existem |
| **marts** | `io_calc_daily_v4`, `io_delivery_daily_v4` | `io_id`, `line_id` | |
| **share / gold** | todos | `io_id`, `line_id` | Estáveis |

**⚠️ Problema:** `io_id` é determinístico (slug). Se `io_number` estiver em branco, dois IOs do mesmo anunciante geram o mesmo `io_id` — o segundo sobrescreve o primeiro silenciosamente.

---

## 6. Proposal ID — agrupamento acima do IO (pouco documentado)

| Camada | Coluna | Observação |
|---|---|---|
| **raw_newadframework** | `proposal_id` | Em `io_manager_v2`, `io_line_bindings_v2`, `proposals`, `proposal_lines` |
| **stg / core / marts / share / gold** | `proposal_id` | Propagado em quase todos os cálculos |

Relação: um `proposal_id` agrupa múltiplos `io_id`. Origem e geração não documentadas no código do repositório.

---

## 7. IDs problemáticos — existem no schema mas causam confusão

| Coluna | Onde aparece | Problema |
|---|---|---|
| `advertiser_id` | `core.platform_client_links`, `gold.dim_client`, marts, share, gold | ⚠️ Coexiste com `newad_client_id` na mesma tabela — é um ID diferente (slug legacy ou hash SHA256 do nome). Dois identificadores para o mesmo cliente real |
| `nwd_adv_id` / `nwd_agc_id` | Apenas tabelas v4 (stg, core, marts, share, gold) | IDs novos — ausentes nas tabelas v2/v3. "adv" = advertiser, "agc" = agency? Significado não documentado |
| `campaign_id` | Coexiste com `platform_campaign_id` em `share.report_*`, `share.dashboard_*`, `share.pacing_*` | ⚠️ Dois nomes para o mesmo campo em views de share — ambíguo |
| `campanha_id` | `share.mediasmart_postview_postclick` | Nome em português — alias isolado, não conecta ao resto do pipeline |
| `io_line_id` | `share.report_daily_roas_line_pivot` | Mais um alias de `line_id` — inconsistência de nomenclatura |
| `newad_advertiser_id` / `newad_campaign_id` | `share.newad_powerdata_daily` | Prefixo `newad_` diferente de `newad_client_id` — relação não documentada |
| `platform_entity_id` / `platform_parent_id` | `core.io_line_bindings_v2` | Sem uso documentado — possivelmente legados de uma versão anterior do binding |
| `creative_group_id` / `sample_creative_id` | `share.report_daily_creative_grouped` | IDs derivados, não originados em DSP — lógica de agrupamento não documentada |

---

## 8. Resumo: cadeia completa raw → gold para uma linha de delivery

```
raw.mediasmart_daily
  controlid          → stg.platform_campaign_id  → core.io_line_bindings.platform_campaign_id
  eventid            → stg.event_id              → share.advertiser_platform_id
                                                    = core.platform_client_links.link_value
                                                    → core.platform_client_links.newad_client_id
  strategyid         → stg.strategy_id           → stg.platform_strategy_id

+ core.io_line_bindings_v2
  binding_id
  io_id              ← io_manager_v2.io_id       ← Firestore io_manager
  line_id            ← io_manager_v2.line_id
  newad_client_id    ← platform_client_links.newad_client_id
  binding_scope      → determina se JOIN é por campaign ou strategy

→ marts.io_delivery_daily_v4 (JOIN delivery + bindings)
→ marts.io_calc_daily_v4 (JOIN io_delivery + io_schedule)
→ share.io_calc_daily_v4
→ gold.fct_delivery_daily
```

**Cada `→` é um ponto de falha silenciosa se os valores não baterem.**
