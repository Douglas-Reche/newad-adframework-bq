-- stg.ms_campaigns
-- T2 STG MediaSmart -- grain: 1 linha por campaign_id.
-- Herda client_id de stg.ms_advertisers (principio "resolve uma vez so").
--
-- formato: detectado no campaign_name em 2 passos:
-- 1. Busca por segmento separado por '_': ANY segment IN keywords.
--    Inclui alias RTG/RETARG → RETARGETING.
-- 2. Fallback: REGEXP no nome completo normalizado (pega nomes com '-' ou
--    espacos como "Cassino - Retargeting" e "RETARGETING2_AGOSTO").
-- Normalizacao de acentuacao via TRANSLATE em ambos os passos.
-- Nao tem como resolver nomes sem keyword (ex: LUCKBET_RETENCAO_, 7K, HBO) --
-- esses ficam NULL. NAO usa posicao fixa (posicao varia por cliente).
--
-- goal_type: join core.dict_format (regra de negocio confirmada pelo
-- comercial em 2026-06-18).

CREATE OR REPLACE VIEW `adframework.stg.ms_campaigns` AS
WITH norm AS (
  SELECT
    c.campaign_id,
    c.client_id AS event_id,
    c.campaign_name,
    c.state AS status,
    c.started_at AS start_date,
    c.finished_at AS end_date,
    -- nome normalizado (sem acentos, upper) para todos os testes de formato
    UPPER(TRANSLATE(c.campaign_name,
      'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç',
      'AAAAEEEIIIOOOOUUUCaaaaeeeiiiooooouuuc')) AS name_norm,
    SPLIT(c.campaign_name, '_') AS parts
  FROM `adframework.raw.ms_campaigns` c
),
with_formato AS (
  SELECT
    n.* EXCEPT(parts, name_norm),
    COALESCE(
      -- Passo 1: segmento exato separado por '_' (inclui alias RTG/RETARG)
      (
        SELECT
          CASE UPPER(TRANSLATE(seg, 'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç', 'AAAAEEEIIIOOOOUUUCaaaaeeeiiiooooouuuc'))
            WHEN 'RTG'         THEN 'RETARGETING'
            WHEN 'RETARG'      THEN 'RETARGETING'
            WHEN 'RETARGETING' THEN 'RETARGETING'
            WHEN 'DISPLAY'     THEN 'DISPLAY'
            WHEN 'VIDEO'       THEN 'VIDEO'
            WHEN 'NATIVE'      THEN 'NATIVE'
          END
        FROM UNNEST(n.parts) AS seg
        WHERE UPPER(TRANSLATE(seg, 'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç', 'AAAAEEEIIIOOOOUUUCaaaaeeeiiiooooouuuc'))
              IN ('DISPLAY', 'VIDEO', 'NATIVE', 'RTG', 'RETARG', 'RETARGETING')
        LIMIT 1
      ),
      -- Passo 2: REGEXP no nome completo (pega "Retargeting2", "- Retargeting", espacos)
      CASE
        WHEN REGEXP_CONTAINS(n.name_norm, r'RETARGET') THEN 'RETARGETING'
        WHEN REGEXP_CONTAINS(n.name_norm, r'\bDISPLAY\b') THEN 'DISPLAY'
        WHEN REGEXP_CONTAINS(n.name_norm, r'\bVIDEO\b')   THEN 'VIDEO'
        WHEN REGEXP_CONTAINS(n.name_norm, r'\bNATIVE\b')  THEN 'NATIVE'
      END
    ) AS formato
  FROM norm n
)
SELECT
  w.campaign_id,
  w.event_id,
  a.client_id,
  w.campaign_name,
  w.formato,
  df.goal_type,
  w.status,
  w.start_date,
  w.end_date
FROM with_formato w
LEFT JOIN `adframework.stg.ms_advertisers` a ON a.event_id = w.event_id
LEFT JOIN `adframework.core.dict_format` df
  ON UPPER(TRANSLATE(df.formato, 'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç', 'AAAAEEEIIIOOOOUUUCaaaaeeeiiiooooouuuc'))
     = UPPER(TRANSLATE(w.formato, 'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç', 'AAAAEEEIIIOOOOUUUCaaaaeeeiiiooooouuuc'))
  AND df.platform = 'mediasmart';
