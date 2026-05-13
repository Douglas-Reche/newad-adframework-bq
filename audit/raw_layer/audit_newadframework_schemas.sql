SELECT table_schema AS dataset, table_name, column_name, data_type, ordinal_position
FROM `adframework.raw_newadframework.INFORMATION_SCHEMA.COLUMNS`
ORDER BY table_name, ordinal_position
