-- core.resolve_platform_rule(client_id, platform_from, formato, as_of_date) -> platform_to
-- Funcao SQL reutilizavel que encapsula "buscar a regra de remapeamento de
-- plataforma vigente numa data especifica" em core.advertiser_platform_rules,
-- mesma motivacao de core.resolve_dict_format.sql (ver esse arquivo pro
-- historico completo do bug do ROW_NUMBER e das limitacoes de SQL UDF em
-- BigQuery que levaram a este desenho).
--
-- 2026-09-07 — Suporte a regra GERAL (client_id NULL), mesmo padrao de
-- prioridade que core.resolve_client_business_rule() ja resolve (ver
-- core/ddl/resolve_client_business_rule.sql para o historico completo da
-- investigacao original do bug de correlated subquery em SQL UDF do
-- BigQuery -- as mesmas limitacoes valem aqui, reaproveitado sem reinventar):
--   client_id NULL em advertiser_platform_rules == regra GERAL (vale para
--   todo client_id que nao tiver override especifico vigente na mesma data).
--   client_id preenchido == override ESPECIFICO daquele cliente. Quando as
--   duas estao vigentes na mesma as_of_date pro mesmo (platform_from, formato),
--   o override especifico vence -- exige ordenacao explicita de
--   especificidade, nao so "achar a vigente" (a versao anterior desta funcao
--   resolvia so 1 escopo, sem ambiguidade, entao nao precisava disso).
--
-- Solucao adotada (identica a resolve_client_business_rule, adaptada pra
-- retorno STRING em vez de JSON -- platform_to ja e STRING simples, sem
-- precisar de PARSE_JSON): codificar num UNICO MAX() (agregacao simples,
-- decorrelaciona em SQL UDF correlacionada -- ARRAY_AGG/ORDER BY/LIMIT NAO
-- decorrelacionam, ver resolve_client_business_rule.sql pro teste isolado
-- que confirmou a causa raiz) tanto a prioridade de escolha quanto o valor:
-- uma STRING de largura fixa nos primeiros 9 caracteres (1 digito de
-- especificidade + 8 digitos de data AAAAMMDD) seguida do platform_to sem
-- separador (nao precisa de separador porque o prefixo tem largura fixa
-- conhecida -- platform_to comeca sempre na posicao 10, SUBSTR(..., 10)).
-- MAX() dessa STRING escolhe a linha certa por comparacao lexicografica:
-- '1' (override do client_id pedido) bate '0' (regra geral) no primeiro
-- caractere; dentro da mesma especificidade, a data AAAAMMDD maior (versao
-- mais recente) vence.
--
-- IF(client_id = p_client_id, '1', '0'): quando client_id da linha e NULL
-- (regra geral), a comparacao `NULL = p_client_id` avalia NULL, e IF() trata
-- condicao NULL como falsa -- '0' e atribuido corretamente sem precisar de
-- COALESCE explicito.
--
-- Retorna NULL se nao houver regra vigente (geral OU especifica) pra essa
-- combinacao platform_from+formato+client_id na data -- o chamador deve
-- fazer COALESCE(resolve_platform_rule(...), platform_original) pra manter o
-- comportamento default (nao reescreve platform quando nao ha regra).
--
-- Validado contra dado real em douglas-bq-staging (2026-09-07): as 2 regras
-- existentes (Cora/Push->Siprocal, Casa do Construtor/Audio->MiQ, ambas
-- client_id especifico) resolvem identico a versao anterior da funcao --
-- 0 divergencias. Cenario sintetico de regra geral (client_id NULL) testado
-- e removido apos validar que resolve corretamente pra um client_id
-- qualquer sem override especifico.

CREATE OR REPLACE FUNCTION `adframework.core.resolve_platform_rule`(
  p_client_id STRING, p_platform_from STRING, p_formato STRING, p_as_of_date DATE
)
RETURNS STRING
AS ((
  SELECT SUBSTR(
    MAX(
      CONCAT(
        IF(client_id = p_client_id, '1', '0'),   -- especificidade: override do cliente ('1') vence sobre geral ('0')
        FORMAT_DATE('%Y%m%d', effective_from),    -- desempate defensivo: versao mais recente vence
        platform_to                               -- payload -- sem separador, prefixo tem largura fixa (9 chars)
      )
    ),
    10  -- 1 (especificidade) + 8 (AAAAMMDD) = 9 chars de prefixo; platform_to comeca na posicao 10
  )
  FROM `adframework.core.advertiser_platform_rules`
  WHERE platform_from = p_platform_from
    AND formato = UPPER(p_formato)
    AND (client_id = p_client_id OR client_id IS NULL)
    AND effective_from <= p_as_of_date
    AND (effective_to IS NULL OR p_as_of_date < effective_to)
));
