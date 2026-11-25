"""Sompo Predict, avaliação de risco de equipamento agrícola.

    streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import modelo_exp
import risco

AQUI = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Sompo Predict | Risco de equipamento agrícola",
    page_icon=str(AQUI / "assets" / "favicon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

COR = {"verde": "#3FCF8E", "amarelo": "#F5B23D", "vermelho": "#F2555A"}
TITULO_PRODUTOR = {"verde": "Sua máquina está bem",
                   "amarelo": "Vale ficar de olho",
                   "vermelho": "Precisa de atenção"}
MUTED = "#94A3B8"

st.markdown(f"""
<style>
  .block-container {{ padding-top: 2.2rem; max-width: 1400px; }}
  h1 {{ font-size: 1.9rem !important; letter-spacing: -0.01em; }}
  .score-num {{ font-size: 5.2rem; font-weight: 700; line-height: 1; }}
  .score-de {{ font-size: 1.3rem; color: {MUTED}; margin-left: 4px; }}
  .nivel {{ font-size: 1.7rem; font-weight: 650; margin: 0.2rem 0 0.4rem; }}
  .recom {{ font-size: 1.05rem; max-width: 46rem; }}
  .escala {{ display: flex; height: 12px; border-radius: 3px; overflow: hidden;
            position: relative; margin-top: 1.1rem; }}
  .escala > div {{ height: 100%; }}
  .marca {{ position: absolute; top: -5px; width: 3px; height: 22px;
           background: #F8FAFC; border-radius: 1px; }}
  .escala-rot {{ display: flex; font-size: .85rem; color: {MUTED};
                margin-top: 6px; }}
  .escala-rot span {{ white-space: nowrap; overflow: hidden; }}
  .aviso {{ border-left: 3px solid #F5B23D; padding: .5rem .9rem;
           background: rgba(245,178,61,.08); font-size: .95rem; }}
  .rodape {{ color: {MUTED}; font-size: .85rem; margin-top: 2.5rem; }}
  button[data-baseweb="tab"] {{ font-size: 1rem; }}
</style>
""", unsafe_allow_html=True)

opc = risco.opcoes()
PADRAO = risco.CENARIOS["Terreno plano e seco"]
CHAVES = {"inclinacao_g": "s_incl", "dist_obstaculo_cm": "s_obst",
          "vibracao_rms": "s_vib", "umidade_pct": "s_umid",
          "temperatura_c": "s_temp"}

for campo, chave in CHAVES.items():
    st.session_state.setdefault(chave, PADRAO[campo])
st.session_state.setdefault("preset", "Terreno plano e seco")


def aplicar_cenario():
    nome = st.session_state.preset
    if nome in risco.CENARIOS:
        for campo, chave in CHAVES.items():
            st.session_state[chave] = risco.CENARIOS[nome][campo]


def marcar_manual():
    st.session_state.preset = "Personalizado"


# ---------------------------------------------------------------- cabeçalho
topo, seletor = st.columns([3, 1.2], vertical_alignment="bottom")
with topo:
    st.title("Risco de dano ou perda de equipamento agrícola")
    st.write("Informe os dados da apólice e as condições em campo. "
             "O score vai de 0 a 100 e mostra o que mais pesa no resultado.")
with seletor:
    visao = st.radio("Quem está olhando", ["Seguradora", "Produtor rural"],
                     horizontal=True)

produtor = visao == "Produtor rural"

# ------------------------------------------------------------------- entrada
col_in, col_out = st.columns([1, 1.9], gap="large")

with col_in:
    st.subheader("Apólice")
    uf = st.selectbox("Estado", opc["uf"], index=opc["uf"].index("MT"))
    modalidade = st.selectbox(
        "Modalidade", opc["modalidade"],
        index=[m.startswith("Penhor") for m in opc["modalidade"]].index(True))
    premio = st.number_input("Prêmio líquido anual (R$)", min_value=1.0,
                             max_value=1_000_000.0, value=6500.0, step=500.0,
                             format="%.0f")
    coberturas = st.number_input("Coberturas contratadas", min_value=1,
                                 max_value=20, value=2, step=1)

    st.subheader("Condições em campo")
    st.selectbox("Cenário pronto", ["Personalizado", *risco.CENARIOS],
                 key="preset", on_change=aplicar_cenario)
    incl = st.slider("Inclinação do terreno (graus)", 0.0, 40.0,
                     key="s_incl", step=0.5, on_change=marcar_manual)
    obst = st.slider("Distância do obstáculo à frente (cm)", 0.0, 400.0,
                     key="s_obst", step=5.0, on_change=marcar_manual,
                     help="400 cm equivale a nada à frente.")
    vib = st.slider("Vibração (RMS)", 0.0, 4.0, key="s_vib", step=0.1,
                    on_change=marcar_manual)
    umid = st.slider("Umidade do ar (%)", 0.0, 100.0, key="s_umid", step=1.0,
                     on_change=marcar_manual)
    temp = st.slider("Temperatura (°C)", 0.0, 50.0, key="s_temp", step=1.0,
                     on_change=marcar_manual)

perfil = {"UF": uf, "MODALIDADE_SUSEP": modalidade,
          "PREMIO_LIQUIDO_BRL": float(premio),
          "QTD_COBERTURAS_CONTRATADAS": int(coberturas)}
tel = {"inclinacao_g": incl, "dist_obstaculo_cm": obst, "vibracao_rms": vib,
       "umidade_pct": umid, "temperatura_c": temp}

try:
    av = risco.avaliar(perfil, tel)
except risco.EntradaInvalida as e:
    col_out.error(f"Não foi possível calcular: {e} Ajuste o campo e tente de novo.")
    st.stop()

cor = COR[av.faixa]
c1, c2 = risco.cortes()


# ------------------------------------------------------------------ blocos
def faixa_resultado():
    marca = min(max(av.score_final, 0), 100)
    st.markdown(f"""
    <div role="img" aria-label="Score {av.score_final:.0f} de 100, risco {av.nivel}">
      <div><span class="score-num" style="color:{cor}">{av.score_final:.0f}</span><span class="score-de">/ 100</span></div>
      <div class="nivel" style="color:{cor}">{"Risco " + av.nivel.lower() if not produtor else TITULO_PRODUTOR[av.faixa]}</div>
      <div class="recom">{av.recomendacao}</div>
      <div class="escala">
        <div style="width:{c1}%;background:{COR['verde']}"></div>
        <div style="width:{c2 - c1}%;background:{COR['amarelo']}"></div>
        <div style="width:{100 - c2}%;background:{COR['vermelho']}"></div>
        <div class="marca" style="left:calc({marca}% - 1px)"></div>
      </div>
      <div class="escala-rot">
        <span style="width:{c1}%">Baixo</span>
        <span style="width:{c2 - c1}%">Médio</span>
        <span style="width:{100 - c2}%">Alto</span></div>
      <div class="escala-rot" style="margin-top:2px">Baixo até {c1:.0f}, médio até {c2:.0f}, alto acima disso.</div>
    </div>
    """, unsafe_allow_html=True)
    if av.override:
        st.markdown(
            '<div class="aviso" style="margin-top:1rem">Regra de segurança acionada: '
            "inclinação ou obstáculo passou do limite crítico, então o nível é Alto "
            "independente do score.</div>", unsafe_allow_html=True)


def lista_motivos(titulo: str):
    st.markdown(f"##### {titulo}")
    frases = risco.frases_produtor(av, perfil, tel) if produtor else av.frases
    for f in frases:
        st.markdown(f"- {f}")


def grafico_fatores():
    dados = [f for f in av.fatores if abs(f.pontos) >= 0.05]
    dados.sort(key=lambda f: f.pontos)
    cores = {"apólice": "#64748B", "campo": "#3B82F6", "regra": COR["vermelho"]}
    fig = go.Figure(go.Bar(
        x=[f.pontos for f in dados], y=[f.nome for f in dados], orientation="h",
        marker_color=[cores[f.grupo] for f in dados],
        text=[f"{f.pontos:+.1f}" if f.grupo != "apólice" else f"{f.pontos:.1f}"
              for f in dados],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:.1f} pontos<extra></extra>"))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", height=60 + 34 * len(dados),
        margin=dict(l=0, r=40, t=10, b=30), font=dict(size=14, color="#F8FAFC"),
        xaxis=dict(title="Pontos no score", gridcolor="#1E293B", zeroline=False),
        yaxis=dict(automargin=True))
    st.plotly_chart(fig, width="stretch",
                    config={"displayModeBar": False})
    st.caption("Cinza: fatores da apólice. Azul: condições em campo, que "
               "aumentam o score da apólice. Juntos somam o score final.")


def tab_resultado():
    faixa_resultado()
    st.write("")
    if produtor:
        lista_motivos("O que mais pesa agora")
        st.caption("O sistema avisa, mas quem decide parar a máquina é o operador.")
        return
    lista_motivos("Por que este nível")
    grafico_fatores()
    campo_pts = av.score_final - av.score_base
    st.write(
        f"Apólice: **{av.score_base:.1f}** pontos, mais alto que "
        f"**{av.percentil_carteira:.0f}%** das 150 apólices da base. "
        f"Condições em campo: **{campo_pts:+.1f}** pontos.")
    with st.expander("Mesma apólice em outros cenários de campo"):
        linhas = []
        for nome, t in risco.CENARIOS.items():
            a = risco.avaliar(perfil, t)
            linhas.append({"Cenário": nome, "Score": round(a.score_final, 1),
                           "Nível": a.nivel})
        st.dataframe(pd.DataFrame(linhas), hide_index=True,
                     width="stretch")


def tab_metodo():
    st.markdown(
        "O score tem duas camadas. A **apólice** dá o ponto de partida (0 a 100), "
        "calculado com colunas reais da SUSEP. As **condições em campo**, lidas "
        "pelo ESP32, multiplicam esse ponto de partida:")
    st.code("score = ponto de partida x (1 + 1,5 x soma dos pesos x intensidades)",
            language=None)
    st.write(
        f"Cortes do nível, calibrados pelos percentis 60 e 90 da carteira: "
        f"Baixo até {c1:.1f}, médio até {c2:.1f}, alto acima disso. "
        "Inclinação acima de 25 graus ou obstáculo a menos de 35 cm força o nível "
        "Alto, mesmo com score baixo.")
    st.table(risco.tabela_pesos())
    st.markdown(
        "**O que o score não é.** Os pesos de campo vêm de julgamento de "
        "especialista, não de treino: a base da SUSEP não tem inclinação, "
        "vibração nem distância de obstáculo, então não existe par "
        "(telemetria, sinistro) para aprender.")


def tab_modelo():
    r = modelo_exp.prever(uf, modalidade, int(coberturas))
    st.markdown(
        "Além do score de regras, treinamos uma **regressão logística** com as "
        "150 apólices para prever caso crítico. Ela usa só o que se sabe na "
        "contratação: estado, modalidade, coberturas e vigência.")
    k1, k2 = st.columns(2)
    k1.metric("Índice do modelo para esta apólice", f"{r['probabilidade']*100:.0f}%",
              help="Não é probabilidade real. A base foi montada com 9,3% de "
                   "críticos e o modelo usa pesos balanceados, então o número "
                   "superestima o risco de uma carteira de verdade.")
    k2.metric("Casos críticos na base", f"{r['prevalencia_amostra']*100:.1f}%",
              help="14 de 150 apólices.")

    inf = pd.Series({k: float(v) for k, v in r["influencia"].items()}).sort_values()
    fig = go.Figure(go.Bar(
        x=inf.values, y=inf.index, orientation="h",
        marker_color=[COR["vermelho"] if v > 0 else COR["verde"] for v in inf.values],
        hovertemplate="%{y}: %{x:+.2f}<extra></extra>"))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", height=230,
        margin=dict(l=0, r=10, t=10, b=30), font=dict(size=14, color="#F8FAFC"),
        xaxis=dict(title="Empurra para menos risco (esquerda) ou mais (direita)",
                   gridcolor="#1E293B"))
    st.plotly_chart(fig, width="stretch",
                    config={"displayModeBar": False})

    st.markdown("##### Por que o modelo não vai para produção")
    cmp = modelo_exp.COMPARATIVO_GRUPO
    base_auc = float(cmp.loc[0, "ROC-AUC"])
    fig2 = go.Figure(go.Bar(
        x=cmp["ROC-AUC"], y=cmp["Modelo"], orientation="h",
        error_x=dict(type="data", array=cmp["Desvio"], color="#F8FAFC"),
        marker_color=["#64748B"] + ["#3B82F6"] * (len(cmp) - 1)))
    fig2.add_vline(x=base_auc, line_dash="dash", line_color=COR["amarelo"])
    fig2.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", height=320,
        margin=dict(l=0, r=10, t=10, b=40), font=dict(size=14, color="#F8FAFC"),
        xaxis=dict(title="ROC-AUC (média e desvio em 50 partições)", range=[0.3, 0.85],
                   gridcolor="#1E293B"),
        yaxis=dict(autorange="reversed", automargin=True))
    st.plotly_chart(fig2, width="stretch",
                    config={"displayModeBar": False})
    st.write(
        "Nenhum modelo supera o baseline por mais de um desvio-padrão. Com 150 "
        "apólices e 14 casos críticos, o limite é o volume de dados, não o "
        "algoritmo. Por isso o score em produção é o de regras, que é auditável "
        "e tem a regra de segurança por cima.")
    st.caption("Fonte: RESULTADOS_MODELO_sprint4.md, validação cruzada 5 folds "
               "x 10 repetições, semente 42, alvo caso crítico.")


# --------------------------------------------------------------------- saída
with col_out:
    if produtor:
        tab_resultado()
    else:
        t1, t2, t3 = st.tabs(["Resultado", "Como o score é calculado",
                              "Modelo de ML"])
        with t1:
            tab_resultado()
        with t2:
            tab_metodo()
        with t3:
            tab_modelo()

st.markdown(
    '<div class="rodape">Protótipo acadêmico FIAP e Sompo. Base: SUSEP, Seguro '
    "Rural 2021, 150 apólices de máquinas agrícolas em GO, MS e MT. As condições "
    "em campo vêm dos controles ao lado, não de um sensor real. Este app não "
    "guarda nenhum dado digitado.</div>", unsafe_allow_html=True)
