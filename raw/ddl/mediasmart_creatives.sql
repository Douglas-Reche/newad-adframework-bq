-- raw.mediasmart_creatives
-- Metadata de criativos da MediaSmart.
-- Grain: creative_id
-- Fonte: API MediaSmart /api/campaign/{id}/creative — carga periódica
-- Chave de join: campaign_id = controlid em mediasmart_delivery

CREATE OR REPLACE TABLE `adframework.raw.mediasmart_creatives`
(
  creative_id     STRING,    -- ID do criativo (id na API)
  campaign_id     STRING,    -- controlid da campanha pai
  name            STRING,    -- nome do criativo
  type            STRING,    -- tipo (banner, native, video, etc.)
  thumbnail_url   STRING,
  image_url       STRING,
  description     STRING,
  creative        STRING,    -- payload completo do criativo (JSON serializado)
  created_at      STRING,
  updated_at      STRING,

  -- Metadados de ingestão
  raw_ingested_at TIMESTAMP
)
OPTIONS (
  description = 'Metadata de criativos MediaSmart. creative_id é a chave. campaign_id = controlid em mediasmart_delivery.'
);
