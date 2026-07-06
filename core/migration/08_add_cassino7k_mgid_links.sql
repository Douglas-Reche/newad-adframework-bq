-- core.platform_client_links — Migração: Passo 8
-- Adiciona 4 campanhas MGID do Cassino 7K sem link (identificadas em auditoria de linhagem 2026-07-06).
-- Executado via insert_rows_json em 2026-07-06.
-- Impacto: gold.dim_campaign.client_id resolvido para as 4 campanhas CassinoPix;
--          NULL client_id em gold.dim_campaign: 5 → 1 (Teste-Newad, conta interna, esperado).

INSERT INTO `adframework.core.platform_client_links`
  (platform, link_type, link_value, client_id, status, notes, created_at)
SELECT 'mgid', 'campaignid', link_value, 'cassino_7k_393b3d2e', 'active', notes, '2026-07-06'
FROM UNNEST([
  STRUCT('12060613' AS link_value, 'CassinoPix - Mar 07-31 (product/Native). Confirmado por auditoria de linhagem 2026-07-06.' AS notes),
  STRUCT('12078840', 'CassinoPix - Mar 25-31 Push. Confirmado por auditoria de linhagem 2026-07-06.'),
  STRUCT('12083629', 'CassinoPix - Abril 01-30 (product/Native). Confirmado por auditoria de linhagem 2026-07-06.'),
  STRUCT('12083632', 'CassinoPix - Abril 01-31 Push. Confirmado por auditoria de linhagem 2026-07-06.')
]);
