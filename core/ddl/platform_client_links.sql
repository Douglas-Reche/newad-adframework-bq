-- core.platform_client_links
-- Mapeia identificadores de plataforma para client_id canônico.
-- Grain: (platform, link_type, link_value) — UNIQUE.
-- link_type por plataforma:
--   mediasmart → eventid   (nível de advertiser; campanhas novas herdam automaticamente)
--   mgid       → campaignid (agência Newad; sem campo advertiser na API)
--   siprocal   → advertiser (texto livre UPPER+TRIM; frágil — monitorar mudanças de nome)
-- client_id NULL = pendente confirmação ou não identificado.

CREATE OR REPLACE TABLE `adframework.core.platform_client_links`
(
  platform    STRING NOT NULL,
  link_type   STRING NOT NULL,
  link_value  STRING NOT NULL,
  client_id   STRING,
  status      STRING NOT NULL,
  notes       STRING,
  created_at  DATE   NOT NULL
)
OPTIONS (
  description = 'Mapeamento de identificadores de plataforma (eventid/campaignid/advertiser) para client_id canonico. Fonte: core/seeds/platform_client_links.csv'
);
