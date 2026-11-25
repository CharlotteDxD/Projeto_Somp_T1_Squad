"""Prova de conceito: rede neural (autoencoder) sobre telemetria do ESP32.

ATENÇÃO: os dados daqui são SIMULADOS. A base SUSEP não tem telemetria e o
carrinho ainda não gerou histórico suficiente. O script mostra o mecanismo
que a rede teria em produção, não mede desempenho real. Nada aqui entra no
score do Sompo Predict.

Ideia: treinar a rede só com janelas de operação normal. Ela aprende a
reconstruir esse comportamento. Quando entra uma janela diferente, o erro de
reconstrução sobe e vira o alerta. Os cinco canais seguem o contrato de
telemetria v1 (inclinação, vibração, obstáculo, temperatura, umidade) e os
limites críticos da regra são os do core_fusao.py (25 graus e 35 cm).

    python prototipo_telemetria.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

SEMENTE = 42
JANELA = 12          # amostras por janela
PASSOS = 70          # amostras por sequência
INICIO_EVENTO = 30
CANAIS = ["inclinacao_graus", "vibracao_rms", "dist_obstaculo_cm",
          "temperatura_c", "umidade_pct"]
LIM_INCLINACAO, LIM_OBSTACULO = 25.0, 35.0   # core_fusao.py
SAIDA = Path(__file__).parent / "saida"


def sequencia_normal(rng):
    t = np.arange(PASSOS)
    incl = rng.uniform(1, 9) + rng.uniform(-3, 3) * np.sin(t / rng.uniform(8, 20)) \
        + rng.normal(0, 0.6, PASSOS)
    vib = rng.uniform(0.5, 1.4) + rng.normal(0, 0.12, PASSOS)
    dist = rng.uniform(90, 190) + rng.normal(0, 4, PASSOS)
    temp = rng.uniform(24, 34) + np.cumsum(rng.normal(0, 0.05, PASSOS))
    umid = rng.uniform(45, 85) + np.cumsum(rng.normal(0, 0.15, PASSOS))
    return np.stack([incl, vib, dist, temp, umid], axis=1)


def sequencia_evento(rng, tipo):
    """Começa igual à normal e muda a partir de INICIO_EVENTO."""
    s = sequencia_normal(rng)
    k = np.clip((np.arange(PASSOS) - INICIO_EVENTO) / 30.0, 0, 1)  # rampa 0 -> 1
    if tipo == "rampa":
        s[:, 0] += k * rng.uniform(22, 30)
    elif tipo == "obstaculo":
        s[:, 2] = s[:, 2] * (1 - k) + k * rng.uniform(10, 25)
    elif tipo == "superaquecimento":
        # caso que a regra de segurança não cobre: vibração e temperatura sobem
        s[:, 1] += k * rng.uniform(1.6, 2.6)
        s[:, 3] += k * rng.uniform(14, 22)
    return s


def janelas(seq):
    return np.stack([seq[i - JANELA:i].ravel() for i in range(JANELA, len(seq) + 1)])


def erro_reconstrucao(rede, escala, X):
    Z = escala.transform(X)
    return ((rede.predict(Z) - Z) ** 2).mean(axis=1)


def primeira_vez(mascara):
    idx = np.flatnonzero(mascara)
    return int(idx[0]) if idx.size else None


def executar():
    rng = np.random.default_rng(SEMENTE)
    treino = [sequencia_normal(rng) for _ in range(150)]
    calib = [sequencia_normal(rng) for _ in range(50)]
    teste_normal = [sequencia_normal(rng) for _ in range(60)]
    tipos = ["rampa", "obstaculo", "superaquecimento"]
    teste_evento = {t: [sequencia_evento(rng, t) for _ in range(40)] for t in tipos}

    X_treino = np.vstack([janelas(s) for s in treino])
    escala = StandardScaler().fit(X_treino)
    rede = MLPRegressor(hidden_layer_sizes=(24, 6, 24), max_iter=600,
                        random_state=SEMENTE).fit(escala.transform(X_treino),
                                                  escala.transform(X_treino))

    # limite do alerta: percentil 99,5 do erro em sequências normais separadas
    err_calib = np.concatenate([erro_reconstrucao(rede, escala, janelas(s)) for s in calib])
    limite = float(np.percentile(err_calib, 99.5))

    # taxa de alarme falso: sequências normais inteiras que disparam em algum ponto
    falsos = np.mean([(erro_reconstrucao(rede, escala, janelas(s)) > limite).any()
                      for s in teste_normal])

    resumo = {"limite_erro": limite, "alarme_falso_sequencia_normal": float(falsos),
              "eventos": {}}
    detalhes = {}
    todos_y, todos_s = [], []
    for s in teste_normal:
        e = erro_reconstrucao(rede, escala, janelas(s))
        todos_y.append(0); todos_s.append(e.max())

    for tipo in tipos:
        detectou, antecip, regra_pegou = 0, [], 0
        for s in teste_evento[tipo]:
            e = erro_reconstrucao(rede, escala, janelas(s))
            todos_y.append(1); todos_s.append(e.max())
            t_rede = primeira_vez(e > limite)            # índice da janela
            t_rede = None if t_rede is None else t_rede + JANELA - 1  # amostra final
            regra = (s[:, 0] >= LIM_INCLINACAO) | (s[:, 2] <= LIM_OBSTACULO)
            t_regra = primeira_vez(regra)
            if t_rede is not None and t_rede >= INICIO_EVENTO:
                detectou += 1
            if t_regra is not None:
                regra_pegou += 1
                if t_rede is not None:
                    antecip.append(t_regra - t_rede)
        n = len(teste_evento[tipo])
        resumo["eventos"][tipo] = {
            "detectados_pela_rede": detectou / n,
            "disparados_pela_regra": regra_pegou / n,
            "antecedencia_media_amostras": float(np.mean(antecip)) if antecip else None,
        }
    resumo["roc_auc_sequencia"] = float(roc_auc_score(todos_y, todos_s))
    detalhes["exemplo"] = {
        t: teste_evento[t][0] for t in tipos}
    return rede, escala, limite, resumo, detalhes


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    rede, escala, limite, resumo, det = executar()
    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "prototipo_telemetria.json").write_text(
        json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    print("DADOS SIMULADOS, só ilustra o mecanismo.\n")
    print(f"limite de erro (p99,5 do normal): {limite:.3f}")
    print(f"alarme falso em sequência normal: {resumo['alarme_falso_sequencia_normal']*100:.0f}%")
    print(f"ROC-AUC (sequência normal x com evento): {resumo['roc_auc_sequencia']:.3f}\n")
    print(f"{'evento':18s} {'rede detecta':>13s} {'regra dispara':>14s} {'antecedência':>14s}")
    for tipo, v in resumo["eventos"].items():
        a = v["antecedencia_media_amostras"]
        print(f"{tipo:18s} {v['detectados_pela_rede']*100:12.0f}% "
              f"{v['disparados_pela_regra']*100:13.0f}% "
              f"{('%.1f amostras' % a) if a is not None else 'sem regra':>14s}")
