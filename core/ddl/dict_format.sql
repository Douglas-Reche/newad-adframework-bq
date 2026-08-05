-- core.dict_format
-- Regra de negócio: mapeamento (platform, formato) -> goal_type.
-- Grain: 1 linha por (platform, formato) VERSÃO (ver effective_from/effective_to abaixo) — UNIQUE em (platform, formato, effective_from).
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
--
-- 2026-08-04 — Sync de drift: notes/confirmed_by/created_at já existiam ao vivo no BQ
-- (não estavam commitadas aqui — mesmo padrão de "shadow object" já documentado em
-- campaign_format_map). Este arquivo foi atualizado para refletir o schema real.
--
-- 2026-08-04 — Versionamento SCD tipo 2 (task Notion "Analisar resiliência e
-- rastreabilidade da camada Gold", passos 1-2): effective_from/effective_to
-- adicionados via ALTER TABLE em produção (não recriando a tabela — CREATE OR
-- REPLACE aqui é destrutivo e o DDL commitado já estava fora de sincronia; ver nota
-- acima). Backfill das 8 linhas existentes: effective_from = DATE '2025-01-01'
-- (retroativo, verificado contra o RAW mais antigo do pipeline — raw.ms_delivery
-- começa em 2025-01-29), não confirmed_at/created_at por linha — usar a data de
-- confirmação da regra quebraria retroativamente o histórico anterior a ela.
-- effective_to NULL = versão ainda ativa.
--
-- Como adicionar/trocar uma regra (procedimento SCD2 — mesmo padrão de
-- campaign_format_map e advertiser_platform_rules, ver core/OWNERSHIP.yaml e
-- docs para a lista completa de tabelas cobertas por este procedimento):
--   1. UPDATE ... SET effective_to = <data da mudança> WHERE (platform, formato) = ... AND effective_to IS NULL;
--   2. INSERT INTO ... a nova linha com effective_from = <data da mudança>, effective_to = NULL.
--   NUNCA fazer UPDATE do goal_type/valor de uma linha existente — isso reinterpretaria
--   retroativamente tudo que já foi reportado com a versão antiga da regra.

CREATE OR REPLACE TABLE `adframework.core.dict_format`
(
  platform        STRING NOT NULL,   -- mediasmart | mgid | siprocal | io_plan
  formato         STRING NOT NULL,   -- Display | Video | Retargeting | Native | Push | AppInstall
  goal_type       STRING NOT NULL,   -- CPM | CPC | CPI
  notes           STRING,            -- contexto / evidência da regra
  confirmed_by    STRING,            -- quem confirmou (ex: 'comercial')
  created_at      DATE,              -- quando a regra foi registrada (trilha de auditoria)
  effective_from  DATE NOT NULL,     -- desde quando esta versão da regra vale para fins de reprocessamento retroativo
  effective_to    DATE               -- até quando valeu; NULL = versão ainda ativa
)
OPTIONS (
  description = 'Regra de negocio: (platform, formato) -> goal_type, versionada (SCD2) por effective_from/effective_to. Confirmado pelo comercial em 2026-06-18. Seed em core/migration/07_seed_dict_format.sql.'
);
