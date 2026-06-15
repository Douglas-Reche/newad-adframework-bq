-- gold.dim_conversion_mapping
-- Camada semântica de conversões por cliente.
-- client_id NULL = regra global (vale para qualquer cliente sem override específico).
-- No Power BI: COALESCE(override do cliente, regra global) para resolver o nome.
-- Fonte: core/seeds/conversion_mapping.csv — adicionar linhas após reunião com clientes.

CREATE OR REPLACE TABLE `adframework.gold.dim_conversion_mapping`
(
  client_id           STRING,
  platform            STRING NOT NULL,
  conversion_slot     STRING NOT NULL,
  conversion_name     STRING NOT NULL,
  conversion_description STRING,
  is_primary          BOOL   NOT NULL,
  created_at          DATE   NOT NULL
)
OPTIONS (description = 'Significado semantico de cada slot de conversao por cliente. NULL client_id = default global.');

INSERT INTO `adframework.gold.dim_conversion_mapping`
  (client_id, platform, conversion_slot, conversion_name, conversion_description, is_primary, created_at)
VALUES
-- Global default — vale para todos sem override
  (NULL, 'mediasmart', 'conversions_1', 'Pageview', 'Visualizacao de pagina — default global', FALSE, '2026-05-26'),
-- LuckBet — mapeamento confirmado
  ('luckbet_bea15ebc', 'mediasmart', 'conversions_2', 'Cadastro',           'Cadastro completo na plataforma',              FALSE, '2026-05-26'),
  ('luckbet_bea15ebc', 'mediasmart', 'conversions_3', 'FTD',                'First Time Deposit — primeiro deposito',        TRUE,  '2026-05-26'),
  ('luckbet_bea15ebc', 'mediasmart', 'conversions_4', 'Deposito Recorrente','Deposito de usuario ja cadastrado',             FALSE, '2026-05-26'),
  ('luckbet_bea15ebc', 'mediasmart', 'conversions_5', 'Inicio Cadastro',    'Usuario iniciou mas nao completou o cadastro',  FALSE, '2026-05-26');
