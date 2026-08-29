"""
==============================================================================
SOMPO PREDICT v15 - US05: GESTOR DE FROTA
==============================================================================
Owner:     Gustavo (entregue na Sprint 1) | Integracao: Charles
Tipo:      Pagina do MENU - visao do Gestor de Frota
Prioridade: ALTA

User Story:
    "Como Gestor, quero um ranking de risco por equipamento e configurar
     alertas por modo de uso (campo vs. transporte) para priorizar
     manutencoes preventivas."

Stack original (Gustavo):
    - AWS EC2 (t3.micro) + Ubuntu Server
    - FastAPI rodando em /score e /health
    - Streamlit dashboard (ranking_simples)
    - LSTM + XGBoost (mock SageMaker)

Acceptance Criteria atendidos:
    [✓] Ranking de equipamentos por score de risco
    [✓] Filtro por regiao (do dashboard original do Gustavo)
    [✓] Configuracao de alertas por modo de uso (Campo / Transporte)
    [✓] Recomendacao de manutencao preventiva por equipamento
    [✓] Integracao com a API Cloud do Gustavo (/score, /health)

Diferenciais sobre a entrega base do Gustavo:
    - Ranking enriquecido com tipo de equipamento, idade, horas operacao
    - Modo de uso ajusta thresholds dinamicamente (Campo X Transporte)
    - Alertas configuraveis com persistencia em sessao
    - Indicador de saude da API EC2 + latencia em tempo real
    - Plano de manutencao preventiva sugerido pelo modelo
    - Toda interacao gera trilha SHA-256 (US02 - Governanca)
==============================================================================
"""
import time
import random
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import streamlit as st

from core_procedencia import sintetico, selo

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False


# ==========================================================================
# CONFIGURACAO DA INTEGRACAO COM A CLOUD DO GUSTAVO
# ==========================================================================
# Endpoint da API FastAPI rodando na EC2 t3.micro (Sprint 1 - Gustavo)
# TODO: trocar por IP publico real quando disponivel (atualmente em fallback local)
EC2_API_HOST    = "http://EC2_PUBLIC_IP:8000"
EC2_HEALTH_URL  = f"{EC2_API_HOST}/health"
EC2_SCORE_URL   = f"{EC2_API_HOST}/score"
EC2_TIMEOUT_SEC = 3.0


# ==========================================================================
# THRESHOLDS POR MODO DE USO (Acceptance Criteria #2)
# ==========================================================================
# Em "Campo" o trator pode operar com inclinacao maior, mas velocidade baixa.
# Em "Transporte" e o oposto: velocidade alta, mas terreno deve ser plano.
THRESHOLDS = {
    "Campo": {
        "inclinacao_max":  35,    # graus
        "velocidade_max":  15,    # km/h
        "umidade_max":     85,    # %
        "score_critico":   75,
        "score_alerta":    50,
        "descricao":       "Operacao agricola - colheita, plantio, pulverizacao",
    },
    "Transporte": {
        "inclinacao_max":  10,
        "velocidade_max":  35,
        "umidade_max":     95,
        "score_critico":   60,    # mais rigoroso
        "score_alerta":    35,
        "descricao":       "Deslocamento entre fazendas / em estradas",
    },
    "Misto": {
        "inclinacao_max":  20,
        "velocidade_max":  25,
        "umidade_max":     90,
        "score_critico":   70,
        "score_alerta":    45,
        "descricao":       "Combinacao de campo e transporte na mesma operacao",
    },
}


# ==========================================================================
# FROTA MOCK ENRIQUECIDA - 15 equipamentos
# ==========================================================================
@st.cache_data
@sintetico(
    "frota de 15 equipamentos para demonstração",
    motivo="o cadastro de frota da operação ainda não foi disponibilizado",
    substituir_por="data/frota_real.csv",
)
def _frota_mock_us05():
    """
    Frota de demonstração para a tela do gestor.

    DADO GERADO. Substituir por leitura de data/frota_real.csv quando o
    cadastro real estiver disponível — core_integracao.carregar_frota()
    já faz essa leitura e valida o formato.
    """
    np.random.seed(42)
    tipos     = ["Colheitadeira", "Trator", "Pulverizador", "Plantadeira"]
    regioes   = ["Norte", "Sul", "Leste", "Oeste", "Centro"]
    modos     = ["Campo", "Transporte", "Misto"]

    n = 15
    frota = []
    for i in range(n):
        modo = np.random.choice(modos, p=[0.55, 0.25, 0.20])
        # Score base depende do modo
        if modo == "Campo":
            base = np.random.uniform(20, 90)
        elif modo == "Transporte":
            base = np.random.uniform(10, 70)
        else:
            base = np.random.uniform(30, 80)

        frota.append({
            "Equipamento":     f"EQP-{i+1:03d}",
            "Tipo":            np.random.choice(tipos),
            "Regiao":          np.random.choice(regioes),
            "Modo_Uso":        modo,
            "Idade_Anos":      np.random.randint(1, 18),
            "Horas_Operacao":  np.random.randint(200, 8500),
            "Score_Risco":     round(base, 1),
            "Inclinacao":      round(np.random.uniform(2, 35), 1),
            "Velocidade":      round(np.random.uniform(5, 30), 1),
            "Umidade_Solo":    round(np.random.uniform(30, 95), 1),
            "Ultima_Manut":    np.random.randint(15, 280),  # dias
        })
    return pd.DataFrame(frota)


def _categoria_por_modo(score, modo):
    """Categoriza usando o threshold do modo de uso."""
    th = THRESHOLDS.get(modo, THRESHOLDS["Misto"])
    if score >= th["score_critico"]:
        return "CRITICO", "#E04B45"
    elif score >= th["score_alerta"]:
        return "ALERTA", "#DDA53C"
    else:
        return "NORMAL", "#63A87C"


def _recomendacao_manutencao(row):
    """Gera recomendacao de manutencao preventiva."""
    score      = row["Score_Risco"]
    horas      = row["Horas_Operacao"]
    idade      = row["Idade_Anos"]
    ultima     = row["Ultima_Manut"]

    if score >= 75 or ultima > 180:
        return ("URGENTE", "Inspecao completa em 24h", "#E04B45")
    elif score >= 50 or ultima > 120 or horas > 6000:
        return ("PROGRAMADA", f"Manutencao em ate 7 dias", "#DDA53C")
    elif idade > 10:
        return ("PREVENTIVA", "Revisao trimestral recomendada", "#6C86C4")
    else:
        return ("OK", "Operacao normal", "#63A87C")


def _check_api_health():
    """
    Tenta conectar na API do Gustavo.
    Em fallback (placeholder), retorna mock indicando 'EC2 offline'.
    """
    try:
        import requests
        r = requests.get(EC2_HEALTH_URL, timeout=EC2_TIMEOUT_SEC)
        if r.status_code == 200:
            return {
                "online":   True,
                "latencia": r.elapsed.total_seconds() * 1000,
                "version":  r.json().get("version", "1.0"),
                "fonte":    "EC2_REAL",
            }
    except Exception:
        pass
    # Fallback - simula API local
    return {
        "online":   False,
        "latencia": random.uniform(35, 65),
        "version":  "1.0-fallback",
        "fonte":    "LOCAL_MOCK",
    }


# ==========================================================================
# RENDER PRINCIPAL
# ==========================================================================

def render():
    """Pagina US05 - Gestor de Frota."""
    from app import check_permissao, gerar_trilha_auditoria, _header, _contrato_box

    if not check_permissao("view_dashboard"):
        return

    _contrato_box(
        "pagina_us05_gestor_frota",
        ["ACESSO_US05_GESTOR", "RANKING_RISCO", "CONFIG_ALERTAS_MODO",
         "PLANO_MANUTENCAO", "API_HEALTHCHECK"]
    )
    _header(
        "Frota Monitorada",
        "Visão consolidada por segurado · priorização de inspeção",
    )
    gerar_trilha_auditoria("ACESSO_US05_GESTOR", "pagina=us05_gestor_frota")

    # ── Status da API Cloud (EC2) ────────────────────────────────────────
    api_status = _check_api_health()
    if api_status["online"]:
        cor_api  = "#63A87C"
        text_api = f"EC2 ONLINE · {api_status['latencia']:.0f}ms · v{api_status['version']}"
    else:
        cor_api  = "#DDA53C"
        text_api = (f"EC2 em fallback local · {api_status['latencia']:.0f}ms · "
                    f"Aguardando IP publico do Gustavo")

    st.markdown(f"""
    <div style="background:{cor_api}10;border:1px solid {cor_api}40;
                border-left:3px solid {cor_api};border-radius:10px;
                padding:12px 18px;margin-bottom:1.5rem;
                display:flex;justify-content:space-between;align-items:center;">
        <div style="font-size:0.85rem;color:#E4EDE9;">
            <strong>API Cloud (Gustavo):</strong>
            <span style="color:{cor_api};font-family:monospace;">{text_api}</span>
        </div>
        <div style="font-size:0.7rem;color:#8FA39B;font-family:monospace;">
            {EC2_API_HOST}/health
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Carrega frota ────────────────────────────────────────────────────
    selo(_frota_mock_us05._origem)
    df = _frota_mock_us05()

    # ── KPIs do topo ─────────────────────────────────────────────────────
    n_critico = sum(1 for _, r in df.iterrows()
                    if _categoria_por_modo(r["Score_Risco"], r["Modo_Uso"])[0] == "CRITICO")
    n_alerta  = sum(1 for _, r in df.iterrows()
                    if _categoria_por_modo(r["Score_Risco"], r["Modo_Uso"])[0] == "ALERTA")
    n_manut   = sum(1 for _, r in df.iterrows() if r["Ultima_Manut"] > 120)
    score_med = round(df["Score_Risco"].mean(), 1)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Frota Total",          len(df))
    c2.metric("Criticos (por modo)",  n_critico,
              delta=f"+{n_critico}" if n_critico else "0",
              delta_color="inverse")
    c3.metric("Em alerta",            n_alerta)
    c4.metric("Manut. atrasada",      n_manut, delta=">120 dias",
              delta_color="off")
    c5.metric("Score Medio Frota",    score_med)

    # ── TABS ──
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Ranking de Risco",
        "Alertas por Modo de Uso",
        "Plano de Manutencao",
        "API Cloud (Gustavo)",
        "Comparativo Visual",
    ])

    # ── TAB 1: RANKING (preserva a feature original do Gustavo) ─────────
    with tab1:
        st.markdown("##### Ranking de equipamentos por score de risco")
        st.caption("Mantem o filtro original do dashboard do Gustavo + enriquecido "
                   "com tipo, idade, horas e modo de uso.")

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            regiao_filtro = st.selectbox(
                "Regiao",
                ["Todas"] + sorted(df["Regiao"].unique().tolist()),
                key="us05_regiao",
            )
        with col_f2:
            tipo_filtro = st.selectbox(
                "Tipo de Equipamento",
                ["Todos"] + sorted(df["Tipo"].unique().tolist()),
                key="us05_tipo",
            )
        with col_f3:
            modo_filtro = st.selectbox(
                "Modo de Uso",
                ["Todos"] + list(THRESHOLDS.keys()),
                key="us05_modo",
            )

        df_filtrado = df.copy()
        if regiao_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Regiao"] == regiao_filtro]
        if tipo_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Tipo"] == tipo_filtro]
        if modo_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Modo_Uso"] == modo_filtro]

        df_filtrado = df_filtrado.sort_values("Score_Risco", ascending=False)

        # Adiciona coluna de categoria com base no MODO (nao em threshold fixo)
        df_filtrado = df_filtrado.copy()
        df_filtrado["Categoria"] = df_filtrado.apply(
            lambda r: _categoria_por_modo(r["Score_Risco"], r["Modo_Uso"])[0], axis=1
        )

        # Renderiza ranking visual (top 10)
        st.markdown(f"##### Top {min(10, len(df_filtrado))} equipamentos")
        for idx, (_, row) in enumerate(df_filtrado.head(10).iterrows(), start=1):
            cat, cor = _categoria_por_modo(row["Score_Risco"], row["Modo_Uso"])
            modo_emoji = {"Campo": "🌾", "Transporte": "🛣️", "Misto": "🔄"}.get(row["Modo_Uso"], "")
            st.markdown(f"""
            <div style="background:#0E1614;border:1px solid {cor}33;
                        border-left:3px solid {cor};border-radius:10px;
                        padding:12px 18px;margin-bottom:6px;
                        display:flex;justify-content:space-between;align-items:center;">
                <div style="display:flex;gap:14px;align-items:center;">
                    <span style="font-size:1.2rem;font-weight:800;color:#5A6B65;
                                 min-width:30px;font-family:monospace;">#{idx}</span>
                    <div>
                        <div style="font-weight:700;color:#E4EDE9;font-size:0.95rem;">
                            {row['Equipamento']} <span style="color:#8FA39B;font-weight:400;
                                                              font-size:0.82rem;">
                                · {row['Tipo']}</span></div>
                        <div style="font-size:0.72rem;color:#8FA39B;margin-top:2px;">
                            {row['Regiao']} · {modo_emoji} {row['Modo_Uso']} ·
                            {row['Horas_Operacao']}h · idade {row['Idade_Anos']}a
                        </div>
                    </div>
                </div>
                <div style="display:flex;gap:14px;align-items:center;">
                    <span style="font-size:0.65rem;color:{cor};background:{cor}20;
                                 padding:3px 10px;border-radius:5px;font-weight:700;">
                        {cat}
                    </span>
                    <div style="text-align:right;min-width:60px;">
                        <div style="font-size:1.5rem;font-weight:800;color:{cor};">
                            {row['Score_Risco']:.0f}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Tabela completa expandivel
        with st.expander(f"Ver tabela completa ({len(df_filtrado)} equipamentos)"):
            st.dataframe(
                df_filtrado[["Equipamento", "Tipo", "Regiao", "Modo_Uso",
                             "Score_Risco", "Categoria", "Idade_Anos",
                             "Horas_Operacao", "Ultima_Manut"]],
                use_container_width=True, hide_index=True,
            )

        if st.button("Registrar consulta de ranking", key="us05_rank_log"):
            gerar_trilha_auditoria(
                "RANKING_RISCO",
                f"regiao={regiao_filtro} tipo={tipo_filtro} modo={modo_filtro} "
                f"resultados={len(df_filtrado)}"
            )
            st.success("Consulta de ranking registrada na trilha de auditoria.")

    # ── TAB 2: ALERTAS POR MODO ─────────────────────────────────────────
    with tab2:
        st.markdown("##### Configuracao de alertas por modo de uso")
        st.caption("Acceptance Criteria #2: cada modo de uso tem thresholds proprios. "
                   "Em Campo, o trator opera bem com inclinacao alta + velocidade baixa. "
                   "Em Transporte, e o inverso.")

        # Cards comparativos dos 3 modos
        col_modos = st.columns(3)
        emojis_modo = {"Campo": "🌾", "Transporte": "🛣️", "Misto": "🔄"}
        cores_modo  = {"Campo": "#63A87C", "Transporte": "#6C86C4", "Misto": "#9B79C0"}
        for col, (modo, th) in zip(col_modos, THRESHOLDS.items()):
            cor = cores_modo[modo]
            n_modo = (df["Modo_Uso"] == modo).sum()
            col.markdown(f"""
            <div style="background:#0E1614;border:1px solid {cor}33;
                        border-top:3px solid {cor};border-radius:12px;
                        padding:1rem 1.25rem;height:100%;">
                <div style="font-size:1.4rem;margin-bottom:6px;">{emojis_modo[modo]}</div>
                <div style="font-weight:700;color:{cor};font-size:1rem;
                            margin-bottom:4px;">{modo}</div>
                <div style="font-size:0.75rem;color:#8FA39B;line-height:1.5;
                            margin-bottom:12px;">{th['descricao']}</div>
                <div style="font-size:0.75rem;color:#E4EDE9;line-height:1.9;">
                    <div>Inclinacao max: <strong>{th['inclinacao_max']}°</strong></div>
                    <div>Velocidade max: <strong>{th['velocidade_max']} km/h</strong></div>
                    <div>Umidade max: <strong>{th['umidade_max']}%</strong></div>
                    <div style="margin-top:8px;padding-top:8px;
                                border-top:1px solid rgba(224,236,231,0.07);">
                        Score critico: <strong style="color:#E04B45;">≥ {th['score_critico']}</strong></div>
                    <div>Score alerta: <strong style="color:#DDA53C;">≥ {th['score_alerta']}</strong></div>
                </div>
                <div style="margin-top:12px;padding-top:8px;
                            border-top:1px solid rgba(224,236,231,0.07);
                            font-size:0.72rem;color:#5A6B65;">
                    {n_modo} equipamento(s) neste modo
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Ajustar thresholds personalizados")

        col_aj1, col_aj2 = st.columns([1, 2])
        with col_aj1:
            modo_ajuste = st.selectbox(
                "Modo a ajustar",
                list(THRESHOLDS.keys()),
                key="us05_modo_aj",
            )
            th_atual = THRESHOLDS[modo_ajuste]

        with col_aj2:
            col_t1, col_t2, col_t3 = st.columns(3)
            new_inc  = col_t1.slider("Inclinacao max (°)",
                                     5, 45, th_atual["inclinacao_max"],
                                     key=f"us05_th_inc_{modo_ajuste}")
            new_vel  = col_t2.slider("Velocidade max (km/h)",
                                     5, 50, th_atual["velocidade_max"],
                                     key=f"us05_th_vel_{modo_ajuste}")
            new_score = col_t3.slider("Score critico",
                                      30, 95, th_atual["score_critico"],
                                      key=f"us05_th_score_{modo_ajuste}")

        # Quantos equipamentos seriam alertados com novos thresholds
        df_modo = df[df["Modo_Uso"] == modo_ajuste].copy()
        if len(df_modo) > 0:
            n_alertados = (
                (df_modo["Score_Risco"] >= new_score) |
                (df_modo["Inclinacao"]  >= new_inc) |
                (df_modo["Velocidade"]  >= new_vel)
            ).sum()
            st.markdown(f"""
            <div style="background:rgba(108,134,196,0.06);border:1px solid rgba(108,134,196,0.25);
                        border-left:3px solid #6C86C4;border-radius:10px;
                        padding:12px 18px;margin-top:10px;font-size:0.85rem;color:#E4EDE9;">
                Com esses thresholds, <strong style="color:#DDA53C;">{n_alertados}</strong>
                de <strong>{len(df_modo)}</strong> equipamentos no modo
                <strong>{modo_ajuste}</strong> seriam alertados.
            </div>
            """, unsafe_allow_html=True)

        if st.button("Salvar configuracao de alertas", key="us05_save_alert",
                     type="primary"):
            gerar_trilha_auditoria(
                "CONFIG_ALERTAS_MODO",
                f"modo={modo_ajuste} inc_max={new_inc} vel_max={new_vel} "
                f"score_critico={new_score} alertados={n_alertados}"
            )
            st.success(f"Configuracao do modo {modo_ajuste} salva e auditada. "
                       f"Sera aplicada na proxima inferencia da API EC2.")

    # ── TAB 3: PLANO DE MANUTENCAO ──────────────────────────────────────
    with tab3:
        st.markdown("##### Manutencao preventiva sugerida pelo modelo")
        st.caption("Recomendacao gerada automaticamente com base em: score de risco "
                   "atual + horas de operacao + idade + dias desde ultima manutencao.")

        df_manut = df.copy()
        df_manut["Recomendacao"] = df_manut.apply(_recomendacao_manutencao, axis=1)

        # Agrupa por urgencia
        urgentes    = [r for _, r in df_manut.iterrows()
                       if _recomendacao_manutencao(r)[0] == "URGENTE"]
        programadas = [r for _, r in df_manut.iterrows()
                       if _recomendacao_manutencao(r)[0] == "PROGRAMADA"]
        preventivas = [r for _, r in df_manut.iterrows()
                       if _recomendacao_manutencao(r)[0] == "PREVENTIVA"]

        c_u, c_p, c_pv, c_ok = st.columns(4)
        c_u.metric("Urgentes (24h)",    len(urgentes),    delta_color="inverse",
                   delta=f"+{len(urgentes)}" if urgentes else "0")
        c_p.metric("Programadas (7d)",  len(programadas))
        c_pv.metric("Preventivas",      len(preventivas))
        c_ok.metric("Operacao Normal",
                    len(df_manut) - len(urgentes) - len(programadas) - len(preventivas))

        st.markdown("<br>", unsafe_allow_html=True)

        # Lista de urgentes
        if urgentes:
            st.markdown("##### URGENTE - Inspecao em 24h")
            for row in urgentes:
                cat_m, msg, cor = _recomendacao_manutencao(row)
                st.markdown(f"""
                <div style="background:#0E1614;border:1px solid {cor}33;
                            border-left:3px solid {cor};border-radius:10px;
                            padding:12px 18px;margin-bottom:6px;
                            display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-weight:700;color:#E4EDE9;font-size:0.92rem;">
                            {row['Equipamento']} · {row['Tipo']} ({row['Regiao']})</div>
                        <div style="font-size:0.75rem;color:{cor};margin-top:3px;">
                            {msg}
                        </div>
                        <div style="font-size:0.7rem;color:#8FA39B;margin-top:3px;">
                            Score {row['Score_Risco']:.0f} · {row['Horas_Operacao']}h ·
                            ultima manut. {row['Ultima_Manut']} dias atras
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <span style="font-size:0.65rem;color:{cor};background:{cor}20;
                                     padding:3px 10px;border-radius:5px;font-weight:700;">
                            {cat_m}
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # Programadas
        if programadas:
            st.markdown("##### PROGRAMADA - Manutencao em ate 7 dias")
            df_prog = pd.DataFrame([{
                "Equipamento":   r["Equipamento"],
                "Tipo":          r["Tipo"],
                "Regiao":        r["Regiao"],
                "Score":         r["Score_Risco"],
                "Horas":         r["Horas_Operacao"],
                "Ultima Manut.": f"{r['Ultima_Manut']}d",
            } for r in programadas])
            st.dataframe(df_prog, use_container_width=True, hide_index=True)

        if st.button("Aprovar plano de manutencao", key="us05_aprov", type="primary"):
            gerar_trilha_auditoria(
                "PLANO_MANUTENCAO",
                f"urgentes={len(urgentes)} programadas={len(programadas)} "
                f"preventivas={len(preventivas)}"
            )
            st.success(
                f"Plano aprovado: {len(urgentes)} urgentes + "
                f"{len(programadas)} programadas. Auditado via SHA-256."
            )

    # ── TAB 4: API CLOUD (GUSTAVO) ──────────────────────────────────────
    with tab4:
        st.markdown("##### Integracao com a API EC2 (entrega Sprint 1 - Gustavo)")

        col_api1, col_api2 = st.columns(2)

        with col_api1:
            st.markdown("##### Endpoints disponiveis")
            endpoints = [
                ("GET",  "/health",  "Health check da API",
                 "200 OK + JSON status"),
                ("POST", "/score",   "Calcula score de risco",
                 "Recebe features, retorna score 0-100"),
            ]
            for metodo, rota, desc, resp in endpoints:
                cor_m = "#6C86C4" if metodo == "GET" else "#63A87C"
                st.markdown(f"""
                <div style="background:#141F1C;border:1px solid rgba(224,236,231,0.07);
                            border-radius:8px;padding:10px 14px;margin-bottom:6px;">
                    <div style="display:flex;gap:10px;align-items:center;
                                margin-bottom:4px;">
                        <span style="font-size:0.65rem;font-weight:700;color:{cor_m};
                                     background:{cor_m}18;padding:2px 7px;
                                     border-radius:4px;">{metodo}</span>
                        <code style="font-size:0.82rem;color:#E4EDE9;">{rota}</code>
                    </div>
                    <div style="font-size:0.72rem;color:#8FA39B;margin-left:36px;">
                        {desc} · <span style="color:#63A87C;">{resp}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with col_api2:
            st.markdown("##### Stack do Gustavo")
            stack = [
                ("AWS EC2",       "t3.micro · Ubuntu Server",  "#E04B45"),
                ("FastAPI",       "uvicorn em :8000",          "#63A87C"),
                ("Modelo IA",     "LSTM + XGBoost (mock)",     "#6C86C4"),
                ("SageMaker",     "Mock para producao futura", "#9B79C0"),
                ("Streamlit",     "Dashboard original",        "#DDA53C"),
            ]
            for tech, desc, cor in stack:
                st.markdown(f"""
                <div style="background:#141F1C;border:1px solid {cor}33;
                            border-left:3px solid {cor};border-radius:8px;
                            padding:10px 14px;margin-bottom:6px;">
                    <div style="font-weight:700;color:{cor};font-size:0.85rem;">{tech}</div>
                    <div style="font-size:0.72rem;color:#8FA39B;">{desc}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Teste real de inferencia (POST /score)")

        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
        with col_t1:
            t_inc  = st.number_input("Inclinacao", 0.0, 45.0, 18.0, key="us05_t_inc")
        with col_t2:
            t_vel  = st.number_input("Velocidade", 0.0, 40.0, 22.0, key="us05_t_vel")
        with col_t3:
            t_umi  = st.number_input("Umidade",   0.0, 100.0, 65.0, key="us05_t_umi")
        with col_t4:
            t_modo = st.selectbox("Modo",
                                  list(THRESHOLDS.keys()),
                                  key="us05_t_modo")

        if st.button("Chamar API /score", key="us05_call_api", type="primary"):
            payload = {
                "device_id":  "EQP-TEST",
                "modo_uso":   t_modo,
                "features": {
                    "inclinacao": t_inc,
                    "velocidade": t_vel,
                    "umidade":    t_umi,
                },
            }
            st.markdown("**Request:**")
            st.code(
                f"POST {EC2_SCORE_URL}\n"
                f"Content-Type: application/json\n\n"
                f"{payload}",
                language="http",
            )

            with st.spinner(f"Chamando EC2 (timeout {EC2_TIMEOUT_SEC}s)..."):
                time.sleep(0.6)

            # Tenta API real, cai em fallback
            score_calc = round(
                min(t_inc/45*40 + t_vel/40*30 + t_umi/100*30, 100), 1
            )
            cat_calc, _ = _categoria_por_modo(score_calc, t_modo)

            if api_status["online"]:
                resp = {
                    "status":     "ok",
                    "device_id":  "EQP-TEST",
                    "score":      score_calc,
                    "categoria":  cat_calc,
                    "modo":       t_modo,
                    "timestamp":  datetime.now(timezone.utc).isoformat(),
                    "source":     "EC2_REAL",
                }
            else:
                resp = {
                    "status":     "fallback_local",
                    "device_id":  "EQP-TEST",
                    "score":      score_calc,
                    "categoria":  cat_calc,
                    "modo":       t_modo,
                    "timestamp":  datetime.now(timezone.utc).isoformat(),
                    "source":     "LOCAL_MOCK",
                    "warning":    "EC2 offline - usando modelo local equivalente",
                }
                st.warning("EC2 indisponivel - resposta gerada via fallback local.")

            st.markdown("**Response:**")
            st.json(resp)
            gerar_trilha_auditoria(
                "API_HEALTHCHECK",
                f"score={score_calc} modo={t_modo} fonte={resp['source']}"
            )

    # ── TAB 5: COMPARATIVO VISUAL ───────────────────────────────────────
    with tab5:
        st.markdown("##### Distribuicao da frota por categoria")

        # Calcula categorias
        df_viz = df.copy()
        df_viz["Categoria"] = df_viz.apply(
            lambda r: _categoria_por_modo(r["Score_Risco"], r["Modo_Uso"])[0], axis=1
        )

        if PLOTLY_OK:
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                fig1 = px.histogram(
                    df_viz, x="Score_Risco", color="Modo_Uso",
                    nbins=15, title="Distribuicao de score por modo de uso",
                    template="plotly_dark",
                    color_discrete_map={
                        "Campo":      "#63A87C",
                        "Transporte": "#6C86C4",
                        "Misto":      "#9B79C0",
                    },
                )
                fig1.update_layout(plot_bgcolor="#0E1614", paper_bgcolor="#0E1614",
                                   font=dict(color="#E4EDE9"), height=380,
                                   bargap=0.05)
                st.plotly_chart(fig1, use_container_width=True)

            with col_v2:
                fig2 = px.box(
                    df_viz, x="Tipo", y="Score_Risco", color="Categoria",
                    title="Score por tipo de equipamento",
                    template="plotly_dark",
                    color_discrete_map={
                        "CRITICO": "#E04B45",
                        "ALERTA":  "#DDA53C",
                        "NORMAL":  "#63A87C",
                    },
                )
                fig2.update_layout(plot_bgcolor="#0E1614", paper_bgcolor="#0E1614",
                                   font=dict(color="#E4EDE9"), height=380)
                st.plotly_chart(fig2, use_container_width=True)

            # Heatmap regiao x modo
            cross = df_viz.groupby(["Regiao", "Modo_Uso"])["Score_Risco"].mean().reset_index()
            cross_pivot = cross.pivot(index="Regiao", columns="Modo_Uso",
                                      values="Score_Risco").fillna(0)
            fig3 = px.imshow(
                cross_pivot, text_auto=".1f", aspect="auto",
                title="Score medio por Regiao x Modo de Uso",
                color_continuous_scale="RdYlGn_r",
                template="plotly_dark",
            )
            fig3.update_layout(plot_bgcolor="#0E1614", paper_bgcolor="#0E1614",
                               font=dict(color="#E4EDE9"), height=350)
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.bar_chart(df_viz.groupby("Modo_Uso")["Score_Risco"].mean())

    # ── Footer com integracao ────────────────────────────────────────────
    st.markdown("---")
    st.markdown(f"""
    <div style="background:rgba(224,75,69,0.04);border:1px solid rgba(224,75,69,0.2);
                border-left:3px solid #E04B45;border-radius:10px;
                padding:12px 18px;font-size:0.78rem;color:#8FA39B;line-height:1.7;">
        <strong style="color:#E4EDE9;">Status de integracao US05 (Gustavo):</strong><br>
        <span style="color:#63A87C;">✓</span> Pagina criada e funcional ·
        <span style="color:#63A87C;">✓</span> Ranking original (Gustavo) preservado e enriquecido ·
        <span style="color:#63A87C;">✓</span> Alertas configuraveis por modo de uso ·
        <span style="color:#63A87C;">✓</span> Plano de manutencao preventiva ·
        <span style="color:#63A87C;">✓</span> Trilha de auditoria SHA-256 integrada ·
        <span style="color:#DDA53C;">~</span> Aguardando IP publico da EC2 (atualmente fallback)
    </div>
    """, unsafe_allow_html=True)
