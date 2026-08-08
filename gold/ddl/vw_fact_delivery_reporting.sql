-- gold.vw_fact_delivery_reporting
-- Grain: igual fact_delivery (client_id + day + platform + formato + goal_type)
-- View de apresentacao: substitui, por override, os dias de
-- banco_cora_fe13d78a anteriores a 2026-07-01 pelo valor de
-- core.historical_overrides_delivery. Fora desse intervalo/cliente, e um
-- passthrough puro de gold.fact_delivery.
--
-- Power BI deve ler daqui, nao de fact_delivery direto, para clientes com
-- override ativo (ver core/ddl/historical_overrides_delivery.sql e
-- core/ddl/resolve_reporting_source.sql, commit 98b8f50).
--
-- conversions: sempre NULL para as linhas vindas do override historico (a
-- fonte da Cora pre-07/2026 nao tem conversao confiavel).
--
-- Nota (2026-08-05, ver fact_delivery.sql): fact_delivery ja resolve
-- override via core.resolve_reporting_source() para as 4 fontes, entao esta
-- view poderia em tese ser simplificada para SELECT * FROM fact_delivery --
-- nao simplificada aqui, fora do escopo desta captura de DDL existente
-- (reproduz fielmente o que ja roda em producao).

CREATE OR REPLACE VIEW `adframework.gold.vw_fact_delivery_reporting` AS
SELECT client_id, day, platform, formato, goal_type, impressions, clicks, conversions
FROM `adframework.gold.fact_delivery`
WHERE NOT (client_id = 'banco_cora_fe13d78a' AND day < '2026-07-01')

UNION ALL

SELECT client_id, day, platform, formato, goal_type, impressions, clicks, CAST(NULL AS FLOAT64) AS conversions
FROM `adframework.core.historical_overrides_delivery`
WHERE client_id = 'banco_cora_fe13d78a' AND day < '2026-07-01';
