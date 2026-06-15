-- raw.mgid_geo_regions
-- Lookup global de regiões MGID — mapeamento region_id → country.
-- Grain: 1 linha por região (region_id único)
-- Fonte: job mgid_geo_lookup (one-time / refresh manual)
--   Passo 1: GET /v1/dictionaries/geo?type=countries → lista todos os países
--   Passo 2: GET /v1/dictionaries/geo?type=cities&countries[]=<todos> → regiões por país
-- Cobertura: todos os países suportados pelo MGID globalmente (independente dos clientes ativos).
-- Utilizado em: stg.mgid_delivery_by_geo (T10) para enriquecer region_id com country_code + nomes.

CREATE OR REPLACE TABLE `adframework.raw.mgid_geo_regions`
(
  -- Chave
  region_id             STRING    NOT NULL,  -- city_ID do /dictionaries/geo (mesmo ID retornado em statistics-reports)

  -- Região
  region_name           STRING,              -- nome da região/cidade (ex: São Paulo)
  region_name_latin     STRING,              -- nome em caracteres latinos (normalizedName)

  -- País
  country_code          STRING,              -- código ISO 2 letras (ex: BR, US)
  country_name          STRING,              -- nome do país (ex: Brazil)

  -- Metadados
  raw_ingested_at       TIMESTAMP
)
OPTIONS (
  description = 'Lookup global de regiões MGID. Grain: region_id único. Fonte: /dictionaries/geo (countries + cities). Usado no JOIN do stg.mgid_delivery_by_geo (T10).'
);
