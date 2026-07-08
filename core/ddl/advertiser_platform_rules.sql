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
-- Como adicionar nova regra: INSERT abaixo + re-executar este script.
-- Sempre preencher confirmed_by e notes com evidência de confirmação.

CREATE TABLE IF NOT EXISTS `adframework.core.advertiser_platform_rules` (
  client_id         STRING  NOT NULL,
  platform_from     STRING  NOT NULL,  -- plataforma no IO Plan (ex: 'unknown')
  formato           STRING  NOT NULL,  -- formato afetado em UPPER (ex: 'PUSH')
  platform_to       STRING  NOT NULL,  -- plataforma real confirmada (ex: 'siprocal')
  confirmed_at      DATE    NOT NULL,  -- data de confirmação
  confirmed_by      STRING  NOT NULL,  -- quem confirmou (ex: 'douglas', 'shiro')
  notes             STRING            -- contexto / evidência
);

-- Limpar e recarregar (fonte de verdade é este arquivo)
DELETE FROM `adframework.core.advertiser_platform_rules` WHERE TRUE;

INSERT INTO `adframework.core.advertiser_platform_rules` VALUES
  -- Cora: Push no IO Plan marcado como 'unknown', entrega chega como 'siprocal'.
  -- Confirmado por análise de equivalência dia-a-dia em 2026-07-08.
  ('banco_cora_fe13d78a', 'unknown', 'PUSH', 'siprocal',
   DATE '2026-07-08', 'douglas',
   'Push Cora roda na Siprocal. Validado: linhas unknown/PUSH no IO Plan batem com entrega siprocal/PUSH no mesmo período.');

-- Adicionar novas regras aqui:
-- ('novo_cliente_id', 'unknown', 'PUSH', 'siprocal',
--  DATE 'YYYY-MM-DD', 'confirmado_por',
--  'descrição da evidência');
