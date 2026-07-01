-- stg.ms_campaigns
-- T2 STG MediaSmart -- grain: 1 linha por campaign_id.
-- Herda client_id de stg.ms_advertisers (principio "resolve uma vez so").
--
-- formato: busca por QUALQUER segmento do campaign_name (separado por '_') que
-- bata com um formato conhecido (Display/Video/Retargeting/Native), normalizando
-- acentuacao via TRANSLATE. NAO usa posicao fixa -- testado contra as 14
-- campanhas reais (2026-06-24): a posicao do formato varia (1 ou 2, dependendo
-- de haver um segmento de "linha de produto" no meio, ex: CORA_CONTADIGITAL_
-- DISPLAY_JUNHO26 -- "CONTADIGITAL" entre cliente e formato). Posicao fixa
-- resolvia so 11/14; busca por qualquer segmento + normalizacao de acento
-- resolve 13/14. Unico sem formato: LUCKBET_APOSTADORES_MAIO -- nome realmente
-- nao contem indicacao de formato, nao e bug de parse. "Teste-Newad" e conta
-- interna, sem padrao de nome, tambem fica sem formato (esperado).
--
-- goal_type: join core.dict_format (regra de negocio confirmada pelo
-- comercial em 2026-06-18).

CREATE OR REPLACE VIEW `adframework.stg.ms_campaigns` AS
WITH segments AS (
  SELECT
    c.campaign_id,
    c.client_id AS event_id,
    c.campaign_name,
    c.state AS status,
    c.started_at AS start_date,
    c.finished_at AS end_date,
    SPLIT(c.campaign_name, '_') AS parts
  FROM `adframework.raw.ms_campaigns` c
),
with_formato AS (
  SELECT
    s.* EXCEPT(parts),
    (
      SELECT seg
      FROM UNNEST(s.parts) AS seg
      WHERE UPPER(TRANSLATE(seg, 'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç', 'AAAAEEEIIIOOOOUUUCaaaaeeeiiiooooouuuc'))
            IN ('DISPLAY', 'VIDEO', 'RETARGETING', 'NATIVE')
      LIMIT 1
    ) AS formato
  FROM segments s
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
