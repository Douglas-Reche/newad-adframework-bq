-- stg.mediasmart_bid_supply
-- Typing e normalização sobre raw.mediasmart_bid_supply.
-- Grain: day + hour + eventid + controlid + strategyid + auction_type + publisher_id

CREATE OR REPLACE VIEW `adframework.stg.mediasmart_bid_supply` AS
SELECT
  SAFE_CAST(day AS DATE)                      AS day,
  SAFE_CAST(hour AS INT64)                    AS hour,
  eventid,
  controlid,
  strategyid,
  auction_type,
  ad_exchange,
  publisher_id,
  publisher_name,
  publisher_domain,
  publisher_url,
  iab_category,
  iab_subcategory,
  SAFE_CAST(bid_offers       AS INT64)        AS bid_offers,
  SAFE_CAST(bids             AS INT64)        AS bids,
  SAFE_CAST(won              AS INT64)        AS won,
  SAFE_CAST(media_cost       AS FLOAT64)      AS media_cost,
  SAFE_CAST(total_bids_cost  AS FLOAT64)      AS total_bids_cost,
  SAFE_CAST(impressions      AS INT64)        AS impressions,
  SAFE_CAST(clicks           AS INT64)        AS clicks,
  SAFE_CAST(conversions_1    AS INT64)        AS conversions_1,
  SAFE_CAST(conversions_2    AS INT64)        AS conversions_2,
  SAFE_CAST(conversions_3    AS INT64)        AS conversions_3,
  SAFE_CAST(conversions_4    AS INT64)        AS conversions_4,
  SAFE_CAST(conversions_5    AS INT64)        AS conversions_5,
  platform,
  report_name,
  raw_ingested_at
FROM `adframework.raw.mediasmart_bid_supply`
WHERE day IS NOT NULL;
