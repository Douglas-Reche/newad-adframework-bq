"""Mapeamento de normalizacao para client_id=teste_agente_backend_xyz.

Cliente FICTICIO de teste (nao e cliente real) -- criado para validar o
ciclo ponta-a-ponta raw -> normalize -> load em douglas-bq-staging (ver
scripts/deploy/normalize_historical_upload.py). Upload de referencia:
upload_id=39a0d9be-1ca8-4d41-b774-cc30489d2286, arquivo
fake_historico_teste.csv, 3 linhas, colunas de origem:
    "Data Ref", "Formato (PT)", "Investimento (R$)", "Cliques"

Armadilhas deliberadas nesse arquivo de teste (propositalmente incluidas
pra provar que a normalizacao trata cada uma):
  - "Data Ref": data no formato BR DD/MM/YYYY (ex: "01/07/2026"), nao ISO.
  - "Investimento (R$)": numero BR com milhar por "." e decimal por ","
    (ex: "1.234,56" -> 1234.56, nao 1.234 nem 1234,56).
  - "Formato (PT)": texto livre em portugues, sem padronizacao.

Colunas que a planilha de origem NAO tem (viram NULL no normalizado,
deliberadamente -- nao inventar valor):
  - platform: a planilha de teste nao informa a plataforma de origem.
  - goal_type, impressions, conversions: nao presentes na planilha de
    teste. NULL e o valor correto aqui (ausencia real de dado), nao 0 --
    0 impressoes seria uma afirmacao factual errada.
  - planned_impressions_daily, planned_clicks_daily, planned_spend_daily,
    unit_price: colunas adicionadas ao contrato em 2026-08-12 (ver
    REQUIRED_COLUMNS em load_historical_override.py) para o lado
    planejado -- este cliente de teste nao usa, sempre None.
"""

from datetime import datetime

# formato PT (texto livre, como vem na planilha) -> token normalizado.
# Mapeamento minimo so pra este cliente de teste -- nao e (e nao deve virar)
# um dicionario geral de formato: classificacao de formato entre
# plataformas/clientes e responsabilidade de core.dict_format /
# core.resolve_dict_format(), fora do escopo desta etapa (normalizacao é so
# "levar o dado bruto ao schema normalizado", nao aplicar regra de negocio
# de classificacao).
_FORMATO_PT_TO_TOKEN = {
    "Video Instream": "video_instream",
    "Display Banner": "display_banner",
    "Native": "native",
}


def _parse_data_ref(value: str) -> str:
    """'01/07/2026' -> '2026-07-01'. Falha alto se o formato nao bater --
    nao tenta adivinhar outro formato de data."""
    return datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()


def _parse_investimento_br(value: str) -> float:
    """'1.234,56' -> 1234.56 ; '987,00' -> 987.0 ; '10.500,75' -> 10500.75.
    Formato BR: '.' e separador de milhar, ',' e separador decimal."""
    cleaned = value.strip().replace(".", "").replace(",", ".")
    return float(cleaned)


def normalize(raw_rows: list[dict]) -> list[dict]:
    out = []
    for item in raw_rows:
        raw = item["raw_row"]
        row_number = item["row_number"]

        formato_pt = (raw.get("Formato (PT)") or "").strip()
        formato_token = _FORMATO_PT_TO_TOKEN.get(formato_pt)
        if formato_token is None:
            raise ValueError(
                f"[teste_agente_backend_xyz] row_number={row_number}: "
                f"'Formato (PT)'={formato_pt!r} nao esta no mapeamento "
                f"conhecido ({sorted(_FORMATO_PT_TO_TOKEN)}). Falhando alto "
                f"em vez de adivinhar -- adicione o valor novo a "
                f"_FORMATO_PT_TO_TOKEN se for legitimo."
            )

        out.append({
            "client_id": item["client_id"],
            "day": _parse_data_ref(raw["Data Ref"]),
            "platform": None,
            "formato": formato_token,
            "goal_type": None,
            "impressions": None,
            "clicks": float(raw["Cliques"]) if raw.get("Cliques") not in (None, "") else None,
            "investimento": _parse_investimento_br(raw["Investimento (R$)"]),
            "conversions": None,
            "planned_impressions_daily": None,
            "planned_clicks_daily": None,
            "planned_spend_daily": None,
            "unit_price": None,
            "source_file": item["source_filename"],
            "notes": (
                f"normalizado via historical_mappings/teste_agente_backend_xyz.py; "
                f"row_number={row_number}"
            ),
        })
    return out
