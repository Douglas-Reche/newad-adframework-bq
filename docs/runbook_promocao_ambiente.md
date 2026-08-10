# Runbook de Promoção de Ambiente — staging → produção

> **Manutenção:** Tier 2 — revisão quando o processo de deploy mudar

> ✅ ATUAL | Criado 2026-08-09 | Baseado em `scripts/deploy/apply_ddl.py` (mecanismo real de
> teste em 2 níveis) e no histórico de promoção documentado em `CHANGELOG.md`
> (2026-08-06, teste ponta-a-ponta em `douglas-bq-staging` + paridade validada). Ver
> `docs/environments.md` para a diferença de projeto GCP entre os dois ambientes.

Promover uma mudança de `douglas-bq-staging` pra `adframework` (produção) nunca é um
simples `git push` ou `git revert` — os dois ambientes são **projetos GCP diferentes**,
então promover/reverter significa reaplicar (ou desfazer) DDL contra o projeto certo.

---

## Passos mecânicos

1. **Branch** — trabalhar a mudança numa branch, nunca direto na `main` (branch
   protection ainda não está habilitada nos dois repos — ver `docs/known_issues.md` S1 —
   então isso é convenção, não bloqueio técnico).

2. **Testar em staging:**
   ```bash
   python scripts/deploy/apply_ddl.py <caminho>/arquivo.sql --env=test \
     --project=douglas-bq-staging --reason="..." --summary="..."
   ```
   Se a mudança exigir dado (não só schema), popular/copiar o necessário em
   `douglas-bq-staging` primeiro (ver `docs/environments.md` — nunca `SELECT *`
   posicional entre schemas potencialmente divergentes, usar lista explícita de colunas).

3. **Validar em staging** — confirmar comportamento correto contra o objetivo da mudança.
   Para views que substituem uma view de produção, rodar `EXCEPT DISTINCT` nos dois
   sentidos contra o equivalente de produção (aplicado em staging via
   `--project=douglas-bq-staging`) — precisão de `ROUND(..., 2)` é aceitável pra
   ruído de ponto flutuante em colunas `FLOAT64` agregadas (ver `CHANGELOG.md`
   2026-08-06, validação de `gold.fact_pacing`).

4. **PR** — abrir PR com a mudança e o resultado da validação em staging na descrição
   (query de `EXCEPT DISTINCT`, contagem de linhas, ou o teste relevante pro tipo de
   mudança). `CODEOWNERS` já lista `@Douglas-Reche` como owner de
   `/raw /stg /core /gold /marts /share /scripts/deploy /hub` — revisão é dele.

5. **Promoção** — aplicar o **mesmo arquivo**, sem nenhuma edição entre teste e produção:
   ```bash
   python scripts/deploy/apply_ddl.py <caminho>/arquivo.sql --env=prod \
     --reason="..." --summary="..."
   ```
   `--env=prod` roda o arquivo exatamente como está no git, sem substituição de dataset —
   é por isso que o passo 3 precisa ter testado o texto real, não uma variação.

   > **Confirmação interativa obrigatória (2026-08-09):** `--env=prod` só prossegue depois
   > que uma pessoa digita ao vivo, num terminal, o nome exato do objeto sendo alterado.
   > Não existe flag de bypass — rodar isso via automação/script não-interativo falha de
   > propósito (`EOF` no `input()`), não é bug. O mesmo vale para `--rollback` (Caso 1
   > abaixo), que também só escreve em produção.

6. **Confirmar em produção** — reconferir o objeto criado/atualizado (contagem de linhas,
   uma query de sanidade) antes de considerar a promoção concluída.

---

## Registro de auditoria automático

Toda execução de `apply_ddl.py` (test **ou** prod) grava uma linha em
`core.schema_change_log` — sempre no dataset `core` real de produção, nunca `core_test`,
mesmo quando o `--env=test` ou `--project` aponta pra staging. Isso é o que possibilita o
rollback abaixo. Nunca rodar com `--no-log` fora de debug pontual.

---

## Plano de rollback

Reverter uma promoção não é `git revert` — o arquivo `.sql` no repo pode já refletir a
versão nova, mas o **objeto físico em produção** só volta ao estado anterior com uma ação
explícita contra o projeto certo.

### Caso 1 — DDL já aplicada em produção, precisa reverter

```bash
python scripts/deploy/apply_ddl.py --rollback <change_id>
```

Reaplica a `previous_definition` capturada automaticamente em `core.schema_change_log`
antes de qualquer `--env=prod` sobrescrever um objeto existente. `<change_id>` vem da
linha de auditoria da promoção original (`core.schema_change_log`).

**Se `previous_definition` não foi capturada** (ex: objeto criado pela primeira vez, sem
versão anterior) — não há o que reverter via `--rollback`; a ação é `DROP` manual do
objeto, com confirmação explícita antes (ver `docs/runbook_incidente_operacional.md` pra
critério de quando uma ação dessas é segura).

### Caso 2 — deploy rodou contra o projeto errado

Já aconteceu uma classe de bug real relacionada (ver `docs/known_issues.md` R3): um bug em
`swap_project()` fazia `--project douglas-bq-staging` reescrever referências a `stg`/`raw`
que deveriam continuar apontando pra produção, gerando uma tabela inexistente
(`douglas-bq-staging.stg.ms_delivery`). Corrigido via `PHYSICAL_DATASETS = {"core", "gold"}`
— só esses dois datasets trocam de projeto quando `--project` é usado; `raw`/`stg` nunca
trocam.

Se uma promoção rodar contra o projeto errado apesar dessa proteção:
1. Confirmar com `--dry-run` o que o comando geraria antes de qualquer ação corretiva.
2. Se o objeto errado foi de fato criado/sobrescrito no projeto errado, tratar como Caso 1
   (rollback via `previous_definition`) se o objeto já existia lá antes, ou `DROP` manual
   se foi criação nova indevida.
3. Reaplicar corretamente contra o projeto certo.

### Caso 3 — dado (não só schema) foi promovido incorretamente

Não há rollback automático de dado carregado via `load_historical_override.py` ou scripts
de sync (`sync_drive.py`, `sync_sheet.py`) — esses não passam por `apply_ddl.py`, não
geram `schema_change_log`. Antes de qualquer carga em produção que não seja idempotente
(`WRITE_TRUNCATE` reversível só se a fonte original ainda existir; `WRITE_APPEND`
não-reversível sem chave de dedup), confirmar explicitamente com o usuário — mesmo
critério de "checar antes de inserir" já usado em `core.*` de referência.

---

## O que NÃO é revertido por `git revert`

- **Objetos físicos no BigQuery** (tabelas, views, funções) — só voltam com `--rollback`
  ou `DROP`/`CREATE OR REPLACE` manual contra o projeto certo.
- **Dado carregado** — precisa de ação específica por tipo de carga (ver Caso 3).
- **Bindings de IAM** aplicados por `hub/deploy.sh` ou `gcloud`/`bq` direto — revertidos
  manualmente (`gcloud ... remove-iam-policy-binding`), nunca por `git revert`.

`git revert` só desfaz o **arquivo `.sql`/`.py` versionado** — o efeito físico no BigQuery
exige reaplicar o mecanismo acima contra o ambiente certo.
