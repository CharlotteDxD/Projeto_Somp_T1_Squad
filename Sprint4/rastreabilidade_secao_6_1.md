# Seção 6.1 — Rastreabilidade da base de dados (versão corrigida)

## Contexto da correção

A base usada até a Sprint 3 (`base_sompo_limpa.csv`, 150 registros) não pôde ser rastreada até o arquivo original do SUSEP: o filtro aplicado não foi documentado no momento do download e, ao reconstruir o processo, as colunas dessa base (`RAMO_SUSEP`, `CLASSIFICACAO_RISCO`, `INTENSIDADE_SINISTRO`, `IDADE_MAQUINA_ANOS`, `ACESSORIOS_SEGURADOS`) não correspondem a nenhum campo existente nos arquivos reais do SUSEP. Em vez de tentar reconstruir uma explicação para uma base que não fecha estruturalmente com a fonte, o grupo refez o pipeline do zero, direto da fonte oficial, com cada etapa documentada abaixo.

## 1) Qual arquivo exato foi baixado (nome + ano/período)

- **Fonte oficial:** https://www.gov.br/susep/pt-br/central-de-conteudos/dados-estatisticos/bases-anonimizadas/bases_rural
- **Arquivos baixados:**
  - `R_RURAL_2021.zip` → `R_RURAL_2021.csv` (base de prêmios/apólices, ano-base 2021)
  - `S_RURAL_2021.zip` → `S_RURAL_2021.csv` (base de sinistros, ano-base 2021)
- **Manual de referência dos campos:** `Dados_Rural_Animais.pdf` (mesma pasta), usado para confirmar o significado de cada coluna e das tabelas de domínio (COD_MOD, ID_BEM, COBERTURA, EV_GER).

## 2) Quantas linhas tinha o arquivo bruto, antes de qualquer filtro

| Arquivo | Linhas brutas (sem header) |
|---|---|
| `R_RURAL_2021.csv` | 12.773.353 |
| `S_RURAL_2021.csv` | 158.640 |

## 3) Qual filtro foi aplicado até chegar nos registros finais

Pipeline completo, em ordem:

1. **Filtro por tipo de bem segurado:** `ID_BEM = 60` — "Máquinas e implementos agrícolas" (Tabela V do manual SUSEP). Esse é o recorte que corresponde ao escopo do desafio Sompo ("risco de dano ou perda de equipamentos agrícolas"). Resultado: 2.393.851 itens (apólice/endosso/item) na base de prêmio, 23.366 na base de sinistro.
2. **Agregação por item segurado:** cada máquina (`COD_APO`+`COD_ENDOSSO`+`COD_ITEM`) tem, na base bruta, uma linha por cobertura contratada — somamos `PREMIO` por item e contamos coberturas (`QTD_COBERTURAS_CONTRATADAS`).
3. **Join prêmio × sinistro:** join à esquerda da base de prêmio agregada com a base de sinistro agregada (mesma chave), somando `INDENIZ` por item; itens sem sinistro ficam com `VALOR_INDENIZADO_BRL = 0`.
4. **Filtro de prêmio válido:** `PREMIO_TOTAL > 0` (remove itens sem cobrança válida). Resultado: 2.290.824 itens — esse é o universo elegível completo.
5. **Filtro geográfico:** `UF IN ('GO','MS','MT')` — recorte regional do projeto (Centro-Oeste). Resultado: 254.995 itens, dos quais 3.082 têm sinistro real registrado em 2021.
6. **Amostragem final, reprodutível (seed=42, reservoir sampling):**
   - 50 registros = amostra aleatória de **todos** os itens com sinistro real (universo de 3.082)
   - 100 registros = amostra aleatória dos itens **sem** sinistro (universo de 251.913)
   - Total: **150 registros**, proporção 33% com sinistro / 67% sem sinistro — desbalanceamento deliberado e documentado para permitir análise da variável de risco (no universo completo, a taxa real de sinistro é de ~1,2%, então 150 registros aleatórios "puros" teriam ~2 sinistros — insuficiente para qualquer análise).

## Colunas finais — o que é SUSEP puro vs. calibrado/derivado

| Coluna | Origem |
|---|---|
| `UF` | **SUSEP pura** — campo `UF` do arquivo R_RURAL |
| `MODALIDADE_SUSEP` | **SUSEP pura**, apenas com rótulo em texto do código `COD_MOD` (10/50/60/70) |
| `CAUSA_SINISTRO` | **SUSEP pura**, rótulo em texto do código `EV_GER` (Tabela X do manual) — para itens sem sinistro, "Sem sinistro" |
| `QTD_COBERTURAS_CONTRATADAS` | **SUSEP pura** (contagem de linhas de `COBERTURA` por item) |
| `DURACAO_APOLICE_DIAS` | **SUSEP pura**, calculado a partir de `FIM_VIG - INICIO_VIG` |
| `PREMIO_LIQUIDO_BRL` | **SUSEP pura**, soma do campo `PREMIO` por item |
| `VALOR_INDENIZADO_BRL` | **SUSEP pura**, soma do campo `INDENIZ` por item (0 quando não há sinistro) |
| `CLASSIFICACAO_RISCO` | **Calibrada/derivada** — bin de `VALOR_INDENIZADO_BRL / PREMIO_LIQUIDO_BRL` (loss ratio). Sem sinistro = "Baixo"; com sinistro, tercis da distribuição positiva definem Médio (≤2,28), Alto (≤5,22) e Crítico (>5,22) |
| `INTENSIDADE_SINISTRO` | **Calibrada/derivada** — bin de `VALOR_INDENIZADO_BRL / IMP_SEG` (severidade sobre valor segurado). Sem sinistro = "Sem sinistro"; com sinistro, tercis definem Leve (≤0,024), Moderado (≤0,062) e Grave (>0,062) |

Não existe no SUSEP nenhum campo de "idade da máquina" ou "acessórios segurados" — por isso essas duas colunas da base antiga foram **descartadas**, não recalculadas, já que não há como derivá-las de forma rastreável a partir da fonte real.

## Nota

Os limites de MT/GO/MS não são os de maior sinistralidade absoluta do Brasil (PR e RS têm mais sinistros em volume, por terem carteiras maiores), mas MT tem a 2ª maior taxa relativa de sinistro entre os grandes estados agrícolas (1,33%, contra 1,18% em GO e 1,06% em MS) — dado real, calculado sobre o universo completo de 2.290.824 itens, não sobre a amostra de 150.
