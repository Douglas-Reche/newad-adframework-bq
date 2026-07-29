-- core.dict_format
-- Regra de negócio: mapeamento (platform, formato) -> goal_type.
-- Grain: 1 linha por (platform, formato) — UNIQUE.
-- Fonte de verdade: regras confirmadas pelo comercial em 2026-06-18.
-- Seed: core/migration/07_seed_dict_format.sql
--
-- Usado em:
--   stg.ms_campaigns (goal_type por campanha MS)
--   stg.mg_campaigns (goal_type por campanha MGID)
--   stg.sp_campaigns (goal_type por campanha Siprocal)
--   gold.fact_io_plan (goal_type para cálculo de investimento_realizado)
--
-- goal_type válidos e suas fórmulas de investimento_realizado (gold.fact_pacing):
--   CPM → (impressions × unit_price) / 1000
--   CPC → clicks × unit_price (sem dividir por 1000 — confirmado pelo usuário 2026-07-08, ver gold/ddl/fact_pacing.sql)
--   CPI → NULL (sem fórmula confirmada — AppInstall)
--
-- ATENÇÃO: CREATE OR REPLACE TABLE aqui recria a tabela do zero.
-- Para adicionar linha: INSERT INTO (nunca re-executar o DDL completo sem re-seed).

CREATE OR REPLACE TABLE `adframework.core.dict_format`
(
  platform   STRING NOT NULL,   -- mediasmart | mgid | siprocal
  formato    STRING NOT NULL,   -- Display | Video | Retargeting | Native | Push | AppInstall
  goal_type  STRING NOT NULL    -- CPM | CPC | CPI
)
OPTIONS (
  description = 'Regra de negocio: (platform, formato) -> goal_type. Confirmado pelo comercial em 2026-06-18. Seed em core/migration/07_seed_dict_format.sql.'
);
