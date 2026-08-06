-- stg.historical_overrides_delivery
-- Dado normalizado de entrega (impressions/clicks/conversions por dia/
-- plataforma/cliente) mantido manualmente para clientes onde o dado real da
-- plataforma nao pode ser reportado (ex: Cora Jan-Jun/2026) -- mesma
-- convencao do resto da camada STG (stg.ms_delivery, stg.mg_delivery,
-- stg.sp_delivery: dado normalizado vive em STG, nunca em CORE).
--
-- MOVIDA de `core.historical_overrides_delivery` para `stg.historical_overrides_delivery`
-- em 2026-08-06 (decisao do usuario, ao corrigir o teste ponta-a-ponta em
-- douglas-bq-staging): dado normalizado nao pertence a CORE -- CORE fica
-- reservado para tabelas de regra/config pequenas e mantidas manualmente
-- (dict_format, campaign_format_map, advertiser_platform_rules,
-- client_reporting_source_config). `client_reporting_source_config` NAO
-- muda de lugar -- e o toggle ativo/inativo + datas, nao dado de entrega,
-- continua em `core`. Ver core/ddl/historical_overrides_delivery.sql para o
-- stub que documenta essa migracao (nao apagado sem rastro).
--
-- Historico do schema (antes da migracao de camada):
--   - Tabela original criada em `hub/ddl_historical_overrides.sql`
--     (CREATE TABLE IF NOT EXISTS, fluxo manual/pontual, fora do deploy
--     automatizado -- ver hub/README.md e docs/PROCESS.md), ja com dado
--     real da Cora em producao (Jan-Jun/2026).
--   - Coluna `conversions` adicionada em 2026-08-05 (task "Ambientes
--     Staging x Producao") para bater com o schema de gold.fact_delivery
--     (as 3 fontes ms_delivery/mg_delivery/sp_delivery tem `conversions`
--     desde 2026-07-07) -- sem essa coluna o UNION ALL em
--     gold/ddl/fact_delivery.sql falha por contagem/tipo de coluna
--     divergente.
--
-- CREATE TABLE IF NOT EXISTS -- nao-destrutivo, seguro rodar via
-- apply_ddl.py tanto em --env=test quanto em --env=prod mesmo se a tabela
-- ja existir (nao recria, nao trunca).

CREATE TABLE IF NOT EXISTS `adframework.stg.historical_overrides_delivery`
(
  client_id     STRING    NOT NULL,
  day           DATE      NOT NULL,
  platform      STRING,
  formato       STRING,
  goal_type     STRING,
  impressions   FLOAT64,
  clicks        FLOAT64,
  investimento  NUMERIC,
  source_file   STRING,
  loaded_by     STRING,
  loaded_at     TIMESTAMP,
  notes         STRING,
  conversions   FLOAT64
)
OPTIONS (
  description = 'Historico manual de entrega (dado normalizado) por client_id+dia, usado por core.resolve_reporting_source()/gold.fact_delivery quando o dado real da plataforma nao pode ser reportado. Movida de core para stg em 2026-08-06 -- dado normalizado pertence a STG, nao a CORE.'
);
