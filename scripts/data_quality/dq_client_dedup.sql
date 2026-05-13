-- DQ: Detecta clientes que compartilham a mesma conta de plataforma
-- Se dois newad_client_id têm o mesmo link_value na mesma plataforma = duplicata potencial
-- Resultado esperado limpo: nenhuma linha retornada

SELECT
  platform,
  link_value,
  STRING_AGG(newad_client_id ORDER BY newad_client_id) AS clientes_compartilham,
  STRING_AGG(client_name    ORDER BY newad_client_id) AS nomes,
  COUNT(*) AS qtd_clientes
FROM `adframework.raw_newadframework.platform_client_links`
WHERE status    =  'active'
  AND link_value IS NOT NULL
  AND link_value != ''
GROUP BY platform, link_value
HAVING COUNT(*) > 1
ORDER BY platform, link_value

-- Problema conhecido (2026-05-12):
-- mediasmart / newad_brazil-dzynxhmnrdg2ec0czgdiabqmwvy0qhgj
--   → nwd_luckbet_a485d6bc (canônico) + nwd_internal_newad (incorreto)
-- siprocal / luckbet
--   → nwd_luckbet_a485d6bc + nwd_luckbet_69e72f18 (legacy)
-- Ação necessária: corrigir link_value do nwd_internal_newad e desativar nwd_luckbet_69e72f18
