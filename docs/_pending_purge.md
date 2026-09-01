# Fila de expurgo semanal

Lista central de arquivos classificados como "análise pontual" pelo agent `governance`
(ver `governance.md`, Função 3 — Gatekeeper), aguardando revisão em lote antes de deletar.
**Nunca deletar direto daqui** — só depois que o usuário confirmar em bloco no fim da
semana (ou quando pedir explicitamente "faz o expurgo").

| Arquivo | Flagueado em | Migrado pra | Motivo |
|---|---|---|---|
| `docs/PRODUCTION_RUNBOOK_override_2026-08-16.md` | 2026-08-31 | `CHANGELOG.md` (entrada 2026-08-31) + `docs/technical_dataflow.md` (patch pontual) | Runbook de execução única (Tier 1, cabeçalho já dizia "apagar/arquivar depois de executado") — Parte A (9 objetos) + Parte B (automação de refresh) executadas e confirmadas em produção nesta data. Achados técnicos (ordem A1-A5 errada no doc, fuso horário do agendamento) já migrados pro CHANGELOG. |
