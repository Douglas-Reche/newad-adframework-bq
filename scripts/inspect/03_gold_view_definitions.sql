-- DDL real das views da camada gold
-- Fonte: INFORMATION_SCHEMA.VIEWS — o que está executando no BigQuery agora
-- Compare com os arquivos em gold/ deste repositório para detectar divergências

SELECT
  table_name AS view_name,
  view_definition
FROM `adframework.gold.INFORMATION_SCHEMA.VIEWS`
ORDER BY table_name

-- Para ver o DDL de uma view específica:
-- WHERE table_name = 'fct_delivery_daily'

-- Para todas as camadas (stg, marts, share, gold):
/*
SELECT 'stg' AS dataset, table_name, view_definition FROM `adframework.stg.INFORMATION_SCHEMA.VIEWS`
UNION ALL
SELECT 'marts', table_name, view_definition FROM `adframework.marts.INFORMATION_SCHEMA.VIEWS`
UNION ALL
SELECT 'share', table_name, view_definition FROM `adframework.share.INFORMATION_SCHEMA.VIEWS`
UNION ALL
SELECT 'gold', table_name, view_definition FROM `adframework.gold.INFORMATION_SCHEMA.VIEWS`
ORDER BY dataset, table_name
*/
