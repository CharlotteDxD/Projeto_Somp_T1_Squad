"""
pagina_relatorios.py
====================
Relatório de risco de frota — o que o motor identifica sobre um período
de operação.

AMBIENTE DE DEMONSTRAÇÃO

    Esta tela opera sobre telemetria simulada enquanto a frota real não
    estiver instrumentada. A distinção que sustenta a demonstração:

        os SENSORES são simulados
        o MOTOR DE ANÁLISE é o mesmo que roda em campo

    Nenhum achado desta tela é escrito à mão. Tendência, exposição,
    antecipação e recomendação saem de aplicar `core_fusao` sobre a série e
    procurar padrões nos resultados. Trocada a origem da série por um
    dispositivo real, a mesma análise roda sem alteração de código.

    O seletor de origem no topo torna isso explícito para quem assiste.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import core_fusao as cf
import core_relatorio as cr
from motor_simulacao import resumo_perfis, simular_frota

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

CAMINHO_BASE = Path("base_sompo_limpa.csv")
_HEX = {"verde": "#3FCF8E", "amarelo": "#F5B23D", "vermelho": "#F2555A"}


@st.cache_data(ttl=3600, show_spinner=False)
def _frota_monitorada(n: int) -> dict[str, float]:
    """
    Score de perfil dos equipamentos monitorados.

    Amostra estratificada da carteira, entre os percentis 8 e 88. Pegar as
    primeiras linhas traria um recorte arbitrário; incluir os extremos
    colocaria equipamentos saturados que não ilustram nada — um que nunca
    sai do verde e outro travado no topo.
    """
    if not CAMINHO_BASE.exists():
        return {f"COL-{i:03d}": 55.0 for i in range(n)}
    base = pd.read_csv(CAMINHO_BASE)
    cf.calibrar_faixas(base)
    sc = cf.calcular_score_base(base).sort_values("score_base").reset_index(drop=True)
    lo, hi = int(len(sc) * 0.08), int(len(sc) * 0.88)
    idx = np.linspace(lo, hi, n).astype(int)
    return {f"COL-{i:03d}": float(v)
            for i, v in enumerate(sc.loc[idx, "score_base"])}


@st.cache_data(ttl=1800, show_spinner="Analisando o período...")
def _analisar(n_equip: int, dias: int):
    df, perfis = simular_frota(n_equipamentos=n_equip, dias=dias)
    dfp = cr.pontuar_serie(df, score_base_por_equip=_frota_monitorada(n_equip))
    return dfp, resumo_perfis(perfis), cr.gerar_relatorio(dfp)


def _kpi(col, valor, rotulo, cor="var(--text)", nota=""):
    extra = (f'<div style="font-size:0.68rem;color:var(--text-3);'
             f'margin-top:4px;">{nota}</div>') if nota else ""
    col.markdown(f"""
    <div class="g-card" style="padding:1rem 1.15rem;">
        <div class="g-num" style="color:{cor};">{valor}</div>
        <div class="g-label">{rotulo}</div>{extra}
    </div>
    """, unsafe_allow_html=True)


def render() -> None:
    from core_app import (check_permissao, gerar_trilha_auditoria,
                          _contrato_box, _header)

    if not check_permissao("view_dashboard"):
        return
    _contrato_box("relatorios", [])
    _header("Relatório de Risco",
            "O que a análise identifica sobre um período de operação")
    gerar_trilha_auditoria("ACESSO_RELATORIO", "pagina=relatorios")

    # ---------------- Selo de procedência ----------------
    st.markdown("""
    <div style="background:rgba(245,178,61,0.07);
          border:1px solid rgba(245,178,61,0.35);
          border-left:3px solid var(--amarelo);border-radius:10px;
          padding:12px 16px;margin-bottom:1.4rem;">
        <div style="display:flex;align-items:center;gap:9px;">
            <span style="width:7px;height:7px;border-radius:50%;
                  background:var(--amarelo);box-shadow:0 0 8px var(--amarelo);
                  flex:none;"></span>
            <span style="color:var(--amarelo);font-weight:600;
                  font-size:0.84rem;">Ambiente de demonstração</span>
        </div>
        <div style="font-size:0.79rem;color:var(--text-2);margin-top:6px;
              line-height:1.6;">
            As leituras de sensor deste relatório são simuladas — a frota
            ainda não está instrumentada. <strong>O motor de análise é o
            mesmo que opera em campo:</strong> tendências, exposição e
            recomendações abaixo são resultado do cálculo real aplicado a
            esta série, não texto pré-escrito. Conectado o dispositivo, a
            mesma análise roda sobre dados reais sem alteração de código.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_a, col_b, _ = st.columns([1, 1, 2])
    n_equip = col_a.selectbox("Equipamentos", [8, 12, 16], index=1,
                              key="rel_n")
    dias = col_b.selectbox("Período analisado", [30, 60, 90], index=2,
                           format_func=lambda d: f"{d} dias", key="rel_d")

    dfp, perfis, r = _analisar(n_equip, dias)

    # ---------------- Indicadores ----------------
    faixas = dfp["faixa"].value_counts(normalize=True) * 100
    em_det = len(r.em_deterioracao)
    urgentes = sum(1 for x in r.recomendacoes if x.prioridade == 1)

    c1, c2, c3, c4 = st.columns(4)
    _kpi(c1, f"{r.n_leituras:,}".replace(",", "."), "Leituras analisadas",
         "var(--text)", f"{r.n_equipamentos} equipamentos · {r.periodo_dias} dias")
    _kpi(c2, f"{faixas.get('verde', 0):.0f}%", "Em operação normal",
         "var(--verde)")
    _kpi(c3, f"{em_det}", "Em deterioração",
         "var(--amarelo)" if em_det else "var(--verde)",
         "tendência estatisticamente consistente")
    _kpi(c4, f"{urgentes}", "Exigem ação imediata",
         "var(--vermelho)" if urgentes else "var(--verde)")

    st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)

    tabs = st.tabs(["Ações recomendadas", "Tendência", "Situação da frota",
                    "Antecipação", "Perfil operacional"])

    # =================================================================
    with tabs[0]:
        if not r.recomendacoes:
            st.success("Nenhuma ação recomendada para o período.", icon="✅")
        else:
            st.markdown(
                "Cada recomendação traz o fundamento numérico que a originou. "
                "Recomendação sem fundamento visível é opinião.")
            cores_p = {1: "var(--vermelho)", 2: "var(--amarelo)",
                       3: "var(--text-3)"}
            rotulo_p = {1: "Imediata", 2: "Programar", 3: "Acompanhar"}
            for rec in r.recomendacoes:
                cor = cores_p[rec.prioridade]
                st.markdown(f"""
                <div class="g-card" style="padding:1.1rem 1.3rem;
                     margin-bottom:9px;border-left:3px solid {cor};">
                    <div style="display:flex;justify-content:space-between;
                          align-items:baseline;gap:14px;">
                        <div>
                            <span style="font-family:'JetBrains Mono',monospace;
                                  font-size:0.8rem;color:var(--text-3);">
                                {rec.equip_id}</span>
                            <span style="font-weight:700;font-size:0.98rem;
                                  color:var(--text);margin-left:10px;">
                                {rec.titulo}</span>
                        </div>
                        <span style="font-size:0.7rem;color:{cor};
                              font-weight:700;text-transform:uppercase;
                              letter-spacing:0.06em;flex:none;">
                            {rotulo_p[rec.prioridade]}</span>
                    </div>
                    <div style="font-size:0.79rem;color:var(--text-3);
                          margin-top:8px;line-height:1.6;
                          font-family:'JetBrains Mono',monospace;">
                        {rec.fundamento}</div>
                    <div style="font-size:0.88rem;color:var(--text);
                          margin-top:9px;line-height:1.6;">
                        {rec.acao}</div>
                </div>
                """, unsafe_allow_html=True)

    # =================================================================
    with tabs[1]:
        st.markdown(
            "Regressão do score diário de cada equipamento. A projeção só é "
            "emitida quando o ajuste explica parte relevante da variação "
            "&mdash; projetar sobre série que apenas oscila produz número "
            "sem significado.")

        det = r.em_deterioracao
        if not det:
            st.info("Nenhum equipamento apresenta tendência consistente de "
                    "piora no período.", icon="📈")
        else:
            st.dataframe(
                pd.DataFrame([{
                    "Equipamento": t.equip_id,
                    "Score inicial": t.score_inicial,
                    "Score atual": t.score_atual,
                    "Pontos/semana": t.inclinacao_pontos_por_semana,
                    "R²": t.r2,
                    "Leitura": t.leitura,
                } for t in det]),
                column_config={
                    "Pontos/semana": st.column_config.NumberColumn(
                        "Pontos/semana", format="%+.2f"),
                    "R²": st.column_config.ProgressColumn(
                        "R²", format="%.2f", min_value=0.0, max_value=1.0),
                },
                hide_index=True, use_container_width=True)

            if PLOTLY_OK:
                alvo = st.selectbox("Ver evolução de",
                                    [t.equip_id for t in det], key="rel_tend")
                g = dfp[dfp["equip_id"] == alvo].groupby("dia")["score"].mean()
                t = next(x for x in det if x.equip_id == alvo)
                coef = np.polyfit(g.index.to_numpy(float), g.to_numpy(), 1)

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=g.index, y=g.values, mode="lines", name="score diário",
                    line=dict(color="#5B7FFF", width=1.6)))
                fig.add_trace(go.Scatter(
                    x=g.index, y=np.polyval(coef, g.index.to_numpy(float)),
                    mode="lines", name="tendência",
                    line=dict(color="#F5B23D", width=2.4, dash="dash")))
                fig.add_hline(y=cf.FAIXAS[1][0], line_dash="dot",
                              line_color="#F5B23D", opacity=0.45)
                fig.add_hline(y=cf.FAIXAS[2][0], line_dash="dot",
                              line_color="#F2555A", opacity=0.45)
                fig.update_layout(
                    template="plotly_dark", height=330,
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=45, r=20, t=20, b=40),
                    xaxis=dict(title="dia de operação",
                               gridcolor="rgba(255,255,255,0.06)"),
                    yaxis=dict(title="score", range=[0, 100],
                               gridcolor="rgba(255,255,255,0.06)"),
                    legend=dict(orientation="h", y=1.12))
                st.plotly_chart(fig, use_container_width=True)
                st.caption(
                    f"{alvo}: {t.inclinacao_pontos_por_semana:+.2f} pontos por "
                    f"semana, R²={t.r2:.2f}. {t.leitura.capitalize()}.")

    # =================================================================
    with tabs[2]:
        st.markdown("Últimos 7 dias de operação.")
        st.dataframe(
            r.situacao,
            column_config={
                "Score médio": st.column_config.ProgressColumn(
                    "Score médio", format="%.1f", min_value=0, max_value=100),
                "% em risco": st.column_config.NumberColumn(
                    "% em risco", format="%.1f%%"),
                "% em atenção": st.column_config.NumberColumn(
                    "% em atenção", format="%.1f%%"),
            },
            hide_index=True, use_container_width=True)

        st.markdown("##### Exposição acumulada no período")
        st.caption(
            "Duas máquinas com o mesmo score médio podem ter históricos "
            "distintos: uma estável no limite, outra alternando entre "
            "tranquila e crítica. A média esconde essa diferença.")
        st.dataframe(r.exposicao, hide_index=True, use_container_width=True)

        st.download_button(
            "Exportar relatório em CSV",
            r.exposicao.to_csv(index=False).encode("utf-8"),
            f"relatorio_frota_{datetime.now():%Y%m%d}.csv", "text/csv",
            key="rel_dl")

    # =================================================================
    with tabs[3]:
        a = r.antecipacao
        st.markdown("##### Alertas que precederam condição crítica")
        c1, c2, c3 = st.columns(3)
        _kpi(c1, a.eventos_criticos, "Episódios críticos")
        _kpi(c2, f"{a.percentual:.0f}%", "Precedidos por alerta",
             "var(--verde)" if a.percentual >= 50 else "var(--amarelo)")
        _kpi(c3, f"{a.mediana_leituras_antes:.0f}" if a.mediana_leituras_antes
             else "—", "Leituras de antecedência", nota="mediana")

        st.markdown(f"""
        <div style='height:1rem;'></div>

        Dos **{a.eventos_criticos} episódios** em que um equipamento atingiu
        condição crítica no período, **{a.precedidos_por_alerta} foram
        precedidos por um alerta** dentro das {a.janela_leituras} leituras
        anteriores.

        É essa a medida que descreve a prevenção de forma verificável: não
        *"quantos sinistros evitamos"* &mdash; isso exige operação em campo
        &mdash; mas *"quantas vezes o sistema teve a chance de avisar
        antes"*. A distância entre as duas afirmações é a diferença entre
        demonstração e promessa.
        """, unsafe_allow_html=True)

    # =================================================================
    with tabs[4]:
        st.markdown(
            "Perfil operacional atribuído a cada equipamento na simulação. "
            "É daqui que emergem os padrões que a análise encontra &mdash; a "
            "deterioração vem do estado de conservação combinado às horas "
            "acumuladas, não de um resultado escrito no relatório.")
        st.dataframe(perfis, hide_index=True, use_container_width=True)
        st.caption(
            "Ao conectar o dispositivo, esta aba deixa de existir: o perfil "
            "operacional passa a ser observado, não atribuído.")


if __name__ == "__main__":
    render()
