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
-- correlacionada, ver resolve_dict_format.sql) nao se aplicam DIRETO a JSON:
-- o BigQuery nao define ordenacao para MIN/MAX de JSON, e ANY_VALUE seria
-- nao-deterministico igual ja documentado, alem de nao dar pra expressar
-- "prefira o mais especifico" com uma agregacao de escolha arbitraria.
--
-- CORRIGIDO 2026-08-10 (ver ADR-0001; historico completo da investigacao no
-- cabecalho antigo de gold/ddl/fact_pacing.sql, ja substituido por esta
-- versao). A causa raiz documentada ate aqui passou por 2 hipoteses
-- INCORRETAS antes desta, cada uma descartada com teste isolado (TEMP
-- FUNCTION identica em estrutura, sem nenhuma tabela gold/UNION/JOIN
-- envolvida, testado ao vivo contra douglas-bq-staging):
--   1a hipotese (incorreta): o UNION ALL/FULL OUTER JOIN a montante em
--      fact_pacing.sql causava o erro -- descartada, o erro reproduz mesmo
--      chamando a funcao direto contra uma tabela fisica simples.
--   2a hipotese (incorreta): o ORDER BY CASE WHEN client_id = p_client_id
--      dentro do ARRAY_AGG referenciava o parametro correlacionado e por
--      isso nao decorrelacionava -- descartada por teste isolado: MESMO SEM
--      CASE nenhum (so ARRAY_AGG(coluna ORDER BY effective_from DESC LIMIT 1)
--      [OFFSET(0)], ORDER BY so por coluna, sem referenciar parametro algum),
--      o erro "Correlated subqueries that reference other tables are not
--      supported unless they can be de-correlated" persiste.
--   Causa raiz real (confirmada): ARRAY_AGG(... ORDER BY ... LIMIT ...)
--      dentro do corpo de uma SQL UDF chamada de forma correlacionada NUNCA
--      decorrelaciona em BigQuery, independente do que o ORDER BY referencia
--      -- so agregacoes "simples" (MIN/MAX/ANY_VALUE/SUM/COUNT, sem
--      ORDER BY/LIMIT) decorrelacionam. Testado tambem: COALESCE de 2
--      subqueries correlacionadas separadas (mesmo cada uma usando so
--      ANY_VALUE simples) tambem NAO decorrelaciona quando combinadas na
--      mesma expressao escalar -- so decorrelaciona quando ha exatamente 1
--      agregacao simples por chamada de funcao.
--
-- Solucao adotada: codificar num UNICO MAX() (agregacao simples de STRING,
-- decorrelaciona) tanto a prioridade de escolha quanto o payload JSON.
-- Constroi, por linha candidata, uma STRING de largura fixa nos primeiros 9
-- caracteres (1 digito de especificidade + 8 digitos de data AAAAMMDD)
-- seguida do JSON serializado (TO_JSON_STRING) sem separador -- nao precisa
-- de separador porque o prefixo tem largura fixa conhecida, entao o corpo
-- JSON comeca sempre na posicao 10 (SUBSTR(..., 10)), mesmo que o JSON em si
-- contenha qualquer caractere. MAX() dessa STRING escolhe naturalmente a
-- linha certa por comparacao lexicografica: '1' (override do client_id
-- pedido) bate '0' (regra geral) no primeiro caractere; dentro da mesma
-- especificidade, a data AAAAMMDD maior (mais recente) vence -- mesmo
-- desempate defensivo ("versao mais recente") da versao anterior. Depois
-- de MAX() escolher a STRING vencedora inteira, SUBSTR(..., 10) descarta o
-- prefixo de ordenacao e PARSE_JSON() reconstitui o JSON original.
--
-- MAX() sobre zero linhas retorna NULL; SUBSTR(NULL, 10) e PARSE_JSON(NULL)
-- tambem retornam NULL (nenhum lanca erro) -- mesmo contrato de "retorna
-- NULL se nao houver regra vigente" das outras resolve_*.
--
-- Retorna NULL se nao houver regra (geral ou especifica) vigente pra esse
-- (client_id, rule_type) na data -- o chamador deve tratar NULL como "regra
-- nao configurada" (ex: nao aplicar nenhum teto).

CREATE OR REPLACE FUNCTION `adframework.core.resolve_client_business_rule`(
  p_client_id STRING, p_rule_type STRING, p_as_of_date DATE
)
RETURNS JSON
AS ((
  SELECT PARSE_JSON(SUBSTR(
    MAX(
      CONCAT(
        IF(client_id = p_client_id, '1', '0'),           -- especificidade: override do cliente ('1') vence sobre geral ('0')
        FORMAT_DATE('%Y%m%d', effective_from),            -- desempate defensivo: versao mais recente vence
        TO_JSON_STRING(rule_params)                       -- payload -- sem separador, prefixo tem largura fixa (9 chars)
      )
    ),
    10  -- 1 (especificidade) + 8 (AAAAMMDD) = 9 chars de prefixo; JSON comeca na posicao 10
  ))
  FROM `adframework.core.client_business_rules`
  WHERE rule_type = p_rule_type
    AND (client_id = p_client_id OR client_id IS NULL)
    AND effective_from <= p_as_of_date
    AND (effective_to IS NULL OR p_as_of_date < effective_to)
));
