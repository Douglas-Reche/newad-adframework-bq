"""Mapeamento de normalizacao para client_id=casa_construtor_adf15c2c
(Casa do Construtor) -- formato Audio, dado de entrega/realizado (nao IO
Plan -- isso e outra fonte, ja resolvida).

Fonte: bloco "Daily Breakdown" da aba "Áuido" (grafia com typo no arquivo
original, nao e erro de leitura) de
RParcial_CasaDoConstrutor_Aluga_Agosto_Áudio (1).xlsx, Google Drive pasta
"DASHBOARD" da Casa do Construtor (folder_id
1A1p-ubmIgEcLklfs10hRWvWQADyrvEl-, file_id
1Xw05BMLH0FWpAW0JKOyUd83jDyI09Owu confirmado 2026-09-07).

REDESENHO 2026-09-07 (2 mudancas de arquitetura confirmadas com o Douglas,
sobre a carga unica construida mais cedo no mesmo dia -- upload_id=
7913421f-0555-4849-b404-f408ace949e3, 23 linhas em
douglas-bq-staging.stg.historical_overrides_delivery):

  1. Preservar TARGET 01/TARGET 02 no realizado (nao so o total blended) --
     porque o IO Plan tem Target 1/Target 2 como valores REAIS e diferentes
     (R$25k/50k impressoes Target 1, R$10k/20k Target 2), e o Douglas quer
     poder comparar planejado x realizado por target. Ver `normalize()`
     abaixo -- emite 3 linhas por dia (blended + 2 targets), usando a nova
     coluna `target_group` (stg/ddl/historical_overrides_delivery.sql).
  2. Extracao direta do xlsx via `extract_daily_breakdown()` -- elimina o
     passo manual de pre-processamento (CSV extraido a mao, ver historico
     git deste arquivo) para permitir reprocessamento automatico/recorrente
     (scripts/deploy/sync_historical_drive.py) sempre que o arquivo do
     Drive mudar (campo modifiedTime, mesmo padrao de scripts/io_plan/
     sync_drive.py).

Estrutura confirmada ao vivo em 2026-09-07 (baixando o arquivo real do
Drive): aba "Áuido" com metadado de flight linhas 1-7, "Topline
Performance" linhas 10-11, "Weekly Breakdown" linhas 13-18, marcadores
'TARGET 01'/'TARGET 02' na linha 19 (colunas H e K), header "Daily
Breakdown" na linha 20, dados diarios linhas 21-N ate a linha "Total" que
fecha o bloco. Colunas A-E = total blended (Date, Started Listens,
Completed Listens, LTR %, Spend); coluna F em branco (spacer); colunas G-I
= bloco Target 01 (Date repetido, Started Listens, Completed Listens);
coluna J em branco (spacer); colunas K-L = bloco Target 02 (Started
Listens, Completed Listens, sem coluna Date propria -- usa a data do bloco
blended). Aba "_InternalCache" (7 linhas de marco/2026 com
Impressions/CTR/clicks -- periodo e colunas que nao tem nada a ver com
Audio, contaminacao confirmada) ignorada.

`extract_daily_breakdown()` NAO hardcoda numero de linha/coluna -- localiza
o header "Daily Breakdown" dinamicamente e segmenta colunas em blocos
(blended vs TARGET N) por coluna-spacer + marcador da linha acima, mesmo
espirito de _find_next_block()/_map_headers() em scripts/io_plan/
sync_drive.py -- tolera pequenas mudancas de layout mes a mes (linhas a
mais/a menos no Weekly Breakdown, por exemplo) sem quebrar, mas ainda falha
alto se a estrutura mudar de verdade (bloco "Daily Breakdown" sumir, por
exemplo -- nunca adivinha).

Decisoes desta normalizacao (Etapa 1+2 do protocolo, algumas AINDA
pendentes de confirmacao do Douglas -- ver avisos abaixo, nao decididas
sozinho):

  - Grain de saida: ALTERADO nesta revisao. Antes so o bloco TOTAL
    alimentava stg.historical_overrides_delivery; agora normalize() emite 3
    linhas por dia -- 1 com target_group=NULL (total blended, o mesmo de
    antes) + 1 com target_group='TARGET 01' + 1 com target_group='TARGET 02'.
    Os valores de TARGET 01/02 continuam sendo um RATEIO PROPORCIONAL
    sintetico (nao contagem independente real -- confirmado: sao
    fracionarios, ex: 525.7248 "escutas iniciadas" no TARGET 01 do dia
    10/08, e a SOMA TARGET01+TARGET02 bate exatamente com o TOTAL blended
    em toda linha verificada) -- por isso as linhas de target NUNCA
    alimentam gold.fact_delivery/stg.fact_pacing_base (que filtram
    target_group IS NULL explicitamente, ver stg/ddl/
    historical_overrides_delivery.sql) -- existem so para auditoria/consulta
    manual comparando contra o planejado por target do IO Plan. NAO existe
    Spend por target nesta planilha -- investimento fica None nas linhas de
    target (só a linha blended tem investimento preenchido, o dinheiro so
    existe no nivel agregado).
  - Corte de linhas sem dado real: dias com Started/Completed
    Listens/LTR/Spend BLENDED vazios (None) mesmo com o split por TARGET
    mostrando explicitamente 0 -- achado de qualidade de dado (blended
    vazio != 0, e o dado por target mostra 0 onde o blended nao tem nada,
    inconsistencia dentro da propria planilha, confirmado nos dias
    2026-09-02 a 2026-09-09 do arquivo de agosto). Tratado como "sem dado
    reportado ainda" -- as 3 linhas desse dia (blended + 2 targets) sao
    descartadas juntas (nao substituidas por 0), mesmo criterio de "falha
    alto/descarta em vez de inventar" do resto do pipeline.
  - impressions <- "Started Listens" (Total ou por target conforme a
    linha): mesma equivalencia ja usada pelo Google Sheet "DASH" (confirmado
    numericamente na investigacao anterior, 24/02/2026: DASH mostra 12.737
    IMPRESSOES = Escutas Iniciadas do RFinal fev/2026). Confianca MEDIA --
    e uma convencao ja em uso no negocio, mas semanticamente "Started
    Listens" != impressao de display tradicional; nao decidido por este
    agente que essa equivalencia esta correta pra sempre, so que e a que ja
    esta em uso.
  - clicks / conversions: sempre None, em toda linha (blended ou target).
    Audio nao tem clique de verdade (Completed Listens e LTR% sao metricas
    de qualidade especificas de audio, sem destino no schema atual de 4
    colunas-alvo (realized_impressions/clicks/conversions +
    investimento_realizado) -- ficam de fora, nao viram coluna nova sem
    necessidade.
  - investimento <- "Spend" (so na linha blended, None nas linhas de
    target -- ver "Grain de saida" acima): alta confianca (unidade R$, sem
    ambiguidade de escala observada).
  - planned_* / unit_price: sempre None, em toda linha. IO Plan da Casa do
    Construtor tem linhas reais de "Áudio Ads" (confirmado em stg.io_plan)
    mas o lado planejado deste override especificamente fica de fora por
    decisao ja fechada do Douglas (2026-08-11, ver docstring de
    banco_cora_fe13d78a): planned_* SEMPRE vem do IO Plan real via
    gold.fact_io_plan, nunca do override.
  - formato = "Áudio" -- bate com core.dict_format/core.strategy_format_map
    (keyword 'áudio'/'audio' inserido em staging nesta mesma sessao, antes
    disso "Áudio Ads" caia em formato=NULL em stg.io_plan).

AVISOS -- decisoes tomadas para DESTRAVAR a normalizacao, NAO fechadas com
o Douglas, PRECISAM de confirmacao antes de promover pra producao
-----------------------------------------------------------------------
  1. platform = "unknown" (nao NULL). Motivo: a decisao real (MiQ vs
     Adsmovil) esta pendente (task Notion "Ingestao de dado de Audio --
     Casa do Construtor", ainda "Waiting" em 2026-09-07). O enunciado desta
     task pediu para nao bloquear por causa disso, no mesmo padrao ja
     usado para Push nesse cliente (que tambem convive com platform=
     "unknown" em gold.fact_io_plan hoje). MAS "unknown" NAO estava na
     lista fechada VALID_PLATFORMS de historical_mappings/__init__.py
     ({"mediasmart","mgid","siprocal"}) -- essa lista foi ESTENDIDA para
     incluir "unknown" nesta mesma sessao (ver __init__.py) para permitir
     isso. Essa extensao afeta a validacao de QUALQUER client_id daqui pra
     frente, nao so este -- decisao tomada para viabilizar a task conforme
     instruido, mas de impacto compartilhado, reportada explicitamente
     para o Douglas confirmar.
  2. platform = "unknown" tambem foi escolhido (em vez de NULL) por um
     motivo TECNICO alem do de negocio: stg.fact_pacing_base_refresh.sql
     faz JOIN entre a linha do override e a linha de gold.fact_io_plan/
     fact_delivery usando UPPER(ov.platform) = UPPER(j.platform) -- e
     gold.fact_io_plan JA emite platform="unknown" para a estrategia real
     "Áudio Ads" da Casa do Construtor (confirmado ao vivo). Se o override
     usasse platform=NULL, o JOIN NUNCA bateria (NULL != 'unknown' em
     SQL), e is_override ficaria TRUE mas os valores restariam vazios --
     um bug silencioso pior do que a falta de confirmacao de negocio. Ver
     achado maior sobre isso abaixo.
  3. goal_type = "CPM" (baixa/media confianca, NAO confirmado). Nao existe
     coluna CPM/CPC direta em nenhum arquivo de Audio (diferente da Cora).
     Em core.dict_format ja fechado nesta sessao para (platform=unknown,
     formato=Áudio) com goal_type=CPM -- mas o proprio stg.io_plan mostra
     buy_model="CPE" pra esta estrategia (nao "CPM"/"CPC"/"CPI" -- um
     buy_model que nao existe na taxonomia hoje). CPM foi a aproximacao
     mais defensavel (preco parece impression-based), NAO uma confirmacao
     comercial. Nao afeta o valor de investimento carregado aqui (vem
     direto de "Spend", nunca da formula CPM/CPC), mas afeta como o dado e
     rotulado/lido depois.

ACHADO MAIOR -- fora do escopo deste arquivo, reportado para o
orquestrador/Douglas, NAO resolvido aqui
-----------------------------------------------------------------------
stg/ddl/fact_pacing_base_refresh.sql constroi a tabela a partir de um FULL
OUTER JOIN entre gold.fact_io_plan (planejado) e gold.fact_delivery
(realizado via conector automatico) -- stg.historical_overrides_delivery
so e lido depois, via LEFT JOIN sobre o resultado desse FULL OUTER JOIN.
Isso significa: se NAO existir NENHUMA linha em fact_io_plan OU
fact_delivery para (client_id, day, formato, platform), a linha do
override NUNCA aparece em stg.fact_pacing_base, nao importa o que for
carregado aqui. Para a Casa do Construtor + Áudio isso quase aconteceu --
fact_delivery nunca teria uma linha (nenhum conector real existe pra
Audio) e fact_io_plan so passou a ter uma linha PORQUE o seed de
strategy_format_map (keyword audio/áudio) foi aplicado nesta mesma sessao
(sem isso, "Áudio Ads" ficava com formato=NULL em stg.io_plan/
gold.fact_io_plan pra sempre, e o override carregado aqui simplesmente
NUNCA apareceria em fact_pacing_base -- um bug silencioso, sem erro
nenhum, so ausencia). Diferente de banco_cora_fe13d78a, onde o override so
CORRIGIA dias que ja tinham linha real em fact_delivery -- aqui o override
e a UNICA fonte de dado realizado, entao depender do lado "planejado" ja
ter uma linha coincidente e uma fragilidade estrutural de
fact_pacing_base_refresh.sql que vale generalizar/revisar (fora do escopo
deste agente -- e SQL compartilhado por todos os clientes, nao so Casa do
Construtor).
"""

from __future__ import annotations

import re
from datetime import date, datetime

CLIENT_ID = "casa_construtor_adf15c2c"
FORMATO = "Áudio"
PLATFORM = "unknown"  # PENDENTE -- ver AVISO 1/2 acima
GOAL_TYPE = "CPM"  # PENDENTE -- ver AVISO 3 acima

# Nomes de coluna do contrato raw_row (raw.historical_uploads.raw_row) --
# fixos, independente de vir do CSV pre-extraido manualmente (fluxo antigo)
# ou de extract_daily_breakdown() (fluxo novo, direto do xlsx). Mantido como
# constante para os dois caminhos nunca divergirem.
COL_DATE = "Date"
COL_IMP_TOTAL = "Started Listens (Total)"
COL_COMPLETED_TOTAL = "Completed Listens (Total)"
COL_LTR_TOTAL = "LTR % (Total)"
COL_SPEND_TOTAL = "Spend (Total)"
COL_IMP_T1 = "Started Listens (Target 01)"
COL_COMPLETED_T1 = "Completed Listens (Target 01)"
COL_IMP_T2 = "Started Listens (Target 02)"
COL_COMPLETED_T2 = "Completed Listens (Target 02)"


# ─── Extracao direta do xlsx (2026-09-07) ──────────────────────────────────
# Substitui o pre-processamento manual (CSV extraido a mao) da versao
# anterior deste arquivo -- permite scripts/deploy/sync_historical_drive.py
# baixar o xlsx do Drive e chamar isto diretamente, sem passo manual.

_TARGET_MARKER_RE = re.compile(r"^TARGET\s*\d+$", re.IGNORECASE)
_DAILY_BREAKDOWN_RE = re.compile(r"^daily\s+breakdown$", re.IGNORECASE)

# Header label (deaccented, lowercased, substring match) -> chave logica.
_HEADER_KEYWORDS = {
    "date": "date",
    "started listens": "started",
    "completed listens": "completed",
    "ltr": "ltr",
    "spend": "spend",
}


def _deaccent(text: str) -> str:
    result = str(text).strip().lower()
    for fr, to in [("á", "a"), ("à", "a"), ("â", "a"), ("ã", "a"), ("é", "e"), ("ê", "e"),
                   ("í", "i"), ("ó", "o"), ("ô", "o"), ("õ", "o"), ("ú", "u"), ("ç", "c")]:
        result = result.replace(fr, to)
    return result


def _find_header_row(ws, max_scan_row: int = 200):
    """Procura a linha cujo valor da coluna A e 'Daily Breakdown'
    (case-insensitive). Retorna o numero da linha, ou None se nao achar
    (falha alto no chamador -- ver extract_daily_breakdown)."""
    for row in ws.iter_rows(min_row=1, max_row=min(max_scan_row, ws.max_row)):
        cell_a = row[0].value
        if cell_a and _DAILY_BREAKDOWN_RE.match(str(cell_a).strip()):
            return row[0].row
    return None


def _segment_blocks(ws, header_row: int):
    """A partir da linha de header (ex: linha 20, colunas A-E=blended,
    F=spacer, G-I=TARGET 01, J=spacer, K-L=TARGET 02), segmenta as colunas
    preenchidas em blocos separados por coluna(s) vazia(s), e associa cada
    bloco a um target_group (None para o bloco blended) lendo os marcadores
    'TARGET N' da linha imediatamente acima do header.

    Retorna lista de dicts: [{"target_group": None|"TARGET 01", "cols":
    {"date": col_idx|None, "started": col_idx, "completed": col_idx|None,
    "ltr": col_idx|None, "spend": col_idx|None}}, ...].
    """
    marker_row_num = header_row - 1
    header_cells = list(ws.iter_rows(min_row=header_row, max_row=header_row))[0]
    marker_cells = list(ws.iter_rows(min_row=marker_row_num, max_row=marker_row_num))[0] if marker_row_num >= 1 else []

    max_col = ws.max_column
    # 1) Agrupa colunas preenchidas (header nao-vazio) em blocos contiguos.
    filled_cols = [c.column for c in header_cells if c.value not in (None, "")]
    blocks_cols = []
    current = []
    prev_col = None
    for col in sorted(filled_cols):
        if prev_col is not None and col > prev_col + 1:
            blocks_cols.append(current)
            current = []
        current.append(col)
        prev_col = col
    if current:
        blocks_cols.append(current)

    # 2) Para cada bloco, mapeia label->chave logica e detecta target_group
    #    olhando os marcadores da linha acima dentro do range de colunas do
    #    bloco (com folga de +1 pra pegar o caso do marcador ficar alinhado
    #    com a 1a coluna de metrica do bloco, nao a coluna de data).
    blocks = []
    for block_index, cols in enumerate(blocks_cols):
        col_map = {}
        for col in cols:
            label = header_cells[col - 1].value
            if not label:
                continue
            norm = _deaccent(label)
            for kw, key in _HEADER_KEYWORDS.items():
                if kw in norm and key not in col_map:
                    col_map[key] = col

        # 'date': o bloco blended (o primeiro, mais a esquerda) tem sua
        # coluna de data marcada com o texto do proprio header "Daily
        # Breakdown" (nao "Date") -- por isso nao casa em _HEADER_KEYWORDS.
        # Blocos de TARGET tem uma coluna de data DUPLICADA (mesmo valor do
        # bloco blended) sem NENHUM header (celula em branco na linha de
        # header) -- ela nao entra em `cols` (que so lista colunas com
        # header preenchido), entao nunca vira 'date' aqui, o que e correto:
        # a data de toda linha vem sempre do bloco blended (col1 de `cols`
        # do bloco 0), os blocos de target nunca precisam da propria.
        if "date" not in col_map and block_index == 0:
            col_map["date"] = min(cols)

        target_group = None
        for col in cols:
            if col - 1 < len(marker_cells):
                marker_val = marker_cells[col - 1].value
                if marker_val and _TARGET_MARKER_RE.match(str(marker_val).strip()):
                    target_group = str(marker_val).strip().upper()
                    break

        if "started" in col_map:  # bloco valido (tem pelo menos a metrica principal)
            blocks.append({"target_group": target_group, "cols": col_map})

    return blocks


def extract_daily_breakdown(xlsx_bytes: bytes, sheet_name: str | None = None) -> list[dict]:
    """Le o bloco 'Daily Breakdown' diretamente do xlsx (sem pre-processamento
    manual) e retorna uma lista de dicts no MESMO formato de raw_row que
    scripts/deploy/load_historical_raw.py grava em raw.historical_uploads --
    {Date, Started Listens (Total), Completed Listens (Total), LTR % (Total),
    Spend (Total), Started Listens (Target 01), Completed Listens (Target 01),
    Started Listens (Target 02), Completed Listens (Target 02)}.

    Falha alto (ValueError) se nao encontrar a linha 'Daily Breakdown' ou o
    bloco blended -- nunca adivinha estrutura."""
    import openpyxl
    import io

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
    sheet_names = [s for s in wb.sheetnames if _deaccent(s) != "_internalcache"]
    if sheet_name:
        if sheet_name not in wb.sheetnames:
            raise ValueError(
                f"[casa_construtor_adf15c2c] sheet_name={sheet_name!r} nao existe no "
                f"arquivo (abas disponiveis: {wb.sheetnames})."
            )
        ws = wb[sheet_name]
    elif len(sheet_names) == 1:
        ws = wb[sheet_names[0]]
    else:
        raise ValueError(
            f"[casa_construtor_adf15c2c] esperava exatamente 1 aba relevante "
            f"(excluindo _InternalCache), achei {len(sheet_names)}: {sheet_names}. "
            f"Passe sheet_name explicitamente."
        )

    header_row = _find_header_row(ws)
    if header_row is None:
        raise ValueError(
            "[casa_construtor_adf15c2c] nao encontrei a linha 'Daily Breakdown' "
            "no arquivo -- estrutura mudou, nao vou adivinhar."
        )

    blocks = _segment_blocks(ws, header_row)
    blended = next((b for b in blocks if b["target_group"] is None), None)
    if blended is None:
        raise ValueError(
            "[casa_construtor_adf15c2c] nao encontrei o bloco blended (sem "
            "marcador TARGET N) logo apos o header 'Daily Breakdown'."
        )
    targets = [b for b in blocks if b["target_group"] is not None]
    # Ordena por numero do target (TARGET 01 antes de TARGET 02) para saida
    # deterministica -- nao afeta correcao, so legibilidade/teste.
    targets.sort(key=lambda b: b["target_group"])

    date_col = blended["cols"].get("date")
    if date_col is None:
        raise ValueError(
            "[casa_construtor_adf15c2c] bloco blended nao tem coluna 'Date' -- "
            "nao consigo alinhar as linhas por dia."
        )

    rows_out = []
    for row in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row):
        date_val = row[date_col - 1].value
        if date_val is None:
            continue
        if isinstance(date_val, str) and date_val.strip().upper() == "TOTAL":
            break  # linha "Total" fecha o bloco -- mesmo criterio do sync_drive.py
        if not isinstance(date_val, (datetime, date)):
            continue  # linha estranha no meio do bloco -- ignora, nao inventa

        def _cell(col_map: dict, key: str):
            col = col_map.get(key)
            if col is None:
                return None
            return row[col - 1].value

        raw_row = {
            COL_DATE: date_val.strftime("%Y-%m-%d") if isinstance(date_val, (datetime, date)) else str(date_val),
            COL_IMP_TOTAL: _cell(blended["cols"], "started"),
            COL_COMPLETED_TOTAL: _cell(blended["cols"], "completed"),
            COL_LTR_TOTAL: _cell(blended["cols"], "ltr"),
            COL_SPEND_TOTAL: _cell(blended["cols"], "spend"),
            COL_IMP_T1: None,
            COL_COMPLETED_T1: None,
            COL_IMP_T2: None,
            COL_COMPLETED_T2: None,
        }
        for i, block in enumerate(targets[:2], start=1):
            raw_row[f"Started Listens (Target 0{i})"] = _cell(block["cols"], "started")
            raw_row[f"Completed Listens (Target 0{i})"] = _cell(block["cols"], "completed")

        rows_out.append(raw_row)

    return rows_out


# ─── normalize() -- contrato historical_mappings ───────────────────────────

def _parse_date(value, row_number) -> date:
    """Aceita string 'YYYY-MM-DD' (fluxo antigo, CSV pre-extraido) ou
    date/datetime (extract_daily_breakdown ja normaliza pra string ISO, mas
    aceitar objeto tambem protege contra chamada direta sem passar por
    raw.historical_uploads). Falha alto se nao bater nenhum dos dois."""
    if isinstance(value, (date, datetime)):
        return value.date() if isinstance(value, datetime) else value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except Exception as exc:
        raise ValueError(
            f"[casa_construtor_adf15c2c] row_number={row_number}: 'Date'={value!r} "
            f"nao parseia como YYYY-MM-DD."
        ) from exc


def _parse_number(value):
    """Colunas ja vem em formato numerico simples (ponto decimal, sem
    separador de milhar BR, sem prefixo R$) -- extraidas diretamente do
    Excel via openpyxl com data_only=True, nao digitadas a mao. None/vazio
    -> None."""
    if value is None:
        return None
    v = str(value).strip()
    if v == "":
        return None
    return float(v)


def normalize(raw_rows: list[dict]) -> list[dict]:
    out = []
    for item in raw_rows:
        raw = item["raw_row"]
        row_number = item["row_number"]

        day = _parse_date(raw[COL_DATE], row_number)

        impressions_total = _parse_number(raw.get(COL_IMP_TOTAL))
        investimento = _parse_number(raw.get(COL_SPEND_TOTAL))

        # Linhas sem dado real reportado (ver docstring do modulo) --
        # blended vazio para os 2 campos que realmente alimentam o
        # override. Descartadas (nao viram linha com 0/NULL falso) -- as 3
        # linhas do dia (blended + 2 targets) saem juntas ou nenhuma sai.
        if impressions_total is None and investimento is None:
            continue

        base_row = {
            "client_id": CLIENT_ID,
            "day": day.isoformat(),
            "platform": PLATFORM,
            "formato": FORMATO,
            "goal_type": GOAL_TYPE,
            "clicks": None,
            "conversions": None,
            "planned_impressions_daily": None,
            "planned_clicks_daily": None,
            "planned_spend_daily": None,
            "unit_price": None,
            "source_file": item["source_filename"],
        }

        out.append({
            **base_row,
            "target_group": None,
            "impressions": impressions_total,
            "investimento": investimento,
            "notes": (
                "PROVISORIO -- platform/goal_type nao confirmados pelo Douglas "
                "(ver docstring de historical_mappings/casa_construtor_adf15c2c.py). "
                "impressions = Started Listens (equivalencia ja usada pelo DASH "
                "do cliente, nao validada por este agente). Linha TOTAL/blended -- "
                "a unica que alimenta gold.fact_delivery/stg.fact_pacing_base "
                "(target_group IS NULL)."
            ),
        })

        # Linhas de target -- auditoria/consulta apenas (ver "Grain de saida"
        # na docstring do modulo). impressions <- Started Listens do bloco do
        # target correspondente; investimento sempre None (nao existe Spend
        # por target nesta fonte).
        for target_group, imp_col in ((("TARGET 01"), COL_IMP_T1), (("TARGET 02"), COL_IMP_T2)):
            target_impressions = _parse_number(raw.get(imp_col))
            if target_impressions is None:
                continue  # mesmo dia sem dado de target -- nao inventa 0
            out.append({
                **base_row,
                "target_group": target_group,
                "impressions": target_impressions,
                "investimento": None,
                "notes": (
                    f"PROVISORIO -- linha de auditoria ({target_group}), rateio "
                    f"proporcional sintetico do blended (NAO medicao independente, "
                    f"confirmado: {target_group} + o outro target somam de volta ao "
                    f"TOTAL blended). NAO alimenta gold.fact_delivery/"
                    f"stg.fact_pacing_base (esses filtram target_group IS NULL) -- "
                    f"existe so para comparar contra o planejado por target do IO "
                    f"Plan."
                ),
            })

    return out
