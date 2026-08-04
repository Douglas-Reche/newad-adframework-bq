-- Overrides historicos (Cora, Jan-Jun/2026) -- rodar manualmente via `bq query`,
-- fora do deploy automatizado. Ver hub/README.md e docs/PROCESS.md para o contexto
-- da decisao: fluxo fechado e pontual, nao generaliza para outros clientes/periodos.

CREATE TABLE IF NOT EXISTS `adframework.core.historical_overrides_delivery` (
  client_id STRING NOT NULL,
  day DATE NOT NULL,
  platform STRING,
  formato STRING,
  goal_type STRING,
  impressions FLOAT64,
  clicks FLOAT64,
  investimento NUMERIC,
  source_file STRING,
  loaded_by STRING,
  loaded_at TIMESTAMP,
  notes STRING
);

CREATE OR REPLACE VIEW `adframework.gold.vw_fact_delivery_reporting` AS
SELECT client_id, day, platform, formato, goal_type, impressions, clicks, conversions
FROM `adframework.gold.fact_delivery`
WHERE NOT (client_id = 'banco_cora_fe13d78a' AND day < '2026-07-01')
UNION ALL
SELECT client_id, day, platform, formato, goal_type, impressions, clicks, CAST(NULL AS FLOAT64) AS conversions
FROM `adframework.core.historical_overrides_delivery`
WHERE client_id = 'banco_cora_fe13d78a' AND day < '2026-07-01';
