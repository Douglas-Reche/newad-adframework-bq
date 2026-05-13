-- 3. Checar se o mesmo platform_campaign_id aparece em ambos os advertiser_ids no mesmo mês
SELECT
  proposal_month,
  platform_campaign_id,
  platform,
  COUNT(DISTINCT advertiser_id) AS advertiser_id_count,
  ARRAY_AGG(DISTINCT advertiser_id ORDER BY advertiser_id) AS advertiser_ids,
  ARRAY_AGG(DISTINCT io_id ORDER BY io_id) AS io_ids,
  ARRAY_AGG(DISTINCT newad_client_id ORDER BY newad_client_id) AS client_ids
FROM `adframework.gold.dim_io_line`
WHERE LOWER(newad_client_id) LIKE '%luckbet%'
  AND platform_campaign_id IS NOT NULL
GROUP BY proposal_month, platform_campaign_id, platform
HAVING COUNT(DISTINCT advertiser_id) > 1
ORDER BY proposal_month, platform_campaign_id
