-- raw.io_plan_drive_snapshot
-- Snapshot cru das planilhas de plano comercial importadas do Google Drive.
-- Grain: 1 linha por estratégia (linha do xlsx) por flight por cliente.
-- Preserva os dados originais sem transformação — rastreabilidade total.
--
-- Ingestão atual: manual (via script Python ou carga direta no BQ Console).
-- Ingestão futura: script automatizado que varre CLIENT/ANO/MÊS/PLANO/*.xlsx no Drive,
--   lê o arquivo mais recente de cada pasta PLANO/ e carrega incrementalmente.
--
-- Downstream: core.io_plan_manual agrega estas linhas ao grain flight × cliente.
--
-- Colunas de contexto (não estão no xlsx — inferidas pela estrutura de pastas):
--   client_id    ← nome da pasta-cliente mapeado para canonical ID
--   drive_folder ← path simbólico no Drive (CLIENT/ANO/MÊS)
--   source_file  ← nome do arquivo .xlsx
--   snapshot_at  ← timestamp da leitura
--
-- ⚠️ PENDÊNCIAS PARA ALINHAMENTO COM COMERCIAL (ver também core/ddl/io_plan_manual.sql)
--   - Coluna 'platform': inferida do nome da estratégia (Mídia Programática → mediasmart).
--     "Vídeo Ads" e "Push APPTARGETING" não têm mapeamento confirmado.
--   - Coluna 'spend_type': 'gross' (taxa cliente) ou 'net' (taxa mídia) depende de qual
--     arquivo está na pasta. Padrão sugerido: um arquivo com ambas as colunas.

CREATE OR REPLACE TABLE `adframework.raw.io_plan_drive_snapshot`
(
  -- ── Contexto (inferido da estrutura de pastas, não do xlsx) ───────────────
  client_id        STRING   NOT NULL,   -- canonical ID mapeado da pasta-cliente
  drive_folder     STRING,              -- ex: 'CORA/2026/MAIO'
  source_file      STRING   NOT NULL,   -- nome do arquivo .xlsx
  spend_type       STRING   NOT NULL,   -- 'gross' (taxa cliente) | 'net' (taxa midia)
  snapshot_at      TIMESTAMP NOT NULL,  -- timestamp da leitura/carga

  -- ── Período do plano (extraído do cabeçalho ou nome do xlsx) ────────────
  flight_label     STRING,              -- ex: '11 MAI A 10 JUN' (texto original)
  flight_start     DATE,                -- data início parseada
  flight_end       DATE,                -- data fim parseada

  -- ── Linha de estratégia (1 row por linha do xlsx) ───────────────────────
  strategy_name    STRING,              -- ex: 'Mídia Programática Display', 'Vídeo Ads'
  platform         STRING,              -- mediasmart | mgid | siprocal | unknown
  device           STRING,              -- ex: 'Desktop e Mobile', 'Mobile'
  format           STRING,              -- ex: 'Banner IAB', 'Vídeo', 'Push Banner'
  buy_model        STRING,              -- CPM | CPC | CPA | null

  -- ── KPIs planejados (valores brutos do xlsx) ────────────────────────────
  unit_price       NUMERIC,             -- taxa unitária (R$/mil para CPM, R$/click para CPC)
  impressions_cpm  INT64,               -- impressões coluna CPM (*** = null)
  impressions_est  INT64,               -- impressões coluna ESTIMATIVA (CPC/Push)
  video_views      INT64,               -- visualizações de vídeo (col. VISUALIZAÇÕES)
  monthly_spend    NUMERIC,             -- INVESTIMENTO LÍQUIDO MENSAL da linha
  ctr_approx       FLOAT64,             -- CTR aproximado (%)
  clicks           INT64,               -- cliques estimados
  reach            INT64                -- alcance mensal estimado
)
PARTITION BY DATE(snapshot_at)
OPTIONS (
  description = 'Snapshot cru das planilhas de plano comercial do Google Drive. Grain: linha de estrategia x flight x cliente. Downstream: core.io_plan_manual agrega ao nivel de flight.'
);
