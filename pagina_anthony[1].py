"""
pagina_anthony.py
=================
Modulo de Telemetria IoT — Anthony (US04)

STATUS: PLACEHOLDER FUNCIONAL.
Anthony entrega a versao final ate sexta 01/05 as 20h.

Substituir o conteudo de render() pela versao com Wokwi/ESP32 + leitura de CSV.
"""
import streamlit as st
from core_audit import gerar_trilha_auditoria


def render():
    """Pagina de Telemetria IoT do Operador de Equipamento."""
    st.title("📡 Telemetria IoT — ESP32 Edge")
    st.warning(
        "⏳ Aguardando entrega final do Anthony (deadline: sex 01/05, 20h). "
        "Esta versao e um placeholder funcional pra testar a integracao."
    )

    st.markdown("""
    **Escopo esperado nesta pagina:**
    - Inputs de telemetria: inclinacao (eixo Z), umidade do solo, idade do equipamento
    - Calculo de score local (edge computing simulado)
    - Visualizacao de status: 🟢 Verde / 🟡 Amarelo / 🔴 Vermelho
    - Geracao de CSV estruturado (ID equip, contexto operacional, sensores)
    - Hooks de auditoria: `gerar_trilha_auditoria("TELEMETRIA_EDGE", ...)`
    """)

    # === MOCK PROVISORIO (sera substituido pelo codigo real do Anthony) ===
    st.markdown("### 🧪 Mock provisorio")

    col1, col2, col3 = st.columns(3)
    inclinacao = col1.slider("Inclinacao Z (graus)", 0.0, 40.0, 15.0, key="anthony_inc")
    umidade = col2.slider("Umidade solo (%)", 0.0, 100.0, 50.0, key="anthony_umi")
    idade = col3.slider("Idade equip (anos)", 0, 20, 5, key="anthony_idade")

    contexto = st.radio(
        "Contexto operacional",
        ["Campo", "Transporte", "Area Critica"],
        horizontal=True,
        key="anthony_ctx",
    )

    if st.button("Calcular Score Edge", key="anthony_btn_calc"):
        score = (
            (min(inclinacao, 40) / 40) * 50
            + (min(umidade, 100) / 100) * 30
            + (min(idade, 20) / 20) * 20
        )
        score = round(min(score, 100), 2)

        st.metric("Score de Risco (Edge)", f"{score}/100")

        if score < 40:
            st.success("🟢 Operacao Segura")
        elif score < 75:
            st.warning("🟡 Atencao — reduzir velocidade")
        else:
            st.error("🔴 ALERTA CRITICO — parada obrigatoria")

        gerar_trilha_auditoria(
            "TELEMETRIA_EDGE_MOCK",
            f"Inc={inclinacao} | Umi={umidade} | Idade={idade} | "
            f"Ctx={contexto} | Score={score}",
        )
        st.success("✅ Trilha de auditoria registrada. Veja no rodape.")
