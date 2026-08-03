-- core.change_proposals
-- Fila generica de "detectou divergencia -> pendente de aprovacao humana -> so
-- aplica depois de aprovado". Nao e especifica de nenhuma fonte -- Siprocal e a
-- primeira a usar (via diff_rows() em adframework_python/src/connectors/siprocal.py,
-- chamado por _run_siprocal_daily em orchestrator.py:1535), mas o desenho e
-- generico para qualquer dataset/tabela que precise do mesmo padrao (ex: fila de
-- regras de negocio no hub, futuramente).
--
-- Fica em `core` (nao `raw`) -- e uma tabela de governanca/workflow, nao dado
-- bruto de ingestao.
--
-- Fluxo de resolucao (implementado no hub, nao aqui): aprovar = INSERT da linha
-- corrigida (new_values) na tabela alvo (target_dataset.target_table) com
-- raw_ingested_at novo -- NUNCA DELETE/UPDATE na tabela alvo, ela e append-only
-- estrito; marca status='approved' e depois 'applied' apos o INSERT confirmado.
-- Rejeitar = so marca status='rejected', tabela alvo fica intocada.
--
-- Dedup: antes de propor, o job detector deve checar se ja existe uma proposta
-- (de qualquer status) com o mesmo target_table + key_fields + new_values --
-- se sim, nao recriar (rejected = ja foi decidido; pending/approved/applied =
-- ja esta/foi tratado).

CREATE TABLE IF NOT EXISTS `adframework.core.change_proposals`
(
  proposal_id     STRING NOT NULL,   -- UUID gerado na deteccao
  target_dataset  STRING NOT NULL,   -- ex: 'raw'
  target_table    STRING NOT NULL,   -- ex: 'sp_delivery'
  operation       STRING NOT NULL,   -- 'insert' | 'update' | 'delete'
  key_fields      JSON   NOT NULL,   -- {"coluna_1":"...", "data":"...", ...}
  old_values      JSON,              -- null quando operation = 'insert'
  new_values      JSON   NOT NULL,
  source          STRING NOT NULL,   -- 'siprocal_diff' (unico valor por enquanto)
  status          STRING NOT NULL,   -- 'pending' | 'approved' | 'rejected' | 'applied'
  detected_at     TIMESTAMP NOT NULL,
  proposed_by     STRING,            -- job/report que detectou
  resolved_by     STRING,
  resolved_at     TIMESTAMP,
  applied_at      TIMESTAMP,
  notes           STRING
)
OPTIONS (
  description = 'Fila generica de propostas de mudanca pendentes de aprovacao humana. Primeira consumidora: reconciliacao Siprocal (raw.sp_delivery).'
);
