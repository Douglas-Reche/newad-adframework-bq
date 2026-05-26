-- raw.mgid_creatives
-- Metadata de teasers/criativos do MGID.
-- Grain: id (teaserid)
-- Fonte: API MGID /goodhits/clients/{client_id}/teasers — carga periódica
-- Chave de join com raw.mgid_delivery: id = teaserid

CREATE OR REPLACE TABLE `adframework.raw.mgid_creatives`
(
  id                        STRING,    -- teaserid
  campaign_id               STRING,    -- campaignid pai
  title                     STRING,    -- título do teaser
  advert_text               STRING,    -- texto do anúncio
  url                       STRING,    -- URL de destino
  image_link                STRING,    -- URL da imagem
  ad_type                   STRING,    -- tipo (native, push, etc.)
  category                  STRING,    -- categoria
  status                    STRING,    -- status (active, paused, etc.)
  call_to_action            STRING,
  good_price                STRING,    -- lance sugerido
  currency                  STRING,
  preview_links             STRING,    -- links de preview (JSON serializado)
  price_of_click_by_locations STRING, -- preço por localização (JSON serializado)
  statistics                STRING,    -- estatísticas (JSON serializado)
  conversion                STRING,    -- dados de conversão (JSON serializado)
  blocked_by                STRING,    -- razão de bloqueio se houver
  who_add                   STRING,    -- quem criou

  -- Metadados de ingestão
  raw_ingested_at           TIMESTAMP
)
OPTIONS (
  description = 'Metadata de teasers/criativos MGID. id = teaserid. Chave de join com mgid_delivery quando teaserid disponível.'
);
