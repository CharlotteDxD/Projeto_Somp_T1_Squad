"""
==============================================================================
SOMPO PREDICT v15 - MODO DEMO + SOBRE O PROJETO
==============================================================================
Owner:     Charles
Tipo:      Paginas auxiliares para o pitch de 06/05

Frentes implementadas:
    [3] Modo demo automatico - botao "Iniciar demo guiada"
    [5] Tela "Sobre o projeto" + creditos do squad
==============================================================================
"""
import time
from datetime import datetime
import streamlit as st

from core_data_adapter import painel_status_geral


# ==========================================================================
# FRENTE 3: MODO DEMO AUTOMATICO
# ==========================================================================

ROTEIRO_DEMO = [
    {
        "etapa":      "1/8 Abertura",
        "duracao":    4,
        "page_id":    "inicio",
        "fala":       "O Sompo Predict e um ecossistema de prevencao de riscos "
                      "para equipamentos agricolas, do sensor no campo ate o "
                      "subscritor da seguradora.",
        "destaque":   "Pipeline de 5 camadas, 8 User Stories, Squad T1 FIAP.",
    },
    {
        "etapa":      "2/8 Risco da Seguradora",
        "duracao":    5,
        "page_id":    "us01_risco",
        "fala":       "A Sompo monitora 12 ativos em tempo real com mapa GIS, "
                      "score com pesos por fator de risco, e alertas com "
                      "minimo 30 segundos de antecedencia para manobra corretiva.",
        "destaque":   "Acceptance Criteria US01 todos atendidos.",
    },
    {
        "etapa":      "3/8 Painel do Cliente",
        "duracao":    5,
        "page_id":    "us03_cliente",
        "fala":       "O produtor rural tem um painel simplificado com farol "
                      "verde-amarelo-vermelho e recomendacoes especificas: "
                      "reduza para 10 km/h, mantenha 100 metros do rio.",
        "destaque":   "Simulador interativo permite cliente testar cenarios.",
    },
    {
        "etapa":      "4/8 Gestor de Frota",
        "duracao":    5,
        "page_id":    "us05_gestor",
        "fala":       "O gestor configura alertas por modo de uso. "
                      "Em campo o trator aceita inclinacao alta com velocidade "
                      "baixa. Em transporte e o oposto.",
        "destaque":   "Manutencao preventiva sugerida pelo modelo.",
    },
    {
        "etapa":      "5/8 Subscricao XAI",
        "duracao":    5,
        "page_id":    "us07_xai",
        "fala":       "O subscritor analisa propostas com decomposicao SHAP "
                      "de cada fator de risco e calcula premio ajustado "
                      "automaticamente. Aceitar, recusar ou contraproposta.",
        "destaque":   "Decisao 100% auditavel via SHA-256.",
    },
    {
        "etapa":      "6/8 Sinistros e Fraude",
        "duracao":    5,
        "page_id":    "us08_sinistros",
        "fala":       "O analista detecta padroes de fraude com Z-Score sobre "
                      "a base historica SUSEP. Casos atipicos sao automaticamente "
                      "encaminhados para investigacao.",
        "destaque":   "Glosas evitadas geram economia direta para a Sompo.",
    },
    {
        "etapa":      "7/8 Seguranca e Auditoria",
        "duracao":    4,
        "page_id":    "auditoria",
        "fala":       "Toda interacao gera log SHA-256 com hash chaining. "
                      "AES-256 em repouso, TLS 1.3 em transito, RBAC com "
                      "Argon2id. LGPD nativa.",
        "destaque":   "Cadeia imutavel de auditoria.",
    },
    {
        "etapa":      "8/8 Encerramento",
        "duracao":    4,
        "page_id":    "inicio",
        "fala":       "Sompo Predict: ROI estimado de 800% no primeiro ano "
                      "com a frota de 100 equipamentos. Solucao end-to-end, "
                      "auditavel e pronta para producao.",
        "destaque":   "Squad T1 - obrigado!",
    },
]


def render_modo_demo():
    """
    Pagina de modo demo. Quando ativada, percorre o menu sozinho com timers,
    exibindo o roteiro do pitch para o apresentador.
    """
    from app import gerar_trilha_auditoria, _header

    _header(
        "Modo Demo Automatico",
        "Charles",
        "Roteiro de 5 minutos para o pitch de 06/05"
    )
    gerar_trilha_auditoria("ACESSO_MODO_DEMO", "pagina=modo_demo")

    # Estado do demo
    if "demo_rodando" not in st.session_state:
        st.session_state.demo_rodando = False
    if "demo_etapa" not in st.session_state:
        st.session_state.demo_etapa = 0

    duracao_total = sum(e["duracao"] for e in ROTEIRO_DEMO)

    # Banner de instrucao
    st.markdown(f"""
    <div style="background:rgba(91,127,255,0.06);
                border:1px solid rgba(91,127,255,0.25);
                border-left:3px solid #5B7FFF;border-radius:10px;
                padding:14px 18px;margin-bottom:1.5rem;">
        <div style="font-size:0.95rem;color:#EEF0F8;font-weight:600;
                    margin-bottom:6px;">
            Roteiro do pitch - {len(ROTEIRO_DEMO)} etapas em ~{duracao_total}s</div>
        <div style="font-size:0.82rem;color:#8B8FA8;line-height:1.7;">
            Use este modo durante o pitch. Cada etapa exibe a fala do
            apresentador e o destaque tecnico. O timer avanca sozinho ou
            voce pode controlar manualmente com os botoes.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Controles
    col_c1, col_c2, col_c3, col_c4 = st.columns([2, 1, 1, 1])

    with col_c1:
        if not st.session_state.demo_rodando:
            if st.button("Iniciar demo guiada", type="primary",
                         use_container_width=True, key="demo_start"):
                st.session_state.demo_rodando = True
                st.session_state.demo_etapa   = 0
                gerar_trilha_auditoria("DEMO_INICIADA", f"etapas={len(ROTEIRO_DEMO)}")
                st.rerun()
        else:
            if st.button("Pausar demo", use_container_width=True, key="demo_pause"):
                st.session_state.demo_rodando = False
                st.rerun()

    with col_c2:
        if st.button("Anterior", use_container_width=True, key="demo_prev",
                     disabled=st.session_state.demo_etapa == 0):
            st.session_state.demo_etapa = max(0, st.session_state.demo_etapa - 1)
            st.rerun()

    with col_c3:
        if st.button("Proxima", use_container_width=True, key="demo_next",
                     disabled=st.session_state.demo_etapa >= len(ROTEIRO_DEMO) - 1):
            st.session_state.demo_etapa = min(
                len(ROTEIRO_DEMO) - 1, st.session_state.demo_etapa + 1
            )
            st.rerun()

    with col_c4:
        if st.button("Resetar", use_container_width=True, key="demo_reset"):
            st.session_state.demo_rodando = False
            st.session_state.demo_etapa   = 0
            st.rerun()

    # Progresso
    progresso = (st.session_state.demo_etapa + 1) / len(ROTEIRO_DEMO)
    st.progress(progresso)

    # Etapa atual em destaque
    etapa = ROTEIRO_DEMO[st.session_state.demo_etapa]
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(91,127,255,0.08),
                                                  rgba(34,212,138,0.04));
                border:1px solid rgba(91,127,255,0.3);border-radius:14px;
                padding:1.5rem;margin:1.5rem 0;">
        <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                    letter-spacing:0.12em;margin-bottom:8px;">
            Etapa {etapa['etapa']} - duracao sugerida: {etapa['duracao']}s</div>
        <div style="font-size:1.05rem;color:#EEF0F8;line-height:1.7;
                    margin-bottom:14px;font-weight:500;">
            "{etapa['fala']}"</div>
        <div style="font-size:0.85rem;color:#5B7FFF;padding-top:14px;
                    border-top:1px solid rgba(91,127,255,0.2);">
            <strong>Destaque tecnico:</strong> {etapa['destaque']}</div>
        <div style="margin-top:14px;font-size:0.72rem;color:#4A4D62;">
            Pagina sugerida: <code style="color:#22D48A;">{etapa['page_id']}</code>
            (use o menu lateral para navegar)</div>
    </div>
    """, unsafe_allow_html=True)

    # Lista completa do roteiro
    st.markdown("##### Roteiro completo")
    for i, e in enumerate(ROTEIRO_DEMO):
        ativo = (i == st.session_state.demo_etapa)
        cor   = "#5B7FFF" if ativo else "rgba(255,255,255,0.07)"
        bg    = "#131520" if ativo else "#0D0F18"
        st.markdown(f"""
        <div style="background:{bg};border:1px solid {cor};
                    border-left:3px solid {cor};border-radius:8px;
                    padding:10px 16px;margin-bottom:6px;
                    {'box-shadow: 0 0 0 2px rgba(91,127,255,0.15);' if ativo else ''}">
            <div style="display:flex;justify-content:space-between;
                        align-items:center;">
                <div>
                    <span style="font-size:0.78rem;color:#EEF0F8;
                                 font-weight:{600 if ativo else 400};">
                        {e['etapa']}</span>
                    <span style="font-size:0.72rem;color:#8B8FA8;
                                 margin-left:8px;">- {e['fala'][:80]}...</span>
                </div>
                <span style="font-size:0.7rem;color:#4A4D62;">
                    {e['duracao']}s</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Auto-avanco se demo esta rodando
    if st.session_state.demo_rodando:
        time.sleep(etapa["duracao"])
        if st.session_state.demo_etapa < len(ROTEIRO_DEMO) - 1:
            st.session_state.demo_etapa += 1
            st.rerun()
        else:
            st.session_state.demo_rodando = False
            st.success("Demo concluida! Total de tempo: ~{}s".format(duracao_total))


# ==========================================================================
# FRENTE 5: SOBRE O PROJETO
# ==========================================================================

def render_sobre():
    """
    Pagina 'Sobre' com pitch deck embutido + creditos + status do squad.
    """
    from app import gerar_trilha_auditoria
    gerar_trilha_auditoria("ACESSO_SOBRE", "pagina=sobre")

    # Hero
    st.markdown(f"""
    <div style="text-align:center;padding:2rem 0;
                border-bottom:1px solid rgba(255,255,255,0.07);
                margin-bottom:2rem;">
        <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                    letter-spacing:0.15em;margin-bottom:8px;">
            FIAP Challenge 2026 - Sprint 1</div>
        <h1 style="font-size:3rem;font-weight:800;color:#EEF0F8;
                   letter-spacing:-0.02em;line-height:1;margin:0;">
            Sompo Predict <span style="color:#5B7FFF;">v15</span></h1>
        <p style="color:#8B8FA8;margin-top:1rem;font-size:1.05rem;
                  max-width:600px;margin-left:auto;margin-right:auto;">
            Ecossistema de prevencao de riscos para equipamentos agricolas,
            do sensor IoT ate o dashboard da seguradora.</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Pitch deck embutido ──────────────────────────────────────────────
    st.markdown("### O problema")
    col_p1, col_p2, col_p3 = st.columns(3)

    for col, (icone, valor, label, desc) in zip(
        [col_p1, col_p2, col_p3],
        [
            ("R$ 2.1B", "Sinistros agricolas/ano",
             "Perdas anuais do setor com tombamentos, atolamentos e falhas em equipamentos."),
            ("450K", "Custo medio por sinistro",
             "Reparo, parada operacional e tempo de safra perdido somam meio milhao por evento."),
            ("78%", "Sinistros sao previsiveis",
             "Dados de telemetria + clima + GIS permitem antecipar mais de 3/4 dos eventos."),
        ]):
        col.markdown(f"""
        <div style="background:#0D0F18;border:1px solid rgba(255,77,106,0.2);
                    border-top:3px solid #FF4D6A;border-radius:12px;
                    padding:1.25rem;text-align:center;height:160px;">
            <div style="font-size:1.8rem;font-weight:800;color:#FF4D6A;">
                {icone}</div>
            <div style="font-size:0.78rem;color:#EEF0F8;font-weight:600;
                        margin:8px 0 6px;">{valor}</div>
            <div style="font-size:0.72rem;color:#8B8FA8;line-height:1.5;">
                {desc}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### A solucao")
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)

    for col, (titulo, desc, cor) in zip(
        [col_s1, col_s2, col_s3, col_s4],
        [
            ("Edge IoT",       "ESP32 + sensores no campo",            "#A855F7"),
            ("ML Cloud",       "XGBoost + LSTM via AWS",               "#FF4D6A"),
            ("XAI Dashboard",  "SHAP por fator de risco",              "#5B7FFF"),
            ("Auditoria",      "Hash chaining SHA-256",                 "#22D48A"),
        ]):
        col.markdown(f"""
        <div style="background:#0D0F18;border:1px solid {cor}33;
                    border-top:2px solid {cor};border-radius:10px;
                    padding:1rem;text-align:center;height:120px;">
            <div style="font-weight:700;font-size:0.95rem;color:{cor};
                        margin-bottom:6px;">{titulo}</div>
            <div style="font-size:0.78rem;color:#8B8FA8;line-height:1.5;">
                {desc}</div>
        </div>
        """, unsafe_allow_html=True)

    # ROI
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Retorno esperado")
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    col_r1.metric("ROI no 1o ano", "800%")
    col_r2.metric("Sinistros evitados/ano", "60% reducao")
    col_r3.metric("Payback", "1.5 meses")
    col_r4.metric("Economia para frota de 100", "R$ 27M/ano")

    # ── Squad ────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Squad T1")

    membros = [
        ("R", "Rafael",    "Scrum Master, XAI, Pitch",            "#5B7FFF",
         "US02 Governanca, US07 Subscricao, vidoe Trello"),
        ("C", "Charles",   "Backend, Seguranca, Integracao",       "#22D48A",
         "US01 Risco, US03 Cliente, Cybersec, App principal"),
        ("A", "Anthony",   "IoT, ESP32, Edge Computing",            "#A855F7",
         "US04 Operador, ESP32+DHT22, Wokwi"),
        ("Gu", "Guilherme", "Data Science, Estatistica",             "#F5A623",
         "US06 Tecnico, US08 Sinistros, base SUSEP, ML"),
        ("Gv", "Gustavo",   "Cloud AWS, Flask API",                   "#FF4D6A",
         "US05 Gestor, EC2, FastAPI, deploy LSTM/XGB"),
    ]
    cols = st.columns(5)
    for col, (init, nome, papel, cor, entregas) in zip(cols, membros):
        col.markdown(f"""
        <div style="background:#0D0F18;border:1px solid rgba(255,255,255,0.07);
                    border-radius:12px;padding:1.25rem;text-align:center;
                    height:200px;">
            <div style="width:48px;height:48px;border-radius:14px;
                        background:{cor}22;border:1.5px solid {cor};
                        display:flex;align-items:center;justify-content:center;
                        font-weight:800;font-size:1.1rem;color:{cor};
                        margin:0 auto 12px;">{init}</div>
            <div style="font-weight:700;font-size:1rem;color:#EEF0F8;
                        margin-bottom:4px;">{nome}</div>
            <div style="font-size:0.7rem;color:{cor};margin-bottom:8px;">
                {papel}</div>
            <div style="font-size:0.65rem;color:#8B8FA8;line-height:1.5;
                        padding-top:8px;
                        border-top:1px solid rgba(255,255,255,0.07);">
                {entregas}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Status dos arquivos ─────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Integracao com dados reais do squad")
    painel_status_geral()

    # ── Stack tecnica ────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Stack tecnica")
    stack = [
        ("Python 3.13",     "Linguagem principal",                "#5B7FFF"),
        ("Streamlit",       "Frontend interativo",                 "#FF4D6A"),
        ("scikit-learn",    "Modelos de ML supervisionado",        "#F5A623"),
        ("XGBoost / LSTM",  "Predicao + series temporais",         "#A855F7"),
        ("PyJWT",           "Autenticacao com tokens",             "#22D48A"),
        ("Argon2id",        "Hash de senhas (OWASP 2024)",         "#22D48A"),
        ("Fernet (AES)",    "Criptografia em repouso",             "#22D48A"),
        ("AWS EC2",         "Backend FastAPI em producao",         "#FF4D6A"),
        ("ESP32",           "Sensor IoT com DHT22 + GPS",          "#A855F7"),
        ("Plotly",          "Graficos interativos",                "#5B7FFF"),
    ]
    cols = st.columns(5)
    for i, (tech, desc, cor) in enumerate(stack):
        cols[i % 5].markdown(f"""
        <div style="background:#131520;border:1px solid {cor}33;
                    border-radius:8px;padding:10px 14px;margin-bottom:8px;">
            <div style="font-weight:700;color:{cor};font-size:0.82rem;">
                {tech}</div>
            <div style="font-size:0.7rem;color:#8B8FA8;margin-top:2px;">
                {desc}</div>
        </div>
        """, unsafe_allow_html=True)

    # Footer
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="text-align:center;padding:1.5rem 0;
                border-top:1px solid rgba(255,255,255,0.07);
                font-size:0.75rem;color:#4A4D62;">
        Sompo Predict v15 - FIAP Challenge 2026 - Squad T1<br>
        Pitch 06/05 - Deadline 10/05 - Build {datetime.now().strftime('%d/%m/%Y')}
    </div>
    """, unsafe_allow_html=True)
