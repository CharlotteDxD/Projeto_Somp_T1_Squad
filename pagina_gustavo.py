"""
pagina_gustavo.py
=================
Modulo Cloud AWS + Pipeline de IA — Gustavo (US05)

Placeholder funcional completo.
Versao final: chamada real a API Flask na EC2 t2.micro.
"""
import json
import time
import streamlit as st
import numpy as np
from datetime import datetime, timezone
from core_audit import gerar_trilha_auditoria

# URL da API Flask que o Gustavo vai expor na EC2
# TODO Gustavo: trocar pelo IP publico da EC2 depois do deploy
EC2_API_URL = "http://EC2_PUBLIC_IP:5000/score"


def _score_mock(inclin: float, umidade: float, temp: float, idade: int) -> float:
    """Calculo de score local (fallback quando EC2 esta offline)."""
    return round(min(
        min(inclin, 40) / 40 * 40
        + min(umidade, 100) / 100 * 20
        + max(0, temp - 90) / 40 * 25
        + min(idade, 20) / 20 * 15,
        100,
    ), 1)


def render():
    """Pagina Cloud + Treino de IA + Gestor de Frota."""
    st.markdown("""
    <div style="border-left:3px solid #FF4D6A;padding:6px 0 6px 16px;margin-bottom:1.5rem;">
        <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                    letter-spacing:0.1em;margin-bottom:4px;">Modulo de Gustavo</div>
        <div style="font-size:1.5rem;font-weight:700;color:#EEF0F8;">☁️ Cloud & IA</div>
        <div style="font-size:0.9rem;color:#8B8FA8;margin-top:4px;">
            AWS EC2 · Flask API · XGBoost · LSTM · Gestor de Frota
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info("✅ **Placeholder funcional** — Versao final do Gustavo conecta API real na EC2 t2.micro.")

    tab1, tab2, tab3 = st.tabs(["☁️ Infraestrutura AWS", "🧠 Treino de IA", "🔌 API Simulator"])

    # ── Tab 1: AWS ────────────────────────────────────────────────────────
    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### Status dos Recursos AWS")
            recursos = [
                ("EC2 t2.micro",   "Backend Flask (Free Tier)",              "🟢 Online"),
                ("Security Group", "Portas 22 (SSH) e 5000 (Flask) abertas", "🟢 Ativo"),
                ("S3 Data Lake",   "Parquet — telemetria e modelos (.pkl)",   "🟢 Conectado"),
                ("SageMaker",      "Endpoint XGBoost em staging",             "🟡 Staging"),
                ("CloudWatch",     "Logs e metricas de auditoria",            "🟢 Monitorando"),
            ]
            for nome, desc, status in recursos:
                cor_s = "#22D48A" if "🟢" in status else "#F5A623"
                st.markdown(f"""
                <div style="background:#131520;border:1px solid rgba(255,255,255,0.07);
                            border-radius:10px;padding:12px 16px;margin-bottom:8px;
                            display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-weight:600;color:#EEF0F8;font-size:0.88rem;">{nome}</div>
                        <div style="font-size:0.72rem;color:#8B8FA8;margin-top:2px;">{desc}</div>
                    </div>
                    <div style="font-size:0.72rem;color:{cor_s};padding:3px 10px;
                                background:{cor_s}15;border-radius:6px;white-space:nowrap;">
                        {status}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with col2:
            st.markdown("##### Rotas Flask — Entregaveis Cloud Computing")
            rotas = [
                ("GET",  "/",             "Boas-vindas da API"),
                ("GET",  "/health",       '{"status":"ok","version":"15.0"}'),
                ("GET",  "/echo/<texto>", "Echo com timestamp"),
                ("POST", "/score",        "Score de risco 0-100 (JSON)"),
                ("GET",  "/fleet",        "Ranking top-10 equipamentos criticos"),
            ]
            for metodo, rota, desc in rotas:
                cor_m = "#5B7FFF" if metodo == "GET" else "#22D48A"
                st.markdown(f"""
                <div style="background:#131520;border:1px solid rgba(255,255,255,0.07);
                            border-radius:8px;padding:10px 14px;margin-bottom:6px;
                            display:flex;gap:12px;align-items:flex-start;">
                    <span style="font-size:0.65rem;font-weight:700;color:{cor_m};
                                 background:{cor_m}18;padding:2px 7px;border-radius:4px;
                                 margin-top:1px;white-space:nowrap;">{metodo}</span>
                    <div>
                        <code style="font-size:0.8rem;color:#EEF0F8;">{rota}</code>
                        <div style="font-size:0.72rem;color:#8B8FA8;margin-top:2px;">{desc}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.caption(f"Endpoint atual: `{EC2_API_URL}`")

    # ── Tab 2: Treino ─────────────────────────────────────────────────────
    with tab2:
        st.markdown("##### Simulador de Treino na EC2")

        col_sl1, col_sl2 = st.columns(2)
        with col_sl1:
            inclin  = st.slider("Inclinacao Eixo Z (graus)", 0, 45, 10, key="gust_inc")
            umidade = st.slider("Umidade do Solo (%)", 20, 100, 55, key="gust_umi")
        with col_sl2:
            temp    = st.slider("Temperatura do Motor (°C)", 60, 130, 85, key="gust_temp")
            idade   = st.slider("Idade do Equipamento (anos)", 1, 25, 5, key="gust_idade")

        score_calc = _score_mock(inclin, umidade, temp, idade)

        cor_score = "#FF4D6A" if score_calc >= 75 else "#F5A623" if score_calc >= 40 else "#22D48A"
        st.markdown(f"""
        <div style="background:#131520;border:1px solid rgba(255,255,255,0.12);
                    border-radius:12px;padding:1.5rem;text-align:center;margin:1rem 0;">
            <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                        letter-spacing:0.1em;margin-bottom:8px;">Score Calculado (XGBoost Mock)</div>
            <div style="font-size:3rem;font-weight:800;color:{cor_score};">{score_calc}</div>
            <div style="font-size:0.85rem;color:#8B8FA8;margin-top:4px;">/ 100</div>
        </div>
        """, unsafe_allow_html=True)

        modelo = st.selectbox("Modelo a treinar", ["XGBoost", "LSTM (Keras)", "Random Forest"], key="gust_modelo")

        if st.button("🚀 Iniciar Treino na EC2 (simulado)", key="gust_treino"):
            with st.spinner(f"Treinando {modelo} na EC2 t2.micro..."):
                time.sleep(2)
            f1  = round(0.80 + np.random.random() * 0.10, 3)
            roc = round(0.85 + np.random.random() * 0.10, 3)
            st.success(f"✅ {modelo} treinado | F1={f1} | ROC-AUC={roc}")
            gerar_trilha_auditoria("TREINO_IA_MOCK", f"Modelo={modelo} | F1={f1} | ROC-AUC={roc}")

    # ── Tab 3: API Simulator ──────────────────────────────────────────────
    with tab3:
        st.markdown("##### Simulador de Chamada a API `/score`")
        st.caption(f"Endpoint: `{EC2_API_URL}` — Em producao, Gustavo substitui pelo IP real da EC2.")

        exemplo_req = {
            "device_id": "COL-099",
            "features":  {
                "inclinacao_z": inclin,
                "umidade_pct":  umidade,
                "temp_motor":   temp,
                "idade_anos":   idade,
            }
        }
        st.code(json.dumps(exemplo_req, indent=2, ensure_ascii=False), language="json")

        if st.button("⚡ Simular POST /score (com fallback local)", key="gust_api"):
            with st.spinner("Tentando EC2... (timeout 3s)"):
                time.sleep(1)
            # Fallback local — simula API offline
            st.warning("🔁 EC2 indisponivel (placeholder). Usando fallback local.")
            resp = {
                "status":     "fallback_local",
                "device_id":  "COL-099",
                "score":      score_calc,
                "categoria":  "CRITICO" if score_calc >= 75 else "ATENCAO" if score_calc >= 40 else "NORMAL",
                "timestamp":  datetime.now(timezone.utc).isoformat(),
                "source":     "local_mock",
            }
            st.code(json.dumps(resp, indent=2, ensure_ascii=False), language="json")
            gerar_trilha_auditoria("FALLBACK_LOCAL", f"Score={score_calc} | EC2 offline")
            st.success("✅ Fallback ativo — demo roda mesmo sem EC2.")

        st.markdown("""
        > **Entregavel real (Gustavo):**
        > - EC2 t2.micro rodando Flask com IP publico
        > - 3 prints: EC2 console + Security Group + API no browser
        > - PDF relatorio com IP, prints e descricao dos passos
        """)

    st.markdown("---")
    from core_audit import renderizar_trilha
    renderizar_trilha(qtd=5)
