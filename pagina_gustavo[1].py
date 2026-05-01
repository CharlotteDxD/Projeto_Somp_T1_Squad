"""
pagina_gustavo.py
=================
Modulo Cloud AWS + Pipeline de IA — Gustavo (US05)

STATUS: PLACEHOLDER FUNCIONAL.
Gustavo entrega a versao final ate sexta 01/05 as 20h.

Substituir por: chamada real a API Flask na EC2 t2.micro,
simulacao de treino XGBoost/LSTM, fallback se API offline.
"""
import streamlit as st
import time
import numpy as np

from core_audit import gerar_trilha_auditoria


# URL da API Flask que o Gustavo vai expor na EC2
URL_EC2_API = "http://EC2_PUBLIC_IP:5000/score"  # TODO: Gustavo preenche


def render():
    """Pagina Cloud + Treino de IA."""
    st.title("☁️  Cloud AWS + Pipeline de IA")
    st.warning(
        "⏳ Aguardando entrega final do Gustavo (deadline: sex 01/05, 20h). "
        "Esta versao e um placeholder funcional pra testar a integracao."
    )

    st.markdown("""
    **Escopo esperado nesta pagina:**
    - URL publica da API Flask rodando na EC2 t2.micro (free tier)
    - Endpoint `/score` recebendo JSON e devolvendo `{"score": float, "categoria": str}`
    - Print da AWS Console (EC2 + Security Group)
    - Simulacao de treino XGBoost / Rede Neural LSTM
    - **Fallback obrigatorio**: se API offline (timeout 3s), usar mock local
    - Hooks de auditoria:
      - `gerar_trilha_auditoria("TREINO_IA", ...)`
      - `gerar_trilha_auditoria("INFERENCIA_CLOUD", ...)`
      - `gerar_trilha_auditoria("FALLBACK_LOCAL", ...)` — quando EC2 offline
    """)

    # === MOCK PROVISORIO ===
    st.markdown("### 🧪 Mock provisorio")

    tab1, tab2 = st.tabs(["Treinar Modelo", "Inferencia via API"])

    with tab1:
        modelo = st.selectbox(
            "Modelo a treinar",
            ["XGBoost", "LSTM (Keras)", "Random Forest"],
            key="gust_modelo",
        )
        if st.button("Iniciar Treino na EC2 (mock)", key="gust_btn_treino"):
            with st.spinner(f"Treinando {modelo} na EC2 t2.micro..."):
                time.sleep(2)
            f1 = round(0.80 + np.random.random() * 0.10, 3)
            roc = round(0.85 + np.random.random() * 0.10, 3)
            st.success(f"✅ {modelo} treinado | F1={f1} | ROC-AUC={roc}")
            gerar_trilha_auditoria(
                "TREINO_IA_MOCK", f"Modelo={modelo} | F1={f1} | ROC-AUC={roc}"
            )

    with tab2:
        st.markdown("**Endpoint atual:** `" + URL_EC2_API + "`")
        st.caption("Quando Gustavo entregar, esta tela vai chamar a API real.")

        if st.button("Chamar API /score (mock com fallback)", key="gust_btn_api"):
            # Simula timeout + fallback
            st.info("Tentando chamar EC2... (mock)")
            time.sleep(1)
            score_mock = round(40 + np.random.random() * 50, 1)
            st.warning("API EC2 indisponivel (placeholder). Usando fallback local.")
            st.metric("Score retornado (fallback)", f"{score_mock}/100")
            gerar_trilha_auditoria(
                "FALLBACK_LOCAL", f"API offline | Score mock={score_mock}"
            )
