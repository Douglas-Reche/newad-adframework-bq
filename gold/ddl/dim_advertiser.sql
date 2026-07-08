-- gold.dim_advertiser
-- Dimensao "filtro mae" do Power BI -- 1 linha por client_id, pra cada
-- dashboard (1 por cliente) travar o filtro nessa tabela e relacionar com
-- todas as fact tables (fact_pacing/fact_delivery/dim_campaign) por
-- client_id.
--
-- Expoe a hierarquia ja modelada em core.dim_client (parent_client_id/
-- client_level) -- ex: Amigo (nivel 2) e sub-cliente do TecPar (nivel 1).
-- NAO resolve o mapeamento Amigo->TecPar do fact_pacing aqui -- essa logica
-- e especifica do pacing (ver gold/ddl/fact_pacing.sql), dim_advertiser so
-- expoe a relacao real de cadastro.
--
-- Separado de core.dim_client por design: core.* e dataset de pipeline
-- (Admin UI/ETL), gold.* e dataset de consumo BI -- Power BI conecta so
-- aqui, sem precisar de acesso ao dataset core.

CREATE OR REPLACE VIEW `adframework.gold.dim_advertiser` AS
SELECT
  client_id,
  name,
  sector,
  status,
  parent_client_id,
  client_level
FROM `adframework.core.dim_client`;
