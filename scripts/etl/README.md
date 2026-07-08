# ETL: Cora Google Sheets → BigQuery

---
> **⚠️ LEGADO — PRÉ-REBUILD 2026-06-16 ⚠️**
> Este script sincroniza para `adframework.gold_cora`, dataset que será dropado no rebuild.
> A nova arquitetura lê Cora via pipeline padrão RAW→STG→GOLD unificado.
> Mantenha para consulta histórica — **não executar este script no ambiente atual.**
> Plano atual: [../../docs/bq_restructuring_plan.md](../../docs/bq_restructuring_plan.md)
---

Sync automático das 13 abas da planilha Cora para `adframework.gold_cora` no BigQuery.

## Arquivos

| Arquivo | Função |
|---|---|
| `cora_sheets_sync.py` | Script principal de ETL |
| `apps_script_trigger.js` | Código para colar na Google Sheet (dispara o workflow) |
| `../.github/workflows/cora_sheets_sync.yml` | GitHub Actions workflow |

## Setup (uma vez só)

### 1. Criar Service Account no GCP

```bash
# Criar SA
gcloud iam service-accounts create cora-sheets-sync \
  --display-name="Cora Sheets Sync"

# Dar permissão de escrita no BigQuery
gcloud projects add-iam-policy-binding striped-bonfire-489318-t9 \
  --member="serviceAccount:cora-sheets-sync@striped-bonfire-489318-t9.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding striped-bonfire-489318-t9 \
  --member="serviceAccount:cora-sheets-sync@striped-bonfire-489318-t9.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

# Gerar chave JSON
gcloud iam service-accounts keys create sa_key.json \
  --iam-account=cora-sheets-sync@striped-bonfire-489318-t9.iam.gserviceaccount.com
```

### 2. Compartilhar a planilha com a Service Account

Na Google Sheet da Cora → Compartilhar → adicionar o email:
```
cora-sheets-sync@striped-bonfire-489318-t9.iam.gserviceaccount.com
```
Permissão: **Leitor**

### 3. Adicionar secret no GitHub

GitHub → repo `newad-adframework-bq` → Settings → Secrets → Actions → New secret:
- Nome: `GCP_SA_KEY`
- Valor: conteúdo completo do `sa_key.json` (apagar o arquivo local depois)

### 4. Configurar o Apps Script na planilha (trigger por edição)

1. Na Google Sheet: **Extensões → Apps Script**
2. Cola o conteúdo de `apps_script_trigger.js`
3. Em **Configurações do projeto → Propriedades do script**, adiciona:
   - `GITHUB_TOKEN` = seu PAT do GitHub com permissão `Actions: Read & Write`
4. Em **Acionadores**, cria:
   - Função: `triggerDailySync` | Origem: Baseado em tempo | Diariamente | 7h-8h
   - (Opcional) Função: `onSheetEdit` | Origem: Planilha | Ao editar

## Execução local

```bash
# Com ADC (sua conta Google)
python scripts/etl/cora_sheets_sync.py

# Com Service Account
GOOGLE_APPLICATION_CREDENTIALS=sa_key.json python scripts/etl/cora_sheets_sync.py
```

## Tabelas geradas em `gold_cora`

| Tabela | Conteúdo |
|---|---|
| `cora_veiculacao` | DIA / FLIGHT / PERÍODO |
| `cora_consolidado_geral` | Todas as estratégias |
| `cora_consolidado_cpm` | Campanhas CPM |
| `cora_consolidado_cpc` | Campanhas CPC |
| `cora_display` | Display (CPM) |
| `cora_retargeting` | Retargeting (CPM) |
| `cora_video` | Vídeo (CPM + views/vtr) |
| `cora_push` | Push (CPC) |
| `cora_native` | Native (CPC) |
| `cora_regioes` | Dia × Região |
| `cora_devices` | Dia × Device |
| `cora_formatos` | Dia × Estratégia × Formato |
| `cora_criativos` | Dia × Estratégia × Criativo |
