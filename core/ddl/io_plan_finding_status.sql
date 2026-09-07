-- core.io_plan_finding_status
-- Tabela de controle pequena para a aba "Saude do IO Plan" do Hub
-- (hub/app.py). A DETECCAO em si (duplicata de valores, arquivo reusado,
-- salto grande, gap de cobertura, multiplas versoes) e SEMPRE recalculada ao
-- vivo a partir de core.io_plan_manual/raw.io_plan_drive_snapshot toda vez
-- que a pagina carrega -- isso nao muda. O que esta tabela guarda e só o
-- TRATAMENTO HUMANO de cada achado (Douglas revisou e decidiu algo sobre
-- ele), que precisa sobreviver entre sessoes -- sem isso, o mesmo achado
-- reaparece "pendente" pra sempre mesmo depois de resolvido.
--
-- Grain: 1 linha por (client_id, flight_start, flight_end, heuristic_name) --
-- um mes pode ter mais de um achado simultaneo (ex: "duplicata_valores" E
-- "salto_grande" no mesmo flight), cada um rastreado/resolvido
-- independentemente. heuristic_name usa os mesmos nomes de chave ja usados
-- em build_io_plan_health_report() (hub/app.py): duplicata_valores,
-- arquivo_duplicado, salto_grande, gap_cobertura, multiplas_versoes.
--
-- status:
--   'pendente'  -- default implicito (linha ausente = pendente, ver UPSERT
--                  abaixo -- nao precisa INSERT automatico quando o achado
--                  nasce, so tratar NULL/ausencia como pendente na leitura)
--   'resolvido' -- Douglas corrigiu a fonte (planilha/Drive) -- `comment`
--                  DEVE vir preenchido descrevendo o ajuste feito
--   'esperado'  -- falso-positivo ou decisao de negocio legitima (ex:
--                  cliente repetiu orcamento de proposito) -- nao e bug
--
-- Escrita: writer SA do Hub (douglas-data-hub-writer-sa), que ja tem
-- roles/bigquery.dataEditor no dataset `core` (staging E producao, ver
-- hub/deploy.sh blocos 1b) -- NENHUM binding de IAM novo necessario pra essa
-- tabela especificamente, ela so precisa EXISTIR (este DDL).
--
-- Aplicar (Nivel 2, ver scripts/deploy/apply_ddl.py):
--   staging (livre):   python scripts/deploy/apply_ddl.py core/ddl/io_plan_finding_status.sql --env=prod --project douglas-bq-staging
--   producao (SO com confirmacao explicita do Douglas -- nao rodar sozinho):
--                       python scripts/deploy/apply_ddl.py core/ddl/io_plan_finding_status.sql --env=prod
CREATE TABLE IF NOT EXISTS `adframework.core.io_plan_finding_status` (
  client_id      STRING NOT NULL,
  flight_start   DATE NOT NULL,
  flight_end     DATE NOT NULL,
  heuristic_name STRING NOT NULL,
  status         STRING NOT NULL,  -- 'pendente' | 'resolvido' | 'esperado'
  comment        STRING,           -- livre; esperado preenchido quando status='resolvido'
  updated_by     STRING,
  updated_at     TIMESTAMP NOT NULL
);
