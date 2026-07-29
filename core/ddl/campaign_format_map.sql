-- core.campaign_format_map
-- Mapeamento de formato de campanha por platform_campaign_id.
-- Grain: platform + platform_campaign_id.
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

CREATE TABLE IF NOT EXISTS `adframework.core.campaign_format_map`
(
  platform              STRING OPTIONS(description="mediasmart, mgid, siprocal, google_ads"),
  platform_campaign_id  STRING OPTIONS(description="ID da estrategia/campanha na plataforma"),
  client_id             STRING OPTIONS(description="dim_client.client_id"),
  format                STRING OPTIONS(description="Display | Native | Push | Retargeting | Video | Outros"),
  source                STRING OPTIONS(description="campaign_name | manual | io_plan"),
  notes                 STRING,
  created_at            TIMESTAMP,
  updated_at            TIMESTAMP
)
OPTIONS(
  description="Mapeamento formato de campanha por platform_campaign_id. Grain: platform + platform_campaign_id. Alimentado manualmente ou via convencao de nomes."
);
