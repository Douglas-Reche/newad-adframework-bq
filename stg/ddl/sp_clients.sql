-- stg.sp_clients
-- T1 STG Siprocal -- grain: 1 linha por client_name extraido e deduplicado.
-- Mesma logica do mg_advertisers (MGID), mas mais simples: ja 100% resolvido
-- em core.platform_client_links (link_type='advertiser', 11/11, sem gap operacional).
--
-- client_name extraido de raw.sp_delivery.campanha (2o segmento), padrao
-- {PREFIXO}_{CLIENTE}_{PAIS}_{PERIODO}. Sem variacao de grafia encontrada
-- (diferente da MGID) -- todos os 11 valores distintos batem 1:1 com
-- core.platform_client_links.

CREATE OR REPLACE VIEW `adframework.stg.sp_clients` AS
WITH extracted AS (
  SELECT
    SPLIT(campanha, '_')[OFFSET(1)] AS client_name
  FROM `adframework.raw.sp_delivery`
)
SELECT
  e.client_name,
  COUNT(*) AS campaign_count,
  pcl.client_id
FROM extracted e
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON pcl.link_value = e.client_name AND LOWER(pcl.platform) = 'siprocal'
GROUP BY e.client_name, pcl.client_id;
