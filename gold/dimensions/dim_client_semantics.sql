CREATE OR REPLACE VIEW `adframework.gold.dim_client_semantics` AS
SELECT * FROM UNNEST([
  -- Luckbet (confirmado Shiro 29/04/2026) — conv1 universal
  STRUCT('nwd_luckbet_a485d6bc' AS newad_client_id, 'conversion' AS semantic_type, 'conversions1' AS field_key, 'pageviews' AS field_label, 'universal' AS scope),
  STRUCT('nwd_luckbet_a485d6bc', 'conversion', 'conversions2', 'cadastros', 'luckbet'),
  STRUCT('nwd_luckbet_a485d6bc', 'conversion', 'conversions3', 'ftds', 'luckbet'),
  STRUCT('nwd_luckbet_a485d6bc', 'conversion', 'conversions4', 'depositos_recorrentes', 'luckbet'),
  STRUCT('nwd_luckbet_a485d6bc', 'conversion', 'conversions5', 'inicio_cadastro', 'luckbet'),
  -- Banco Cora (pendente definição comercial)
  STRUCT('nwd_banco-cora_acfae3ab', 'conversion', 'conversions1', 'pageviews', 'universal'),
  STRUCT('nwd_banco-cora_acfae3ab', 'conversion', 'conversions2', 'conversion2', 'pending'),
  STRUCT('nwd_banco-cora_acfae3ab', 'conversion', 'conversions3', 'conversion3', 'pending'),
  STRUCT('nwd_banco-cora_acfae3ab', 'conversion', 'conversions4', 'conversion4', 'pending'),
  STRUCT('nwd_banco-cora_acfae3ab', 'conversion', 'conversions5', 'conversion5', 'pending'),
  -- Tec-Par (pendente)
  STRUCT('nwd_tec-par_4ee38788', 'conversion', 'conversions1', 'pageviews', 'universal'),
  STRUCT('nwd_tec-par_4ee38788', 'conversion', 'conversions2', 'conversion2', 'pending'),
  STRUCT('nwd_tec-par_4ee38788', 'conversion', 'conversions3', 'conversion3', 'pending'),
  STRUCT('nwd_tec-par_4ee38788', 'conversion', 'conversions4', 'conversion4', 'pending'),
  STRUCT('nwd_tec-par_4ee38788', 'conversion', 'conversions5', 'conversion5', 'pending'),
  -- Einstein (pendente)
  STRUCT('nwd_einstein_223330d5', 'conversion', 'conversions1', 'pageviews', 'universal'),
  STRUCT('nwd_einstein_223330d5', 'conversion', 'conversions2', 'conversion2', 'pending'),
  STRUCT('nwd_einstein_223330d5', 'conversion', 'conversions3', 'conversion3', 'pending'),
  STRUCT('nwd_einstein_223330d5', 'conversion', 'conversions4', 'conversion4', 'pending'),
  STRUCT('nwd_einstein_223330d5', 'conversion', 'conversions5', 'conversion5', 'pending')
])
