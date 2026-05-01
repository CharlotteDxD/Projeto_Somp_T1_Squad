"""
dashboard_cliente.py
====================
Painel do Segurado (US03) — visao simplificada para o cliente final.

Refatorado pra ser chamado como modulo (def render) a partir do app.py.
Owner: Charles
"""
import streamlit as st
from core_audit import gerar_trilha_auditoria


def render():
    """Renderiza o painel simplificado do segurado (cliente final Sompo)."""
    st.title("🚜 Sompo Predict — Painel do Segurado")
    st.markdown(
        "Bem-vindo ao seu assistente de prevencao de riscos agricolas em tempo real."
    )

    st.subheader("📡 Telemetria Edge IoT (Ativo: COL-099)")

    col1, col2 = st.columns(2)
    inclinacao = col1.slider(
        "Inclinacao Lateral (graus - eixo Z)",
        0.0, 40.0, 10.0,
        key="cliente_inc",
    )
    umidade = col2.slider(
        "Umidade do Solo (%) — Open-Meteo/INMET",
        0.0, 100.0, 50.0,
        key="cliente_umi",
    )

    # Score com cap em 100 (logica simplificada — em prod vem do XGBoost na EC2)
    score_risco = min((inclinacao / 30) * 50 + (umidade / 100) * 50, 100)

    st.divider()
    st.subheader("🚦 Status Operacional")

    if score_risco <= 50:
        st.success(f"Score de Risco: {score_risco:.1f}/100 — ✅ OPERACAO SEGURA")
        st.info("Acao: prossiga com a colheita normalmente.")
    elif score_risco <= 75:
        st.warning(f"Score de Risco: {score_risco:.1f}/100 — ⚠️  ATENCAO")
        st.info("Acao: reduza a velocidade. Terreno em degradacao.")
    else:
        st.error(f"Score de Risco: {score_risco:.1f}/100 — 🛑 ALERTA CRITICO")
        st.error(
            "ACAO IMEDIATA: risco iminente de tombamento — interrompa a operacao."
        )

    st.divider()
    st.subheader("📈 Valor Gerado: Mitigacao de Sinistros (mes atual)")
    st.metric("Sinistros Potenciais Evitados", "3", delta="+1 vs mes anterior")
    st.caption(
        "A inteligencia preditiva da Sompo protegeu sua frota de 3 eventos "
        "criticos este mes, garantindo a produtividade da safra."
    )

    # Auditoria registra cada visualizacao (LGPD: rastreabilidade de acesso a dados)
    gerar_trilha_auditoria(
        "VISUALIZACAO_PAINEL_CLIENTE",
        f"Inc={inclinacao} | Umi={umidade} | Score={score_risco:.1f}",
    )
