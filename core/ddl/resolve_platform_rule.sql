-- core.resolve_platform_rule(client_id, platform_from, formato, as_of_date) -> platform_to
-- Funcao SQL reutilizavel que encapsula "buscar a regra de remapeamento de
-- plataforma vigente numa data especifica" em core.advertiser_platform_rules,
-- mesma motivacao de core.resolve_dict_format.sql (ver esse arquivo pro
-- historico completo do bug do ROW_NUMBER e das limitacoes de SQL UDF em
-- BigQuery que levaram a este desenho).
--
-- Retorna NULL se nao houver regra vigente (cliente sem regra cadastrada
-- pra essa combinacao platform_from+formato, ou data anterior a
-- effective_from da regra) -- o chamador deve fazer
-- COALESCE(resolve_platform_rule(...), platform_original) pra manter o
-- comportamento default (nao reescreve platform quando nao ha regra).

CREATE OR REPLACE FUNCTION `adframework.core.resolve_platform_rule`(
  p_client_id STRING, p_platform_from STRING, p_formato STRING, p_as_of_date DATE
)
RETURNS STRING
AS ((
  SELECT MIN(platform_to)
  FROM `adframework.core.advertiser_platform_rules`
  WHERE client_id = p_client_id
    AND platform_from = p_platform_from
    AND formato = UPPER(p_formato)
    AND effective_from <= p_as_of_date
    AND (effective_to IS NULL OR p_as_of_date < effective_to)
));
