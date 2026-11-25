"""MLP (32, 16) sobre a base SUSEP real, refeito para o vídeo do 4º entregável de Redes Neurais.

Mesmo recorte do avaliacao_modelo.py da Sprint 4: alvo "caso crítico", só
variáveis que o subscritor conhece na contratação (sem prêmio, indenização,
causa nem intensidade, que vazam o desfecho). Validação cruzada estratificada
de 5 folds com 10 repetições, semente 42.

    python mlp_base_real.py
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import RepeatedStratifiedKFold, cross_validate
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

AQUI = Path(__file__).parent
SEMENTE = 42
SAIDA = AQUI / "saida"


def carregar():
    df = pd.read_csv(AQUI / "dados" / "base_sompo_limpa.csv")
    y = (df["CLASSIFICACAO_RISCO"] == "Crítico").astype(int)
    fora = ["CLASSIFICACAO_RISCO", "INTENSIDADE_SINISTRO", "CAUSA_SINISTRO",
            "PREMIO_LIQUIDO_BRL", "VALOR_INDENIZADO_BRL"]
    restante = df.drop(columns=fora)
    cats = list(restante.select_dtypes(exclude="number").columns)
    return pd.get_dummies(restante, columns=cats, dtype=float), y


def rodar():
    X, y = carregar()
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=SEMENTE)
    modelos = {
        "Baseline (sorteio estratificado)": DummyClassifier(
            strategy="stratified", random_state=SEMENTE),
        "MLP (32, 16)": make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=1500,
                          random_state=SEMENTE)),
    }
    linhas = {}
    for nome, m in modelos.items():
        r = cross_validate(m, X, y, cv=cv, scoring=["roc_auc", "balanced_accuracy"])
        linhas[nome] = {
            "roc_auc": float(r["test_roc_auc"].mean()),
            "roc_auc_dp": float(r["test_roc_auc"].std()),
            "bal_acc": float(r["test_balanced_accuracy"].mean()),
            "bal_acc_dp": float(r["test_balanced_accuracy"].std()),
        }
    return X, y, linhas


def contar_parametros(X):
    m = MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=1, random_state=SEMENTE)
    m.fit(StandardScaler().fit_transform(X), np.arange(len(X)) % 2)
    return sum(w.size for w in m.coefs_) + sum(b.size for b in m.intercepts_)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    X, y, linhas = rodar()
    print(f"base: {X.shape[0]} apólices, {int(y.sum())} críticas ({y.mean()*100:.1f}%), "
          f"{X.shape[1]} entradas após o one-hot")
    print(f"parâmetros do MLP nesta base: {contar_parametros(X)}\n")
    print(f"{'modelo':34s} {'ROC-AUC':>16s} {'acc. balanceada':>18s}")
    for nome, v in linhas.items():
        print(f"{nome:34s} {v['roc_auc']:.3f} ± {v['roc_auc_dp']:.3f}"
              f"   {v['bal_acc']:.3f} ± {v['bal_acc_dp']:.3f}")
    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "mlp_base_real.json").write_text(
        json.dumps(linhas, indent=2, ensure_ascii=False), encoding="utf-8")
