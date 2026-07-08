-- stg.mg_advertisers
-- T1 STG MGID -- grain: 1 linha por advertiser_name extraido e deduplicado.
-- Resolve client_id de negocio AQUI (principio "resolve uma vez so" -- ver
-- stg_layer_design.md). MGID nao tem entidade "advertiser" nativa na API
-- (confirmado exaustivamente) -- extraido do campaign_name (texto livre).
--
-- Logica de extracao (testada e refinada contra as 173 campanhas reais):
-- 1. 1o segmento de campaign_name, separando por '|' ou '-'
-- 2. Exceção: se o 1o segmento for um prefixo generico (Brand, New Ad/NewAd, Push)
--    OU for puramente numerico (ex: "1 - PARDINI...", "2 - PARDINI..." --
--    numeracao sequencial de variantes da mesma campanha, nao e advertiser),
--    usar o 2o segmento. Sem essa exceção "Brand | Amigo | ..." extraia "Brand"
--    (53 campanhas erradas) em vez de "Amigo", e "1 - PARDINI..." extraia "1"
--    em vez de "PARDINI..." (2 grupos falsos "1"/"2" encontrados e corrigidos
--    em 2026-06-24).
--
-- Resolucao de client_id: herda de QUALQUER campanha do grupo que já tenha
-- vinculo individual em core.platform_client_links (link_type='campaignid',
-- 130+ linhas existentes) -- nao exige vinculo novo por advertiser_name.
-- Testado: 25/40 grupos resolvidos automaticamente assim, ZERO conflitos
-- (nenhum grupo tem 2 client_ids diferentes -- confirma que a extracao agrupa
-- corretamente o mesmo cliente real).

CREATE OR REPLACE VIEW `adframework.stg.mg_advertisers` AS
WITH segments AS (
  SELECT
    campaign_id,
    SPLIT(REPLACE(campaign_name, '-', '|'), '|') AS parts
  FROM `adframework.raw.mg_campaigns`
),
extracted AS (
  SELECT
    campaign_id,
    CASE
      WHEN (
        LOWER(TRIM(parts[OFFSET(0)])) IN ('brand', 'new ad', 'newad', 'push')
        OR REGEXP_CONTAINS(TRIM(parts[OFFSET(0)]), r'^[0-9]+$')
      ) AND ARRAY_LENGTH(parts) > 1
        THEN TRIM(parts[OFFSET(1)])
      ELSE TRIM(parts[OFFSET(0)])
    END AS advertiser_name
  FROM segments
),
resolved_per_campaign AS (
  SELECT e.campaign_id, e.advertiser_name, pcl.client_id
  FROM extracted e
  LEFT JOIN `adframework.core.platform_client_links` pcl
    ON pcl.link_value = e.campaign_id AND LOWER(pcl.platform) = 'mgid'
)
SELECT
  advertiser_name,
  COUNT(*) AS campaign_count,
  MIN(campaign_id) AS first_campaign_id,
  -- todos os client_id nao-nulos do grupo sao iguais (testado, 0 conflitos) --
  -- MAX() so para extrair o valor unico de forma segura
  MAX(client_id) AS client_id
FROM resolved_per_campaign
GROUP BY advertiser_name;
