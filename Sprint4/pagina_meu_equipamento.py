"""
pagina_meu_equipamento.py
=========================
Histórico e tendência — portal do segurado.

DIFERENÇA PARA A TELA DA SEGURADORA

    A tela de frota mostra todos os equipamentos monitorados, para
    priorizar carteira. Esta mostra UM equipamento — o do próprio segurado
    — e nada além dele.

    Não é a mesma tela com filtro aplicado: reaproveitar a tela da frota
    filtrando por equipamento manteria em memória, e no código, o acesso ao
    conjunto inteiro. Aqui a análise recebe apenas a série daquele
    equipamento; o restante da frota não é carregado.

    A linguagem também muda. O subscritor lê "R²=0,86 · +0,71 pontos por
    semana". O produtor lê "o risco da sua máquina vem subindo há seis
    semanas". É a mesma análise, traduzida para quem opera.

AMBIENTE DE DEMONSTRAÇÃO

    Enquanto o equipamento não estiver instrumentado, a série é simulada.
    O motor que a analisa é o mesmo que roda em campo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import core_fusao as cf
import core_relatorio as cr
from motor_simulacao import simular_frota

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

CAMINHO_BASE = Path("base_sompo_limpa.csv")

# Equipamento do segurado nesta demonstração. Em operação real vem do
# cadastro vinculado ao login, não de constante.
EQUIP_DEMO = "COL-008"

_HEX = {"verde": "#3FCF8E", "amarelo": "#F5B23D", "vermelho": "#F2555A"}
_TITULO = {"verde": "Sua máquina está bem",
           "amarelo": "Vale ficar de olho",
           "vermelho": "Precisa de atenção"}


@st.cache_data(ttl=3600, show_spinner=False)
def _score_perfil(equip_id: str) -> float:
    """Score de perfil da apólice deste equipamento."""
    if not CAMINHO_BASE.exists():
        return 55.0
    base = pd.read_csv(CAMINHO_BASE)
    cf.calibrar_faixas(base)
    sc = cf.calcular_score_base(base).sort_values("score_base").reset_index(drop=True)
    lo, hi = int(len(sc) * 0.08), int(len(sc) * 0.88)
    idx = np.linspace(lo, hi, 12).astype(int)
    try:
        pos = int(equip_id.split("-")[1])
    except (IndexError, ValueError):
        pos = 0
    return float(sc.loc[idx[min(pos, len(idx) - 1)], "score_base"])


@st.cache_data(ttl=1800, show_spinner="Carregando seu histórico...")
def _serie_do_equipamento(equip_id: str, dias: int):
    """
    Série apenas deste equipamento. A frota completa é gerada pelo
    simulador, mas o recorte acontece aqui — daqui para frente, nenhuma
    função recebe dado de outro equipamento.
    """
    df, _ = simular_frota(n_equipamentos=12, dias=dias)
    df = df[df["equip_id"] == equip_id].copy()
    dfp = cr.pontuar_serie(df, score_base_por_equip={
        equip_id: _score_perfil(equip_id)})
    return dfp


def _semanas_de_alta(t: cr.Tendencia | None, dias: int) -> str:
    if t is None or not t.confiavel:
        return ""
    return f"há cerca de {max(1, int(dias / 7))} semanas"


def render() -> None:
    from core_app import (check_permissao_silenciosa, gerar_trilha_auditoria,
                          _contrato_box, _header)

    if not (check_permissao_silenciosa("view_proprio_equipamento")
            or check_permissao_silenciosa("view_dashboard")):
        st.error("Acesso negado a esta tela.")
        return

    _contrato_box("meu_equipamento", [])
    _header("Histórico do equipamento",
            "Como o risco da sua máquina vem se comportando")
    gerar_trilha_auditoria("ACESSO_MEU_EQUIPAMENTO", f"equip={EQUIP_DEMO}")

    # ---------------- Procedência ----------------
    st.markdown("""
    <div style="background:rgba(245,178,61,0.07);
          border:1px solid rgba(245,178,61,0.35);
          border-left:3px solid var(--amarelo);border-radius:10px;
          padding:11px 15px;margin-bottom:1.3rem;">
        <div style="display:flex;align-items:center;gap:9px;">
            <span style="width:7px;height:7px;border-radius:50%;
                  background:var(--amarelo);box-shadow:0 0 8px var(--amarelo);
                  flex:none;"></span>
            <span style="color:var(--amarelo);font-weight:600;
                  font-size:0.83rem;">Dados de demonstração</span>
        </div>
        <div style="font-size:0.78rem;color:var(--text-2);margin-top:5px;
              line-height:1.55;">
            O sensor ainda não está instalado nesta máquina. As leituras
            abaixo são simuladas para mostrar como o acompanhamento
            funciona. A análise é a de verdade.
        </div>
    </div>
    """, unsafe_allow_html=True)

    dias = st.selectbox("Período", [30, 60, 90], index=2,
                        format_func=lambda d: f"últimos {d} dias",
                        key="meq_dias")

    dfp = _serie_do_equipamento(EQUIP_DEMO, dias)
    if dfp.empty:
        st.info("Ainda não há histórico registrado para esta máquina.",
                icon="📊")
        return

    tendencias = cr.analisar_tendencia(dfp)
    t = tendencias[0] if tendencias else None

    diario = dfp.groupby("dia")["score"].mean()
    atual = float(diario.tail(7).mean())
    inicial = float(diario.head(7).mean())
    faixa_atual = cf.classificar(atual)[0]
    cor = _HEX[faixa_atual]

    # ---------------- Situação em uma frase ----------------
    if t and t.confiavel and t.inclinacao_pontos_por_semana > 0.3:
        resumo = (f"O risco da sua máquina vem <strong>subindo</strong> "
                  f"{_semanas_de_alta(t, dias)}.")
        cor_resumo = "var(--amarelo)"
    elif t and t.confiavel and t.inclinacao_pontos_por_semana < -0.3:
        resumo = "O risco da sua máquina vem <strong>melhorando</strong>."
        cor_resumo = "var(--verde)"
    else:
        resumo = "O risco da sua máquina está <strong>estável</strong>."
        cor_resumo = "var(--verde)"

    st.markdown(f"""
    <div class="g-card lit" style="padding:1.4rem 1.6rem;margin-bottom:1.3rem;">
        <div style="font-family:'Manrope',sans-serif;font-size:1.6rem;
              font-weight:800;color:{cor};letter-spacing:-0.02em;">
            {_TITULO[faixa_atual]}</div>
        <div style="font-size:1rem;color:var(--text);margin-top:8px;
              line-height:1.6;">{resumo}</div>
    </div>
    """, unsafe_allow_html=True)

    # ---------------- Números, em linguagem simples ----------------
    c1, c2, c3 = st.columns(3)
    delta = atual - inicial
    for col, val, rot, cr_ in [
        (c1, f"{atual:.0f}", "Nível de risco hoje", cor),
        (c2, f"{delta:+.0f}", "Mudança no período",
         "var(--amarelo)" if delta > 3 else "var(--verde)"),
        (c3, f"{int(dfp['override'].sum())}", "Alertas no período",
         "var(--vermelho)" if dfp["override"].sum() else "var(--verde)"),
    ]:
        col.markdown(f"""
        <div class="g-card" style="padding:1rem 1.15rem;">
            <div class="g-num" style="color:{cr_};">{val}</div>
            <div class="g-label">{rot}</div>
        </div>
        """, unsafe_allow_html=True)

    # ---------------- Gráfico ----------------
    st.markdown("<div style='height:1.3rem;'></div>", unsafe_allow_html=True)
    st.markdown("##### Como variou no período")

    if PLOTLY_OK:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=diario.index, y=diario.values, mode="lines",
            name="nível de risco",
            line=dict(color="#5B7FFF", width=1.8),
            hovertemplate="dia %{x}: %{y:.0f}<extra></extra>"))
        if t and t.confiavel:
            coef = np.polyfit(diario.index.to_numpy(float), diario.to_numpy(), 1)
            fig.add_trace(go.Scatter(
                x=diario.index,
                y=np.polyval(coef, diario.index.to_numpy(float)),
                mode="lines", name="tendência",
                line=dict(color="#F5B23D", width=2.2, dash="dash")))
        fig.add_hline(y=cf.FAIXAS[1][0], line_dash="dot",
                      line_color="#F5B23D", opacity=0.4,
                      annotation_text="atenção", annotation_position="right",
                      annotation_font=dict(color="#F5B23D", size=10))
        fig.add_hline(y=cf.FAIXAS[2][0], line_dash="dot",
                      line_color="#F2555A", opacity=0.4,
                      annotation_text="risco", annotation_position="right",
                      annotation_font=dict(color="#F2555A", size=10))
        fig.update_layout(
            template="plotly_dark", height=310,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=40, r=50, t=16, b=38),
            xaxis=dict(title="dia", gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(title="", range=[0, 100],
                       gridcolor="rgba(255,255,255,0.06)"),
            legend=dict(orientation="h", y=1.14))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(diario)

    # ---------------- O que está pesando ----------------
    st.markdown("##### O que mais pesa no risco da sua máquina")
    recentes = dfp.tail(200)
    medias = {
        "inclinacao_g": recentes["inclinacao_g"].mean(),
        "vibracao_rms": recentes["vibracao_rms"].mean(),
        "umidade_pct": recentes["umidade_pct"].mean(),
    }
    contrib = []
    for campo, valor in medias.items():
        cfg = cf.FATORES_TELEMETRIA.get(campo)
        if not cfg:
            continue
        a = cf._normalizar_fator(valor, cfg)
        contrib.append((campo, cfg["peso"] * a, valor))
    contrib.sort(key=lambda x: x[1], reverse=True)

    frases = {
        "inclinacao_g": lambda v: (
            f"**Terreno inclinado** — média de {v:.0f}° no período. "
            f"É o fator que mais pesa: máquina inclinada é máquina que pode tombar."),
        "vibracao_rms": lambda v: (
            f"**Trepidação** — média de {v:.2f}. Vibração acima do normal "
            f"costuma indicar terreno irregular ou folga em peça."),
        "umidade_pct": lambda v: (
            f"**Solo úmido** — média de {v:.0f}% no período. "
            f"Solo encharcado tira aderência e aumenta risco de atolamento."),
    }
    for campo, peso, valor in contrib:
        if peso <= 0.02:
            continue
        st.markdown(f"- {frases[campo](valor)}")

    if not any(p > 0.02 for _, p, _ in contrib):
        st.markdown("- Nenhum fator em nível de atenção no período.")

    # ---------------- O que fazer ----------------
    st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
    if t and t.confiavel and t.inclinacao_pontos_por_semana > 0.3:
        st.warning(
            "**Vale procurar assistência.** O risco vem subindo de forma "
            "consistente, não é oscilação de um dia ruim. Uma revisão "
            "mecânica agora costuma custar bem menos que uma parada no meio "
            "da colheita.", icon="🔧")
    elif faixa_atual == "vermelho":
        st.error(
            "**Sua máquina está operando em condição de risco.** Vale "
            "conversar com sua corretora sobre uma inspeção.", icon="⚠️")
    else:
        st.success(
            "**Nada exige ação agora.** Continue acompanhando — o "
            "sinalizador na máquina avisa se algo mudar.", icon="✅")

    with st.expander("Como esse número é calculado"):
        st.markdown(f"""
        O nível de risco combina duas coisas.

        A primeira é o **perfil da sua apólice** — idade da máquina, região,
        tipo de cobertura. Para esta máquina, esse ponto de partida é
        **{_score_perfil(EQUIP_DEMO):.0f}**.

        A segunda é **o que o sensor mede durante a operação** — inclinação,
        obstáculo, trepidação, umidade do solo.

        A mesma inclinação pesa diferente em máquinas diferentes: numa
        máquina nova, em região tranquila, 14° é normal. Numa máquina de
        quinze anos, em região de mais sinistros, os mesmos 14° já são
        situação de atenção.
        """)
        st.caption(
            "O sistema avisa; a decisão de parar continua sendo sua. Nenhum "
            "comando é enviado à máquina.")


if __name__ == "__main__":
    render()
