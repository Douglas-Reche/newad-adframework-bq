-- core.resolve_dict_format_fallback(formato, as_of_date) -> goal_type
-- Companheira de core.resolve_dict_format: usada quando a plataforma nao e
-- conhecida (ex: platform='unknown' no IO Plan) -- busca goal_type so por
-- formato, mas apenas se o resultado for inequivoco entre TODAS as
-- plataformas vigentes naquela data (o mesmo formato tem o mesmo goal_type
-- em todas). Se ambiguo, retorna NULL (mesma regra de negocio de
-- gold/ddl/fact_io_plan.sql antes da versao SCD2, so que agora sensivel a
-- data em vez de sempre olhar o estado mais recente).
--
-- 2026-08-04 -- ver core/ddl/resolve_dict_format.sql pro historico completo
-- (bug do ROW_NUMBER, limitacao de LIMIT 1 em SQL UDF, troca de ANY_VALUE
-- por MIN pra determinismo). Mesmas limitacoes/decisoes valem aqui.

CREATE OR REPLACE FUNCTION `adframework.core.resolve_dict_format_fallback`(
  p_formato STRING, p_as_of_date DATE
)
RETURNS STRING
AS ((
  SELECT IF(COUNT(DISTINCT goal_type) = 1, MIN(goal_type), NULL)
  FROM `adframework.core.dict_format`
  WHERE UPPER(formato) = UPPER(p_formato)
    AND effective_from <= p_as_of_date
    AND (effective_to IS NULL OR p_as_of_date < effective_to)
));
