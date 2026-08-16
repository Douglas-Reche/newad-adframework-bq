# Protocolo de Ingestão Histórica — Banco Cora

> **Manutenção:** Tier 3 — atualizar só se a Cora mandar planilha nova (novo `upload_id`) ou se o mapeamento `historical_mappings/banco_cora_fe13d78a.py` mudar.

Registro técnico da ingestão do histórico manual da Cora em `stg.historical_overrides_delivery`, seguindo o "Protocolo de Análise Conjunta — 3 etapas" (`C:\Users\dougl\.claude\agents\historical-data-analyst.md`). Ponto de partida semântico para revisitar esta ingestão ou processar uma planilha nova do mesmo cliente. Discussão completa (o porquê de cada decisão) mora na task Notion "Desenhar override histórico por cliente" — este doc é só o marcador técnico enxuto.

- `client_id`: `banco_cora_fe13d78a`
- `upload_id`: `7b73b6f8-2456-44b5-8f2c-f28aa60675e7`
- Arquivo original: `cora override.xlsx`
- Mapeamento: `scripts/deploy/historical_mappings/banco_cora_fe13d78a.py`

## Etapa 1 — Estrutura bruta

1078 linhas, 17 colunas, range real `2026-01-07` a `2026-08-10` (agosto incompleto — 25 linhas NULL nos últimos 5 dias, lag de reporte). Grid dia×estratégia quase completo (só faltam `2026-08-01 DISPLAY`/`VÍDEO`). Sem duplicata de linha.

**Colunas:** `DIA, ESTRATÉGIA, IMPRESSÕES(+PROJETADAS+PACING), CPM(+PROJETADO), CLIQUES(+PROJETADOS+PACING), CPC(+PROJETADO), CTR(+PROJETADO), INVESTIMENTO(+PROJETADO+PACING)`.

**Achados de qualidade de dado:**
- **Bug de truncamento do Excel**: 113/1078 linhas de `IMPRESSÕES` e 86/1078 de `IMPRESSÕES PROJETADAS` vêm com valor cortado (ex: `"16.88"` em vez do valor real ~`16.880`). Quantificado: sem correção, subestima o total em ~10% (2,42M impressões no range usado). Correção `×1000` confirmada matematicamente certa (95/113 batem quase exato contra estimativa independente via `PACING`). `CLIQUES`/`INVESTIMENTO` e seus `PROJETADO` não têm esse bug.
- **23 linhas com bug de fórmula na origem**: `CPM`/`CPC = R$0,00` com impressão/investimento reais e positivos (célula de fórmula quebrada na planilha, não falta de entrega).
- `CPM`/`CPC` diretas na planilha confirmam `goal_type` linha a linha, sem discordância com `core.dict_format` em nenhuma das 1078 linhas.

## Etapa 2 — De/para de colunas (17 origem → schema `stg.historical_overrides_delivery`/`stg.fact_pacing_base`)

| origem | destino | regra |
|---|---|---|
| `DIA` | `day` | parse `DD/MM/YYYY` → ISO |
| `ESTRATÉGIA` | `formato` | normaliza (remove acento de `VÍDEO`) |
| `ESTRATÉGIA` (derivado) | `platform` | Display/Retargeting/Video→`mediasmart`; Native→`mgid`; Push→`siprocal` — via `core.dict_format`+`core.campaign_format_map` (dado real, não inferência; corrigiu suposição anterior errada de que Native seria `mediasmart`) |
| `ESTRATÉGIA` (derivado) | `goal_type` | Display/Retargeting/Video→CPM; Native/Push→CPC — via `core.dict_format` |
| `IMPRESSÕES` | `impressions` | `×1000` nas linhas com bug de truncamento |
| `CLIQUES` | `clicks` | direto |
| `INVESTIMENTO` | `investimento` | direto (BR→numérico) |
| `IMPRESSÕES PROJETADAS` | `planned_impressions_daily` | `×1000` no mesmo padrão de bug |
| `CLIQUES PROJETADOS` | `planned_clicks_daily` | direto |
| `INVESTIMENTO PROJETADO` | `planned_spend_daily` | direto |
| `CPM PROJETADO`/`CPC PROJETADO` | `unit_price` | qual das duas vier preenchida na linha |
| `PACING IMPRESSÕES/CLIQUES/INVESTIMENTO`, `CPM`, `CPC`, `CTR`, `CTR PROJETADO` | — | descartadas (derivadas/redundantes) |
| — | `conversions` | sempre `NULL` (fonte não tem essa dimensão) |
| — | `client_id` | constante `banco_cora_fe13d78a` |

**Tratamento das 23 linhas com bug de fórmula:** mantém o lado PLANEJADO da planilha; substitui só o lado REALIZADO (`impressions`, `clicks`, `investimento`) pelo dado real de `stg.fact_pacing_base` no mesmo dia+formato — evita criar buraco no pipeline (`core.resolve_reporting_source()` decide por dia inteiro do cliente, não por linha).

**Corte de data:** só até `2026-07-31` (decisão de negócio — 48 linhas de agosto descartadas por incompletude).

## Etapa 3 — Promoção e ativação

- `load_historical_override.py` (sem `--dry-run`) → **1030 linhas** em `stg.historical_overrides_delivery` (`douglas-bq-staging`). Σimpressions=23.831.592, Σclicks=95.941, Σinvestimento=R$378.486,74.
- `core.client_reporting_source_config`: ativado/desativado via toggle no Hub (aba Regras de Negócio) — controla se `resolve_reporting_source()` retorna `'override'` para esse cliente/período.
- `stg.fact_pacing_base` refrescado (automático desde 2026-08-12 ao usar o toggle do Hub) — `is_override=TRUE` confirmado nas linhas do período coberto quando ativo.
- Validado no Power BI pelo Douglas (2026-08-12).

## Pendência conhecida

Workbench intermediário (`douglas-bq-staging.stg_workbench`) desenhado no protocolo original nunca foi implementado — a promoção desta ingestão pulou direto de `normalize_historical_upload.py` (gera CSV local) para `load_historical_override.py`, sem etapa de rascunho em tabela BQ intermediária. Decisão consciente (2026-08-12, dado o prazo do dia), não bug.
