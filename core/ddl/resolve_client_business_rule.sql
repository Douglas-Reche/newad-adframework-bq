-- core.resolve_client_business_rule(client_id, rule_type, as_of_date) -> rule_params (JSON)
-- Funcao SQL reutilizavel que encapsula "buscar a regra de negocio vigente
-- numa data especifica" em core.client_business_rules, mesma motivacao de
-- core.resolve_dict_format / core.resolve_platform_rule (ver
-- core/ddl/resolve_dict_format.sql pro historico completo do bug do
-- ROW_NUMBER e das limitacoes de SQL UDF em BigQuery que levaram a este
-- desenho -- as mesmas limitacoes valem aqui).
--
-- Prioridade de resolucao (diferenca em relacao as outras duas resolve_*):
-- client_id NULL na tabela representa a regra GERAL (vale pra todos os
-- clientes); client_id preenchido e um OVERRIDE especifico daquele cliente.
-- Quando as duas estao vigentes na mesma as_of_date pro mesmo rule_type,
-- o override especifico do cliente vence. Isso exige uma ordenacao
-- explicita de especificidade, nao so "achar a vigente" como nas outras
-- duas funcoes (que resolvem uma unica chave sem ambiguidade de escopo).
--
-- rule_params e JSON -- MIN()/MAX()/ANY_VALUE() (usados nas outras duas
-- resolve_* pra contornar a nao-decorrelacao de LIMIT 1 em subquery
-- correlacionada, ver resolve_dict_format.sql) nao se aplicam a JSON: o
-- BigQuery nao define ordenacao para MIN/MAX de JSON, e ANY_VALUE seria
-- nao-deterministico igual ja documentado, alem de nao dar pra expressar
-- "prefira o mais especifico" com uma agregacao de escolha arbitraria.
-- Solucao adotada, seguindo o mesmo principio (aggregation em vez de LIMIT 1
-- puro pra permitir decorrelacao): ARRAY_AGG(... ORDER BY ... LIMIT 1)
-- [OFFSET(0)] dentro do UDF -- e uma funcao de agregacao (decorrelaciona
-- normalmente) e o ORDER BY explicito garante determinismo, ordenando por
-- especificidade (cliente antes de geral) e, dentro da mesma
-- especificidade, pela versao mais recente (effective_from DESC) como
-- desempate defensivo caso exista mais de uma linha vigente por engano.
-- ARRAY_AGG sobre zero linhas retorna NULL, e indexar [OFFSET(0)] de um
-- array NULL tambem retorna NULL (nao lanca erro) -- mesmo contrato de
-- "retorna NULL se nao houver regra vigente" das outras resolve_*.
--
-- Retorna NULL se nao houver regra (geral ou especifica) vigente pra esse
-- (client_id, rule_type) na data -- o chamador deve tratar NULL como "regra
-- nao configurada" (ex: nao aplicar nenhum teto).

CREATE OR REPLACE FUNCTION `adframework.core.resolve_client_business_rule`(
  p_client_id STRING, p_rule_type STRING, p_as_of_date DATE
)
RETURNS JSON
AS ((
  SELECT ARRAY_AGG(
    rule_params
    ORDER BY
      CASE WHEN client_id = p_client_id THEN 0 ELSE 1 END ASC,  -- especifico do cliente vence sobre o geral
      effective_from DESC                                        -- desempate defensivo: versao mais recente
    LIMIT 1
  )[OFFSET(0)]
  FROM `adframework.core.client_business_rules`
  WHERE rule_type = p_rule_type
    AND (client_id = p_client_id OR client_id IS NULL)
    AND effective_from <= p_as_of_date
    AND (effective_to IS NULL OR p_as_of_date < effective_to)
));
