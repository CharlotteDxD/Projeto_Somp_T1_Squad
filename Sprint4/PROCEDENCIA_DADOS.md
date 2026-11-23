# Procedência dos dados — apoio à revisão final

Gerado por `auditoria_procedencia.py`. Cada entrada é uma função que produz dados artificialmente, classificada pelo risco que representa numa apresentação.

| Classificação | Ocorrências | Significado |
|---|---|---|
| Crítico | 0 | Dado gerado exibido **sem identificação** — o espectador não tem como saber que é fictício |
| Sem marca | 6 | Gerador não declarado no código; invisível para a revisão |
| Declarado | 8 | Gerado, porém com procedência explícita — aceitável |

**Critério de aceite da revisão:** zero ocorrências em Crítico. Entradas em Declarado podem permanecer, desde que a justificativa esteja preenchida.

## Sem marca — não declarado no código · 6


### `motor_simulacao.py`

- **`_sortear_perfis()`** — linha 102
  - 5 chamada(s) de geração fora de tela
  - *Ação:* decorar com @sintetico, ou remover se não for usada
- **`_leituras_do_dia()`** — linha 122
  - 8 chamada(s) de geração fora de tela
  - *Ação:* decorar com @sintetico, ou remover se não for usada
- **`simular_frota()`** — linha 184
  - 1 chamada(s) de geração fora de tela
  - *Ação:* decorar com @sintetico, ou remover se não for usada

### `pagina_us05_gestor_frota.py`

- **`_check_api_health()`** — linha 176
  - 1 chamada(s) de geração; a tela identifica a procedência, mas a função não está declarada
  - *Ação:* decorar com @sintetico para aparecer no inventário

### `pagina_us08_analista_sinistros.py`

- **`_historico_sinistros_mock()`** — linha 42
  - 9 chamada(s) de geração; a tela identifica a procedência, mas a função não está declarada
  - *Ação:* decorar com @sintetico para aparecer no inventário
- **`_sinistros_pendentes_mock()`** — linha 66
  - 10 chamada(s) de geração; a tela identifica a procedência, mas a função não está declarada
  - *Ação:* decorar com @sintetico para aparecer no inventário

## Declarado — procedência explícita · 8


### `pagina_guilherme.py`

- **`_gerar_dataset_mock()`** — linha 23
  - 9 chamada(s) de geração, com declaração explícita
  - *Ação:* nenhuma — procedência declarada no código

### `pagina_ml_deep_learning.py`

- **`_treinar_decision_tree()`** — linha 112
  - 1 chamada(s) de geração, com declaração explícita
  - *Ação:* nenhuma — procedência declarada no código
- **`_treinar_isolation_forest()`** — linha 173
  - 3 chamada(s) de geração, com declaração explícita
  - *Ação:* nenhuma — procedência declarada no código
- **`_simular_lstm_metricas()`** — linha 211
  - 3 chamada(s) de geração, com declaração explícita
  - *Ação:* nenhuma — procedência declarada no código
- **`_shap_mock()`** — linha 282
  - 3 chamada(s) de geração, com declaração explícita
  - *Ação:* nenhuma — procedência declarada no código

### `pagina_us05_gestor_frota.py`

- **`_frota_mock_us05()`** — linha 107
  - 13 chamada(s) de geração, com declaração explícita
  - *Ação:* nenhuma — procedência declarada no código

### `pagina_us07_subscricao_xai.py`

- **`_propostas_mock()`** — linha 51
  - 8 chamada(s) de geração, com declaração explícita
  - *Ação:* nenhuma — procedência declarada no código
- **`_shap_proposta()`** — linha 95
  - 4 chamada(s) de geração, com declaração explícita
  - *Ação:* nenhuma — procedência declarada no código

## Como declarar procedência

```python
from core_procedencia import sintetico, real, selo

@sintetico("frota de demonstração",
           motivo="cadastro real ainda não disponível",
           substituir_por="data/frota_real.csv")
def _frota_demo():
    ...

# no topo da tela que exibe:
selo(_frota_demo._origem)
```

A função decorada entra no inventário automaticamente e a tela passa a exibir o aviso sem depender de o autor lembrar.
