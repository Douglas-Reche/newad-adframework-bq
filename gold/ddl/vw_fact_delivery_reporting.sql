-- gold.vw_fact_delivery_reporting
-- Grain: igual fact_delivery (client_id + day + platform + formato + goal_type)
--
-- SIMPLIFICADA em 2026-08-15 (promocao do mecanismo de override historico
-- generico para producao, task Notion "Regras de Negocio Configuraveis por
-- Cliente -- Cap 20% Impressoes"): ate aqui esta view tinha o hardcode
-- `client_id = 'banco_cora_fe13d78a' AND day < '2026-07-01'` cravado no SQL,
-- substituindo esses dias pelo valor de `core.historical_overrides_delivery`
-- (tabela antiga, ja stub/0 linhas). Desde 2026-08-05,
-- `gold.fact_delivery` ja resolve isso sozinha via
-- `core.resolve_reporting_source()` (ver gold/ddl/fact_delivery.sql, 4o
-- branch do UNION ALL lendo `stg.historical_overrides_delivery`) -- entao
-- esta view pode virar um passthrough puro, sem reimplementar a logica de
-- override aqui.
--
-- `core.historical_overrides_delivery` (tabela antiga, pre-migracao) NAO e
-- mais referenciada por esta view -- fica como stub historico (0 linhas em
-- producao), decisao de descomissiona-la ou nao fica fora do escopo desta
-- mudanca.
--
-- Power BI deve continuar lendo daqui (nao de fact_delivery direto) --
-- nenhuma mudanca de contrato de leitura pro consumidor, so a origem do dado
-- de override que mudou de "hardcode nesta view" para "resolvido em
-- fact_delivery via core.resolve_reporting_source()".

CREATE OR REPLACE VIEW `adframework.gold.vw_fact_delivery_reporting` AS
SELECT * FROM `adframework.gold.fact_delivery`;
