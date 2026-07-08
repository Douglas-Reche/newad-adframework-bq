-- stg.mg_teasers
-- T3 STG MGID -- grain: 1 linha por creative_id (teaser).
-- Sem client_id aqui (principio "resolve uma vez so") -- quem precisar junta
-- com stg.mg_campaigns pelo campaign_id.
--
-- size: '1280x720' fixo -- width/height ja vem fixo pelo comercial na RAW
-- (MGID nao expoe resolucao por teaser na API).

CREATE OR REPLACE VIEW `adframework.stg.mg_teasers` AS
SELECT
  creative_id,
  campaign_id,
  creative_name,
  status,
  url,
  thumbnail_url,
  advert_text,
  call_to_action,
  width,
  height,
  '1280x720' AS size
FROM `adframework.raw.mg_teasers`;
