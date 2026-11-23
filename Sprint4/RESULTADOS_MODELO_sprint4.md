# Avaliação de modelos · Sompo Predict · Sprint 4

Gerado por `avaliacao_modelo.py` · 5-fold estratificado × 10 repetições (50 partições) · semente 42.

## Auditoria da base por UF

| UF   |   n |   pct_base |   LR_pct | vs_global   |   criticos |   crit_pct |
|:-----|----:|-----------:|---------:|:------------|-----------:|-----------:|
| MT   |  67 |       44.7 |    359.3 | acima       |          9 |       13.4 |
| GO   |  54 |       36   |    215.6 | abaixo      |          4 |        7.4 |
| MS   |  29 |       19.3 |    124.7 | abaixo      |          1 |        3.4 |

`n` é o número de registros, `LR_pct` a sinistralidade (indenizado ÷ prêmio) e `crit_pct` a taxa de caso crítico dentro da própria UF. Ordenado por sinistralidade, não por contagem.

## Comparação de modelos · alvo: caso crítico · todas as colunas

| modelo             | ROC-AUC       | F1-macro      | Bal.Acc       |
|:-------------------|:--------------|:--------------|:--------------|
| Dummy (baseline)   | 0.553 ± 0.106 | 0.560 ± 0.120 | 0.553 ± 0.106 |
| Decision Tree d=3  | 0.871 ± 0.122 | 0.822 ± 0.107 | 0.865 ± 0.119 |
| LogReg L2 balanced | 0.893 ± 0.140 | 0.852 ± 0.138 | 0.845 ± 0.145 |
| Random Forest d=3  | 0.964 ± 0.036 | 0.826 ± 0.117 | 0.856 ± 0.132 |
| MLP (32,16)        | 0.887 ± 0.142 | 0.826 ± 0.134 | 0.788 ± 0.137 |
| XGBoost d=3        | 0.985 ± 0.033 | 0.894 ± 0.122 | 0.898 ± 0.129 |

Todos os valores são média ± desvio-padrão entre as partições. O `Dummy (baseline)` é obrigatório na leitura: um modelo cuja média não supera a do baseline por mais de um desvio não demonstrou aprendizado.

## Comparação de modelos · alvo: caso crítico · apenas variáveis disponíveis na subscrição

| modelo             | ROC-AUC       | F1-macro      | Bal.Acc       |
|:-------------------|:--------------|:--------------|:--------------|
| Dummy (baseline)   | 0.553 ± 0.106 | 0.560 ± 0.120 | 0.553 ± 0.106 |
| Decision Tree d=3  | 0.557 ± 0.156 | 0.467 ± 0.083 | 0.564 ± 0.136 |
| LogReg L2 balanced | 0.595 ± 0.165 | 0.474 ± 0.069 | 0.633 ± 0.130 |
| Random Forest d=3  | 0.574 ± 0.125 | 0.518 ± 0.064 | 0.569 ± 0.097 |
| MLP (32,16)        | 0.608 ± 0.136 | 0.475 ± 0.011 | 0.497 ± 0.013 |
| XGBoost d=3        | 0.498 ± 0.132 | 0.467 ± 0.079 | 0.506 ± 0.137 |

Todos os valores são média ± desvio-padrão entre as partições. O `Dummy (baseline)` é obrigatório na leitura: um modelo cuja média não supera a do baseline por mais de um desvio não demonstrou aprendizado.

## Comparação de modelos · alvo: apólice deficitária (indenizado > prêmio)

| modelo             | ROC-AUC       | F1-macro      | Bal.Acc       |
|:-------------------|:--------------|:--------------|:--------------|
| Dummy (baseline)   | 0.542 ± 0.056 | 0.544 ± 0.062 | 0.542 ± 0.056 |
| Decision Tree d=3  | 0.609 ± 0.114 | 0.557 ± 0.084 | 0.614 ± 0.096 |
| LogReg L2 balanced | 0.588 ± 0.099 | 0.558 ± 0.085 | 0.627 ± 0.093 |
| Random Forest d=3  | 0.587 ± 0.102 | 0.535 ± 0.079 | 0.567 ± 0.083 |
| MLP (32,16)        | 0.538 ± 0.104 | 0.433 ± 0.042 | 0.465 ± 0.041 |
| XGBoost d=3        | 0.528 ± 0.089 | 0.544 ± 0.078 | 0.571 ± 0.081 |

Todos os valores são média ± desvio-padrão entre as partições. O `Dummy (baseline)` é obrigatório na leitura: um modelo cuja média não supera a do baseline por mais de um desvio não demonstrou aprendizado.

## Limitações declaradas

- **n = 150** com 14 casos críticos (9.3%). Cada partição de teste contém poucos positivos, o que produz desvios largos entre partições.
- **Ausência de série temporal por máquina.** A base é transversal, sem coluna de data por apólice, o que impede tanto modelagem recorrente quanto validação temporal.
- **Nenhuma variável de telemetria na base.** Inclinação, vibração e distância de obstáculo não existem nos registros da SUSEP, portanto a relação telemetria → sinistro não pode ser aprendida. É por isso que a Camada 2 do `core_fusao.py` é determinística e calibrada por limiar, não treinada.
- **Ampliar o volume de dados é a meta explícita da Sprint 4.**
