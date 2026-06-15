# IO Plan Pipeline — Documentação

> Criado: 2026-06-09  
> Autor: Douglas Reche

Pipeline de planejamento de veiculação: planilhas comerciais do Google Drive → BigQuery → Power BI.

---

## Visão Geral

```
Google Drive                    BigQuery                           Power BI
CLIENT/ANO/MES/PLANO/*.xlsx
  └── sync_drive.py ────────→  raw.io_plan_drive_snapshot        fact_io_plan
                                   (grain: estratégia × flight)    (grain: diário)
                              ↓ core.io_plan_manual               JOIN fact_delivery
                                   (grain: flight × cliente)       → Pacing Dashboard
                              ↓ gold.fact_io_plan VIEW
                                   (grain: diário, GENERATE_DATE_ARRAY)
```

**JOIN com entregas:**
```sql
ON p.client_id = d.client_id AND p.report_date = d.day
```

---

## Tabelas

### `raw.io_plan_drive_snapshot`

Snapshot cru das planilhas. Preserva todos os dados originais sem transformação.

- **Grain:** 1 linha por estratégia × flight × cliente
- **Partição:** `DATE(snapshot_at)`
- **Campos chave:** `client_id`, `source_file`, `spend_type`, `flight_start`, `flight_end`, `strategy_name`, `platform`, `monthly_spend`, `impressions_cpm`, `impressions_est`
- **`spend_type`:** `'gross'` = taxa cliente (R$10-12 CPM) | `'net'` = taxa mídia (R$2-2.25 CPM)
- **Detecção automática de spend_type:** se `unit_price > R$5` → gross, else net

### `core.io_plan_manual`

Agregação ao nível de flight. Fonte de verdade para `gold.fact_io_plan`.

- **Grain:** 1 linha por (client_id, flight_start, flight_end)
- **Clientes ativos:** banco_cora_fe13d78a, amigo_db1c2f0c
- **`plan_version`:** `'DRIVE-SYNC'` (sync automático) | valores manuais para seed inicial
- **`planned_spend_gross`:** somado dos arquivos com taxas de cliente
- **`planned_spend_net`:** somado dos arquivos com taxas de mídia (NULL se não disponível)
- **`planned_impressions`:** prefer arquivo net; fallback para arquivo gross

### `gold.fact_io_plan` (VIEW)

Distribui valores de flight para grain diário via `GENERATE_DATE_ARRAY`.

- **Grain:** 1 linha por (client_id, report_date)
- **Distribuição:** linear (valor_flight ÷ dias_flight por dia)
- **Colunas diárias:** `planned_impressions_daily`, `planned_clicks_daily`, `planned_spend_gross_daily`, `planned_spend_net_daily`
- **Colunas flight:** `planned_*_flight` para auditoria / comparação full-flight

---

## Estrutura de Pastas no Drive

```
ROOT (0ACFCcMtN5j8EUk9PVA)
  ├── CORA/
  │   └── 2026/
  │       ├── JANEIRO/PLANO/*.xlsx
  │       ├── FEVEREIRO/PLANO/*.xlsx
  │       └── MAIO/PLANO/
  │           ├── Plano NEWAD CORA MAI 2026.xlsx           (gross, R$12 CPM)
  │           └── Plano_RAFA_NEWAD_CORA_MAIO_V3.xlsx      (net, R$2.25 CPM)
  └── TEC PAR/
      └── 2026/
          └── JUNHO/PLANO/
              └── Plano NEWAD RAFA_AMIGOCUIABÁ JUNHO.xlsx
```

**Regra de arquivo oficial:** todos os `.xlsx` na pasta `PLANO/` são processados.  
Arquivos com taxas diferentes (gross vs net) são detectados automaticamente pelo `unit_price`:
- `unit_price > R$5` → `spend_type = 'gross'`
- `unit_price ≤ R$5` → `spend_type = 'net'`

**Mapeamento de clientes:**

| Pasta no Drive | client_id         |
|---------------|-------------------|
| CORA          | banco_cora_fe13d78a |
| TEC PAR       | amigo_db1c2f0c    |

---

## Sync Script

**Localização:** `scripts/io_plan/sync_drive.py`

```bash
# Sync todos os clientes (pula arquivos sem modificações no Drive)
python scripts/io_plan/sync_drive.py

# Sync apenas Cora
python scripts/io_plan/sync_drive.py --client cora

# Forçar re-sync (ignora modifiedTime)
python scripts/io_plan/sync_drive.py --force
```

**Lógica de skip:** compara `Drive modifiedTime` com o último `snapshot_at` em `raw.io_plan_drive_snapshot`. Arquivo não modificado = skip.

**Auth:** Application Default Credentials (`gcloud auth login` localmente, service account no Cloud Run).

---

## Admin UI (Cloud Run)

Serviço web para sync on-demand sem precisar da linha de comando.

**Localização:** `services/io-plan-admin/`

**URL:** `https://io-plan-admin-911847757485.us-central1.run.app/?token=0JtsJHAcWtAbCWoslIDEfPS0KcW8koR`

> Guarde este token com segurança — quem tiver a URL completa pode disparar o sync.

**Botões disponíveis:**
- Sync All — todos os clientes, skip se não modificado
- Sync All (forçar) — re-sync mesmo sem modificação
- Sync CORA / Sync TEC PAR — por cliente

**Endpoints:**
- `GET /?token=<token>` — página HTML com botões
- `POST /sync` — executa sync (form: token, client opcional, force opcional)
- `GET /status?token=<token>` — resultado do último sync (JSON)
- `GET /health` — health check sem auth (para Cloud Run probe)

### Deploy

```bash
# Na raiz do repo:
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/adframework/io-plan/io-plan-admin \
  --project adframework \
  -f services/io-plan-admin/Dockerfile .

# Deploy (substituir TOKEN pelo valor real)
gcloud run deploy io-plan-admin \
  --image us-central1-docker.pkg.dev/adframework/io-plan/io-plan-admin \
  --region us-central1 \
  --project adframework \
  --no-allow-unauthenticated \
  --service-account io-plan-sync@adframework.iam.gserviceaccount.com \
  --set-env-vars SYNC_TOKEN=<TOKEN> \
  --memory 512Mi \
  --timeout 120
```

### Service Account necessário

```bash
# Criar service account
gcloud iam service-accounts create io-plan-sync \
  --display-name="IO Plan Drive Sync" \
  --project=adframework

# Permissões BQ
gcloud projects add-iam-policy-binding adframework \
  --member="serviceAccount:io-plan-sync@adframework.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding adframework \
  --member="serviceAccount:io-plan-sync@adframework.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```

**Drive access:** ⚠️ PENDENTE — adicionar `io-plan-sync@adframework.iam.gserviceaccount.com` como Viewer na pasta raiz do Drive (0ACFCcMtN5j8EUk9PVA).  
Sem isso o sync via Cloud Run retorna erro 403 do Drive API. Para sync local, `gcloud auth login` é suficiente.

---

## Cloud Scheduler (Sync Semanal)

```bash
# Segunda-feira 7h (horário de Brasília = UTC-3 → 10h UTC)
# Já criado em 2026-06-09. Próxima execução: 2026-06-15 10h UTC (7h BRT)
# Job: io-plan-weekly-sync (projects/adframework/locations/us-central1)
gcloud scheduler jobs describe io-plan-weekly-sync --location=us-central1 --project=adframework
```

---

## Dados Atuais (seed manual 2026-06-09)

### Banco Cora (banco_cora_fe13d78a)

| Flight | Impressões | Gross R$ | Net R$ | Fonte |
|--------|-----------|---------|--------|-------|
| 01/01–31/01 | NULL | 35.000 | NULL | JAN-MAR manual |
| 01/02–28/02 | NULL | 35.000 | NULL | JAN-MAR manual |
| 01/03–31/03 | NULL | 35.000 | NULL | JAN-MAR manual |
| 01/04–30/04 | 4.248.274 | 60.000 | NULL | ABR AJUSTADO |
| 01/05–10/05 | 914.789 | 12.500 | 2.365 | V3-RAFA |
| 11/05–10/06 | 6.030.115 | 78.750 | 14.700 | V3-RAFA |
| 11/06–10/07 | 2.473.157 | 31.500 | 6.100 | V3-RAFA |
| 11/07–10/08 | 3.631.958 | 47.250 | 8.850 | V3-RAFA |
| 11/08–31/08 | 914.789 | 12.500 | 2.365 | V3-RAFA |

**Total gross:** R$347.500 (Jan-Ago 2026)

### TecPar / Amigo (amigo_db1c2f0c)

| Flight | Impressões | Gross R$ | Net R$ | Nota |
|--------|-----------|---------|--------|------|
| Jan | 3.861.607 | 10.450 | NULL | |
| Fev | 3.861.607 | 10.450 | NULL | |
| Mar | 3.861.607 | 10.450 | NULL | |
| Abr | 3.968.065 | 12.700 | NULL | |
| Mai | 3.861.607 | 60.000 | NULL | ⚠️ ANOMALIA — confirmar |
| Jun | 3.968.065 | 12.700 | NULL | |

**Total gross:** R$116.750 (Jan-Jun 2026)

---

## Pendências Comerciais

Ver `core/ddl/io_plan_manual.sql` para lista completa. Resumo:

1. **[ARQUIVO OFICIAL]** Quando há múltiplos .xlsx na pasta, regra vigente: detectar spend_type pelo `unit_price`. Formalizar padrão de nomes com o time comercial.
2. **[PLANO LÍQUIDO TECPAR]** Sem arquivo de taxas de mídia para TecPar — `planned_spend_net = NULL` para todos os meses.
3. **[IMPRESSÕES CORA JAN-MAR]** Arquivos originais não lidos pelo pipeline — `planned_impressions = NULL`.
4. **[VÍDEO ADS + PUSH APPTARGETING]** Plataforma desconhecida — mapeado para `unknown` no pipeline.
5. **[ANOMALIA MAI TECPAR]** R$60.000 vs média R$10-12K — confirmar com comercial.
6. **[FLIGHTS vs MESES CORA]** Ciclo 11-10 cruza meses calendário — comunicar ao comercial sobre filtros de "Junho" no Power BI.
