"""
==============================================================================
SOMPO PREDICT · Gestão de Risco (US01)
==============================================================================
Owner: Charles · Reviewers: Rafael (score), Guilherme (dados)

Tela do subscritor/analista da Sompo: ordena a carteira por risco, permite
abrir um equipamento e ver por que ele está naquela posição.

Sprint 3 — reconstruída sobre core_fusao:
    A versão anterior tinha `_score_local()`, uma fórmula própria com pesos
    para inclinação/velocidade/proximidade de água/temperatura de motor —
    variáveis que não existem na base SUSEP real — e cortes 75/50/25 escritos
    à mão. Era a terceira implementação de score no projeto, e nenhuma delas
    concordava com as outras.
    Agora existe uma só: core_fusao. Camada 1 (perfil da apólice) alimenta
    esta tela; Camada 2 (telemetria) entra quando o equipamento tem sensor
    ativo. Os cortes das faixas são calibrados nos percentis da carteira,
    não constantes.
==============================================================================
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

import core_fusao as cf

CAMINHO_BASE = Path("base_sompo_limpa.csv")

_CORES = {"verde": "var(--verde)", "amarelo": "var(--amarelo)",
          "vermelho": "var(--vermelho)"}
_HEX = {"verde": "#3FCF8E", "amarelo": "#F5B23D", "vermelho": "#F2555A"}
_ROTULO = {"verde": "Operação normal", "amarelo": "Atenção",
           "vermelho": "Risco elevado"}


@st.cache_data(ttl=3600, show_spinner="Carregando carteira...")
def _carregar():
    """Base real. Sem fallback sintético — a tela avisa se faltar."""
    if not CAMINHO_BASE.exists():
        return None
    df = pd.read_csv(CAMINHO_BASE)
    df["equip_id"] = [f"COL-{i:03d}" for i in range(len(df))]
    return df


def _kpi(col, valor, rotulo, cor="var(--text)"):
    col.markdown(f"""
    <div class="g-card" style="padding:1rem 1.15rem;">
        <div class="g-num" style="color:{cor};">{valor}</div>
        <div class="g-label">{rotulo}</div>
    </div>
    """, unsafe_allow_html=True)


def render() -> None:
    from core_app import check_permissao, gerar_trilha_auditoria, _contrato_box

    if not check_permissao("view_dashboard"):
        return
    _contrato_box("pagina_us01", ["ACESSO_US01", "DRILL_DOWN_RISCO"])
    gerar_trilha_auditoria("ACESSO_US01", "pagina=gestao_risco")

    st.markdown("""
    <div style="padding:0.2rem 0 1.4rem;">
        <h1 style="margin:0;font-size:2.15rem;">Carteira de Risco</h1>
        <p style="color:var(--text-2);margin-top:0.6rem;font-size:0.95rem;
                  max-width:600px;line-height:1.6;">
            Apólices ordenadas por exposição. As primeiras posições concentram
            o risco que justifica inspeção ou revisão de cobertura na renovação.
        </p>
    </div>
    """, unsafe_allow_html=True)

    df = _carregar()
    if df is None:
        st.error(
            "`base_sompo_limpa.csv` não está na pasta do projeto. Esta tela "
            "trabalha apenas com a base SUSEP real — coloque o arquivo aqui "
            "para carregá-la.", icon="🚨")
        return

    cf.calibrar_faixas(df)
    scored = cf.calcular_score_base(df)
    scored["faixa"] = scored["score_base"].apply(lambda s: cf.classificar(s)[0])
    scored = scored.sort_values("score_base", ascending=False).reset_index(drop=True)
    scored.insert(0, "posição", scored.index + 1)

    # ---------- KPIs ----------
    n = {f: int((scored.faixa == f).sum()) for f in ("verde", "amarelo", "vermelho")}
    c1, c2, c3, c4 = st.columns(4)
    _kpi(c1, len(scored), "Apólices")
    _kpi(c2, n["verde"], "Operação normal", "var(--verde)")
    _kpi(c3, n["amarelo"], "Em atenção", "var(--amarelo)")
    _kpi(c4, n["vermelho"], "Risco elevado", "var(--vermelho)")

    st.markdown("<div style='height:1.6rem;'></div>", unsafe_allow_html=True)

    tab_cart, tab_detalhe, tab_modelo = st.tabs(
        ["Carteira", "Detalhe do equipamento", "Como o score é montado"])

    # =====================================================================
    # CARTEIRA
    # =====================================================================
    with tab_cart:
        col_f1, col_f2 = st.columns([1, 2])
        faixas_sel = col_f1.multiselect(
            "Mostrar faixas", ["vermelho", "amarelo", "verde"],
            default=["vermelho", "amarelo", "verde"],
            format_func=lambda f: _ROTULO[f], key="us01_faixas")
        ufs = sorted(scored.UF.unique().tolist())
        ufs_sel = col_f2.multiselect("Estados", ufs, default=ufs, key="us01_ufs")

        view = scored[scored.faixa.isin(faixas_sel)
                      & scored.UF.isin(ufs_sel)].copy()
        view["situação"] = view.faixa.map(_ROTULO)

        st.dataframe(
            view[["posição", "equip_id", "RAMO_SUSEP", "UF",
                  "IDADE_MAQUINA_ANOS", "score_base", "situação"]],
            column_config={
                "posição": st.column_config.NumberColumn("#", width="small"),
                "equip_id": st.column_config.TextColumn("Equipamento"),
                "RAMO_SUSEP": st.column_config.TextColumn("Ramo"),
                "UF": st.column_config.TextColumn("UF", width="small"),
                "IDADE_MAQUINA_ANOS": st.column_config.NumberColumn(
                    "Idade", width="small", format="%d anos"),
                "score_base": st.column_config.ProgressColumn(
                    "Score", format="%.1f", min_value=0, max_value=100),
                "situação": st.column_config.TextColumn("Situação"),
            },
            hide_index=True, use_container_width=True, height=430)

        st.download_button(
            "Baixar carteira em CSV",
            view.to_csv(index=False).encode("utf-8"),
            "carteira_risco_sompo.csv", "text/csv", key="us01_dl")

    # =====================================================================
    # DETALHE
    # =====================================================================
    with tab_detalhe:
        equip = st.selectbox("Equipamento", scored.equip_id.tolist(),
                             key="us01_drill")
        linha = scored.loc[scored.equip_id == equip].iloc[0]
        faixa = linha.faixa
        cor, hexcor = _CORES[faixa], _HEX[faixa]

        col_a, col_b = st.columns([1, 2])
        with col_a:
            st.markdown(f"""
            <div class="g-card lit" style="text-align:center;padding:1.6rem 1.2rem;">
                <div class="g-eyebrow">Score de perfil</div>
                <div style="font-family:'Manrope',sans-serif;font-size:3.4rem;
                      font-weight:800;color:{cor};line-height:1;margin:10px 0;
                      letter-spacing:-0.04em;">{linha.score_base:.1f}</div>
                <div class="pill" style="border-color:{hexcor}55;">
                    <span class="dot" style="background:{hexcor};
                          box-shadow:0 0 9px {hexcor};"></span>
                    <span style="color:{cor};">{_ROTULO[faixa]}</span>
                </div>
                <div style="margin-top:14px;font-size:0.76rem;color:var(--text-3);
                      line-height:1.7;">
                    {linha.RAMO_SUSEP}<br>{linha.UF} ·
                    {int(linha.IDADE_MAQUINA_ANOS)} anos ·
                    {int(linha.ACESSORIOS_SEGURADOS)} acessórios
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_b:
            st.markdown("**O que pesa neste score**")
            contribs = {c: float(linha[f"{c}_contrib"])
                        for c in cf.PESOS_PERFIL if f"{c}_contrib" in linha.index}
            nomes = {"IDADE_MAQUINA_ANOS": "Idade da máquina",
                     "UF": "Estado", "ACESSORIOS_SEGURADOS": "Acessórios",
                     "RAMO_SUSEP": "Ramo do seguro"}
            ordenado = sorted(contribs.items(), key=lambda kv: kv[1], reverse=True)
            if PLOTLY_OK:
                fig = go.Figure(go.Bar(
                    x=[v for _, v in ordenado],
                    y=[nomes.get(k, k) for k, _ in ordenado],
                    orientation="h", marker_color=hexcor,
                    hovertemplate="%{y}: %{x:.1f} pontos<extra></extra>"))
                fig.update_layout(
                    template="plotly_dark", height=230,
                    margin=dict(l=0, r=10, t=6, b=6),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(title="pontos no score",
                               gridcolor="rgba(255,255,255,0.06)"),
                    yaxis=dict(gridcolor="rgba(0,0,0,0)"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                for k, v in ordenado:
                    st.markdown(f"- **{nomes.get(k, k)}** · {v:.1f} pontos")

            st.caption(
                "Contribuições da Camada 1 (perfil da apólice). Quando o "
                "equipamento tem sensor ativo, a exposição do momento entra "
                "por cima disso — ver Área do Cliente.")

        gerar_trilha_auditoria("US01_DRILL_DOWN", f"equip={equip}")

    # =====================================================================
    # MODELO
    # =====================================================================
    with tab_modelo:
        st.markdown(
            "O score tem duas camadas. A primeira olha o histórico da "
            "apólice e muda de mês em mês. A segunda olha o que o sensor "
            "está medindo agora e muda a cada segundo.")

        c1, c2, c3 = st.columns(3)
        c1.metric("Operação normal", f"abaixo de {cf.FAIXAS[0][1]:.0f}")
        c2.metric("Atenção", f"{cf.FAIXAS[1][0]:.0f} a {cf.FAIXAS[1][1]:.0f}")
        c3.metric("Risco elevado", f"acima de {cf.FAIXAS[2][0]:.0f}")
        st.caption(
            "Os cortes são calibrados nos percentis 60 e 90 da própria "
            "carteira, recalculados a cada carga da base — não são "
            "constantes escritas no código.")

        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        st.markdown("**Camada 1 · perfil da apólice**")
        st.dataframe(cf.descrever_pesos().query("camada == 'perfil'")
                     [["fator", "peso", "justificativa"]],
                     use_container_width=True, hide_index=True)

        st.markdown("**Camada 2 · exposição medida pelo sensor**")
        st.dataframe(cf.descrever_pesos().query("camada == 'telemetria'")
                     [["fator", "peso", "justificativa"]],
                     use_container_width=True, hide_index=True)

        st.info(
            "Os pesos da Camada 2 são limiares de especialista, não "
            "aprendidos: a base SUSEP não contém inclinação, vibração nem "
            "distância de obstáculo, então não existe par (telemetria, "
            "sinistro) para treinar um modelo. Aprender esses pesos depende "
            "de acumular telemetria rotulada — etapa seguinte do roadmap.",
            icon="📌")

        with st.expander("Risco por estado — por que volume não é risco"):
            crit = (df.CLASSIFICACAO_RISCO == "Crítico")
            g = df.groupby("UF")
            t = pd.DataFrame({
                "registros": g.size(),
                "loss_ratio_%": (g.VALOR_INDENIZADO_BRL.sum()
                                 / g.PREMIO_LIQUIDO_BRL.sum() * 100).round(1),
                "críticos": crit.groupby(df.UF).sum(),
            }).sort_values("loss_ratio_%", ascending=False)
            st.dataframe(t, use_container_width=True)
            st.caption(
                "O estado com mais registros na base não é o de maior "
                "sinistralidade. O mapa usado no score suaviza a taxa por "
                "credibilidade de Bühlmann-Straub (k=30), o que impede uma "
                "UF com poucos casos de dominar o resultado.")


if __name__ == "__main__":
    render()
