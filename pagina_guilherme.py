"""
pagina_guilherme.py
===================
Modulo de Analise de Dados + Anomalias — Guilherme (US06/US08)

Placeholder funcional completo.
Versao final: substituir mock por base real SUSEP + Isolation Forest real.
"""
import streamlit as st
import pandas as pd
import numpy as np
from core_audit import gerar_trilha_auditoria


def _gerar_dataset_mock() -> pd.DataFrame:
    """Extrato simulado com estrutura da base SUSEP rural."""
    np.random.seed(42)
    n = 120
    regioes  = ["Sul", "Centro-Oeste", "Sudeste", "Norte", "Nordeste"]
    tipos    = ["Colheitadeira", "Trator", "Pulverizador", "Plantadeira"]
    sinistros = np.random.choice([0, 1, 2, 3], n, p=[0.55, 0.25, 0.12, 0.08])
    return pd.DataFrame({
        "ID_Apolice":    [f"AP-{1000+i}" for i in range(n)],
        "Equipamento":   np.random.choice(tipos, n),
        "Regiao":        np.random.choice(regioes, n),
        "Idade_Anos":    np.random.randint(1, 20, n),
        "Valor_BRL":     np.random.randint(200_000, 2_000_000, n),
        "Sinistros_Ano": sinistros,
        "Temp_Max_C":    np.round(np.random.uniform(22, 42, n), 1),
        "Umidade_Pct":   np.round(np.random.uniform(30, 95, n), 1),
        "Score_Risco":   np.round(np.clip(sinistros * 25 + np.random.uniform(5, 30, n), 0, 100), 1),
    })


def render():
    """Pagina de Analise de Dados + Deteccao de Anomalias."""
    st.markdown("""
    <div style="border-left:3px solid #F5A623;padding:6px 0 6px 16px;margin-bottom:1.5rem;">
        <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                    letter-spacing:0.1em;margin-bottom:4px;">Modulo de Guilherme</div>
        <div style="font-size:1.5rem;font-weight:700;color:#EEF0F8;">📊 Dados & Estatistica</div>
        <div style="font-size:0.9rem;color:#8B8FA8;margin-top:4px;">
            Base SUSEP · Analise Exploratoria · Z-Score · Isolation Forest
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info("✅ **Placeholder funcional** — Versao final do Guilherme usa base real SUSEP + Isolation Forest sklearn.")

    df = _gerar_dataset_mock()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Dataset SUSEP",
        "📈 Visualizacoes",
        "🔍 Anomalias Z-Score",
        "🤖 Isolation Forest",
    ])

    # ── Tab 1: Dataset ────────────────────────────────────────────────────
    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Apolices", len(df))
        col2.metric("Sinistros Medio/Apolice", round(df["Sinistros_Ano"].mean(), 2))
        col3.metric("Valor Medio (R$)", f"{df['Valor_BRL'].mean()/1e6:.2f}M")
        col4.metric("Score Medio Risco", round(df["Score_Risco"].mean(), 1))

        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(df.head(30), use_container_width=True)
        st.caption("Mock baseado na estrutura real da base SUSEP rural (seguros agricolas).")

        if st.button("📥 Simular Ingestao SUSEP Real", key="guil_ingest"):
            gerar_trilha_auditoria("INGESTAO_DADOS_MOCK", f"Linhas={len(df)} | Fonte=SUSEP_simulado")
            st.success(f"✅ Dataset carregado: {len(df)} apolices | Trilha registrada.")

    # ── Tab 2: Visualizacoes ─────────────────────────────────────────────
    with tab2:
        try:
            import plotly.express as px

            col_a, col_b = st.columns(2)
            with col_a:
                fig1 = px.histogram(
                    df, x="Score_Risco", nbins=20, color="Equipamento",
                    title="Distribuicao de Score por Equipamento",
                    template="plotly_dark",
                )
                fig1.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18")
                st.plotly_chart(fig1, use_container_width=True)

            with col_b:
                media_reg = df.groupby("Regiao")["Score_Risco"].mean().reset_index()
                fig2 = px.bar(
                    media_reg, x="Regiao", y="Score_Risco",
                    title="Score Medio por Regiao",
                    color="Score_Risco", color_continuous_scale="RdYlGn_r",
                    template="plotly_dark",
                )
                fig2.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18")
                st.plotly_chart(fig2, use_container_width=True)

            fig3 = px.scatter(
                df, x="Umidade_Pct", y="Score_Risco",
                color="Equipamento", size="Sinistros_Ano",
                title="Umidade vs Score de Risco (tamanho = sinistros)",
                template="plotly_dark",
            )
            fig3.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18")
            st.plotly_chart(fig3, use_container_width=True)

        except ImportError:
            st.info("Instale plotly: `pip install plotly`")
            st.bar_chart(df.groupby("Regiao")["Score_Risco"].mean())

    # ── Tab 3: Z-Score ────────────────────────────────────────────────────
    with tab3:
        st.markdown("**Z-Score aplicado em `Score_Risco` — outliers com |Z| > 2 sao anomalias.**")

        df_z = df.copy()
        mu, sigma = df_z["Score_Risco"].mean(), df_z["Score_Risco"].std()
        df_z["Z_Score"]  = ((df_z["Score_Risco"] - mu) / sigma).round(3)
        df_z["Anomalia"] = df_z["Z_Score"].abs() > 2

        anomalias = df_z[df_z["Anomalia"]]
        pct = round(100 * len(anomalias) / len(df_z), 1)
        st.info(f"🔍 {len(anomalias)} anomalias em {len(df_z)} registros ({pct}%)")
        st.dataframe(
            anomalias[["ID_Apolice", "Equipamento", "Regiao", "Score_Risco", "Z_Score"]],
            use_container_width=True,
        )

        if len(anomalias) > 0:
            gerar_trilha_auditoria(
                "DETECCAO_ANOMALIAS_ZSCORE",
                f"Anomalias={len(anomalias)} | Threshold=|Z|>2",
            )

    # ── Tab 4: Isolation Forest ───────────────────────────────────────────
    with tab4:
        st.markdown("**Isolation Forest (sklearn) — deteccao nao-supervisionada de anomalias.**")

        contamination = st.slider(
            "Taxa de Contaminacao Esperada (%)", 5, 30, 10,
            key="guil_contam",
        )

        if st.button("🤖 Rodar Isolation Forest", key="guil_iso"):
            from sklearn.ensemble import IsolationForest

            features = df[["Score_Risco", "Sinistros_Ano", "Umidade_Pct", "Idade_Anos"]].values

            iso = IsolationForest(
                contamination=contamination / 100,
                random_state=42,
            )
            labels = iso.fit_predict(features)

            df_iso = df.copy()
            df_iso["Anomalia_IF"] = labels == -1

            n_anomalias = df_iso["Anomalia_IF"].sum()
            st.success(f"✅ Isolation Forest concluido: {n_anomalias} anomalias detectadas.")
            st.dataframe(
                df_iso[df_iso["Anomalia_IF"]][["ID_Apolice", "Equipamento", "Regiao", "Score_Risco", "Sinistros_Ano"]],
                use_container_width=True,
            )

            gerar_trilha_auditoria(
                "DETECCAO_ANOMALIAS_IF",
                f"Anomalias={n_anomalias} | Contaminacao={contamination}% | Algoritmo=IsolationForest",
            )

        st.caption("Parametros: n_estimators=100, max_samples=auto, random_state=42.")

    st.markdown("---")
    from core_audit import renderizar_trilha
    renderizar_trilha(qtd=5)
