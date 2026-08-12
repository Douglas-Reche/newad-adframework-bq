"""Mapeamento de normalizacao para client_id=banco_cora_fe13d78a (Banco Cora).

Fonte: planilha "cora override.xlsx", upload_id=7b73b6f8-2456-44b5-8f2c-f28aa60675e7,
1078 linhas em douglas-bq-staging.raw.historical_uploads, 17 colunas (confirmado
ao vivo em raw.historical_uploads_meta para esse upload_id):
    DIA, ESTRATÉGIA, IMPRESSÕES, IMPRESSÕES PROJETADAS, PACING IMPRESSÕES,
    CPM, CPM PROJETADO, CLIQUES, CLIQUES PROJETADOS, PACING CLIQUES, CPC,
    CPC PROJETADO, CTR, CTR PROJETADO, INVESTIMENTO, INVESTIMENTO PROJETADO,
    PACING INVESTIMENTO.

Decisoes ja fechadas com o Douglas nesta sessao (Etapa 1 + Etapa 2 do
"Protocolo de Analise Conjunta", agente historical-data-analyst) -- este
arquivo so implementa, nao reabre nenhuma:

  - Corte de data: so linhas com DIA <= 2026-07-31 (inclusive) entram --
    linhas depois disso sao DESCARTADAS (nao e erro, so filtradas).
  - ESTRATEGIA (planilha) -> formato/platform/goal_type: mapeamento fechado,
    ver _ESTRATEGIA_TO_FORMATO / _FORMATO_TO_PLATFORM / _FORMATO_TO_GOAL_TYPE
    abaixo. platform confirmado por core.campaign_format_map (o range da
    planilha nao cobre a unica campanha Push em mgid, de dez/2025, fora do
    range <=31/07). goal_type confirmado por core.dict_format -- bate 100%
    com qual coluna CPM/CPC vem preenchida por linha na planilha.
  - Bug de truncamento em IMPRESSOES e IMPRESSOES PROJETADAS: valores no
    padrao regex ^\\d{1,3}\\.\\d{1,2}$ (ex: "16.88") estao truncados --
    confirmado matematicamente (95/113 casos batem quase exato com
    estimativa independente via pacing). Corrigidos multiplicando por 1000
    sempre que o padrao bater, sem excecao linha a linha (ver
    _TRUNCATED_RE / _parse_impressoes_like()).
  - Bug de formula CPM/CPC=0 (8 linhas conhecidas no momento da analise
    original, mas a deteccao aqui e GENERICA -- nao hardcoded por
    row_number): quando o campo realizado relevante pro formato da linha
    (CPM para Display/Retargeting/Video, CPC para Native/Push) vem
    "R$ 0,00" MAS a linha teve entrega real (impressoes corrigidas > 0 OU
    investimento > 0), a formula da planilha quebrou -- nao e falta de
    entrega real. Para essas linhas, `impressions`, `clicks` e
    `investimento` (o lado REALIZADO) sao substituidos pelo dado real
    equivalente em stg.fact_pacing_base (mesmo client_id, day, formato,
    platform -- ja materializada em douglas-bq-staging;
    realized_impressions / realized_clicks / investimento_realizado).

    NAO ESTENDIDO ao lado planejado (planned_impressions_daily/
    planned_clicks_daily/planned_spend_daily/unit_price) -- decisao tomada
    AQUI, na implementacao, nao fechada previamente com o Douglas, entao
    sinalizada de volta pro orquestrador/Douglas para confirmacao: o
    enunciado original dizia "nao confie nos valores da planilha nem pro
    lado realizado nem planejado", o que sugeriria trocar os 4 campos
    planejados tambem, mas so deu a formula de substituicao para os 3
    campos realizados. Verificado ao vivo (2026-08-12, day=2026-01-09,
    formato=Native) que stg.fact_pacing_base.planned_impressions_daily
    (10752.68) e MUITO diferente de IMPRESSOES PROJETADAS na planilha
    (14493) para o mesmo dia/formato -- sao metricas diferentes (planejado
    prorateado do IO Plan vs. meta declarada na planilha do cliente), nao
    substitutas intercambiaveis. Por isso os 4 campos planejados desta
    linha continuam vindo da propria planilha (com a correcao de
    truncamento aplicada quando o padrao bater), e so os 3 campos
    REALIZADOS sao trocados, exatamente como a formula de substituicao
    literal do enunciado descreve.

Requer acesso a BigQuery (douglas-bq-staging) durante normalize() -- diferente
do exemplo teste_agente_backend_xyz.py, que e uma funcao pura. Necessario
para resolver as linhas do bug de formula contra stg.fact_pacing_base. Usa
Application Default Credentials, mesmo padrao dos scripts irmaos. O import
do bigquery e feito sob demanda (so quando alguma linha realmente precisa),
para nao pagar o custo/latencia de uma query numa planilha sem nenhuma linha
com o bug.
"""

from __future__ import annotations

import re
from datetime import date, datetime

CLIENT_ID = "banco_cora_fe13d78a"

# Corte de data aprovado -- linhas com DIA > isso sao descartadas (nao erro).
CUTOFF_DATE = date(2026, 7, 31)

FACT_PACING_BASE_PROJECT = "douglas-bq-staging"
FACT_PACING_BASE_TABLE = f"{FACT_PACING_BASE_PROJECT}.stg.fact_pacing_base"

_ESTRATEGIA_TO_FORMATO = {
    "DISPLAY": "Display",
    "VÍDEO": "Video",
    "RETARGETING": "Retargeting",
    "NATIVE": "Native",
    "PUSH": "Push",
}

_FORMATO_TO_PLATFORM = {
    "Display": "mediasmart",
    "Retargeting": "mediasmart",
    "Video": "mediasmart",
    "Native": "mgid",
    "Push": "siprocal",
}

_FORMATO_TO_GOAL_TYPE = {
    "Display": "CPM",
    "Retargeting": "CPM",
    "Video": "CPM",
    "Native": "CPC",
    "Push": "CPC",
}

# Padrao do bug de truncamento -- ver docstring do modulo. So bate em valores
# tipo "16.88" (1-3 digitos, ponto, 1-2 digitos) -- um valor legitimo com
# separador de milhar tipo "2.737" ou "45.504" (3 digitos apos o ponto) nao
# bate, entao nao sofre a correcao.
_TRUNCATED_RE = re.compile(r"^\d{1,3}\.\d{1,2}$")

_ZERO_BR = "R$ 0,00"


def _parse_dia(value: str, row_number: int) -> date:
    """'07/01/2026' -> date(2026, 1, 7). Falha alto se o formato nao bater --
    nao tenta adivinhar outro formato de data."""
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except Exception as exc:
        raise ValueError(
            f"[banco_cora_fe13d78a] row_number={row_number}: 'DIA'={value!r} "
            f"nao parseia como DD/MM/YYYY."
        ) from exc


def _parse_br_number(value):
    """'R$ 1.234,56' -> 1234.56 ; '987,00' -> 987.0 ; '44' -> 44.0.
    Formato BR: '.' e separador de milhar, ',' e separador decimal. NAO usar
    para IMPRESSOES/IMPRESSOES PROJETADAS -- essas tem o bug de truncamento
    tratado a parte em _parse_impressoes_like()."""
    if value is None:
        return None
    v = value.strip()
    if v == "":
        return None
    if v.startswith("R$"):
        v = v[2:].strip()
    v = v.replace(".", "").replace(",", ".")
    return float(v)


def _parse_impressoes_like(value):
    """Aplica a correcao do bug de truncamento (ver docstring do modulo)
    quando o valor bate no padrao ^\\d{1,3}\\.\\d{1,2}$ (ex: '16.88' ->
    16880.0, multiplicado por 1000). Caso contrario, parse BR normal
    (separador de milhar '.', sem parte decimal esperada para contagem de
    impressoes)."""
    if value is None:
        return None
    v = value.strip()
    if v == "":
        return None
    if _TRUNCATED_RE.match(v):
        return float(v) * 1000
    return _parse_br_number(v)


def _fetch_fact_pacing_base_lookup() -> dict:
    """Busca todas as linhas de stg.fact_pacing_base para banco_cora_fe13d78a
    e monta um lookup (day_iso, formato, platform) -> row. Usado SO pelas
    linhas com o bug de formula CPM/CPC=0 (ver docstring do modulo) -- uma
    unica query para o cliente inteiro, em vez de uma query por linha
    afetada."""
    from google.cloud import bigquery

    client = bigquery.Client(project=FACT_PACING_BASE_PROJECT)
    query = f"""
        SELECT day, formato, platform, realized_impressions, realized_clicks,
               investimento_realizado
        FROM `{FACT_PACING_BASE_TABLE}`
        WHERE client_id = @client_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("client_id", "STRING", CLIENT_ID)]
    )
    lookup = {}
    for r in client.query(query, job_config=job_config).result():
        lookup[(r.day.isoformat(), r.formato, r.platform)] = r
    return lookup


def normalize(raw_rows: list[dict]) -> list[dict]:
    out = []
    fact_pacing_lookup = None  # so carregado sob demanda (ver abaixo)

    for item in raw_rows:
        raw = item["raw_row"]
        row_number = item["row_number"]

        day = _parse_dia(raw["DIA"], row_number)
        if day > CUTOFF_DATE:
            continue  # fora do range aprovado -- descarte silencioso, nao erro

        estrategia = (raw.get("ESTRATÉGIA") or "").strip().upper()
        formato = _ESTRATEGIA_TO_FORMATO.get(estrategia)
        if formato is None:
            raise ValueError(
                f"[banco_cora_fe13d78a] row_number={row_number}: "
                f"'ESTRATÉGIA'={estrategia!r} nao esta no mapeamento fechado "
                f"({sorted(_ESTRATEGIA_TO_FORMATO)}). Falhando alto em vez de "
                f"adivinhar -- confirmar com o Douglas se for um valor novo "
                f"legitimo."
            )
        platform = _FORMATO_TO_PLATFORM[formato]
        goal_type = _FORMATO_TO_GOAL_TYPE[formato]

        impressions = _parse_impressoes_like(raw.get("IMPRESSÕES"))
        planned_impressions_daily = _parse_impressoes_like(raw.get("IMPRESSÕES PROJETADAS"))
        clicks = _parse_br_number(raw.get("CLIQUES"))
        planned_clicks_daily = _parse_br_number(raw.get("CLIQUES PROJETADOS"))
        investimento = _parse_br_number(raw.get("INVESTIMENTO"))
        planned_spend_daily = _parse_br_number(raw.get("INVESTIMENTO PROJETADO"))

        if goal_type == "CPM":
            unit_price = _parse_br_number(raw.get("CPM PROJETADO"))
            active_realized_raw = raw.get("CPM")
        else:
            unit_price = _parse_br_number(raw.get("CPC PROJETADO"))
            active_realized_raw = raw.get("CPC")

        notes = None
        is_formula_bug = (active_realized_raw or "").strip() == _ZERO_BR and (
            (impressions or 0) > 0 or (investimento or 0) > 0
        )
        if is_formula_bug:
            if fact_pacing_lookup is None:
                fact_pacing_lookup = _fetch_fact_pacing_base_lookup()
            key = (day.isoformat(), formato, platform)
            fpb_row = fact_pacing_lookup.get(key)
            if fpb_row is None:
                raise ValueError(
                    f"[banco_cora_fe13d78a] row_number={row_number}: linha com "
                    f"bug de formula CPM/CPC=0 (day={day}, formato={formato}, "
                    f"platform={platform}) mas nao existe linha equivalente em "
                    f"stg.fact_pacing_base para substituir o dado -- nao da pra "
                    f"confiar no valor da planilha nem inventar um. Investigar "
                    f"manualmente antes de rodar a normalizacao deste upload de "
                    f"novo."
                )
            impressions = fpb_row.realized_impressions
            clicks = fpb_row.realized_clicks
            investimento = fpb_row.investimento_realizado
            notes = (
                "linha com bug de formula CPM/CPC=0 na planilha original -- "
                "valores substituidos pelo dado real da plataforma "
                "(stg.fact_pacing_base)"
            )

        out.append({
            "client_id": CLIENT_ID,
            "day": day.isoformat(),
            "platform": platform,
            "formato": formato,
            "goal_type": goal_type,
            "impressions": impressions,
            "clicks": clicks,
            "investimento": investimento,
            "conversions": None,
            "planned_impressions_daily": planned_impressions_daily,
            "planned_clicks_daily": planned_clicks_daily,
            "planned_spend_daily": planned_spend_daily,
            "unit_price": unit_price,
            "source_file": item["source_filename"],
            "notes": notes,
        })

    return out
