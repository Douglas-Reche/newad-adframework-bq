-- stg.ms_creatives
-- T3 STG MediaSmart -- grain: 1 linha por creative_id (associacao criativo-strategy).
-- Sem client_id aqui (principio "resolve uma vez so") -- quem precisar junta
-- com stg.ms_campaigns pelo campaign_id.
--
-- size: CAST(FLOAT64 AS STRING) ja produz formato limpo sem ".0" quando nao
-- ha fracao (testado contra dado real 2026-06-24) -- sem necessidade de cast
-- intermediario pra INT64. Criativos "native" tem width/height = 0 (sem
-- dimensao fixa, esperado -- nao e bug).

CREATE OR REPLACE VIEW `adframework.stg.ms_creatives` AS
SELECT
  creative_id,
  campaign_id,
  creative_name,
  status,
  url,
  thumbnail_url,
  creative_type,
  width,
  height,
  CONCAT(CAST(width AS STRING), 'x', CAST(height AS STRING)) AS size
FROM `adframework.raw.ms_creatives`;
