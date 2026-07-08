-- stg.io_plan
-- STG do IO Plan (planejamento de verba) -- grain: 1 linha por
-- (client_id, drive_folder, strategy_name, flight_start), dedup pelo
-- snapshot mais recente. RAW (raw.io_plan_drive_snapshot) e fiel a fonte
-- (planilha) -- toda derivacao acontece aqui.
--
-- formato: extraido de strategy_name (texto livre da planilha), vocabulario
-- igual ao usado em entrega (Display/Video/Retargeting/Native/Push) +
-- AppInstall (exclusivo do plano, ainda nao roda em nenhuma plataforma de
-- entrega ativa). Testado contra as 295 linhas reais (2026-06-24): 295/295
-- (100%) resolvido.
--
-- SEM goal_type aqui (decisao do usuario 2026-06-24): goal_type e conceito
-- de campanha/entrega (ms_campaigns/mg_campaigns/sp_campaigns), nao de
-- planejamento. O IO Plan so carrega formato.
--
-- platform: raw.platform (PLATFORM_RULES no sync_drive.py) tem gaps --
-- corrigido aqui (sem mudar o parser RAW) com 2 regras adicionais:
-- contem 'SIPROCAL' -> siprocal, contem 'MGID' -> mgid. Resolve 7/91 dos
-- 'unknown'. Os outros 84 (Push e AppInstall genericos) realmente nao tem
-- sinal de plataforma no texto -- limitacao real do dado, nao bug de regex.

CREATE OR REPLACE VIEW `adframework.stg.io_plan` AS
WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY client_id, drive_folder, strategy_name, flight_start
      ORDER BY snapshot_at DESC
    ) AS _rn
  FROM `adframework.raw.io_plan_drive_snapshot`
  WHERE flight_start IS NOT NULL
    AND flight_end IS NOT NULL
    AND monthly_spend IS NOT NULL
),
deduped AS (
  SELECT * FROM ranked WHERE _rn = 1
),
extracted AS (
  SELECT
    *,
    CASE
      WHEN LOWER(strategy_name) LIKE '%native%' THEN 'Native'
      WHEN LOWER(strategy_name) LIKE '%video%' OR LOWER(strategy_name) LIKE '%vídeo%' THEN 'Video'
      WHEN LOWER(strategy_name) LIKE '%retargeting%' THEN 'Retargeting'
      WHEN LOWER(strategy_name) LIKE '%display%' THEN 'Display'
      WHEN LOWER(strategy_name) LIKE '%push%' THEN 'Push'
      WHEN LOWER(strategy_name) LIKE '%appinstall%' OR LOWER(strategy_name) LIKE '%app install%' THEN 'AppInstall'
      ELSE NULL
    END AS formato,
    CASE
      WHEN LOWER(strategy_name) LIKE '%siprocal%' THEN 'siprocal'
      WHEN LOWER(strategy_name) LIKE '%mgid%' THEN 'mgid'
      ELSE platform
    END AS platform_fixed
  FROM deduped
)
SELECT
  TO_HEX(MD5(CONCAT(
    COALESCE(e.client_id, ''), '|',
    COALESCE(e.drive_folder, ''), '|',
    COALESCE(e.strategy_name, '')
  ))) AS plan_line_id,
  e.client_id,
  e.drive_folder,
  e.source_file,
  e.spend_type,
  e.snapshot_at,
  e.flight_start,
  e.flight_end,
  e.flight_label,
  DATE_DIFF(e.flight_end, e.flight_start, DAY) + 1 AS flight_days,
  e.strategy_name,
  e.platform_fixed AS platform,
  e.formato,
  e.device,
  e.format AS creative_format_label,
  e.buy_model,
  e.monthly_spend AS planned_spend,
  e.unit_price,
  e.impressions_cpm,
  e.impressions_est,
  COALESCE(e.impressions_cpm, e.impressions_est) AS planned_impressions,
  e.video_views AS planned_video_views,
  e.clicks AS planned_clicks,
  e.ctr_approx,
  e.reach
FROM extracted e;
