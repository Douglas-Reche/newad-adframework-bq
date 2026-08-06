-- core.resolve_reporting_source(client_id, day, as_of_date) -> 'override' | 'platform'
-- Funcao SQL reutilizavel que encapsula "esse client_id+dia deve reportar o
-- historico manual ou o dado real da plataforma", pra qualquer view que
-- precise disso (comecando por gold.fact_delivery), em vez de cada view
-- reimplementar a logica de range + regra vigente na mao. Mesmo estilo de
-- core.resolve_dict_format / core.resolve_platform_rule.
--
-- Criada em 2026-08-05 (task "Ambientes Staging x Produção") para
-- generalizar o hardcode hoje existente em gold.vw_fact_delivery_reporting
-- (client_id = 'banco_cora_fe13d78a' AND day < '2026-07-01' cravado no SQL).
--
-- Regra (nessa ordem):
--   1. Sem linha SCD2-vigente em core.client_reporting_source_config para
--      esse client_id na data as_of_date, OU override_active = false
--      -> 'platform'.
--   2. Com override_active = true E day dentro do range real
--      (MIN(day)..MAX(day)) de stg.historical_overrides_delivery para
--      esse client_id -> 'override'.
--   3. Fora desse range (mesmo com override_active = true) -> 'platform'
--      (o override so cobre os dias que de fato foram carregados; fora
--      disso o dado real da plataforma e a unica fonte).
--
-- 2026-08-06 -- REESCRITA (bug bloqueante confirmado em teste ponta-a-ponta
-- contra douglas-bq-staging): a versao anterior funcionava isolada
-- (client_id constante), mas quebrava com "Correlated subqueries that
-- reference other tables are not supported unless they can be
-- de-correlated" quando chamada do jeito que gold/ddl/fact_delivery.sql de
-- fato chama -- correlacionada por linha, dentro do WHERE, com
-- client_id/date vindo de uma tabela externa (stg.ms_delivery etc.).
--
-- Causa raiz confirmada: a versao anterior tinha 2 CTEs (`vigente`,
-- `range_real`), cada uma um SELECT numa tabela diferente, e o SELECT final
-- referenciava essas CTEs atraves de 3 subqueries escalares SEPARADAS
-- (`(SELECT MAX(...) FROM vigente)`, `(SELECT min_day FROM range_real)`,
-- `(SELECT max_day FROM range_real)`) dentro do IF/AND. Isso e uma
-- correlacao de 2 niveis (SELECT final correlacionado -> CTE correlacionada
-- -> tabela) que o BigQuery nao consegue decorrelacionar automaticamente em
-- JOIN, mesmo cada subquery isolada sendo valida. Diferente de
-- core.resolve_dict_format/core.resolve_platform_rule, que funcionam porque
-- sao UM UNICO SELECT flat (1 nivel de correlacao: SELECT MIN(...) FROM
-- <tabela> WHERE <parametros>).
--
-- Fix aplicado: achatar para UM UNICO SELECT flat (1 nivel), com as duas
-- tabelas combinadas via LEFT JOIN dentro do MESMO FROM, e a decisao
-- calculada com agregacao (LOGICAL_OR/MIN/MAX) sobre esse JOIN -- mesmo
-- padrao estrutural de resolve_dict_format, generalizado para 2 tabelas em
-- vez de 1. Testado e confirmado em douglas-bq-staging (query correlacionada
-- real, WHERE + SELECT, cliente com override dentro/fora do range e
-- cliente sem nenhuma linha em historical_overrides_delivery) -- ver
-- CHANGELOG.md para a evidencia completa.
--
-- Nota sobre a agregacao sem GROUP BY: quando FROM ov WHERE ov.client_id =
-- p_client_id nao encontra nenhuma linha (cliente sem override cadastrado),
-- a query ainda retorna exatamente 1 linha (semantica padrao de agregacao
-- sem GROUP BY sobre 0 linhas -- MIN/MAX/LOGICAL_OR retornam NULL, nunca 0
-- linhas), entao o COALESCE(..., FALSE) sempre resolve para 'platform' --
-- a funcao nunca retorna NULL nem lanca erro de "0 rows", preservando a
-- garantia de saida documentada abaixo.
--
-- Limitacoes conhecidas do BigQuery (mesmas ja documentadas em
-- resolve_dict_format.sql, reaplicadas aqui):
--   - Nao usar LIMIT 1 em subquery correlacionada dentro do corpo da UDF
--     (nao decorrelaciona).
--   - Nao usar ANY_VALUE (nao-deterministico em empate) -- usar MIN/MAX/
--     LOGICAL_OR. LOGICAL_OR(override_active) e usado aqui porque, no caso
--     (que nao deveria acontecer, mas nao e garantido pelo schema) de mais
--     de uma linha vigente simultanea para o mesmo client_id, o
--     comportamento mais conservador e priorizar TRUE (expor o override) --
--     a ambiguidade em si deve ser corrigida na fonte via SCD2, nao aqui.
--
-- Retorna 'platform' (nunca NULL) em qualquer caso sem regra/sem dado --
-- saida padrao segura, ver core/ddl/client_reporting_source_config.sql.

CREATE OR REPLACE FUNCTION `adframework.core.resolve_reporting_source`(
  p_client_id STRING, p_day DATE, p_as_of_date DATE
)
RETURNS STRING
AS ((
  SELECT
    IF(
      COALESCE(LOGICAL_OR(cfg.override_active), FALSE)
        AND p_day >= MIN(ov.day)
        AND p_day <= MAX(ov.day),
      'override',
      'platform'
    )
  FROM `adframework.stg.historical_overrides_delivery` AS ov
  LEFT JOIN `adframework.core.client_reporting_source_config` AS cfg
    ON cfg.client_id = ov.client_id
    AND cfg.effective_from <= p_as_of_date
    AND (cfg.effective_to IS NULL OR p_as_of_date < cfg.effective_to)
  WHERE ov.client_id = p_client_id
));
