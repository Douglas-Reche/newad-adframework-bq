# Fila de expurgo semanal

Lista central de arquivos classificados como "análise pontual" pelo agent `docs`
(ver `docs.md`, Função 3 — Gatekeeper), aguardando revisão em lote antes de deletar.
**Nunca deletar direto daqui** — só depois que o usuário confirmar em bloco no fim da
semana (ou quando pedir explicitamente "faz o expurgo").

| Arquivo | Flagueado em | Migrado pra | Motivo |
|---|---|---|---|
| `docs/bigquery_analysis.md` | 2026-08-05 | `bq_restructuring_plan.md` (nenhum fato novo) | Análise pontual abr/26 (auditoria BQ pré-rebuild) — conclusão já superada pelo rebuild de 2026-06-16 e coberta pelo plano atual; classificação confirmada por Douglas 2026-08-05 |
| `docs/bigquery_cleanup_proposal.md` | 2026-08-05 | `bq_restructuring_plan.md` (nenhum fato novo) | Proposta pontual abr/26 (limpeza de storage pré-rebuild) — superada pelo DROP total de 2026-06-16; classificação confirmada por Douglas 2026-08-05 |
