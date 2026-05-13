-- Amostras das tabelas do Admin UI (raw_newadframework)

-- 1. io_manager_v2: estrutura de um IO completo
SELECT io_id, proposal_id, newad_client_id, advertiser_id, advertiser,
  platform, platform_campaign_id, platform_line_item_id,
  line_id, line_number, line_item,
  buying_model, proposal_month, line_status
FROM `adframework.raw_newadframework.io_manager_v2`
ORDER BY proposal_month DESC
LIMIT 10;

-- 2. io_line_bindings_v2: como as campanhas são vinculadas
SELECT io_id, line_id, newad_client_id, platform,
  platform_entity_id, platform_campaign_id, platform_strategy_id,
  binding_scope, link_status, start_date, end_date, proposal_month
FROM `adframework.raw_newadframework.io_line_bindings_v2`
ORDER BY proposal_month DESC
LIMIT 10;

-- 3. platform_client_links: mapeamento cliente → conta na plataforma
SELECT newad_client_id, client_name, advertiser_id,
  platform, link_value, link_label, status
FROM `adframework.raw_newadframework.platform_client_links`
ORDER BY newad_client_id, platform;
