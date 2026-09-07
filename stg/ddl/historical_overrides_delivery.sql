-- stg.historical_overrides_delivery
-- Dado normalizado de entrega (impressions/clicks/conversions por dia/
-- plataforma/cliente) mantido manualmente para clientes onde o dado real da
-- plataforma nao pode ser reportado (ex: Cora Jan-Jun/2026) -- mesma
-- convencao do resto da camada STG (stg.ms_delivery, stg.mg_delivery,
-- stg.sp_delivery: dado normalizado vive em STG, nunca em CORE).
--
-- MOVIDA de `core.historical_overrides_delivery` para `stg.historical_overrides_delivery`
-- em 2026-08-06 (decisao do usuario, ao corrigir o teste ponta-a-ponta em
-- douglas-bq-staging): dado normalizado nao pertence a CORE -- CORE fica
-- reservado para tabelas de regra/config pequenas e mantidas manualmente
-- (dict_format, campaign_format_map, advertiser_platform_rules,
-- client_reporting_source_config). `client_reporting_source_config` NAO
-- muda de lugar -- e o toggle ativo/inativo + datas, nao dado de entrega,
-- continua em `core`. Ver core/ddl/historical_overrides_delivery.sql para o
-- stub que documenta essa migracao (nao apagado sem rastro).
--
-- Historico do schema (antes da migracao de camada):
--   - Tabela original criada em `hub/ddl_historical_overrides.sql`
--     (CREATE TABLE IF NOT EXISTS, fluxo manual/pontual, fora do deploy
--     automatizado -- ver hub/README.md e docs/PROCESS.md), ja com dado
--     real da Cora em producao (Jan-Jun/2026).
--   - Coluna `conversions` adicionada em 2026-08-05 (task "Ambientes
--     Staging x Producao") para bater com o schema de gold.fact_delivery
--     (as 3 fontes ms_delivery/mg_delivery/sp_delivery tem `conversions`
--     desde 2026-07-07) -- sem essa coluna o UNION ALL em
--     gold/ddl/fact_delivery.sql falha por contagem/tipo de coluna
--     divergente.
--
-- CREATE TABLE IF NOT EXISTS -- nao-destrutivo, seguro rodar via
-- apply_ddl.py tanto em --env=test quanto em --env=prod mesmo se a tabela
-- ja existir (nao recria, nao trunca).
--
-- Colunas `planned_impressions_daily`/`planned_clicks_daily`/
-- `planned_spend_daily`/`unit_price` adicionadas em 2026-08-10 (task Notion
-- "Materializar base de fact_pacing na STG (stg.fact_pacing_base) -- resolve
-- desvio do ADR-0001", decisao fechada com o Douglas): alinhar o schema
-- desta tabela com o de stg.fact_pacing_base -- ela cobre hoje so o lado
-- REALIZADO (impressions/clicks/conversions), mas um cliente especifico
-- pode um dia precisar sobrescrever tambem o lado PLANEJADO (ex: um IO Plan
-- historico que nao pode ser reconstruido a partir da planilha original).
-- Todas NULLABLE de proposito -- a maioria dos clientes so usa o lado
-- realizado e deixa essas 4 colunas NULL; decisao de preencher ou nao e
-- caso a caso por cliente, NAO existe logica automatica aqui que decida
-- quando usar o override de planejado (fora de escopo desta task). ALTER
-- TABLE ADD COLUMN (nao recriar a tabela) -- ja tem dado real da Cora nela
-- (mesmo com a tabela de teste zerada nesta sessao, a estrutura de
-- referencia de cliente real precisa ser preservada, incluindo em
-- producao).
--
-- Achado (nao corrigido aqui, so documentado): a coluna `investimento`
-- (NUMERIC) e MORTA -- nunca selecionada por gold/ddl/fact_delivery.sql
-- (que so le impressions/clicks/conversions desta tabela). O calculo de
-- investimento_realizado pro override, se algum dia for necessario, hoje
-- teria que vir das novas colunas planned_spend_daily/unit_price + a mesma
-- formula CPC/CPM ja usada em stg/ddl/fact_pacing_base_refresh.sql -- nao
-- desta coluna solta.
--
-- Coluna `target_group` adicionada em 2026-09-07 (redesenho de ingestao
-- Casa do Construtor/Audio, 1a das 2 mudancas de arquitetura confirmadas com
-- o Douglas -- preservar split por TARGET no realizado, comparavel ao
-- planejado por target do IO Plan). Mesmo nome/conceito ja usado em
-- raw.io_plan_drive_snapshot.target_group (ver esse arquivo): STRING
-- nullable, NULL para o caso comum (nenhum split), preenchido (ex:
-- 'TARGET 01', 'TARGET 02') quando a fonte tem blocos por target lado a
-- lado com o total blended.
--
-- DECISAO DE GRAIN (nao trivial, documentada aqui por afetar consumidores
-- compartilhados entre TODOS os clientes): `target_group` NAO entra na
-- chave usada pelos consumidores de producao
-- (gold/ddl/fact_delivery.sql, stg/ddl/fact_pacing_base_refresh.sql) --
-- ambos passam a filtrar `target_group IS NULL` explicitamente ao ler
-- esta tabela. Motivo: os valores por TARGET em clientes como Casa do
-- Construtor sao um RATEIO proporcional do blended (TARGET01+TARGET02 =
-- TOTAL, confirmado numericamente na investigacao original) -- NUNCA uma
-- medicao independente. Se as linhas de target entrassem no
-- SUM()/JOIN de producao junto com a linha blended, o resultado dobraria
-- (blended + (target1+target2, que ja somam de volta ao blended)). As
-- linhas com target_group preenchido existem SO para auditoria/consulta
-- manual (comparar realizado por target contra o planejado por target do
-- IO Plan, que tem valores REAIS e diferentes por target -- R$25k/50k
-- impressoes Target 1, R$10k/20k Target 2) -- nunca para alimentar
-- fact_delivery/fact_pacing_base diretamente. Se um cliente futuro
-- precisar que o detalhe por target ALIMENTE producao de verdade (ex:
-- medicao independente real, nao rateio), isso exige revisitar esta
-- decisao explicitamente, nao assumir que basta remover o filtro.
--
-- Consequencia em load_historical_override.py: a chave de deduplicacao
-- DENTRO do proprio arquivo (validate_rows(), antes so
-- client_id+day+platform+formato) passou a incluir target_group -- sem
-- isso, um arquivo com blended+target1+target2 no mesmo dia seria
-- rejeitado como "duplicata" (mesma client_id/day/platform/formato, 3x)
-- mesmo sendo 3 linhas legitimamente diferentes.

-- Ordem importa: CREATE TABLE IF NOT EXISTS primeiro (ambiente novo, tabela
-- ainda nao existe -- ja nasce com o schema completo, incluindo as colunas
-- novas) e SO DEPOIS o ALTER TABLE (ambiente onde a tabela ja existe sem as
-- colunas novas -- ex: producao hoje, com dado real da Cora). Rodar o ALTER
-- antes do CREATE falharia com "table not found" num ambiente novo/vazio.

CREATE TABLE IF NOT EXISTS `adframework.stg.historical_overrides_delivery`
(
  client_id     STRING    NOT NULL,
  day           DATE      NOT NULL,
  platform      STRING,
  formato       STRING,
  goal_type     STRING,
  impressions   FLOAT64,
  clicks        FLOAT64,
  investimento  NUMERIC,
  source_file   STRING,
  loaded_by     STRING,
  loaded_at     TIMESTAMP,
  notes         STRING,
  conversions   FLOAT64,
  planned_impressions_daily FLOAT64,
  planned_clicks_daily      FLOAT64,
  planned_spend_daily       NUMERIC,
  unit_price                NUMERIC,
  target_group              STRING
)
OPTIONS (
  description = 'Historico manual de entrega (dado normalizado) por client_id+dia, usado por core.resolve_reporting_source()/gold.fact_delivery quando o dado real da plataforma nao pode ser reportado. Movida de core para stg em 2026-08-06 -- dado normalizado pertence a STG, nao a CORE. Colunas planned_* /unit_price (2026-08-10) cobrem override opcional do lado planejado, alinhado ao schema de stg.fact_pacing_base -- NULL na maioria dos casos.'
);

-- Safety net para ambiente onde a tabela JA existia antes desta mudanca
-- (producao, com dado real da Cora) -- CREATE TABLE IF NOT EXISTS acima e
-- no-op nesse caso, entao as colunas novas precisam ser adicionadas
-- explicitamente. No-op tambem se ja tiverem sido adicionadas (IF NOT
-- EXISTS por coluna).
ALTER TABLE `adframework.stg.historical_overrides_delivery`
  ADD COLUMN IF NOT EXISTS planned_impressions_daily FLOAT64,
  ADD COLUMN IF NOT EXISTS planned_clicks_daily      FLOAT64,
  ADD COLUMN IF NOT EXISTS planned_spend_daily        NUMERIC,
  ADD COLUMN IF NOT EXISTS unit_price                 NUMERIC,
  ADD COLUMN IF NOT EXISTS target_group               STRING;
