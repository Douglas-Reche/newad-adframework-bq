-- core.vw_delivery_unattributed
-- Observabilidade do que gold.fact_delivery descarta silenciosamente.
--
-- gold/ddl/fact_delivery.sql termina em `WHERE client_id IS NOT NULL` —
-- entrega sem client_id resolvido some do Gold sem contador nem alerta
-- (achado #1 da auditoria de consistência 2026-07-29). Esta view espelha
-- exatamente o mesmo UNION de gold.fact_delivery, mas filtra o lado
-- oposto (client_id IS NULL) e agrega por dia/plataforma, para dar
-- visibilidade ao volume perdido sem alterar o comportamento do Gold.
--
-- Não substitui stg.unresolved_client_links (que lista vínculos de
-- CADASTRO pendentes) — esta view mostra VOLUME de entrega já ocorrida
-- que não tem para onde ir.

CREATE OR REPLACE VIEW `adframework.core.vw_delivery_unattributed` AS
WITH unioned AS (
  SELECT date AS day, 'mediasmart' AS platform, client_id, impressions, clicks
  FROM `adframework.stg.ms_delivery`

  UNION ALL

  SELECT date AS day, 'mgid' AS platform, client_id, impressions, clicks
  FROM `adframework.stg.mg_delivery`

  UNION ALL

  SELECT date AS day, 'siprocal' AS platform, client_id, impressions, clicks
  FROM `adframework.stg.sp_delivery`
)
SELECT
  day,
  platform,
  COUNT(*) AS rows_unattributed,
  SUM(impressions) AS impressions_lost,
  SUM(clicks) AS clicks_lost
FROM unioned
WHERE client_id IS NULL
GROUP BY day, platform
ORDER BY day DESC, platform;
