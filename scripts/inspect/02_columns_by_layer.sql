-- Schema completo de colunas por camada
-- Mostra dataset, tabela, coluna, tipo e posição
-- Use para entender a estrutura de qualquer tabela sem precisar abrir o console GCP

SELECT
  table_schema AS dataset,
  table_name,
  ordinal_position AS pos,
  column_name,
  data_type,
  is_nullable,
  -- Útil para identificar colunas que são sempre NULL (possível problema de schema)
  is_partitioning_column
FROM (
  SELECT * FROM `adframework.raw.INFORMATION_SCHEMA.COLUMNS`
  UNION ALL
  SELECT * FROM `adframework.raw_newadframework.INFORMATION_SCHEMA.COLUMNS`
  UNION ALL
  SELECT * FROM `adframework.stg.INFORMATION_SCHEMA.COLUMNS`
  UNION ALL
  SELECT * FROM `adframework.core.INFORMATION_SCHEMA.COLUMNS`
  UNION ALL
  SELECT * FROM `adframework.marts.INFORMATION_SCHEMA.COLUMNS`
  UNION ALL
  SELECT * FROM `adframework.share.INFORMATION_SCHEMA.COLUMNS`
  UNION ALL
  SELECT * FROM `adframework.gold.INFORMATION_SCHEMA.COLUMNS`
)
ORDER BY
  CASE table_schema
    WHEN 'raw'                THEN 1
    WHEN 'raw_newadframework' THEN 2
    WHEN 'stg'                THEN 3
    WHEN 'core'               THEN 4
    WHEN 'marts'              THEN 5
    WHEN 'share'              THEN 6
    WHEN 'gold'               THEN 7
  END,
  table_name,
  ordinal_position

-- Para filtrar por dataset específico, adicione WHERE:
-- WHERE table_schema = 'gold'
-- WHERE table_schema = 'raw' AND table_name = 'mediasmart_daily_operational'
