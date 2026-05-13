# Registro de Clientes — AdFramework

> Última atualização: 2026-05-12

## Clientes com entrega real confirmada

| newad_client_id | Nome | Status | MediaSmart account | MGID account | Siprocal account | Observação |
|---|---|---|---|---|---|---|
| `nwd_luckbet_a485d6bc` | Luckbet | **CANÔNICO** | `newad_brazil-dzynxh...` | 12220857 | luckbet | Usar este, ignorar _69e72f18 |
| `nwd_banco-cora_acfae3ab` | Banco Cora | Ativo | `newad_brazil-2ruu4w...` | 12368531 | bancocora | IO apenas para mar/26 |
| `nwd_tec-par_4ee38788` | TecPar | Ativo | `newad_brazil-oqdfn8...` | 12339736 | tecpar | 31M impressões |
| `nwd_casa-do-construtor_6a447f18` | Casa do Construtor | Ativo | `newad_brazil-nvwu1c...` | — | — | 16M impressões |
| `nwd_einstein_223330d5` | Einstein | Ativo | `newad_brazil-oignlz...` | — | — | 3M impressões |
| `nwd_dr-consulta_6fa795e9` | Dr. Consulta | Ativo | `newad_brazil-a5e1oy...` | 12333908 | drconsulta | 7.5M impressões |
| `nwd_stocco_3d6ca7f5` | Stocco | Ativo | `newad_brazil-4au3o3...` | — | — | 2.5M impressões |

## Clientes problemáticos / a resolver

| newad_client_id | Nome | Problema | Ação necessária |
|---|---|---|---|
| `nwd_luckbet_69e72f18` | Luckbet (legacy) | Mesmo campaign IDs que o canônico — duplica entrega | Desativar todos os IOs e bindings |
| `nwd_internal_newad` | NewAD Interno | Aponta para conta MediaSmart da Luckbet — contamina gold | Corrigir link_value no Admin UI |

## Clientes sem entrega real

| newad_client_id | Nome | Observação |
|---|---|---|
| `nwd_catalise_48ac10a2` | Catalise | Link MGID cadastrado (12384838), sem impressões |
| `nwd_demo_adv_powerbet` | PowerBet Demo | Sem link de plataforma ativo — apenas para testes |

## IDs de conta por plataforma (platform_client_links)

### MediaSmart — link_value = advertiser account ID
Formato: `newad_brazil-XXXXX`

### MGID — link_value = advertiser account ID numérico

### Siprocal — link_value = nome do anunciante (ex: `luckbet`, `bancocora`)
⚠️ Siprocal não tem ID estruturado — atribuição por nome. Risco de colisão.
