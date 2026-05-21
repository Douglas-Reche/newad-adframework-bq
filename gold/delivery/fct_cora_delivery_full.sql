-- =============================================================================
-- gold.fct_cora_delivery_full
-- =============================================================================
-- MVP workaround for Cora delivery gap.
--
-- ROOT CAUSE: Standard pipeline (fct_delivery_daily) shows only ~823K for Cora
-- because the single March 2026 IO covers only that month, so the INNER JOIN
-- on start_date/end_date drops all other delivery. Additionally, MGID and
-- Siprocal have advertiser_platform_id = NULL, so link_value joins never fire.
--
-- THIS VIEW uses three attribution paths:
--   A) MediaSmart  → join via platform_client_links.link_value = advertiser_platform_id
--   B) MGID/Siprocal registered → join via io_binding_registry_v4 campaign_id
--   C) MGID/Siprocal unregistered → hardcoded campaign IDs not yet in the IO registry
--
-- NUMBERS (Jan–May 2026 vs dashboard 15.6M):
--   PATH A MediaSmart:            11.17M
--   PATH B MGID (registered):      1.62M  (campaign 12368531, March IO)
--   PATH B Siprocal (registered):  0.01M  (spr_bancocora_30, March IO)
--   PATH C MGID (unregistered):    1.36M  (4 campaigns, March only)
--   PATH C Siprocal (unregistered):0.26M  (spr_bancocora_20261 Jan + spr_bancocora_20262 Feb)
--   Subtotal:                     ~14.4M  — remaining ~1.2M gap requires Shiro
--                                           to add IO bindings for pre-March campaigns
--
-- PERMANENT FIX (needs Shiro / Admin UI):
--   Create IO bindings for all MGID and Siprocal Cora campaigns from Aug 2025
--   so the main pipeline captures full history automatically.
-- =============================================================================

WITH

-- PATH A: MediaSmart — attributed via advertiser_platform_id = link_value
mediasmart_delivery AS (
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
    ON  l.newad_client_id = 'nwd_banco-cora_acfae3ab'
    AND l.platform        = d.platform
    AND l.link_value      = d.advertiser_platform_id
    AND LOWER(COALESCE(l.status, 'active')) = 'active'
  LEFT JOIN `adframework.core.io_binding_registry_v4` b
    ON  b.newad_client_id      = 'nwd_banco-cora_acfae3ab'
    AND b.platform             = d.platform
    AND b.platform_campaign_id = d.platform_campaign_id
    AND d.date BETWEEN b.start_date AND b.end_date
    AND LOWER(COALESCE(b.link_status, 'active')) = 'active'
    AND (
      b.binding_scope != 'strategy'
      OR COALESCE(b.platform_strategy_id, '') = COALESCE(d.platform_strategy_id, '')
    )
),

-- PATH B: MGID + Siprocal campaigns registered in io_binding_registry_v4
-- advertiser_platform_id is NULL for these platforms, so must join via campaign_id
mgid_siprocal_registered AS (
  SELECT DISTINCT
    LOWER(TRIM(platform)) AS platform,
    platform_campaign_id,
    io_id,
    line_id,
    proposal_id,
    binding_scope
  FROM `adframework.core.io_binding_registry_v4`
  WHERE newad_client_id = 'nwd_banco-cora_acfae3ab'
    AND LOWER(TRIM(platform)) IN ('mgid', 'siprocal')
    AND platform_campaign_id IS NOT NULL
    AND LOWER(COALESCE(link_status, 'active')) = 'active'
),

mgid_siprocal_registered_delivery AS (
  SELECT
    d.date,
    d.platform,
    d.advertiser_platform_id,
    d.platform_campaign_id,
    d.platform_campaign_name,
    d.platform_strategy_id,
    d.platform_strategy_name,
    b.io_id,
    b.line_id,
    b.proposal_id,
    b.binding_scope,
    TRUE AS is_io_attributed,
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
  INNER JOIN mgid_siprocal_registered b
    ON  b.platform             = d.platform
    AND b.platform_campaign_id = d.platform_campaign_id
  GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12
),

-- PATH C: MGID + Siprocal campaigns NOT yet registered in the IO registry.
-- These are known Cora campaigns confirmed in newad_operational_daily that lack
-- IO bindings. To be replaced with proper bindings in the registry once Shiro
-- extends the IO to cover all campaign history.
mgid_siprocal_unregistered AS (
  SELECT
    d.date,
    d.platform,
    d.advertiser_platform_id,
    d.platform_campaign_id,
    d.platform_campaign_name,
    d.platform_strategy_id,
    d.platform_strategy_name,
    CAST(NULL AS STRING) AS io_id,
    CAST(NULL AS STRING) AS line_id,
    CAST(NULL AS STRING) AS proposal_id,
    CAST(NULL AS STRING) AS binding_scope,
    FALSE AS is_io_attributed,
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
  WHERE
    -- MGID campaigns not in io_binding_registry_v4
    (d.platform = 'mgid'     AND d.platform_campaign_id IN ('12368541','12368543','12368539','12368544'))
    -- Siprocal campaigns not in io_binding_registry_v4
    OR (d.platform = 'siprocal' AND d.platform_campaign_id IN ('spr_bancocora_20261','spr_bancocora_20262'))
  GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12
),

-- Combine all three paths
combined AS (
  SELECT
    date, platform, advertiser_platform_id, platform_campaign_id,
    platform_campaign_name, platform_strategy_id, platform_strategy_name,
    io_id, line_id, proposal_id, binding_scope, is_io_attributed,
    impressions, clicks, video_start, video_completion,
    conversions_1, conversions_2, conversions_3, conversions_4, conversions_5
  FROM mediasmart_delivery

  UNION ALL

  SELECT
    date, platform, advertiser_platform_id, platform_campaign_id,
    platform_campaign_name, platform_strategy_id, platform_strategy_name,
    io_id, line_id, proposal_id, binding_scope, is_io_attributed,
    impressions, clicks, video_start, video_completion,
    conversions_1, conversions_2, conversions_3, conversions_4, conversions_5
  FROM mgid_siprocal_registered_delivery

  UNION ALL

  SELECT
    date, platform, advertiser_platform_id, platform_campaign_id,
    platform_campaign_name, platform_strategy_id, platform_strategy_name,
    io_id, line_id, proposal_id, binding_scope, is_io_attributed,
    impressions, clicks, video_start, video_completion,
    conversions_1, conversions_2, conversions_3, conversions_4, conversions_5
  FROM mgid_siprocal_unregistered
)

SELECT
  date,
  platform,
  advertiser_platform_id,
  platform_campaign_id,
  platform_campaign_name,
  platform_strategy_id,
  platform_strategy_name,

  -- Client identity (fixed for this view)
  'nwd_banco-cora_acfae3ab'  AS newad_client_id,
  'Cora'                     AS advertiser,
  'cora'                     AS advertiser_id,

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
