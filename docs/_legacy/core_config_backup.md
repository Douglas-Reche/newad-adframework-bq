# Core Config Backup — adframework.core

> 📦 **HISTÓRICO** — backup de segurança pré-DROP de junho/2026, não é doc de consulta
> ativa (`core.dim_client`/`platform_client_links`/`campaign_format_map` já foram
> re-seedadas e evoluíram desde então — ver `core/OWNERSHIP.yaml` para o estado atual).
> Mantido como referência histórica caso precise reconstituir o estado pré-rebuild.
> Movido para `docs/_legacy/` em 2026-08-09.

> Exportado em 2026-06-16 antes do rebuild do BigQuery.
> Fonte: `adframework.core` (dim_client, platform_client_links, campaign_format_map)
> **NÃO DELETAR** — referência para re-seed após DROP dos datasets.

---

## 1. `core.dim_client` — 26 clientes

| client_id | slug | name | sector | status | client_level | parent_client_id | notes |
|---|---|---|---|---|---|---|---|
| `amigo_db1c2f0c` | amigo | Amigo | unknown | active | 2 | `tecpar_edfcc744` | aguardando confirmacao comercial |
| `aperam_14d1f27e` | aperam | Aperam | industria | active | 1 | — | — |
| `banco_cora_fe13d78a` | banco_cora | Banco Cora | fintech | active | 1 | — | — |
| `bet7k_b777ab9c` | bet7k | Bet7k | apostas | active | 1 | — | Aparece em MGID sem delivery. Aguardando confirmacao comercial. |
| `caloi_8ac28140` | caloi | Caloi | unknown | active | 1 | — | 689K imp no MediaSmart + 2 campanhas MGID sem delivery. Aguardando confirmacao. |
| `casa_construtor_adf15c2c` | casa_construtor | Casa do Construtor | construcao | active | 2 | `dax_agency_00000001` | — |
| `catalise_0b7d18d6` | catalise | Catalise | unknown | active | 1 | — | 1.2M imp no MGID (mar/2026). Nao estava na lista de clientes. Aguardando confirmacao. |
| `dax_agency_00000001` | dax | DAX | Agência | active | 1 | — | Agência guarda-chuva que gerencia Dr. Consulta, Dr. Consulta RJ e Casa do Construtor |
| `dooing_994db77e` | dooing | Dooing | imobiliario | active | 1 | — | — |
| `dr_consulta_215378ef` | dr_consulta | Dr. Consulta | saude | active | 2 | `dax_agency_00000001` | — |
| `dr_consulta_rj_11040bf9` | dr_consulta_rj | Dr. Consulta RJ | saude | active | 2 | `dax_agency_00000001` | aguardando confirmacao comercial |
| `efi_bank_ee79e91b` | efi_bank | Efi Bank | fintech | active | 1 | — | — |
| `einstein_6b33a588` | einstein | Einstein | saude_educacao | active | 1 | — | — |
| `fox_lux_55ed8992` | fox_lux | Fox Lux | unknown | active | 1 | — | — |
| `lab2lab_efb1cb34` | lab2lab | Lab2Lab | unknown | active | 1 | — | Aparece em MGID sem delivery. Aguardando confirmacao comercial. |
| `luckbet_bea15ebc` | luckbet | LuckBet | apostas | active | 1 | — | — |
| `mopar_a47949f4` | mopar | Mopar | automotivo | active | 1 | — | — |
| `mrv_f19a2136` | mrv | MRV | imobiliario | active | 1 | — | — |
| `ocupacional_98c851f5` | ocupacional | Ocupacional | saude_ocupacional | active | 2 | `pardini_60395024` | — |
| `pardini_60395024` | pardini | Pardini | saude_labs | active | 1 | — | — |
| `patio_medeiros_874a0358` | patio_medeiros | Patio Medeiros | unknown | active | 1 | — | — |
| `senar_105bd174` | senar | Senar | unknown | active | 1 | — | — |
| `stocco_b712c66e` | stocco | Stocco | unknown | active | 1 | — | aguardando confirmacao comercial |
| `stoquinho_56a6ee2a` | stoquinho | Stoquinho | educacao | active | 2 | `stocco_b712c66e` | aguardando confirmacao comercial |
| `tecpar_edfcc744` | tecpar | TecPar | unknown | active | 1 | — | aguardando confirmacao comercial |
| `townhouses_bc40f009` | townhouses | TownHouses | imobiliario | active | 1 | — | — |

---

## 2. `core.platform_client_links` — 155 vínculos

### MediaSmart — eventid links (14 vínculos)

| link_value (eventid) | client_id | status | notes |
|---|---|---|---|
| `newad_brazil-neu83z5jjnkcnrbmwwxjsrzzfwaigdx7` | NULL | unresolved | eventid compartilhado por Pardini e Ocupacional — aguardando esclarecimento |
| `newad_brazil-oqdfn8xxlwghvcsezq0ixv7ldvckzozp` | `amigo_db1c2f0c` | active | Confirmado — Amigo e sub-cliente ativo de TecPar |
| `newad_brazil-lmslprwlhne8cbxmbatffxhsspboav5q` | `aperam_14d1f27e` | active | — |
| `newad_brazil-2ruu4wonoghjuhvngq7lz3xbxcx6mcui` | `banco_cora_fe13d78a` | active | — |
| `newad_brazil-fqpt3ef3uv6gubwadgcrxdjmlum7njnx` | `caloi_8ac28140` | pending_confirmation | CALOI — pendente confirmacao comercial; 689K imp no MediaSmart |
| `newad_brazil-nvwu1cidagrt331cqxqvatuyauxjtofa` | `casa_construtor_adf15c2c` | active | — |
| `newad_brazil-plbe1ab6ic2aoxdlelqrb4h5v2xxqtus` | `dooing_994db77e` | active | — |
| `newad_brazil-a5e1oyk9h6lgr3mhby5exudluugkiuma` | `dr_consulta_rj_11040bf9` | active | aguardando confirmacao comercial Dr Consulta vs RJ |
| `newad_brazil-mew7xi9ewnwy7xysvolgxa6whskxtmmu` | `efi_bank_ee79e91b` | active | — |
| `newad_brazil-oignlzzcisjwprmdxjlilzc3v1j28fi1` | `einstein_6b33a588` | active | — |
| `newad_brazil-0ormcgkknfdbfjkmqeoxbbdwl5xsxng7` | `fox_lux_55ed8992` | active | — |
| `newad_brazil-dzynxhmnrdg2ec0czgdiabqmwvy0qhgj` | `luckbet_bea15ebc` | active | — |
| `newad_brazil-1viks0pwxjnv2hafcvkdjajucmfxxlnq` | `mrv_f19a2136` | active | — |
| `newad_brazil-4au3o3liw2fjujlj6bup6fm05xyqm8a1` | `stocco_b712c66e` | active | aguardando confirmacao comercial Stocco vs Stoquinho |

### MGID — campaignid links (130 vínculos)

| campaign_id | client_id | status | notes |
|---|---|---|---|
| `12224048` | `amigo_db1c2f0c` | active | — |
| `12339737` | `amigo_db1c2f0c` | active | — |
| `12430497` | `amigo_db1c2f0c` | active | Brand / Amigo / Native / Junho 01-30 — add 2026-06-15 |
| `12224047` | `amigo_db1c2f0c` | active | — |
| `12400004` | `amigo_db1c2f0c` | active | — |
| `12273460` | `amigo_db1c2f0c` | active | — |
| `12322542` | `amigo_db1c2f0c` | active | — |
| `12414818` | `amigo_db1c2f0c` | active | — |
| `12322545` | `amigo_db1c2f0c` | active | — |
| `12273466` | `amigo_db1c2f0c` | active | — |
| `12184060` | `amigo_db1c2f0c` | active | — |
| `12298875` | `amigo_db1c2f0c` | active | — |
| `12400002` | `amigo_db1c2f0c` | active | — |
| `12298866` | `amigo_db1c2f0c` | active | — |
| `12298867` | `amigo_db1c2f0c` | active | — |
| `12368541` | `amigo_db1c2f0c` | active | — |
| `12339736` | `amigo_db1c2f0c` | active | — |
| `12246781` | `amigo_db1c2f0c` | active | — |
| `12339738` | `amigo_db1c2f0c` | active | — |
| `12184059` | `amigo_db1c2f0c` | active | — |
| `12414816` | `amigo_db1c2f0c` | active | — |
| `12224045` | `amigo_db1c2f0c` | active | — |
| `12273461` | `amigo_db1c2f0c` | active | — |
| `12224046` | `amigo_db1c2f0c` | active | — |
| `12322540` | `amigo_db1c2f0c` | active | — |
| `12196876` | `amigo_db1c2f0c` | active | — |
| `12196878` | `amigo_db1c2f0c` | active | — |
| `12273462` | `amigo_db1c2f0c` | active | — |
| `12368539` | `amigo_db1c2f0c` | active | — |
| `12246782` | `amigo_db1c2f0c` | active | — |
| `12368544` | `amigo_db1c2f0c` | active | — |
| `12196877` | `amigo_db1c2f0c` | active | — |
| `12246780` | `amigo_db1c2f0c` | active | — |
| `12322541` | `amigo_db1c2f0c` | active | — |
| `12339734` | `amigo_db1c2f0c` | active | — |
| `12196875` | `amigo_db1c2f0c` | active | — |
| `12246779` | `amigo_db1c2f0c` | active | — |
| `12298872` | `amigo_db1c2f0c` | active | — |
| `12368543` | `amigo_db1c2f0c` | active | — |
| `12251219` | `aperam_14d1f27e` | active | — |
| `12273319` | `aperam_14d1f27e` | active | — |
| `12322530` | `aperam_14d1f27e` | active | — |
| `12273321` | `aperam_14d1f27e` | active | — |
| `12251786` | `aperam_14d1f27e` | active | — |
| `12301954` | `aperam_14d1f27e` | active | — |
| `12301953` | `aperam_14d1f27e` | active | — |
| `12322529` | `aperam_14d1f27e` | active | — |
| `12196873` | `banco_cora_fe13d78a` | active | — |
| `12273458` | `banco_cora_fe13d78a` | active | — |
| `12326714` | `banco_cora_fe13d78a` | active | — |
| `12298848` | `banco_cora_fe13d78a` | active | — |
| `12220919` | `banco_cora_fe13d78a` | active | — |
| `12339730` | `banco_cora_fe13d78a` | active | — |
| `12273457` | `banco_cora_fe13d78a` | active | — |
| `12246818` | `banco_cora_fe13d78a` | active | — |
| `12400006` | `banco_cora_fe13d78a` | active | — |
| `12196874` | `banco_cora_fe13d78a` | active | — |
| `12414810` | `banco_cora_fe13d78a` | active | — |
| `12246817` | `banco_cora_fe13d78a` | active | — |
| `12368531` | `banco_cora_fe13d78a` | active | — |
| `12220920` | `banco_cora_fe13d78a` | active | — |
| `12414814` | `banco_cora_fe13d78a` | active | — |
| `12437129` | `banco_cora_fe13d78a` | active | Banco Cora / Native / Jun-Jul 11/06-10/07 — add 2026-06-15 |
| `12298849` | `banco_cora_fe13d78a` | active | — |
| `12078841` | `bet7k_b777ab9c` | pending_confirmation | — |
| `12083624` | `bet7k_b777ab9c` | pending_confirmation | — |
| `12060612` | `bet7k_b777ab9c` | pending_confirmation | — |
| `12083627` | `bet7k_b777ab9c` | pending_confirmation | — |
| `12159901` | `caloi_8ac28140` | pending_confirmation | — |
| `12116277` | `caloi_8ac28140` | pending_confirmation | — |
| `12384838` | `catalise_0b7d18d6` | pending_confirmation | 1.2M imp mar/2026 — cliente nao confirmado |
| `12283455` | `dooing_994db77e` | active | — |
| `12321172` | `dr_consulta_215378ef` | active | — |
| `12297181` | `dr_consulta_215378ef` | active | — |
| `12321171` | `dr_consulta_215378ef` | active | — |
| `12297182` | `dr_consulta_215378ef` | active | — |
| `12374019` | `dr_consulta_rj_11040bf9` | active | — |
| `12333908` | `dr_consulta_rj_11040bf9` | active | — |
| `12333909` | `dr_consulta_rj_11040bf9` | active | — |
| `12289450` | `efi_bank_ee79e91b` | active | — |
| `12298879` | `efi_bank_ee79e91b` | active | — |
| `12430495` | `einstein_6b33a588` | active | Einstein / Native / Junho 01-30 — add 2026-06-15 |
| `12416908` | `einstein_6b33a588` | active | — |
| `12374021` | `einstein_6b33a588` | active | — |
| `12414276` | `einstein_6b33a588` | active | — |
| `12400020` | `einstein_6b33a588` | active | — |
| `12241369` | `fox_lux_55ed8992` | active | — |
| `11877910` | `lab2lab_efb1cb34` | pending_confirmation | — |
| `12333892` | `luckbet_bea15ebc` | active | — |
| `12273475` | `luckbet_bea15ebc` | active | — |
| `12246849` | `luckbet_bea15ebc` | active | — |
| `12220857` | `luckbet_bea15ebc` | active | — |
| `12246847` | `luckbet_bea15ebc` | active | — |
| `12372673` | `luckbet_bea15ebc` | active | — |
| `12220858` | `luckbet_bea15ebc` | active | — |
| `12212704` | `luckbet_bea15ebc` | active | — |
| `12372675` | `luckbet_bea15ebc` | active | — |
| `12212612` | `luckbet_bea15ebc` | active | — |
| `12276194` | `mopar_a47949f4` | active | — |
| `12276195` | `mopar_a47949f4` | active | — |
| `12298832` | `mopar_a47949f4` | active | — |
| `12236535` | `mrv_f19a2136` | active | — |
| `11969739` | `pardini_60395024` | active | — |
| `11944803` | `pardini_60395024` | active | — |
| `11916496` | `pardini_60395024` | active | — |
| `12093311` | `pardini_60395024` | active | — |
| `12126341` | `pardini_60395024` | active | — |
| `12093313` | `pardini_60395024` | active | — |
| `12126343` | `pardini_60395024` | active | — |
| `11933918` | `pardini_60395024` | active | — |
| `12264568` | `pardini_60395024` | active | — |
| `12231080` | `pardini_60395024` | active | — |
| `11969737` | `pardini_60395024` | active | — |
| `11933911` | `pardini_60395024` | active | — |
| `12093310` | `pardini_60395024` | active | — |
| `12366313` | `patio_medeiros_874a0358` | active | — |
| `12334682` | `patio_medeiros_874a0358` | active | — |
| `12419236` | `senar_105bd174` | active | — |
| `12419235` | `senar_105bd174` | active | — |
| `12430502` | `senar_105bd174` | active | Senar / Native / Junho 01-30 — add 2026-06-15 |
| `12430501` | `senar_105bd174` | active | Senar / Push / Junho 01-30 — add 2026-06-15 |
| `12301950` | `stocco_b712c66e` | active | — |
| `12259280` | `stocco_b712c66e` | active | — |
| `12281330` | `stocco_b712c66e` | active | — |
| `12281333` | `stoquinho_56a6ee2a` | pending_confirmation | — |
| `12259284` | `stoquinho_56a6ee2a` | pending_confirmation | — |
| `12301951` | `stoquinho_56a6ee2a` | pending_confirmation | — |
| `12324550` | `stoquinho_56a6ee2a` | pending_confirmation | — |
| `12432098` | `stoquinho_56a6ee2a` | active | Stoquinho / Native / Jun — add 2026-06-15 |
| `12224819` | `townhouses_bc40f009` | active | — |

### Siprocal — advertiser links (11 vínculos)

| link_value (advertiser) | client_id | status | notes |
|---|---|---|---|
| `AMIGOTECPAR` | `amigo_db1c2f0c` | active | advertiser unico que cobre Amigo+TecPar no Siprocal |
| `APERAM` | `aperam_14d1f27e` | active | — |
| `BANCOCORA` | `banco_cora_fe13d78a` | active | — |
| `CATALISE` | `catalise_0b7d18d6` | active | — |
| `DOOING` | `dooing_994db77e` | active | — |
| `DRCONSULTA` | `dr_consulta_215378ef` | active | — |
| `LUCKBET` | `luckbet_bea15ebc` | active | — |
| `PARDINI` | `pardini_60395024` | active | — |
| `PATIOMEDEIROS` | `patio_medeiros_874a0358` | active | — |
| `SENAR` | `senar_105bd174` | active | — |
| `TECPAR` | `tecpar_edfcc744` | active | aguardando confirmacao comercial |

---

## 3. `core.campaign_format_map` — 18 mapeamentos

> Nota: campo `format` no BQ (não `category`). Gold usa `UPPER(format)` como `category`.

| platform | platform_campaign_id | client_id | format | notes |
|---|---|---|---|---|
| `mediasmart` | `xhhllbabxmo2qkxc9whasy8hhkyiezcz` | `banco_cora_fe13d78a` | Retargeting | CORA_CONTADIGITAL_RETARGETING_* |
| `mediasmart` | `ort2cyrsbe6bi3qwih8oevekeuufbslj` | `banco_cora_fe13d78a` | Retargeting | CORA_CONTADIGITAL_RETARGETING_* |
| `mediasmart` | `errlanmxbhbi6pk0v1oexsi18qqhdjwi` | `banco_cora_fe13d78a` | Display | CORA_CONTADIGITAL_DISPLAY_* / JANEIRO_DISPLAY |
| `mediasmart` | `rzbgy9dnanut237evniapc8vkxv7rnkf` | `banco_cora_fe13d78a` | Display | CORA_CONTADIGITAL_JANEIRO_DISPLAY |
| `mediasmart` | `axanbi5rdtyqkndet6fcxwz6zsqzh1et` | `banco_cora_fe13d78a` | Video | CORA_CONTADIGITAL_VIDEO_* |
| `mediasmart` | `xn12soc3trqqcaejkxixiewtrwvuzwxe` | `banco_cora_fe13d78a` | Video | CORA_CONTADIGITAL_VIDEO_* |
| `mgid` | `12326714` | `banco_cora_fe13d78a` | Native | Banco Cora / Native / 01/01-31/01 |
| `mgid` | `12339730` | `banco_cora_fe13d78a` | Native | Banco Cora / Native / 01/02-28/02 |
| `mgid` | `12368531` | `banco_cora_fe13d78a` | Native | Banco Cora / Native / 01/03-31/03 |
| `mgid` | `12298849` | `banco_cora_fe13d78a` | Native | Banco Cora / Native / 01/12-31/12 |
| `mgid` | `12400006` | `banco_cora_fe13d78a` | Native | Banco Cora / Native / Abril |
| `mgid` | `12414810` | `banco_cora_fe13d78a` | Native | Banco Cora / Native / Maio 01-10 |
| `mgid` | `12414814` | `banco_cora_fe13d78a` | Native | Banco Cora / Native / Maio/Jun |
| `mgid` | `12298848` | `banco_cora_fe13d78a` | Push | Banco Cora / Push / 01/12-31/12 |
| `siprocal` | `` | `banco_cora_fe13d78a` | Push | Siprocal sem campaign_id — assumido Push, verificar |
| `siprocal` | `30` | `banco_cora_fe13d78a` | Push | Verificar formato real com equipe |
| `siprocal` | `34` | `banco_cora_fe13d78a` | Push | Verificar formato real com equipe |
| `siprocal` | `38` | `banco_cora_fe13d78a` | Push | Verificar formato real com equipe |

---

## Observações para o rebuild

- `campaign_format_map` só tem mapeamentos de **Banco Cora** — os demais clientes usam constantes no código (MGID → NATIVE, Siprocal → PUSH)
- `platform_client_links` tem 1 eventid MediaSmart **unresolved** (Pardini/Ocupacional compartilham o mesmo eventid — pendente esclarecimento)
- Clientes com `pending_confirmation`: Bet7k, Caloi, Catalise, Lab2Lab, Stoquinho (MGID) — confirmar antes de ativar no rebuild
- `newad_account_id` é sempre `newad_main` para todos os clientes ativos
