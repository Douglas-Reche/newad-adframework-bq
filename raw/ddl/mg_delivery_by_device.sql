-- raw.mg_delivery_by_device
-- Fato de entrega diaria por device da MGID (T6).
-- Grain: dia + creative + device_type
-- Fonte: GET /v1/goodhits/clients/{MGID_CLIENT_ID}/statistics-reports
--   dimensions[] = day, teaserId, deviceType
--   metrics[] = impressions, clicks, conversionsInterest, conversionsDecision, conversionsBuy
-- Ingestao: diaria incremental
--
-- SEM operating_system e SEM campaign_id, decisoes deliberadas (2026-06-22):
--
-- 1. Limite de 3 dimensoes por chamada (mesma restricao do T5) torna IMPOSSIVEL
--    ter day+entidade+device+os juntos, independente de usar campaignId ou
--    teaserId como entidade. Decisao validada com o usuario: ingerir so device
--    por agora -- OS fica de fora até surgir necessidade real de analise.
--
-- 2. campaign_id removido: teaserId ja e FK para raw.mg_teasers (que tem
--    campaign_id no catalogo) -- resolvido via JOIN na STG, mesmo padrao do T5.
--
-- Campo correto confirmado por teste real: "deviceType" (camelCase) -- "device"
-- (lowercase) e rejeitado pela API ("not a valid choice").

CREATE OR REPLACE TABLE `adframework.raw.mg_delivery_by_device`
(
  date                  DATE,
  creative_id           STRING,     -- teaserId -- FK para raw.mg_teasers.creative_id
  device_type           STRING,     -- ex: mobile, desktop, tablet, smarttv
  impressions           FLOAT64,
  clicks                FLOAT64,
  conversions_interest  FLOAT64,
  conversions_decision  FLOAT64,
  conversions_buy       FLOAT64,
  platform              STRING,
  raw_ingested_at       TIMESTAMP
)
PARTITION BY date
OPTIONS (
  description = 'T6 MGID — entrega por device, nivel creative. Sem OS/campaign_id (ver DDL). Particionado por date, incremental.'
);
