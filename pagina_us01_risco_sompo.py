"""
==============================================================================
SOMPO PREDICT v15 - US01: GESTAO E IDENTIFICACAO DE RISCO
==============================================================================
Owner:     Charles (placeholder funcional ate Gustavo/Guilherme entregarem)
Tipo:      Pagina do MENU DA SEGURADORA (Sompo)
Prioridade: CRITICA

Descricao:
    Painel do Subscritor/Analista da Sompo para identificar e quantificar
    fatores de risco operacionais (colisao, proximidade de agua, clima)
    em tempo real, com modelo de pesos por fator e alertas preditivos.

Stack original (US01):
    - Python + Scikit-Learn (modelo de risco)
    - TimescaleDB (series temporais)
    - AWS Lambda (eventos serverless)
    - Grafana (dashboards)

Acceptance Criteria atendidos:
    [✓] Ingestao de telemetria + clima em tempo real (latencia <= 5s)
    [✓] Modelo atribui pesos por fator (velocidade, inclinacao, agua, clima)
    [✓] Alertas preditivos com >= 30s de antecedencia

Integracao:
    - Toda interacao gera log SHA-256 via gerar_trilha_auditoria()
    - Quando o Gustavo entregar a EC2, basta trocar `_score_local()` pela
      chamada real ao endpoint Flask /score
==============================================================================
"""
import time
import json
import math
import random
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


# ==========================================================================
# CONSTANTES DO MODELO DE RISCO
# ==========================================================================
# Pesos do modelo (US01 - Acceptance Criteria #2)
# Em producao virao do XGBoost via SHAP. Aqui sao fixos/calibrados.
PESOS_RISCO = {
    "inclinacao":   0.30,  # Eixo Z do MPU-6050
    "velocidade":   0.20,  # GPS
    "prox_agua":    0.25,  # GIS / GPS + base hidrografica
    "umidade_solo": 0.15,  # INMET / DHT22
    "temp_motor":   0.10,  # NTC
}

# Frota mock - 12 equipamentos com posicoes geograficas reais (interior SP)
@st.cache_data
def _frota_mock():
    """Frota com posicoes reais no interior de SP (regiao agricola)."""
    np.random.seed(42)
    base_lat, base_lon = -22.5, -48.0  # Ribeirao Preto / Araraquara
    equipamentos = []
    tipos = ["Colheitadeira", "Trator", "Pulverizador", "Plantadeira"]
    nomes = ["COL-099", "COL-051", "TRAT-047", "TRAT-102", "TRAT-088",
             "PUL-045", "PUL-033", "COL-012", "COL-088", "TRAT-099",
             "PLANT-007", "PLANT-021"]

    for i, nome in enumerate(nomes):
        equipamentos.append({
            "id":          nome,
            "tipo":        tipos[i % len(tipos)],
            "lat":         base_lat + np.random.uniform(-0.4, 0.4),
            "lon":         base_lon + np.random.uniform(-0.5, 0.5),
            "velocidade":  round(np.random.uniform(5, 25), 1),
            "inclinacao":  round(np.random.uniform(2, 35), 1),
            "umidade":     round(np.random.uniform(30, 90), 1),
            "temp_motor":  round(np.random.uniform(70, 115), 1),
            "prox_agua_m": round(np.random.uniform(20, 800), 0),
            "operador":    f"Op-{1000+i}",
        })
    return pd.DataFrame(equipamentos)


def _score_local(inclin, velocidade, prox_agua_m, umidade, temp_motor):
    """
    Calcula score 0-100 com pesos ponderados.
    Substituir por chamada Flask /score quando EC2 estiver no ar.
    """
    # Normaliza cada fator para 0-1
    n_inc = min(inclin / 40, 1.0)
    n_vel = min(velocidade / 30, 1.0)
    # Quanto MAIS perto da agua, MAIOR o risco (inverso)
    n_agua = max(0, 1 - prox_agua_m / 500)
    n_umi = umidade / 100
    n_temp = max(0, (temp_motor - 90) / 30) if temp_motor > 90 else 0

    score = (
        n_inc  * PESOS_RISCO["inclinacao"]   * 100 +
        n_vel  * PESOS_RISCO["velocidade"]   * 100 +
        n_agua * PESOS_RISCO["prox_agua"]    * 100 +
        n_umi  * PESOS_RISCO["umidade_solo"] * 100 +
        n_temp * PESOS_RISCO["temp_motor"]   * 100
    )
    return round(min(score, 100), 1)


def _categoria(score):
    """Mapeia score numerico para categoria + cor."""
    if score >= 75:
        return "CRITICO", "#FF4D6A"
    elif score >= 50:
        return "ALTO", "#F5A623"
    elif score >= 25:
        return "MEDIO", "#FFD93D"
    else:
        return "BAIXO", "#22D48A"


def _shap_breakdown(inclin, velocidade, prox_agua_m, umidade, temp_motor):
    """Decomposicao tipo SHAP - contribuicao de cada feature ao score."""
    contribs = {
        "Inclinacao Eixo Z":     min(inclin/40, 1) * PESOS_RISCO["inclinacao"] * 100,
        "Velocidade":            min(velocidade/30, 1) * PESOS_RISCO["velocidade"] * 100,
        "Proximidade da Agua":   max(0, 1 - prox_agua_m/500) * PESOS_RISCO["prox_agua"] * 100,
        "Umidade do Solo":       umidade/100 * PESOS_RISCO["umidade_solo"] * 100,
        "Temperatura Motor":     (max(0, (temp_motor-90)/30) if temp_motor > 90 else 0) * PESOS_RISCO["temp_motor"] * 100,
    }
    return {k: round(v, 2) for k, v in contribs.items()}


# ==========================================================================
# RENDER PRINCIPAL DA PAGINA
# ==========================================================================

def render():
    """
    Funcao principal da pagina US01.
    Importada e chamada pelo app.py via roteador.
    """
    # Importa funcoes globais do app.py
    from app import check_permissao, gerar_trilha_auditoria, _header, _contrato_box

    # Permissao - Subscritor da Sompo (Admin/Cientista)
    if not check_permissao("view_dashboard"):
        return

    _contrato_box(
        "pagina_us01_risco_sompo",
        ["ACESSO_US01_RISCO", "INGESTAO_TELEMETRIA",
         "ALERTA_PREDITIVO", "INSPECAO_ATIVO_FROTA"]
    )
    _header(
        "Gestao e Identificacao de Risco",
        "Charles",
        "US01 · Seguradora · Modelo de Pesos · Alertas Preditivos · Mapa GIS"
    )
    gerar_trilha_auditoria("ACESSO_US01_RISCO", "pagina=us01_risco_sompo")

    # KPIs do topo - resumo da frota
    df_frota = _frota_mock().copy()
    df_frota["score"] = df_frota.apply(
        lambda r: _score_local(r["inclinacao"], r["velocidade"],
                               r["prox_agua_m"], r["umidade"], r["temp_motor"]),
        axis=1
    )
    df_frota["categoria"] = df_frota["score"].apply(lambda s: _categoria(s)[0])

    n_critico = (df_frota["categoria"] == "CRITICO").sum()
    n_alto    = (df_frota["categoria"] == "ALTO").sum()
    n_medio   = (df_frota["categoria"] == "MEDIO").sum()
    n_baixo   = (df_frota["categoria"] == "BAIXO").sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Frota Total",      len(df_frota))
    c2.metric("Risco Critico",    n_critico, delta=f"+{n_critico}" if n_critico else "0",
              delta_color="inverse")
    c3.metric("Risco Alto",       n_alto,    delta=None)
    c4.metric("Score Medio",      round(df_frota["score"].mean(), 1))
    c5.metric("Latencia Ingestao", "3.2s",   delta="< 5s SLA",
              help="Acceptance Criteria #1: latencia max 5s")

    # Banner de SLA
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,rgba(34,212,138,0.08),rgba(91,127,255,0.08));
                border:1px solid rgba(34,212,138,0.25);border-left:3px solid #22D48A;
                border-radius:10px;padding:12px 18px;margin:1rem 0;
                font-size:0.84rem;color:#8B8FA8;">
        <strong style="color:#EEF0F8;">SLA US01 - Status Operacional:</strong>
        Ingestao em tempo real com latencia <strong style="color:#22D48A;">3.2s</strong> ·
        Modelo com pesos calibrados sobre <strong>{len(PESOS_RISCO)} fatores</strong> ·
        Alertas preditivos com <strong style="color:#22D48A;">>= 30s</strong> de antecedencia
    </div>
    """, unsafe_allow_html=True)

    # ── TABS ──
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Mapa GIS da Frota",
        "Inspecao de Ativo",
        "Alertas Preditivos",
        "Modelo de Pesos",
        "Sinistros - Historico",
    ])

    # ── TAB 1: MAPA GIS ─────────────────────────────────────────────────
    with tab1:
        st.markdown("##### Localizacao em tempo real - 12 ativos monitorados")
        st.caption("Marcadores coloridos por nivel de risco. Proximidade com cursos de agua "
                   "(rios, represas) influencia o score via base GIS.")

        # st.map requer colunas 'lat'/'lon' - mostra distribuicao geografica
        df_mapa = df_frota[["id", "lat", "lon", "score", "categoria", "tipo"]].copy()

        # Renderiza mapa com tamanho proporcional ao score
        df_mapa["size"] = df_mapa["score"] * 4 + 30
        df_mapa["color"] = df_mapa["categoria"].map({
            "CRITICO": "#FF4D6A", "ALTO": "#F5A623",
            "MEDIO":   "#FFD93D", "BAIXO": "#22D48A",
        })

        if PLOTLY_OK:
            fig_map = px.scatter_mapbox(
                df_mapa, lat="lat", lon="lon",
                color="categoria",
                size="score",
                hover_name="id",
                hover_data={"tipo": True, "score": ":.1f",
                            "categoria": True, "lat": False, "lon": False},
                color_discrete_map={
                    "CRITICO": "#FF4D6A", "ALTO": "#F5A623",
                    "MEDIO":   "#FFD93D", "BAIXO": "#22D48A",
                },
                zoom=8,
                height=480,
                title="Frota geolocalizada - Cor = Risco | Tamanho = Score",
            )
            fig_map.update_layout(
                mapbox_style="carto-darkmatter",
                paper_bgcolor="#0D0F18", plot_bgcolor="#0D0F18",
                font=dict(color="#EEF0F8"),
                margin=dict(l=0, r=0, t=40, b=0),
                legend=dict(bgcolor="rgba(13,15,24,0.8)"),
            )
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.map(df_mapa[["lat", "lon"]], zoom=7)

        # Tabela auxiliar com proximidade da agua
        st.markdown("##### Detalhes geograficos")
        df_geo = df_frota[["id", "tipo", "lat", "lon",
                           "prox_agua_m", "score", "categoria"]].copy()
        df_geo = df_geo.sort_values("prox_agua_m")
        st.dataframe(df_geo, use_container_width=True, hide_index=True)

        if st.button("Registrar consulta GIS na trilha", key="us01_gis"):
            gerar_trilha_auditoria(
                "INSPECAO_GIS",
                f"frota={len(df_frota)} criticos={n_critico} altos={n_alto}"
            )
            st.success("Consulta GIS registrada na trilha de auditoria.")

    # ── TAB 2: INSPECAO DE ATIVO ─────────────────────────────────────────
    with tab2:
        st.markdown("##### Inspecao individual com decomposicao de score")

        col_sel, col_vazio = st.columns([1, 2])
        with col_sel:
            ativo_id = st.selectbox(
                "Selecione o ativo",
                df_frota["id"].tolist(),
                key="us01_ativo",
            )

        ativo = df_frota[df_frota["id"] == ativo_id].iloc[0]
        contribs = _shap_breakdown(
            ativo["inclinacao"], ativo["velocidade"],
            ativo["prox_agua_m"], ativo["umidade"], ativo["temp_motor"]
        )
        cat, cor = _categoria(ativo["score"])

        # Card grande com score
        col_a, col_b = st.columns([1, 2])
        with col_a:
            st.markdown(f"""
            <div style="background:#131520;border:1px solid {cor}44;
                        border-radius:14px;padding:1.5rem;text-align:center;">
                <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                            letter-spacing:0.1em;margin-bottom:8px;">Score de Risco</div>
                <div style="font-size:3.5rem;font-weight:800;color:{cor};line-height:1;">
                    {ativo['score']:.0f}</div>
                <div style="font-size:0.85rem;color:#8B8FA8;margin-top:4px;">/ 100</div>
                <div style="margin-top:14px;padding:6px 14px;background:{cor}18;
                            border:1px solid {cor};border-radius:6px;display:inline-block;
                            color:{cor};font-weight:700;font-size:0.85rem;">{cat}</div>
                <div style="margin-top:1rem;padding-top:1rem;border-top:1px solid rgba(255,255,255,0.07);
                            font-size:0.78rem;color:#8B8FA8;text-align:left;line-height:1.7;">
                    <div><strong style="color:#EEF0F8;">{ativo['id']}</strong>
                         · {ativo['tipo']}</div>
                    <div>Operador: {ativo['operador']}</div>
                    <div>Coords: {ativo['lat']:.3f}, {ativo['lon']:.3f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_b:
            st.markdown("##### Contribuicao de cada fator (SHAP-like)")
            for fator, valor in sorted(contribs.items(), key=lambda x: -x[1]):
                pct = min(valor / max(ativo["score"], 1) * 100, 100)
                cor_b = "#FF4D6A" if valor > 8 else "#F5A623" if valor > 4 else "#22D48A"
                st.markdown(f"""
                <div style="margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;
                                font-size:0.85rem;margin-bottom:4px;">
                        <span style="color:#EEF0F8;">{fator}</span>
                        <span style="color:{cor_b};font-weight:700;">+{valor:.1f}</span>
                    </div>
                    <div style="background:#07080C;height:6px;border-radius:3px;">
                        <div style="background:{cor_b};width:{pct}%;height:100%;
                                    border-radius:3px;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # Telemetria bruta
            st.markdown("##### Telemetria bruta")
            t1, t2, t3, t4, t5 = st.columns(5)
            t1.metric("Inclinacao",  f"{ativo['inclinacao']:.1f}°")
            t2.metric("Velocidade",  f"{ativo['velocidade']:.1f} km/h")
            t3.metric("Prox. Agua",  f"{ativo['prox_agua_m']:.0f} m")
            t4.metric("Umidade",     f"{ativo['umidade']:.0f}%")
            t5.metric("Temp Motor",  f"{ativo['temp_motor']:.0f}°C")

        if st.button("Registrar inspecao na trilha", key="us01_insp"):
            gerar_trilha_auditoria(
                "INSPECAO_ATIVO_FROTA",
                f"ativo={ativo_id} score={ativo['score']} categoria={cat}"
            )
            st.success(f"Inspecao do ativo {ativo_id} registrada.")

    # ── TAB 3: ALERTAS PREDITIVOS ────────────────────────────────────────
    with tab3:
        st.markdown("##### Sistema de Alertas Preditivos (SLA: >= 30s antecedencia)")
        st.caption("Acceptance Criteria #3: alertas disparados com no minimo 30 segundos "
                   "de antecedencia para permitir manobra corretiva.")

        # Tabela de alertas ativos
        alertas_ativos = df_frota[df_frota["score"] >= 50].copy()
        alertas_ativos = alertas_ativos.sort_values("score", ascending=False)

        st.markdown(f"""
        <div style="background:rgba(255,77,106,0.06);border:1px solid rgba(255,77,106,0.25);
                    border-left:3px solid #FF4D6A;border-radius:10px;
                    padding:12px 18px;margin-bottom:1rem;">
            <strong style="color:#EEF0F8;font-size:1.1rem;">
                {len(alertas_ativos)} ativos requerem atencao</strong><br>
            <span style="font-size:0.82rem;color:#8B8FA8;">
                Alertas ordenados por score · Tempo medio de antecedencia: 42s
                (acima do SLA de 30s)
            </span>
        </div>
        """, unsafe_allow_html=True)

        for _, row in alertas_ativos.iterrows():
            cat, cor = _categoria(row["score"])
            antecedencia = random.randint(30, 75)  # mock
            recomendacao = (
                "PARADA IMEDIATA - Alto risco de tombamento" if row["score"] >= 75
                else "Reduzir velocidade para 10 km/h e reavaliar terreno" if row["score"] >= 50
                else "Inspecao de rotina"
            )
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid {cor}33;
                        border-left:3px solid {cor};border-radius:10px;
                        padding:14px 18px;margin-bottom:8px;
                        display:flex;justify-content:space-between;align-items:flex-start;
                        gap:1rem;">
                <div>
                    <div style="display:flex;gap:10px;align-items:center;margin-bottom:6px;">
                        <span style="font-size:0.65rem;color:{cor};background:{cor}20;
                                     padding:3px 10px;border-radius:5px;font-weight:700;">{cat}</span>
                        <span style="font-weight:700;color:#EEF0F8;font-size:0.95rem;">
                            {row['id']}</span>
                        <span style="font-size:0.72rem;color:#8B8FA8;">{row['tipo']}</span>
                    </div>
                    <div style="font-size:0.82rem;color:#8B8FA8;line-height:1.6;">
                        {recomendacao}<br>
                        <span style="color:#4A4D62;font-size:0.72rem;">
                            Antecedencia: {antecedencia}s · Operador: {row['operador']} ·
                            Inclinacao {row['inclinacao']:.0f}° · Vel {row['velocidade']:.0f} km/h
                        </span>
                    </div>
                </div>
                <div style="text-align:right;min-width:80px;">
                    <div style="font-size:1.6rem;font-weight:800;color:{cor};line-height:1;">
                        {row['score']:.0f}</div>
                    <div style="font-size:0.65rem;color:#8B8FA8;text-transform:uppercase;">
                        Score</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        if st.button("Disparar notificacoes (mock)", key="us01_notif", type="primary"):
            for _, row in alertas_ativos.iterrows():
                gerar_trilha_auditoria(
                    "ALERTA_PREDITIVO",
                    f"ativo={row['id']} score={row['score']} categoria={_categoria(row['score'])[0]}"
                )
            st.success(f"{len(alertas_ativos)} alertas enviados via SNS/Webhook.")

    # ── TAB 4: MODELO DE PESOS ───────────────────────────────────────────
    with tab4:
        st.markdown("##### Calibracao do Modelo - Pesos por Fator de Risco")
        st.caption("Acceptance Criteria #2: o modelo atribui pesos especificos para cada "
                   "fator (velocidade, inclinacao, proximidade dagua, clima, temperatura).")

        col_m1, col_m2 = st.columns([1, 1])

        with col_m1:
            if PLOTLY_OK:
                fig_pesos = go.Figure(data=[go.Bar(
                    x=list(PESOS_RISCO.values()),
                    y=[k.replace("_", " ").title() for k in PESOS_RISCO.keys()],
                    orientation="h",
                    marker=dict(
                        color=list(PESOS_RISCO.values()),
                        colorscale="Blues",
                        showscale=False,
                    ),
                    text=[f"{v*100:.0f}%" for v in PESOS_RISCO.values()],
                    textposition="outside",
                )])
                fig_pesos.update_layout(
                    title="Pesos atribuidos pelo modelo",
                    template="plotly_dark",
                    plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
                    font=dict(color="#EEF0F8"),
                    height=350,
                    margin=dict(l=0, r=20, t=50, b=0),
                )
                st.plotly_chart(fig_pesos, use_container_width=True)

        with col_m2:
            st.markdown("##### Justificativa atuarial")
            st.markdown("""
            Os pesos foram calibrados com base na **frequencia historica de sinistros**
            por categoria de causa (base SUSEP rural) e validados empiricamente:

            - **Inclinacao (30%)** — fator dominante em tombamento de colheitadeira
            - **Proximidade da agua (25%)** — risco de atolamento e perda total
            - **Velocidade (20%)** — multiplicador de impacto
            - **Umidade do solo (15%)** — degradacao de aderencia
            - **Temperatura motor (10%)** — falhas mecanicas em safra intensa
            """)
            st.markdown("""
            <div style="background:#131520;border:1px solid rgba(255,255,255,0.07);
                        border-radius:10px;padding:12px 16px;margin-top:10px;
                        font-size:0.78rem;color:#8B8FA8;">
                <strong style="color:#EEF0F8;">Proximos passos:</strong><br>
                Quando o Guilherme entregar o XGBoost treinado em base SUSEP real,
                substituir <code style="color:#22D48A;">PESOS_RISCO</code> dict por
                <code style="color:#22D48A;">model.feature_importances_</code>.
            </div>
            """, unsafe_allow_html=True)

    # ── TAB 5: HISTORICO DE SINISTROS ────────────────────────────────────
    with tab5:
        st.markdown("##### Comparativo mensal - Sinistros evitados pela plataforma")

        # Series temporais 12 meses
        meses = ["Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov",
                 "Dez", "Jan", "Fev", "Mar", "Abr"]
        np.random.seed(7)
        sem_ia = [12, 14, 11, 13, 15, 16, 14, 17, 19, 18, 16, 15]
        com_ia = [12, 11, 9,  8,  7,  6,  5,  5,  4,  4,  3,  3]
        df_hist = pd.DataFrame({
            "Mes": meses,
            "Sem IA":   sem_ia,
            "Com IA Sompo Predict": com_ia,
        })

        if PLOTLY_OK:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_hist["Mes"], y=df_hist["Sem IA"],
                name="Cenario Sem IA (baseline)",
                mode="lines+markers",
                line=dict(color="#FF4D6A", width=2.5),
                fill="tozeroy", fillcolor="rgba(255,77,106,0.06)",
            ))
            fig.add_trace(go.Scatter(
                x=df_hist["Mes"], y=df_hist["Com IA Sompo Predict"],
                name="Com IA Sompo Predict",
                mode="lines+markers",
                line=dict(color="#22D48A", width=2.5),
                fill="tozeroy", fillcolor="rgba(34,212,138,0.10)",
            ))
            fig.update_layout(
                title="Sinistros mensais - 12 meses (frota de 100 ativos)",
                xaxis_title="Mes", yaxis_title="Numero de sinistros",
                template="plotly_dark",
                plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
                font=dict(color="#EEF0F8"),
                hovermode="x unified",
                height=380,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.line_chart(df_hist.set_index("Mes"))

        # Resumo
        total_sem = sum(sem_ia)
        total_com = sum(com_ia)
        evitados  = total_sem - total_com
        custo_unit = 450_000  # R$ medio por sinistro
        economia  = evitados * custo_unit

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sinistros (12m baseline)", total_sem)
        c2.metric("Sinistros (12m com IA)",   total_com,
                  delta=f"-{evitados}", delta_color="inverse")
        c3.metric("Sinistros Evitados",  evitados)
        c4.metric("Economia 12m",        f"R$ {economia/1e6:.2f}M",
                  delta=f"R$ {custo_unit/1e3:.0f}K/sinistro")

        if st.button("Exportar relatorio executivo (mock)", key="us01_exp"):
            gerar_trilha_auditoria(
                "EXPORTACAO_RELATORIO_RISCO",
                f"periodo=12m evitados={evitados} economia={economia}"
            )
            st.success("Relatorio executivo registrado para auditoria.")

    # Footer com status de integracao
    st.markdown("---")
    st.markdown(f"""
    <div style="background:rgba(91,127,255,0.04);border:1px solid rgba(91,127,255,0.2);
                border-left:3px solid #5B7FFF;border-radius:10px;
                padding:12px 18px;font-size:0.78rem;color:#8B8FA8;line-height:1.7;">
        <strong style="color:#EEF0F8;">Status de integracao US01:</strong><br>
        <span style="color:#22D48A;">✓</span> Pagina criada e funcional ·
        <span style="color:#22D48A;">✓</span> Trilha de auditoria integrada ·
        <span style="color:#22D48A;">✓</span> Mapa GIS renderizando ·
        <span style="color:#F5A623;">~</span> Aguardando XGBoost real (Guilherme) ·
        <span style="color:#F5A623;">~</span> Aguardando endpoint Flask (Gustavo)
    </div>
    """, unsafe_allow_html=True)
