"""
==============================================================================
SOMPO PREDICT v15 - US07: SUBSCRICAO COM XAI
==============================================================================
Owner:     Charles (placeholder funcional ate Rafael entregar SHAP real)
Tipo:      Pagina do MENU - visao do Subscritor / Underwriter
Prioridade: ALTA

User Story:
    "Como Subscritor da Sompo, quero analisar uma proposta de seguro
     com explicabilidade XAI para decidir aceitacao, recusa ou ajuste
     de premio com base em fatores tecnicos transparentes."

Acceptance Criteria atendidos:
    [x] Lista de propostas pendentes ordenada por urgencia
    [x] Decomposicao SHAP-like de cada fator de risco
    [x] Decisao auditada (aceitar / recusar / contraproposta)
    [x] Calculo de premio ajustado pelo score
    [x] Comparativo com perfil medio da carteira
==============================================================================
"""
import time
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

from core_data_adapter import carregar_dataset, status_dados


# ==========================================================================
# DATASET MOCK - PROPOSTAS PENDENTES DE SUBSCRICAO
# ==========================================================================

def _propostas_mock() -> pd.DataFrame:
    """Propostas aguardando aprovacao do subscritor."""
    np.random.seed(73)
    nomes = [
        "Fazenda Santa Helena", "Agro Vale Verde", "Estancia Boa Vista",
        "Sitio Capim Dourado", "Fazenda Tres Irmaos", "Campos do Cerrado SA",
        "Agropecuaria Aurora", "Fazenda Sao Bento", "Vale do Sol Agro",
        "Fazenda Nova Era",
    ]
    tipos     = ["Colheitadeira", "Trator", "Pulverizador", "Plantadeira"]
    regioes   = ["Sul", "Centro-Oeste", "Sudeste", "Norte", "Nordeste"]

    propostas = []
    for i, nome in enumerate(nomes):
        valor = np.random.randint(450_000, 2_500_000)
        score = round(np.random.uniform(20, 88), 1)
        # Premio base e 4% do valor, ajustado pelo score
        premio_base = valor * 0.04
        premio_ajustado = premio_base * (1 + (score - 50) / 100)

        propostas.append({
            "ID":              f"PROP-{2024100 + i}",
            "Cliente":         nome,
            "Equipamento":     np.random.choice(tipos),
            "Regiao":          np.random.choice(regioes),
            "Valor_Segurado":  valor,
            "Score_Risco":     score,
            "Premio_Base":     round(premio_base, 2),
            "Premio_Sugerido": round(premio_ajustado, 2),
            "Idade_Equip":     np.random.randint(1, 18),
            "Hist_Sinistros":  np.random.choice([0, 1, 2, 3], p=[0.55, 0.25, 0.15, 0.05]),
            "Dias_Aguardando": np.random.randint(1, 14),
            "Status":          "Pendente",
        })
    return pd.DataFrame(propostas)


def _shap_proposta(row: pd.Series) -> dict:
    """
    Decomposicao SHAP-like dos fatores que compoem o score.
    Em producao virá do modelo XGBoost real do Guilherme/Rafael.
    """
    np.random.seed(int(row["Score_Risco"] * 100) % 2**31)

    # Distribui o score entre os 5 fatores
    base    = row["Score_Risco"] * 0.15
    inclin  = row["Score_Risco"] * np.random.uniform(0.20, 0.35)
    idade   = min(row["Idade_Equip"] / 18, 1) * 12
    hist    = row["Hist_Sinistros"] * 8
    regiao  = np.random.uniform(2, 8)
    clima   = np.random.uniform(3, 10)

    return {
        "Inclinacao do terreno":   round(inclin, 1),
        "Idade do equipamento":    round(idade, 1),
        "Historico de sinistros":  round(hist, 1),
        "Risco regional":          round(regiao, 1),
        "Clima / sazonalidade":    round(clima, 1),
        "Base (E[f(x)])":          round(base, 1),
    }


def _categoria_subscricao(score: float) -> tuple:
    """Mapeia score em decisao recomendada pelo modelo."""
    if score >= 75:
        return ("RECUSAR", "#FF4D6A",
                "Risco muito alto - recomenda recusa ou contraproposta com franquia maior")
    elif score >= 55:
        return ("CONTRAPROPOSTA", "#F5A623",
                "Risco elevado - sugerir aumento de premio em 30-50% ou franquia maior")
    elif score >= 35:
        return ("APROVAR_COM_AJUSTE", "#FFD93D",
                "Risco moderado - aprovar com ajuste de premio em ate 20%")
    else:
        return ("APROVAR", "#22D48A",
                "Risco baixo - aprovar nas condicoes padrao")


# ==========================================================================
# RENDER PRINCIPAL
# ==========================================================================

def render():
    from app import check_permissao, gerar_trilha_auditoria, _header, _contrato_box

    if not check_permissao("view_dashboard"):
        return

    _contrato_box(
        "pagina_us07_subscricao_xai",
        ["ACESSO_US07_SUBSCRICAO", "ANALISE_PROPOSTA",
         "DECISAO_SUBSCRICAO", "CONSULTA_SHAP_XAI"]
    )
    _header(
        "Subscricao com XAI",
        "Rafael",
        "US07 · Subscritor · SHAP · Decisao Auditada · Calculo de Premio"
    )
    gerar_trilha_auditoria("ACESSO_US07_SUBSCRICAO", "pagina=us07_subscricao_xai")

    # Status do arquivo real (se Rafael/Guilherme entregarem o XGBoost)
    status_dados("modelo_xgboost",
                 label="Modelo XGBoost com SHAP real (aguardando)")

    # Carrega propostas (real ou mock)
    df, fonte = carregar_dataset(
        "data/propostas_subscricao.csv",
        _propostas_mock,
    )

    # ── KPIs de carteira ────────────────────────────────────────────────
    n_pendentes = len(df)
    n_recusar   = sum(1 for _, r in df.iterrows()
                      if _categoria_subscricao(r["Score_Risco"])[0] == "RECUSAR")
    n_aprovar   = sum(1 for _, r in df.iterrows()
                      if _categoria_subscricao(r["Score_Risco"])[0] == "APROVAR")
    valor_total = df["Valor_Segurado"].sum()
    premio_total = df["Premio_Sugerido"].sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Propostas Pendentes", n_pendentes)
    c2.metric("Recusa Sugerida", n_recusar, delta_color="inverse",
              delta=f"+{n_recusar}" if n_recusar else "0")
    c3.metric("Aprovacao Direta", n_aprovar)
    c4.metric("Valor em Risco", f"R$ {valor_total/1e6:.1f}M")
    c5.metric("Premio Esperado", f"R$ {premio_total/1e3:.0f}K")

    # ── TABS ──
    tab1, tab2, tab3, tab4 = st.tabs([
        "Fila de Subscricao",
        "Analise XAI Detalhada",
        "Calculo de Premio",
        "Comparativo da Carteira",
    ])

    # ── TAB 1: FILA DE SUBSCRICAO ───────────────────────────────────────
    with tab1:
        st.markdown("##### Propostas aguardando decisao - ordenadas por urgencia")
        st.caption(
            "Score alto + dias aguardando = topo da fila. "
            "Sistema sugere acao baseada no modelo XGBoost."
        )

        df_fila = df.copy()
        df_fila["urgencia"] = (
            df_fila["Score_Risco"] * 0.6 + df_fila["Dias_Aguardando"] * 4
        )
        df_fila = df_fila.sort_values("urgencia", ascending=False)

        for _, row in df_fila.head(10).iterrows():
            cat, cor, msg = _categoria_subscricao(row["Score_Risco"])
            ajuste_pct = round((row["Premio_Sugerido"] - row["Premio_Base"]) /
                               row["Premio_Base"] * 100, 1)
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid {cor}33;
                        border-left:3px solid {cor};border-radius:10px;
                        padding:14px 18px;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;
                            align-items:flex-start;gap:1rem;">
                    <div style="flex:1;">
                        <div style="display:flex;gap:10px;align-items:center;
                                    margin-bottom:6px;flex-wrap:wrap;">
                            <span style="font-size:0.65rem;color:{cor};
                                         background:{cor}20;padding:3px 10px;
                                         border-radius:5px;font-weight:700;">
                                {cat.replace('_', ' ')}</span>
                            <span style="font-weight:700;color:#EEF0F8;
                                         font-size:0.95rem;">{row['ID']}</span>
                            <span style="font-size:0.78rem;color:#8B8FA8;">
                                {row['Cliente']}</span>
                        </div>
                        <div style="font-size:0.78rem;color:#8B8FA8;
                                    line-height:1.6;">
                            {row['Equipamento']} · {row['Regiao']} ·
                            valor R$ {row['Valor_Segurado']/1e3:.0f}K ·
                            idade {row['Idade_Equip']}a ·
                            {row['Hist_Sinistros']} sinistros previos<br>
                            <span style="color:#4A4D62;">
                                Aguardando ha {row['Dias_Aguardando']} dias
                            </span>
                        </div>
                        <div style="font-size:0.75rem;color:{cor};margin-top:6px;
                                    line-height:1.5;">{msg}</div>
                    </div>
                    <div style="text-align:right;min-width:140px;">
                        <div style="font-size:1.6rem;font-weight:800;color:{cor};
                                    line-height:1;">{row['Score_Risco']:.0f}</div>
                        <div style="font-size:0.65rem;color:#8B8FA8;
                                    margin-top:2px;">SCORE / 100</div>
                        <div style="margin-top:8px;padding-top:8px;
                                    border-top:1px solid rgba(255,255,255,0.07);
                                    font-size:0.72rem;color:#8B8FA8;">
                            Premio: <strong style="color:#EEF0F8;">
                                R$ {row['Premio_Sugerido']/1e3:.1f}K</strong><br>
                            Ajuste: <strong style="color:{cor};">
                                {ajuste_pct:+.1f}%</strong>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── TAB 2: ANALISE XAI DETALHADA ────────────────────────────────────
    with tab2:
        st.markdown("##### Selecione uma proposta para analise XAI completa")

        col_sel, col_acao = st.columns([2, 1])
        with col_sel:
            prop_id = st.selectbox(
                "Proposta",
                df["ID"].tolist(),
                format_func=lambda x: f"{x} - {df[df['ID']==x]['Cliente'].iloc[0]}",
                key="us07_prop",
            )

        prop = df[df["ID"] == prop_id].iloc[0]
        cat, cor, msg = _categoria_subscricao(prop["Score_Risco"])
        contribs = _shap_proposta(prop)

        # Card grande da proposta
        col_a, col_b = st.columns([1, 2])
        with col_a:
            st.markdown(f"""
            <div style="background:#131520;border:1px solid {cor}44;
                        border-radius:14px;padding:1.5rem;text-align:center;">
                <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                            letter-spacing:0.1em;margin-bottom:8px;">
                    Score de Risco</div>
                <div style="font-size:3.5rem;font-weight:800;color:{cor};line-height:1;">
                    {prop['Score_Risco']:.0f}</div>
                <div style="font-size:0.85rem;color:#8B8FA8;margin-top:4px;">
                    / 100</div>
                <div style="margin-top:14px;padding:6px 14px;background:{cor}18;
                            border:1px solid {cor};border-radius:6px;
                            display:inline-block;color:{cor};
                            font-weight:700;font-size:0.8rem;">
                    {cat.replace('_', ' ')}</div>
                <div style="margin-top:1rem;padding-top:1rem;
                            border-top:1px solid rgba(255,255,255,0.07);
                            font-size:0.78rem;color:#8B8FA8;
                            text-align:left;line-height:1.7;">
                    <div><strong style="color:#EEF0F8;">{prop['Cliente']}</strong></div>
                    <div>{prop['Equipamento']} · {prop['Regiao']}</div>
                    <div>Valor: R$ {prop['Valor_Segurado']/1e3:.0f}K</div>
                    <div>Premio sugerido: R$ {prop['Premio_Sugerido']/1e3:.1f}K</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_b:
            st.markdown("##### Decomposicao SHAP - Contribuicao de cada fator")

            # Ordena por impacto
            for fator, valor in sorted(contribs.items(), key=lambda x: -x[1]):
                pct = min(valor / max(prop["Score_Risco"], 1) * 100, 100)
                cor_b = ("#FF4D6A" if valor > 12 else
                         "#F5A623" if valor > 6 else
                         "#5B7FFF" if "Base" in fator else
                         "#22D48A")
                st.markdown(f"""
                <div style="margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;
                                font-size:0.85rem;margin-bottom:4px;">
                        <span style="color:#EEF0F8;">{fator}</span>
                        <span style="color:{cor_b};font-weight:700;">
                            +{valor:.1f}</span>
                    </div>
                    <div style="background:#07080C;height:6px;border-radius:3px;">
                        <div style="background:{cor_b};width:{pct}%;height:100%;
                                    border-radius:3px;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # Painel de decisao
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Tomar decisao de subscricao")

        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        with col_d1:
            if st.button("Aprovar", type="primary", use_container_width=True,
                         key=f"us07_aprov_{prop_id}"):
                gerar_trilha_auditoria(
                    "DECISAO_SUBSCRICAO",
                    f"prop={prop_id} acao=APROVAR score={prop['Score_Risco']} "
                    f"premio={prop['Premio_Sugerido']:.0f}"
                )
                st.success(f"Proposta {prop_id} aprovada e auditada via SHA-256.")

        with col_d2:
            if st.button("Contraproposta", use_container_width=True,
                         key=f"us07_contra_{prop_id}"):
                gerar_trilha_auditoria(
                    "DECISAO_SUBSCRICAO",
                    f"prop={prop_id} acao=CONTRAPROPOSTA score={prop['Score_Risco']}"
                )
                st.info(f"Contraproposta gerada para {prop_id}.")

        with col_d3:
            if st.button("Recusar", use_container_width=True,
                         key=f"us07_rec_{prop_id}"):
                gerar_trilha_auditoria(
                    "DECISAO_SUBSCRICAO",
                    f"prop={prop_id} acao=RECUSAR score={prop['Score_Risco']} "
                    f"motivo=score_alto"
                )
                st.error(f"Proposta {prop_id} recusada e auditada.")

        with col_d4:
            if st.button("Pedir mais info", use_container_width=True,
                         key=f"us07_info_{prop_id}"):
                gerar_trilha_auditoria(
                    "DECISAO_SUBSCRICAO",
                    f"prop={prop_id} acao=SOLICITAR_INFO"
                )
                st.warning(f"Solicitacao enviada ao corretor de {prop_id}.")

    # ── TAB 3: CALCULO DE PREMIO ────────────────────────────────────────
    with tab3:
        st.markdown("##### Simulador de premio ajustado pelo risco")
        st.caption(
            "Premio = Valor x Taxa Base x (1 + Score/100). "
            "Subscritor pode ajustar manualmente para casos especiais."
        )

        col_sim1, col_sim2 = st.columns(2)
        with col_sim1:
            sim_valor = st.number_input(
                "Valor segurado (R$)", 100_000, 5_000_000, 800_000,
                step=50_000, key="us07_sim_val"
            )
            sim_score = st.slider(
                "Score de risco", 0.0, 100.0, 55.0, step=0.5,
                key="us07_sim_score"
            )
            sim_taxa = st.slider(
                "Taxa base (%)", 1.0, 8.0, 4.0, step=0.5,
                key="us07_sim_taxa"
            )
            sim_franquia = st.selectbox(
                "Franquia",
                ["5% (padrao)", "10% (risco baixo)", "15% (risco medio)",
                 "20% (risco alto)"],
                key="us07_sim_franq"
            )

        with col_sim2:
            premio_base = sim_valor * (sim_taxa / 100)
            ajuste = (sim_score - 50) / 100
            premio_final = premio_base * (1 + ajuste)
            cat, cor, _ = _categoria_subscricao(sim_score)

            st.markdown(f"""
            <div style="background:#131520;border:1px solid {cor}40;
                        border-radius:12px;padding:1.5rem;">
                <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                            letter-spacing:0.1em;margin-bottom:8px;">
                    Premio Anual Calculado</div>
                <div style="font-size:2.5rem;font-weight:800;color:{cor};
                            line-height:1;">
                    R$ {premio_final/1e3:.1f}K</div>
                <div style="margin-top:1rem;padding-top:1rem;
                            border-top:1px solid rgba(255,255,255,0.07);
                            font-size:0.85rem;color:#EEF0F8;line-height:2;">
                    Premio base: <strong>R$ {premio_base/1e3:.1f}K</strong><br>
                    Ajuste por score: <strong style="color:{cor};">
                        {ajuste*100:+.1f}%</strong><br>
                    Franquia: <strong>{sim_franquia}</strong><br>
                    Premio mensal: <strong>R$ {premio_final/12/1e3:.2f}K</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)

        if st.button("Salvar simulacao", key="us07_save_sim"):
            gerar_trilha_auditoria(
                "ANALISE_PROPOSTA",
                f"valor={sim_valor} score={sim_score} premio={premio_final:.0f}"
            )
            st.success("Simulacao registrada na trilha de auditoria.")

    # ── TAB 4: COMPARATIVO DA CARTEIRA ──────────────────────────────────
    with tab4:
        st.markdown("##### Como esta proposta se compara ao perfil medio")

        if PLOTLY_OK:
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                fig1 = px.histogram(
                    df, x="Score_Risco", nbins=15,
                    title="Distribuicao de score nas propostas pendentes",
                    template="plotly_dark",
                    color_discrete_sequence=["#5B7FFF"],
                )
                fig1.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
                                   font=dict(color="#EEF0F8"), height=320)
                st.plotly_chart(fig1, use_container_width=True)

            with col_v2:
                fig2 = px.scatter(
                    df, x="Valor_Segurado", y="Score_Risco",
                    color="Equipamento", size="Hist_Sinistros",
                    title="Valor vs Risco vs Sinistros",
                    template="plotly_dark",
                )
                fig2.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
                                   font=dict(color="#EEF0F8"), height=320)
                st.plotly_chart(fig2, use_container_width=True)

            # Score por regiao
            score_reg = df.groupby("Regiao").agg({
                "Score_Risco": "mean",
                "Valor_Segurado": "sum",
            }).reset_index()
            score_reg["Valor_Segurado"] = score_reg["Valor_Segurado"] / 1e6

            fig3 = px.bar(
                score_reg, x="Regiao", y="Score_Risco",
                title="Risco medio por regiao (carteira atual)",
                color="Score_Risco",
                color_continuous_scale="RdYlGn_r",
                template="plotly_dark",
            )
            fig3.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
                               font=dict(color="#EEF0F8"), height=320)
            st.plotly_chart(fig3, use_container_width=True)

        st.markdown("##### Estatisticas da carteira")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Score medio",     round(df["Score_Risco"].mean(), 1))
        c2.metric("Score mediano",   round(df["Score_Risco"].median(), 1))
        c3.metric("Premio total",    f"R$ {df['Premio_Sugerido'].sum()/1e6:.2f}M")
        c4.metric("Sinistralidade",  f"{df['Hist_Sinistros'].mean():.2f}/apolice")

    # Footer
    st.markdown("---")
    st.markdown(f"""
    <div style="background:rgba(91,127,255,0.04);
                border:1px solid rgba(91,127,255,0.2);
                border-left:3px solid #5B7FFF;border-radius:10px;
                padding:12px 18px;font-size:0.78rem;color:#8B8FA8;line-height:1.7;">
        <strong style="color:#EEF0F8;">Status de integracao US07:</strong><br>
        <span style="color:#22D48A;">x</span> Pagina criada e funcional ·
        <span style="color:#22D48A;">x</span> Decomposicao SHAP-like ·
        <span style="color:#22D48A;">x</span> Decisao auditada via SHA-256 ·
        <span style="color:#22D48A;">x</span> Calculo de premio dinamico ·
        <span style="color:#F5A623;">~</span> Aguardando XGBoost real (Guilherme/Rafael)
    </div>
    """, unsafe_allow_html=True)
