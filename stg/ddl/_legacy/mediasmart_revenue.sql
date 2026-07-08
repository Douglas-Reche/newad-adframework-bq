-- stg.mediasmart_revenue
-- Typing e normalização sobre raw.mediasmart_revenue.
-- Grain: day + controlid + strategyid + revenuesource

CREATE OR REPLACE VIEW `adframework.stg.mediasmart_revenue` AS
SELECT
  SAFE_CAST(day AS DATE)                  AS day,
  controlid,
  strategyid,
  revenuesource,
  SAFE_CAST(clientrevenue AS FLOAT64)     AS clientrevenue,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.mediasmart_revenue`
WHERE day IS NOT NULL;
