"""
pagina_anthony.py
=================
Modulo de Telemetria IoT — Anthony (US04)

Placeholder funcional completo.
Simula leitura do ESP32 + MPU-6050 + DHT22 com score edge computing.
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from core_audit import gerar_trilha_auditoria


def render():
    """Pagina de Telemetria IoT do Operador de Equipamento."""
    st.markdown("""
    <div style="border-left:3px solid #A855F7;padding:6px 0 6px 16px;margin-bottom:1.5rem;">
        <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                    letter-spacing:0.1em;margin-bottom:4px;">Modulo de Anthony</div>
        <div style="font-size:1.5rem;font-weight:700;color:#EEF0F8;">📡 IoT & Telemetria</div>
        <div style="font-size:0.9rem;color:#8B8FA8;margin-top:4px;">
            ESP32 · MPU-6050 · DHT22 · Edge Computing · Wokwi
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info("✅ **Placeholder funcional** — Versão final do Anthony integra CSV real do Wokwi/ESP32.")

    tab1, tab2, tab3 = st.tabs(["📡 Leitura em Tempo Real", "🗃️ Historico", "📋 Contexto Operacional"])

    # ── Tab 1: Leitura ──────────────────────────────────────────────────
    with tab1:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("##### Parametros do Sensor ESP32")

            device_id = st.selectbox(
                "ID do Equipamento",
                ["TRAT-047", "COLH-012", "TRAT-099", "COLH-088", "PUL-033"],
                key="anthony_device",
            )
            contexto = st.selectbox(
                "Contexto Operacional",
                ["Campo", "Transporte em Estrada", "Area Critica"],
                key="anthony_ctx",
            )
            inc_x = st.number_input(
                "Inclinacao Eixo X (graus)", -45.0, 45.0, 5.0, step=0.5,
                key="anthony_ix",
            )
            inc_z = st.number_input(
                "Inclinacao Eixo Z (graus)", -45.0, 45.0, 12.0, step=0.5,
                key="anthony_iz",
            )
            umidade = st.number_input(
                "Umidade do Solo (%)", 0.0, 100.0, 58.0, step=1.0,
                key="anthony_umi",
            )
            temp = st.number_input(
                "Temperatura Motor (°C)", 40.0, 140.0, 85.0, step=1.0,
                key="anthony_temp",
            )

        with col2:
            st.markdown("##### Serial Monitor — ESP32")

            # Score edge computing
            multiplicador = 1.4 if contexto == "Area Critica" else 1.0
            score_edge = round(min(
                abs(inc_z) / 45 * 50 + umidade / 100 * 30 + max(0, temp - 90) / 50 * 20,
                100,
            ) * multiplicador, 1)
            score_edge = min(score_edge, 100)

            status_str = (
                "ALERTA CRITICO — PARADA OBRIGATORIA"
                if score_edge >= 75
                else "ATENCAO — reduzir velocidade"
                if score_edge >= 40
                else "OPERACAO SEGURA"
            )
            status_emoji = "⚠️" if score_edge >= 75 else "🟡" if score_edge >= 40 else "🟢"

            serial_output = f"""> SOMPO PREDICT v15 · ESP32 · Anthony
> ─────────────────────────────────────
> Device  : {device_id}
> Contexto: {contexto}
> ─────────────────────────────────────
> [MPU-6050] Eixo X   : {inc_x:+.1f}°
> [MPU-6050] Eixo Z   : {inc_z:+.1f}°
> [DHT22]   Umidade   : {umidade:.1f} %
> [NTC]     Temp Motor: {temp:.0f} °C
> ─────────────────────────────────────
> [EDGE AI] Score     : {score_edge} / 100
> [STATUS]  {status_emoji} {status_str}
> [MQTT]    Enviando para AWS IoT Core...
"""
            st.code(serial_output, language="text")

            if st.button("📤 Enviar Telemetria para Cloud", use_container_width=True, key="anthony_send"):
                with st.spinner("Transmitindo via MQTT / TLS 1.3..."):
                    import time
                    time.sleep(0.8)

                entrada = {
                    "timestamp":  datetime.now().strftime("%H:%M:%S"),
                    "device_id":  device_id,
                    "contexto":   contexto,
                    "inc_x":      inc_x,
                    "inc_z":      inc_z,
                    "umidade":    umidade,
                    "temp_motor": temp,
                    "score_edge": score_edge,
                    "status":     "CRITICO" if score_edge >= 75 else "ATENCAO" if score_edge >= 40 else "NORMAL",
                }

                if "anthony_historico" not in st.session_state:
                    st.session_state.anthony_historico = []
                st.session_state.anthony_historico.append(entrada)

                gerar_trilha_auditoria(
                    "TELEMETRIA_ENVIADA",
                    f"Device:{device_id} | Score:{score_edge} | Ctx:{contexto}",
                )
                st.success(f"✅ Payload enviado! Latencia simulada: 847ms")

    # ── Tab 2: Historico ─────────────────────────────────────────────────
    with tab2:
        historico = st.session_state.get("anthony_historico", [])
        if not historico:
            st.info("Nenhuma leitura enviada ainda. Use a aba '📡 Leitura em Tempo Real'.")
        else:
            df_hist = pd.DataFrame(historico)
            st.dataframe(df_hist, use_container_width=True)
            st.metric("Total de leituras", len(df_hist))
            st.metric(
                "Score maximo registrado",
                df_hist["score_edge"].max(),
                delta="risco mais alto da sessao",
            )

    # ── Tab 3: Contexto ───────────────────────────────────────────────────
    with tab3:
        st.markdown("##### Logica de Contexto Operacional (ESP32)")
        contextos = [
            ("🌾 Campo",              "Operacao normal de colheita ou plantio. Limites: Inc < 15°, Vel < 10km/h.",       "#22D48A"),
            ("🛣️ Transporte Estrada", "Deslocamento entre fazendas. Limites: Vel < 30km/h, sem operacao de implemento.", "#F5A623"),
            ("⚠️ Area Critica",       "Proximo a rios, encostas ou areas alagadas. Multiplicador de risco: 1.4x.",        "#FF4D6A"),
        ]
        for nome, desc, cor in contextos:
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid {cor}33;border-left:3px solid {cor};
                        border-radius:10px;padding:12px 18px;margin-bottom:8px;">
                <div style="font-weight:700;color:{cor};margin-bottom:4px;">{nome}</div>
                <div style="font-size:0.82rem;color:#8B8FA8;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("""
        > **Entregavel real (Anthony):** CSV de 100+ linhas gerado pelo Wokwi com colunas:
        > `ID_Equip | Contexto | Eixo_X | Eixo_Z | Umidade | Temp | Score | Status | Timestamp`
        """)

    renderizar_rodape()


def renderizar_rodape():
    st.markdown("---")
    from core_audit import renderizar_trilha
    renderizar_trilha(qtd=5)
