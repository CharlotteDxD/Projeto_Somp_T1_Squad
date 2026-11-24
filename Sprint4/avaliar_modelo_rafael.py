"""
avaliar_modelo_rafael.py
========================
Reproduz o pipeline de modelagem do notebook de Machine Learning e exporta
os resultados para a plataforma.

POR QUE ESTE SCRIPT EXISTE

    As telas de desempenho de modelo exibiam métricas digitadas à mão. Toda
    vez que o modelo mudava, os números da tela ficavam para trás sem que
    ninguém percebesse.

    Aqui o caminho é único: o script roda o pipeline, escreve
    `metricas_modelo.json`, e a tela lê esse arquivo. Nenhuma métrica é
    digitada em código de interface.

O QUE ELE REPRODUZ

    Pipeline idêntico ao do notebook:
      · remoção de VALOR_INDENIZADO_BRL, INTENSIDADE_SINISTRO e CAUSA_SINISTRO
        (vazamento — as três só existem/se fixam depois do evento)
      · encoding ordinal do alvo (CLASSIFICACAO_RISCO)
      · one-hot de UF e MODALIDADE_SUSEP com drop_first
      · split 70/30 estratificado, semente 42
      · StandardScaler ajustado apenas no treino
      · XGBoost com RandomizedSearchCV, otimizado por acurácia e por f1_macro

CORRECAO DE SPRINT 4 — leia isto antes de mexer no preparo de dados

    Ate a Sprint 3 este script rodava sobre a base antiga (149 registros, nao
    rastreavel ate o SUSEP — ver core_fusao.py e rastreabilidade_secao_6_1.md
    para o contexto completo da correcao) e tinha tres bugs de vazamento e
    schema que so nao quebravam porque as colunas certas por acaso existiam
    na base fabricada:

      1. NUMERICAS citava IDADE_MAQUINA_ANOS e ACESSORIOS_SEGURADOS, que nao
         existem em nenhum campo real do SUSEP — vieram de uma base que nao
         pode ser rastreada. Trocadas por QTD_COBERTURAS_CONTRATADAS e
         DURACAO_APOLICE_DIAS, que sao SUSEP puro.
      2. INTENSIDADE_SINISTRO entrava em X como feature ordinal — mas ela e
         derivada de VALOR_INDENIZADO_BRL/IMP_SEG, a MESMA fonte que define o
         alvo CLASSIFICACAO_RISCO. Igual a INTENSIDADE_SINISTRO, e vazamento
         disfarcado de feature, nao removido antes por coincidencia da base
         antiga. Agora entra na lista de remocao, ao lado de
         VALOR_INDENIZADO_BRL.
      3. one-hot citava RAMO_SUSEP, que tambem nao existe na base real —
         trocado por MODALIDADE_SUSEP (SUSEP puro, rotulo de COD_MOD).
         CAUSA_SINISTRO (coluna nova da reconstrucao, "Sem sinistro" ou o
         nome do evento) tambem sai de X pelo mesmo motivo: ela por si so
         quase entrega se houve sinistro.

    Ver avaliacao_modelo.py para a mesma correcao aplicada ao harness de
    validação cruzada honesta (RepeatedStratifiedKFold + baseline Dummy).

RESULTADO ESPERADO

    Ambas as versões falham em identificar as classes que importam. Isso não
    é um defeito deste script — é o resultado, e ele é reportado como tal.

USO
    python3 avaliar_modelo_rafael.py
    python3 avaliar_modelo_rafael.py --salvar-modelo    # exporta o .pkl
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from sklearn.preprocessing import StandardScaler

SEMENTE = 42
CAMINHO_BASE = Path("base_sompo_limpa.csv")
SAIDA_JSON = Path("metricas_modelo.json")
CLASSES = ["Baixo", "Médio", "Alto", "Crítico"]
# Sprint 4: IDADE_MAQUINA_ANOS e ACESSORIOS_SEGURADOS nao existem na base
# real (ver correcao no topo do arquivo) — QTD_COBERTURAS_CONTRATADAS e
# DURACAO_APOLICE_DIAS sao as numericas SUSEP puras disponiveis no lugar.
NUMERICAS = ["QTD_COBERTURAS_CONTRATADAS", "DURACAO_APOLICE_DIAS",
             "PREMIO_LIQUIDO_BRL"]

GRADE = {
    "n_estimators":     [50, 100, 200],
    "max_depth":        [3, 4, 5, 6],
    "learning_rate":    [0.01, 0.05, 0.1, 0.2],
    "subsample":        [0.7, 0.85, 1.0],
    "min_child_weight": [1, 3, 5],
}


def preparar(df: pd.DataFrame):
    """
    Pré-processamento do notebook.

    VALOR_INDENIZADO_BRL, INTENSIDADE_SINISTRO e CAUSA_SINISTRO saem das
    features: as três só existem, ou só se fixam, depois do evento de
    sinistro — mantê-las para prever um rótulo de risco a priori seria
    informação do futuro vazando para o passado (mesmo motivo que já
    excluía VALOR_INDENIZADO_BRL; a correção de Sprint 4 estende a regra
    às outras duas, ver docstring do módulo).
    """
    dm = df.drop(
        columns=["VALOR_INDENIZADO_BRL", "INTENSIDADE_SINISTRO",
                 "CAUSA_SINISTRO"],
        errors="ignore").copy()
    dm["CLASSIFICACAO_RISCO"] = dm["CLASSIFICACAO_RISCO"].map(
        {"Baixo": 0, "Médio": 1, "Alto": 2, "Crítico": 3})
    dm = pd.get_dummies(dm, columns=["UF", "MODALIDADE_SUSEP"],
                        drop_first=True)

    y = dm["CLASSIFICACAO_RISCO"]
    X = dm.drop(columns=["CLASSIFICACAO_RISCO"])
    return X, y


def avaliar(X, y, salvar_modelo: bool = False) -> dict:
    from xgboost import XGBClassifier

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.30, random_state=SEMENTE, stratify=y)

    # Scaler ajustado só no treino — o teste apenas recebe a transformação
    scaler = StandardScaler()
    X_tr, X_te = X_tr.copy(), X_te.copy()
    X_tr[NUMERICAS] = scaler.fit_transform(X_tr[NUMERICAS])
    X_te[NUMERICAS] = scaler.transform(X_te[NUMERICAS])

    baseline = float(y_te.value_counts(normalize=True).max())
    resultados = {}
    melhor_f1 = None

    for metrica in ("accuracy", "f1_macro"):
        busca = RandomizedSearchCV(
            XGBClassifier(eval_metric="mlogloss", random_state=SEMENTE),
            GRADE, n_iter=25, cv=5, scoring=metrica,
            random_state=SEMENTE, n_jobs=-1,
        ).fit(X_tr, y_tr)

        modelo = busca.best_estimator_
        pred = modelo.predict(X_te)
        previstas = Counter(int(p) for p in pred)

        # Quantas classes o modelo chega a prever? Prever uma só significa
        # que ele convergiu para o chute constante.
        classes_previstas = sorted(previstas.keys())
        rel = classification_report(
            y_te, pred, target_names=CLASSES, zero_division=0,
            output_dict=True, labels=[0, 1, 2, 3])

        resultados[metrica] = {
            "acuracia": round(float(accuracy_score(y_te, pred)), 3),
            "f1_macro": round(float(f1_score(y_te, pred, average="macro",
                                             zero_division=0)), 3),
            "melhores_parametros": busca.best_params_,
            "classes_previstas": classes_previstas,
            "distribuicao_previsoes": {CLASSES[k]: v
                                       for k, v in sorted(previstas.items())},
            "recall_por_classe": {c: round(rel[c]["recall"], 3) for c in CLASSES},
            "matriz_confusao": confusion_matrix(
                y_te, pred, labels=[0, 1, 2, 3]).tolist(),
        }
        if metrica == "f1_macro":
            melhor_f1 = modelo

    # Importância de fatores do modelo f1_macro (base do SHAP)
    importancias = sorted(
        zip(X.columns, melhor_f1.feature_importances_),
        key=lambda kv: kv[1], reverse=True)

    if salvar_modelo:
        Path("data").mkdir(exist_ok=True)
        try:
            import joblib
            joblib.dump(melhor_f1, "data/modelo_xgboost.pkl")
            print("  [ok] modelo salvo em data/modelo_xgboost.pkl")
        except Exception as e:
            print(f"  [aviso] não foi possível salvar o modelo: {e}")

    return {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "base": {"registros": int(len(X)), "features": int(X.shape[1]),
                 "treino": int(len(X_tr)), "teste": int(len(X_te))},
        "baseline_ingenuo": round(baseline, 3),
        "xgboost": resultados,
        "referencia_sprint2": {"decision_tree": 0.267, "mlp": 0.422},
        "importancias": [{"feature": f, "peso": round(float(p), 4)}
                         for f, p in importancias[:10]],
    }


def imprimir(r: dict) -> None:
    print("=" * 70)
    print("  DESEMPENHO DOS MODELOS — execução real")
    print("=" * 70)
    b = r["base"]
    print(f"  {b['registros']} registros · {b['features']} features · "
          f"{b['treino']} treino / {b['teste']} teste\n")

    base = r["baseline_ingenuo"]
    print(f"  {'modelo':<34} {'acurácia':>9} {'f1_macro':>9}  classes previstas")
    print(f"  {'-'*34} {'-'*9} {'-'*9}  {'-'*17}")
    print(f"  {'Baseline ingênuo (sempre Baixo)':<34} {base:>9.3f} "
          f"{'—':>9}  1 de 4")
    ref = r["referencia_sprint2"]
    print(f"  {'Decision Tree':<34} {ref['decision_tree']:>9.3f} {'—':>9}")
    print(f"  {'Rede neural (MLP)':<34} {ref['mlp']:>9.3f} {'—':>9}")
    for met, d in r["xgboost"].items():
        nome = f"XGBoost (otimizado por {met})"
        print(f"  {nome:<34} {d['acuracia']:>9.3f} {d['f1_macro']:>9.3f}  "
              f"{len(d['classes_previstas'])} de 4")

    print("\n  Recall por classe — a leitura que importa:\n")
    print(f"  {'classe':<12} " + "  ".join(
        f"{m:>16}" for m in r["xgboost"]))
    for c in CLASSES:
        linha = f"  {c:<12} "
        for met in r["xgboost"]:
            linha += f"{r['xgboost'][met]['recall_por_classe'][c]:>16.2f}  "
        print(linha)

    acc = r["xgboost"]["accuracy"]
    if len(acc["classes_previstas"]) == 1:
        print(f"\n  >> O modelo otimizado por acurácia prevê uma única classe")
        print(f"     para todas as {b['teste']} apólices de teste. Iguala o")
        print(f"     baseline ({base:.3f}) sem aprender padrão algum — o número")
        print(f"     parece bom e não significa nada.")

    # Corrigido na Sprint 4: a versão antiga disparava esta mensagem se
    # QUALQUER uma das duas otimizações zerasse Crítico, mesmo que a outra
    # tivesse acertado algum caso — texto que, com a base real, passou a
    # afirmar "nenhuma versão" quando uma das duas efetivamente acerta.
    todas = list(r["xgboost"].items())
    criticos_zerados = [met for met, d in todas
                        if d["recall_por_classe"]["Crítico"] == 0.0]
    if len(criticos_zerados) == len(todas):
        print(f"\n  >> Nenhuma versão identificou um caso Crítico. É a classe")
        print(f"     que decide subscrição — e é a que o modelo não enxerga.")
        print(f"     Conclusão: o limite está na base, não no algoritmo.")
    elif criticos_zerados:
        acertou = [met for met, d in todas
                  if d["recall_por_classe"]["Crítico"] > 0.0]
        print(f"\n  >> A versão otimizada por {'/'.join(acertou)} identifica "
              f"algum caso Crítico;")
        print(f"     a otimizada por {'/'.join(criticos_zerados)} não. Recall "
              f"baixo em amostra de {b['teste']}")
        print(f"     apólices de teste (poucos positivos por partição) — não "
              f"trate como comparação")
        print(f"     estável entre as duas otimizações.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(CAMINHO_BASE))
    ap.add_argument("--salvar-modelo", action="store_true")
    ap.add_argument("--saida", default=str(SAIDA_JSON))
    args = ap.parse_args()

    caminho = Path(args.base)
    if not caminho.exists():
        print(f"[erro] base não encontrada: {caminho}")
        return 1

    df = pd.read_csv(caminho)
    X, y = preparar(df)
    r = avaliar(X, y, salvar_modelo=args.salvar_modelo)
    imprimir(r)

    Path(args.saida).write_text(
        json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Métricas exportadas para {args.saida}")
    print("  A tela de desempenho lê este arquivo — nenhum número é digitado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
