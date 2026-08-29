"""
pagina_simulador_cenarios.py
============================
Simulacao de Cenarios · Sompo Predict · Sprint 3 · Squad T1

Owner: Rafael (UX do pitch) · Reviewers: Charles (core), Gustavo (API)

MIGRACAO Sprint 3 (substitui a versao que importava core_scoring):

    - Trocado core_scoring -> core_fusao. As 12 features simulaveis antigas
      (prox_corpo_dagua_km, velocidade_avg_kmh, etc) foram substituidas
      pelas features reais das duas camadas do motor: 4 de perfil (idade,
      UF, acessorios, ramo SUSEP) e 5 de telemetria (inclinacao, obstaculo,
      vibracao, umidade, temperatura).

    - O BASELINE_SUSEP nao e mais um dicionario chumbado com valores "P50
      SUSEP" inventados — agora e derivado da base real (mediana e moda de
      base_sompo_limpa.csv) e cai em fallback declarado se a base nao
      estiver disponivel.

    - Curva de sensibilidade agora respeita a estrutura de duas camadas:
      variavel de perfil varia o score_base; variavel de telemetria varia
      o score_final mantendo o perfil no baseline.

    - As linhas de cutoff do grafico (antes 40/75 fixos) agora vem de
      cf.FAIXAS, entao acompanham a calibracao empirica.

Diferencial vs simulador da US01:
    - A US01.tab_simul tem sliders simultaneos das duas camadas.
    - Esta pagina foca em UMA variavel critica por vez e exibe a CURVA DE
      SENSIBILIDADE completa do score, facilitando a narrativa do pitch
      ("se eu reduzo a inclinacao de 18 para 12 graus, o score cai X pontos").
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from core_audit import gerar_trilha_auditoria
from core_recomendacoes import gerar_recomendacao
import core_fusao as cf

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False


# =========================================================================
# 1. BASELINE EMPIRICO — derivado da base real, nao chumbado
# =========================================================================
_CAMINHO_BASE = Path("base_sompo_limpa.csv")


@st.cache_data(ttl=3600)
def _derivar_baseline_perfil() -> dict[str, Any]:
    """
    Mediana / moda das colunas de perfil na base real. Se a base nao existir,
    devolve fallback declarado (nao silencioso) — a tela avisa via badge.
    """
    if not _CAMINHO_BASE.exists():
        return {
            "IDADE_MAQUINA_ANOS":   8,
            "UF":                    "GO",
            "ACESSORIOS_SEGURADOS": 5,
            "RAMO_SUSEP":            "0621 - Agrícola",
            "_fonte":                "fallback",
        }
    df = pd.read_csv(_CAMINHO_BASE)
    return {
        "IDADE_MAQUINA_ANOS":   int(df["IDADE_MAQUINA_ANOS"].median()),
        "UF":                    str(df["UF"].mode().iloc[0]),
        "ACESSORIOS_SEGURADOS": int(df["ACESSORIOS_SEGURADOS"].median()),
        "RAMO_SUSEP":            str(df["RAMO_SUSEP"].mode().iloc[0]),
        "_fonte":                "base_sompo_limpa.csv",
    }


BASELINE_TELEMETRIA: dict[str, float] = {
    "inclinacao_g":      3.0,
    "dist_obstaculo_cm": 200.0,
    "vibracao_rms":      0.4,
    "umidade_pct":       50.0,
    "temperatura_c":     28.0,
}


# =========================================================================
# 2. METADADOS DAS VARIAVEIS SIMULAVEIS
# =========================================================================
VARIAVEIS_PERFIL: dict[str, dict] = {
    "IDADE_MAQUINA_ANOS": {
        "label":   "Idade da máquina",
        "min":      0.0, "max": 25.0, "step": 1.0,
        "unidade":  "anos",
        "ajuda":    "Pesa 40% do score de perfil. Satura em 15 anos.",
        "tipo":     "int",
    },
    "ACESSORIOS_SEGURADOS": {
        "label":   "Acessórios segurados",
        "min":      0.0, "max": 12.0, "step": 1.0,
        "unidade":  "itens",
        "ajuda":    "Relação inversa: mais cobertura, perfil melhor.",
        "tipo":     "int",
    },
}

VARIAVEIS_TELEMETRIA: dict[str, dict] = {
    "inclinacao_g": {
        "label":   "Inclinação",
        "min":      0.0, "max": 30.0, "step": 0.5,
        "unidade":  "°",
        "ajuda":    "Pesa 45% da telemetria. Override crítico em 25°.",
        "tipo":     "float",
    },
    "dist_obstaculo_cm": {
        "label":   "Distância do obstáculo",
        "min":      2.0, "max": 400.0, "step": 5.0,
        "unidade":  "cm",
        "ajuda":    "Neutro em 120 cm. Override crítico em 35 cm.",
        "tipo":     "float",
    },
    "vibracao_rms": {
        "label":   "Vibração",
        "min":      0.0, "max": 5.0, "step": 0.1,
        "unidade":  "m/s²",
        "ajuda":    "Proxy de terreno irregular e folga mecânica.",
        "tipo":     "float",
    },
    "umidade_pct": {
        "label":   "Umidade",
        "min":      0.0, "max": 100.0, "step": 1.0,
        "unidade":  "%",
        "ajuda":    "Fator ambiental do desafio Sompo.",
        "tipo":     "float",
    },
    "temperatura_c": {
        "label":   "Temperatura ambiente",
        "min":      -10.0, "max": 50.0, "step": 1.0,
        "unidade":  "°C",
        "ajuda":    "Menor peso do conjunto — completude climática.",
        "tipo":     "float",
    },
}

_TODAS_VARIAVEIS = {
    **{k: {**v, "camada": "perfil"} for k, v in VARIAVEIS_PERFIL.items()},
    **{k: {**v, "camada": "telemetria"} for k, v in VARIAVEIS_TELEMETRIA.items()},
}


# =========================================================================
# 3. CURVA DE SENSIBILIDADE
# =========================================================================
@st.cache_data(ttl=3600)
def _mapa_uf() -> dict:
    """
    Deriva o mapa de risco por UF UMA VEZ, da base completa. calcular_score_base
    aplicado a uma linha isolada nao consegue derivar esse mapa (nao tem
    CLASSIFICACAO_RISCO em uma linha so), entao passamos o mapa pronto.
    """
    if not _CAMINHO_BASE.exists():
        return {}
    return cf.mapa_uf_credibilidade(pd.read_csv(_CAMINHO_BASE))


def _score_base_linha(perfil: dict, mapa_uf: dict) -> float:
    df_1 = pd.DataFrame([perfil])
    return float(cf.calcular_score_base(df_1, mapa_uf=mapa_uf)["score_base"].iloc[0])


@st.cache_data(ttl=300, show_spinner=False)
def calcular_curva_sensibilidade(
    feature_alvo: str,
    baseline_perfil_tuple: tuple,
    baseline_tel_tuple: tuple,
    mapa_uf_tuple: tuple,
    n_pontos: int = 60,
) -> pd.DataFrame:
    """
    Varre a variavel alvo em n pontos e devolve (valor, score_final, faixa).
    Todos os args em tuple porque @st.cache_data exige hasheavel.
    """
    meta = _TODAS_VARIAVEIS[feature_alvo]
    baseline_perfil = dict(baseline_perfil_tuple)
    baseline_tel = dict(baseline_tel_tuple)
    mapa_uf = dict(mapa_uf_tuple)

    valores = np.linspace(meta["min"], meta["max"], n_pontos)
    scores, faixas = [], []

    for v in valores:
        if meta["camada"] == "perfil":
            perfil = {**baseline_perfil, feature_alvo: v}
            score_base = _score_base_linha(perfil, mapa_uf)
            resultado = cf.fundir(score_base, baseline_tel, perfil=perfil)
        else:
            score_base = _score_base_linha(baseline_perfil, mapa_uf)
            tel = {**baseline_tel, feature_alvo: v}
            resultado = cf.fundir(score_base, tel, perfil=baseline_perfil)

        scores.append(resultado.score_final)
        faixas.append(resultado.faixa)

    return pd.DataFrame({"valor": valores, "score": scores, "faixa": faixas})


# =========================================================================
# 4. PAGINA
# =========================================================================
def render() -> None:
    st.title("🧪 Simulador de Cenários")
    st.caption(
        "Rafael · Sprint 3 · Uma variável por vez, curva de sensibilidade "
        "completa. Ideal para narrar impacto no pitch."
    )

    baseline_perfil_completo = _derivar_baseline_perfil()
    fonte = baseline_perfil_completo.get("_fonte", "?")
    baseline_perfil = {k: v for k, v in baseline_perfil_completo.items()
                       if k != "_fonte"}

    if fonte == "fallback":
        st.warning(
            "⚠️ Baseline SUSEP em modo fallback — `base_sompo_limpa.csv` "
            "não encontrada. Os números são plausíveis, mas não derivados "
            "dos dados reais.",
            icon="⚠️",
        )
    else:
        st.caption(f"Baseline derivado de `{fonte}` (mediana/moda por coluna).")

    gerar_trilha_auditoria("ACESSO_SIMULADOR", "pagina=simulador_cenarios")

    st.info(
        "**Contrato funcional** · Slider único altera a variável selecionada · "
        "resto do baseline ancorado em `base_sompo_limpa.csv` · Score "
        "recalculado em tempo real via `core_fusao.fundir` · Recomendação "
        "acionável via `core_recomendacoes.gerar_recomendacao`."
    )

    # ---- seletor ----
    feature_alvo = st.selectbox(
        "🎯 Variável crítica a simular",
        options=list(_TODAS_VARIAVEIS.keys()),
        format_func=lambda f: (
            f"[{_TODAS_VARIAVEIS[f]['camada']}] "
            f"{_TODAS_VARIAVEIS[f]['label']} ({f})"
        ),
        help="Cada variável exibe seu range natural. As demais ficam "
             "fixas no baseline.",
        key="simul_feature",
    )
    meta = _TODAS_VARIAVEIS[feature_alvo]

    # ---- slider + score ----
    st.markdown("---")
    col_slider, col_score = st.columns([2, 1])

    if meta["camada"] == "perfil":
        baseline_val = baseline_perfil[feature_alvo]
    else:
        baseline_val = BASELINE_TELEMETRIA[feature_alvo]

    with col_slider:
        st.markdown(f"##### 🎚️ Ajuste a variável: **{meta['label']}**")
        if meta["tipo"] == "int":
            valor_atual = st.slider(
                f"Valor ({meta['unidade']})",
                int(meta["min"]), int(meta["max"]),
                int(baseline_val), int(meta["step"]),
                help=meta["ajuda"], key=f"simul_slider_{feature_alvo}",
            )
        else:
            valor_atual = st.slider(
                f"Valor ({meta['unidade']})",
                float(meta["min"]), float(meta["max"]),
                float(baseline_val), float(meta["step"]),
                help=meta["ajuda"], key=f"simul_slider_{feature_alvo}",
            )
        st.caption(
            f"🔎 Baseline: **{baseline_val} {meta['unidade']}** · "
            f"variação: **{valor_atual - float(baseline_val):+.2f} "
            f"{meta['unidade']}**"
        )

    # score do cenario atual
    perfil_atual = dict(baseline_perfil)
    tel_atual = dict(BASELINE_TELEMETRIA)
    if meta["camada"] == "perfil":
        perfil_atual[feature_alvo] = valor_atual
    else:
        tel_atual[feature_alvo] = valor_atual

    df_1 = pd.DataFrame([perfil_atual])
    mapa_uf = _mapa_uf()
    score_base = _score_base_linha(perfil_atual, mapa_uf)
    resultado = cf.fundir(score_base, tel_atual, perfil=perfil_atual)

    # score do baseline
    score_base_baseline = _score_base_linha(baseline_perfil, mapa_uf)
    resultado_base = cf.fundir(score_base_baseline, BASELINE_TELEMETRIA,
                               perfil=baseline_perfil)
    delta_score = resultado.score_final - resultado_base.score_final

    with col_score:
        cor = {"verde": "#22D48A", "amarelo": "#F5A623",
               "vermelho": "#FF4D6A"}[resultado.faixa]
        seta = "▲" if delta_score > 0 else ("▼" if delta_score < 0 else "▬")
        cor_delta = ("#FF4D6A" if delta_score > 0
                     else "#22D48A" if delta_score < 0 else "#8B8FA8")
        override = (
            f"<div style='color:#FF4D6A;font-size:0.72rem;margin-top:6px;'>"
            f"⚠️ Override: {resultado.motivo_override}</div>"
            if resultado.override_seguranca else ""
        )
        st.markdown(
            f"""<div style="background:#0D0F18;border:1px solid {cor}55;
                  border-left:4px solid {cor};border-radius:10px;
                  padding:18px;margin-top:1.2rem;">
                <div style="color:#8B8FA8;font-size:0.7rem;
                      letter-spacing:0.1em;text-transform:uppercase;">
                    Score do Cenário</div>
                <div style="font-size:2.6rem;font-weight:800;color:{cor};
                      margin:4px 0;line-height:1;">
                    {resultado.score_final:.1f}</div>
                <div style="font-size:0.78rem;color:{cor_delta};
                      font-weight:600;margin-top:6px;">
                    {seta} {delta_score:+.1f} vs baseline</div>
                <div style="color:#8B8FA8;font-size:0.7rem;margin-top:8px;">
                    Faixa: <strong style="color:{cor};">
                    {resultado.faixa.upper()}</strong></div>
                {override}
            </div>""",
            unsafe_allow_html=True,
        )

    # ---- curva ----
    st.markdown("---")
    st.markdown("##### 📈 Curva de Sensibilidade")
    corte_amarelo = cf.FAIXAS[1][0]
    corte_vermelho = cf.FAIXAS[2][0]
    st.caption(
        f"Varredura completa de **{meta['label']}** mantendo as demais "
        f"variáveis no baseline. Linhas tracejadas: cortes calibrados "
        f"({corte_amarelo:.1f} amarelo · {corte_vermelho:.1f} vermelho)."
    )

    baseline_perfil_tuple = tuple(sorted(baseline_perfil.items()))
    baseline_tel_tuple = tuple(sorted(BASELINE_TELEMETRIA.items()))
    mapa_uf_tuple = tuple(sorted(mapa_uf.items()))
    df_curva = calcular_curva_sensibilidade(
        feature_alvo, baseline_perfil_tuple, baseline_tel_tuple, mapa_uf_tuple
    )

    if PLOTLY_OK:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_curva["valor"], y=df_curva["score"], mode="lines",
            line=dict(color="#5B7FFF", width=2.5),
            hovertemplate=(
                f"<b>{meta['label']}</b>: %{{x:.2f}} {meta['unidade']}<br>"
                f"Score: <b>%{{y:.1f}}</b><extra></extra>"
            ),
        ))
        fig.add_trace(go.Scatter(
            x=[valor_atual], y=[resultado.score_final],
            mode="markers+text",
            marker=dict(color=cor, size=14,
                        line=dict(color="#EEF0F8", width=2)),
            text=[f"  {resultado.score_final:.1f}"],
            textposition="middle right",
            textfont=dict(color=cor, size=12, family="Arial Black"),
        ))
        fig.add_hline(y=corte_amarelo, line_dash="dash",
                      line_color="#F5A623", opacity=0.5,
                      annotation_text=f"{corte_amarelo:.1f} · amarelo",
                      annotation_position="right",
                      annotation_font=dict(color="#F5A623", size=10))
        fig.add_hline(y=corte_vermelho, line_dash="dash",
                      line_color="#FF4D6A", opacity=0.5,
                      annotation_text=f"{corte_vermelho:.1f} · vermelho",
                      annotation_position="right",
                      annotation_font=dict(color="#FF4D6A", size=10))
        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
            font=dict(color="#EEF0F8", family="Arial"),
            xaxis=dict(title=f"{meta['label']} ({meta['unidade']})",
                       gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(title="Score de Risco (0-100)",
                       gridcolor="rgba(255,255,255,0.06)", range=[0, 100]),
            height=380, margin=dict(l=50, r=30, t=20, b=50),
            showlegend=False, hovermode="closest",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(df_curva.set_index("valor")[["score"]])

    # ---- recomendacao ----
    st.markdown("---")
    st.markdown("##### 💡 Recomendação Acionável")
    recom = gerar_recomendacao(
        score=resultado.score_final, fator_dominante=feature_alvo,
    )
    st.markdown(
        f"""<div style="background:#0D0F18;border:1px solid {recom.cor}55;
              border-left:4px solid {recom.cor};border-radius:10px;
              padding:18px;margin-top:0.5rem;">
            <div style="display:flex;align-items:center;gap:12px;
                  margin-bottom:12px;">
                <div style="font-size:1.6rem;">{recom.icone}</div>
                <div>
                    <div style="font-size:1.05rem;font-weight:700;
                          color:{recom.cor};">
                        {recom.titulo}</div>
                    <div style="font-size:0.72rem;color:#8B8FA8;
                          letter-spacing:0.08em;text-transform:uppercase;">
                        SLA: {recom.prioridade_sla}</div>
                </div>
            </div>
            <div style="color:#EEF0F8;font-size:0.92rem;line-height:1.6;
                  margin-bottom:10px;">
                <strong>Ação principal:</strong> {recom.acao_principal}</div>
            <div style="color:#EEF0F8;font-size:0.92rem;line-height:1.6;
                  background:rgba(91,127,255,0.06);
                  border-left:2px solid #5B7FFF;
                  padding:10px 14px;border-radius:6px;margin-bottom:10px;">
                <strong style="color:#5B7FFF;">Contexto ({feature_alvo}):</strong>
                {recom.acao_contextual or '— sem alerta contextual para esta faixa'}
            </div>
            <div style="color:#8B8FA8;font-size:0.78rem;line-height:1.5;">
                ⏰ <strong>Prazo:</strong> {recom.prazo_acao}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ---- fatores ativos ----
    with st.expander("🔬 Detalhes técnicos · fatores da telemetria"):
        st.caption(
            f"Agravantes ativos na fusão (Camada 2). Contribuição = w × a. "
            f"Score base do perfil: **{score_base:.1f}**."
        )
        for campo, a in sorted(
            resultado.agravantes.items(),
            key=lambda kv: kv[1] * cf.FATORES_TELEMETRIA[kv[0]]["peso"],
            reverse=True,
        ):
            peso = cf.FATORES_TELEMETRIA[campo]["peso"]
            contrib = peso * a * 100
            direcao = "▲" if contrib > 0.5 else "▬"
            cor_pt = "#FF4D6A" if contrib > 0.5 else "#8B8FA8"
            st.markdown(
                f"<div style='font-family:monospace;color:#EEF0F8;"
                f"font-size:0.85rem;'>"
                f"<span style='color:{cor_pt};'>{direcao}</span> "
                f"<code>{campo}</code> · a={a:.2f} · peso={peso:.2f} · "
                f"<strong style='color:{cor_pt};'>"
                f"{contrib:+.1f}</strong> pontos brutos</div>",
                unsafe_allow_html=True,
            )

    gerar_trilha_auditoria(
        "SIMULACAO_CENARIO",
        f"feature={feature_alvo} | valor={valor_atual} | "
        f"score_base={score_base:.1f} | score_final={resultado.score_final:.1f} | "
        f"faixa={resultado.faixa} | delta_vs_base={delta_score:+.1f}",
    )


if __name__ == "__main__":
    render()
