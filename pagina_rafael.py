"""
pagina_rafael.py
================
Modulo XAI + Ranking de Risco da Frota — Rafael/Gon (US02 + US07)

Placeholder funcional completo.
Versao final: SHAP real com XGBoost treinado na base SUSEP.
"""
import streamlit as st
import pandas as pd
import numpy as np
from core_audit import gerar_trilha_auditoria


def render():
    """Pagina XAI + Ranking da Frota (visao Subscritor Sompo)."""
    st.markdown("""
    <div style="border-left:3px solid #5B7FFF;padding:6px 0 6px 16px;margin-bottom:1.5rem;">
        <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                    letter-spacing:0.1em;margin-bottom:4px;">Modulo de Rafael (Gon)</div>
        <div style="font-size:1.5rem;font-weight:700;color:#EEF0F8;">🎯 XAI & Gestao Agil</div>
        <div style="font-size:0.9rem;color:#8B8FA8;margin-top:4px;">
            SHAP Values · Ranking de Frota · Sprint 1 · ROI Sompo
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info("✅ **Placeholder funcional** — Versao final do Rafael integra SHAP real com XGBoost treinado.")

    tab1, tab2, tab3 = st.tabs(["🎯 Explicabilidade SHAP", "💰 Simulador de ROI", "📋 Sprint 1 Status"])

    # ── Tab 1: SHAP ──────────────────────────────────────────────────────
    with tab1:
        st.markdown("##### Explicacao SHAP do Score de Risco")
        st.info("SHAP (SHapley Additive exPlanations) — explica o peso de cada feature no score final do modelo.")

        # Frota mock
        frota_mock = pd.DataFrame({
            "Ativo":        ["COL-099", "TRT-102", "PUL-045", "COL-051", "TRT-088"],
            "Tipo":         ["Colheitadeira", "Trator", "Pulverizador", "Colheitadeira", "Trator"],
            "Regiao":       ["Sul", "Centro-Oeste", "Sudeste", "Sul", "Norte"],
            "Score_Risco":  [88.5, 45.2, 72.1, 65.0, 31.8],
            "Recomendacao": [
                "🔴 Parada Imediata",
                "🟢 Inspecao Normal",
                "🟡 Reduzir Velocidade",
                "🟡 Manutencao Preventiva",
                "🟢 Operacao Segura",
            ],
        }).sort_values("Score_Risco", ascending=False)

        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("##### Ranking de Risco da Frota")
            st.dataframe(frota_mock, use_container_width=True, hide_index=True)

            ativo_sel = st.selectbox(
                "Selecione ativo para ver SHAP",
                frota_mock["Ativo"].tolist(),
                key="rafa_sel",
            )

        with col2:
            st.markdown("##### Waterfall SHAP — Contribuicao por Feature")

            score_ativo = frota_mock[frota_mock["Ativo"] == ativo_sel]["Score_Risco"].iloc[0]

            # SHAP mock — em producao vira do XGBoost real
            np.random.seed(hash(ativo_sel) % 2**31)
            sh_inclin  = round(np.random.uniform(15, 35), 1)
            sh_umidade = round(np.random.uniform(10, 25), 1)
            sh_temp    = round(np.random.uniform(5, 20), 1)
            sh_idade   = round(np.random.uniform(3, 15), 1)
            sh_base    = round(score_ativo - sh_inclin - sh_umidade - sh_temp - sh_idade, 1)

            features = [
                ("📊 Base (E[f(x)])",    sh_base,    "#5B7FFF"),
                ("📐 Inclinacao Eixo Z", sh_inclin,  "#FF4D6A"),
                ("💧 Umidade Solo",      sh_umidade, "#FF4D6A"),
                ("🌡️ Temperatura Motor", sh_temp,    "#F5A623"),
                ("🔧 Idade Equipamento", sh_idade,   "#F5A623"),
            ]

            for label, val, cor in features:
                direcao = "▲" if val > 0 else "▼"
                pct_barra = min(abs(val) / max(score_ativo, 1) * 100, 100)
                st.markdown(f"""
                <div style="margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;
                                font-size:0.82rem;color:#EEF0F8;margin-bottom:3px;">
                        <span>{label}</span>
                        <span style="color:{cor};font-weight:700;">{direcao} {abs(val):.1f}</span>
                    </div>
                    <div style="background:#07080C;height:5px;border-radius:3px;">
                        <div style="background:{cor};width:{pct_barra}%;height:100%;border-radius:3px;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            top = sorted(features[1:], key=lambda x: abs(x[1]), reverse=True)[0]
            st.markdown(f"""
            <div style="background:rgba(91,127,255,0.08);border-left:2px solid #5B7FFF;
                        border-radius:6px;padding:12px 16px;margin-top:1rem;">
                <div style="font-size:0.78rem;color:#EEF0F8;line-height:1.7;">
                    ✦ O ativo <strong>{ativo_sel}</strong> tem score de
                    <strong style="color:#FF4D6A;">{score_ativo}/100</strong>.<br>
                    Principal fator: <strong>{top[0]}</strong>
                    contribuindo com <strong style="color:{top[2]};">+{top[1]:.1f} pontos</strong>.
                </div>
            </div>
            """, unsafe_allow_html=True)

        if st.button("📊 Registrar Consulta SHAP", key="rafa_audit"):
            gerar_trilha_auditoria(
                "CONSULTA_XAI",
                f"Ativo={ativo_sel} | Score={score_ativo} | Top fator: inclinacao_z (+{sh_inclin})",
            )
            st.success("✅ Trilha de auditoria registrada.")

    # ── Tab 2: ROI ────────────────────────────────────────────────────────
    with tab2:
        st.markdown("##### Simulador de ROI Sompo")

        col_a, col_b = st.columns(2)
        with col_a:
            frota        = st.slider("Frota Monitorada (equipamentos)", 10, 500, 150, key="rafa_frota")
            ef_preditiva = st.slider("Eficiencia Preditiva (%)", 10, 80, 40, key="rafa_ef")
            custo_medio  = st.slider("Custo Medio por Sinistro (R$ mil)", 100, 2000, 450, key="rafa_custo")

        with col_b:
            sinistros_base = frota * 0.15
            evitados       = int(sinistros_base * ef_preditiva / 100)
            economia       = evitados * custo_medio * 1000
            tco            = frota * 2000
            lucro          = economia - tco
            roi_pct        = round(lucro / tco * 100) if tco else 0
            payback        = round(tco / (economia / 12)) if economia > 0 else 0

            st.metric("Sinistros Evitados/ano", evitados)
            st.metric("Economia Bruta", f"R$ {economia/1e6:.2f}M")
            st.metric("TCO Plataforma", f"R$ {tco/1e3:.0f}K")
            st.metric("ROI Estimado", f"{roi_pct}%", delta=f"Payback: {payback} meses")

            st.markdown(f"""
            <div style="background:#131520;border:1px solid rgba(34,212,138,0.3);
                        border-radius:10px;padding:14px 18px;margin-top:1rem;">
                <div style="font-size:0.7rem;color:#8B8FA8;margin-bottom:6px;
                            text-transform:uppercase;letter-spacing:0.08em;">Resumo Executivo</div>
                <div style="font-size:0.85rem;color:#EEF0F8;line-height:1.7;">
                    Com <strong>{frota}</strong> equipamentos monitorados e eficiencia preditiva de
                    <strong>{ef_preditiva}%</strong>, o Sompo Predict evita
                    <strong style="color:#22D48A;">{evitados} sinistros/ano</strong>,
                    gerando economia bruta de
                    <strong style="color:#22D48A;">R$ {economia/1e6:.2f}M</strong>
                    com ROI de <strong style="color:#22D48A;">{roi_pct}%</strong>.
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Tab 3: Sprint 1 ───────────────────────────────────────────────────
    with tab3:
        st.markdown("##### Sprint 1 — Status das User Stories")

        us_data = [
            ("US01", "Identificacao de Risco",   "Charles",   "🟡 Em andamento", 70),
            ("US02", "Governanca / Auditoria",   "Rafael",    "🟡 Em andamento", 60),
            ("US03", "Painel Cliente",            "Charles",   "🔵 Planejado",    30),
            ("US04", "Operador de Equipamento",  "Anthony",   "🟡 Em andamento", 55),
            ("US05", "Gestor de Frota",          "Gustavo",   "🔵 Planejado",    25),
            ("US06", "Tecnico / Anomalias",      "Guilherme", "🟡 Em andamento", 50),
            ("US07", "Subscricao XAI",           "Rafael",    "🟡 Em andamento", 65),
            ("US08", "Analista de Sinistros",    "Guilherme", "🔵 Planejado",    20),
        ]

        cores_membro = {
            "Rafael": "#5B7FFF", "Charles": "#22D48A",
            "Anthony": "#A855F7", "Guilherme": "#F5A623", "Gustavo": "#FF4D6A",
        }

        for us_id, titulo, dono, status, pct in us_data:
            cor_d = cores_membro.get(dono, "#8B8FA8")
            cor_s = "#22D48A" if "Concluido" in status else "#F5A623" if "andamento" in status else "#5B7FFF"
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid rgba(255,255,255,0.07);
                        border-radius:10px;padding:14px 18px;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;
                            align-items:center;margin-bottom:8px;">
                    <div style="display:flex;gap:10px;align-items:center;">
                        <span style="font-size:0.65rem;color:{cor_d};background:{cor_d}20;
                                     padding:2px 8px;border-radius:4px;font-weight:700;">{us_id}</span>
                        <span style="font-weight:600;font-size:0.9rem;color:#EEF0F8;">{titulo}</span>
                    </div>
                    <div style="display:flex;gap:12px;align-items:center;">
                        <span style="font-size:0.72rem;color:{cor_d};">{dono}</span>
                        <span style="font-size:0.7rem;color:{cor_s};">{status}</span>
                    </div>
                </div>
                <div style="background:#07080C;height:5px;border-radius:3px;overflow:hidden;">
                    <div style="background:{cor_s};width:{pct}%;height:100%;border-radius:3px;"></div>
                </div>
                <div style="font-size:0.65rem;color:#4A4D62;margin-top:4px;text-align:right;">{pct}%</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    from core_audit import renderizar_trilha
    renderizar_trilha(qtd=5)
