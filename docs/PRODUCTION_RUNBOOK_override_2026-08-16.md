# Runbook de Promoção — Mecanismo de Override Histórico → Produção

> **Manutenção:** Tier 1 (temporário) — apagar/arquivar depois que os passos abaixo forem executados e confirmados. Não é doc de referência permanente, é um runbook de execução única.

Preparado em 2026-08-16, pra rodar quando o Douglas tiver acesso a terminal (VS Code, provavelmente). Cobre: (A) promoção do encanamento de override + regras de negócio inertes pra `adframework` (produção), (B) agendamento automático do refresh de `stg.fact_pacing_base`, (C) fallback manual.

**Guarda-corpo:** nada disto promove a regra de negócio real (cap 20%) — só o "encanamento" vazio, decisão já fechada com o Douglas (2026-08-16). `core.client_business_rules` fica **vazia** ao final de tudo.

**Ambiente de cada comando está marcado explicitamente** — `[STAGING]` = `douglas-bq-staging`, `[PRODUÇÃO]` = `adframework`. Nunca rodar um comando `[PRODUÇÃO]` sem ter certeza absoluta.

Todos os comandos assumem PowerShell, a partir da raiz do repo (`cd c:\Users\dougl\newad-adframework-bq`).

---

## Pré-requisito — reautenticar

```powershell
gcloud auth login
gcloud auth application-default login
```

Confirmar antes de seguir:
```powershell
gcloud config get-value project
```

---

## Parte A — Promoção do encanamento (9 passos, `[PRODUÇÃO]`)

Cada `apply_ddl.py --env=prod` pede confirmação — **digite o nome exato do objeto** quando pedido (mostrado abaixo de cada comando).

### A1 — `core.resolve_client_business_rule()` (função, inerte)
```powershell
python scripts/deploy/apply_ddl.py core/ddl/resolve_client_business_rule.sql --env=prod --project adframework --reason "Promocao do mecanismo de override historico/regras de negocio (encanamento, sem regra ativada)" --summary "Cria core.resolve_client_business_rule() em producao"
```
Confirmar digitando: `resolve_client_business_rule`

Verificar:
```powershell
bq query --use_legacy_sql=false --project_id=adframework "SELECT routine_name FROM adframework.core.INFORMATION_SCHEMA.ROUTINES WHERE routine_name = 'resolve_client_business_rule'"
```

### A2 — `core.client_business_rules` (tabela, fica vazia)
```powershell
python scripts/deploy/apply_ddl.py core/ddl/client_business_rules.sql --env=prod --project adframework --reason "Promocao do mecanismo de regras de negocio (encanamento, sem regra ativada)" --summary "Cria core.client_business_rules em producao, vazia"
```
Confirmar: `client_business_rules`

Verificar (**esperado: `n=0`**):
```powershell
bq query --use_legacy_sql=false --project_id=adframework "SELECT COUNT(*) AS n FROM adframework.core.client_business_rules"
```

### A3 — `core.resolve_reporting_source()` (função)
```powershell
python scripts/deploy/apply_ddl.py core/ddl/resolve_reporting_source.sql --env=prod --project adframework --reason "Promocao do mecanismo de override historico" --summary "Cria core.resolve_reporting_source() em producao"
```
Confirmar: `resolve_reporting_source`

### A4 — `core.client_reporting_source_config` (tabela + 1 linha Cora)
```powershell
python scripts/deploy/apply_ddl.py core/ddl/client_reporting_source_config.sql --env=prod --project adframework --reason "Promocao do mecanismo de override historico" --summary "Cria core.client_reporting_source_config em producao"
```
Confirmar: `client_reporting_source_config`

Checar que não há linha vigente ambígua (**esperado: 0 linhas**):
```powershell
bq query --use_legacy_sql=false --project_id=adframework "SELECT * FROM adframework.core.client_reporting_source_config WHERE client_id = 'banco_cora_fe13d78a' AND effective_to IS NULL"
```

Inserir a linha real da Cora:
```powershell
bq query --use_legacy_sql=false --project_id=adframework "INSERT INTO adframework.core.client_reporting_source_config (client_id, override_active, effective_from, effective_to, reason, confirmed_by, confirmed_at) VALUES ('banco_cora_fe13d78a', TRUE, CURRENT_DATE(), NULL, 'Promocao para producao -- mecanismo de override historico, MAE Regras de Negocio Configuraveis por Cliente', 'douglas', CURRENT_TIMESTAMP())"
```

Verificar (**esperado: exatamente 1 linha, `override_active=true`**):
```powershell
bq query --use_legacy_sql=false --project_id=adframework "SELECT * FROM adframework.core.client_reporting_source_config"
```

### A5 — `stg.historical_overrides_delivery` (tabela + migração de 1030 linhas)
```powershell
python scripts/deploy/apply_ddl.py stg/ddl/historical_overrides_delivery.sql --env=prod --project adframework --reason "Promocao do mecanismo de override historico" --summary "Cria stg.historical_overrides_delivery em producao"
```
Confirmar: `historical_overrides_delivery`

**Nota sobre os comandos abaixo:** usam here-string (`@'...'@`) em vez de string com aspas duplas, de propósito — evita o problema de escape de backtick do PowerShell que já mordeu esta sessão antes (`douglas-bq-staging` tem hífen, precisa de backtick pra qualificar tabela cross-project, e aspas duplas normais do PowerShell tratam backtick como caractere de escape). Copiar o bloco inteiro de cada comando, incluindo as linhas `$q = @'` e `'@`.

Conferir origem `[STAGING]` (**esperado: `n=1030`, `sum_impr=23831592`, `sum_clicks=95941`, `sum_invest≈378486.74`**):
```powershell
$q = @'
SELECT COUNT(*) AS n, SUM(impressions) AS sum_impr, SUM(clicks) AS sum_clicks, SUM(investimento) AS sum_invest
FROM `douglas-bq-staging.stg.historical_overrides_delivery`
WHERE client_id = 'banco_cora_fe13d78a' AND day BETWEEN '2026-01-07' AND '2026-07-31'
'@
bq query --use_legacy_sql=false --project_id=douglas-bq-staging $q
```

Conferir destino `[PRODUÇÃO]` vazio antes de migrar (**esperado: `n=0` — se não for 0, PARAR e não rodar o INSERT abaixo**):
```powershell
bq query --use_legacy_sql=false --project_id=adframework "SELECT COUNT(*) AS n FROM adframework.stg.historical_overrides_delivery WHERE client_id = 'banco_cora_fe13d78a' AND day BETWEEN '2026-01-07' AND '2026-07-31'"
```

Migrar (staging → produção):
```powershell
$q = @'
INSERT INTO `adframework.stg.historical_overrides_delivery`
  (client_id, day, platform, formato, goal_type, impressions, clicks, investimento, source_file, loaded_by, loaded_at, notes, conversions, planned_impressions_daily, planned_clicks_daily, planned_spend_daily, unit_price)
SELECT client_id, day, platform, formato, goal_type, impressions, clicks, investimento, source_file, loaded_by, loaded_at, notes, conversions, planned_impressions_daily, planned_clicks_daily, planned_spend_daily, unit_price
FROM `douglas-bq-staging.stg.historical_overrides_delivery`
WHERE client_id = 'banco_cora_fe13d78a' AND day BETWEEN '2026-01-07' AND '2026-07-31'
'@
bq query --use_legacy_sql=false --project_id=adframework $q
```

Conferir destino depois (**esperado: idêntico à origem**):
```powershell
bq query --use_legacy_sql=false --project_id=adframework "SELECT COUNT(*) AS n, SUM(impressions) AS sum_impr, SUM(clicks) AS sum_clicks, SUM(investimento) AS sum_invest FROM adframework.stg.historical_overrides_delivery WHERE client_id = 'banco_cora_fe13d78a' AND day BETWEEN '2026-01-07' AND '2026-07-31'"
```

### A6 — `stg.fact_pacing_base` (tabela física + refresh)
```powershell
python scripts/deploy/apply_ddl.py stg/ddl/fact_pacing_base.sql --env=prod --project adframework --reason "Promocao de fact_pacing_base (dependencia de gold.fact_pacing)" --summary "Cria stg.fact_pacing_base em producao"
```
Confirmar: `fact_pacing_base`

```powershell
python scripts/deploy/apply_ddl.py stg/ddl/fact_pacing_base_refresh.sql --env=prod --project adframework --reason "Popula fact_pacing_base com dado real de producao" --summary "Primeiro refresh em producao"
```
Confirmar: `fact_pacing_base`

Verificar (linha da Cora deve mostrar `is_override=true`, `realized_impressions=16880` pra Video 2026-01-09):
```powershell
bq query --use_legacy_sql=false --project_id=adframework "SELECT * FROM adframework.stg.fact_pacing_base WHERE client_id = 'banco_cora_fe13d78a' AND day = '2026-01-09' AND formato = 'Video'"
```

### A7 — `gold.fact_delivery` (view — já muda comportamento real)
```powershell
python scripts/deploy/apply_ddl.py gold/ddl/fact_delivery.sql --env=prod --project adframework --reason "Ativa 4a fonte (override historico) em gold.fact_delivery" --summary "gold.fact_delivery inclui stg.historical_overrides_delivery para dias/clientes com override ativo"
```
Confirmar: `fact_delivery`

### A8 — `gold.fact_pacing` (view)
```powershell
python scripts/deploy/apply_ddl.py gold/ddl/fact_pacing.sql --env=prod --project adframework --reason "Ativa business_rule_* (sem regra ativa) em gold.fact_pacing" --summary "business_rule_* NULL para todos, client_business_rules vazia"
```
Confirmar: `fact_pacing`

Verificar (roda sem erro, `business_rule_*` tudo `NULL`, `is_override` visível):
```powershell
bq query --use_legacy_sql=false --project_id=adframework "SELECT client_id, day, formato, is_override, business_rule_base_field, business_rule_capped_value FROM adframework.gold.fact_pacing WHERE client_id = 'banco_cora_fe13d78a' LIMIT 20"
```

### A9 — `gold.vw_fact_delivery_reporting` (view simplificada — já escrita, `gold/ddl/vw_fact_delivery_reporting.sql`)
```powershell
python scripts/deploy/apply_ddl.py gold/ddl/vw_fact_delivery_reporting.sql --env=prod --project adframework --reason "Simplifica vw_fact_delivery_reporting -- remove hardcode Cora, ja resolvido em fact_delivery" --summary "vw_fact_delivery_reporting vira SELECT * FROM gold.fact_delivery"
```
Confirmar: `vw_fact_delivery_reporting`

Verificar (range Jan-Jul/2026 da Cora deve retornar dado, `n > 0`):
```powershell
bq query --use_legacy_sql=false --project_id=adframework "SELECT COUNT(*) AS n FROM adframework.gold.vw_fact_delivery_reporting WHERE client_id = 'banco_cora_fe13d78a' AND day BETWEEN '2026-01-01' AND '2026-07-31'"
```

### Verificação end-to-end final
```powershell
bq query --use_legacy_sql=false --project_id=adframework "SELECT * FROM adframework.gold.fact_pacing WHERE client_id = 'banco_cora_fe13d78a' AND day = '2026-01-09'"
```
Confirmar: `is_override=TRUE`, `realized_impressions` corrigido, `business_rule_*` tudo `NULL`.

---

## Parte B — Agendamento automático do refresh de `stg.fact_pacing_base` (`[PRODUÇÃO]`)

**Faz depois da Parte A estar 100% confirmada** (a tabela precisa existir antes de agendar o refresh dela).

### B0 — Confirmar horário real do ETL diário (pra não agendar o refresh antes dele terminar)
```powershell
gcloud scheduler jobs describe adframework-etl-daily --project=adframework --location=us-central1 --format="value(schedule)"
```
Anotar o horário — o job novo (`B2` abaixo) precisa rodar depois que esse termina (com folga de segurança, ex: +30min).

### B1 — Criar service account dedicada + permissões
```powershell
gcloud iam service-accounts create fact-pacing-base-refresh-sa --project=adframework --display-name="Refresh automatico de fact_pacing_base"

gcloud projects add-iam-policy-binding adframework --member="serviceAccount:fact-pacing-base-refresh-sa@adframework.iam.gserviceaccount.com" --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding adframework --member="serviceAccount:fact-pacing-base-refresh-sa@adframework.iam.gserviceaccount.com" --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding adframework --member="serviceAccount:fact-pacing-base-refresh-sa@adframework.iam.gserviceaccount.com" --role="roles/bigquery.jobUser"
```

### B2 — Deploy da Cloud Function (já escrita: `scripts/deploy/fact_pacing_base_scheduler/`)
```powershell
gcloud functions deploy fact-pacing-base-refresh --gen2 --project=adframework --region=southamerica-east1 --runtime=python312 --source=scripts/deploy/fact_pacing_base_scheduler --entry-point=refresh_fact_pacing_base --trigger-http --no-allow-unauthenticated --service-account=fact-pacing-base-refresh-sa@adframework.iam.gserviceaccount.com --memory=256Mi --timeout=300s
```

Pegar a URL gerada:
```powershell
gcloud functions describe fact-pacing-base-refresh --gen2 --project=adframework --region=southamerica-east1 --format="value(serviceConfig.uri)"
```

### B3 — Testar manualmente (chamada autenticada única, sem esperar o Scheduler)
```powershell
$url = gcloud functions describe fact-pacing-base-refresh --gen2 --project=adframework --region=southamerica-east1 --format="value(serviceConfig.uri)"
$token = gcloud auth print-identity-token
Invoke-RestMethod -Uri $url -Headers @{ Authorization = "Bearer $token" } -Method Post
```
Esperado: JSON `{"status": "ok", "table": "adframework.stg.fact_pacing_base", "row_count": N}`.

### B4 — Criar o Cloud Scheduler (ajustar `--schedule` com o horário confirmado em B0 — exemplo abaixo assume ETL às 05:00 UTC, refresh às 05:45 UTC)
```powershell
gcloud iam service-accounts create fact-pacing-base-scheduler-invoker --project=adframework --display-name="Invoca a function de refresh via OIDC"

gcloud functions add-invoker-policy-binding fact-pacing-base-refresh --gen2 --project=adframework --region=southamerica-east1 --member="serviceAccount:fact-pacing-base-scheduler-invoker@adframework.iam.gserviceaccount.com"

$url = gcloud functions describe fact-pacing-base-refresh --gen2 --project=adframework --region=southamerica-east1 --format="value(serviceConfig.uri)"

gcloud scheduler jobs create http fact-pacing-base-refresh-daily --project=adframework --location=southamerica-east1 --schedule="45 5 * * *" --time-zone="UTC" --uri=$url --http-method=POST --oidc-service-account-email="fact-pacing-base-scheduler-invoker@adframework.iam.gserviceaccount.com"
```

Verificar:
```powershell
gcloud scheduler jobs describe fact-pacing-base-refresh-daily --project=adframework --location=southamerica-east1
```

---

## Parte C — Refresh manual (fallback, já existe, sem precisar de nada novo)

Sempre disponível, a qualquer momento, sem esperar o agendamento:
```powershell
python scripts/deploy/apply_ddl.py stg/ddl/fact_pacing_base_refresh.sql --env=prod --project adframework --reason "Refresh manual sob demanda" --summary "Refresh manual"
```
Confirmar: `fact_pacing_base`

(Ou, se estiver sem terminal de novo no futuro: `--confirmed-via-chat=fact_pacing_base` em vez de digitar interativamente, seguindo o mesmo protocolo de confirmação via AskUserQuestion já estabelecido.)

---

## Depois de tudo — commit final

```powershell
git add scripts/deploy/apply_ddl.py core/ddl/schema_change_log.sql gold/ddl/vw_fact_delivery_reporting.sql scripts/deploy/fact_pacing_base_scheduler/ hub/app.py hub/deploy.sh docs/PRODUCTION_RUNBOOK_override_2026-08-16.md
git commit -m "feat: promocao do mecanismo de override historico para producao + agendamento automatico de fact_pacing_base"
git push
```

Depois, atualizar a task Notion MÃE com o resultado real e apagar/arquivar este runbook.
