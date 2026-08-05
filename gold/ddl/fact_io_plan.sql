-- gold.fact_io_plan
-- Grain: client_id + report_date + formato + platform.
-- Expande cada linha de stg.io_plan (grain = voo) em 1 linha por dia de
-- calendario dentro do voo, distribuindo planned_spend/impressions/clicks
-- linearmente (/ flight_days).
--
-- platform entra na granularidade (alem de formato) -- CONFIRMADO contra
-- dado real 2026-06-24: client_id+formato+dia sozinho tem 212 dias com 2
-- unit_price/buy_model diferentes coexistindo (ex: TecPar "Push - MGID"
-- R$0,35 vs "Push - App Targeting SIPROCAL" R$0,80, rodando juntos em
-- jan-mar/2026 -- nao e erro, sao 2 estrategias/plataformas genuinamente
-- diferentes).
--
-- platform_resolved: PLATFORM_RULES do sync_drive mapeia Push como 'unknown'
-- por padrao (seguro globalmente). Para clientes onde confirmamos que o Push
-- roda em uma plataforma especifica, a regra fica em
-- core.advertiser_platform_rules (nao hardcoded aqui). Adicionar novas regras
-- naquela tabela seguindo o procedimento SCD2 descrito no proprio arquivo
-- (nao mais DELETE+INSERT total).
--
-- unit_price: trazido de volta (passthrough) -- usado em gold.fact_pacing
-- pra calcular investimento_realizado (impressions/clicks reais x preco).
--
-- goal_type: regra platform+formato via core.dict_format (igual ao pipeline
-- de entrega). NAO via buy_model da planilha (pouco confiavel).
-- Fallback: quando platform='unknown', busca goal_type so por formato -- mas
-- apenas se o resultado for inequivoco (o mesmo formato tem o mesmo goal_type
-- em todas as plataformas cadastradas, na data em questao). Se ambiguo, NULL.
--
-- 2026-08-04 -- SCD2 (task Notion "Analisar resiliencia e rastreabilidade da
-- camada Gold", passo 3): core.dict_format e core.advertiser_platform_rules
-- agora sao versionadas por effective_from/effective_to. Os 2 JOINs que
-- existiam aqui foram substituidos por chamadas as funcoes SQL reutilizaveis
-- core.resolve_dict_format / core.resolve_dict_format_fallback /
-- core.resolve_platform_rule (ver core/ddl/resolve_*.sql para o design
-- completo e o historico de decisao -- vira ADR). Cada uma resolve "qual e a
-- regra vigente nesta report_date" em vez de sempre pegar a mais recente --
-- assim uma regra nova so vale a partir da sua propria effective_from, sem
-- reinterpretar retroativamente dias ja reportados com a regra anterior.
--
-- Por que funcoes em vez de JOIN inline (como era antes): a primeira
-- tentativa de fazer o JOIN versionado inline nesta view (usando
-- ROW_NUMBER() OVER() como chave sintetica numa CTE referenciada 3x) causou
-- um bug real de nao-determinismo -- BigQuery nao garante materializar uma
-- CTE uma unica vez quando ela e referenciada em multiplos lugares, e
-- ROW_NUMBER() sem ORDER BY nao tem ordem estavel entre rematerializacoes.
-- Sintoma observado: 5.101 linhas viraram 5.925 com a MESMA soma total
-- (dado certo, particionado errado). As funcoes core.resolve_* isolam essa
-- logica, foram testadas exaustivamente (casos de borda + comparacao linha a
-- linha contra a view antiga com tolerancia de arredondamento, 0 divergencias
-- em multiplas execucoes) antes de entrarem aqui.
--
-- Hoje so existe 1 versao de cada regra (effective_from = 2025-01-01, sem
-- effective_to) em ambas as tabelas -- o resultado desta view e identico ao
-- de antes da mudanca (verificado).

CREATE OR REPLACE VIEW `adframework.gold.fact_io_plan` AS
WITH expanded AS (
  SELECT
    p.client_id,
    p.formato,
    COALESCE(
      `adframework.core.resolve_platform_rule`(p.client_id, p.platform, UPPER(p.formato), day),
      p.platform
    ) AS platform,
    p.unit_price,
    day AS report_date,
    p.planned_spend / p.flight_days AS planned_spend_daily,
    SAFE_DIVIDE(p.planned_impressions, p.flight_days) AS planned_impressions_daily,
    SAFE_DIVIDE(p.planned_clicks, p.flight_days) AS planned_clicks_daily
  FROM `adframework.stg.io_plan` p,
  UNNEST(GENERATE_DATE_ARRAY(p.flight_start, p.flight_end)) AS day
  WHERE p.client_id IS NOT NULL
),
with_goal AS (
  SELECT
    e.*,
    COALESCE(
      `adframework.core.resolve_dict_format`(e.platform, e.formato, e.report_date),
      `adframework.core.resolve_dict_format_fallback`(e.formato, e.report_date)
    ) AS goal_type
  FROM expanded e
)
SELECT
  client_id,
  report_date,
  formato,
  platform,
  unit_price,
  goal_type,
  SUM(planned_spend_daily)       AS planned_spend_daily,
  SUM(planned_impressions_daily) AS planned_impressions_daily,
  SUM(planned_clicks_daily)      AS planned_clicks_daily
FROM with_goal
GROUP BY client_id, report_date, formato, platform, unit_price, goal_type;
