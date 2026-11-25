"""Gráficos dos slides do vídeo (lê os resultados dos dois scripts)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import prototipo_telemetria as pt

AQUI = Path(__file__).parent
SAIDA = AQUI / "saida"
FUNDO, TEXTO, APAGADO = "#020617", "#F8FAFC", "#94A3B8"
AZUL, VERMELHO, AMBAR, VERDE = "#3B82F6", "#F87171", "#FBBF24", "#34D399"

plt.rcParams.update({
    "figure.facecolor": FUNDO, "axes.facecolor": FUNDO, "savefig.facecolor": FUNDO,
    "text.color": TEXTO, "axes.labelcolor": TEXTO, "xtick.color": APAGADO,
    "ytick.color": APAGADO, "axes.edgecolor": "#334155", "font.size": 17,
    "font.family": ["Segoe UI", "DejaVu Sans"], "axes.spines.top": False,
    "axes.spines.right": False,
})


def grafico_auc():
    r = json.loads((SAIDA / "mlp_base_real.json").read_text(encoding="utf-8"))
    nomes = list(r)
    medias = [r[n]["roc_auc"] for n in nomes]
    dps = [r[n]["roc_auc_dp"] for n in nomes]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    y = np.arange(len(nomes))[::-1]
    ax.barh(y, medias, xerr=dps, color=["#64748B", AZUL], height=0.5,
            error_kw={"ecolor": TEXTO, "capsize": 6, "lw": 2})
    for yi, m, d in zip(y, medias, dps):
        ax.text(0.31, yi, f"{m:.3f}".replace(".", ","), va="center", fontsize=20, fontweight="bold")
    ax.axvline(medias[0], color=AMBAR, ls="--", lw=1.5)
    ax.set_yticks(y, nomes)
    ax.set_xlim(0.3, 0.85)
    ax.set_xlabel("ROC-AUC, média e desvio em 50 partições")
    fig.tight_layout()
    fig.savefig(SAIDA / "grafico_auc.png", dpi=200)
    plt.close(fig)


def grafico_telemetria():
    rede, escala, limite, _, det = pt.executar()
    casos = [("rampa", 0, "Rampa: inclinação (°)", pt.LIM_INCLINACAO, "limite 25°"),
             ("superaquecimento", 1, "Superaquec.: vibração (RMS)", None, None)]
    fig, eixos = plt.subplots(2, 2, figsize=(10.2, 6.6), sharex="col")
    for col, (tipo, canal, titulo, lim, rotulo) in enumerate(casos):
        s = det["exemplo"][tipo]
        t = np.arange(len(s))
        e = pt.erro_reconstrucao(rede, escala, pt.janelas(s))
        te = np.arange(pt.JANELA - 1, len(s))
        a, b = eixos[0, col], eixos[1, col]
        a.plot(t, s[:, canal], color=AZUL, lw=2.4)
        a.axvline(pt.INICIO_EVENTO, color=APAGADO, ls=":", lw=1.2)
        if lim:
            a.axhline(lim, color=VERMELHO, ls="--", lw=1.5)
            a.text(1, lim + 0.8, rotulo, color=VERMELHO, fontsize=14)
        a.set_title(titulo, loc="left", fontsize=16, pad=8)
        b.plot(te, e, color=VERDE, lw=2.4)
        b.axhline(limite, color=AMBAR, ls="--", lw=1.5)
        b.axvline(pt.INICIO_EVENTO, color=APAGADO, ls=":", lw=1.2)
        b.set_xlabel("amostra")
        pos = np.flatnonzero(e > limite)
        if pos.size:
            b.scatter(te[pos[0]], e[pos[0]], color=AMBAR, zorder=5, s=70)
            b.annotate("rede alerta", (te[pos[0]], e[pos[0]]), xytext=(-60, 38),
                       textcoords="offset points", color=AMBAR, fontsize=15,
                       arrowprops={"arrowstyle": "-", "color": AMBAR})
        if lim:
            r = np.flatnonzero(s[:, canal] >= lim)
            if r.size:
                a.scatter(r[0], s[r[0], canal], color=VERMELHO, zorder=5, s=70)
                a.annotate("regra dispara", (r[0], s[r[0], canal]), xytext=(16, -38),
                           textcoords="offset points", color=VERMELHO, fontsize=15)
    eixos[0, 0].text(pt.INICIO_EVENTO + 0.8, eixos[0, 0].get_ylim()[0] + 1,
                     "início do evento", color=APAGADO, fontsize=13)
    eixos[1, 0].set_ylabel("erro de reconstrução")
    fig.tight_layout()
    fig.savefig(SAIDA / "grafico_telemetria.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    grafico_auc()
    grafico_telemetria()
    print("ok")
