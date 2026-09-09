-- core.dim_client_reconciliation
-- ----------------------------------------------------------------------------
-- Registro de decisão humana sobre pares de `core.dim_client` sinalizados
-- como possível duplicata pela tela "Gerenciamento de Clientes" do Hub
-- (hub/app.py) — heurística de nome parecido e/ou mesmo `parent_client_id`
-- sem estar de fato diferenciado (ver detect_duplicate_candidates() no Hub).
--
-- Motivador real (2026-09-06/07): "DR CONSULTA" (sub-cliente da DAXX) tem 2
-- candidatos em dim_client — dr_consulta_215378ef e dr_consulta_rj_11040bf9 —
-- sem saber qual é o certo pra uma pasta ambígua do Drive/planilha de
-- plataforma. A tela precisa: (a) não voltar a perguntar sobre um par já
-- decidido a cada reload (mesmo padrão de core.io_plan_finding_status), e
-- (b) manter uma trilha auditável de quem decidiu o quê e quando — mesmo
-- quando a decisão é "são clientes diferentes mesmo, mantidos separados".
--
-- Grain: 1 linha por PAR não-ordenado de client_id (client_id_a sempre o
-- lexicograficamente MENOR dos dois — normalização feita pelo código que
-- escreve, nunca pelo BigQuery — para (A,B) e (B,A) caírem na mesma linha).
-- Chave natural: (client_id_a, client_id_b). Sem SCD2 aqui — decisão pode ser
-- corrigida via novo MERGE (UPSERT), não precisa de histórico de versão como
-- as tabelas de regra de negócio.
--
-- decision = 'same' -> Douglas confirmou que são o MESMO cliente. Quando a
--   tela grava essa decisão, ela TAMBÉM desativa o registro duplicado em
--   core.dim_client (status='inactive', notes apontando pro client_id
--   sobrevivente) — ver deactivate_duplicate_client() em hub/app.py. Esta
--   tabela não mescla dado histórico de fact_delivery/io_plan/etc: isso seria
--   mudança de pipeline (fora do escopo do Hub/front-end), fica registrado
--   aqui como próximo passo se algum dia for decidido.
-- decision = 'different' -> Douglas confirmou que são clientes DE FATO
--   diferentes (dismiss) — o par some da lista de candidatos a duplicata,
--   mas nenhuma linha de dim_client é alterada.

CREATE TABLE IF NOT EXISTS `adframework.core.dim_client_reconciliation` (
  client_id_a  STRING    NOT NULL,  -- menor dos dois client_id do par (normalizado no código, não no BQ)
  client_id_b  STRING    NOT NULL,  -- maior dos dois
  decision     STRING    NOT NULL,  -- 'same' | 'different' -- sem CHECK constraint (BigQuery não suporta), validar no código
  decided_by   STRING,              -- ex: 'douglas'
  decided_at   TIMESTAMP,
  notes        STRING               -- evidência/contexto da decisão
)
OPTIONS (
  description = 'Decisao humana persistida sobre pares de core.dim_client sinalizados como possivel duplicata pela tela Gerenciamento de Clientes do Hub. Chave natural (client_id_a, client_id_b), client_id_a sempre o menor lexicograficamente. decision=same tambem desativa o client_id duplicado em dim_client (ver hub/app.py deactivate_duplicate_client); decision=different so descarta o par da lista de candidatos, sem alterar dim_client.'
);
