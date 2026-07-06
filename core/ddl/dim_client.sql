-- core.dim_client
-- Dimensão canônica de clientes Newad — fonte da verdade de IDs oficial da empresa.
-- Grain: 1 linha por cliente (client_id é imutável após geração).
-- Seed: core/seeds/clients.csv — ÚNICO lugar onde novos IDs são gerados.
-- Qualquer sistema (adframework, pixel, BQ) consome estes IDs; nunca gera os próprios.

CREATE OR REPLACE TABLE `adframework.core.dim_client`
(
  -- Identificação canônica
  client_id     STRING    NOT NULL,  -- {slug}_{8hex} — imutável
  slug          STRING    NOT NULL,  -- lowercase a-z0-9_ — estável mesmo em rebrand
  name          STRING    NOT NULL,  -- nome comercial atual

  -- Classificação
  sector        STRING,              -- apostas | fintech | saude | imobiliario | ...

  -- Ciclo de vida
  status        STRING    NOT NULL,  -- active | inactive | pending_confirmation | legacy
  created_at    DATE      NOT NULL,  -- data de registro do ID (nunca muda)
  deactivated_at DATE,               -- preenchido quando cliente encerra contrato

  -- Metadados
  notes         STRING,              -- observações internas

  -- Hierarquia pai-filho (ex: Amigo é sub-cliente de TecPar)
  parent_client_id  STRING,  -- NULL = cliente raiz; FK self-referencial para dim_client.client_id
  client_level      INT64,   -- 1 = raiz, 2 = sub-cliente, NULL = raiz implícita (legados sem hierarquia definida)

  -- Controle de carga
  seed_loaded_at TIMESTAMP
)
OPTIONS (
  description = 'Dimensao canonica de clientes Newad. client_id e imutavel. Fonte: core/seeds/clients.csv no repo newad-adframework-bq. ATENCAO: CREATE OR REPLACE TABLE recria do zero — nunca executar em producao sem backup. Para adicionar colunas: ALTER TABLE ... ADD COLUMN IF NOT EXISTS.'
);
