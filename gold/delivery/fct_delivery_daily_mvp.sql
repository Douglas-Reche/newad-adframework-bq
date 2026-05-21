-- =============================================================================
-- gold.fct_delivery_daily_mvp
-- =============================================================================
-- Fixed version of gold.fct_delivery_daily. Differences from the original:
--
--   1. Excludes nwd_internal_newad (phantom client — shares MS account with
--      Luckbet, has 0 real impressions but pollutes every client list).
--
--   2. Removes the hard binding_scope = 'campaign' filter — replaced with
--      a priority: campaign-scope wins over strategy-scope for the same
--      (date, platform_campaign_id, newad_client_id) via ROW_NUMBER.
--      This recovers impressions from strategy-scoped bindings that were
--      previously invisible in the original view.
--
--   3. Keeps the existing dedup logic (latest proposal_month wins) so
--      overlapping IOs for the same campaign don't double-count.
--
-- KNOWN REMAINING LIMITATIONS (require Shiro / Admin UI fixes):
--   - Cora:        IO dates cover March only → use fct_cora_delivery_full.sql
--   - Dr. Consulta: IO dates cover Feb-Mar only → prior history missing
--   - TecPar:      advertiser_id split (tecpar vs nwd_tec-par_4ee38788)
--                  → inconsistent in IO bindings, fix in Admin UI
--   - Luckbet:     ~122% of raw due to overlapping IO bindings across 7 IOs
--   - Stocco:      zero IOs → zero gold data
-- =============================================================================

WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY date, platform_campaign_id, newad_client_id
      ORDER BY
        -- Prefer campaign-scope over strategy-scope
        CASE binding_scope WHEN 'campaign' THEN 0 ELSE 1 END,
        -- Among same scope, prefer most recent IO
        proposal_month DESC
    ) AS _rn
  FROM `adframework.share.io_calc_daily_v4`
  WHERE platform_campaign_id IS NOT NULL
    -- Exclude known phantom / legacy clients
    AND newad_client_id NOT IN (
      'nwd_luckbet_69e72f18',  -- legacy Luckbet account, no real delivery
      'nwd_internal_newad'     -- phantom: shares MS account with Luckbet, 0 real impressions
    )
)

SELECT
  date,
  io_id,
  proposal_id,
  newad_client_id,
  nwd_adv_id,
  advertiser,
  advertiser_id,
  product,
  campaign_name,
  campaign_type,
  line_id,
  line_number,
  line_item,
  line_status,
  platform,
  binding_scope,
  platform_campaign_id,
  platform_campaign_name,
  platform_strategy_id,
  platform_strategy_name,
  proposal_month,
  buying_model,
  buying_value,
  deliverable_metric,
  deliverable_volume,
  start_date,
  end_date,
  -- Planned (from IO schedule)
  planned_budget_daily,
  planned_volume_daily,
  planned_volume_total,
  budget_total,
  -- Delivered
  impressions,
  clicks,
  video_start,
  video_completed,
  conversions1,
  conversions2,
  conversions3,
  conversions4,
  conversions5,
  realized_volume,
  pacing_ratio
FROM ranked
WHERE _rn = 1
