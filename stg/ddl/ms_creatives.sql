-- stg.ms_creatives (T5)
-- Dimensão de criativos MediaSmart.
-- Grain: 1 linha por creative_id único.
-- Fonte: raw.mediasmart_creatives (WRITE_TRUNCATE)
--
-- Nota sobre os dados (verificado 2026-06-12):
--   34.438 linhas totais, 4.434 IDs únicos → fator ~7.8× de duplicação (WRITE_APPEND histórico)
--   PK real = `id` (sempre preenchido). `creative_id` = igual ao `id` quando presente, mas
--   NULL em 33.250 linhas — não usar `creative_id` como PK.
--   Muitos criativos têm campaign_id = NULL (sem vínculo de campanha ativo).
--   O campo `creative` (JSON) contém dimensões físicas (width, height).
--
-- Depende de: stg.ms_campaigns (para resolver ms_client_id)
-- NÃO substitui nenhuma view existente — view nova.

CREATE OR REPLACE VIEW `adframework.stg.ms_creatives` AS
SELECT
  cr.id                                                                AS ms_creative_id,
  cr.campaign_id                                                       AS ms_campaign_id,
  c.ms_client_id,
  cr.name                                                              AS creative_name,
  cr.type                                                              AS creative_type,
  SAFE_CAST(JSON_VALUE(cr.creative, '$.creative.width')  AS INT64)    AS size_width,
  SAFE_CAST(JSON_VALUE(cr.creative, '$.creative.height') AS INT64)    AS size_height,
  cr.thumbnail_url                                                     AS image_url,
  SAFE_CAST(cr.updated_at AS TIMESTAMP)                               AS updated_at
FROM (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY id
      ORDER BY SAFE_CAST(updated_at AS TIMESTAMP) DESC
    ) AS rn
  FROM `adframework.raw.mediasmart_creatives`
  WHERE id IS NOT NULL
) cr
LEFT JOIN `adframework.stg.ms_campaigns` c ON c.ms_campaign_id = cr.campaign_id
WHERE cr.rn = 1;
