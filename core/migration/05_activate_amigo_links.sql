-- Promove para 'active' os vinculos de Amigo (sub-cliente de TecPar) que ficaram
-- presos em 'pending_confirmation' desde 2026-05-26 -- mesmo dia em que core.dim_client
-- ja registrou amigo_db1c2f0c como active (parent_client_id = tecpar_edfcc744,
-- client_level = 2, seed_loaded_at = 2026-05-26 18:02:50). A confirmacao comercial
-- ja aconteceu (Amigo e empresa abaixo de TecPar); so faltou propagar para
-- platform_client_links.
--
-- Escopo: 1 eventid MediaSmart + 38 campaignids MGID, todos client_id = amigo_db1c2f0c,
-- status = pending_confirmation, created_at = 2026-05-26 (verificado em 2026-06-08).
-- Os vinculos Siprocal (TECPAR, AMIGOTECPAR) ja estavam active e nao sao afetados.

UPDATE `adframework.core.platform_client_links`
SET
  status = 'active',
  notes  = 'Confirmado -- Amigo e sub-cliente ativo de TecPar (dim_client desde 2026-05-26). Status sincronizado em 2026-06-08.'
WHERE client_id  = 'amigo_db1c2f0c'
  AND status     = 'pending_confirmation'
  AND platform   IN ('mediasmart', 'mgid')
  AND created_at = '2026-05-26';
