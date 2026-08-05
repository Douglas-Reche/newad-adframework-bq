-- core.resolve_dict_format(platform, formato, as_of_date) -> goal_type
-- Funcao SQL reutilizavel que encapsula "buscar a regra vigente numa data
-- especifica" em core.dict_format, pra qualquer view que precise disso, em
-- vez de cada view reimplementar o JOIN + filtro de effective_from/
-- effective_to na mao (foi exatamente esse tipo de logica espalhada que quase
-- causou um bug real em gold/ddl/fact_io_plan.sql -- ver historico abaixo).
--
-- 2026-08-04 -- criada como parte da task Notion "Analisar resiliencia e
-- rastreabilidade da camada Gold" (passo 3), a pedido do usuario, depois de
-- uma primeira tentativa de repetir o JOIN versionado em cada view ter
-- revelado um bug real de nao-determinismo (ROW_NUMBER() OVER() como chave
-- sintetica numa CTE referenciada 3x -- BigQuery nao garante materializacao
-- unica de CTE, e ROW_NUMBER sem ORDER BY nao tem ordem estavel entre
-- rematerializacoes).
--
-- Limitacoes reais do BigQuery confirmadas empiricamente antes de escrever
-- esta funcao (nao assumidas):
--   1. SQL UDF com LIMIT 1 na subquery interna NAO decorrelaciona -- erro
--      "Correlated subqueries that reference other tables are not supported
--      unless they can be de-correlated". Preciso usar uma funcao de
--      agregacao (MIN/MAX/ANY_VALUE) em vez de LIMIT 1 pra o BigQuery
--      conseguir reescrever a chamada como JOIN + GROUP BY internamente.
--   2. ANY_VALUE() e explicitamente nao-deterministico entre execucoes
--      diferentes da mesma query quando ha empate -- usar MIN() em vez disso
--      (determinismo garantido; hoje so existe 1 linha por
--      (platform, formato) vigente por vez, entao MIN==ANY_VALUE em valor,
--      mas MIN e reprodutivel).
--
-- Retorna NULL se nao houver regra vigente pra (platform, formato) na data
-- (formato inexistente no dicionario, ou data anterior a qualquer
-- effective_from cadastrado).

CREATE OR REPLACE FUNCTION `adframework.core.resolve_dict_format`(
  p_platform STRING, p_formato STRING, p_as_of_date DATE
)
RETURNS STRING
AS ((
  SELECT MIN(goal_type)
  FROM `adframework.core.dict_format`
  WHERE platform = p_platform
    AND UPPER(formato) = UPPER(p_formato)
    AND effective_from <= p_as_of_date
    AND (effective_to IS NULL OR p_as_of_date < effective_to)
));
