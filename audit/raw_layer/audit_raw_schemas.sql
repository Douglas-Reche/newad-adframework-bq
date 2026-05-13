-- Schema de todas as tabelas raw principais (colunas e tipos)
SELECT table_schema AS dataset, table_name, column_name, data_type, ordinal_position
FROM `adframework.raw.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name IN (
  'mediasmart_daily',
  'mediasmart_daily_operational',
  'mediasmart_campaigns',
  'mediasmart_advertisers',
  'mediasmart_daily_creative',
  'mediasmart_revenue_daily',
  'mgid_daily',
  'mgid_campaigns',
  'siprocal_daily_materialized',
  'siprocal_daily_native'
)

UNION ALL

SELECT table_schema, table_name, column_name, data_type, ordinal_position
FROM `adframework.raw_newadframework.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name IN (
  'io_manager_v2',
  'io_line_bindings_v2',
  'proposal_lines',
  'proposals',
  'platform_client_links'
)

ORDER BY dataset, table_name, ordinal_position
