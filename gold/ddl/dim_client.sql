-- gold.dim_client
-- Dimensão de clientes para o star schema GOLD.
-- View sobre core.dim_client — sempre sincronizada.

CREATE OR REPLACE VIEW `adframework.gold.dim_client` AS
SELECT
  client_id,
  slug,
  name        AS client_name,
  sector,
  status,
  created_at,
  notes
FROM `adframework.core.dim_client`;
