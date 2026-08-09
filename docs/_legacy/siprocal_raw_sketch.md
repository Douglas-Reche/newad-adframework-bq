# Siprocal — RAW Layer Sketch

> Status: ⚠️ SUPERADO em 2026-06-22 — ver `raw_layer_design.md` (seção Siprocal) e `CHANGELOG.md` (entrada 2026-06-22) para a decisão vigente.
> Criado em: 2026-06-18
> Metodologia original: análise do Google Sheets `raw daily` (1093 linhas, 2025-08-22 → 2026-06-11) — **sem confirmar os headers reais**.
>
> **O que mudou:** este sketch assumia headers `PI Externo` e `Campanha` na planilha. O header real (confirmado em 22/06 via planilha ao vivo) é `Coluna 1, Data, Campanha, Criativo, Impressions, Clicks, CTR` — `"Coluna 1"` é o `pi_externo`, mas com nome genérico. O aliasing assumido aqui (`PI Externo → campaign_id`) nunca batia, e causava perda silenciosa de dado em produção (`campaign_id` vinha vazio em 100% das linhas).
>
> **Decisão vigente:** RAW passou a ser o dump literal da planilha (`raw.sp_delivery`, implementado e validado — 1121 linhas). T1 (`sp_clients`) e T2 (`sp_campaigns`) descritos abaixo **não serão implementados como tabelas separadas** — `client_name` e `campaign_id` são derivados na STG a partir de `sp_delivery.campanha`, mesmo princípio adotado para o MGID. O conteúdo abaixo permanece como referência da lógica de parse (2º segmento = cliente, sufixo = período), que ainda é válida para a STG — só o ponto de execução mudou (STG, não ingestão RAW).

---

## O que é a Siprocal

Siprocal é uma rede de publicidade programática que entrega dados via **arquivo flat no Google Sheets** — sem API própria no momento. Não há separação de catálogo vs analytics: tudo vem em uma única planilha com uma linha por dia/campanha/criativo.

Diferenças críticas vs MediaSmart e MGID:

| | MediaSmart | MGID | Siprocal |
|---|---|---|---|
| Fonte | API REST | API REST | Google Sheets |
| Catálogo separado | Sim | Sim | Não |
| ID de cliente estável | Sim | Sim | Não (`pi_externo` muda por período) |
| Dados financeiros | Sim | Sim | Não |
| Breakdowns | 9 dimensões | 7 dimensões | Nenhum |
| Métricas principais | 80+ KPIs | ~30 KPIs | 3 (impressions, clicks, ctr) |

---

## Estrutura geral

```
CATÁLOGO (derivado do flat file)    ANALYTICS
────────────────────────────────    ─────────
T1. sp_clients                      T3. sp_delivery    ← único fato
T2. sp_campaigns
```

**Como as tabelas se conectam:**
- `T2.client_id` → `T1.client_id` (via `pi_externo`)
- `T3.campaign_id` → `T2.campaign_id` (via nome normalizado)
- `T3.client_id` → `T1.client_id`
- O vínculo `client_id` → `newad_client_id` acontece na gold via tabela de mapeamento

---

## CATÁLOGO

---

### T1 — `sp_clients`

**Fonte:** Google Sheets `raw daily` — extraído das colunas `PI Externo` + `Campanha`
**Grain:** 1 linha por `pi_externo` distinto
**Ingestão:** diária — full refresh

> **Nota de design:** `pi_externo` não é um ID estável por cliente — muda por campanha/período (ex: Luckbet aparece como 10, 14, NW0825 em meses diferentes). O mapeamento para `newad_client_id` é feito na gold. `client_name` é extraído do nome da campanha via padrão `NEWAD_{CLIENTE}_{PAIS}_{PERIODO}`.

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `client_id` | STRING | `pi_externo` — ID nativo Siprocal, instável por período | `10` / `NW0825` |
| `client_name` | STRING | Parseado do nome de campanha (2º segmento) | `LUCKBET` |
| `category` | STRING | **Não existe na Siprocal** | `null` |
| `platform` | STRING | Identificador da plataforma | `siprocal` |

#### Código de ingestão planejado

```python
def ingest_sp_clients(sheets_client, bq_client, spreadsheet_id: str):
    # 1. ler planilha completa
    raw_rows = sheets_client.read_sheet(spreadsheet_id, sheet="raw daily")

    # 2. extrair pares distintos pi_externo + campanha
    seen = {}
    for row in raw_rows:
        pi = str(row["PI Externo"]).strip()
        campaign = str(row["Campanha"]).strip()
        if pi not in seen:
            seen[pi] = campaign  # mantém a primeira ocorrência

    # 3. derivar client_name do nome de campanha
    # padrão: NEWAD_{CLIENTE}_{PAIS}_{PERIODO}
    rows = []
    for pi, campaign_name in seen.items():
        parts = campaign_name.upper().split("_")
        client_name = parts[1] if len(parts) >= 2 else campaign_name

        rows.append({
            "client_id":   pi,
            "client_name": client_name,
            "category":    None,        # não existe na Siprocal
            "platform":    "siprocal",
            "ingested_at": datetime.utcnow().isoformat(),
        })

    # catálogo — full refresh diário
    bq_client.load_table("raw.sp_clients", rows, write_disposition="WRITE_TRUNCATE")
```

---

### T2 — `sp_campaigns`

**Fonte:** Google Sheets `raw daily` — extraído da coluna `Campanha`
**Grain:** 1 linha por nome de campanha distinto
**Ingestão:** diária — full refresh

> **Nota de design:** Siprocal não tem `campaign_id` nativo. O campo `campaign_id` é derivado do nome normalizado (`UPPER + espaços → _`). `start_date` e `end_date` são parseados do sufixo do nome (`SET25` → 2025-09-01 / 2025-09-30). Sujeito a revisão após reunião com Siprocal.

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `campaign_id` | STRING | Nome normalizado — ID derivado, sem nativo | `NEWAD_LUCKBET_BR_SET25` |
| `campaign_name` | STRING | Nome original da campanha | `NEWAD_LUCKBET_BR_SET25` |
| `client_id` | STRING | `pi_externo` — FK → `sp_clients.client_id` | `10` |
| `start_date` | DATE | Início do período parseado do nome | `2025-09-01` |
| `end_date` | DATE | Fim do período parseado do nome | `2025-09-30` |
| `country` | STRING | País parseado do nome (3º segmento) | `BR` |

#### Código de ingestão planejado

```python
MONTH_MAP = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}

def parse_period(period_str: str):
    """SET25 → (date(2025,9,1), date(2025,9,30))"""
    import calendar
    try:
        month_abbr = period_str[:3].upper()
        year = int("20" + period_str[3:5])
        month = MONTH_MAP.get(month_abbr)
        if not month:
            return None, None
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
    except Exception:
        return None, None


def ingest_sp_campaigns(sheets_client, bq_client, spreadsheet_id: str):
    raw_rows = sheets_client.read_sheet(spreadsheet_id, sheet="raw daily")

    seen = {}
    for row in raw_rows:
        campaign_name = str(row["Campanha"]).strip()
        pi = str(row["PI Externo"]).strip()
        campaign_id = campaign_name.upper().replace(" ", "_")
        if campaign_id not in seen:
            seen[campaign_id] = (campaign_name, pi)

    rows = []
    for campaign_id, (campaign_name, pi) in seen.items():
        parts = campaign_id.split("_")
        # padrão: NEWAD_{CLIENTE}_{PAIS}_{PERIODO}
        country = parts[3] if len(parts) >= 4 else None
        period  = parts[4] if len(parts) >= 5 else (parts[3] if len(parts) == 4 else None)
        start_date, end_date = parse_period(period) if period else (None, None)

        rows.append({
            "campaign_id":   campaign_id,
            "campaign_name": campaign_name,
            "client_id":     pi,            # FK → sp_clients.client_id
            "start_date":    start_date.isoformat() if start_date else None,
            "end_date":      end_date.isoformat() if end_date else None,
            "country":       country,
            "platform":      "siprocal",
            "ingested_at":   datetime.utcnow().isoformat(),
        })

    bq_client.load_table("raw.sp_campaigns", rows, write_disposition="WRITE_TRUNCATE")
```

---

## ANALYTICS

---

### T3 — `sp_delivery`

**Fonte:** Google Sheets `raw daily` — todas as linhas
**Grain:** 1 linha por `date` + `campaign` + `creative`
**Ingestão:** diária incremental (por data)

| Campo | Tipo | O que é | Exemplo |
|---|---|---|---|
| `date` | DATE | Data de entrega | `2025-09-15` |
| `campaign_id` | STRING | FK → `sp_campaigns.campaign_id` | `NEWAD_LUCKBET_BR_SET25` |
| `client_id` | STRING | FK → `sp_clients.client_id` | `10` |
| `creative` | STRING | Label de segmento do criativo | `Apps` / `No Apps` / `N/A` |
| `impressions` | INT | Total de impressões | `120000` |
| `clicks` | INT | Total de cliques | `850` |
| `ctr` | FLOAT | CTR (derivado — clicks/impressions) | `0.0071` |

> **Nota:** CTR vem da planilha mas é derivado — sempre recalcular no STG para consistência.
> **Não existe:** spend, CPM, CPC, receita, conversões, geo, device, hora.
