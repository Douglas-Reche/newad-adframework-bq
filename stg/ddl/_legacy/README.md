# Arquivos legados — schema STG pré-rebuild

Movidos para esta pasta em 2026-06-24, ao descobrir (durante a construção do T2 do rebuild STG) que `stg/ddl/` não estava vazia como se assumia — tinha 28 arquivos do schema anterior ao DROP de 2026-06-18.

Todos referenciam tabelas RAW já dropadas (`raw.mediasmart_campaigns`, `raw.mediasmart_delivery`, `raw.mediasmart_daily`, etc.) e tabelas STG antigas (`stg.ms_clients`) que não existem mais no BigQuery. Não funcionam se executados.

**Por que preservados em vez de deletados:** podem ter valor de referência histórica (lógica de negócio antiga, padrões de transformação) — mas não devem ser confundidos com o schema STG atual em construção desde 2026-06-24.

Ver `docs/stg_layer_design.md` e `CHANGELOG.md` para o schema STG vigente.
