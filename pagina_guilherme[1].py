"""
pagina_guilherme.py
===================
Modulo de Analise de Dados + Anomalias — Guilherme (US06/US08)

STATUS: PLACEHOLDER FUNCIONAL.
Guilherme entrega a versao final ate sexta 01/05 as 20h.

Substituir por: ingestao SUSEP/INMET, EDA com Pandas, Z-Score outliers,
Isolation Forest pra anomalias, 2+ insights escritos.
"""
import streamlit as st
import pandas as pd
import numpy as np

from core_audit import gerar_trilha_auditoria


def render():
    """Pagina de Analise de Dados + Deteccao de Anomalias."""
    st.title("📊 Analise de Dados + Deteccao de Anomalias")
    st.warning(
        "⏳ Aguardando entrega final do Guilherme (deadline: sex 01/05, 20h). "
        "Esta versao e um placeholder funcional pra testar a integracao."
    )

    st.markdown("""
    **Escopo esperado nesta pagina:**
    - Carregamento de CSV (SUSEP sintetico ou base real)
    - Estatisticas descritivas (Pandas: media, mediana, std, distribuicao)
    - Tratamento de outliers via Z-Score
    - Treinamento de **Isolation Forest** (sklearn.ensemble) pra anomalias
    - 3+ visualizacoes (matplotlib/seaborn) e 2+ insights escritos
    - Hooks de auditoria:
      - `gerar_trilha_auditoria("INGESTAO_DADOS", ...)`
      - `gerar_trilha_auditoria("DETECCAO_ANOMALIAS", ...)`
    """)

    # === MOCK PROVISORIO ===
    st.markdown("### 🧪 Mock provisorio")

    if st.button("Carregar dataset SUSEP (mock)", key="guil_btn_load"):
        df = pd.DataFrame({
            "ID_Apolice": [f"AP-{100+i}" for i in range(8)],
            "Equipamento": [
                "Colheitadeira", "Trator", "Pulverizador", "Trator",
                "Colheitadeira", "Pulverizador", "Trator", "Colheitadeira",
            ],
            "Regiao": [
                "Sul", "Centro-Oeste", "Sudeste", "Sul",
                "Centro-Oeste", "Norte", "Sudeste", "Sul",
            ],
            "Sinistro_Anterior": [1, 0, 0, 2, 1, 0, 1, 3],
            "Valor_Risco_BRL": [
                1200000, 450000, 300000, 800000,
                1500000, 320000, 600000, 1700000,
            ],
        })
        st.session_state.guil_df = df
        st.success(f"✅ Dataset carregado: {len(df)} apolices")
        gerar_trilha_auditoria(
            "INGESTAO_DADOS_MOCK", f"Linhas={len(df)} | Fonte=SUSEP_sintetico"
        )

    if "guil_df" in st.session_state:
        df = st.session_state.guil_df
        st.dataframe(df, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Apolices", len(df))
        col2.metric("Risco Total (BRL)", f"R$ {df['Valor_Risco_BRL'].sum():,.0f}")
        col3.metric("Sinistros Anteriores", df["Sinistro_Anterior"].sum())

        if st.button("Detectar Anomalias (Isolation Forest mock)", key="guil_btn_iso"):
            # Mock simples — quem tem 2+ sinistros vira anomalia
            anomalias = df[df["Sinistro_Anterior"] >= 2]
            st.warning(f"⚠️  {len(anomalias)} anomalia(s) detectada(s):")
            st.dataframe(anomalias, use_container_width=True)
            gerar_trilha_auditoria(
                "DETECCAO_ANOMALIAS_MOCK",
                f"Anomalias={len(anomalias)} | Algoritmo=IsolationForest_mock",
            )
            st.success("✅ Trilha de auditoria registrada.")
