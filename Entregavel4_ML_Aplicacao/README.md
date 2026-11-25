# Sompo Predict: aplicação e apresentação final

4º entregável de Machine Learning & Modelling (FIAP, Squad T1). É um aplicativo Streamlit que recebe os dados de um equipamento agrícola e devolve um score de risco de 0 a 100, o nível (baixo, médio ou alto) e os fatores que mais pesaram.

Esta pasta foi montada à parte para não mexer no projeto das sprints anteriores. O motor de score é uma cópia sem alteração do `core_fusao.py` da Sprint 4 (mesmo hash do arquivo original), e a base é a `base_sompo_limpa.csv` de 150 apólices da SUSEP.

## Como rodar

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\streamlit run app.py
```

O aplicativo abre em `http://localhost:8501`. Para rodar os testes: `pip install -r requirements-dev.txt` e depois `pytest`.

## O que o aplicativo mostra

- Na entrada vão estado, modalidade, prêmio e coberturas da apólice, mais cinco leituras de campo (inclinação, obstáculo, vibração, umidade, temperatura). Há quatro cenários prontos da maquete.
- Na saída aparecem o score, o nível e a recomendação, com as frases dos fatores que mais pesam e um gráfico com os pontos de cada fator. Os pontos somam o score final.
- Há duas visões, baseadas nas histórias de usuário do projeto. A seguradora (subscrição) vê pontos por fator, a posição da apólice na carteira, o método de cálculo e o painel de ML. O produtor rural vê o nível em palavras simples e o que pesa no terreno agora.
- A aba Modelo de ML traz uma regressão logística treinada com as 150 apólices, ao lado da comparação com o baseline.

## Sobre o modelo

O score em produção é um motor de regras em duas camadas: o perfil da apólice (colunas reais da SUSEP) dá o ponto de partida e as condições em campo o multiplicam. Uma regra de segurança força o nível alto se a inclinação passar de 25 graus ou o obstáculo estiver a menos de 35 cm.

Os modelos de ML ficaram de fora do score porque não superaram o baseline. Na validação cruzada (5 folds, 10 repetições, alvo caso crítico, só variáveis conhecidas na contratação), o baseline de sorteio fez ROC-AUC 0,553 ± 0,106 e a regressão logística 0,596 ± 0,164. A diferença está dentro de um desvio-padrão. `python modelo_exp.py` refaz essa conta.

## Limites

- Os pesos de campo são julgamento de especialista. A base da SUSEP não tem telemetria, então não há par (leitura, sinistro) para treinar.
- No aplicativo, as leituras de campo vêm dos controles da tela. Não há sensor ao vivo.
- A base tem 150 apólices e 14 casos críticos, sem data por apólice.
- É um protótipo funcional simulado. O sistema alerta, e quem decide parar a máquina é o operador.

## Estrutura

```
app.py              interface Streamlit
risco.py            validação da entrada e decomposição do score em pontos por fator
modelo_exp.py       regressão logística experimental e validação cruzada
motor/              core_fusao.py e base_sompo_limpa.csv (cópias do Sprint 4)
tests/              24 testes (pytest)
apresentacao/       slides finais (.pptx) e capturas do aplicativo
```

## Publicar no Streamlit Community Cloud

1. Em share.streamlit.io, criar um app apontando para este repositório, branch `main`.
2. Arquivo principal: `Entregavel4_ML_Aplicacao/app.py`.
3. O arquivo `requirements.txt` desta pasta já tem as versões fixas. Não há segredos nem variáveis de ambiente.

O aplicativo não grava nenhum dado digitado.

## Fontes

Base: SUSEP, Bases Anonimizadas, Seguro Rural 2021 (R_RURAL_2021 e S_RURAL_2021), filtradas e amostradas na Sprint 4. Comparativo de modelos: `RESULTADOS_MODELO_sprint4.md`, em `motor/`.
