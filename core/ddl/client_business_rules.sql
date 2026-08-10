-- core.client_business_rules
-- Regras de negócio configuráveis por cliente (ou globais, para todos os
-- clientes), extensíveis a qualquer `rule_type` futuro — não hardcoded por
-- tipo de regra. Primeiro caso de uso: teto de 20% de impressão diária
-- (`rule_type = 'impression_cap_pct'`), motivado pelo Rafael (Newad) para
-- Native e Push — impressões realizadas no dia não podem superar em mais de
-- X% as impressões projetadas pro dia, senão trava a contagem (mantém CTR
-- controlado). Aplicado em gold.fact_pacing (única view que já cruza
-- projetado vs. realizado no grain cliente+dia+formato+plataforma) via um
-- flag calculado (ex: impressions_capped_flag), não capando o dado bruto
-- agregado. Ver task "Desenhar mecanismo de regras de negócio configuráveis
-- por cliente" (2026-08-09).
--
-- Grain: 1 linha por (rule_type, client_id, effective_from) VERSÃO — mesmo
-- padrão SCD2 de core.dict_format / core.advertiser_platform_rules (ver ADR
-- docs/adr/0001-versionamento-scd2-regras-negocio-via-funcoes-resolve.md,
-- que já antecipava esta tabela na seção de procedimento SCD2 de
-- advertiser_platform_rules.sql). Resolver sempre via
-- core.resolve_client_business_rule(client_id, rule_type, as_of_date) —
-- nunca reimplementar o JOIN versionado inline numa view nova.
--
-- client_id NULL = regra vale para todos os clientes (regra geral NewAd).
-- client_id preenchido = override específico daquele cliente, que
-- core.resolve_client_business_rule prioriza sobre a regra geral quando
-- ambas estão vigentes na mesma data (ver função).
--
-- rule_params é JSON deliberadamente livre — cada rule_type define seu
-- próprio formato de parâmetros, sem schema fixo no BigQuery (não dá pra
-- validar estrutura aqui; validação de shape fica a cargo de quem escreve
-- e de quem lê). Exemplo para 'impression_cap_pct':
--   {"threshold_pct": 20, "strategies": ["native", "push"]}
--
-- Ativação/pausa de uma regra (geral ou por cliente) NÃO usa flag booleana
-- separada — segue o mesmo mecanismo SCD2 de fechar/abrir linha:
--   - Pausar: UPDATE ... SET effective_to = <data da pausa> na linha vigente.
--     A partir dessa data, resolve_client_business_rule retorna NULL pra
--     esse (rule_type, client_id) — comportamento idêntico a "sem regra".
--   - Reativar (mesmos parâmetros ou novos): INSERT de uma linha nova com
--     effective_from = <data da reativação>, effective_to = NULL.
--   Isso evita um segundo mecanismo de estado (is_active) conflitando com o
--   já existente (effective_to) — a mesma linha do tempo responde as duas
--   perguntas ("qual o valor da regra" e "está ativa").
--
-- Como adicionar/trocar/pausar uma regra (procedimento SCD2 — mesmo padrão
-- de dict_format e advertiser_platform_rules):
--   1. UPDATE ... SET effective_to = <data da mudança> WHERE rule_type = ...
--      AND client_id = ... (ou IS NULL) AND effective_to IS NULL;
--   2. Se a regra continua ativa com novo valor: INSERT INTO ... a nova
--      linha com effective_from = <mesma data>, effective_to = NULL.
--      Se é uma pausa (sem nova versão), pare no passo 1.
--   NUNCA fazer UPDATE do rule_params de uma linha existente — isso
--   reinterpretaria retroativamente tudo que já foi reportado com a versão
--   antiga da regra. Sempre preencher confirmed_by e notes com evidência da
--   decisão. SELECT antes de INSERT pra checar override existente/ambíguo
--   pro mesmo (rule_type, client_id) com effective_to IS NULL.

CREATE TABLE IF NOT EXISTS `adframework.core.client_business_rules` (
  rule_type       STRING  NOT NULL,  -- tipo de regra, extensível (ex: 'impression_cap_pct')
  client_id       STRING,            -- NULL = regra geral (todos os clientes); preenchido = override por cliente
  rule_params     JSON    NOT NULL,  -- parâmetros específicos do rule_type, formato livre (ver exemplo no topo)
  confirmed_at    DATE    NOT NULL,  -- data de confirmação (trilha de auditoria, != effective_from)
  confirmed_by    STRING  NOT NULL,  -- quem confirmou (ex: 'rafael', 'douglas')
  notes           STRING,            -- contexto / evidência da decisão
  effective_from  DATE    NOT NULL,  -- desde quando esta versão da regra vale para fins de reprocessamento retroativo
  effective_to    DATE               -- até quando valeu (ou quando foi pausada); NULL = versão ainda ativa
)
OPTIONS (
  description = 'Regras de negocio configuraveis por cliente (client_id) ou gerais (client_id NULL), versionadas (SCD2) por effective_from/effective_to. rule_type extensivel, rule_params em JSON livre por tipo. Primeiro rule_type: impression_cap_pct (teto de 20% de impressao diaria Native/Push, confirmado por Rafael).'
);

-- Exemplo de INSERT (procedimento SCD2, ver comentário no topo do arquivo) —
-- regra geral NewAd (client_id NULL) de teto de 20% para Native e Push:
-- INSERT INTO `adframework.core.client_business_rules` VALUES (
--   'impression_cap_pct',
--   NULL,
--   JSON '{"threshold_pct": 20, "strategies": ["native", "push"]}',
--   DATE '2026-08-09',
--   'rafael',
--   'Teto de 20% pra manter CTR controlado em Native/Push — demais estratégias já travam direto na plataforma.',
--   DATE '2026-08-09',
--   NULL
-- );
--
-- Exemplo de override específico de cliente (ex: threshold diferente pra um
-- cliente específico), com prioridade sobre a regra geral acima:
-- INSERT INTO `adframework.core.client_business_rules` VALUES (
--   'impression_cap_pct',
--   'novo_cliente_id',
--   JSON '{"threshold_pct": 10, "strategies": ["native", "push"]}',
--   DATE 'YYYY-MM-DD',
--   'confirmado_por',
--   'descrição da evidência',
--   DATE 'YYYY-MM-DD',
--   NULL
-- );
