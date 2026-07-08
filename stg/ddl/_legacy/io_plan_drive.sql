-- stg.io_plan_drive
-- VIEW deduplicada sobre raw.io_plan_drive_snapshot.
-- Grain: 1 linha por (client_id, drive_folder, strategy_name, flight_start) — snapshot mais recente.
-- Adiciona: plan_line_id (ID estável por linha de plano), category (DISPLAY/VIDEO/RETARGETING/NATIVE/PUSH).
-- Filtro: apenas linhas com datas e valor preenchidos.
--
-- plan_line_id: MD5(client_id | drive_folder | strategy_name)
--   Estável entre re-syncs — permite referenciar linhas em formulários externos.
--   Nota: não inclui flight_start para que uma linha de estratégia recorrente
--   (mesmo cliente, mesma pasta, mesmo nome) tenha o mesmo ID entre meses.
--   Se client_id+drive_folder+strategy_name se repetir em meses diferentes, o dedup
--   mantém apenas o snapshot mais recente por flight_start.
--
-- Fonte: raw.io_plan_drive_snapshot
-- Downstream: gold.fact_io_plan

CREATE OR REPLACE VIEW `adframework.stg.io_plan_drive` AS

WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY client_id, drive_folder, strategy_name, flight_start
      ORDER BY snapshot_at DESC
    ) AS _rn
  FROM `adframework.raw.io_plan_drive_snapshot`
  WHERE flight_start IS NOT NULL
    AND flight_end   IS NOT NULL
    AND monthly_spend IS NOT NULL
    AND EXTRACT(YEAR FROM flight_start) >= 2026
)

SELECT
  -- ── Identidade ─────────────────────────────────────────────────────────────
  TO_HEX(MD5(CONCAT(
    COALESCE(client_id, ''), '|',
    COALESCE(drive_folder, ''), '|',
    COALESCE(strategy_name, '')
  )))                                  AS plan_line_id,

  client_id,
  drive_folder,
  source_file,
  spend_type,
  snapshot_at,

  -- ── Período do flight ───────────────────────────────────────────────────────
  flight_start,
  flight_end,
  flight_label,
  DATE_DIFF(flight_end, flight_start, DAY) + 1 AS flight_days,

  -- ── Estratégia e classificação ──────────────────────────────────────────────
  strategy_name,

  -- PUSH sempre = siprocal (todos os clientes atuais operam Push via Siprocal)
  CASE
    WHEN LOWER(strategy_name) LIKE '%push%' THEN 'siprocal'
    ELSE platform
  END                                  AS platform,

  CASE
    WHEN LOWER(strategy_name) LIKE '%retarget%'                             THEN 'RETARGETING'
    WHEN LOWER(strategy_name) LIKE '%display%'                              THEN 'DISPLAY'
    WHEN LOWER(strategy_name) LIKE '%video%' OR LOWER(strategy_name) LIKE '%vídeo%' THEN 'VIDEO'
    WHEN LOWER(strategy_name) LIKE '%native%'                               THEN 'NATIVE'
    WHEN LOWER(strategy_name) LIKE '%push%'                                 THEN 'PUSH'
    ELSE 'OTHER'
  END                                  AS category,

  device,
  format,
  buy_model,

  -- ── KPIs planejados ─────────────────────────────────────────────────────────
  monthly_spend                        AS planned_spend,
  unit_price,
  impressions_cpm,
  impressions_est,
  COALESCE(impressions_cpm, impressions_est) AS planned_impressions,
  video_views                          AS planned_video_views,
  clicks                               AS planned_clicks,
  ctr_approx,
  reach

FROM ranked
WHERE _rn = 1;
