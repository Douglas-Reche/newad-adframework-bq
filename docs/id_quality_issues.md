# Análise de Qualidade de IDs — AdFramework

> Realizada em 2026-05-12 | Fonte: `github.com/rshiro-newad/adframework` + inspeção BigQuery

---

## 1. Mapa de IDs — origem, formato e onde vivem

| ID | Formato | Gerado por | Armazenado em | Exemplo |
|---|---|---|---|---|
| `newad_client_id` | `nwd_{slug}_{8hex}` | `_gen_platform_client_id()` — `main.py:312` | Firestore `platform_clients` → BQ `core.platform_client_links` | `nwd_luckbet_a485d6bc` |
| `io_id` | `io_{slug(io_number)}` | `main.py:1232` (determinístico) | Firestore `io_manager` → BQ `core.io_manager_v2` | `io_202603_nwd-banco-cora-acfae3ab_001` |
| `line_id` | `{io_id}_line_{slug(line_number)}` | `main.py:1232` (determinístico) | Firestore `io_manager` → BQ `core.io_manager_v2` | `io_202603_..._001_line_001` |
| `platform_campaign_id` | string livre (vem do DSP) | Entrada manual no Admin UI (campo de formulário) | `core.io_line_bindings_v2`, `raw.mediasmart_daily` | `35ey8fny8gizx3vfxwac4ft1xjitbfbe` |
| `platform_strategy_id` | string livre (vem do DSP) | Entrada manual ou derivado no stg | `core.io_line_bindings_v2` | — |
| `link_value` | varia por plataforma | Admin UI — seleção de lista BQ | Firestore `activations` → BQ `core.platform_client_links` | MS: `newad_brazil-xyz`, MGID: `12220857`, Siprocal: `luckbet` |
| `advertiser_id` | slug ou hash SHA256 | Legado — várias origens | `core.io_line_bindings_v2`, `gold.dim_client` | `adv_b559ffdcbd` ou `luckbet` |

---

## 2. Problemas encontrados por ID

### `newad_client_id`

| Campo | Detalhe |
|---|---|
| **Problema** | Unicidade checada só pelo ID gerado, não pelo nome do anunciante |
| **Causa raiz** | `/platform-clients/create` não valida se já existe cliente com mesmo `advertiser_name` |
| **Risco adicional** | Read-before-write sem transaction Firestore — concorrência pode criar duplicata |
| **Caso real** | `nwd_luckbet_a485d6bc` (canônico) + `nwd_luckbet_69e72f18` (legacy) — mesmo anunciante, dois IDs |
| **Impacto BQ** | Entrega da Luckbet contada 2-3x na gold layer |
| **Urgência** | 🔴 Alta |
| **Ação** | Adicionar validação por `advertiser_name` antes de criar; bloquear duplicata |

---

### `io_id` e `line_id`

| Campo | Detalhe |
|---|---|
| **Problema** | IDs determinísticos — gerados por slug do `io_number`, não por UUID |
| **Fórmula** | `io_id = f"io_{slug(io_number or advertiser_name)}"` |
| **Risco de colisão** | Se `io_number` estiver em branco, todos os IOs do mesmo anunciante geram o mesmo `io_id` |
| **Comportamento Firestore** | `.set()` sem merge = segundo write sobrescreve o primeiro silenciosamente |
| **Impacto BQ** | `gold.dim_io_line` faz `ROW_NUMBER() PARTITION BY line_id` — mantém só o mais recente, descarta os outros sem aviso |
| **Problema secundário** | Editar `io_number` cria novo documento + deleta o antigo no Firestore; BQ fica desatualizado até o próximo sync manual |
| **Urgência** | 🔴 Alta |
| **Ação** | Tornar `io_number` obrigatório e único; ou trocar para UUID aleatório |

---

### `platform_campaign_id` e `platform_strategy_id`

| Campo | Detalhe |
|---|---|
| **Problema** | Campo de texto livre — sem validação se o ID existe no DSP |
| **Armazenamento** | Guardado exatamente como digitado — sem TRIM, sem LOWER |
| **Risco** | Espaço extra ou capitalização diferente quebra o JOIN com `raw.mediasmart_daily` silenciosamente |
| **Caso real** | 2 campaigns com entrega real (~6M impressões) sem IO binding — nunca aparecem na gold |
| **Impacto BQ** | Linhas da raw que não fazem JOIN com nenhum binding ficam invisíveis na gold |
| **Urgência** | 🟡 Média |
| **Ação** | Adicionar lookup BQ para validar que o ID existe antes de salvar; aplicar TRIM no formulário |

---

### `link_value` (platform_client_links)

| Campo | Detalhe |
|---|---|
| **Problema MediaSmart** | ID estruturado — funciona bem; sem colisão confirmada |
| **Problema MGID** | ID numérico — funciona bem; sem colisão confirmada |
| **Problema Siprocal** | Atribuição por nome (`advertiser = 'luckbet'`) — sem ID estruturado |
| **Risco Siprocal** | Capitalização diferente no Google Sheet (`Luckbet` vs `luckbet`) quebra JOIN silenciosamente |
| **Colisão atual** | `nwd_luckbet_a485d6bc` e `nwd_luckbet_69e72f18` compartilham `link_value = 'luckbet'` no Siprocal |
| **Sem unicidade** | Nada impede dois `newad_client_id` diferentes de ter o mesmo `link_value` na mesma plataforma |
| **Urgência** | 🟡 Média |
| **Ação** | Aplicar `LOWER(TRIM())` no storage do Siprocal; bloquear `link_value` duplicado na mesma plataforma |

---

### `core.*` — tabelas sem sync automático

| Campo | Detalhe |
|---|---|
| **Problema** | `core.platform_client_links`, `core.io_manager_v2`, `core.io_line_bindings_v2` não existem em nenhum script do repositório |
| **O que acontece** | Admin UI escreve no Firestore; BQ recebe via sync **manual** sem frequência documentada |
| **Risco** | Qualquer link ou IO criado no Admin UI pode levar horas/dias para aparecer no BQ |
| **Urgência** | 🟡 Média |
| **Ação** | Documentar quem faz o sync, quando e como; ou automatizar via Cloud Function |

---

## 3. Problemas por plataforma de ingestão

| Plataforma | Script | Modo de carga | Problema |
|---|---|---|---|
| MediaSmart | `orchestrator._run_mediasmart_daily()` | APPEND diário | Funciona bem; valores gravados como STRING (`df.astype(str)`) |
| MGID | `orchestrator._run_mgid_daily()` | APPEND diário | `campaignId` → `campaignid` após normalize (sem underscore); pode quebrar JOIN |
| Siprocal | `orchestrator._run_siprocal_external()` | `CREATE OR REPLACE` (destrói histórico) | Recria tabela inteira a cada run; histórico perdido se Sheet for editado |
| Criativos MS | `orchestrator._fetch_mediasmart_creatives_iter()` | Query em `core.io_manager_enriched` | Usa tabela legada (62 IOs) em vez de `core.io_manager_v2` (229 IOs) — 73% dos IOs sem criativo |

---

## 4. Quadro consolidado — o que levar para o Shiro

| # | ID afetado | Problema | Impacto atual na gold | Urgência |
|---|---|---|---|---|
| 1 | `newad_client_id` | Sem unicidade por anunciante — permite duplicata | Luckbet contada 2-3x | 🔴 Alta |
| 2 | `io_id` / `line_id` | Determinístico — colisão quando `io_number` em branco | IO sobrescrito silenciosamente | 🔴 Alta |
| 3 | `link_value` Siprocal | Nome livre sem LOWER — JOIN quebra por capitalização | Entrega Siprocal pode sumir | 🔴 Alta |
| 4 | `platform_campaign_id` | Campo livre sem validação — sem TRIM | Campaigns órfãs invisíveis na gold | 🟡 Média |
| 5 | `core.*` | Sem sync automático Firestore → BQ | Lag desconhecido | 🟡 Média |
| 6 | MGID `campaignid` | Coluna sem underscore — potencial JOIN NULL | Dados MGID podem sumir no stg | 🟡 Média |
| 7 | Criativos | orchestrator usa `io_manager_enriched` (legado) | 73% dos criativos não são buscados | 🟡 Média |

---

## 5. Perguntas abertas para o Shiro

| Pergunta | Por que importa |
|---|---|
| Quem executa o sync Firestore → `core.*`? Com que frequência? | Sem isso não sabemos o lag real dos dados |
| `core.platform_client_links` foi criado como? Por qual script? | Não existe em nenhum arquivo do repositório |
| `share.io_validation_full` (48 linhas, fev/26) ainda é usada? | Pode ser objeto morto ocupando espaço |
| O dataset `pixel` existe no projeto BQ? O que armazena? | Mencionado no orchestrator mas não aparece nos datasets auditados |
| `nwd_luckbet_69e72f18` pode ser desativado com segurança? | Precisa confirmar que nenhum IO ativo depende dele |
