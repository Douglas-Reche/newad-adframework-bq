-- gold.fact_pacing
-- Grain: client_id + day + formato + platform.
-- Le o cruzamento planejado x realizado direto de stg.fact_pacing_base
-- (TABELA FISICA, ver stg/ddl/fact_pacing_base.sql) -- ate 2026-08-10 esse
-- cruzamento era uma CTE nesta propria view (FULL OUTER JOIN entre
-- gold.fact_io_plan e gold.fact_delivery, com uma CTE io_agg pre-agregando
-- gold.fact_io_plan antes do JOIN). Refresh de stg.fact_pacing_base e
-- stg/ddl/fact_pacing_base_refresh.sql, nao esta view.
--
-- client_id NAO remapeado aqui (TecPar/Amigo) -- diferente da versao
-- anterior. Decisao 2026-06-24: esse rollup fica para a hierarquia
-- pai-filho do Power BI (gold.dim_advertiser.parent_client_id), nao em SQL,
-- pra nao hardcodear regra de negocio que pode mudar (TecPar pode ganhar
-- outras sub-marcas no futuro).
--
-- investimento_realizado: calculado em stg.fact_pacing_base (nao aqui) --
-- cruza unit_price/goal_type (atributos do PLANO) com impressions/clicks
-- (atributos da ENTREGA) linha a linha, na mesma granularidade. Formula
-- confirmada pelo usuario 2026-07-08:
--   CPC: clicks realizadas x unit_price
--   CPM: impressions realizadas x unit_price x 1000
-- CPI (AppInstall) e outros goal_type sem formula confirmada -- fica NULL.
--
-- Principio de negocio confirmado (2026-06-16, mantido): cliente nunca ve
-- spend real da plataforma -- "investimento_realizado" aqui e uma metrica
-- nova (estimativa via preco do plano x volume real), nao o spend nativo
-- da API (que nao existe no pipeline -- fora de escopo do rebuild RAW).
--
-- Regra de negocio "impression_cap_pct" (Rafael via Douglas, 2026-08-09/10 --
-- task Notion "Regras de Negocio Configuraveis por Cliente -- Cap 20%
-- Impressoes (Native/Push)"): teto configuravel por cliente aplicado via
-- COLUNAS ADICIONAIS `business_rule_*`, NUNCA sobrescrevendo/capando as
-- colunas de dado bruto existentes acima (realized_impressions etc.
-- continuam mostrando sempre o valor real -- decisao registrada na sub-task
-- anterior, ver docs/gold_layer_design.md).
--
-- core.resolve_client_business_rule() e chamada DIRETO abaixo, sem desvio --
-- 2026-08-10, task "Corrigir core.resolve_client_business_rule() -- remover
-- desvio do ADR-0001". A causa raiz real (ARRAY_AGG(...ORDER BY...LIMIT...)
-- nunca decorrelaciona em BigQuery dentro de uma SQL UDF chamada de forma
-- correlacionada) foi corrigida reescrevendo a funcao pra usar uma unica
-- agregacao simples (MAX de STRING codificada) -- ver
-- core/ddl/resolve_client_business_rule.sql pro historico completo da
-- investigacao (2 hipoteses anteriores descartadas) e o desenho da solucao.

CREATE OR REPLACE VIEW `adframework.gold.fact_pacing` AS
WITH pacing_base AS (
  SELECT *
  FROM `adframework.stg.fact_pacing_base`
),
pacing_with_rule AS (
  SELECT
    pb.*,
    core.resolve_client_business_rule(pb.client_id, 'impression_cap_pct', pb.day) AS resolved_rule_params
  FROM pacing_base pb
),
rule_expanded AS (
  SELECT
    *,
    -- `IN UNNEST(...)` e operador de pertencimento em array, nao subquery --
    -- forma mais simples e sem risco de reintroduzir subquery correlacionada.
    -- Assume `rule_params.strategies` sempre em lowercase (convencao
    -- observada nos 4 casos de teste reais e no exemplo de
    -- core/ddl/client_business_rules.sql) -- so `formato` (que varia de
    -- caixa, ex: "Native"/"Push") precisa de LOWER().
    resolved_rule_params IS NOT NULL
      AND formato IS NOT NULL
      AND LOWER(formato) IN UNNEST(JSON_VALUE_ARRAY(resolved_rule_params, '$.strategies'))
      -- 2026-08-11 (task "Regras de Negocio Configuraveis por Cliente -- Cap
      -- 20% Impressoes (Native/Push)", 2a lacuna estrutural): regra de cap
      -- nunca se aplica a dia de override (historico manual). `is_override`
      -- vem de stg.fact_pacing_base (propagado via pb.* na CTE pacing_base
      -- acima) -- ver stg/ddl/fact_pacing_base_refresh.sql para o calculo.
      -- COALESCE(..., FALSE) porque is_override so existe a partir deste
      -- refresh -- uma linha antiga nunca reprocessada ficaria NULL, e NULL
      -- nao pode travar o cap por engano (fail-open pro cap, nao pro
      -- override).
      AND NOT COALESCE(is_override, FALSE) AS rule_applies,
    CAST(JSON_VALUE(resolved_rule_params, '$.threshold_pct') AS FLOAT64) AS rule_threshold_pct,
    COALESCE(JSON_VALUE(resolved_rule_params, '$.base_field'), 'realized_impressions') AS rule_base_field,
    COALESCE(JSON_VALUE(resolved_rule_params, '$.reference_field'), 'planned_impressions_daily') AS rule_reference_field
  FROM pacing_with_rule
),
rule_valued AS (
  SELECT
    *,
    -- `base_field`/`reference_field` (chaves opcionais em rule_params,
    -- ausentes nas regras de teste atuais e no exemplo padrao em
    -- core/ddl/client_business_rules.sql) escolhem QUAIS colunas de
    -- fact_pacing sao a base/referencia do teto -- generico entre os 7
    -- campos numericos ja expostos pelo hub (aba Regras de Negocio /
    -- Simulador de Impacto, ver hub/app.py FACT_PACING_FIELDS), nao
    -- hardcoded para impressoes. Ausencia de qualquer uma das duas chaves
    -- cai no default (realized_impressions / planned_impressions_daily) --
    -- mesmo fallback que hub/app.py aplica na exibicao (summarize_rule_params).
    -- BigQuery nao tem selecao dinamica de coluna por string em SQL puro;
    -- o mapeamento string->coluna abaixo (CASE) e a forma estatica de
    -- expressar essa genericidade sem SQL dinamico.
    CASE rule_base_field
      WHEN 'realized_impressions'       THEN realized_impressions
      WHEN 'realized_clicks'            THEN realized_clicks
      WHEN 'realized_conversions'       THEN realized_conversions
      WHEN 'investimento_realizado'     THEN investimento_realizado
      WHEN 'planned_impressions_daily'  THEN planned_impressions_daily
      WHEN 'planned_clicks_daily'       THEN planned_clicks_daily
      WHEN 'planned_spend_daily'        THEN planned_spend_daily
      ELSE NULL
    END AS rule_base_value,
    CASE rule_reference_field
      WHEN 'realized_impressions'       THEN realized_impressions
      WHEN 'realized_clicks'            THEN realized_clicks
      WHEN 'realized_conversions'       THEN realized_conversions
      WHEN 'investimento_realizado'     THEN investimento_realizado
      WHEN 'planned_impressions_daily'  THEN planned_impressions_daily
      WHEN 'planned_clicks_daily'       THEN planned_clicks_daily
      WHEN 'planned_spend_daily'        THEN planned_spend_daily
      ELSE NULL
    END AS rule_reference_value
  FROM rule_expanded
)
SELECT
  client_id,
  day,
  formato,
  platform,
  planned_spend_daily,
  planned_impressions_daily,
  planned_clicks_daily,
  unit_price,
  goal_type,
  realized_impressions,
  realized_clicks,
  realized_conversions,
  investimento_realizado,
  -- Colunas novas -- teto de regra de negocio ("impression_cap_pct"), NULL
  -- quando nao ha regra vigente pra este client_id+data, ou o formato desta
  -- linha nao esta em rule_params.strategies (ver comentario no topo).
  -- Formula: cap = referencia * (1 + threshold_pct/100); capped =
  -- MIN(base, cap) quando ha referencia (nao-NULL), senao base (sem teto
  -- quando nao ha o que comparar); excess = MAX(base - capped, 0).
  CASE WHEN rule_applies THEN rule_base_field END       AS business_rule_base_field,
  CASE WHEN rule_applies THEN rule_reference_field END  AS business_rule_reference_field,
  CASE WHEN rule_applies THEN rule_threshold_pct END    AS business_rule_threshold_pct,
  CASE WHEN rule_applies THEN rule_base_value END       AS business_rule_base_value,
  CASE WHEN rule_applies THEN rule_reference_value END  AS business_rule_reference_value,
  CASE WHEN rule_applies THEN
    rule_reference_value * (1 + rule_threshold_pct / 100)
  END AS business_rule_cap_value,
  CASE WHEN rule_applies THEN
    IF(rule_reference_value IS NULL, rule_base_value,
       LEAST(rule_base_value, rule_reference_value * (1 + rule_threshold_pct / 100)))
  END AS business_rule_capped_value,
  CASE WHEN rule_applies THEN
    GREATEST(
      rule_base_value - IF(rule_reference_value IS NULL, rule_base_value,
        LEAST(rule_base_value, rule_reference_value * (1 + rule_threshold_pct / 100))),
      0)
  END AS business_rule_excess
FROM rule_valued;
