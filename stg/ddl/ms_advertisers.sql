-- stg.ms_advertisers
-- T1 STG MediaSmart -- grain: 1 linha por event_id (advertiser nativo da MediaSmart).
-- Resolve client_id de negocio AQUI (mesmo ponto unico de resolucao usado em
-- stg.mg_advertisers/stg.sp_clients -- principio "resolve uma vez so", ver
-- stg_layer_design.md). Fatos de delivery (T4-T7) NAO repetem esse join.
--
-- Campos descartados (decisao de 2026-06-24, sem uso identificado):
--   id -- sufixo curto do event_id, nenhum join usa
--   sensitive_content -- STRING vazia em 100% das 21 linhas reais, sem valor de negocio
--
-- event_id (ID nativo da MediaSmart) != client_id (ID de negocio do core.dim_client).
-- Confirmado em 2026-06-24: 13/21 (62%) resolvidos via core.platform_client_links
-- (link_type='eventid'). Ver stg.unresolved_client_links para os 8 sem vinculo.

CREATE OR REPLACE VIEW `adframework.stg.ms_advertisers` AS
SELECT
  a.event_id,
  a.name              AS client_name_native,
  a.iab_category       AS category,
  a.domain,
  pcl.client_id,
  a.platform,
  SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ', a.raw_ingested_at) AS raw_ingested_at
FROM `adframework.raw.ms_advertisers` a
LEFT JOIN `adframework.core.platform_client_links` pcl
  ON pcl.link_value = a.event_id AND LOWER(pcl.platform) = 'mediasmart';
