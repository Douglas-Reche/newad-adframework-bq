# CLAUDE.md — AdFramework BQ Pipeline

Instruções permanentes para sessões Claude Code neste repositório.
Carregado automaticamente em toda nova sessão.

---

## Contexto

- **Repo:** `newad-adframework-bq` — SQL, DDLs, seeds, migrations, agents BigQuery
- **Projeto GCP (produção):** `adframework`
- **Pipeline:** RAW → STG → CORE → GOLD → Power BI
- **Maintainers:** Douglas Reche (escrita), Shiro (leitura via `rshiro-newad/adframework`)
- **Second brain:** Notion — contexto, decisões e estado de negócio

---

## Regras absolutas — nunca violar

| O que | Regra |
|---|---|
| Datasets `pixel`, `adtracking`, `analytics`, `finops_billing` | **Intocáveis** — serviços externos, nunca modificar |
| Tabelas `io_manager_v2`, `io_line_bindings_v2`, `proposals`, `proposal_lines`, views `_v4` | **Admin UI do Shiro** — nunca referenciar no pipeline gold |
| Projeto `striped-bonfire-489318-t9` | **Nunca modificar** — dashboard emergencial temporário |
| Repo `rshiro-newad/adframework` | **Somente leitura** — analisar, nunca modificar |

---

## Protocolo de registro

### O que vai para o git
Tudo que é **código, schema ou dado canônico**:
- DDL (tabelas e views de qualquer camada)
- Migrations executadas no BQ
- Seeds e CSVs de referência
- Scripts SQL de auditoria e inspeção
- Agentes Python
- Documentação técnica de API e design de camadas
- `CHANGELOG.md` — obrigatório em toda sessão com decisão relevante
- `docs/INDEX.md` — atualizar quando criar ou modificar docs

**Formato CHANGELOG:**
```
## YYYY-MM-DD — {título}
{1-3 linhas: o que foi feito e por quê}
```

### O que vai para o Notion
Tudo que é **contexto, raciocínio ou estado de negócio**:
- Decisões técnicas (o porquê de cada escolha arquitetural)
- Issues identificados e resolvidos
- Contexto de cliente (prazos, pedidos, histórico comercial)
- IO Plans e contexto de entrega
- Perguntas pendentes para área comercial

### O que vai para os dois
- Novo cliente → seed no git + registro no Notion
- Novo link plataforma → cliente → seed no git + Notion

---

## Checklist de fim de sessão

Executar nesta ordem antes de encerrar:

1. `CHANGELOG.md` — entry com data e resumo das decisões
2. `docs/INDEX.md` — atualizar se criou ou modificou docs
3. **Notion** — registrar decisões técnicas, issues e contexto de cliente
4. **git commit** — pedir confirmação ao usuário antes de commitar
