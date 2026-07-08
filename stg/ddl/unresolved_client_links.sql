-- stg.unresolved_client_links
-- View de monitoramento: lista toda entidade nativa (advertiser/campanha) que aparece
-- na RAW de alguma plataforma mas NAO tem vinculo em core.platform_client_links.
-- Uso: checklist manual para o time comercial/Douglas preencherem o vinculo.
-- Nao e fato de delivery -- e ferramenta operacional, fora do fluxo T1-T7.
--
-- Criada em 2026-06-24 apos auditoria mostrar:
--   MS: 8/21 advertisers sem vinculo (62% resolvido)
--   MGID: 47/173 campanhas sem vinculo (73% resolvido)
--   Siprocal: 0/11 sem vinculo (100% resolvido -- referencia de "bem mantido")
--
-- Causa raiz identificada: nao e bug tecnico -- e atraso operacional (cliente
-- existe em core.dim_client mas campanha nova nao foi vinculada) ou cliente nunca
-- cadastrado (sem nenhuma entrada em core.dim_client ainda).

-- Coluna suggested_client_id: NAO e vinculo automatico -- e so uma sugestao por
-- fuzzy-match de texto (nome nativo <-> core.dim_client.name) para acelerar o
-- preenchimento manual. MGID nao tem ID de advertiser nativo (confirmado
-- exaustivamente, ver CHANGELOG.md/stg_layer_design.md) -- a sugestao usa o
-- primeiro segmento do campaign_name (split por '|' ou '-') como aproximacao.

CREATE OR REPLACE VIEW `adframework.stg.unresolved_client_links` AS

WITH unresolved AS (
  -- MediaSmart: event_id sem vinculo
  SELECT
    'mediasmart' AS platform,
    'eventid' AS link_type_expected,
    a.event_id AS native_id,
    a.name AS native_name,
    NULL AS category_or_status,
    a.name AS name_for_match
  FROM `adframework.raw.ms_advertisers` a
  LEFT JOIN `adframework.core.platform_client_links` pcl
    ON pcl.link_value = a.event_id AND LOWER(pcl.platform) = 'mediasmart'
  WHERE pcl.client_id IS NULL

  UNION ALL

  -- MGID: campaign_id sem vinculo -- sem ID de advertiser nativo (ver nota acima),
  -- usa o 1o segmento do campaign_name (antes de '|' ou '-') como aproximacao
  SELECT
    'mgid' AS platform,
    'campaignid' AS link_type_expected,
    mc.campaign_id AS native_id,
    mc.campaign_name AS native_name,
    mc.status_name AS category_or_status,
    TRIM(SPLIT(REPLACE(mc.campaign_name, '-', '|'), '|')[OFFSET(0)]) AS name_for_match
  FROM `adframework.raw.mg_campaigns` mc
  LEFT JOIN `adframework.core.platform_client_links` pcl
    ON pcl.link_value = mc.campaign_id AND LOWER(pcl.platform) = 'mgid'
  WHERE pcl.client_id IS NULL

  UNION ALL

  -- Siprocal: client_name parseado de campanha, sem vinculo
  SELECT
    'siprocal' AS platform,
    'advertiser' AS link_type_expected,
    client_name_parsed AS native_id,
    client_name_parsed AS native_name,
    NULL AS category_or_status,
    client_name_parsed AS name_for_match
  FROM (
    SELECT DISTINCT SPLIT(campanha, '_')[OFFSET(1)] AS client_name_parsed
    FROM `adframework.raw.sp_delivery`
  ) sp
  LEFT JOIN `adframework.core.platform_client_links` pcl
    ON pcl.link_value = sp.client_name_parsed AND LOWER(pcl.platform) = 'siprocal'
  WHERE pcl.client_id IS NULL
)

SELECT
  u.platform,
  u.link_type_expected,
  u.native_id,
  u.native_name,
  u.category_or_status,
  (
    SELECT STRING_AGG(DISTINCT dc.client_id)
    FROM `adframework.core.dim_client` dc
    -- guarda de tamanho minimo: evita match espurio quando o segmento extraido
    -- e curto/numerico (ex: prefixos "1 - ", "2 - " de nomeacao sequencial)
    WHERE LENGTH(TRIM(u.name_for_match)) >= 4
      AND NOT REGEXP_CONTAINS(TRIM(u.name_for_match), r'^[0-9\s]+$')
      AND (
        LOWER(dc.name) LIKE CONCAT('%', LOWER(u.name_for_match), '%')
        OR LOWER(u.name_for_match) LIKE CONCAT('%', LOWER(dc.name), '%')
      )
  ) AS suggested_client_id
FROM unresolved u;
