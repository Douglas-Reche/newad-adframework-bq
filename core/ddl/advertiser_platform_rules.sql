-- core.advertiser_platform_rules
-- Regras de remapeamento de plataforma por anunciante.
-- Usada por gold.fact_io_plan para corrigir platform='unknown' no IO Plan
-- quando confirmado que o formato roda em uma plataforma específica.
--
-- Por que existe: o sync_drive.py mapeia Push como 'unknown' globalmente
-- (seguro — evita assumir plataforma para todos os clientes). Quando
-- confirmamos com o cliente/Shiro que o Push roda na Siprocal, adicionamos
-- uma linha aqui. fact_io_plan faz JOIN e aplica o remapeamento.
--
-- 2026-08-04 — Versionamento SCD tipo 2 (task Notion "Analisar resiliência e
-- rastreabilidade da camada Gold", passos 1-2): effective_from/effective_to
-- adicionados via ALTER TABLE em produção (não via re-execução deste arquivo,
-- que faz DELETE+INSERT — evitado aqui para não misturar uma migração de schema
-- com o fluxo normal de "trocar regra"). Backfill da linha existente (Cora/Push):
-- effective_from = DATE '2025-01-01', e NÃO confirmed_at (2026-07-08) como
-- cogitado inicialmente — confirmed_at é só a data em que a regra foi
-- documentada/confirmada, não desde quando ela vale para reprocessamento. A
-- regra Cora/Push cobre stg.io_plan desde flight_start = 2025-04-01 (16 linhas);
-- usar confirmed_at como effective_from teria feito a regra "sumir" pra
-- qualquer relatório de Abr/2025–Jul/2026 assim que a view (passo 3) passar a
-- filtrar por effective_from. 2025-01-01 é retroativo o suficiente (antes do
-- RAW mais antigo do pipeline: raw.ms_delivery começa em 2025-01-29) para não
-- mudar nada do que já foi reportado. effective_to NULL = versão ainda ativa.
--
-- Como adicionar/trocar uma regra (procedimento SCD2 — mesmo padrão de
-- dict_format e campaign_format_map, ver core/OWNERSHIP.yaml e docs para a lista
-- completa de tabelas cobertas por este procedimento; o mesmo procedimento vale
-- também para core.client_business_rules quando essa tabela for desenhada):
--   1. UPDATE ... SET effective_to = <data da mudança> WHERE (client_id, platform_from, formato) = ... AND effective_to IS NULL;
--   2. INSERT INTO ... a nova linha com effective_from = <data da mudança>, effective_to = NULL.
--   NUNCA fazer UPDATE do platform_to de uma linha existente (nem DELETE+re-INSERT
--   em massa como este arquivo fazia antes do versionamento) — isso reinterpretaria
--   retroativamente tudo que já foi reportado com a versão antiga da regra.
--   Sempre preencher confirmed_by e notes com evidência de confirmação.

CREATE TABLE IF NOT EXISTS `adframework.core.advertiser_platform_rules` (
  client_id         STRING  NOT NULL,
  platform_from     STRING  NOT NULL,  -- plataforma no IO Plan (ex: 'unknown')
  formato           STRING  NOT NULL,  -- formato afetado em UPPER (ex: 'PUSH')
  platform_to       STRING  NOT NULL,  -- plataforma real confirmada (ex: 'siprocal')
  confirmed_at      DATE    NOT NULL,  -- data de confirmação (trilha de auditoria, != effective_from)
  confirmed_by      STRING  NOT NULL,  -- quem confirmou (ex: 'douglas', 'shiro')
  notes             STRING,            -- contexto / evidência
  effective_from    DATE    NOT NULL,  -- desde quando esta versão da regra vale para fins de reprocessamento retroativo
  effective_to      DATE               -- até quando valeu; NULL = versão ainda ativa
);

-- ATENÇÃO: o bloco DELETE+INSERT abaixo é o estado ANTERIOR ao versionamento
-- (2026-08-04) e não deve ser re-executado como está — falta a coluna
-- effective_from/effective_to no INSERT e re-rodar um DELETE FROM ... WHERE TRUE
-- destruiria o backfill já aplicado em produção via ALTER TABLE/UPDATE. A partir
-- de agora, usar o procedimento SCD2 descrito acima (UPDATE do effective_to da
-- linha antiga + INSERT da nova) em vez deste padrão de recarga total.
--
-- DELETE FROM `adframework.core.advertiser_platform_rules` WHERE TRUE;
--
-- INSERT INTO `adframework.core.advertiser_platform_rules` VALUES
--   -- Cora: Push no IO Plan marcado como 'unknown', entrega chega como 'siprocal'.
--   -- Confirmado por análise de equivalência dia-a-dia em 2026-07-08.
--   ('banco_cora_fe13d78a', 'unknown', 'PUSH', 'siprocal',
--    DATE '2026-07-08', 'douglas',
--    'Push Cora roda na Siprocal. Validado: linhas unknown/PUSH no IO Plan batem com entrega siprocal/PUSH no mesmo período.',
--    DATE '2025-01-01', NULL);

-- Adicionar novas regras (procedimento SCD2, ver comentário no topo do arquivo):
-- INSERT INTO `adframework.core.advertiser_platform_rules` VALUES
--   ('novo_cliente_id', 'unknown', 'PUSH', 'siprocal',
--    DATE 'YYYY-MM-DD', 'confirmado_por',
--    'descrição da evidência',
--    DATE 'YYYY-MM-DD', NULL);
