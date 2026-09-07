-- stg.io_plan
-- STG do IO Plan (planejamento de verba) -- grain: 1 linha por
-- (client_id, drive_folder, strategy_name, flight_start), dedup pelo
-- snapshot mais recente. RAW (raw.io_plan_drive_snapshot) e fiel a fonte
-- (planilha) -- toda derivacao acontece aqui.
--
-- formato: extraido de strategy_name (texto livre da planilha) via
-- core.resolve_strategy_format(strategy_name, flight_start) -- classificacao
-- por keyword versionada (SCD2) em core.strategy_format_map, vigente na data
-- de INICIO DO VOO (flight_start, nao snapshot_at -- e o conceito de quando a
-- estrategia esteve em vigor pra fins de planejamento). Testado contra as 295
-- linhas reais (2026-06-24): 295/295 (100%) resolvido pelo vocabulario
-- original (Display/Video/Retargeting/Native/Push/AppInstall).
--
-- 2026-09-07 -- migrado do CASE WHEN hardcoded que existia aqui (vocabulario
-- fixo de 6 formatos, ELSE NULL silencioso e permanente) para
-- core.resolve_strategy_format -- mesmo padrao ja usado em
-- core.resolve_dict_format/core.resolve_platform_rule (ver esses arquivos e
-- gold/ddl/fact_io_plan.sql pro historico completo da migracao SCD2 da
-- camada Gold). Formato nao mapeado agora fica documentavel/auditavel como
-- linha pendente em core.strategy_format_map em vez de exigir deploy de
-- codigo -- achado real que motivou: "Áudio Ads" da Casa do Construtor
-- (client_id=casa_construtor_adf15c2c) cai em formato=NULL (esperado --
-- keyword 'audio' ainda nao cadastrada, ver core/migration/10_seed_strategy_format_map.sql).
-- Validado contra a view antiga: 0 divergencias nas 27 combinacoes reais de
-- strategy_name em douglas-bq-staging.stg.io_plan.
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
--
-- 2026-09-07 -- target_group adicionado ao PARTITION BY do dedup (achado
-- real, Casa do Construtor): quando a aba do xlsx tem múltiplos blocos
-- "TARGET N" empilhados, a MESMA strategy_name se repete uma vez por bloco
-- com valores diferentes (ver raw/ddl/io_plan_drive_snapshot.sql e
-- scripts/io_plan/sync_drive.py, _find_next_block). Sem target_group no
-- PARTITION BY, o ROW_NUMBER original colidia as duas linhas na mesma
-- partição (mesmo client_id/drive_folder/strategy_name/flight_start) e
-- descartava uma delas -- perda de dado silenciosa igual à do parser RAW
-- que motivou esta correção, só que uma camada acima. target_group é NULL
-- para a maioria dos arquivos (sem blocos), então o PARTITION BY se
-- comporta exatamente como antes nesses casos.

CREATE OR REPLACE VIEW `adframework.stg.io_plan` AS
WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY client_id, drive_folder, strategy_name, flight_start, target_group
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
    `adframework.core.resolve_strategy_format`(strategy_name, flight_start) AS formato,
    CASE
      WHEN LOWER(strategy_name) LIKE '%siprocal%' THEN 'siprocal'
      WHEN LOWER(strategy_name) LIKE '%mgid%' THEN 'mgid'
      ELSE platform
    END AS platform_fixed,
    -- Registros históricos de TecPar pertencem a Amigo (sub-cliente).
    -- Planos novos já entrarão diretamente como amigo_db1c2f0c.
    CASE
      WHEN client_id = 'tecpar_edfcc744' THEN 'amigo_db1c2f0c'
      ELSE client_id
    END AS client_id_resolved
  FROM deduped
)
SELECT
  TO_HEX(MD5(CONCAT(
    COALESCE(e.client_id_resolved, ''), '|',
    COALESCE(e.drive_folder, ''), '|',
    COALESCE(e.strategy_name, ''), '|',
    COALESCE(e.target_group, '')
  ))) AS plan_line_id,
  e.client_id_resolved AS client_id,
  e.drive_folder,
  e.source_file,
  e.spend_type,
  e.snapshot_at,
  e.flight_start,
  e.flight_end,
  e.flight_label,
  DATE_DIFF(e.flight_end, e.flight_start, DAY) + 1 AS flight_days,
  e.target_group,
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
