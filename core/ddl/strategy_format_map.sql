-- core.strategy_format_map
-- Regra de negocio: keyword (texto livre) -> formato, usada para classificar
-- strategy_name (texto livre da planilha do IO Plan) em vez do CASE WHEN
-- hardcoded que existia antes em stg/ddl/io_plan.sql.
-- Grain: 1 linha por keyword VERSAO (ver effective_from/effective_to abaixo)
-- -- UNIQUE em (keyword, effective_from).
--
-- Por que existe: o CASE WHEN LOWER(strategy_name) LIKE '%palavra%' hardcoded
-- em stg.io_plan tinha um vocabulario fixo de 6 formatos -- qualquer
-- strategy_name que nao batesse virava NULL silenciosamente, pra sempre, sem
-- trilha de quem/quando decidiu que aquele formato nao existe. Achado real
-- 2026-09-07: "Áudio Ads" da Casa do Construtor (client_id=casa_construtor_adf15c2c)
-- cai nesse buraco -- R$25.000/50.000 impressoes corretos no total agregado,
-- mas sem formato em gold.fact_io_plan. Extraida pra tabela de referencia
-- editavel (mesmo padrao de core.dict_format/core.advertiser_platform_rules)
-- para que um formato novo vire 1 INSERT auditavel em vez de uma mudanca de
-- codigo, e para que "nao classificado" vire uma fila de pendencias visivel
-- (Hub, task separada) em vez de um NULL mudo.
--
-- Resolucao: core.resolve_strategy_format(strategy_name, as_of_date) procura,
-- entre as keywords vigentes na data, a que aparece na posicao mais a
-- esquerda dentro de strategy_name (LOWER(strategy_name) LIKE
-- CONCAT('%', LOWER(keyword), '%')) -- ver core/ddl/resolve_strategy_format.sql.
-- Isso preserva o comportamento do CASE WHEN antigo pra todas as 27 combinacoes
-- reais de strategy_name existentes em douglas-bq-staging.stg.io_plan em
-- 2026-09-07 (validado linha a linha, 0 divergencias -- nenhuma tinha 2
-- keywords em posicoes que discordassem da ordem de prioridade antiga do
-- CASE WHEN: native, video/vídeo, retargeting, display, push,
-- appinstall/app install).
--
-- Seed (6 keywords que ja existiam hardcoded): core/migration/10_seed_strategy_format_map.sql
--
-- Migrado de: stg/ddl/io_plan.sql (CASE WHEN hardcoded, linhas 42-50 antes
-- desta mudanca).
--
-- ATENCAO: CREATE OR REPLACE TABLE aqui recria a tabela do zero.
-- Para adicionar linha: INSERT INTO (nunca re-executar o DDL completo sem re-seed).
--
-- Como adicionar/trocar uma regra (procedimento SCD2 -- mesmo padrao de
-- dict_format/advertiser_platform_rules/campaign_format_map, ver
-- core/OWNERSHIP.yaml e docs para a lista completa de tabelas cobertas por
-- este procedimento):
--   1. UPDATE ... SET effective_to = <data da mudanca> WHERE keyword = ... AND effective_to IS NULL;
--   2. INSERT INTO ... a nova linha com effective_from = <data da mudanca>, effective_to = NULL.
--   NUNCA fazer UPDATE do formato de uma linha existente -- isso reinterpretaria
--   retroativamente tudo que ja foi reportado com a versao antiga da regra.
--   Sempre preencher confirmed_by e notes com evidencia de confirmacao.

CREATE OR REPLACE TABLE `adframework.core.strategy_format_map`
(
  keyword         STRING NOT NULL,   -- substring procurada em LOWER(strategy_name), case-insensitive
  formato         STRING NOT NULL,   -- resultado (ex: Native, Video, Áudio)
  notes           STRING,            -- contexto / evidencia da regra
  confirmed_by    STRING,            -- quem confirmou (ex: 'migracao_hardcode', 'douglas')
  created_at      DATE,              -- quando a regra foi registrada (trilha de auditoria)
  effective_from  DATE NOT NULL,     -- desde quando esta versao da regra vale para fins de reprocessamento retroativo
  effective_to    DATE               -- ate quando valeu; NULL = versao ainda ativa
)
OPTIONS (
  description = 'Regra de negocio: keyword (substring de strategy_name) -> formato, versionada (SCD2) por effective_from/effective_to. Substitui o CASE WHEN hardcoded que existia em stg.io_plan. Seed em core/migration/10_seed_strategy_format_map.sql.'
);
