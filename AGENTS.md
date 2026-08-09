# AGENTS.md — newad-adframework-bq

> **Manutenção:** Tier 3 — revisão quando comando de build/test/deploy mudar

Comandos universais/mecânicos deste repositório, válidos pra qualquer assistente de IA
(Copilot, Cursor, Claude, etc.) — não só o ecossistema Claude. Comportamento, roteamento
de subagentes e protocolo de documentação/Notion ficam em `CLAUDE.md`, não aqui.

Este repo é **SQL/DDL/scripts Python de operação**, não uma aplicação com build/test
tradicional — a maioria das seções "padrão" de um `AGENTS.md` (build, lint, test suite)
não se aplica hoje. O que existe é documentado abaixo; não invente comando que não roda.

---

## O que este repositório é

- SQL/DDL do pipeline BigQuery Medallion (RAW → STG → CORE → GOLD).
- Scripts Python de deploy/ETL operacional (`scripts/deploy/`, `scripts/io_plan/`,
  `scripts/siprocal/`).
- O painel Streamlit `hub/` (deploy próprio, Cloud Run `douglas-data-hub`).
- **Não vive aqui:** o código do ETL/orquestrador (`adframework_python`) — isso é o
  repositório `rshiro-newad/adframework` (write access do Shiro; leitura permitida daqui
  pra confirmar fato real).

---

## Setup

Não há `pip install -r requirements.txt` de projeto único — cada componente tem o seu:

```bash
# Hub Streamlit
cd hub && pip install -r requirements.txt

# Scripts de deploy (apply_ddl.py, load_historical_override.py, etc.) usam
# google-cloud-bigquery — não há requirements.txt dedicado; instalar conforme
# o import falhar (google-cloud-bigquery, pandas).
```

Autenticação GCP local (obrigatória antes de qualquer comando `bq`/`gcloud`/script Python
que use `google.cloud.bigquery`):

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project adframework
```

---

## Aplicar DDL (raw/stg/core/gold)

**Nunca** rode DDL direto via `bq query` contra produção sem passar por `apply_ddl.py` —
é o mecanismo formal de teste em 2 níveis (ver docstring completo do script).

```bash
# Testar contra dataset _test gêmeo, produção
python scripts/deploy/apply_ddl.py gold/ddl/fact_delivery.sql --env=test

# Aplicar em produção de verdade
python scripts/deploy/apply_ddl.py gold/ddl/fact_delivery.sql --env=prod \
  --reason="..." --summary="..."

# Aplicar contra um projeto GCP inteiro alternativo (ex: staging)
python scripts/deploy/apply_ddl.py gold/ddl/fact_delivery.sql --env=test \
  --project=douglas-bq-staging

# Ver o SQL final sem executar
python scripts/deploy/apply_ddl.py gold/ddl/fact_delivery.sql --env=test --dry-run

# Reverter uma mudança já aplicada em prod (usa previous_definition capturada
# automaticamente em core.schema_change_log)
python scripts/deploy/apply_ddl.py --rollback <change_id>
```

Toda execução (test ou prod) grava uma linha de auditoria em `core.schema_change_log`
(sempre no dataset `core` real, nunca `core_test`) — não pular com `--no-log` fora de
debug pontual.

---

## Fluxo de dado histórico por cliente (staging)

```bash
# 1. Normalizar upload já pousado em douglas-bq-staging.raw.historical_uploads
python scripts/deploy/normalize_historical_upload.py --upload-id <upload_id>

# 2. Carregar o CSV normalizado em stg.historical_overrides_delivery
python scripts/deploy/load_historical_override.py --input <arquivo.csv> --client-id <client_id>
```

Cada cliente precisa de um mapeamento próprio em
`scripts/deploy/historical_mappings/<client_id>.py` (contrato documentado em
`historical_mappings/__init__.py`) — o normalizador falha alto se o mapeamento não existir.

---

## Sync de planilhas (Google Drive/Sheets)

```bash
python scripts/io_plan/sync_drive.py       # IO Plan (Google Drive → BQ)
python scripts/siprocal/sync_sheet.py      # legado — ver docs/known_issues.md #10, substituído por SiproCalConnector
```

---

## Hub Streamlit (`hub/`)

```bash
# Rodar local antes de qualquer deploy
cd hub && streamlit run app.py
# → http://localhost:8501

# Deploy — SEMPRE confirmar com o usuário antes de rodar (cria/altera recursos GCP reais)
HUB_PASSWORD="..." ./hub/deploy.sh
```

Deploy automático também dispara via `.github/workflows/hub_deploy.yml` em push na `main`
que toca `hub/**` (chave de SA em secret do GitHub — ver `docs/known_issues.md` pra estado
de provisionamento).

---

## Checks de qualidade de dado

```bash
# SQLs de auditoria — rodar manualmente via bq/console, sem runner automatizado
ls scripts/data_quality/
ls audit/client_analysis/
ls audit/raw_layer/
```

---

## Zonas não-editáveis (nunca escrever)

| O quê | Por quê |
|---|---|
| Datasets `pixel`, `adtracking`, `analytics`, `finops_billing` | Serviços externos — ver `CLAUDE.md` |
| Objetos listados como `shiro_admin_ui`/`legacy_disabled` em `core/OWNERSHIP.yaml` | Não são deste pipeline |
| Projeto GCP `striped-bonfire-489318-t9` | Dashboard emergencial temporário |
| Repositório `rshiro-newad/adframework` | Somente leitura a partir daqui |
| `docs/*` (exceto via processo do agente `docs` — ver `CLAUDE.md`) | Documentação tem dono único |

---

## Testes

Não existe suíte de testes automatizada neste repositório nem em `adframework_python`
(confirmado por auditoria em 2026-08-03 — ver `.claude`/`agents/backend.md` local para o
critério de o que seria testável se/quando construído). "Testado" hoje significa: rodado
contra `--env=test` ou `douglas-bq-staging`, resultado conferido manualmente (linha a
linha ou via `EXCEPT DISTINCT` contra produção).

---

## CI

- `.github/workflows/cora_sheets_sync.yml` — sync agendado da planilha Cora.
- `.github/workflows/hub_deploy.yml` — deploy do hub em push na `main` tocando `hub/**`.

Nenhum workflow roda lint/test — não existe pipeline de CI de qualidade de código neste
repositório hoje.
