"""Regressão logística experimental sobre a base SUSEP (150 apólices).

Existe para o app mostrar, ao lado do score de regras, o que um modelo de ML
treinado nos mesmos dados diria, e quão pouco ele sabe. Não alimenta o score.

Variáveis: só o que o subscritor conhece antes do sinistro (mesmo recorte do
avaliacao_modelo.py do Sprint 4, alvo "caso crítico"). Prêmio e valor
indenizado ficam de fora, e CAUSA/INTENSIDADE_SINISTRO também, por vazamento.

    python modelo_exp.py        # refaz a validação cruzada e imprime a tabela
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RepeatedStratifiedKFold, cross_validate
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import risco

SEMENTE = 42
COLUNAS = ["UF", "MODALIDADE_SUSEP", "QTD_COBERTURAS_CONTRATADAS",
           "DURACAO_APOLICE_DIAS"]

# Tabela do RESULTADOS_MODELO_sprint4.md (alvo caso crítico, variáveis da
# subscrição, 5-fold x 10 repetições). Copiada de lá, não recalculada aqui.
COMPARATIVO_GRUPO = pd.DataFrame(
    [
        ("Baseline (sorteio estratificado)", 0.553, 0.106),
        ("Árvore de decisão (prof. 3)", 0.557, 0.156),
        ("Regressão logística L2", 0.595, 0.165),
        ("Random Forest (prof. 3)", 0.574, 0.125),
        ("MLP (32, 16)", 0.608, 0.136),
        ("XGBoost (prof. 3)", 0.498, 0.132),
    ],
    columns=["Modelo", "ROC-AUC", "Desvio"],
)


def _alvo(df: pd.DataFrame) -> pd.Series:
    return (df["CLASSIFICACAO_RISCO"] == "Crítico").astype(int)


def _codificar(df: pd.DataFrame, colunas: list[str] | None = None) -> pd.DataFrame:
    x = pd.get_dummies(df[COLUNAS], columns=["UF", "MODALIDADE_SUSEP"], dtype=float)
    if colunas is not None:
        x = x.reindex(columns=colunas, fill_value=0.0)
    return x


@dataclass
class ModeloTreinado:
    pipeline: object
    colunas: list[str]
    prevalencia: float


@lru_cache(maxsize=1)
def treinar() -> ModeloTreinado:
    base = risco.carteira()
    x = _codificar(base)
    y = _alvo(base)
    pipe = make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=2000,
                           random_state=SEMENTE),
    )
    pipe.fit(x, y)
    return ModeloTreinado(pipe, list(x.columns), float(y.mean()))


def prever(uf: str, modalidade: str, coberturas: int, duracao: int = 365) -> dict:
    """Probabilidade do modelo e quanto cada variável empurrou o resultado."""
    m = treinar()
    linha = pd.DataFrame([{
        "UF": uf, "MODALIDADE_SUSEP": modalidade,
        "QTD_COBERTURAS_CONTRATADAS": coberturas,
        "DURACAO_APOLICE_DIAS": duracao,
    }])
    x = _codificar(linha, m.colunas)
    prob = float(m.pipeline.predict_proba(x)[0, 1])

    scaler, lr = m.pipeline.steps[0][1], m.pipeline.steps[1][1]
    z = scaler.transform(x)[0]
    contrib = pd.Series(z * lr.coef_[0], index=m.colunas)
    agrupado = {
        "Estado": contrib.filter(like="UF_").sum(),
        "Modalidade": contrib.filter(like="MODALIDADE_SUSEP_").sum(),
        "Coberturas": contrib["QTD_COBERTURAS_CONTRATADAS"],
        "Vigência": contrib["DURACAO_APOLICE_DIAS"],
    }
    return {"probabilidade": prob, "influencia": {k: float(v) for k, v in agrupado.items()},
            "prevalencia_amostra": m.prevalencia}


def validar() -> pd.DataFrame:
    """Refaz a validação cruzada de baseline e regressão logística."""
    base = risco.carteira()
    x, y = _codificar(base), _alvo(base)
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=SEMENTE)
    modelos = {
        "Baseline (sorteio estratificado)": DummyClassifier(
            strategy="stratified", random_state=SEMENTE),
        "Regressão logística L2": make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=2000,
                               random_state=SEMENTE)),
    }
    linhas = []
    for nome, mod in modelos.items():
        r = cross_validate(mod, x, y, cv=cv, scoring="roc_auc")["test_score"]
        linhas.append((nome, round(r.mean(), 3), round(r.std(), 3)))
    return pd.DataFrame(linhas, columns=["Modelo", "ROC-AUC", "Desvio"])


if __name__ == "__main__":
    print(validar().to_string(index=False))
