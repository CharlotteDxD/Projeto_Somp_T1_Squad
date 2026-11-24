# Correção "scoragem" — feedback Sompo Sprint 3 → fechamento Sprint 4

Card do Trello: "Feedbacks Sompo" · item 3 ("perfil"/variáveis do score).

## O que estava pendente

A correção da base (SUSEP real, 150 registros rastreáveis — ver
`rastreabilidade_secao_6_1.md`) e o recálculo dos pesos de `core_fusao.py`
já tinham sido feitos. Mas os dois scripts que avaliam o modelo estatístico
(o experimental, não o motor determinístico de produção) continuavam
escritos pra base antiga e não rodavam mais:

1. **`avaliar_modelo_rafael.py`** — gera `metricas_modelo.json`, lido pela
   tela "Desempenho dos Modelos" (`pagina_desempenho_modelos.py`) e pela
   tela de explicabilidade. Citava `IDADE_MAQUINA_ANOS`,
   `ACESSORIOS_SEGURADOS` e `RAMO_SUSEP` — nenhuma existe na base real.
   O `metricas_modelo.json` que estava no repositório era de 19/ago,
   **gerado com a base antiga não rastreável** — ou seja, a tela de
   desempenho estava mostrando número de dado fabricado enquanto o resto
   do app já rodava com dado real. Risco direto de contaminação mock/real.
2. **`avaliacao_modelo.py`** — harness de validação cruzada honesta
   (RepeatedStratifiedKFold + baseline Dummy). Mesmo problema de schema;
   quebrava com `ValueError` ao tentar rodar.

## O que foi corrigido

- `avaliar_modelo_rafael.py`: `NUMERICAS` trocado pras colunas reais
  (`QTD_COBERTURAS_CONTRATADAS`, `DURACAO_APOLICE_DIAS`,
  `PREMIO_LIQUIDO_BRL`); one-hot trocado de `RAMO_SUSEP` pra
  `MODALIDADE_SUSEP`; **`INTENSIDADE_SINISTRO` e `CAUSA_SINISTRO` passaram a
  ser removidas de X** — as duas são derivadas do mesmo evento de sinistro
  que define o alvo, ou seja, vazamento disfarçado de feature (mesmo motivo
  que já excluía `VALOR_INDENIZADO_BRL`).
- `avaliacao_modelo.py`: mesma correção de schema, com detecção genérica de
  coluna categórica (`select_dtypes(exclude="number")`) em vez de nome
  hardcoded — não quebra de novo se a base mudar outra vez. Textos do
  relatório exportado (contagem de registros/críticos) passaram a vir do
  dado real em vez de número digitado.
- Texto de veredito em `avaliar_modelo_rafael.py` corrigido: a versão antiga
  dizia "nenhuma versão identificou Crítico" mesmo quando só uma das duas
  otimizações zerava — com a base real, a otimizada por F1 acerta 1 caso
  (recall 0,25) e a de acurácia não. O texto agora distingue os dois casos
  em vez de generalizar errado.

## Resultado, rodado agora sobre a base real (150 registros, 14 críticos)

`metricas_modelo.json` regenerado (ver arquivo) — resumo:

| Modelo | Acurácia | F1 macro | Recall Crítico |
|---|---|---|---|
| Baseline ingênuo (sempre Baixo) | 0.733 | — | — |
| XGBoost, otimizado por acurácia | 0.733 | 0.212 | 0.00 |
| XGBoost, otimizado por F1 macro | 0.689 | 0.367 | 0.25 |

Leitura honesta, igual à da Sprint 3: com features disponíveis **no momento
da subscrição** (sem prêmio/indenização/intensidade — ver
`avaliacao_modelo.py`, alvo "subscrição"), **nenhum modelo supera o
baseline aleatório** (ROC-AUC ~0,50–0,61 contra baseline 0,553). O limite
segue sendo volume de dados, não algoritmo — e é exatamente por isso que o
score de produção (`core_fusao.py`, Camada 1) é determinístico e calibrado
por limiar justificado, não aprendido. Isso não mudou; agora está medido
sobre dado real e rastreável, não sobre a base fabricada.

`RESULTADOS_MODELO_sprint4.md` (gerado por `avaliacao_modelo.py`) tem a
tabela completa com ROC-AUC/F1/Bal.Acc e desvio-padrão por partição —
cola direto no capítulo de ML do documento mestre.

## Arquivos alterados nesta correção
- `avaliar_modelo_rafael.py`
- `avaliacao_modelo.py`
- `metricas_modelo.json` (regenerado)
- `RESULTADOS_MODELO_sprint4.md` (novo)
