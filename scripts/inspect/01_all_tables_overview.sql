-- Visão geral de todas as tabelas e views do projeto adframework
-- Executa contra INFORMATION_SCHEMA de cada dataset e consolida
-- Rode isso para saber o que existe de verdade no BigQuery

SELECT
  table_schema AS dataset,
  table_name,
  table_type,
  CASE table_type
    WHEN 'BASE TABLE' THEN 'tabela'
    WHEN 'VIEW'       THEN 'view'
    WHEN 'EXTERNAL'   THEN 'externa'
  END AS tipo,
  creation_time
FROM (
  SELECT * FROM `adframework.raw.INFORMATION_SCHEMA.TABLES`
  UNION ALL
  SELECT * FROM `adframework.raw_newadframework.INFORMATION_SCHEMA.TABLES`
  UNION ALL
  SELECT * FROM `adframework.stg.INFORMATION_SCHEMA.TABLES`
  UNION ALL
  SELECT * FROM `adframework.core.INFORMATION_SCHEMA.TABLES`
  UNION ALL
  SELECT * FROM `adframework.marts.INFORMATION_SCHEMA.TABLES`
  UNION ALL
  SELECT * FROM `adframework.share.INFORMATION_SCHEMA.TABLES`
  UNION ALL
  SELECT * FROM `adframework.gold.INFORMATION_SCHEMA.TABLES`
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
  table_type,
  table_name
