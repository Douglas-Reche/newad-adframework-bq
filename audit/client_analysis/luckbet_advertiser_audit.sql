-- 1. Quais advertiser_ids existem para luckbet
SELECT
  newad_client_id,
  client_name,
  advertiser_id
FROM `adframework.gold.dim_client`
WHERE LOWER(newad_client_id) LIKE '%luckbet%'
ORDER BY newad_client_id, advertiser_id
