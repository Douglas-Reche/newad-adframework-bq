-- stg.fact_pacing_base
-- Materializacao FISICA (TABLE, nao VIEW) do cruzamento planejado x realizado
-- que antes vivia como a CTE `pacing_base` dentro de gold/ddl/fact_pacing.sql
-- (FULL OUTER JOIN entre gold.fact_io_plan e gold.fact_delivery, agregando
-- gold.fact_io_plan por client_id+dia+formato+platform antes do JOIN pra
-- evitar duplicacao quando o mesmo dia tem 2 unit_price/goal_type
-- diferentes -- ver CTE io_agg no arquivo de origem/no script de refresh).
--
-- Schema identico ao que a CTE pacing_base ja calculava -- so passou a ser
-- gravado em vez de recalculado a cada leitura de gold.fact_pacing. NAO
-- inclui as colunas business_rule_* (essas continuam calculadas dentro da
-- propria view gold.fact_pacing, a partir de core.client_business_rules --
-- fact_pacing_base e so o "planejado x realizado", sem regra de negocio
-- aplicada).
--
-- POR QUE TABELA E NAO VIEW (motivo central desta materializacao, task
-- Notion "Materializar base de fact_pacing na STG (stg.fact_pacing_base) --
-- resolve desvio do ADR-0001"): o BigQuery expande toda VIEW dentro da
-- query que a consulta -- entao mesmo que pacing_base virasse uma VIEW
-- separada, uma chamada de core.resolve_client_business_rule(...) dentro de
-- gold.fact_pacing ainda enxergaria, no plano de execucao final, a mesma
-- cadeia de UNION ALL (gold.fact_delivery = UNION ALL de 4 fontes stg) +
-- FULL OUTER JOIN (io_agg x fact_delivery) que causa
-- "Correlated subqueries that reference other tables are not supported
-- unless they can be de-correlated" -- confirmado empiricamente em
-- 2026-08-10 (ver DESVIO DELIBERADO documentado em gold/ddl/fact_pacing.sql
-- antes desta mudanca). So uma TABELA FISICA quebra essa cadeia: uma leitura
-- de tabela nao carrega o plano de execucao de quem a populou.
--
-- Consequencia aceita: fact_pacing_base fica sujeita a REFRESH (nao
-- atualiza sozinha quando fact_io_plan/fact_delivery mudam, diferente de
-- uma VIEW) -- ver stg/ddl/fact_pacing_base_refresh.sql para o mecanismo de
-- populacao (CREATE OR REPLACE TABLE ... AS SELECT, aplicavel via
-- apply_ddl.py). O agendamento automatico desse refresh (Cloud Scheduler ou
-- equivalente) fica FORA de escopo desta task -- por ora, refresh manual
-- sob demanda.
--
-- CREATE TABLE IF NOT EXISTS -- nao-destrutivo, seguro rodar via
-- apply_ddl.py tanto em --env=test/--project douglas-bq-staging quanto em
-- --env=prod mesmo se a tabela ja existir (nao recria, nao trunca). O
-- refresh de fato (que substitui o conteudo) e sempre o script separado
-- (fact_pacing_base_refresh.sql), nunca este arquivo.
--
-- client_id/day NOT NULL aqui e so DOCUMENTACAO de intencao -- a
-- fact_pacing_base_refresh.sql (CREATE OR REPLACE TABLE AS SELECT) SUBSTITUI
-- o schema inteiro a cada execucao, entao a nulabilidade real apos o
-- primeiro refresh e a que o BigQuery infere da SELECT (o refresh ja filtra
-- explicitamente client_id/day nulos via WHERE, entao a garantia pratica
-- vem de la, nao desta constraint). Este CREATE so importa na primeira vez
-- (tabela ainda nao existe, antes de qualquer refresh rodar).

CREATE TABLE IF NOT EXISTS `adframework.stg.fact_pacing_base`
(
  client_id                 STRING   NOT NULL,
  day                       DATE     NOT NULL,
  formato                   STRING,
  platform                  STRING,
  planned_spend_daily       NUMERIC,
  planned_impressions_daily FLOAT64,
  planned_clicks_daily      FLOAT64,
  unit_price                NUMERIC,
  goal_type                 STRING,
  realized_impressions      FLOAT64,
  realized_clicks           FLOAT64,
  realized_conversions      FLOAT64,
  investimento_realizado    FLOAT64
)
OPTIONS (
  description = 'Materializacao fisica do cruzamento planejado (gold.fact_io_plan) x realizado (gold.fact_delivery) por client_id+dia+formato+platform -- quebra a cadeia de UNION ALL/FULL OUTER JOIN que impede chamada direta de core.resolve_client_business_rule() dentro de gold.fact_pacing (correlated subquery nao decorrelacionavel). Populada via stg/ddl/fact_pacing_base_refresh.sql (CREATE OR REPLACE TABLE AS SELECT) -- refresh manual, agendamento fora de escopo. Este arquivo so garante o schema, nunca popula/sobrescreve dado.'
);
