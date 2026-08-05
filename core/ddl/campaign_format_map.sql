-- core.campaign_format_map
-- Mapeamento de formato de campanha por platform_campaign_id.
-- Grain: platform + platform_campaign_id + effective_from (versionado, ver abaixo).
-- Alimentado manualmente ou via convenção de nomes (source = 'campaign_name'
-- quando o formato é inferido por parsing do nome da campanha no DSP —
-- ver docs/audit_pipeline_consistency_2026-07-29.md §07/§8 para a proposta
-- de padronização que torna esse parsing confiável).
--
-- Existia ao vivo no BigQuery sem DDL commitado (objeto "shadow",
-- achado #3 da auditoria de consistência 2026-07-29). Este arquivo foi
-- criado retroativamente lendo a definição real via
-- core.INFORMATION_SCHEMA.TABLES — sincroniza o git com o schema já em
-- produção, não altera dado nem estrutura.
--
-- 2026-08-04 — Versionamento SCD tipo 2 (task Notion "Analisar resiliência e
-- rastreabilidade da camada Gold", passos 1-2): effective_from/effective_to
-- adicionados via ALTER TABLE em produção. Backfill das 18 linhas existentes:
-- effective_from = DATE '2025-01-01' (retroativo, verificado contra o RAW mais
-- antigo do pipeline — raw.ms_delivery começa em 2025-01-29), não created_at por
-- linha (created_at aqui é 2026-06-03 para todas as linhas — usar essa data
-- quebraria retroativamente o histórico anterior a ela, já que essas campanhas
-- rodaram desde antes). effective_to NULL = versão ainda ativa.
--
-- Como adicionar/trocar uma regra (procedimento SCD2 — mesmo padrão de
-- dict_format e advertiser_platform_rules, ver core/OWNERSHIP.yaml e docs para a
-- lista completa de tabelas cobertas por este procedimento):
--   1. UPDATE ... SET effective_to = <data da mudança> WHERE (platform, platform_campaign_id) = ... AND effective_to IS NULL;
--   2. INSERT INTO ... a nova linha com effective_from = <data da mudança>, effective_to = NULL.
--   NUNCA fazer UPDATE do format de uma linha existente — isso reinterpretaria
--   retroativamente tudo que já foi reportado com a versão antiga da regra.

CREATE TABLE IF NOT EXISTS `adframework.core.campaign_format_map`
(
  platform              STRING OPTIONS(description="mediasmart, mgid, siprocal, google_ads"),
  platform_campaign_id  STRING OPTIONS(description="ID da estrategia/campanha na plataforma"),
  client_id             STRING OPTIONS(description="dim_client.client_id"),
  format                STRING OPTIONS(description="Display | Native | Push | Retargeting | Video | Outros"),
  source                STRING OPTIONS(description="campaign_name | manual | io_plan"),
  notes                 STRING,
  created_at            TIMESTAMP,
  updated_at            TIMESTAMP,
  effective_from        DATE NOT NULL OPTIONS(description="desde quando esta versao do mapeamento vale para fins de reprocessamento retroativo"),
  effective_to          DATE OPTIONS(description="ate quando valeu; NULL = versao ainda ativa")
)
OPTIONS(
  description="Mapeamento formato de campanha por platform_campaign_id, versionado (SCD2) por effective_from/effective_to. Grain: platform + platform_campaign_id + effective_from. Alimentado manualmente ou via convencao de nomes."
);
