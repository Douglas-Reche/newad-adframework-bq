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
-- Depende de: nenhuma view STG (fonte direta da RAW)
-- NÃO substitui nenhuma view existente — view nova.

CREATE OR REPLACE VIEW `adframework.stg.ms_creatives` AS
SELECT
  id                                                                   AS ms_creative_id,
  campaign_id                                                          AS ms_campaign_id,
  name                                                                 AS ms_creative_name,
  type                                                                 AS creative_type,
  SAFE_CAST(JSON_VALUE(creative, '$.creative.width')  AS INT64)       AS size_width,
  SAFE_CAST(JSON_VALUE(creative, '$.creative.height') AS INT64)       AS size_height,
  thumbnail_url,
  SAFE_CAST(updated_at AS TIMESTAMP)                                   AS updated_at
FROM (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY id
      ORDER BY SAFE_CAST(updated_at AS TIMESTAMP) DESC
    ) AS rn
  FROM `adframework.raw.mediasmart_creatives`
  WHERE id IS NOT NULL
)
WHERE rn = 1;
