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
-- ============================================================================
-- ACHADO 2026-08-10 (task "Materializar base de fact_pacing na STG" --
-- resultado PARCIAL, nao o esperado -- ver relato completo da task no
-- Notion): materializar pacing_base em stg.fact_pacing_base (tabela fisica)
-- NAO foi suficiente para permitir a chamada DIRETA de
-- core.resolve_client_business_rule() abaixo. O erro "Correlated
-- subqueries that reference other tables are not supported unless they can
-- be de-correlated" CONTINUA acontecendo -- reproduzido com uma query
-- minima (SELECT client_id, day, resolve_client_business_rule(...) FROM
-- stg.fact_pacing_base LIMIT 5, SEM nenhuma CTE/UNION/JOIN alem da propria
-- tabela fisica), testado ao vivo contra douglas-bq-staging.
--
-- Root cause real (mais especifico do que o "DESVIO DELIBERADO" documentado
-- aqui ate 2026-08-10, que atribuia o erro ao UNION ALL/FULL OUTER JOIN a
-- montante -- essa hipotese NAO se sustentou: o erro reproduz mesmo sem
-- nenhum UNION/JOIN no caminho): dentro de
-- core/ddl/resolve_client_business_rule.sql, o ARRAY_AGG usa
-- `ORDER BY CASE WHEN client_id = p_client_id THEN 0 ELSE 1 END ASC` --
-- essa expressao de ORDER BY referencia o PARAMETRO CORRELACIONADO
-- (p_client_id) da funcao, nao so o WHERE. Confirmado isolando com 2
-- TEMP FUNCTIONs identicas em estrutura: uma variante com agregacao simples
-- (ANY_VALUE/MIN, sem referenciar o parametro correlacionado no ORDER BY)
-- funciona perfeitamente contra a mesma stg.fact_pacing_base; a variante
-- IDENTICA ao corpo real de resolve_client_business_rule (ARRAY_AGG com
-- ORDER BY CASE WHEN client_id = p_client_id ...) falha com o MESMO erro,
-- mesmo como TEMP FUNCTION sem nenhuma tabela gold/UNION/JOIN envolvida.
-- resolve_dict_format/resolve_platform_rule (as outras 2 resolve_*, que
-- funcionam direto em fact_io_plan.sql) NAO tem esse padrao -- usam
-- MIN()/ANY_VALUE() simples, sem referenciar o parametro correlacionado
-- dentro do ORDER BY de uma agregacao.
--
-- Por isso o workaround abaixo (rule_candidates/rule_resolved, JOIN real +
-- ARRAY_AGG) CONTINUA em uso -- nao foi removido, ao contrario do que a
-- task pretendia. A materializacao de stg.fact_pacing_base ainda TROUXE um
-- ganho real (a CTE local pacing_base virou uma leitura simples de tabela,
-- sem o FULL OUTER JOIN/io_agg inline nesta view -- mais simples e mais
-- barato de reprocessar), mas NAO resolveu o desvio do ADR-0001 -- ele
-- continua sendo um desvio deliberado, agora por um motivo mais preciso e
-- documentado. Corrigir de fato exigiria reescrever
-- core.resolve_client_business_rule() para nao referenciar o parametro
-- correlacionado dentro do ORDER BY (ex: 2 chamadas separadas -- uma so
-- para o override do cliente, outra so para a regra geral -- com COALESCE
-- entre elas, cada uma com agregacao simples) -- fora de escopo desta task,
-- reportado como proximo passo pro usuario decidir.
-- ============================================================================

CREATE OR REPLACE VIEW `adframework.gold.fact_pacing` AS
WITH pacing_base AS (
  SELECT *
  FROM `adframework.stg.fact_pacing_base`
),
-- rule_candidates/rule_resolved: reimplementa resolve_client_business_rule
-- como JOIN real + ARRAY_AGG (ver ACHADO 2026-08-10 acima -- a chamada
-- direta da funcao continua falhando com "Correlated subqueries..." mesmo
-- depois da materializacao, por um motivo diferente do que se pensava
-- originalmente). Mesma condicao de vigencia e mesma prioridade
-- (client_id especifico > geral, effective_from DESC como desempate) da
-- funcao original -- ver core/ddl/resolve_client_business_rule.sql.
rule_candidates AS (
  SELECT
    pb.client_id,
    pb.day,
    r.rule_params,
    CASE WHEN r.client_id = pb.client_id THEN 0 ELSE 1 END AS specificity,
    r.effective_from
  FROM (
    SELECT DISTINCT client_id, day
    FROM pacing_base
    WHERE client_id IS NOT NULL AND day IS NOT NULL
  ) pb
  JOIN `adframework.core.client_business_rules` r
    ON r.rule_type = 'impression_cap_pct'
    AND (r.client_id = pb.client_id OR r.client_id IS NULL)
    AND r.effective_from <= pb.day
    AND (r.effective_to IS NULL OR pb.day < r.effective_to)
),
rule_resolved AS (
  SELECT
    client_id,
    day,
    ARRAY_AGG(
      rule_params ORDER BY specificity ASC, effective_from DESC LIMIT 1
    )[OFFSET(0)] AS resolved_rule_params
  FROM rule_candidates
  GROUP BY client_id, day
),
pacing_with_rule AS (
  SELECT
    pb.*,
    rr.resolved_rule_params
  FROM pacing_base pb
  LEFT JOIN rule_resolved rr
    ON pb.client_id = rr.client_id
    AND pb.day = rr.day
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
      AND LOWER(formato) IN UNNEST(JSON_VALUE_ARRAY(resolved_rule_params, '$.strategies')) AS rule_applies,
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
