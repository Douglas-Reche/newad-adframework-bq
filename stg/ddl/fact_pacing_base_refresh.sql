-- REFRESH de stg.fact_pacing_base (nao e o schema -- ver
-- stg/ddl/fact_pacing_base.sql para o CREATE TABLE IF NOT EXISTS e o
-- raciocinio completo de por que esta materializacao existe).
--
-- Mecanismo: CREATE OR REPLACE TABLE ... AS SELECT -- escolhido em vez de
-- MERGE/DELETE+INSERT porque fact_pacing_base nao tem chave natural estavel
-- fora de (client_id, day, formato, platform) e o volume (agregado por
-- client+dia+formato+plataforma, nao por linha de evento) e pequeno o
-- suficiente pra recalcular por inteiro a cada refresh -- mais simples e
-- sem risco de dessincronizar com fact_io_plan/fact_delivery (nao ha
-- conceito de "delta" aqui, os dois lados podem mudar retroativamente
-- ambos). Mesmo padrao ja usado no repo para outras tabelas pequenas
-- reconstruidas por inteiro (ex: DELETE+INSERT de ms_campaigns) -- CTAS e a
-- forma mais direta de expressar "recalcula tudo" quando o resultado e uma
-- SELECT pura, sem exigir um DELETE explicito antes.
--
-- Aplicavel via apply_ddl.py, igual a qualquer outro DDL do repo (o script
-- reconhece "CREATE [OR REPLACE] TABLE" e trata este arquivo como o dono do
-- alvo `stg.fact_pacing_base` -- mesma tabela do arquivo de schema, dois
-- arquivos aplicaveis independentemente):
--   python scripts/deploy/apply_ddl.py stg/ddl/fact_pacing_base_refresh.sql \
--       --project douglas-bq-staging
--
-- Idempotente: rodar 2x seguidas produz o mesmo resultado (recalcula do
-- zero a cada vez a partir de gold.fact_io_plan/gold.fact_delivery, sem
-- acumular nem duplicar linha).
--
-- Agendamento automatico deste refresh (Cloud Scheduler ou equivalente) e
-- FORA DE ESCOPO desta task -- por ora, refresh manual sob demanda (rodar
-- de novo sempre que fact_io_plan ou fact_delivery mudarem e a leitura via
-- gold.fact_pacing precisar refletir o dado mais recente).
--
-- Logica idêntica a CTE `pacing_base` (+ CTE `io_agg` que a alimenta) que
-- existia em gold/ddl/fact_pacing.sql antes desta mudanca -- ver esse
-- arquivo (historico git) para o raciocinio completo de cada campo
-- (investimento_realizado, agregacao de io_agg antes do JOIN, etc.).
--
-- is_override / override.investimento (2026-08-11, task "Regras de Negocio
-- Configuraveis por Cliente -- Cap 20% Impressoes (Native/Push)", 2 lacunas
-- estruturais encontradas ao construir o cap): duas mudancas juntas --
--   1. is_override = adframework.core.resolve_reporting_source(client_id,
--      day, CURRENT_DATE()) = 'override' -- reaproveita a MESMA funcao ja
--      usada em gold/ddl/fact_delivery.sql (nao duplica a logica de range +
--      regra vigente). Calculada 1x por linha final (client_id/day ja
--      resolvidos via COALESCE), nao por lado do JOIN.
--   2. LEFT JOIN em stg.historical_overrides_delivery (mesma chave
--      client_id+day+formato+platform ja usada no FULL OUTER JOIN entre
--      io_agg e gold.fact_delivery acima -- confirmado em douglas-bq-staging
--      que client_id+day+platform+formato ja e chave suficiente, sem
--      duplicata, nesta tabela hoje; goal_type NAO entra na chave porque o
--      FULL OUTER JOIN principal (io_agg x fact_delivery) tambem nao usa
--      goal_type como chave -- so como coluna de saida via COALESCE) --
--      so pra expor `override.investimento`, a coluna NUMERIC que ja existia
--      em stg.historical_overrides_delivery mas nunca era lida por nada (ver
--      "Achado" no cabecalho de stg/ddl/historical_overrides_delivery.sql).
--      investimento_realizado passa a ser COALESCE(override.investimento,
--      <formula CPC/CPM original>) -- override com investimento preenchido
--      ganha prioridade; fora isso, comportamento identico ao anterior.
--
-- planned_* via override (2026-08-11, extensao da mudanca acima no mesmo
-- dia -- decisao revista: o lado PLANEJADO tambem pode vir do override, nao
-- so o realizado): planned_spend_daily, planned_impressions_daily,
-- planned_clicks_daily e unit_price no SELECT final passam a ser
-- COALESCE(ov.<campo>, j.<campo>) -- mesmo padrao ja usado pra
-- investimento_realizado (override tem prioridade quando preenchido, senao
-- mantem o que veio do IO Plan via io_agg/joined). As colunas
-- planned_impressions_daily/planned_clicks_daily/planned_spend_daily/
-- unit_price ja existiam em stg.historical_overrides_delivery (adicionadas
-- 2026-08-10), hoje sempre NULL pra todo mundo -- COALESCE cai no valor do
-- IO Plan ate a primeira carga real de override com esses campos
-- preenchidos. LEFT JOIN em stg.historical_overrides_delivery e o mesmo ja
-- usado acima (nao duplicado).

CREATE OR REPLACE TABLE `adframework.stg.fact_pacing_base` AS
WITH io_agg AS (
  SELECT
    client_id,
    report_date,
    formato,
    platform,
    goal_type,
    IF(COUNT(DISTINCT unit_price) = 1, ANY_VALUE(unit_price), NULL) AS unit_price,
    SUM(planned_spend_daily)       AS planned_spend_daily,
    SUM(planned_impressions_daily) AS planned_impressions_daily,
    SUM(planned_clicks_daily)      AS planned_clicks_daily
  FROM `adframework.gold.fact_io_plan`
  GROUP BY client_id, report_date, formato, platform, goal_type
),
joined AS (
  SELECT
    COALESCE(p.client_id, d.client_id) AS client_id,
    COALESCE(p.report_date, d.day) AS day,
    COALESCE(p.formato, d.formato) AS formato,
    COALESCE(p.platform, d.platform) AS platform,
    p.planned_spend_daily,
    p.planned_impressions_daily,
    p.planned_clicks_daily,
    p.unit_price,
    COALESCE(p.goal_type, d.goal_type) AS goal_type,
    d.impressions AS realized_impressions,
    d.clicks AS realized_clicks,
    d.conversions AS realized_conversions,
    CASE COALESCE(p.goal_type, d.goal_type)
      WHEN 'CPC' THEN d.clicks * p.unit_price
      WHEN 'CPM' THEN SAFE_DIVIDE(d.impressions * p.unit_price, 1000)
      ELSE NULL
    END AS investimento_realizado_formula
  FROM io_agg p
  FULL OUTER JOIN `adframework.gold.fact_delivery` d
    ON p.client_id = d.client_id
    AND p.report_date = d.day
    AND UPPER(p.formato) = UPPER(d.formato)
    AND p.platform = d.platform
  WHERE COALESCE(p.client_id, d.client_id) IS NOT NULL
    AND COALESCE(p.report_date, d.day) IS NOT NULL
)
SELECT
  j.client_id,
  j.day,
  j.formato,
  j.platform,
  COALESCE(ov.planned_spend_daily, j.planned_spend_daily) AS planned_spend_daily,
  COALESCE(ov.planned_impressions_daily, j.planned_impressions_daily) AS planned_impressions_daily,
  COALESCE(ov.planned_clicks_daily, j.planned_clicks_daily) AS planned_clicks_daily,
  COALESCE(ov.unit_price, j.unit_price) AS unit_price,
  j.goal_type,
  j.realized_impressions,
  j.realized_clicks,
  j.realized_conversions,
  COALESCE(ov.investimento, j.investimento_realizado_formula) AS investimento_realizado,
  `adframework.core.resolve_reporting_source`(j.client_id, j.day, CURRENT_DATE()) = 'override' AS is_override
FROM joined j
LEFT JOIN `adframework.stg.historical_overrides_delivery` ov
  ON ov.client_id = j.client_id
  AND ov.day = j.day
  AND UPPER(ov.formato) = UPPER(j.formato)
  AND UPPER(ov.platform) = UPPER(j.platform);
