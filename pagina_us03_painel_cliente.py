"""
==============================================================================
SOMPO PREDICT v15 - US03: PAINEL SIMPLIFICADO DO CLIENTE
==============================================================================
Owner:     Charles (placeholder funcional)
Tipo:      Pagina do MENU - visao do Cliente Segurado
Prioridade: ALTA

Descricao:
    Interface simplificada para o produtor rural (cliente final da Sompo).
    Foco em simplicidade radical: farol de risco gigante, recomendacoes
    em linguagem natural, e demonstracao de valor (sinistros evitados).

Stack original (US03):
    - React + Tailwind (frontend)
    - GraphQL (queries)
    - WebSocket (alertas tempo real)
    - React Native (mobile)

Acceptance Criteria atendidos:
    [✓] Interface estilo farol (verde/amarelo/vermelho) com status de risco
    [✓] Recomendacoes especificas e mensuraveis ("reduza para 10km/h")
    [✓] Relatorio mensal comparando indice de risco atual vs. anterior

Diferenciais sobre o exemplo base:
    - Layout responsivo profissional com gauge animado
    - Simulador interativo de cenarios (e se eu reduzir a velocidade?)
    - ROI personalizado para o produtor (nao apenas para a Sompo)
    - Historico visual de 30 dias com tendencia
    - Recomendacoes contextuais baseadas no fator dominante
==============================================================================
"""
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False


# ==========================================================================
# LOGICA DE NEGOCIO
# ==========================================================================

PESOS_CLIENTE = {
    "inclinacao":   0.35,
    "umidade":      0.25,
    "velocidade":   0.20,
    "prox_agua":    0.20,
}


def _calcular_score_cliente(inclinacao, umidade, velocidade, prox_agua_m):
    """Score 0-100 para o cliente (versao simplificada)."""
    n_inc  = min(inclinacao / 35, 1.0)
    n_umi  = umidade / 100
    n_vel  = min(velocidade / 25, 1.0)
    n_agua = max(0, 1 - prox_agua_m / 500)
    score = (
        n_inc  * PESOS_CLIENTE["inclinacao"] * 100 +
        n_umi  * PESOS_CLIENTE["umidade"]    * 100 +
        n_vel  * PESOS_CLIENTE["velocidade"] * 100 +
        n_agua * PESOS_CLIENTE["prox_agua"]  * 100
    )
    return round(min(score, 100), 1)


def _farol(score):
    """Mapeia score em (categoria, cor, emoji, texto)."""
    if score <= 30:
        return ("VERDE",    "#22D48A", "🟢", "Operacao Segura")
    elif score <= 60:
        return ("AMARELO",  "#F5A623", "🟡", "Atencao - Reduzir Ritmo")
    elif score <= 80:
        return ("LARANJA",  "#FF7C3A", "🟠", "Risco Alto - Acao Imediata")
    else:
        return ("VERMELHO", "#FF4D6A", "🔴", "Risco Critico - PARAR")


def _recomendacoes(inclinacao, umidade, velocidade, prox_agua_m, score):
    """Gera recomendacoes especificas baseadas no fator dominante."""
    recs = []

    if inclinacao > 25:
        recs.append({
            "icone": "📐",
            "titulo": "Inclinacao critica do terreno",
            "acao": f"Reduza velocidade para 8 km/h (atual: {velocidade:.0f} km/h)",
            "porque": "Inclinacao acima de 25° aumenta em 4x o risco de tombamento",
            "cor": "#FF4D6A",
        })
    elif inclinacao > 15:
        recs.append({
            "icone": "📐",
            "titulo": "Inclinacao moderada",
            "acao": "Mantenha velocidade abaixo de 15 km/h e evite manobras bruscas",
            "porque": "Aderencia reduzida em declives umidos",
            "cor": "#F5A623",
        })

    if umidade > 75:
        recs.append({
            "icone": "💧",
            "titulo": "Solo encharcado",
            "acao": "Adie a operacao em 24-48h ou mude para terreno mais seco",
            "porque": "Solo com umidade > 75% causa atolamento e patinacao",
            "cor": "#FF4D6A",
        })

    if velocidade > 18:
        recs.append({
            "icone": "🏎️",
            "titulo": "Velocidade elevada",
            "acao": "Reduza para 10-12 km/h em area de operacao",
            "porque": "Cada 5 km/h acima da media dobra a distancia de parada",
            "cor": "#F5A623",
        })

    if prox_agua_m < 100:
        recs.append({
            "icone": "🌊",
            "titulo": "Proximidade de curso d'agua",
            "acao": f"Mantenha distancia minima de 100m (atual: {prox_agua_m:.0f}m)",
            "porque": "Margens de rio tem solo instavel - risco de queda",
            "cor": "#FF4D6A",
        })
    elif prox_agua_m < 200:
        recs.append({
            "icone": "🌊",
            "titulo": "Atencao com proximidade da agua",
            "acao": "Reduza velocidade ao se aproximar de cursos d'agua",
            "porque": "Solo proximo a agua tende a ter menor capacidade de carga",
            "cor": "#F5A623",
        })

    # Se nada critico, dica positiva
    if not recs and score < 30:
        recs.append({
            "icone": "✅",
            "titulo": "Tudo dentro dos parametros",
            "acao": "Prossiga com a operacao normal",
            "porque": "Todas as variaveis estao em faixa segura",
            "cor": "#22D48A",
        })

    return recs


# ==========================================================================
# RENDER PRINCIPAL
# ==========================================================================

def render():
    """
    Pagina US03 - Painel do Cliente Segurado.
    Importada e chamada pelo app.py via roteador.
    """
    from app import check_permissao, gerar_trilha_auditoria, _header, _contrato_box

    # Cliente tem acesso ao seu dashboard via view_dashboard
    if not check_permissao("view_dashboard"):
        return

    _contrato_box(
        "pagina_us03_painel_cliente",
        ["ACESSO_US03_CLIENTE", "SIMULACAO_CENARIO",
         "VISUALIZACAO_FAROL", "EXPORTACAO_RELATORIO_MENSAL"]
    )
    _header(
        "Painel do Segurado",
        "Charles",
        "US03 · Cliente · Farol de Risco · Recomendacoes · Comparativo Mensal"
    )
    gerar_trilha_auditoria("ACESSO_US03_CLIENTE", "pagina=us03_painel_cliente")

    # Saudacao personalizada
    hora = datetime.now().hour
    saudacao = "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"
    st.markdown(f"""
    <div style="margin-bottom:1.5rem;">
        <div style="font-size:0.85rem;color:#8B8FA8;">{saudacao}, produtor!</div>
        <div style="font-size:1.1rem;color:#EEF0F8;margin-top:4px;">
            Aqui esta o status da sua frota agora -
            <span style="color:#5B7FFF;">Fazenda Santa Helena</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── TABS ──
    tab1, tab2, tab3, tab4 = st.tabs([
        "Status Agora",
        "Simular Cenario",
        "Relatorio Mensal",
        "Meu Beneficio",
    ])

    # ── TAB 1: STATUS AGORA (FAROL) ──────────────────────────────────────
    with tab1:
        st.markdown("##### Telemetria em tempo real - Ativo COL-099")

        col_in, col_out = st.columns([1, 2])

        with col_in:
            st.markdown("**Variaveis monitoradas**")
            inclinacao  = st.slider("Inclinacao (graus)", 0.0, 40.0, 18.0, step=0.5,
                                    key="us03_inc",
                                    help="Eixo Z do giroscopio MPU-6050")
            umidade     = st.slider("Umidade do solo (%)", 0.0, 100.0, 65.0, step=1.0,
                                    key="us03_umi",
                                    help="Sensor DHT22 / dados INMET")
            velocidade  = st.slider("Velocidade (km/h)", 0.0, 30.0, 14.0, step=0.5,
                                    key="us03_vel",
                                    help="GPS embarcado")
            prox_agua_m = st.slider("Distancia de cursos d'agua (m)", 20, 800, 250,
                                    step=10, key="us03_agua",
                                    help="Calculado via GIS")

        score = _calcular_score_cliente(inclinacao, umidade, velocidade, prox_agua_m)
        cat, cor, emoji, texto_cat = _farol(score)

        with col_out:
            # Gauge de farol gigante
            if PLOTLY_OK:
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=score,
                    number={"suffix": "/100",
                            "font": {"size": 56, "color": cor}},
                    gauge={
                        "axis": {"range": [0, 100], "tickwidth": 1,
                                 "tickcolor": "#4A4D62"},
                        "bar":  {"color": cor, "thickness": 0.3},
                        "bgcolor": "#0D0F18",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [0, 30],   "color": "rgba(34,212,138,0.18)"},
                            {"range": [30, 60],  "color": "rgba(245,166,35,0.18)"},
                            {"range": [60, 80],  "color": "rgba(255,124,58,0.18)"},
                            {"range": [80, 100], "color": "rgba(255,77,106,0.18)"},
                        ],
                        "threshold": {
                            "line":  {"color": cor, "width": 3},
                            "thickness": 0.85,
                            "value": score,
                        },
                    },
                    domain={"x": [0, 1], "y": [0, 1]},
                ))
                fig_gauge.update_layout(
                    paper_bgcolor="#0D0F18",
                    font=dict(color="#EEF0F8", family="Arial"),
                    height=280,
                    margin=dict(l=20, r=20, t=10, b=10),
                )
                st.plotly_chart(fig_gauge, use_container_width=True)

            st.markdown(f"""
            <div style="background:{cor}15;border:2px solid {cor};
                        border-radius:14px;padding:1rem 1.5rem;text-align:center;
                        margin-top:-1rem;">
                <div style="font-size:2rem;margin-bottom:4px;">{emoji}</div>
                <div style="font-size:1.4rem;font-weight:800;color:{cor};
                            letter-spacing:0.02em;">{cat}</div>
                <div style="font-size:0.95rem;color:#EEF0F8;margin-top:6px;">
                    {texto_cat}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### O que voce deve fazer agora")
        recs = _recomendacoes(inclinacao, umidade, velocidade, prox_agua_m, score)

        for rec in recs:
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid {rec['cor']}33;
                        border-left:4px solid {rec['cor']};border-radius:10px;
                        padding:14px 18px;margin-bottom:8px;
                        display:flex;gap:14px;align-items:flex-start;">
                <div style="font-size:1.5rem;">{rec['icone']}</div>
                <div style="flex:1;">
                    <div style="font-weight:700;color:#EEF0F8;font-size:0.95rem;
                                margin-bottom:4px;">{rec['titulo']}</div>
                    <div style="color:{rec['cor']};font-weight:600;font-size:0.88rem;
                                margin-bottom:6px;">{rec['acao']}</div>
                    <div style="font-size:0.78rem;color:#8B8FA8;">
                        <strong style="color:#4A4D62;">Por que?</strong> {rec['porque']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        if st.button("Confirmar leitura do alerta", key="us03_ack"):
            gerar_trilha_auditoria(
                "VISUALIZACAO_FAROL",
                f"score={score} categoria={cat} num_recs={len(recs)}"
            )
            st.success("Confirmacao registrada na trilha de auditoria.")

    # ── TAB 2: SIMULAR CENARIO ───────────────────────────────────────────
    with tab2:
        st.markdown("##### Simulador 'E se eu fizer diferente?'")
        st.caption("Ajuste cada variavel e veja como o seu score de risco muda em tempo real.")

        # Cenario base = valores atuais da tab 1
        score_atual = _calcular_score_cliente(inclinacao, umidade, velocidade, prox_agua_m)
        cat_a, cor_a, emoji_a, _ = _farol(score_atual)

        col_sim1, col_sim2 = st.columns(2)

        with col_sim1:
            st.markdown("**🔴 Situacao atual**")
            st.markdown(f"""
            <div style="background:{cor_a}15;border:1px solid {cor_a};
                        border-radius:10px;padding:1rem;text-align:center;">
                <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;">
                    Score Atual</div>
                <div style="font-size:2.5rem;font-weight:800;color:{cor_a};">{score_atual:.1f}</div>
                <div style="font-size:0.85rem;color:#EEF0F8;">{emoji_a} {cat_a}</div>
            </div>
            """, unsafe_allow_html=True)

            st.caption(
                f"Inclinacao: {inclinacao:.0f}° · Umidade: {umidade:.0f}% · "
                f"Vel: {velocidade:.0f} km/h · Agua: {prox_agua_m}m"
            )

        with col_sim2:
            st.markdown("**🎯 Cenario simulado**")
            sim_inc  = st.slider("Inclinacao",   0.0, 40.0, max(0.0, inclinacao - 10), step=0.5, key="sim_inc")
            sim_umi  = st.slider("Umidade",      0.0, 100.0, max(0.0, umidade - 15),    step=1.0, key="sim_umi")
            sim_vel  = st.slider("Velocidade",   0.0, 30.0, max(0.0, velocidade - 5),   step=0.5, key="sim_vel")
            sim_agua = st.slider("Dist. agua",   20, 800, min(800, int(prox_agua_m + 100)), step=10, key="sim_agua")

            score_sim = _calcular_score_cliente(sim_inc, sim_umi, sim_vel, sim_agua)
            cat_s, cor_s, emoji_s, _ = _farol(score_sim)
            delta_score = score_sim - score_atual
            delta_cor   = "#22D48A" if delta_score < 0 else "#FF4D6A"
            seta        = "▼" if delta_score < 0 else "▲"

            st.markdown(f"""
            <div style="background:{cor_s}15;border:1px solid {cor_s};
                        border-radius:10px;padding:1rem;text-align:center;">
                <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;">
                    Score Simulado</div>
                <div style="font-size:2.5rem;font-weight:800;color:{cor_s};">{score_sim:.1f}</div>
                <div style="font-size:0.85rem;color:#EEF0F8;">{emoji_s} {cat_s}</div>
                <div style="margin-top:8px;font-size:0.85rem;color:{delta_cor};font-weight:700;">
                    {seta} {abs(delta_score):.1f} pontos
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Comparativo visual
        if PLOTLY_OK:
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(
                x=["Inclinacao", "Umidade", "Velocidade", "Distancia Agua"],
                y=[inclinacao, umidade, velocidade, prox_agua_m / 10],
                name="Atual",
                marker_color=cor_a,
                opacity=0.85,
            ))
            fig_comp.add_trace(go.Bar(
                x=["Inclinacao", "Umidade", "Velocidade", "Distancia Agua"],
                y=[sim_inc, sim_umi, sim_vel, sim_agua / 10],
                name="Simulado",
                marker_color=cor_s,
                opacity=0.85,
            ))
            fig_comp.update_layout(
                title="Comparativo de variaveis (Distancia Agua dividida por 10 para escala)",
                barmode="group",
                template="plotly_dark",
                plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
                font=dict(color="#EEF0F8"),
                height=320,
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            xanchor="right", x=1),
            )
            st.plotly_chart(fig_comp, use_container_width=True)

        if st.button("Salvar simulacao", key="us03_sim"):
            gerar_trilha_auditoria(
                "SIMULACAO_CENARIO",
                f"score_atual={score_atual} score_sim={score_sim} delta={delta_score:+.1f}"
            )
            st.success("Simulacao registrada para auditoria.")

    # ── TAB 3: RELATORIO MENSAL ──────────────────────────────────────────
    with tab3:
        st.markdown("##### Indice de risco - 30 dias")
        st.caption("Acceptance Criteria #3: comparacao do indice atual vs. periodo anterior.")

        # Series temporais 30 dias
        np.random.seed(13)
        dias = pd.date_range(end=datetime.now(), periods=30, freq="D")
        # Tendencia decrescente (cliente esta melhorando)
        scores_atual = np.clip(
            45 + np.cumsum(np.random.randn(30) * 1.2) - np.linspace(0, 15, 30),
            10, 80
        )
        scores_anterior = np.clip(
            55 + np.random.randn(30) * 4 + np.linspace(5, -5, 30),
            10, 85
        )
        df_hist = pd.DataFrame({
            "Data":           dias,
            "Periodo Atual":  scores_atual.round(1),
            "Periodo Anterior": scores_anterior.round(1),
        })

        media_atual    = df_hist["Periodo Atual"].mean()
        media_anterior = df_hist["Periodo Anterior"].mean()
        delta_media    = media_atual - media_anterior

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Media 30d (atual)",     f"{media_atual:.1f}",
                  delta=f"{delta_media:+.1f} vs. anterior",
                  delta_color="inverse")
        c2.metric("Pior dia",              f"{df_hist['Periodo Atual'].max():.1f}")
        c3.metric("Melhor dia",            f"{df_hist['Periodo Atual'].min():.1f}")
        c4.metric("Dias verdes (<= 30)",
                  int((df_hist["Periodo Atual"] <= 30).sum()),
                  delta=f"de 30 dias")

        if PLOTLY_OK:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_hist["Data"], y=df_hist["Periodo Anterior"],
                name="Periodo Anterior",
                mode="lines",
                line=dict(color="#4A4D62", width=2, dash="dot"),
            ))
            fig.add_trace(go.Scatter(
                x=df_hist["Data"], y=df_hist["Periodo Atual"],
                name="Periodo Atual",
                mode="lines+markers",
                line=dict(color="#5B7FFF", width=2.5),
                fill="tozeroy", fillcolor="rgba(91,127,255,0.08)",
            ))
            # Faixas de farol
            fig.add_hrect(y0=0,  y1=30, fillcolor="rgba(34,212,138,0.05)",
                          line_width=0, annotation_text="Verde",
                          annotation_position="right")
            fig.add_hrect(y0=30, y1=60, fillcolor="rgba(245,166,35,0.05)",
                          line_width=0, annotation_text="Amarelo",
                          annotation_position="right")
            fig.add_hrect(y0=60, y1=100, fillcolor="rgba(255,77,106,0.05)",
                          line_width=0, annotation_text="Vermelho/Laranja",
                          annotation_position="right")
            fig.update_layout(
                title="Evolucao do indice diario de risco",
                xaxis_title="Data", yaxis_title="Score (0-100)",
                template="plotly_dark",
                plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
                font=dict(color="#EEF0F8"),
                height=400,
                hovermode="x unified",
                yaxis=dict(range=[0, 100]),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Mensagem motivacional baseada no delta
        if delta_media < -5:
            msg_cor = "#22D48A"
            msg = (f"Excelente! Voce reduziu seu risco medio em {abs(delta_media):.1f} pontos. "
                   "Continue seguindo as recomendacoes.")
        elif delta_media < 0:
            msg_cor = "#5B7FFF"
            msg = f"Voce esta no caminho certo. Reducao de {abs(delta_media):.1f} pontos no mes."
        else:
            msg_cor = "#F5A623"
            msg = (f"Atencao: seu risco medio aumentou {delta_media:.1f} pontos. "
                   "Reveja as recomendacoes da aba 'Status Agora'.")

        st.markdown(f"""
        <div style="background:{msg_cor}10;border:1px solid {msg_cor};
                    border-left:3px solid {msg_cor};border-radius:10px;
                    padding:14px 18px;margin-top:1rem;font-size:0.88rem;color:#EEF0F8;">
            {msg}
        </div>
        """, unsafe_allow_html=True)

        if st.button("Baixar relatorio completo (PDF)", key="us03_pdf"):
            gerar_trilha_auditoria(
                "EXPORTACAO_RELATORIO_MENSAL",
                f"media_atual={media_atual:.1f} delta={delta_media:+.1f}"
            )
            st.success("Relatorio mensal registrado para auditoria.")

    # ── TAB 4: MEU BENEFICIO ─────────────────────────────────────────────
    with tab4:
        st.markdown("##### Quanto voce ja economizou com o Sompo Predict?")
        st.caption("Demonstracao de valor para o produtor (nao apenas para a Sompo).")

        # KPIs do mes
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Sinistros Evitados (mes)", "3", delta="+1 vs. mes anterior")
        col_b.metric("Horas de operacao salvas", "47h",
                     delta="3 paradas evitadas")
        col_c.metric("Combustivel preservado",   "184 L",
                     delta="manobras otimizadas")
        col_d.metric("Reducao no premio",        "8%",
                     delta="bom historico de risco",
                     delta_color="off")

        st.markdown("<br>", unsafe_allow_html=True)

        # Cards de valor
        col_v1, col_v2 = st.columns(2)

        with col_v1:
            st.markdown("""
            <div style="background:linear-gradient(135deg,rgba(34,212,138,0.08),rgba(91,127,255,0.04));
                        border:1px solid rgba(34,212,138,0.3);
                        border-radius:14px;padding:1.5rem;">
                <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                            letter-spacing:0.1em;margin-bottom:6px;">Economia Estimada (12m)</div>
                <div style="font-size:2.2rem;font-weight:800;color:#22D48A;line-height:1;">
                    R$ 1.35 M</div>
                <div style="font-size:0.82rem;color:#8B8FA8;margin-top:8px;line-height:1.6;">
                    3 sinistros evitados × R$ 450k de custo medio.
                    Inclui parada operacional, reparo do equipamento e tempo de safra perdido.
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_v2:
            st.markdown("""
            <div style="background:linear-gradient(135deg,rgba(91,127,255,0.08),rgba(168,85,247,0.04));
                        border:1px solid rgba(91,127,255,0.3);
                        border-radius:14px;padding:1.5rem;">
                <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                            letter-spacing:0.1em;margin-bottom:6px;">Indice de Eficiencia</div>
                <div style="font-size:2.2rem;font-weight:800;color:#5B7FFF;line-height:1;">
                    87%</div>
                <div style="font-size:0.82rem;color:#8B8FA8;margin-top:8px;line-height:1.6;">
                    Suas decisoes baseadas no Sompo Predict tem alto alinhamento
                    com as recomendacoes do modelo. Top 15% dos segurados.
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Resumo dos eventos do mes")
        eventos = [
            ("12/04", "🟢 Verde",    "Operacao normal",
             "Inclinacao baixa, solo seco"),
            ("15/04", "🟡 Amarelo",  "Velocidade reduzida",
             "Voce desacelerou ao receber alerta - risco evitado"),
            ("19/04", "🔴 Vermelho", "Parada preventiva",
             "Tombamento evitado em terreno encharcado proximo a represa"),
            ("23/04", "🟡 Amarelo",  "Manobra alternativa",
             "Voce contornou area critica - economia de 2h"),
            ("28/04", "🟢 Verde",    "Operacao normal",
             "Recomendacao seguida com 100% de aderencia"),
        ]
        for data, status, titulo, desc in eventos:
            st.markdown(f"""
            <div style="background:#131520;border:1px solid rgba(255,255,255,0.07);
                        border-radius:8px;padding:10px 16px;margin-bottom:6px;
                        display:flex;gap:16px;align-items:center;">
                <div style="min-width:50px;font-size:0.78rem;color:#8B8FA8;
                            font-family:monospace;">{data}</div>
                <div style="min-width:100px;font-size:0.82rem;">{status}</div>
                <div style="flex:1;">
                    <div style="font-weight:600;color:#EEF0F8;font-size:0.85rem;">{titulo}</div>
                    <div style="font-size:0.75rem;color:#8B8FA8;">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Footer
    st.markdown("---")
    st.markdown(f"""
    <div style="background:rgba(91,127,255,0.04);border:1px solid rgba(91,127,255,0.2);
                border-left:3px solid #5B7FFF;border-radius:10px;
                padding:12px 18px;font-size:0.78rem;color:#8B8FA8;line-height:1.7;">
        <strong style="color:#EEF0F8;">Status de integracao US03:</strong><br>
        <span style="color:#22D48A;">✓</span> Pagina criada e funcional ·
        <span style="color:#22D48A;">✓</span> Farol implementado ·
        <span style="color:#22D48A;">✓</span> Simulador interativo ·
        <span style="color:#22D48A;">✓</span> Relatorio comparativo ·
        <span style="color:#F5A623;">~</span> Aguardando dados WebSocket reais (Anthony)
    </div>
    """, unsafe_allow_html=True)
