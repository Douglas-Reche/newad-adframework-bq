-- raw.mediasmart_bid_supply
-- Dados de supply/leilão por hora da MediaSmart.
-- Grain: day + hour + eventid + controlid + strategyid + auction_type + publisher_id + iab_category
-- Fonte: job mediasmart_bid_supply_daily (orchestrator)
-- Atualização: diária (sob demanda / diagnóstico)

CREATE OR REPLACE TABLE `adframework.raw.mediasmart_bid_supply`
(
  -- Dimensões de tempo
  day             STRING    NOT NULL,  -- YYYY-MM-DD
  hour            STRING,              -- hora do dia (0-23)

  -- Dimensões de conta e campanha
  eventid         STRING,              -- ID da conta
  controlid       STRING,              -- ID da campanha
  strategyid      STRING,              -- ID da estratégia

  -- Dimensões de leilão
  auction_type    STRING,              -- tipo de leilão (open, deal, etc.)
  ad_exchange     STRING,              -- exchange de anúncio

  -- Dimensões de publisher
  publisher_id    STRING,
  publisher_name  STRING,
  publisher_domain STRING,
  publisher_url   STRING,

  -- Dimensões de categorização
  iab_category    STRING,
  iab_subcategory STRING,

  -- Métricas de leilão
  bid_offers      STRING,              -- lances ofertados
  bids            STRING,              -- lances enviados
  won             STRING,              -- lances ganhos
  media_cost      STRING,              -- custo de mídia (wonprice)
  total_bids_cost STRING,              -- custo total de lances

  -- Métricas de entrega (quando disponível)
  impressions     STRING,
  clicks          STRING,
  conversions_1   STRING,
  conversions_2   STRING,
  conversions_3   STRING,
  conversions_4   STRING,
  conversions_5   STRING,

  -- Metadados de ingestão
  platform        STRING,              -- sempre 'mediasmart'
  report_name     STRING,
  raw_ingested_at TIMESTAMP
)
PARTITION BY DATE(raw_ingested_at)
OPTIONS (
  description = 'Supply e leilão horário MediaSmart. Usado para diagnóstico de bid landscape e publisher mix.'
);
