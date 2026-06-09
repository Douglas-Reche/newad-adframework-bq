# Perguntas para a Área Comercial

> Criado em: 2026-06-08
> Contexto: levantadas durante auditoria de pipeline para entrega do dashboard Cora/TecPar (prazo: 2026-06-11)

---

## 1. Mapeamento de Conversões (labels no dashboard)

Os pixels MediaSmart têm 5 slots genéricos (conv_1 a conv_5). Sem o nome de negócio de cada evento, o dashboard mostra números sem contexto.

| Cliente | Slot | Eventos (histórico) | Qual é o evento? |
|---|---|---|---|
| **Banco Cora** | conversions_3 | 108 | ? _(ex: "Lead", "Simulação", "Cadastro")_ |
| **Dr. Consulta RJ** | conversions_2 | 51 | ? |
| **Dr. Consulta RJ** | conversions_3 | 21 | ? |
| **Dr. Consulta RJ** | conversions_4 | 4 | ? |

> Luckbet já está mapeado (confirmado por Shiro em 29/04/2026): conv_1=Pageview, conv_2=Cadastro, conv_3=FTD, conv_4=Depósito Recorrente, conv_5=Início Cadastro.

**Pergunta adicional:** TecPar/Amigo, MRV, Einstein e demais clientes ativos têm pixel de conversão configurado no MediaSmart? Se sim, o que cada slot representa?

---

## 2. Confirmação de Campanhas (`pending_confirmation`)

21 vínculos estão mapeados com o cliente sugerido mas aguardam confirmação comercial para entrar com atribuição correta no dashboard.

### MediaSmart — eventids (3)

| Cliente sugerido | O que confirmar |
|---|---|
| **Caloi** (689 mil impressões) | Esse eventid é da Caloi? |
| **Dr. Consulta RJ** | Esse eventid é da RJ (e não da SP)? |
| **Stocco** | Esse eventid é da Stocco (e não da Stoquinho)? |

### MGID — campaign IDs (18)

| Cliente sugerido | Campanhas | O que confirmar |
|---|---|---|
| **Bet7k** | 4 campanhas | São da Bet7k? |
| **Caloi** | 2 campanhas | São da Caloi? |
| **Catalise** | 1 campanha | É da Catalise? (1,2M impressões em mar/26) |
| **Dr. Consulta RJ** | 3 campanhas | São da RJ e não da SP? |
| **Lab2Lab** | 1 campanha | É da Lab2Lab? |
| **Stocco** | 3 campanhas | São da Stocco (não Stoquinho)? |
| **Stoquinho** | 4 campanhas | São da Stoquinho (não Stocco)? |

---

## 3. Eventid Compartilhado — Pardini / Ocupacional

Um eventid MediaSmart tem **4,28 milhões de impressões** sem cliente atribuído — aparece ligado a dois clientes ao mesmo tempo: Pardini e Ocupacional (sub-cliente de Pardini).

**Pergunta:** essas impressões são da Pardini, da Ocupacional, ou divididas? Se divididas, existe critério para separar (período, nome de campanha)?

---

## 4. Google Ads

Há dados de Google Ads para algum cliente gerenciado pela NewAD? Stocco foi mencionado.

**Pergunta:** quais clientes têm campanhas no Google Ads? Quem autoriza o acesso à conta para integração?

---

## 5. Escopo de Dashboard por Cliente

**Banco Cora:** temos dados de delivery desde ago/2025, mas o IO formal cobre apenas a partir de mar/2026. O dashboard deve mostrar histórico completo (ago/25 em diante) ou apenas a partir do IO (mar/26)?

**TecPar:** a entrega real fica em "Amigo" (sub-cliente de TecPar). No dashboard, o TecPar quer ver os números do Amigo consolidados como "TecPar", ou quer Amigo e TecPar como contas separadas?

---

## 6. Siprocal — enriquecimento de dados

O feed da Siprocal não inclui spend (custo) nem device. Para ter esses KPIs também para Siprocal:

**Pergunta:** podemos solicitar à Siprocal que inclua `spend`, `device_type` e `country` no export? Quem é o contato comercial da Siprocal?

---

## 7. Novos Clientes

Há novos clientes a ser integrados nos próximos 30 dias? Se sim, precisamos preparar o pipeline antes da campanha ir ao ar.
