-- =============================================================================
-- gold.fct_luckbet_delivery_full
-- =============================================================================
-- MVP workaround for Luckbet delivery data quality issues.
--
-- ROOT CAUSE: The standard pipeline (fct_delivery_daily / fct_delivery_daily_mvp)
-- produces unreliable numbers for Luckbet because:
--
--   1. Luckbet has TWO client IDs pointing to the same actual campaigns:
--        nwd_luckbet_a485d6bc (advertiser_id = adv_b559ffdcbd) — active account
--        nwd_luckbet_69e72f18 (advertiser_id = luckbet)        — legacy account
--
--   2. All 9 MGID campaign IDs are registered in io_binding_registry_v4 under
--      BOTH accounts → same physical delivery is counted twice (25.3M + 25.8M).
--
--   3. nwd_internal_newad shares the same MediaSmart link_value as
--      nwd_luckbet_a485d6bc → phantom rows pollute every query that doesn't
--      explicitly exclude it.
--
-- THIS VIEW uses two attribution paths:
--   A) MediaSmart + Siprocal → join via platform_client_links.link_value = advertiser_platform_id
--      (anchored to nwd_luckbet_a485d6bc only — nwd_luckbet_69e72f18 MS delivery is 0)
--   B) MGID → join via distinct campaign_ids from io_binding_registry_v4,
--      combining both Luckbet accounts and deduplicating at campaign level to
--      eliminate the double-count
--
-- NUMBERS (Aug 2025 – May 2026):
--   PATH A MediaSmart:   ~246M
--   PATH A Siprocal:      ~2.8M
--   PATH B MGID:          ~25.7M (unique campaigns, no double-count)
--   TOTAL:               ~274.5M
--
-- PERMANENT FIX (needs Shiro / Admin UI):
--   Merge the two Luckbet client IDs into one canonical account and remove
--   duplicate IO bindings. Set advertiser_id = 'luckbet' consistently.
-- =============================================================================

WITH

-- PATH A: MediaSmart + Siprocal — attributed via advertiser_platform_id = link_value
-- Anchored to nwd_luckbet_a485d6bc because:
--   - It has the correct MediaSmart link_value (newad_brazil-dzynxhmnrdg2ec0czgdiabqmwvy0qhgj)
--   - nwd_luckbet_69e72f18 MediaSmart link_value yields 0 real impressions
--   - nwd_internal_newad is excluded (phantom sharing same MS link_value)
mediasmart_siprocal_delivery AS (
  SELECT
    d.date,
    d.platform,
    d.advertiser_platform_id,
    d.platform_campaign_id,
    d.platform_campaign_name,
    d.platform_strategy_id,
    d.platform_strategy_name,
    -- IO attribution where available (LEFT JOIN — NULL when no binding covers date)
    b.io_id,
    b.line_id,
    b.proposal_id,
    b.binding_scope,
    CASE WHEN b.io_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_io_attributed,
    d.impressions,
    d.clicks,
    d.video_start,
    d.video_completion,
    d.conversions_1,
    d.conversions_2,
    d.conversions_3,
    d.conversions_4,
    d.conversions_5
  FROM `adframework.share.newad_operational_daily` d
  INNER JOIN `adframework.core.platform_client_links` l
    ON  l.newad_client_id = 'nwd_luckbet_a485d6bc'
    AND l.platform        = d.platform
    AND l.link_value      = d.advertiser_platform_id
    AND LOWER(COALESCE(l.status, 'active')) = 'active'
  LEFT JOIN `adframework.core.io_binding_registry_v4` b
    ON  b.newad_client_id      = 'nwd_luckbet_a485d6bc'
    AND b.platform             = d.platform
    AND b.platform_campaign_id = d.platform_campaign_id
    AND d.date BETWEEN b.start_date AND b.end_date
    AND LOWER(COALESCE(b.link_status, 'active')) = 'active'
    AND (
      b.binding_scope != 'strategy'
      OR COALESCE(b.platform_strategy_id, '') = COALESCE(d.platform_strategy_id, '')
    )
),

-- PATH B: MGID + Siprocal via IO registry campaign_ids.
-- Both platforms have advertiser_platform_id = NULL, so PATH A can't capture them.
-- MGID: same campaigns appear under both Luckbet account IDs → deduplicate by
--   taking distinct campaign_ids from EITHER account (union), then join once.
-- Siprocal: nwd_luckbet_69e72f18 uses a ghost campaign_id ('siprocal-pushapp')
--   that has no delivery; only nwd_luckbet_a485d6bc has the real campaign_ids.
luckbet_io_campaign_ids AS (
  SELECT DISTINCT
    platform,
    platform_campaign_id
  FROM `adframework.core.io_binding_registry_v4`
  WHERE platform = 'mgid'
    AND newad_client_id IN ('nwd_luckbet_a485d6bc', 'nwd_luckbet_69e72f18')
    AND platform_campaign_id IS NOT NULL
    AND LOWER(COALESCE(link_status, 'active')) = 'active'

  UNION DISTINCT

  SELECT DISTINCT
    platform,
    platform_campaign_id
  FROM `adframework.core.io_binding_registry_v4`
  WHERE platform = 'siprocal'
    AND newad_client_id = 'nwd_luckbet_a485d6bc'
    AND platform_campaign_id IS NOT NULL
    AND LOWER(COALESCE(link_status, 'active')) = 'active'
),

mgid_siprocal_io_delivery AS (
  SELECT
    d.date,
    d.platform,
    d.advertiser_platform_id,
    d.platform_campaign_id,
    d.platform_campaign_name,
    d.platform_strategy_id,
    d.platform_strategy_name,
    -- IO attribution from nwd_luckbet_a485d6bc (primary/active account)
    b.io_id,
    b.line_id,
    b.proposal_id,
    b.binding_scope,
    CASE WHEN b.io_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_io_attributed,
    SUM(d.impressions)       AS impressions,
    SUM(d.clicks)            AS clicks,
    SUM(d.video_start)       AS video_start,
    SUM(d.video_completion)  AS video_completion,
    SUM(d.conversions_1)     AS conversions_1,
    SUM(d.conversions_2)     AS conversions_2,
    SUM(d.conversions_3)     AS conversions_3,
    SUM(d.conversions_4)     AS conversions_4,
    SUM(d.conversions_5)     AS conversions_5
  FROM `adframework.share.newad_operational_daily` d
  INNER JOIN luckbet_io_campaign_ids ids
    ON  ids.platform             = d.platform
    AND ids.platform_campaign_id = d.platform_campaign_id
  LEFT JOIN `adframework.core.io_binding_registry_v4` b
    ON  b.newad_client_id      = 'nwd_luckbet_a485d6bc'
    AND b.platform             = d.platform
    AND b.platform_campaign_id = d.platform_campaign_id
    AND d.date BETWEEN b.start_date AND b.end_date
    AND LOWER(COALESCE(b.link_status, 'active')) = 'active'
  GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12
),

-- Combine both paths
combined AS (
  SELECT
    date, platform, advertiser_platform_id, platform_campaign_id,
    platform_campaign_name, platform_strategy_id, platform_strategy_name,
    io_id, line_id, proposal_id, binding_scope, is_io_attributed,
    impressions, clicks, video_start, video_completion,
    conversions_1, conversions_2, conversions_3, conversions_4, conversions_5
  FROM mediasmart_siprocal_delivery

  UNION ALL

  SELECT
    date, platform, advertiser_platform_id, platform_campaign_id,
    platform_campaign_name, platform_strategy_id, platform_strategy_name,
    io_id, line_id, proposal_id, binding_scope, is_io_attributed,
    impressions, clicks, video_start, video_completion,
    conversions_1, conversions_2, conversions_3, conversions_4, conversions_5
  FROM mgid_siprocal_io_delivery
)

SELECT
  date,
  platform,
  advertiser_platform_id,
  platform_campaign_id,
  platform_campaign_name,
  platform_strategy_id,
  platform_strategy_name,

  -- Canonical client identity (both legacy IDs map here)
  'nwd_luckbet_a485d6bc'  AS newad_client_id,
  'Luckbet'               AS advertiser,
  'luckbet'               AS advertiser_id,

  -- IO attribution metadata
  io_id,
  line_id,
  proposal_id,
  binding_scope,
  is_io_attributed,

  -- Metrics
  impressions,
  clicks,
  video_start,
  video_completion,
  conversions_1,
  conversions_2,
  conversions_3,
  conversions_4,
  conversions_5
FROM combined
