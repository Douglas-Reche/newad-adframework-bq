-- core.vw_platform_campaign_links
-- View de conveniência: expõe os vínculos platform_client_links do tipo
-- 'campaignid' (MGID) num formato que o Power BI consegue consumir sem
-- o mismatch de schema causado pelo grain genérico de platform_client_links.
--
-- Criada ao vivo no BigQuery em 2026-07-29 (sessão de auditoria de
-- consistência) para resolver erro de schema no Power BI da Cora.
-- Este DDL foi commitado retroativamente na mesma sessão, lendo a
-- definição real via core.INFORMATION_SCHEMA.VIEWS — sincroniza o git
-- com o que já estava rodando, não altera comportamento.
--
-- Fonte: core.platform_client_links, filtrado a link_type = 'campaignid'.

CREATE OR REPLACE VIEW `adframework.core.vw_platform_campaign_links` AS
SELECT
  client_id,
  platform,
  link_value AS platform_campaign_id,
  link_type,
  status,
  notes
FROM `adframework.core.platform_client_links`
WHERE link_type = 'campaignid';
