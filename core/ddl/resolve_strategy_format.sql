-- core.resolve_strategy_format(strategy_name, as_of_date) -> formato
-- Funcao SQL reutilizavel que encapsula "classificar o formato de uma
-- strategy_name de texto livre usando as keywords vigentes numa data
-- especifica" em core.strategy_format_map -- mesma motivacao/padrao de
-- core.resolve_dict_format.sql e core.resolve_platform_rule.sql (ver esses
-- arquivos pro historico completo do bug do ROW_NUMBER e das limitacoes de
-- SQL UDF em BigQuery que levaram a esse desenho -- LIMIT 1 em subquery
-- correlacionada nao decorrelaciona, MIN/agregacao decorrelaciona).
--
-- Regra de desempate quando mais de uma keyword vigente aparece dentro de
-- strategy_name (ex: "Retargeting Display" contem tanto 'retargeting' quanto
-- 'display'): vence a keyword que aparece na posicao mais a ESQUERDA dentro
-- do texto (STRPOS menor). Empate de posicao (nunca visto nos dados reais,
-- mas coberto por seguranca): desempate alfabetico por formato, pra
-- determinismo. Essa regra foi escolhida por reproduzir, pra todas as 27
-- combinacoes reais de strategy_name em douglas-bq-staging.stg.io_plan
-- (validado 2026-09-07, 0 divergencias), o mesmo resultado que o CASE WHEN
-- hardcoded antigo dava com sua ordem de prioridade fixa (native, video,
-- retargeting, display, push, appinstall) -- nos dados reais a keyword de
-- maior prioridade no CASE antigo sempre tambem era a que aparecia mais a
-- esquerda no texto, entao as duas regras coincidem. Se um strategy_name
-- futuro quebrar essa coincidencia, a REGRA (posicao no texto) e a fonte de
-- verdade daqui pra frente, nao a ordem antiga do CASE (que deixou de
-- existir).
--
-- Tres tentativas anteriores FALHARAM em producao (testado 2026-09-07):
-- (1) ARRAY_AGG(... ORDER BY ... LIMIT 1)[SAFE_OFFSET(0)] -- ORDER BY +
--     LIMIT dentro do ARRAY_AGG nao decorrelacionou ("Correlated subqueries
--     that reference other tables are not supported...").
-- (2) Duas agregacoes MIN() encadeadas via subquery correlacionada no WHERE
--     -- mesmo erro (a subquery interna, mesmo sendo ela propria uma
--     agregacao simples, ainda contava como correlacionada ao ser
--     referenciada de dentro do WHERE da agregacao externa).
-- (3) MIN(STRUCT(pos, formato)).formato -- erro DIFERENTE: "MIN is not
--     defined for arguments of type STRUCT<...>" (BigQuery nao suporta
--     MIN/MAX sobre STRUCT, mesmo com campos todos orderable).
--
-- Solucao que funciona: UMA UNICA agregacao MIN() sobre STRING (mesma
-- classe de expressao simples que MIN(goal_type)/MIN(platform_to) ja usam
-- nas funcoes irmas -- sem ORDER BY, sem LIMIT, sem subquery aninhada, sem
-- STRUCT). A posicao (STRPOS) e o formato sao empacotados numa unica string
-- ordenavel ("posicao com zero-padding | formato"), MIN() escolhe a menor
-- (menor posicao primeiro, empate resolvido alfabeticamente pelo formato
-- que vem depois do separador), e SPLIT extrai o formato de volta.
--
-- Retorna NULL se nenhuma keyword vigente na data aparecer dentro de
-- strategy_name -- o chamador (stg.io_plan) trata NULL como "nao
-- classificado ainda", nao como erro.

CREATE OR REPLACE FUNCTION `adframework.core.resolve_strategy_format`(
  p_strategy_name STRING, p_as_of_date DATE
)
RETURNS STRING
AS ((
  SELECT SPLIT(
    MIN(CONCAT(
      LPAD(CAST(STRPOS(LOWER(p_strategy_name), LOWER(keyword)) AS STRING), 6, '0'),
      '|', formato
    )),
    '|'
  )[SAFE_OFFSET(1)]
  FROM `adframework.core.strategy_format_map`
  WHERE effective_from <= p_as_of_date
    AND (effective_to IS NULL OR p_as_of_date < effective_to)
    AND STRPOS(LOWER(p_strategy_name), LOWER(keyword)) > 0
));
