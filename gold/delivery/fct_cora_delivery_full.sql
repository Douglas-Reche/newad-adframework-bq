-- =============================================================================
-- gold.fct_cora_delivery_full
-- =============================================================================
-- MVP workaround for Cora delivery gap.
--
-- PROBLEM: fct_delivery_daily only shows 823K impressions for Cora because:
--   1. The single IO (io_202603_nwd-banco-cora-acfae3ab_001) covers March 2026 only.
--   2. io_delivery_daily_v4 uses INNER JOIN with date BETWEEN start/end,
--      so Aug 2025 – Feb 2026 and Apr 2026+ delivery is dropped.
--   3. fct_delivery_daily also filters binding_scope = 'campaign', which
--      further excludes the strategy-scoped bindings (5.5M impressions).
--   Real raw delivery: ~68.9M impressions across 3 campaigns (Aug 2025 – May 2026).
--
-- THIS VIEW: bypasses the IO date restriction.
--   - Reads directly from share.newad_operational_daily using platform_client_links
--   - LEFT JOINs to io_binding_registry_v4 to add IO metadata where available
--   - Shows ALL delivery regardless of whether an IO binding covers that date
--
-- PERMANENT FIX (requires Shiro / Admin UI):
--   Extend IO dates or create IOs for Aug 2025 – present so the main
--   fct_delivery_daily pipeline picks up all campaigns correctly.
-- =============================================================================

WITH

-- All delivery rows attributed to Cora via platform_client_links
delivery AS (
  SELECT
    d.date,
    d.platform,
    d.advertiser_platform_id,
    d.platform_campaign_id,
    d.platform_campaign_name,
    d.platform_strategy_id,
    d.platform_strategy_name,
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
  INNER JOIN `adframework.core.platform_client_links` l
    ON  l.newad_client_id = 'nwd_banco-cora_acfae3ab'
    AND l.platform        = d.platform
    AND l.link_value      = d.advertiser_platform_id
    AND LOWER(COALESCE(l.status, 'active')) = 'active'
  GROUP BY 1, 2, 3, 4, 5, 6, 7
),

-- IO binding metadata — only where a binding covers that campaign
-- (used to enrich rows that fall within a binding window)
bindings AS (
  SELECT
    platform_campaign_id,
    platform_strategy_id,
    LOWER(TRIM(platform))  AS platform,
    io_id,
    line_id,
    proposal_id,
    binding_scope,
    start_date,
    end_date
  FROM `adframework.core.io_binding_registry_v4`
  WHERE newad_client_id = 'nwd_banco-cora_acfae3ab'
    AND LOWER(COALESCE(link_status, 'active')) = 'active'
    AND line_id IS NOT NULL
    AND platform_campaign_id IS NOT NULL
)

SELECT
  d.date,
  d.platform,
  d.advertiser_platform_id,
  d.platform_campaign_id,
  d.platform_campaign_name,
  d.platform_strategy_id,
  d.platform_strategy_name,

  -- Client identity
  'nwd_banco-cora_acfae3ab'  AS newad_client_id,
  'Cora'                     AS advertiser,
  'cora'                     AS advertiser_id,

  -- IO attribution (NULL when no binding covers this date)
  b.io_id,
  b.line_id,
  b.proposal_id,
  b.binding_scope,
  CASE
    WHEN b.io_id IS NOT NULL THEN TRUE
    ELSE FALSE
  END AS is_io_attributed,

  -- Metrics
  d.impressions,
  d.clicks,
  d.video_start,
  d.video_completion,
  d.conversions_1,
  d.conversions_2,
  d.conversions_3,
  d.conversions_4,
  d.conversions_5

FROM delivery d
LEFT JOIN bindings b
  ON  b.platform            = d.platform
  AND b.platform_campaign_id = d.platform_campaign_id
  AND d.date BETWEEN b.start_date AND b.end_date
  -- For strategy-scoped bindings, also match on strategy_id
  AND (
    b.binding_scope != 'strategy'
    OR COALESCE(b.platform_strategy_id, '') = COALESCE(d.platform_strategy_id, '')
  )
