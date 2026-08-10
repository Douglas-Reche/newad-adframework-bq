# Diagrama Técnico — Topologia de Sistema + DFD Medallion

> **Manutenção:** híbrido de dois tiers, cada seção com gatilho próprio.
> - **Diagrama 1 (Topologia de Sistema)** — Tier 2. Muda por decisão de arquitetura/deploy
>   (novo repositório, novo projeto GCP, novo consumidor, novo workflow de CI/CD) — não é
>   gerado de `INFORMATION_SCHEMA`, é lido do código real (`apply_ddl.py`,
>   `.github/workflows/*.yml`, `docs/io_plan_domain.md`, scripts de override histórico).
>   Revisitar quando qualquer uma dessas peças mudar de lugar ou de mecanismo.
> - **Diagrama 2 (DFD Medallion)** — Tier 1. Nomes de tabela/view devem ser regenerados por
>   consulta a `INFORMATION_SCHEMA.TABLES`/`VIEWS` dos dois projetos (`adframework`,
>   `douglas-bq-staging`) sempre que houver dúvida se está desatualizado — não editar de
>   memória.
>
> Verificado ao vivo em **2026-08-09** contra `adframework` (produção) e
> `douglas-bq-staging` (staging), via `INFORMATION_SCHEMA.TABLES`/`VIEWS` dos dois projetos
> + leitura de `scripts/deploy/apply_ddl.py`, `.github/workflows/*.yml`,
> `scripts/deploy/load_historical_raw.py`/`normalize_historical_upload.py`/
> `load_historical_override.py`, `docs/io_plan_domain.md` e `docs/runbook_promocao_ambiente.md`.

---

## Diagrama 1 — Topologia de Sistema (C4 Nível 2 — Containers)

Mostra como o código sai do GitHub e vira schema aplicado no BigQuery, os dois projetos
GCP como blocos distintos, os consumidores finais, e onde cada mecanismo de ingestão
(diário via API, Drive, upload manual de histórico) se encaixa.

```mermaid
flowchart TB
    subgraph EXT["Fontes externas"]
        MSAPI["MediaSmart API"]
        MGAPI["MGID API"]
        SPAPI["Siprocal — Google Sheets"]
        DRIVE["Google Drive — IO Plan (.xlsx)\nCLIENT/ANO/MÊS/PLANO"]
        SHEET["Planilha de cliente\n(histórico manual, ad hoc)"]
    end

    subgraph INGEST["Ingestão"]
        ETL["adframework_python ETL\nCloud Run: adframework-etl\n(Cloud Scheduler diário)"]
        SYNCDRIVE["sync_drive.py\nCloud Run: services/io-plan-admin\n(POST /sync, sob demanda)"]
        HISTLOAD["load_historical_raw.py\n(manual, CLI, sempre --project staging)"]
        HISTNORM["normalize_historical_upload.py\n+ historical_mappings/&lt;client_id&gt;.py\n(manual, CLI)"]
        HISTOVR["load_historical_override.py\n(manual, CLI, default --project=adframework)"]
    end

    subgraph GH["GitHub — newad-adframework-bq"]
        DDL["raw/ddl, stg/ddl, core/ddl, gold/ddl\n(.sql versionado)"]
        APPLYDDL["scripts/deploy/apply_ddl.py\n(execução MANUAL — não disparada por CI/CD)"]
        GHA["GitHub Actions\nhub_deploy.yml — só hub/**\ncora_sheets_sync.yml — projeto à parte"]
    end

    subgraph PROD["GCP: adframework (PRODUÇÃO)"]
        PRAW["raw.*"]
        PSTG["stg.*"]
        PCORE["core.*"]
        PGOLD["gold.*"]
    end

    subgraph STG_ENV["GCP: douglas-bq-staging (STAGING)"]
        SRAW["raw.* (snapshot físico de prod, 18 tabelas)\n+ raw.historical_uploads / historical_uploads_meta\n(existem SÓ aqui)"]
        SSTG["stg.* (físico local)\n+ stg.historical_overrides_delivery\n(existe SÓ aqui)"]
        SCORE["core.* (físico local)\n+ client_reporting_source_config\n+ resolve_reporting_source()\n(existem SÓ aqui, staging_only)"]
        SGOLD["gold.* (físico local)"]
        SPLANNED["core.client_business_rules\n🔜 PLANEJADO — não construído\n(task Notion 'Desenhar core.client_business_rules', Waiting)"]
    end

    subgraph CONSUME["Consumo"]
        HUB["Hub — douglas-data-hub\nCloud Run, Streamlit\n(inclui 'Comparar Snapshot: Planilha vs. Dado Real')"]
        PBI["Power BI\n(SA powerbi-reader, read-only)"]
    end

    MSAPI --> ETL
    MGAPI --> ETL
    SPAPI --> ETL
    ETL -->|"WRITE_TRUNCATE/APPEND diário"| PRAW

    DRIVE --> SYNCDRIVE
    SYNCDRIVE -->|"WRITE_APPEND + skip por modifiedTime"| PRAW

    SHEET -->|"upload via Hub"| HISTLOAD
    HISTLOAD --> SRAW
    SRAW --> HISTNORM
    HISTNORM -->|"CSV normalizado"| HISTOVR
    HISTOVR -->|"default: adframework.stg\n(tabela só existe hoje em staging)"| SSTG
    HISTOVR -.->|"--project douglas-bq-staging\n(uso real hoje)"| SSTG

    DDL --> APPLYDDL
    APPLYDDL -->|"--env=prod (default --project=adframework)"| PROD
    APPLYDDL -->|"--project=douglas-bq-staging"| STG_ENV
    GHA -->|"push em hub/** → deploy automático"| HUB

    PRAW --> PSTG --> PCORE --> PGOLD
    SRAW --> SSTG --> SCORE --> SGOLD

    PGOLD --> HUB
    PGOLD --> PBI
    SGOLD -.->|"validação pré-promoção\n(ver runbook_promocao_ambiente.md)"| APPLYDDL

    style SPLANNED stroke-dasharray: 5 5
    style HISTLOAD stroke-dasharray: 3 3
    style HISTNORM stroke-dasharray: 3 3
    style HISTOVR stroke-dasharray: 3 3
```

**Notas de precisão (não simplificar na próxima edição sem reconfirmar):**
- `apply_ddl.py` **nunca roda via GitHub Actions** — é sempre execução manual (Douglas ou
  um agente com acesso ao BigQuery). O único workflow de CI/CD real do repo que faz deploy
  automático é `hub_deploy.yml` (só para `hub/**`). `cora_sheets_sync.yml` existe no mesmo
  repo mas escreve num projeto GCP totalmente à parte (`striped-bonfire-489318-t9`,
  dashboard emergencial temporário — fora do escopo deste diagrama).
- A árvore de **dado histórico manual** é genuinamente separada da ingestão diária: 3
  scripts CLI distintos, cada um rodado à mão, em sequência (`load_historical_raw.py` →
  `normalize_historical_upload.py` → `load_historical_override.py`), sem Cloud Scheduler
  nem gatilho automático. As duas primeiras etapas só têm onde rodar em
  `douglas-bq-staging` (`raw.historical_uploads`/`historical_uploads_meta` não existem
  fisicamente em produção). `load_historical_override.py` aceita `--project` apontando
  para produção (`adframework`, valor default do flag), mas como a tabela-alvo
  (`stg.historical_overrides_delivery`) **não existe ainda em produção** (só em staging —
  confirmado ao vivo em 2026-08-09), o uso real hoje é sempre com
  `--project douglas-bq-staging`.
- `core.client_business_rules` é **planejado, não construído** (task Notion "Desenhar
  core.client_business_rules", `Status: Waiting`) — não existe em nenhum dos dois projetos
  (confirmado ao vivo em 2026-08-09). Representado tracejado de propósito para não misturar
  estado real com estado desejado.
- Staging não espelha produção 1:1: produção não tem `raw.historical_uploads`/
  `historical_uploads_meta`, `stg.historical_overrides_delivery`,
  `core.client_reporting_source_config` nem `core.resolve_reporting_source()` — essas 4
  peças existem **só** em `douglas-bq-staging`, de propósito (MVP validado, ainda não
  promovido). Staging também tem um dataset a mais sem equivalente em produção:
  `stg_workbench` (não coberto neste diagrama, fora do escopo do pipeline oficial).

### Componente no diagrama → implementação real

| Componente no diagrama | Implementação real |
|---|---|
| MediaSmart / MGID / Siprocal API → ETL | `adframework_python` (repo irmão, Cloud Run `adframework-etl`) |
| Google Drive → IO Plan | `scripts/io_plan/sync_drive.py`, serviço `services/io-plan-admin/main.py` (endpoint `POST /sync`) |
| Planilha de cliente → histórico manual | `scripts/deploy/load_historical_raw.py` → `scripts/deploy/normalize_historical_upload.py` (+ `scripts/deploy/historical_mappings/<client_id>.py`) → `scripts/deploy/load_historical_override.py` |
| BigQuery RAW/STG/CORE/GOLD (DDL versionado) | `raw/ddl/*.sql`, `stg/ddl/*.sql`, `core/ddl/*.sql`, `gold/ddl/*.sql` |
| Deploy de schema (manual, 2 níveis test/prod) | `scripts/deploy/apply_ddl.py` |
| GitHub Actions (CI/CD) | `.github/workflows/hub_deploy.yml` (deploy automático do Hub), `.github/workflows/cora_sheets_sync.yml` (cron à parte, projeto `striped-bonfire-489318-t9`) |
| Hub | `hub/app.py`, `hub/deploy.sh`, Cloud Run `douglas-data-hub` |
| Power BI | Service Account `powerbi-reader` (read-only), lê `gold.*` diretamente |
| Promoção staging → produção | `docs/runbook_promocao_ambiente.md` (processo), `scripts/deploy/apply_ddl.py --project douglas-bq-staging` → `--env=prod` |

---

## Diagrama 2 — DFD Medallion (fluxo de dado dentro do BigQuery)

Nomes reais de tabela/view, produção (`adframework`) salvo indicação contrária. Onde
staging diverge de produção, ambos os estados aparecem lado a lado.

```mermaid
flowchart LR
    subgraph RAW["RAW"]
        direction TB
        ms_adv["ms_advertisers"]
        ms_camp["ms_campaigns"]
        ms_creat["ms_creatives"]
        ms_creatd["ms_creative_daily"]
        ms_del["ms_delivery"]
        ms_geo["ms_delivery_by_geo"]
        ms_dev["ms_delivery_by_device"]
        ms_hr["ms_delivery_by_hour"]
        mg_camp["mg_campaigns"]
        mg_teas["mg_teasers"]
        mg_del["mg_delivery"]
        mg_geo["mg_delivery_by_geo"]
        mg_dev["mg_delivery_by_device"]
        mg_hr["mg_delivery_by_hour"]
        mg_statd["mgid_stats_daily"]
        mg_statc["mgid_stats_creative"]
        sp_del["sp_delivery"]
        ioplan_raw["io_plan_drive_snapshot"]
        histup["historical_uploads /\nhistorical_uploads_meta\n(SÓ staging)"]
    end

    subgraph STG["STG"]
        direction TB
        stg_msadv["stg.ms_advertisers"]
        stg_mscamp["stg.ms_campaigns"]
        stg_mscreat["stg.ms_creatives"]
        stg_msdel["stg.ms_delivery"]
        stg_msgeo["stg.ms_delivery_by_geo"]
        stg_msdev["stg.ms_delivery_by_device"]
        stg_mshr["stg.ms_delivery_by_hour"]
        stg_mgadv["stg.mg_advertisers"]
        stg_mgcamp["stg.mg_campaigns"]
        stg_mgteas["stg.mg_teasers"]
        stg_mgdel["stg.mg_delivery"]
        stg_mggeo["stg.mg_delivery_by_geo"]
        stg_mgdev["stg.mg_delivery_by_device"]
        stg_mghr["stg.mg_delivery_by_hour"]
        stg_spcli["stg.sp_clients"]
        stg_spcamp["stg.sp_campaigns"]
        stg_spdel["stg.sp_delivery"]
        stg_ioplan["stg.io_plan"]
        stg_unres["stg.unresolved_client_links"]
        stg_hist["stg.historical_overrides_delivery\n(SÓ staging hoje)"]
    end

    subgraph CORE["CORE"]
        direction TB
        core_dim["core.dim_client"]
        core_links["core.platform_client_links"]
        core_fmt["core.campaign_format_map"]
        core_dict["core.dict_format\n+ resolve_dict_format()"]
        core_rules["core.advertiser_platform_rules\n+ resolve_platform_rule()"]
        core_ioplan["core.io_plan_manual"]
        core_histprod["core.historical_overrides_delivery\n(PRODUÇÃO — hardcoded Cora, cutoff 2026-07-01)"]
        core_reportcfg["core.client_reporting_source_config\n+ resolve_reporting_source()\n(SÓ staging, generalizado)"]
        core_planned["core.client_business_rules\n🔜 PLANEJADO"]
    end

    subgraph GOLD["GOLD"]
        direction TB
        g_dimadv["gold.dim_advertiser"]
        g_dimcamp["gold.dim_campaign"]
        g_fdel["gold.fact_delivery"]
        g_fdev["gold.fact_delivery_by_device"]
        g_fsize["gold.fact_delivery_by_size"]
        g_fcreat["gold.fact_delivery_creative"]
        g_fioplan["gold.fact_io_plan"]
        g_fpacing["gold.fact_pacing"]
        g_vwreport["gold.vw_fact_delivery_reporting\n(PRODUÇÃO: UNION fact_delivery + core.historical_overrides_delivery,\nfiltro hardcoded client_id=banco_cora_fe13d78a)"]
    end

    ms_adv --> stg_msadv --> core_links
    ms_camp --> stg_mscamp
    ms_creat --> stg_mscreat
    ms_creatd -.->|"sem STG/GOLD ainda — gap, ver known_issues"| stg_mscamp
    ms_del --> stg_msdel
    ms_geo --> stg_msgeo
    ms_dev --> stg_msdev
    ms_hr --> stg_mshr

    mg_camp --> stg_mgcamp --> stg_mgadv
    mg_teas --> stg_mgteas
    mg_del --> stg_mgdel
    mg_geo --> stg_mggeo
    mg_dev --> stg_mgdev
    mg_hr --> stg_mghr
    mg_statd -.->|"sem STG/GOLD ainda — gap, ver known_issues"| stg_mgcamp
    mg_statc -.->|"sem STG/GOLD ainda — gap, ver known_issues"| stg_mgteas

    sp_del --> stg_spcli
    sp_del --> stg_spcamp
    sp_del --> stg_spdel

    ioplan_raw --> stg_ioplan --> core_ioplan --> g_fioplan

    histup --> stg_hist

    stg_msadv & stg_mgadv & stg_spcli --> core_dim
    core_dim --> g_dimadv

    stg_mscamp & stg_mgcamp & stg_spcamp --> g_dimcamp
    core_fmt -.-> stg_mscamp
    core_dict -.-> stg_mscamp & stg_mgcamp & stg_spcamp

    stg_msdel & stg_mgdel & stg_spdel --> g_fdel
    core_rules -.->|"remapeamento plataforma\n(ex: Push→siprocal)"| g_fdel
    stg_hist -.->|"4ª fonte no UNION ALL\n(commitado no git — filtro via resolve_reporting_source(),\nSÓ ativo em staging hoje)"| g_fdel

    stg_msdev & stg_mgdev --> g_fdev
    stg_msdel & stg_mgdel --> g_fsize
    stg_msdel & stg_mgdel & stg_spdel --> g_fcreat

    g_fioplan --> g_fpacing
    g_fdel --> g_fpacing

    g_fdel --> g_vwreport
    core_histprod -.->|"UNION hardcoded (client_id + data de corte)"| g_vwreport

    core_reportcfg -.->|"planejado para generalizar vw_fact_delivery_reporting\n(hoje só ativo dentro do fact_delivery.sql de staging)"| core_histprod
    core_planned -.-> core_dim
```

**Como ler as linhas tracejadas:** dependência condicional/planejada/parcial — não o
caminho principal de dado. Linhas sólidas = `UNION`/`JOIN`/`SELECT FROM` real e ativo hoje.

**Confirmado ao vivo em 2026-08-09 — divergência de topologia do override histórico entre
produção e staging (ponto mais importante deste diagrama):**
- **Em produção**, o mecanismo é o antigo, hardcoded: `gold.vw_fact_delivery_reporting`
  faz `UNION ALL` entre `gold.fact_delivery` (tudo, exceto Cora antes de 2026-07-01) e
  `core.historical_overrides_delivery` (só Cora, só antes de 2026-07-01) — `client_id` e
  data de corte literais na definição da view.
- **Em staging**, o mecanismo generalizado (por cliente, via `core.resolve_reporting_source()`
  + `core.client_reporting_source_config`) já está embutido diretamente dentro de
  `gold/ddl/fact_delivery.sql` (4ª fonte do `UNION ALL`, lendo
  `stg.historical_overrides_delivery`) — validado ponta-a-ponta (ver `known_issues.md`
  R1/R2/`docs/environments.md`), mas **nunca promovido para produção**.
- As duas árvores de dado histórico (Drive/IO Plan vs. upload manual de override) são
  mecanismos completamente distintos — não confundir: IO Plan é sobre **planejamento**
  (budget), override histórico é sobre **substituir entrega real** por dado retroativo
  quando a plataforma não tinha o histórico.

### Componente no diagrama → implementação real

| Componente no diagrama | Implementação real |
|---|---|
| RAW (ingestão diária MS/MGID/Siprocal) | `raw/ddl/*.sql` |
| RAW → STG (resolução client_id/formato) | `stg/ddl/*.sql` |
| CORE (regras versionadas SCD2) | `core/ddl/dict_format.sql`, `core/ddl/advertiser_platform_rules.sql`, `core/ddl/campaign_format_map.sql`, `core/ddl/resolve_dict_format.sql`, `core/ddl/resolve_platform_rule.sql` |
| GOLD (agregação final) | `gold/ddl/fact_delivery.sql`, `gold/ddl/fact_pacing.sql`, `gold/ddl/dim_campaign.sql`, etc. |
| IO Plan (Drive → RAW → CORE → GOLD) | `scripts/io_plan/sync_drive.py`, `raw/ddl/io_plan_drive_snapshot.sql` (schema), `stg/ddl/io_plan.sql`, `core/ddl/io_plan_manual.sql` (ver `docs/io_plan_domain.md` para o pipeline completo) |
| Override histórico — produção (hardcoded) | `gold/ddl/vw_fact_delivery_reporting.sql`, `core/ddl/historical_overrides_delivery.sql` |
| Override histórico — staging (generalizado, não promovido) | `core/ddl/client_reporting_source_config.sql`, `core/ddl/resolve_reporting_source.sql`, `stg/ddl/historical_overrides_delivery.sql`, `gold/ddl/fact_delivery.sql` (4ª fonte do UNION, só ativa em staging) |
| Upload de histórico (raw → normalizado → carregado) | `scripts/deploy/load_historical_raw.py` → `scripts/deploy/normalize_historical_upload.py` → `scripts/deploy/load_historical_override.py` |
| `core.client_business_rules` (planejado) | Não implementado — task Notion "Desenhar core.client_business_rules" |

---

## Gaps conhecidos já documentados em outro lugar (não repetidos aqui em detalhe)

- `mgid_stats_daily`, `mgid_stats_creative`, `ms_creative_daily` existem em RAW mas ainda
  sem STG/GOLD correspondente — ver `docs/raw_layer_design.md` e `docs/known_issues.md`.
- `_resolve_test_simple` (função órfã em `core`, só existe em produção — confirmado ausente
  em `douglas-bq-staging`) — ver `core/OWNERSHIP.yaml`.

## Achados da varredura de reconhecimento (2026-08-09) — não fazem parte dos diagramas

Antes de fechar B6, foi feita uma varredura completa de todas as pastas de primeiro/segundo
nível do repo (`raw/`, `stg/`, `core/`, `gold/`, `scripts/`, `hub/`, `services/`, `agents/`,
`.github/`, `audit/`) e de `INFORMATION_SCHEMA.ROUTINES` dos dois projetos, pra garantir que
nenhum componente real ficasse de fora por reação só às correções pontuais já incorporadas
acima. Achados que **não** entraram nos diagramas, com o motivo:

- **`gold/delivery/*.sql`, `gold/creative/*.sql`, `gold/dimensions/dim_client_semantics.sql`**
  — arquivos `.sql` no repo que **não correspondem a nenhum objeto vivo em produção nem em
  staging** (confirmado via `INFORMATION_SCHEMA.TABLES`/`VIEWS` dos dois projetos, zero
  resultados para os 7 nomes). `dim_client_semantics.sql` em especial usa o formato de
  `client_id` antigo pré-rebuild (`nwd_luckbet_a485d6bc`, prefixo `nwd_`) — mesma categoria
  de objeto morto já registrada em `known_issues.md` A4/A5/C1 (fechados nesta sessão, ver
  seção correspondente). Não representados no DFD por não serem parte do caminho de dado
  real hoje.
- **`core/migration/*.sql`, `raw/migration/*.sql`, `raw/execute/*.sql`, `core/seeds/*.csv`**
  — scripts de migração/seed numerados (`01_...`, `02_...`), já executados uma vez cada,
  históricos — não são componentes recorrentes do pipeline, são o "como as tabelas `core`/
  `raw` chegaram no estado atual". Não representados no diagrama de topologia (que descreve
  o fluxo recorrente, não o histórico de como se chegou lá).
- **`audit/client_analysis/*.sql`, `audit/raw_layer/*.sql`, `scripts/data_quality/*.sql`,
  `scripts/inspect/*.sql`** — queries SQL ad hoc de auditoria/inspeção, rodadas manualmente
  quando necessário, sem agendamento nem trigger. Não são um "container" do sistema (não
  cabem no nível C4 Containers) — ferramentas de investigação, não infraestrutura.
- **`agents/bq_validator.py`** — CLI de validação que usa a API da Anthropic para decidir
  quais queries rodar contra o BigQuery e interpretar o resultado; ferramenta de
  operação/auditoria (rodada manualmente pelo Douglas ou por um agente), não um componente
  do pipeline de dado em si.
- **`douglas-bq-staging.stg_workbench`** — dataset existe no projeto de staging mas está
  **vazio** (zero tabelas, confirmado ao vivo) — sem uso ativo hoje, não representado no
  diagrama de topologia por não ter conteúdo a mostrar.
- **`hub/jobs_config.yaml`, `hub/powerbi_status.yaml`, `hub/ddl_historical_overrides.sql`**
  — arquivos de configuração/DDL auxiliares do próprio Hub, já cobertos pela caixa única
  "Hub" no Diagrama 1 (nível de detalhe interno do Hub é escopo do `hub/README.md`, mantido
  pelo agente `hub-frontend`, não deste diagrama de pipeline de dado).

Nenhum desses achados mudou a estrutura dos 2 diagramas — todos são ferramentas auxiliares,
histórico já aplicado, ou código morto já coberto por outro doc. Sinalizados aqui para que
a lista fique auditável, não porque exigissem representação própria no desenho.
