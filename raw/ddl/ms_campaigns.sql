-- raw.ms_campaigns
-- Cadastro de campanhas da MediaSmart (T2).
-- Grain: 1 linha por campaign_id
-- Fonte: GET /api/campaigns (lista de IDs) -> GET /api/campaign/{id} (corpo completo, 1 chamada por ID, sleep 0.5s)
-- Ingestao: WRITE_TRUNCATE diario (catalogo)
--
-- Validado contra API real em 2026-06-22 (5 campanhas reais: Cora, Amigo, Stocco, Einstein).
-- goal, client_pricing e conversion_names vem sempre vazios/null em todas as campanhas
-- testadas (optimization_type='off' em 100%) -- omitidos deste schema. Se precisarem no
-- futuro, adicionar coluna apos confirmar dado real (mesma regra de processo do MGID/Siprocal).
--
-- NOTA DE TIPO: campos inteiros nullable (attribution_window_*, max_daily/global_impressions)
-- sao FLOAT64, nao INT64. Motivo: BigQueryService.load_data() (src/bigquery.py) converte
-- toda a linha via pandas DataFrame.astype(str) antes de carregar -- quando uma coluna tem
-- None misturado com inteiros, o pandas promove a coluna para float64, e o valor vira "30.0"
-- em vez de "30". BQ aceita "30.0" em coluna FLOAT64, mas rejeita em coluna INT64 estrita
-- ("Could not convert value 'string_value: 30.0' to integer"). Descoberto e corrigido em 2026-06-22.

CREATE OR REPLACE TABLE `adframework.raw.ms_campaigns`
(
  campaign_id                       STRING,     -- id nativo da campanha -- PK
  campaign_name                     STRING,     -- nome da campanha
  client_id                         STRING,     -- event_id -- FK para raw.ms_advertisers.event_id
  advertiser_name                   STRING,     -- nome do advertiser (redundante com T1, util p/ debug)
  state                             STRING,     -- active/inactive/deleted/preview/imported
  type                              STRING,     -- generic/dooh/smart-tv/synchronized
  color                             STRING,
  description                      STRING,
  tags                              STRING,     -- JSON array como string
  tracking_tool                     STRING,     -- mediasmart/appsflyer/adjust/branch/kochava/SKAdNetwork
  cross_device                      BOOL,
  desktop_allowed                   BOOL,
  premium_dashboard                 BOOL,
  use_custom_conversion_names       BOOL,
  minimal_cpm                       FLOAT64,    -- price floor real -- substitui o goal_cpm sempre vazio
  attribution_window_on_click       FLOAT64,    -- dias -- FLOAT64, nao INT64 (ver nota abaixo)
  attribution_window_on_impression  FLOAT64,    -- dias -- FLOAT64, nao INT64 (ver nota abaixo)
  -- schedule (confirmado rico em produção)
  started_at                        DATE,
  finished_at                       DATE,
  max_daily_cost                    FLOAT64,
  max_global_cost                   FLOAT64,
  max_daily_impressions             FLOAT64,    -- FLOAT64, nao INT64 (ver nota abaixo)
  max_global_impressions            FLOAT64,    -- FLOAT64, nao INT64 (ver nota abaixo)
  delivered_cost                    FLOAT64,
  daily_limits_type                 STRING,     -- auto/manual
  uniform_distribution              BOOL,
  timezone                          STRING,
  -- segmentacao preservada como JSON (rico, nao vale a pena achatar agora)
  targeting                         STRING,     -- JSON
  retargeting                       STRING,     -- JSON
  created_at                        DATE,       -- vem so como data, sem hora (ex: "2025-10-31")
  updated_at                        STRING,     -- vem como ISO 8601 com milissegundos+Z (ex: "2026-06-11T18:09:12.880Z") -- cast na STG
  platform                          STRING,     -- 'mediasmart' (injetado)
  raw_ingested_at                   TIMESTAMP   -- timestamp da ingestao (injetado)
)
OPTIONS (
  description = 'T2 MS — cadastro de campanhas. client_id = event_id, FK para ms_advertisers. WRITE_TRUNCATE diario.'
);
