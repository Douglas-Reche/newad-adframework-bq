# Meta Ads — Integração ao Pipeline AdFramework

> Criado em: 2026-06-12  
> Autor: Douglas Reche  
> Status: **Em andamento** — acesso à conta obtido, token ainda não gerado

---

## Visão Geral

Integração do Meta Ads Manager (Facebook Ads) ao pipeline de ingestão AdFramework.  
Objetivo: puxar dados de entrega diários para `raw.meta_daily` → `stg.meta_delivery` → `gold.fact_delivery`.

```
Meta Ads API (Marketing API)
  └── ETL job meta_daily  ──────────→  raw.meta_daily
                                            ↓
                                       stg.meta_delivery
                                            ↓
                                       gold.fact_delivery  (JOIN com platform_client_links)
```

---

## Credenciais obtidas em 2026-06-12

| Campo | Valor |
|---|---|
| Business ID | `1790435678080700` |
| Ad Account ID | `act_726031882766561` |
| Conta | New Ad |
| System User token | ⏳ pendente (ver seção abaixo) |
| App ID | ⏳ pendente (verificar em business.facebook.com → Apps) |

---

## Onde paramos — retomar aqui

Etapa atual: **Criação do System User e geração de token**.

### Passos pendentes

**Passo 1 — Criar System User** _(não feito ainda)_
1. Acessar: `business.facebook.com/settings/system-users?business_id=1790435678080700`
2. Clicar em **"+ Adicionar"**
3. Nome: `adframework-etl` | Função: **Admin**
4. Clicar em **"Criar usuário do sistema"**

**Passo 2 — Atribuir a conta de anúncios ao System User** _(não feito ainda)_
1. Clicar no usuário `adframework-etl` recém-criado
2. Clicar em **"Atribuir recursos"**
3. Tipo: **Contas de anúncios** → selecionar `New Ad (726031882766561)`
4. Permissão: **Admin**

**Passo 3 — Verificar App disponível** _(não feito ainda)_
1. Acessar menu lateral: **Apps**
2. Verificar se existe algum app com Marketing API ativo
3. Se não existir, criar um novo app em `developers.facebook.com`
   - Tipo: **Business**
   - Adicionar produto: **Marketing API**
   - Anotar App ID e App Secret

**Passo 4 — Gerar token do System User** _(não feito ainda)_
1. Voltar para Usuários do Sistema → clicar em `adframework-etl`
2. Clicar em **"Gerar token"**
3. Selecionar o App (do Passo 3)
4. Permissões a marcar:
   - `ads_read`
   - `read_insights`
   - `business_management`
5. Clicar em **"Gerar token"** — **copiar e guardar agora** (só aparece uma vez)
6. Salvar token no Secret Manager GCP: `meta-ads-access-token`

---

## Contexto da conta

- **42 campanhas** visíveis no Ads Manager (últimos 30 dias)
- Campanhas identificadas: Stocco, Stoquinho, BET (provavelmente Luckbet)
- Já existem 2 System Users na conta (`61587030066967`, `61587175529683`) — ambos são "Conversions API System User" para envio de eventos, **não** para leitura de dados
- Os pixels existentes são para Patio Medeiros (sem relação com o pipeline de delivery)

---

## Endpoints da Marketing API a usar

| Endpoint | Uso |
|---|---|
| `GET /{ad_account_id}/insights` | Métricas de entrega agregadas por campanha/dia |
| `GET /{ad_account_id}/campaigns` | Catálogo de campanhas (nome, status, objetivo) |
| `GET /{ad_account_id}/adsets` | Conjuntos de anúncios (targeting, budget) |

**Parâmetros base para `/insights`:**
```
fields=campaign_id,campaign_name,impressions,clicks,spend,reach,frequency
level=campaign
time_increment=1
date_preset=last_30d
```

**Rate limit:** 200 req/hora por token de usuário (Business API).

---

## Schema proposto — raw.meta_daily

```sql
CREATE TABLE IF NOT EXISTS `adframework.raw.meta_daily` (
  date              DATE,
  campaign_id       STRING,
  campaign_name     STRING,
  adset_id          STRING,
  adset_name        STRING,
  impressions       INT64,
  clicks            INT64,
  spend             FLOAT64,
  reach             INT64,
  frequency         FLOAT64,
  platform_position STRING,   -- facebook_feed, instagram_feed, etc.
  device_platform   STRING,   -- mobile_app, desktop
  raw_ingested_at   TIMESTAMP
)
PARTITION BY date
CLUSTER BY campaign_id;
```

---

## Atribuição de clientes

Após a integração, adicionar em `core.platform_client_links`:

| client_id | platform | link_type | link_value |
|---|---|---|---|
| (a definir por campanha) | meta | campaign_id | ID da campanha Meta |

As campanhas "STOCCO \| ..." serão vinculadas ao cliente `stocco_b712c66e`.  
As campanhas "BET..." serão vinculadas ao cliente Luckbet canônico `nwd_luckbet_a485d6bc`.

---

## Próximos passos após obter o token

1. Adicionar `meta` como plataforma em `gold.dim_platform`
2. Criar job `meta_daily` no Firestore (estrutura igual ao `mediasmart_daily_daily`)
3. Criar `stg/ddl/meta_delivery.sql` com normalização e JOIN de criativos
4. Backfill histórico (sugerir: 2026-01-01 em diante)
5. Confirmar atribuição campanha → cliente com time comercial

---

*Documento criado em 2026-06-12 | AdFramework — Newad | douglas@newad.com.br*
