-- Volume real de dados por tabela: linhas, tamanho, última modificação
-- Usa __TABLES__ (metadado nativo do BigQuery, não cobra processamento)
-- type: 1 = tabela física, 2 = view, 3 = externa

SELECT
  dataset_id AS dataset,
  table_id AS tabela,
  CASE type WHEN 1 THEN 'tabela' WHEN 2 THEN 'view' WHEN 3 THEN 'externa' END AS tipo,
  row_count AS linhas,
  ROUND(size_bytes / 1024 / 1024, 1) AS tamanho_mb,
  TIMESTAMP_MILLIS(last_modified_time) AS ultima_modificacao,
  TIMESTAMP_MILLIS(creation_time) AS criacao
FROM (
  SELECT 'raw'                AS dataset_id, * FROM `adframework.raw.__TABLES__`
  UNION ALL
  SELECT 'raw_newadframework', * FROM `adframework.raw_newadframework.__TABLES__`
  UNION ALL
  SELECT 'stg',               * FROM `adframework.stg.__TABLES__`
  UNION ALL
  SELECT 'core',              * FROM `adframework.core.__TABLES__`
  UNION ALL
  SELECT 'marts',             * FROM `adframework.marts.__TABLES__`
  UNION ALL
  SELECT 'share',             * FROM `adframework.share.__TABLES__`
  UNION ALL
  SELECT 'gold',              * FROM `adframework.gold.__TABLES__`
)
ORDER BY
  CASE dataset_id
    WHEN 'raw'                THEN 1
    WHEN 'raw_newadframework' THEN 2
    WHEN 'stg'                THEN 3
    WHEN 'core'               THEN 4
    WHEN 'marts'              THEN 5
    WHEN 'share'              THEN 6
    WHEN 'gold'               THEN 7
  END,
  row_count DESC

-- NOTA: views (type=2) sempre mostram row_count=0 e size_bytes=0 pois não armazenam dados
-- Para saber o volume real de uma view, rode SELECT COUNT(*) FROM `adframework.gold.fct_delivery_daily`
