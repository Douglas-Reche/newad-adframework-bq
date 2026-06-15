# Google Ads — Integração ao Pipeline AdFramework

> Criado em: 2026-06-12  
> Autor: Douglas Reche  
> Status: **Planejado** — acesso ainda não obtido (confirmar com comercial quais clientes têm campanhas Google Ads)

---

## Contexto

Integração do Google Ads ao pipeline de ingestão AdFramework.  
Objetivo: puxar dados de entrega diários para `raw.google_ads_daily` → `stg.google_ads_delivery` → `gold.fact_delivery`.

**Clientes com possível Google Ads:** Stocco (mencionado pelo time comercial em 2026-06-12).  
**Confirmação pendente:** quais clientes têm campanhas Google Ads gerenciadas pela NewAD?

```
Google Ads API (Reports API v18)
  └── ETL job google_ads_daily  ──────→  raw.google_ads_daily
                                               ↓
                                          stg.google_ads_delivery
                                               ↓
                                          gold.fact_delivery  (JOIN com platform_client_links)
```

---

## Credenciais necessárias

| Campo | Como obter | Status |
|---|---|---|
| Developer Token | Google Ads → Ferramentas → API Center (conta MCC) | ⏳ pendente |
| Client ID (OAuth2) | Google Cloud Console → Credenciais → OAuth 2.0 | ⏳ pendente |
| Client Secret (OAuth2) | Idem | ⏳ pendente |
| Refresh Token | Gerado via fluxo OAuth2 (script abaixo) | ⏳ pendente |
| Customer ID | ID numérico da conta Google Ads (ex: `123-456-7890`) | ⏳ pendente |
| Login Customer ID | ID da conta MCC (manager), se aplicável | ⏳ pendente |

**Nota:** usar credenciais OAuth2 já existentes no projeto GCP `adframework` se possível
(Cloud Console → APIs & Services → Credentials).

---

## Passos para obter credenciais

### Passo 1 — Developer Token

1. Acessar a conta MCC do Google Ads: `ads.google.com`
2. Ir em **Ferramentas → Centro de API**
3. Copiar o **Developer Token** (string alfanumérica)
4. Nível básico (`Basic`) é suficiente para leitura de dados próprios

### Passo 2 — Credenciais OAuth2 no GCP

1. Acessar: `console.cloud.google.com` → projeto `adframework`
2. **APIs & Services → Library** → habilitar **Google Ads API**
3. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
   - Tipo: **Desktop app** (para gerar o refresh token localmente)
   - Nome: `adframework-google-ads`
4. Baixar o JSON com `client_id` e `client_secret`

### Passo 3 — Gerar Refresh Token

Instalar a biblioteca e rodar o script de autenticação:

```bash
pip install google-ads
```

Criar arquivo `google_ads.yaml` temporário:
```yaml
developer_token: SEU_DEVELOPER_TOKEN
client_id: SEU_CLIENT_ID
client_secret: SEU_CLIENT_SECRET
```

Rodar o gerador de credenciais:
```bash
python -m google.auth.transport.requests
# ou usar o script authenticate_in_standalone_application.py
# da biblioteca python-google-ads
```

Processo:
1. Abre URL de autorização no browser
2. Faz login com a conta Google que tem acesso ao Google Ads
3. Autoriza as permissões
4. Script retorna o `refresh_token` — copiar e guardar

### Passo 4 — Salvar no Secret Manager GCP

```bash
gcloud secrets create google-ads-developer-token --replication-policy="automatic"
gcloud secrets create google-ads-client-id --replication-policy="automatic"
gcloud secrets create google-ads-client-secret --replication-policy="automatic"
gcloud secrets create google-ads-refresh-token --replication-policy="automatic"
```

### Passo 5 — Identificar Customer IDs

Para cada cliente com Google Ads:
- Acessar `ads.google.com` com a conta MCC
- Anotar o Customer ID de cada sub-conta (formato: `XXX-XXX-XXXX`)

---

## Endpoints da Google Ads API a usar

| Recurso GAQL | Uso |
|---|---|
| `campaign` | Catálogo de campanhas |
| `ad_group` | Grupos de anúncios |
| `segments.date` + `campaign.id` + métricas | Entrega diária por campanha |

**Query GAQL base para entrega diária:**
```sql
SELECT
  segments.date,
  campaign.id,
  campaign.name,
  campaign.status,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.video_views,
  metrics.view_through_conversions
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
  AND campaign.status != 'REMOVED'
```

**Custo:** `cost_micros` → dividir por `1_000_000` para obter valor em reais (ou moeda da conta).

**Rate limit:** 15.000 operações/dia por conta de desenvolvedor (nível básico).

---

## Schema proposto — raw.google_ads_daily

```sql
CREATE TABLE IF NOT EXISTS `adframework.raw.google_ads_daily` (
  date                      DATE,
  customer_id               STRING,    -- ID da conta Google Ads (sem hifens)
  campaign_id               STRING,
  campaign_name             STRING,
  campaign_status           STRING,
  impressions               INT64,
  clicks                    INT64,
  cost_micros               INT64,     -- custo em micros (÷ 1.000.000 = BRL)
  conversions               FLOAT64,
  video_views               INT64,
  view_through_conversions  INT64,
  raw_ingested_at           TIMESTAMP
)
PARTITION BY date
CLUSTER BY customer_id, campaign_id;
```

---

## Configuração no Firestore (job ETL)

Seguir o mesmo padrão dos jobs existentes. Criar em `platform_reports/google_ads_daily`:

```json
{
  "job_name": "google_ads_daily",
  "platform": "google_ads",
  "table_name": "google_ads_daily",
  "dataset_id": "raw",
  "write_mode": "WRITE_APPEND",
  "schedule": "daily",
  "enabled": true
}
```

---

## Atribuição de clientes

Após obter os Customer IDs e confirmar com o comercial, adicionar em `core.platform_client_links`:

| client_id | platform | link_type | link_value |
|---|---|---|---|
| `stocco_b712c66e` | google_ads | customer_id | (a confirmar) |
| (outros a confirmar) | google_ads | customer_id | (a confirmar) |

---

## Diferenças em relação a MediaSmart/MGID

| Aspecto | MediaSmart/MGID | Google Ads |
|---|---|---|
| Auth | API Key / Bearer token | OAuth2 com refresh token |
| Custo | `wonprice` / `spent` (float) | `cost_micros` (int, ÷1M) |
| Granularidade | `eventid`/`campaign_id` | `campaign.id` (hierarquia: account > campaign > ad_group > ad) |
| Rate limit | 128 req/min | 15.000 ops/dia |
| Dados históricos | Desde ago/2025 (no BQ) | A partir da data de acesso à API |

---

## Perguntas abertas (confirmar com comercial)

1. Quais clientes têm campanhas no Google Ads gerenciadas pela NewAD?
2. Quem tem acesso à conta MCC (conta master) para gerar o Developer Token?
3. O acesso é para leitura somente (relatórios) ou também configuração de campanhas?
4. Stocco: confirmar se os dados do Google Ads são separados do MediaSmart ou complementares?

---

*Documento criado em 2026-06-12 | AdFramework — Newad | douglas@newad.com.br*
