# Problemas de Qualidade de IDs — AdFramework

> Análise realizada em 2026-05-12  
> Baseada no repositório github.com/rshiro-newad/adframework + inspeção BigQuery

---

## Resumo executivo

Há **6 classes de problemas estruturais** na geração e uso de IDs no AdFramework. Alguns causam duplicação silenciosa na gold layer, outros causam perda de dados históricos, e alguns criam JOINs que silenciosamente retornam NULL sem erro. Nenhum é catastrófico isolado, mas combinados explicam os problemas de duplicação observados (especialmente Luckbet).

---

## 1. `newad_client_id` — sem unicidade por anunciante real

**Arquivo:** `admin_ui/app/main.py`, linha 312  
**Função:** `_gen_platform_client_id(name)`

```python
def _gen_platform_client_id(name: str = "") -> str:
    base = _slug(name)
    suffix = uuid.uuid4().hex[:8]   # apenas 8 hex = sufixo curto
    return f"nwd_{base[:20]}_{suffix}"
```

**Problema:** A unicidade é checada pelo ID gerado (document ID no Firestore), não pelo nome do anunciante. Dois admins podem criar dois `platform_clients` para o mesmo anunciante real — o sistema não impede isso. O endpoint `/platform-clients/create` não tem validação de duplicidade por `advertiser_name`.

**O que causou o Luckbet duplo:** `nwd_luckbet_a485d6bc` e `nwd_luckbet_69e72f18` foram criados em dois momentos diferentes (possivelmente via backfill e depois via UI, ou dois imports manuais). O sistema aceitou ambos sem reclamar.

**Risco adicional:** A verificação de unicidade é um Firestore read-before-write **sem transaction**. Sob concorrência, dois creates simultâneos podem ambos ver `exists=False` e o segundo sobrescreve o primeiro silenciosamente.

**Ação necessária (Shiro):**
- Adicionar validação por `advertiser_name` antes de criar novo `platform_client`
- Implementar deduplicação: verificar se já existe um cliente com mesmo nome ou mesmo DSP account ID

---

## 2. `io_id` e `line_id` — determinísticos, não aleatórios

**Arquivo:** `admin_ui/app/main.py`, linha 1232; `scripts/import_io_manager_firestore.py`

```python
io_id   = f"io_{_slug(io_number or advertiser_name or 'io')}"
line_id = f"{io_id}_line_{_slug(line_number)}"
```

**Problema crítico:** Se `io_number` estiver em branco para múltiplos IOs do mesmo anunciante, todos recebem o mesmo `io_id`. Exemplo: dois IOs da Luckbet sem `io_number` → ambos geram `io_luckbet`. As linhas de ambos ficam com `line_id` idênticos. O Firestore (`.set()`) silenciosamente sobrescreve o primeiro com o segundo.

**Impacto no BigQuery:** `gold.dim_io_line` faz `QUALIFY ROW_NUMBER() OVER (PARTITION BY line_id ORDER BY start_date DESC) = 1` — mantém apenas o mais recente, descartando os outros sem nenhum aviso ou erro.

**Problema secundário:** Quando um IO é editado (novo `io_number` ou `line_number`), o código cria um novo documento Firestore e deleta o antigo. O BigQuery (`core.io_manager_v2`) é sincronizado manualmente — existe uma janela de tempo onde o `line_id` em `core.io_line_bindings_v2` aponta para um documento que não existe mais.

**Ação necessária (Shiro):**
- Garantir que `io_number` seja obrigatório e único por anunciante
- Ou trocar para UUID aleatório (`uuid4().hex[:8]`) em vez de slug determinístico
- Implementar sync automático Firestore → BQ após qualquer operação de IO

---

## 3. `platform_client_links` — tabela manual, fora do código

**Achado:** `core.platform_client_links` (27 linhas), `core.io_manager_v2` (229 linhas) e `core.io_line_bindings_v2` (170 linhas) **não são criadas por nenhum script do repositório**. São objetos BQ mantidos manualmente.

**O Admin UI escreve no Firestore** (subcollection `platform_clients/{id}/activations/{platform}`). A sincronização Firestore → BigQuery não está automatizada no código.

**Impacto:** Qualquer ativação de link feita no Admin UI só chega ao BigQuery quando alguém executa a sincronização manual. O intervalo de desatualização é desconhecido.

**Ação necessária (Shiro):**
- Documentar o processo de sync manual: quem executa, com que frequência, qual query/script
- Ou implementar sync automático via Cloud Function/Pub-Sub no evento de write do Firestore

---

## 4. Siprocal — atribuição por nome, sem ID estruturado + histórico destruído

**Arquivo:** `orchestrator.py`, método `_run_siprocal_external()`

```python
# Recria a tabela do zero a cada execução
"CREATE OR REPLACE TABLE raw.siprocal_daily_materialized AS SELECT ... FROM {source_ref}"
```

**Dois problemas independentes:**

**4a. Sem ID estruturado:** `link_value` para Siprocal é o campo `advertiser` (STRING livre, ex: `"luckbet"`). Se alguém digitar `"Luckbet"` no Google Sheet em vez de `"luckbet"`, o JOIN falha silenciosamente e a entrega desaparece da gold. Não há LOWER() aplicado no storage.

**4b. Histórico destruído:** `CREATE OR REPLACE TABLE` apaga e recria a tabela inteira a cada run. Se o Google Sheet for editado retroativamente, dados históricos são perdidos. Isso explica por que `raw.siprocal_daily_materialized` parou em **2026-03-08** — se o Sheet foi encerrado ou modificado, o histórico anterior foi sobrescrito.

**Ação necessária (Shiro):**
- Trocar `CREATE OR REPLACE` por INSERT incremental com deduplicação por `(day, advertiser, campaign_id)`
- Aplicar `LOWER(TRIM(advertiser))` no momento da ingestão
- Definir um ID numérico para Siprocal ou usar `campaign_id` como chave em vez do nome do anunciante

---

## 5. MGID — nome de coluna sem underscore após normalize_data

**Arquivo:** `adframework_python/src/base.py`, método `normalize_data()`

O normalizador converte `campaignId` → `campaignid` (tudo minúsculo, sem underscore). Isso é diferente de `campaign_id` (com underscore).

**Impacto potencial:** Qualquer SQL que referencie `campaign_id` esperando dados MGID pode silenciosamente receber NULL se a coluna real se chama `campaignid`. Precisa verificar nos views stg se o JOIN está usando o nome correto.

**Ação necessária (Shiro):**
- Confirmar que todas as stg views que leem `raw.mgid_daily` usam o nome correto `campaignid` (sem underscore)
- Ou corrigir o normalizador para gerar `campaign_id` via regex `s/([a-z])([A-Z])/\1_\2/`

---

## 6. Creative fetch usa `io_manager_enriched` (legacy, 62 linhas) em vez de `io_manager_v2` (229 linhas)

**Arquivo:** `orchestrator.py`, linha ~723, método `_fetch_mediasmart_creatives_iter()`

O código busca criativos usando `core.io_manager_enriched`, que por sua vez lê `core.io_manager` — a **tabela externa apontando para o Google Sheets** com apenas 62 linhas (IO legados). `core.io_manager_v2` tem 229 linhas (estado atual).

**Impacto:** Metadados de criativos só são buscados para ~27% dos IOs. Os outros 73% nunca têm criativos fetchados automaticamente.

**Ação necessária (Shiro):**
- Trocar a query de lookup de criativos para usar `core.io_manager_v2` em vez de `core.io_manager_enriched`

---

## Quadro resumo — o que dizer para o Shiro

| # | Problema | Impacto atual | Urgência |
|---|---|---|---|
| 1 | Dois client IDs para Luckbet | Duplicação na gold — números errados | 🔴 Alta |
| 2 | io_id determinístico + sem io_number obrigatório | Perda silenciosa de IOs com mesmo slug | 🔴 Alta |
| 3 | core.* sem sync automático | Lag desconhecido entre Admin UI e BQ | 🟡 Média |
| 4a | Siprocal sem ID estruturado | Risco de JOIN falhar por capitalização | 🟡 Média |
| 4b | Siprocal `CREATE OR REPLACE` destrói histórico | Dados históricos não recuperáveis | 🔴 Alta |
| 5 | MGID coluna `campaignid` vs `campaign_id` | Possível NULL silencioso em JOINs stg | 🟡 Média |
| 6 | Creative fetch usa io_manager legado | 73% dos IOs sem fetch de criativo | 🟡 Média |

---

## O que NÃO está no código (precisa documentar com Shiro)

- Quem executa o sync Firestore → `core.io_manager_v2`?
- Com que frequência e como `core.io_line_bindings_v2` é atualizado?
- Como `core.platform_client_links` foi criado inicialmente e quem o mantém?
- A tabela `share.io_validation_full` (48 linhas, última modificação fev/26) — ainda é usada?
- O dataset `pixel` (mencionado no orchestrator) — existe no projeto BQ? O que armazena?
