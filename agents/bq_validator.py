#!/usr/bin/env python3
"""
BQ Validator Agent — AdFramework
Agente Claude para auditoria e validação do pipeline BigQuery.

Como funciona:
    1. Você passa uma tarefa em linguagem natural
    2. Claude decide quais queries BQ rodar para validar
    3. Claude interpreta os resultados e reporta anomalias

Uso:
    python agents/bq_validator.py "valida Banco Cora Abril 2026"
    python agents/bq_validator.py "checa se RAW tem dados novos hoje em todas as plataformas"
    python agents/bq_validator.py "compara totais RAW vs STG vs GOLD para mediasmart"

Requisitos:
    pip install anthropic google-cloud-bigquery
    Variável de ambiente: ANTHROPIC_API_KEY=sk-ant-...
    GCP auth: gcloud auth application-default login
"""

import sys
import json
import anthropic
from google.cloud import bigquery

# ─────────────────────────────────────────────────────────────────────────────
# Clients
# ─────────────────────────────────────────────────────────────────────────────
bq_client = bigquery.Client(project="adframework")
claude    = anthropic.Anthropic()          # lê ANTHROPIC_API_KEY do ambiente

MODEL = "claude-sonnet-4-6"

# ─────────────────────────────────────────────────────────────────────────────
# System prompt — contexto do projeto que o agente recebe sempre
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM = """
Você é o BQ Validator, agente de auditoria do pipeline BigQuery AdFramework.
Projeto GCP: `adframework`.

## Arquitetura das camadas

| Camada  | Dataset   | Descrição                                                       |
|---------|-----------|----------------------------------------------------------------|
| RAW     | raw       | Ingestão crua das APIs — tipos nativos, sanitização mínima     |
| STG     | stg       | Normalização — snake_case, client_id resolvido, tipos corretos |
| GOLD    | gold      | Analítico — fact_delivery, fact_pacing, dim_campaign, fact_io_plan |
| CORE    | core      | Referência — dim_client, platform_client_links, campaign_format_map |

## Tabelas RAW principais
- `raw.mediasmart_delivery` — entregas MediaSmart (eventid = link para cliente)
- `raw.mgid_delivery`       — entregas MGID (campaignid = link para cliente)
- `raw.siprocal_delivery`   — entregas Siprocal (advertiser = link para cliente)

## Como client_id é atribuído (join key)
- MediaSmart : `core.platform_client_links` WHERE platform='mediasmart' → link_value = eventid
- MGID       : `core.platform_client_links` WHERE platform='mgid'       → link_value = campaignid
- Siprocal   : `core.platform_client_links` WHERE platform='siprocal'   → link_value = advertiser

## Clientes relevantes (exemplos)
- banco_cora_fe13d78a → Banco Cora (MGID Native + Push; MediaSmart Display/Retargeting/Video)
- tecpar_edfcc744     → TecPar
- luckbet_bea15ebc    → LuckBet

## Datasets PROTEGIDOS — nunca use em queries de modificação
pixel, adtracking, analytics, finops_billing

## Seu trabalho
Recebe uma tarefa de validação em linguagem natural e usa `run_bq_query` para:
1. Descobrir o estado atual (schemas, row counts, date ranges)
2. Comparar métricas entre camadas (RAW vs STG vs GOLD)
3. Identificar anomalias (dias faltando, clientes sem dados, totais divergentes)
4. Reportar em português de forma clara: o que está OK, o que está errado, o que precisa de ação

Regras de query:
- Sempre use nomes completos: `adframework.{dataset}.{tabela}`
- Prefira queries agregadas — evite SELECT * em tabelas grandes
- Use SAFE_CAST para tipos quando a tabela RAW pode ter strings
- Se não souber o schema de uma tabela, consulte INFORMATION_SCHEMA primeiro
"""

# ─────────────────────────────────────────────────────────────────────────────
# Tools — funções que o agente pode chamar
# ─────────────────────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "run_bq_query",
        "description": (
            "Executa uma query SQL no BigQuery (projeto adframework) e retorna os resultados. "
            "Use para inspecionar schemas, contar linhas, comparar métricas entre camadas, "
            "checar date ranges e identificar anomalias no pipeline. "
            "Retorna lista de dicts com os resultados, ou {'error': '...'} em caso de falha."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Query SQL a executar. Use nomes completos: `adframework.dataset.tabela`"
                },
                "description": {
                    "type": "string",
                    "description": "Uma linha descrevendo o que esta query está checando (aparece no log)"
                }
            },
            "required": ["sql", "description"]
        }
    }
]

# ─────────────────────────────────────────────────────────────────────────────
# Implementação da tool
# ─────────────────────────────────────────────────────────────────────────────
def run_bq_query(sql: str, description: str = "") -> list[dict]:
    print(f"  🔎 {description}")
    try:
        rows = list(bq_client.query(sql).result())
        return [dict(row) for row in rows]
    except Exception as e:
        return [{"error": str(e)}]

# ─────────────────────────────────────────────────────────────────────────────
# Agent loop — o coração do agente
#
# O loop funciona assim:
#   1. Enviamos a tarefa para Claude
#   2. Claude responde com tool_use (quer rodar uma query) ou end_turn (terminou)
#   3. Se tool_use: executamos a query, enviamos o resultado de volta para Claude
#   4. Claude analisa o resultado e decide se precisa de mais queries ou pode responder
#   5. Repetimos até end_turn
# ─────────────────────────────────────────────────────────────────────────────
def run_validator(task: str):
    print(f"\n{'─' * 60}")
    print(f"  Tarefa: {task}")
    print(f"{'─' * 60}\n")

    messages = [{"role": "user", "content": task}]

    while True:
        response = claude.messages.create(
            model=MODEL,
            max_tokens=8096,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )

        # Claude terminou — imprime a resposta final
        if response.stop_reason == "end_turn":
            print(f"\n{'─' * 60}")
            for block in response.content:
                if hasattr(block, "text"):
                    print(block.text)
            break

        # Claude quer usar uma tool — executamos e devolvemos o resultado
        if response.stop_reason == "tool_use":
            # Adiciona a resposta do Claude (com os tool_use blocks) ao histórico
            messages.append({"role": "assistant", "content": response.content})

            # Executa cada tool call e coleta os resultados
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = run_bq_query(
                        sql=block.input["sql"],
                        description=block.input.get("description", "query")
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str)
                    })

            # Devolve os resultados para Claude continuar
            messages.append({"role": "user", "content": tool_results})

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    run_validator(task)
