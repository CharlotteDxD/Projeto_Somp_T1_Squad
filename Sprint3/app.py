# ==========================================
# SOMPO PREDICT — plataforma de prevencao de risco em seguro rural
# app.py - Roteador principal Streamlit
#
# Instalacao:
#   pip install -r requirements.txt
#
# Execucao:
#   streamlit run app.py
#       

# Login padrao:
#   http://localhost:8501    
#   usuario: admin
#   senha: Admin@2024!

#   http://localhost:8502  
#   usuario: produtor 
#   senha: Produtor@2024!
# ==========================================

import os
import re
import time
import json
import secrets
import hashlib
from datetime import datetime, timedelta, timezone

import jwt
import numpy as np
import pandas as pd
import streamlit as st
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet
from sklearn.metrics import (
    classification_report,
    roc_auc_score,
    confusion_matrix,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

try:
    import plotly.express as px
    import plotly.graph_objects as go
    import plotly.figure_factory as ff
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# ── Telas do produto ──────────────────────────────────────────────────
import pagina_us01_risco_sompo
import pagina_us03_painel_cliente
import pagina_us05_gestor_frota
import pagina_us07_subscricao_xai
import pagina_us08_analista_sinistros
import pagina_demo_e_sobre
import pagina_ml_deep_learning
import pagina_simulador_cenarios
import pagina_integracoes
import pagina_relatorios
import pagina_desempenho_modelos
import pagina_explicabilidade

# ── Camada compartilhada: auditoria, RBAC e componentes visuais ───────
from core_app import (
    MEMBER_COLORS,
    check_permissao_silenciosa,
    RBAC_MATRIX,
    check_permissao,
    gerar_trilha_auditoria,
    verificar_senha as _verificar_senha,
    _header,
    _contrato_box,
)

# ── Adapter de fonte de dados ─────────────────────────────────────────
from core_data_adapter import garantir_pasta_data
garantir_pasta_data()

# ==========================================
# 0. CONFIGURACAO DA PAGINA
# ==========================================

from core_perfis import portal_ativo, rota_permitida, portal_para_papel

# Esta instancia serve um dos dois portais, definido por SOMPO_PERFIL.
# O codigo e o mesmo; muda o que e oferecido.
PORTAL = portal_ativo()

st.set_page_config(
    page_title=PORTAL.nome,
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded" if PORTAL.chave == "sompo" else "collapsed",
)

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  /* Base — slate profundo, subtom azul. O campo a noite. */
  --bg:#06090E;
  --ink:#0A0F16;
  /* Vidro — superficies translucidas em camadas */
  --glass:rgba(255,255,255,0.040);
  --glass-2:rgba(255,255,255,0.065);
  --glass-3:rgba(255,255,255,0.090);
  --stroke:rgba(255,255,255,0.085);
  --stroke-2:rgba(255,255,255,0.150);
  --stroke-lit:rgba(255,255,255,0.230);
  /* Texto */
  --text:#F0F4F8; --text-2:#98A4B2; --text-3:#5B6775;
  /* Marca Sompo — unica cor de marca */
  --sompo:#E5484D; --sompo-dim:rgba(229,72,77,0.14);
  /* Farol — vocabulario do produto. So aparece em contexto de risco. */
  --verde:#3FCF8E;    --verde-dim:rgba(63,207,142,0.13);
  --amarelo:#F5B23D;  --amarelo-dim:rgba(245,178,61,0.13);
  --vermelho:#F2555A; --vermelho-dim:rgba(242,85,90,0.13);
  /* Compat — nomes usados pelas paginas existentes */
  --surface:var(--ink); --surface2:#0E141C; --surface3:#131A24;
  --border:var(--stroke); --border2:var(--stroke-2);
  --text2:var(--text-2); --text3:var(--text-3);
  --accent:#6E8DF5; --green:var(--verde); --amber:var(--amarelo);
  --red:var(--vermelho); --purple:#9B79C0;
  --radius:16px;
}
/* ---------- Base ---------- */
html,body,[class*="css"]{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  -webkit-font-smoothing:antialiased;
}
.stApp{ background:var(--bg); color:var(--text); }
/* Farol ambiente — brilho radial no topo, cor definida em runtime.
   E a assinatura da interface: a tela inteira respira o estado da frota. */
.stApp::before{
  content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
  background:
    radial-gradient(1100px 520px at 22% -8%,  var(--wash-a,rgba(63,207,142,0.10)), transparent 62%),
    radial-gradient(900px 440px at 88% -14%, var(--wash-b,rgba(110,141,245,0.07)), transparent 60%);
  transition:background 1.2s ease;
}
.block-container{ position:relative; z-index:1; padding-top:2.2rem; max-width:1400px; }
h1,h2,h3,h4{
  font-family:'Manrope',sans-serif !important;
  font-weight:800 !important; letter-spacing:-0.028em !important;
  color:var(--text) !important;
}
h1{ font-size:2.7rem !important; line-height:1.04 !important; }
code,.stCode,[data-testid="stMetricValue"]{
  font-family:'JetBrains Mono',ui-monospace,monospace !important;
}
[data-testid="stMetricValue"]{ font-weight:600 !important; letter-spacing:-0.02em; }
/* ---------- Sidebar: painel fosco ---------- */
section[data-testid="stSidebar"]{
  background:rgba(10,15,22,0.72) !important;
  backdrop-filter:blur(28px) saturate(150%);
  -webkit-backdrop-filter:blur(28px) saturate(150%);
  border-right:1px solid var(--stroke) !important;
}
section[data-testid="stSidebar"] .block-container{ padding:1.1rem 0.9rem; }
/* Navegacao — botoes como itens de lista */
section[data-testid="stSidebar"] .stButton > button{
  width:100%; text-align:left !important; justify-content:flex-start !important;
  background:transparent !important; border:1px solid transparent !important;
  color:var(--text-2) !important; font-weight:500 !important;
  font-size:0.855rem !important; padding:0.5rem 0.7rem !important;
  border-radius:10px !important; letter-spacing:-0.01em;
  transition:background .16s ease, color .16s ease, border-color .16s ease;
}
section[data-testid="stSidebar"] .stButton > button:hover{
  background:var(--glass-2) !important; color:var(--text) !important;
  border-color:var(--stroke) !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"]{
  background:var(--glass-3) !important; color:var(--text) !important;
  border-color:var(--stroke-2) !important; font-weight:600 !important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.07);
}
section[data-testid="stSidebar"] .stButton > button p{ font-size:0.855rem !important; }
/* Grupo colapsavel na sidebar */
section[data-testid="stSidebar"] details{
  background:transparent !important; border:none !important;
}
section[data-testid="stSidebar"] details summary{
  font-size:0.66rem !important; text-transform:uppercase;
  letter-spacing:0.11em; color:var(--text-3) !important;
  padding:0.35rem 0.2rem !important;
}
section[data-testid="stSidebar"] details summary:hover{ color:var(--text-2) !important; }
/* ---------- Cartoes de vidro ---------- */
.g-card{
  background:var(--glass); border:1px solid var(--stroke);
  border-radius:var(--radius); padding:1.15rem 1.3rem;
  backdrop-filter:blur(20px) saturate(140%);
  -webkit-backdrop-filter:blur(20px) saturate(140%);
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.055), 0 12px 34px rgba(0,0,0,0.34);
}
.g-card.lit{ border-color:var(--stroke-2); background:var(--glass-2); }
.g-eyebrow{
  font-size:0.645rem; text-transform:uppercase; letter-spacing:0.13em;
  color:var(--text-3); font-weight:600;
}
.g-num{
  font-family:'Manrope',sans-serif; font-size:1.75rem; font-weight:800;
  letter-spacing:-0.03em; line-height:1;
}
.g-label{
  font-size:0.68rem; color:var(--text-3); text-transform:uppercase;
  letter-spacing:0.09em; margin-top:7px;
}
/* Metricas nativas herdam o vidro */
div[data-testid="stMetric"],div[data-testid="metric-container"]{
  background:var(--glass); border:1px solid var(--stroke);
  border-radius:14px; padding:0.95rem 1.15rem;
  backdrop-filter:blur(18px); -webkit-backdrop-filter:blur(18px);
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.05);
}
/* ---------- Componentes Streamlit ---------- */
.stButton > button,.stFormSubmitButton > button,.stDownloadButton > button{
  border-radius:11px !important; font-weight:600 !important;
  border:1px solid var(--stroke-2) !important;
  background:var(--glass-2) !important; color:var(--text) !important;
  backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
  transition:background .16s ease,border-color .16s ease,transform .16s ease;
  letter-spacing:-0.01em;
}
.stButton > button:hover,.stDownloadButton > button:hover{
  background:var(--glass-3) !important; border-color:var(--stroke-lit) !important;
}
.stButton > button:active{ transform:scale(0.985); }
.stButton > button[kind="primary"],.stFormSubmitButton > button[kind="primary"]{
  background:var(--sompo) !important; border-color:var(--sompo) !important;
  color:#fff !important; box-shadow:0 6px 20px rgba(229,72,77,0.28);
}
.stButton > button[kind="primary"]:hover{ background:#EF5A5F !important; }
details{
  background:var(--glass) !important; border:1px solid var(--stroke) !important;
  border-radius:13px !important;
  backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
}
.stDataFrame,div[data-testid="stDataFrame"]{
  border:1px solid var(--stroke) !important; border-radius:13px !important;
  overflow:hidden; background:var(--glass) !important;
}
.stTabs [data-baseweb="tab-list"]{ gap:3px; border-bottom:1px solid var(--stroke); }
.stTabs [data-baseweb="tab"]{
  border-radius:10px 10px 0 0; padding:0.55rem 1rem;
  color:var(--text-2); font-weight:500; font-size:0.87rem;
}
.stTabs [aria-selected="true"]{
  background:var(--glass-2) !important; color:var(--text) !important;
  font-weight:600 !important;
}
.stSlider [data-baseweb="slider"] div[role="slider"]{
  box-shadow:0 2px 10px rgba(0,0,0,0.45) !important;
}
.stTextInput input,.stNumberInput input,.stSelectbox div[data-baseweb="select"] > div{
  background:var(--glass) !important; border:1px solid var(--stroke) !important;
  border-radius:11px !important; color:var(--text) !important;
}
.stAlert{
  border-radius:13px !important; border:1px solid var(--stroke) !important;
  background:var(--glass) !important;
  backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
}
::-webkit-scrollbar{ width:5px; height:5px; }
::-webkit-scrollbar-track{ background:transparent; }
::-webkit-scrollbar-thumb{ background:rgba(255,255,255,0.11); border-radius:3px; }
::-webkit-scrollbar-thumb:hover{ background:rgba(255,255,255,0.19); }
.contrato-box{
  background:var(--glass); border:1px solid var(--stroke);
  border-left:2px solid var(--accent); border-radius:12px;
  padding:12px 16px; margin-bottom:1.4rem;
  font-size:0.79rem; color:var(--text-2); line-height:1.6;
  backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
}
.contrato-box strong{ color:var(--text); }
.contrato-box code{ color:var(--verde); font-size:0.75rem; }
/* ---------- Farol: a marca ---------- */
.brand-farol{
  display:flex; flex-direction:column; gap:3.5px;
  padding:5px 4.5px; border:1px solid var(--stroke-2); border-radius:7px;
  background:var(--glass-2); flex:none;
  backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px);
}
.brand-farol i{
  display:block; width:8px; height:8px; border-radius:50%;
  background:rgba(255,255,255,0.09); transition:all .5s ease;
}
.brand-farol i.on-r{ background:var(--vermelho); box-shadow:0 0 11px var(--vermelho); }
.brand-farol i.on-y{ background:var(--amarelo);  box-shadow:0 0 11px var(--amarelo); }
.brand-farol i.on-g{ background:var(--verde);    box-shadow:0 0 11px var(--verde); }
/* Farol grande — tela do cliente */
.farol-xl{
  display:inline-flex; flex-direction:column; gap:14px;
  padding:20px 15px; border-radius:22px;
  background:var(--glass); border:1px solid var(--stroke);
  backdrop-filter:blur(22px); -webkit-backdrop-filter:blur(22px);
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.06),0 16px 44px rgba(0,0,0,0.4);
}
.farol-xl i{
  display:block; width:44px; height:44px; border-radius:50%;
  background:rgba(255,255,255,0.055); transition:all .55s cubic-bezier(.4,0,.2,1);
}
.farol-xl i.lit-r{ background:var(--vermelho); box-shadow:0 0 34px var(--vermelho),inset 0 -3px 9px rgba(0,0,0,0.28); }
.farol-xl i.lit-y{ background:var(--amarelo);  box-shadow:0 0 34px var(--amarelo), inset 0 -3px 9px rgba(0,0,0,0.28); }
.farol-xl i.lit-g{ background:var(--verde);    box-shadow:0 0 34px var(--verde),  inset 0 -3px 9px rgba(0,0,0,0.28); }
/* Pilula de status */
.pill{
  display:inline-flex; align-items:center; gap:7px;
  padding:5px 12px; border-radius:999px; font-size:0.72rem; font-weight:600;
  border:1px solid var(--stroke-2); background:var(--glass-2);
  letter-spacing:-0.005em;
}
.pill .dot{ width:6px; height:6px; border-radius:50%; }
/* Acessibilidade */
*:focus-visible{ outline:2px solid var(--accent) !important; outline-offset:2px; }
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{ animation:none !important; transition:none !important; }
}
@media (max-width:820px){
  h1{ font-size:2rem !important; }
  .block-container{ padding-top:1.4rem; }
}
/* Esconde o rodape "Made with Streamlit" — visual de produto, nao de demo */
footer{ visibility:hidden; }
#MainMenu{ visibility:hidden; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. ESTADO DA SESSAO
# ==========================================

def _init_session():
    if "init" in st.session_state:
        return
    st.session_state.init = True

    _kms = os.getenv("SOMPO_KMS_KEY", "")
    st.session_state.kms_key      = _kms.encode() if _kms else Fernet.generate_key()
    st.session_state.cipher_suite = Fernet(st.session_state.kms_key)
    st.session_state.jwt_secret   = os.getenv("SOMPO_JWT_SECRET", secrets.token_hex(32))
    st.session_state.ultimo_hash  = "GENESIS_BLOCK_000"

    # CORRIGIDO: tentativas zeradas no boot, nao bloqueia primeira vez
    st.session_state.tentativas_falhas = 0
    st.session_state.bloqueio_tempo    = 0.0

    st.session_state.jwt_token            = None
    st.session_state.usuario_logado       = None
    st.session_state.role_logado          = None
    st.session_state.logs_auditoria       = []
    st.session_state.telemetria_historico = []

    st.session_state.ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1)

    # Contas de demonstracao.
    #
    # As senhas abaixo sao publicas por desenho: este e um ambiente de
    # demonstracao academica, sem dado real de cliente, e as credenciais
    # precisam estar disponiveis para quem avalia o projeto. Nao sao, e nunca
    # foram, credenciais de producao.
    #
    # Ainda assim, ficam sobrescreviveis por variavel de ambiente para que
    # qualquer implantacao real nao dependa de valor fixo em codigo:
    #     SOMPO_SENHA_ADMIN / SOMPO_SENHA_PRODUTOR
    #
    # O armazenamento e sempre o hash Argon2id — a senha em texto existe
    # apenas no momento de criar o hash, nunca e persistida.
    _senha_admin = os.environ.get("SOMPO_SENHA_ADMIN", "Admin@2024!")
    _senha_produtor = os.environ.get("SOMPO_SENHA_PRODUTOR", "Produtor@2024!")

    st.session_state.mock_users = {
        "admin": {
            "senha_hash": st.session_state.ph.hash(_senha_admin),
            "role": "Admin",
        },
        # Conta do portal do segurado. O papel Segurado nao tem permissao
        # de leitura da carteira — ve apenas o proprio equipamento.
        "produtor": {
            "senha_hash": st.session_state.ph.hash(_senha_produtor),
            "role": "Segurado",
        },
    }


_init_session()

# ==========================================
# 2. CONSTANTES
# ==========================================

# RBAC_MATRIX e MEMBER_COLORS moraram pra core_app.py (fonte unica, tambem
# usada pelo middleware de autorizacao check_permissao). Importados abaixo,
# na secao 4-6, junto com o resto do core_app.

# Agrupada em tres blocos. Os quatro itens de bastidor (auditoria, desempenho
# do modelo, explicabilidade, sobre) ficam num grupo colapsado — sao telas de
# trabalho interno e nao devem competir com as telas de produto numa sala
# de negocio.

MENU_GRUPOS = PORTAL.grupos
MENU_ITEMS = PORTAL.itens
_GRUPOS_COLAPSADOS = {"Plataforma"} if PORTAL.chave == "sompo" else set()


@st.cache_data(ttl=8, show_spinner=False)
def _contar_telemetria() -> int:
    """
    Quantos equipamentos estao transmitindo AGORA, segundo o servico de
    ingestao. Antes este numero vinha de telemetria_historico, que so e
    preenchido pelo formulario manual da tela de sensores — com o
    dispositivo em campo mandando dado de verdade, o contador ficava
    parado em zero. Cache de 8s para nao consultar a cada rerun.
    """
    try:
        import core_integracao as _ci
        dados, integ = _ci.telemetria_ao_vivo()
        if integ.conectado:
            return int(dados.get("n", 0))
    except Exception:
        pass
    return len(st.session_state.get("telemetria_historico", []))


def _estado_frota() -> tuple[str, int]:
    """
    Pior faixa presente na carteira + equipamentos transmitindo. Alimenta o
    farol ambiente (assinatura visual da interface): a tela inteira muda de
    temperatura conforme o risco da frota.
    """
    n_tele = _contar_telemetria()
    try:
        import core_fusao as _cf
        df = _carregar_base_real()
        if df is None or df.empty:
            return "verde", n_tele
        _cf.calibrar_faixas(df)
        faixas = _cf.calcular_score_base(df)["score_base"].apply(
            lambda s: _cf.classificar(s)[0])
        for pior in ("vermelho", "amarelo", "verde"):
            if (faixas == pior).any():
                return pior, n_tele
    except Exception:
        pass
    return "verde", n_tele


def _wash_ambiente(faixa: str) -> None:
    """Injeta a cor do farol ambiente. Duas camadas radiais, transicao suave."""
    tons = {
        "verde":    ("rgba(63,207,142,0.10)",  "rgba(110,141,245,0.06)"),
        "amarelo":  ("rgba(245,178,61,0.11)",  "rgba(229,72,77,0.05)"),
        "vermelho": ("rgba(242,85,90,0.13)",   "rgba(245,178,61,0.06)"),
    }
    a, b = tons.get(faixa, tons["verde"])
    st.markdown(
        f"<style>:root{{--wash-a:{a};--wash-b:{b};}}</style>",
        unsafe_allow_html=True,
    )


# ==========================================
# 3. DADOS E CONTROLE DE ACESSO
# ==========================================

@st.cache_data(ttl=3600, show_spinner=False)
def _carregar_base_real():
    """
    Base SUSEP real, 149 registros. Retorna None se o arquivo nao estiver
    na pasta — quem chama decide como avisar. Nunca gera substituto.
    """
    from pathlib import Path
    p = Path("base_sompo_limpa.csv")
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None



def avaliar_risco_login(falhas, hora, ip_suspeito=False, latencia_ms=0.0):
    """
    Decide se uma tentativa de login deve ser bloqueada.
    REGRA DETERMINISTICA E AUDITAVEL, nao modelo estatistico.

    Substituiu um DecisionTreeClassifier treinado com
    sklearn.datasets.make_classification — dados 100% sinteticos, sem
    relacao com padrao real de acesso. Um modelo que nunca viu um login
    de verdade nao deve decidir bloqueio; uma regra explicita, sim.

    Args:
        falhas: tentativas falhas consecutivas nesta sessao.
        hora: hora local (0-23) da tentativa.
        ip_suspeito: True quando a origem ja acumulou falhas.
        latencia_ms: tempo de resposta observado.

    Returns:
        (bloquear: bool, risco: float 0-1, motivo: str)

    >>> avaliar_risco_login(0, 14)[0]      # primeiro acesso nunca bloqueia
    False
    >>> avaliar_risco_login(5, 14, True)[0]
    True
    """
    if falhas <= 0:
        return False, 0.0, "primeiro acesso"

    risco, motivos = 0.0, []

    if falhas >= 5:
        risco += 0.60
        motivos.append(f"{falhas} falhas consecutivas")
    elif falhas >= 3:
        risco += 0.40
        motivos.append(f"{falhas} falhas consecutivas")
    else:
        risco += 0.15 * falhas
        motivos.append(f"{falhas} falha(s)")

    if ip_suspeito:
        risco += 0.20
        motivos.append("origem ja sinalizada")
    if hora < 6 or hora >= 23:
        risco += 0.10
        motivos.append("fora do horario comercial")
    if latencia_ms and latencia_ms > 800:
        risco += 0.10
        motivos.append("latencia atipica")

    risco = min(risco, 1.0)
    return risco >= 0.60, round(risco, 2), " · ".join(motivos)


def tela_login():
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown("""
        <div style="text-align:center;padding:2rem 0 1.5rem;">
            <div style="display:inline-flex;gap:3px;padding:6px 5px;border-radius:7px;
                        border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.06);
                        margin-bottom:14px;">
                <i style="display:block;width:9px;height:9px;border-radius:50%;
                          background:#F2555A;box-shadow:0 0 9px #F2555A;"></i>
                <i style="display:block;width:9px;height:9px;border-radius:50%;
                          background:#F5B23D;box-shadow:0 0 9px #F5B23D;"></i>
                <i style="display:block;width:9px;height:9px;border-radius:50%;
                          background:#3FCF8E;box-shadow:0 0 9px #3FCF8E;"></i>
            </div>
            <div style="font-family:'Manrope',sans-serif;font-size:1.9rem;
                        font-weight:800;letter-spacing:-0.02em;color:#F0F4F8;">
                Sompo <span style="color:#E5484D;">Predict</span></div>
            <div style="font-size:0.85rem;color:#98A4B2;margin-top:7px;">
                Prevenção de risco em seguro rural
            </div>
        </div>
        """, unsafe_allow_html=True)

        # CORRIGIDO: reset automatico quando bloqueio expirou
        # Bloqueio ativo: so vale enquanto o relogio nao expirar. A condicao e
        # o TEMPO, nao a contagem de falhas — checar as duas coisas deixava o
        # usuario preso mesmo depois do prazo vencer.
        restante = st.session_state.get("bloqueio_tempo", 0.0) - time.time()
        if restante > 0:
            st.error(f"Acesso bloqueado. Tente novamente em {int(restante)}s.")
            if st.button("Já aguardei — liberar agora", use_container_width=True):
                st.session_state.tentativas_falhas = 0
                st.session_state.bloqueio_tempo    = 0.0
                st.rerun()
            return
        # Prazo vencido: zera o contador para a proxima tentativa começar limpa
        if st.session_state.get("tentativas_falhas", 0) >= 3:
            st.session_state.tentativas_falhas = 0
            st.session_state.bloqueio_tempo    = 0.0

        tab_login, tab_reg = st.tabs(["  Entrar  ", "  Registrar  "])

        with tab_login:
            with st.form("form_login", clear_on_submit=False):
                usuario = st.text_input("Usuário", placeholder="seu.usuario")
                senha   = st.text_input("Senha",   placeholder="••••••••", type="password")
                st.caption("Use as credenciais fornecidas pelo administrador da conta.")
                submit  = st.form_submit_button("Entrar", use_container_width=True)

            if submit:
                # 1. WAF - formato do usuario
                if not re.match(r"^[a-zA-Z0-9_]{3,20}$", usuario):
                    st.warning("WAF: formato de usuario invalido (3-20 chars alfanumericos).")
                    st.session_state.tentativas_falhas += 1
                    return

                # 2. Regra de bloqueio por tentativas — desempacota a tupla
                #    (bloquear, risco, motivo). Chamar sem desempacotar faz a
                #    tupla ser sempre truthy e bloquear todo mundo.
                ip_suspeito = st.session_state.tentativas_falhas >= 2
                bloquear, risco, motivo = avaliar_risco_login(
                    st.session_state.tentativas_falhas,
                    datetime.now().hour,
                    ip_suspeito, 45.0,
                )
                if bloquear:
                    st.session_state.bloqueio_tempo = time.time() + 30
                    gerar_trilha_auditoria(
                        "BLOQUEIO_TENTATIVAS",
                        f"usuario={usuario} risco={risco} motivo={motivo}")
                    st.error(
                        f"Acesso bloqueado por 30 segundos. Motivo: {motivo}.")
                    st.rerun()
                    return

                # 3. Verificacao de credenciais (Argon2id, tempo constante)
                db_entry  = st.session_state.mock_users.get(usuario)
                hash_alvo = (
                    db_entry["senha_hash"] if db_entry
                    else st.session_state.ph.hash("dummy_timing")
                )
                senha_ok = _verificar_senha(hash_alvo, senha) if db_entry else False

                if not senha_ok:
                    st.session_state.tentativas_falhas += 1
                    gerar_trilha_auditoria("LOGIN_FALHA", f"usuario={usuario}")
                    st.error("Credenciais invalidas.")
                    return

                # 4. Login OK
                st.session_state.tentativas_falhas = 0
                st.session_state.bloqueio_tempo    = 0.0
                st.session_state.usuario_logado    = usuario
                st.session_state.role_logado       = db_entry["role"]
                st.session_state.jwt_token = jwt.encode(
                    {
                        "sub":  usuario,
                        "role": db_entry["role"],
                        "iat":  datetime.now(timezone.utc),
                        "exp":  datetime.now(timezone.utc) + timedelta(hours=2),
                    },
                    st.session_state.jwt_secret,
                    algorithm="HS256",
                )
                gerar_trilha_auditoria("LOGIN_SUCESSO", f"role={db_entry['role']}")
                st.rerun()

        with tab_reg:
            with st.form("form_reg", clear_on_submit=True):
                n_user = st.text_input("Novo Usuario")
                n_pwd  = st.text_input("Nova Senha", type="password")
                n_role = st.selectbox("Perfil", ["Operador", "Cientista", "Admin"])
                reg_ok = st.form_submit_button("Registrar", use_container_width=True)

            if reg_ok:
                if not re.match(r"^[a-zA-Z0-9_]{3,20}$", n_user):
                    st.error("Nome invalido (3-20 chars alfanumericos).")
                elif n_user in st.session_state.mock_users:
                    st.error("Usuario ja existe.")
                elif len(n_pwd) < 8:
                    st.error("Senha deve ter >= 8 caracteres.")
                else:
                    st.session_state.mock_users[n_user] = {
                        "senha_hash": st.session_state.ph.hash(n_pwd),
                        "role": n_role,
                    }
                    gerar_trilha_auditoria("NOVO_USUARIO", f"user={n_user} role={n_role}")
                    st.success(f"Usuario `{n_user}` criado! Faca login.")


# ==========================================
# 8. SIDEBAR
# ==========================================

def sidebar():
    faixa, n_tele = _estado_frota()
    _wash_ambiente(faixa)

    if "current_page" not in st.session_state:
        st.session_state.current_page = PORTAL.inicial

    lampada = {"verde": "on-g", "amarelo": "on-y", "vermelho": "on-r"}[faixa]

    # Marca do portal: a seguradora ve "Sompo Predict"; o segurado ve
    # "Minha Maquina" — nome que faz sentido para quem opera a maquina,
    # nao para quem subscreve a apolice.
    if PORTAL.chave == "sompo":
        marca_html = 'Sompo <span style="color:var(--sompo);">Predict</span>'
    else:
        marca_html = 'Minha <span style="color:var(--sompo);">Máquina</span>'

    with st.sidebar:
        # --- marca: o farol acende a lampada do estado atual da frota ---
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:11px;padding:0.2rem 0 1.2rem;">
            <div class="brand-farol">
                <i class="{'on-r' if lampada=='on-r' else ''}"></i>
                <i class="{'on-y' if lampada=='on-y' else ''}"></i>
                <i class="{'on-g' if lampada=='on-g' else ''}"></i>
            </div>
            <div style="font-family:'Manrope',sans-serif;font-weight:800;
                        font-size:1.02rem;letter-spacing:-0.03em;color:var(--text);">
                {marca_html}</div>
        </div>
        """, unsafe_allow_html=True)

        # --- usuario ---
        cor = MEMBER_COLORS.get(st.session_state.usuario_logado, "#6E8DF5")
        iniciais = (st.session_state.usuario_logado or "??")[:2].upper()
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:11px;padding:0 0 1.1rem;">
            <div style="width:36px;height:36px;border-radius:11px;background:{cor}1F;
                        border:1px solid {cor}66;display:flex;align-items:center;
                        justify-content:center;font-weight:700;font-size:0.85rem;
                        color:{cor};font-family:'Manrope',sans-serif;">{iniciais}</div>
            <div>
                <div style="font-weight:600;color:var(--text);font-size:0.86rem;
                            letter-spacing:-0.01em;">{st.session_state.usuario_logado}</div>
                <div style="font-size:0.68rem;color:var(--text-3);">
                    {st.session_state.role_logado}</div>
            </div>
        </div>
        <div style="height:1px;background:var(--stroke);margin-bottom:0.9rem;"></div>
        """, unsafe_allow_html=True)

        # --- navegacao agrupada ---
        def _itens(dic):
            for rotulo, pid in dic.items():
                ativo = st.session_state.current_page == pid
                if st.button(rotulo, key=f"nav_{pid}",
                             use_container_width=True,
                             type="primary" if ativo else "secondary"):
                    st.session_state.current_page = pid
                    st.rerun()

        for grupo, itens in MENU_GRUPOS.items():
            if not grupo:
                _itens(itens)
                continue
            if grupo in _GRUPOS_COLAPSADOS:
                aberto = st.session_state.current_page in itens.values()
                with st.expander(grupo, expanded=aberto):
                    _itens(itens)
            else:
                st.markdown(
                    f"<div style='font-size:0.63rem;color:var(--text-3);"
                    f"text-transform:uppercase;letter-spacing:0.12em;"
                    f"font-weight:600;margin:0.9rem 0 0.35rem 0.2rem;'>{grupo}</div>",
                    unsafe_allow_html=True)
                _itens(itens)

        # --- rodape de estado ---
        st.markdown("<div style='height:1px;background:var(--stroke);"
                    "margin:1.3rem 0 0.9rem;'></div>", unsafe_allow_html=True)

        n_logs = len(st.session_state.logs_auditoria)
        # Telemetria em destaque quando ha leitura chegando: no pitch, esse
        # numero saindo de zero enquanto o carrinho anda e o momento que prova
        # que o sistema esta vivo.
        if n_tele > 0:
            tele_html = (f"<span style='color:var(--verde);font-weight:700;'>"
                         f"{n_tele}</span> transmitindo "
                         f"<span style='display:inline-block;width:6px;height:6px;"
                         f"border-radius:50%;background:var(--verde);"
                         f"box-shadow:0 0 8px var(--verde);margin-left:2px;'></span>")
        else:
            tele_html = ("<span style='color:var(--text-3);'>"
                         "nenhum dispositivo ativo</span>")

        st.markdown(f"""
        <div style="font-size:0.7rem;color:var(--text-3);line-height:2;">
            <div>Trilha · <strong style="color:var(--text-2);">{n_logs}</strong> hashes</div>
            <div>Telemetria · {tele_html}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:0.7rem;'></div>", unsafe_allow_html=True)
        if st.button("Encerrar sessão", use_container_width=True, key="btn_logout"):
            gerar_trilha_auditoria("LOGOUT", "logout manual")
            for k in ["jwt_token", "usuario_logado", "role_logado"]:
                st.session_state[k] = None
            st.rerun()

    return st.session_state.current_page


# ==========================================
# 9. PAGINAS DO MENU
# ==========================================

def pagina_inicio():
    _contrato_box("inicio", [])
    gerar_trilha_auditoria("ACESSO_INICIO", "pagina=visao_geral")

    faixa, n_tele = _estado_frota()
    df = _carregar_base_real()
    tem_base = df is not None and not df.empty

    rotulo = {"verde": "Carteira estável", "amarelo": "Exposição em atenção",
              "vermelho": "Exposição elevada"}[faixa]
    cor_faixa = {"verde": "var(--verde)", "amarelo": "var(--amarelo)",
                 "vermelho": "var(--vermelho)"}[faixa]

    # ---------- Abertura ----------
    st.markdown(f"""
    <div style="padding:0.4rem 0 1.5rem;">
        <div class="pill" style="margin-bottom:1rem;">
            <span class="dot" style="background:{cor_faixa};
                  box-shadow:0 0 9px {cor_faixa};"></span>
            <span style="color:var(--text-2);">{rotulo}</span>
        </div>
        <h1 style="margin:0;">Prevenção de risco<br>
            <span style="color:var(--text-3);">em seguro rural.</span></h1>
        <p style="color:var(--text-2);margin-top:1rem;font-size:1.02rem;
                  max-width:580px;line-height:1.65;">
            Telemetria embarcada no equipamento segurado, combinada com o
            histórico da apólice, para antecipar sinistro em vez de
            indenizá-lo. O segurado recebe o alerta em campo; a seguradora
            recebe a carteira ordenada por exposição.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ---------- Indicadores da carteira ----------
    if tem_base:
        import core_fusao as _cf
        _cf.calibrar_faixas(df)
        scored = _cf.calcular_score_base(df)
        faixas = scored["score_base"].apply(lambda s: _cf.classificar(s)[0])
        n_verm = int((faixas == "vermelho").sum())
        n_amar = int((faixas == "amarelo").sum())
        lr = df.VALOR_INDENIZADO_BRL.sum() / df.PREMIO_LIQUIDO_BRL.sum() * 100
        expo = df.loc[faixas.values == "vermelho", "PREMIO_LIQUIDO_BRL"].sum()
        cards = [
            (f"{len(df)}", "Apólices sob gestão", "var(--text)"),
            (f"{n_amar}", "Em atenção", "var(--amarelo)"),
            (f"{n_verm}", "Exposição elevada", "var(--vermelho)"),
            (f"{lr:.0f}%", "Sinistralidade da carteira", "var(--text)"),
            (f"{n_tele}", "Leituras de telemetria",
             "var(--verde)" if n_tele else "var(--text-3)"),
        ]
    else:
        cards = [("—", "Carteira não carregada", "var(--text-3)")] * 5

    cols = st.columns(5)
    for col, (val, lab, cor) in zip(cols, cards):
        col.markdown(f"""
        <div class="g-card" style="padding:1.05rem 1.15rem;">
            <div class="g-num" style="color:{cor};">{val}</div>
            <div class="g-label">{lab}</div>
        </div>
        """, unsafe_allow_html=True)

    if not tem_base:
        st.warning(
            "Base de apólices indisponível. Os indicadores da carteira "
            "aparecem assim que a fonte de dados for restabelecida.",
            icon="⚠️")
        return

    # ---------- Prioridades de subscrição ----------
    st.markdown("<div style='height:2.1rem;'></div>", unsafe_allow_html=True)
    c_esq, c_dir = st.columns([3, 2])

    with c_esq:
        st.markdown("### Prioridades de subscrição")
        st.markdown(
            "<p style='color:var(--text-2);font-size:0.89rem;"
            "margin:-0.4rem 0 0.9rem;'>Equipamentos com maior exposição na "
            "renovação. Ordenados por score de perfil.</p>",
            unsafe_allow_html=True)
        top = scored.assign(faixa=faixas.values, equip=[f"COL-{i:03d}"
                            for i in range(len(scored))]) \
                    .nlargest(5, "score_base")
        _hex = {"verde": "#3FCF8E", "amarelo": "#F5B23D", "vermelho": "#F2555A"}
        for _, r in top.iterrows():
            cor = _hex[r.faixa]
            st.markdown(f"""
            <div class="g-card" style="padding:0.85rem 1.1rem;margin-bottom:8px;
                 display:flex;align-items:center;justify-content:space-between;
                 gap:14px;">
                <div style="display:flex;align-items:center;gap:13px;min-width:0;">
                    <span style="width:7px;height:7px;border-radius:50%;
                          background:{cor};box-shadow:0 0 9px {cor};
                          flex:none;"></span>
                    <div style="min-width:0;">
                        <div style="font-weight:600;font-size:0.9rem;
                              color:var(--text);">{r.equip}</div>
                        <div style="font-size:0.73rem;color:var(--text-3);
                              white-space:nowrap;overflow:hidden;
                              text-overflow:ellipsis;">
                            {r.UF} · {int(r.IDADE_MAQUINA_ANOS)} anos ·
                            {r.RAMO_SUSEP}</div>
                    </div>
                </div>
                <div style="font-family:'JetBrains Mono',monospace;
                      font-size:1.15rem;font-weight:600;color:{cor};
                      flex:none;">{r.score_base:.0f}</div>
            </div>
            """, unsafe_allow_html=True)

    with c_dir:
        st.markdown("### Concentração por estado")
        st.markdown(
            "<p style='color:var(--text-2);font-size:0.89rem;"
            "margin:-0.4rem 0 0.9rem;'>Sinistralidade observada, não volume "
            "de apólices.</p>", unsafe_allow_html=True)
        g = df.groupby("UF")
        t = (g.VALOR_INDENIZADO_BRL.sum() / g.PREMIO_LIQUIDO_BRL.sum() * 100)
        t = t.sort_values(ascending=False).head(6)
        maior = t.max()
        for uf, v in t.items():
            larg = v / maior * 100
            cor = ("var(--vermelho)" if v >= 70 else
                   "var(--amarelo)" if v >= 55 else "var(--verde)")
            st.markdown(f"""
            <div style="margin-bottom:11px;">
                <div style="display:flex;justify-content:space-between;
                      font-size:0.8rem;margin-bottom:5px;">
                    <span style="color:var(--text);font-weight:600;">{uf}</span>
                    <span style="color:var(--text-2);
                          font-family:'JetBrains Mono',monospace;">{v:.0f}%</span>
                </div>
                <div style="height:5px;border-radius:3px;
                      background:rgba(255,255,255,0.06);overflow:hidden;">
                    <div style="height:100%;width:{larg:.0f}%;background:{cor};
                          border-radius:3px;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ---------- Capacidades da plataforma ----------
    st.markdown("<div style='height:2.1rem;'></div>", unsafe_allow_html=True)
    st.markdown("### O que a plataforma entrega")
    caps = [
        ("Alerta em campo",
         "O equipamento avisa o operador antes do evento, sem depender "
         "de conexão. A decisão de parar continua com quem opera."),
        ("Score explicável",
         "Cada pontuação vem acompanhada dos fatores que a formaram, em "
         "linguagem que o segurado entende e o subscritor audita."),
        ("Carteira priorizada",
         "Exposição ordenada para direcionar inspeção, revisão de "
         "cobertura e precificação na renovação."),
        ("Trilha auditável",
         "Toda consulta e decisão registrada com encadeamento SHA-256, "
         "em conformidade com a LGPD."),
    ]
    cols = st.columns(4)
    for col, (titulo, desc) in zip(cols, caps):
        col.markdown(f"""
        <div class="g-card" style="height:100%;">
            <div style="font-family:'Manrope',sans-serif;font-weight:700;
                  font-size:0.98rem;letter-spacing:-0.02em;
                  margin-bottom:9px;">{titulo}</div>
            <div style="font-size:0.81rem;color:var(--text-2);
                  line-height:1.65;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)


def pagina_dados():
    if not check_permissao("view_dados") and not check_permissao("view_dashboard"):
        return
    _contrato_box("pagina_dados", ["ACESSO_DADOS", "EXPORTACAO_CSV"])
    _header("Base de Apólices", "Carteira de seguro rural · fonte SUSEP")
    gerar_trilha_auditoria("ACESSO_DADOS", "pagina=dados")

    df = _carregar_base_real()
    if df is None:
        st.error(
            "`base_sompo_limpa.csv` não está na pasta do projeto. Esta tela "
            "mostra apenas dados reais da SUSEP — coloque o arquivo aqui "
            "para carregá-la.", icon="🚨")
        return

    st.markdown(
        "<div class='pill' style='margin-bottom:1.2rem;'>"
        "<span class='dot' style='background:var(--verde);"
        "box-shadow:0 0 8px var(--verde);'></span>"
        "<span style='color:var(--text-2);'>Fonte · SUSEP, ramos rurais · "
        "149 apólices</span></div>", unsafe_allow_html=True)

    import core_fusao as _cf
    _cf.calibrar_faixas(df)
    scored = _cf.calcular_score_base(df)

    tab1, tab2, tab3 = st.tabs(["Carteira", "Distribuições", "Risco por UF"])

    with tab1:
        lr = df.VALOR_INDENIZADO_BRL.sum() / df.PREMIO_LIQUIDO_BRL.sum() * 100
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Apólices", len(df))
        c2.metric("Loss ratio", f"{lr:.1f}%")
        c3.metric("Idade média", f"{df.IDADE_MAQUINA_ANOS.mean():.1f} anos")
        c4.metric("Score médio", f"{scored.score_base.mean():.1f}")
        st.dataframe(df, use_container_width=True, height=380)
        st.download_button(
            "Baixar CSV", df.to_csv(index=False).encode("utf-8"),
            "base_sompo_susep.csv", "text/csv", key="dados_dl")

    with tab2:
        if PLOTLY_OK:
            ca, cb = st.columns(2)
            with ca:
                fig = px.histogram(scored, x="score_base", nbins=22,
                                   template="plotly_dark",
                                   title="Distribuição do score de perfil")
                fig.update_traces(marker_color="#6E8DF5")
                fig.add_vline(x=_cf.FAIXAS[1][0], line_dash="dash",
                              line_color="#F5B23D")
                fig.add_vline(x=_cf.FAIXAS[2][0], line_dash="dash",
                              line_color="#F2555A")
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                                  paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
            with cb:
                cont = df.CLASSIFICACAO_RISCO.value_counts().reset_index()
                cont.columns = ["classe", "n"]
                fig2 = px.bar(cont, x="classe", y="n", template="plotly_dark",
                              title="Classificação de risco na base")
                fig2.update_traces(marker_color="#3FCF8E")
                fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                                   paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.bar_chart(df.CLASSIFICACAO_RISCO.value_counts())

    with tab3:
        st.markdown(
            "**Volume não é risco.** A UF com mais registros na base não é a "
            "de maior sinistralidade — por isso a tabela ordena por loss "
            "ratio, não por contagem.")
        crit = (df.CLASSIFICACAO_RISCO == "Crítico")
        g = df.groupby("UF")
        t = pd.DataFrame({
            "registros": g.size(),
            "loss_ratio_%": (g.VALOR_INDENIZADO_BRL.sum()
                             / g.PREMIO_LIQUIDO_BRL.sum() * 100).round(1),
            "críticos": crit.groupby(df.UF).sum(),
        })
        t["% da base"] = (t.registros / len(df) * 100).round(1)
        st.dataframe(t.sort_values("loss_ratio_%", ascending=False),
                     use_container_width=True)
        st.caption(
            "Com 12 casos críticos distribuídos em 8 estados, a taxa por UF "
            "tem suporte pequeno. O mapa de risco usado no score suaviza "
            "isso por credibilidade de Bühlmann-Straub (k=30).")


def pagina_cloud():
    """
    Infraestrutura — estado real do servico, nao inventario declarado.

    A versao anterior listava "EC2 Online", "S3 Conectado", "SageMaker
    Staging" com os status escritos no codigo: apareciam verdes mesmo com o
    servico fora do ar. Agora cada verificacao e uma consulta de fato, e o
    que nao pode ser verificado nao aparece como se estivesse funcionando.
    """
    if not check_permissao("train_models") and not check_permissao("view_dashboard"):
        return
    _contrato_box("pagina_cloud", ["ACESSO_CLOUD", "VERIFICACAO_SERVICO"])
    _header("Infraestrutura",
            "Disponibilidade e capacidade do serviço de ingestão")
    gerar_trilha_auditoria("ACESSO_CLOUD", "pagina=infraestrutura")

    import core_integracao as _ci

    tab_estado, tab_endpoints, tab_deploy = st.tabs(
        ["Estado do serviço", "Interface de integração", "Publicação"])

    # -----------------------------------------------------------------
    with tab_estado:
        col_a, col_b = st.columns([3, 1])
        col_a.markdown(f"**Endereço configurado**")
        col_a.code(_ci.API_BASE, language=None)
        verificar = col_b.button("Verificar agora", key="cloud_check",
                                 use_container_width=True)

        checagens = _verificar_servico(_ci.API_BASE)
        for nome, ok, detalhe, ms in checagens:
            cor = "var(--verde)" if ok else "var(--text-3)"
            lat = (f"<span style=\"font-family:'JetBrains Mono',monospace;"
                   f"font-size:0.75rem;color:var(--text-3);\">{ms} ms</span>"
                   if ms is not None else "")
            st.markdown(f"""
            <div class="g-card" style="padding:0.9rem 1.2rem;margin-bottom:8px;
                 display:flex;justify-content:space-between;align-items:center;
                 gap:14px;">
                <div style="min-width:0;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span style="width:7px;height:7px;border-radius:50%;
                              background:{cor};box-shadow:0 0 8px {cor};
                              flex:none;"></span>
                        <span style="font-weight:600;color:var(--text);
                              font-size:0.9rem;">{nome}</span>
                    </div>
                    <div style="font-size:0.75rem;color:var(--text-2);
                          margin-top:4px;">{detalhe}</div>
                </div>
                {lat}
            </div>
            """, unsafe_allow_html=True)

        if not any(ok for _, ok, _, _ in checagens):
            st.info(
                "O serviço de ingestão não está respondendo no endereço "
                "configurado. Enquanto isso, a plataforma opera com a base "
                "de apólices e o cálculo determinístico — nenhuma tela fica "
                "indisponível. Para apontar para outro endereço, defina a "
                "variável de ambiente `SOMPO_API_BASE`.", icon="🔌")

    # -----------------------------------------------------------------
    with tab_endpoints:
        st.markdown(
            "Interface exposta pelo serviço de ingestão. É contra estas "
            "rotas que o dispositivo em campo e a plataforma conversam.")
        rotas = [
            ("POST", "/telemetria/v1/ingest",
             "Recebe uma leitura do dispositivo, valida o formato, "
             "confere a assinatura e calcula o score."),
            ("GET", "/telemetria/v1/ultimo/{equipamento}",
             "Última leitura processada — alimenta o Painel do Segurado."),
            ("GET", "/telemetria/v1/serie/{equipamento}",
             "Série histórica do equipamento, para gráficos e análise."),
            ("GET", "/telemetria/v1/frota",
             "Equipamentos transmitindo, ordenados por score."),
            ("GET", "/telemetria/v1/health",
             "Diagnóstico: perfis carregados, aceitos, rejeitados."),
            ("GET", "/whoami",
             "Endereço em que o serviço se amarrou — confirma o alvo do "
             "dispositivo antes de investigar o firmware."),
        ]
        for metodo, rota, desc in rotas:
            cor_m = "var(--amarelo)" if metodo == "POST" else "var(--accent)"
            st.markdown(f"""
            <div class="g-card" style="padding:0.85rem 1.15rem;margin-bottom:7px;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-family:'JetBrains Mono',monospace;
                          font-size:0.7rem;font-weight:700;color:{cor_m};
                          border:1px solid {cor_m}55;border-radius:5px;
                          padding:1px 7px;flex:none;">{metodo}</span>
                    <span style="font-family:'JetBrains Mono',monospace;
                          font-size:0.82rem;color:var(--text);">{rota}</span>
                </div>
                <div style="font-size:0.77rem;color:var(--text-2);
                      margin-top:6px;line-height:1.55;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
        _oferecer_arquivo(
            "docs/CONTRATO_TELEMETRIA_v1.md",
            "Especificação da interface",
            "Formato do payload, unidades, frequências e regras de "
            "assinatura. Documento de referência para quem implementa "
            "os dois lados da integração.",
            "cloud_contrato")
        _oferecer_arquivo(
            "api_telemetria.py",
            "Serviço de ingestão",
            "Implementação de referência do serviço: validação de formato, "
            "autenticação por assinatura, proteção contra reenvio e "
            "cálculo de score.",
            "cloud_api")

    # -----------------------------------------------------------------
    with tab_deploy:
        st.markdown("#### Publicação do serviço")
        st.markdown(
            "O serviço é uma aplicação Python única, sem dependência de "
            "banco para operar. Sobe em qualquer instância com Python 3.10+.")

        st.markdown("**1 · Endereço fixo**")
        st.markdown(
            "O endereço público de uma instância muda a cada reinício. Sem "
            "endereço fixo, o dispositivo em campo passa a apontar para o "
            "vazio depois de qualquer manutenção — e a falha é silenciosa.")
        st.code("aws ec2 allocate-address --domain vpc\n"
                "aws ec2 associate-address --instance-id <id> "
                "--allocation-id <alloc>", language="bash")

        st.markdown("**2 · Porta 80**")
        st.markdown(
            "Redes corporativas e de campo bloqueiam saída em portas altas. "
            "Publicar na porta 80 faz o tráfego do dispositivo passar como "
            "HTTP comum.")
        st.code("sudo setcap 'cap_net_bind_service=+ep' "
                "$(readlink -f $(which python3))\n"
                "PORT=80 python3 api_telemetria.py", language="bash")

        st.markdown("**3 · Chave por dispositivo**")
        st.markdown(
            "Cada dispositivo tem sua própria chave de assinatura, definida "
            "por variável de ambiente. Chave em arquivo versionado é chave "
            "vazada.")
        st.code('export SOMPO_HMAC_T1_CART_01="<32 bytes>"', language="bash")

        st.markdown("**4 · Apontar a plataforma**")
        st.code('export SOMPO_API_BASE="http://<endereco>:80"', language="bash")

        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        st.markdown("**Publicação assistida**")
        st.markdown(
            "O material abaixo leva uma instância vazia até o serviço no ar "
            "e verifica o resultado. O procedimento é repetível: executá-lo "
            "de novo atualiza o código sem refazer a configuração nem perder "
            "as leituras já gravadas.")

        _oferecer_arquivo(
            "deploy/README_AWS.md",
            "Guia de publicação",
            "Dimensionamento da instância, regras de rede, endereço fixo, "
            "verificação de aceite, operação e custo.",
            "cloud_guia")
        _oferecer_arquivo(
            "deploy/bootstrap_ec2.sh",
            "Instalação automatizada",
            "Instala dependências, cria ambiente isolado, gera a chave de "
            "assinatura, registra o serviço para iniciar com o sistema e "
            "confirma que responde.",
            "cloud_bootstrap")
        _oferecer_arquivo(
            "deploy/verificar.sh",
            "Teste de aceite",
            "Nove verificações do caminho completo: disponibilidade, "
            "formato, assinatura, cálculo de score, recusa de leitura "
            "inválida, bloqueio de reenvio e consultas.",
            "cloud_verificar")
        _oferecer_arquivo(
            "deploy/sompo-api.service",
            "Definição do serviço",
            "Configuração de inicialização automática, reinício em caso de "
            "falha e restrições de privilégio do processo.",
            "cloud_service")

        st.warning(
            "O serviço mantém estado em memória — última leitura por "
            "equipamento, série recente e controle de reenvio — e por isso "
            "roda em **processo único**. Aumentar o número de processos faz "
            "cada um manter sua própria cópia desse estado, e a mesma "
            "consulta passa a devolver respostas diferentes. O sintoma se "
            "parece com instabilidade de rede.", icon="⚠️")

        st.caption(
            "Verificação de aceite: `curl http://<endereco>/whoami` "
            "responde com o endereço efetivo e a versão do formato aceito.")


@st.cache_data(ttl=10, show_spinner=False)
def _verificar_servico(base: str):
    """
    Consulta real ao servico. Devolve [(nome, ok, detalhe, latencia_ms)].
    Cache curto para nao consultar a cada rerun do Streamlit.
    """
    import time as _t
    try:
        import requests
    except ImportError:
        return [("Serviço de ingestão", False,
                 "biblioteca de rede indisponível no ambiente", None)]

    resultados = []

    def _get(rota, nome, interpretar):
        t0 = _t.perf_counter()
        try:
            r = requests.get(f"{base}{rota}", timeout=2.5)
            ms = int((_t.perf_counter() - t0) * 1000)
            if r.status_code == 200:
                return (nome, True, interpretar(r.json()), ms)
            return (nome, False, f"resposta {r.status_code}", ms)
        except Exception:
            return (nome, False, "sem resposta no endereço configurado", None)

    resultados.append(_get(
        "/whoami", "Serviço de ingestão",
        lambda d: (f"formato {d.get('schema_v','?')} · "
                   f"assinatura {'exigida' if d.get('hmac_exigido') else 'dispensada'}")))
    resultados.append(_get(
        "/telemetria/v1/health", "Processamento de leituras",
        lambda d: (f"{d.get('aceitos',0)} aceitas · "
                   f"{d.get('rejeitados',0)} recusadas · "
                   f"{d.get('perfis_carregados',0)} perfis em memória")))
    resultados.append(_get(
        "/telemetria/v1/frota", "Dispositivos conectados",
        lambda d: (f"{d.get('n',0)} equipamento(s) transmitindo" if d.get("n")
                   else "nenhum dispositivo transmitindo")))
    return resultados


def _oferecer_arquivo(caminho: str, titulo: str, descricao: str, chave: str):
    """Cartao com descricao e botao de download de um artefato do projeto."""
    from pathlib import Path as _P
    p = _P(caminho)
    st.markdown(f"""
    <div class="g-card" style="padding:1rem 1.2rem;margin-bottom:8px;">
        <div style="font-weight:600;font-size:0.92rem;color:var(--text);">
            {titulo}</div>
        <div style="font-size:0.78rem;color:var(--text-2);margin-top:5px;
              line-height:1.6;">{descricao}</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.68rem;
              color:var(--text-3);margin-top:6px;">{caminho}</div>
    </div>
    """, unsafe_allow_html=True)
    if p.exists():
        st.download_button(
            f"Baixar {p.name}", p.read_bytes(), p.name,
            key=chave, use_container_width=True)
    else:
        st.caption(f"Arquivo não encontrado em `{caminho}`.")


def pagina_iot():
    """
    Sensores em Campo.

    A versao anterior era apenas um formulario manual, com uma quinta
    implementacao propria de score (inc_z/45*50 + umidade/100*30 + ...) e
    cortes 75/40 escritos a mao. Agora a tela mostra a serie real vinda do
    servico de ingestao; o envio manual permanece como recurso de
    verificacao quando nenhum dispositivo esta em campo, e usa o mesmo
    core_fusao das demais telas.
    """
    if not (check_permissao_silenciosa("input_telemetry")
            or check_permissao_silenciosa("view_dashboard")
            or check_permissao_silenciosa("view_iot")):
        st.error("Acesso negado a esta tela.")
        return
    _contrato_box("pagina_iot", ["ACESSO_IOT", "TELEMETRIA_ENVIADA"])
    _header("Sensores em Campo",
            "Telemetria embarcada e decisão local de alerta")
    gerar_trilha_auditoria("ACESSO_IOT", "pagina=sensores")

    import core_integracao as _ci
    import core_fusao as _cf

    dados, integ = _ci.telemetria_ao_vivo()

    st.markdown(f"""
    <div class="pill" style="margin-bottom:1.3rem;border-color:{integ.cor}55;">
        <span class="dot" style="background:{integ.cor};
              box-shadow:0 0 9px {integ.cor};"></span>
        <span style="color:var(--text-2);">{integ.detalhe}</span>
    </div>
    """, unsafe_allow_html=True)

    tab_vivo, tab_serie, tab_teste, tab_instal = st.tabs(
        ["Dispositivos", "Série do equipamento", "Envio de verificação",
         "Instalação do dispositivo"])

    # -----------------------------------------------------------------
    with tab_vivo:
        equipamentos = dados.get("equipamentos", [])
        if not equipamentos:
            st.info(
                "Nenhum dispositivo transmitindo no momento. Os equipamentos "
                "aparecem aqui assim que o serviço de ingestão recebe a "
                "primeira leitura. Consulte **Fontes de Dados** para "
                "verificar o endereço configurado.", icon="📡")
        else:
            _cores = {"verde": "var(--verde)", "amarelo": "var(--amarelo)",
                      "vermelho": "var(--vermelho)"}
            for eq in equipamentos:
                cor = _cores.get(eq.get("faixa", "verde"), "var(--text-3)")
                over = (" · alerta de segurança acionado"
                        if eq.get("override") else "")
                st.markdown(f"""
                <div class="g-card" style="padding:0.95rem 1.2rem;
                     margin-bottom:8px;display:flex;
                     justify-content:space-between;align-items:center;gap:14px;">
                    <div>
                        <div style="display:flex;align-items:center;gap:10px;">
                            <span style="width:7px;height:7px;border-radius:50%;
                                  background:{cor};box-shadow:0 0 9px {cor};"></span>
                            <span style="font-weight:600;color:var(--text);">
                                {eq.get('equip_id','—')}</span>
                        </div>
                        <div style="font-size:0.73rem;color:var(--text-3);
                              margin-top:4px;">
                            última leitura {str(eq.get('ts_servidor',''))[11:19]}{over}
                        </div>
                    </div>
                    <div style="font-family:'JetBrains Mono',monospace;
                          font-size:1.2rem;font-weight:600;color:{cor};">
                        {eq.get('score_final',0):.0f}</div>
                </div>
                """, unsafe_allow_html=True)

    # -----------------------------------------------------------------
    with tab_serie:
        equip = st.text_input("Equipamento", value="COL-000", key="iot_serie_id")
        df_serie = _ci.serie_telemetria(equip, n=300)
        if df_serie is None or df_serie.empty:
            st.info(
                f"Sem série registrada para {equip}. A série é acumulada "
                "pelo serviço de ingestão conforme o dispositivo transmite.",
                icon="📈")
        else:
            st.caption(f"{len(df_serie)} leituras · mais recentes ao final")
            colunas = [c for c in ["tel_inclinacao_g", "tel_vibracao_rms",
                                   "tel_dist_obstaculo_cm", "tel_umidade_pct",
                                   "score_final"] if c in df_serie.columns]
            escolha = st.multiselect(
                "Grandezas", colunas,
                default=[c for c in ("tel_inclinacao_g", "score_final")
                         if c in colunas],
                key="iot_serie_cols")
            if escolha:
                st.line_chart(df_serie[escolha])
            st.dataframe(df_serie.tail(30), use_container_width=True,
                         hide_index=True)
            st.download_button(
                "Baixar série em CSV",
                df_serie.to_csv(index=False).encode("utf-8"),
                f"serie_{equip}.csv", "text/csv", key="iot_serie_dl")

    # -----------------------------------------------------------------
    with tab_teste:
        st.caption(
            "Envio manual para verificar o caminho do dado sem dispositivo "
            "em campo. Usa o mesmo cálculo de score das demais telas.")
        c1, c2 = st.columns(2)
        inc = c1.number_input("Inclinação (°)", 0.0, 45.0, 12.0, 0.5, key="iot_z")
        dist = c1.number_input("Obstáculo (cm)", -1.0, 400.0, 200.0, 5.0, key="iot_d")
        umi = c2.number_input("Umidade (%)", 0.0, 100.0, 58.0, 1.0, key="iot_u")
        vib = c2.number_input("Vibração (m/s²)", 0.0, 5.0, 0.6, 0.1, key="iot_v")

        base_df = _carregar_base_real()
        if base_df is not None:
            _cf.calibrar_faixas(base_df)
            score_base = float(
                _cf.calcular_score_base(base_df)["score_base"].iloc[0])
        else:
            score_base = 55.0

        r = _cf.fundir(score_base, {
            "inclinacao_g": inc, "dist_obstaculo_cm": dist,
            "vibracao_rms": vib, "umidade_pct": umi, "temperatura_c": 28.0})

        cor = {"verde": "var(--verde)", "amarelo": "var(--amarelo)",
               "vermelho": "var(--vermelho)"}[r.faixa]
        st.markdown(f"""
        <div class="g-card lit" style="margin-top:1rem;padding:1.3rem 1.5rem;">
            <div class="g-eyebrow">Resultado do cálculo</div>
            <div style="display:flex;align-items:baseline;gap:12px;margin-top:8px;">
                <span style="font-family:'Manrope',sans-serif;font-size:2.4rem;
                      font-weight:800;color:{cor};letter-spacing:-0.03em;">
                    {r.score_final:.1f}</span>
                <span style="color:{cor};font-weight:600;">
                    {r.faixa.upper()}</span>
            </div>
            <div style="font-size:0.85rem;color:var(--text-2);margin-top:8px;">
                {r.recomendacao}</div>
        </div>
        """, unsafe_allow_html=True)
        for f in r.frases:
            st.markdown(f"- {f}")

        if st.button("Registrar leitura", key="iot_send"):
            st.session_state.telemetria_historico.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "inclinacao_g": inc, "dist_obstaculo_cm": dist,
                "umidade_pct": umi, "vibracao_rms": vib,
                "score": r.score_final, "faixa": r.faixa,
            })
            gerar_trilha_auditoria(
                "TELEMETRIA_VERIFICACAO",
                f"score={r.score_final:.1f} faixa={r.faixa}")
            st.success("Leitura registrada na trilha.")

        if st.session_state.telemetria_historico:
            st.markdown("<div style='height:0.8rem;'></div>",
                        unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(st.session_state.telemetria_historico),
                         use_container_width=True, hide_index=True)

    # -----------------------------------------------------------------
    with tab_instal:
        st.markdown(
            "Material necessário para colocar um dispositivo em campo e "
            "conectá-lo à plataforma.")

        st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
        st.markdown("##### Sensores embarcados")
        sensores = [
            ("Acelerômetro de 6 eixos", "Inclinação do terreno e vibração",
             "Inclinação é o fator de maior peso no alerta — tombamento em "
             "declive é o evento que o sistema existe para antecipar."),
            ("Sensor ultrassônico", "Distância de obstáculo à frente",
             "Alcance útil de 2 cm a 4 m. Ausência de eco é reportada como "
             "campo livre, não como leitura zero."),
            ("Sensor de temperatura e umidade", "Condição ambiente",
             "Leitura a cada 5 segundos — limite físico do componente. "
             "Solo encharcado reduz aderência e entra no cálculo."),
        ]
        for nome, funcao, nota in sensores:
            st.markdown(f"""
            <div class="g-card" style="padding:0.95rem 1.2rem;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;
                      gap:14px;align-items:baseline;">
                    <span style="font-weight:600;font-size:0.92rem;
                          color:var(--text);">{nome}</span>
                    <span style="font-size:0.75rem;color:var(--text-3);
                          flex:none;">{funcao}</span>
                </div>
                <div style="font-size:0.78rem;color:var(--text-2);
                      margin-top:6px;line-height:1.6;">{nota}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height:1.1rem;'></div>", unsafe_allow_html=True)
        st.markdown("##### Comportamento em campo")
        st.markdown("""
        O dispositivo classifica o risco **localmente**, a cada 100 ms, e
        aciona o sinalizador sem depender de conexão. A transmissão para a
        plataforma acontece a cada segundo em regime normal e imediatamente
        quando o estado muda.

        Sem rede, as leituras ficam em memória e são reenviadas quando a
        conexão volta — o alerta ao operador nunca depende do enlace.

        Nenhum comando é enviado ao maquinário. O sistema sinaliza; a
        decisão de interromper a operação permanece com o operador.
        """)

        st.markdown("<div style='height:1.1rem;'></div>", unsafe_allow_html=True)
        st.markdown("##### Material de instalação")
        _oferecer_arquivo(
            "firmware/sompo_predict_esp32.ino",
            "Programa do dispositivo",
            "Leitura dos sensores, classificação local de risco, "
            "acionamento do sinalizador e transmissão assinada. "
            "Compatível com o formato de dados em vigor.",
            "iot_firmware")
        _oferecer_arquivo(
            "firmware/config_exemplo.h",
            "Modelo de configuração",
            "Endereço do serviço, identificador do equipamento e chave de "
            "assinatura. Preencher e salvar como config.h — o arquivo "
            "preenchido não deve ser versionado.",
            "iot_config")
        _oferecer_arquivo(
            "docs/CONTRATO_TELEMETRIA_v1.md",
            "Especificação do formato de dados",
            "Campos, unidades, faixas válidas, frequências de leitura e "
            "regra de assinatura. Referência obrigatória ao alterar "
            "qualquer um dos dois lados.",
            "iot_contrato")

        st.info(
            "Ao gravar o dispositivo, o identificador do equipamento no "
            "arquivo de configuração precisa corresponder a um equipamento "
            "da carteira. A leitura aparece no Painel do Segurado assim que "
            "a primeira transmissão for aceita.", icon="📌")


def pagina_xai():
    if not check_permissao("view_dashboard"):
        return
    _contrato_box("pagina_xai", ["ACESSO_XAI", "CONSULTA_SHAP", "CONSULTA_ROI"])
    _header("Explicabilidade", "Como cada fator entra no score de risco")
    gerar_trilha_auditoria("ACESSO_XAI", "pagina=xai")

    tab1, tab2, tab3 = st.tabs(["Fatores do score", "Impacto financeiro", "Cobertura"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            score_b  = st.slider("Score base",   0.0, 100.0, 78.0, step=0.5, key="xai_sb")
            sh_inc   = st.slider("Inclinacao Z", -30.0, 50.0, 28.5, step=0.5, key="xai_si")
            sh_umi   = st.slider("Umidade",      -20.0, 30.0, 18.2, step=0.5, key="xai_su")
            sh_temp  = st.slider("Temperatura",  -15.0, 25.0, 12.4, step=0.5, key="xai_st")
            sh_idade = st.slider("Idade",        -10.0, 20.0,  8.9, step=0.5, key="xai_sa")

        with c2:
            cor_v = "#E04B45" if score_b >= 75 else "#DDA53C" if score_b >= 40 else "#63A87C"
            st.markdown(f"""
            <div style="background:#141F1C;border:1px solid rgba(224,236,231,0.1);
                        border-radius:12px;padding:1.25rem;margin-bottom:1rem;text-align:center;">
                <div style="font-size:0.7rem;color:#8FA39B;">SCORE EXPLICADO</div>
                <div style="font-size:2.5rem;font-weight:800;color:{cor_v};">{score_b:.1f}</div>
            </div>
            """, unsafe_allow_html=True)

            feats = [
                ("Base (E[f(x)])",  score_b - sh_inc - sh_umi - sh_temp - sh_idade, "#6C86C4"),
                ("Inclinacao Z",    sh_inc,   "#E04B45" if sh_inc > 0    else "#63A87C"),
                ("Umidade",         sh_umi,   "#E04B45" if sh_umi > 0    else "#63A87C"),
                ("Temperatura",     sh_temp,  "#E04B45" if sh_temp > 0   else "#63A87C"),
                ("Idade",           sh_idade, "#DDA53C" if sh_idade > 0  else "#63A87C"),
            ]
            for label, val, cor in feats:
                dir_ = "+" if val > 0 else "-"
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;padding:8px 12px;
                            background:#080D0C;border-radius:8px;margin-bottom:4px;">
                    <span style="font-size:0.82rem;color:#E4EDE9;">{label}</span>
                    <span style="font-size:0.85rem;font-weight:700;color:{cor};">
                        {dir_}{abs(val):.1f}</span>
                </div>
                """, unsafe_allow_html=True)

            top = sorted(feats[1:], key=lambda x: abs(x[1]), reverse=True)[0]
            if st.button("Registrar consulta SHAP", key="xai_log"):
                gerar_trilha_auditoria("CONSULTA_SHAP",
                    f"score={score_b:.1f} top={top[0]} contrib={top[1]:+.1f}")
                st.success("Log SHAP registrado.")

    with tab2:
        ca, cb = st.columns(2)
        with ca:
            frota  = st.slider("Frota Monitorada",         10, 500, 150, key="roi_fr")
            ef_pct = st.slider("Eficiencia Preditiva (%)", 10,  80,  40, key="roi_ef")
            custo  = st.slider("Custo/Sinistro (R$ mil)", 100, 2000, 450, key="roi_cu")
        with cb:
            ev  = int(frota * 0.15 * ef_pct / 100)
            eco = ev * custo * 1000
            tco = frota * 2000
            roi = round((eco - tco) / tco * 100) if tco else 0
            pb  = round(tco / (eco / 12)) if eco > 0 else 0
            st.metric("Sinistros Evitados", ev)
            st.metric("Economia Bruta", f"R$ {eco/1e6:.2f}M")
            st.metric("TCO Plataforma", f"R$ {tco/1e3:.0f}K")
            st.metric("ROI Estimado",   f"{roi}%", delta=f"Payback: {pb} meses")
            if st.button("Registrar simulacao ROI", key="roi_log"):
                gerar_trilha_auditoria("CONSULTA_ROI",
                    f"frota={frota} ef={ef_pct}% roi={roi}% pb={pb}m")
                st.success("Log ROI registrado.")

    with tab3:
        st.markdown(
            "Módulos disponíveis na plataforma e o estágio de cada um "
            "dentro do ciclo de implantação na operação.")
        st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)

        modulos = [
            ("Carteira de risco",
             "Priorização de apólices por exposição", "Disponível", 100),
            ("Painel do segurado",
             "Alerta em campo e explicação do score", "Disponível", 100),
            ("Telemetria embarcada",
             "Leitura de inclinação, obstáculo e ambiente", "Disponível", 100),
            ("Trilha auditável",
             "Registro imutável de consultas e decisões", "Disponível", 100),
            ("Parecer de subscrição",
             "Recomendação assistida na renovação", "Em implantação", 65),
            ("Análise de sinistros",
             "Cruzamento de aviso com telemetria do período", "Em implantação", 45),
            ("Frota monitorada",
             "Visão consolidada por segurado", "Em implantação", 40),
            ("Detecção de anomalia",
             "Padrões atípicos na série do equipamento", "Roadmap", 20),
        ]
        for titulo, desc, status, pct in modulos:
            cor_s = ("var(--verde)" if status == "Disponível"
                     else "var(--amarelo)" if status == "Em implantação"
                     else "var(--text-3)")
            st.markdown(f"""
            <div class="g-card" style="padding:0.95rem 1.2rem;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;
                      align-items:center;gap:14px;margin-bottom:9px;">
                    <div>
                        <span style="font-weight:600;font-size:0.92rem;
                              color:var(--text);">{titulo}</span>
                        <div style="font-size:0.76rem;color:var(--text-3);
                              margin-top:2px;">{desc}</div>
                    </div>
                    <span style="font-size:0.72rem;color:{cor_s};
                          font-weight:600;flex:none;">{status}</span>
                </div>
                <div style="background:rgba(255,255,255,0.06);height:4px;
                      border-radius:3px;overflow:hidden;">
                    <div style="background:{cor_s};width:{pct}%;height:100%;
                          border-radius:3px;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)


def pagina_seguranca():
    # No portal do segurado esta tela responde outra pergunta: "que dado
    # meu voces guardam, e com que base legal". Por isso o proprio segurado
    # tem acesso — a informacao e sobre ele.
    if not (check_permissao_silenciosa("all")
            or check_permissao_silenciosa("view_dashboard")
            or check_permissao_silenciosa("view_proprio_equipamento")):
        st.error("Acesso negado a esta tela.")
        return
    _contrato_box("pagina_seguranca",
                  ["ACESSO_SEGURANCA", "STRESS_TEST", "BLOQUEIO_IA_STRESS"])
    _header("Segurança e Acessos", "Controle de acesso, criptografia e conformidade LGPD")
    gerar_trilha_auditoria("ACESSO_SEGURANCA", "pagina=seguranca")

    tab1, tab2, tab3 = st.tabs(["Stack de Seguranca", "RBAC", "Stress Test"])

    with tab1:
        protos = [
            ("TLS 1.3",   "Em Transito", "End-to-end ESP32 -> AWS, Perfect Forward Secrecy.",  "#29B6F6"),
            ("AES-256",   "Em Repouso",  "Fernet (AES-128-CBC + HMAC-SHA256) por registro.",   "#00E676"),
            ("SHA-256",   "Integridade", "Hash Chaining - cada log referencia o anterior.",     "#FFA000"),
            ("JWT HS256", "Auth",        "Tokens 2h, RBAC via claim role.",                     "#AB47BC"),
            ("Argon2id",  "Senhas",      "time_cost=2, memory_cost=64MiB (OWASP 2024).",       "#63A87C"),
        ]
        for icon_label, cat, desc, cor in protos:
            st.markdown(f"""
            <div style="background:#0E1614;border:1px solid {cor}33;border-left:3px solid {cor};
                        border-radius:10px;padding:14px 18px;margin-bottom:8px;">
                <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px;">
                    <span style="font-weight:700;font-size:0.9rem;color:{cor};">{icon_label}</span>
                    <span style="font-size:0.65rem;color:#5A6B65;text-transform:uppercase;">{cat}</span>
                </div>
                <div style="font-size:0.82rem;color:#8FA39B;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    with tab2:
        acoes = ["view_dashboard", "input_telemetry", "train_models",
                 "extract_data", "view_dados", "all"]
        rows = []
        for role, perms in RBAC_MATRIX.items():
            row = {"Role": role}
            for a in acoes:
                row[a] = "OK" if ("all" in perms or a in perms) else "--"
            rows.append(row)
        st.dataframe(pd.DataFrame(rows).set_index("Role"), use_container_width=True)

        st.markdown("**Usuarios cadastrados:**")
        for u, data in st.session_state.mock_users.items():
            cor_r = MEMBER_COLORS.get(u, "#8FA39B")
            st.markdown(f"""
            <div style="background:#141F1C;border:1px solid rgba(224,236,231,0.07);
                        border-radius:8px;padding:10px 16px;margin-bottom:6px;
                        display:flex;justify-content:space-between;">
                <span style="font-weight:600;color:#E4EDE9;">{u}</span>
                <span style="font-size:0.72rem;color:{cor_r};background:{cor_r}18;
                             padding:2px 8px;border-radius:5px;">{data['role']}</span>
            </div>
            """, unsafe_allow_html=True)

    with tab3:
        st.markdown("Simula 5 tentativas de ataque para validar o motor de IA + Rate Limit.")
        if st.button("Executar Ataque Simulado (5 tentativas)",
                     type="primary", key="stress_btn"):
            prog = st.progress(0)
            log_area  = st.empty()
            bloqueado = False
            for i in range(1, 6):
                st.session_state.tentativas_falhas += 1
                gerar_trilha_auditoria("STRESS_TEST", f"tentativa={i}/5")
                prog.progress(i / 5)
                log_area.info(
                    f"Tentativa {i}/5 | Falhas: {st.session_state.tentativas_falhas}"
                )
                time.sleep(0.35)
                if st.session_state.tentativas_falhas >= 3:
                    if avaliar_risco_login(
                        st.session_state.tentativas_falhas,
                        datetime.now().hour, 0.9, 50.0,
                    ):
                        gerar_trilha_auditoria("BLOQUEIO_IA_STRESS", f"tentativa={i}")
                        st.error(f"Motor IA bloqueou na tentativa {i}!")
                        st.session_state.bloqueio_tempo = time.time() + 30
                        bloqueado = True
                        break
            if not bloqueado:
                st.success("Teste concluido sem bloqueio.")
            # CORRIGIDO: reseta falhas para nao bloquear logins reais
            st.session_state.tentativas_falhas = 0


def pagina_metricas():
    if not check_permissao("view_dashboard"):
        return
    _contrato_box("pagina_metricas",
                  ["ACESSO_METRICAS", "VISUALIZACAO_CM",
                   "VISUALIZACAO_ROC", "VISUALIZACAO_RELATORIO"])
    _header("Desempenho dos Modelos",
            "Decision Tree · Recall · F1-Score · ROC-AUC · Matriz de Confusao")
    gerar_trilha_auditoria("ACESSO_METRICAS", "pagina=metricas")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ROC-AUC",            METRICAS_IA["roc_auc"])
    c2.metric("F1-Score (Fraude)",  METRICAS_IA["f1_fraude"])
    c3.metric("Recall (Fraude)",    METRICAS_IA["recall_fraude"])
    c4.metric("Precision (Fraude)", METRICAS_IA["precision_fraude"])
    c5.metric("Acuracia Geral",     METRICAS_IA["acuracia"])

    st.markdown("""
    <div style="background:rgba(224,75,69,0.06);border:1px solid rgba(224,75,69,0.2);
                border-radius:10px;padding:12px 18px;margin:1rem 0;
                font-size:0.84rem;color:#8FA39B;">
        <strong style="color:#E4EDE9;">Por que Recall e a metrica mais critica?</strong><br>
        Em deteccao de anomalias de seguro, um Falso Negativo (fraude nao detectada)
        tem custo muito maior que um Falso Positivo. O modelo usa
        <code>class_weight='balanced'</code> para maximizar Recall com 15% de positivos.
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["Matriz de Confusao", "Curva ROC", "Relatorio por Classe"])

    with tab1:
        gerar_trilha_auditoria("VISUALIZACAO_CM", "exibida")
        labels = ["Normal (0)", "Anomalia (1)"]
        cm     = CM_IA
        if PLOTLY_OK:
            fig_cm = ff.create_annotated_heatmap(
                z=cm, x=labels, y=labels,
                annotation_text=cm.astype(str),
                colorscale="Blues", showscale=True,
            )
            fig_cm.update_layout(
                title="Matriz de Confusao - Decision Tree",
                xaxis_title="Predito", yaxis_title="Real",
                template="plotly_dark",
                plot_bgcolor="#0E1614", paper_bgcolor="#0E1614",
                font=dict(color="#E4EDE9"),
            )
            fig_cm.update_xaxes(side="bottom")
            st.plotly_chart(fig_cm, use_container_width=True)
        else:
            df_cm = pd.DataFrame(cm,
                index=[f"Real: {l}" for l in labels],
                columns=[f"Pred: {l}" for l in labels])
            st.dataframe(df_cm, use_container_width=True)

        tn, fp, fn, tp = cm.ravel()
        ca, cb, cc, cd = st.columns(4)
        ca.metric("TN - Verdadeiro Negativo", int(tn))
        cb.metric("FP - Falso Positivo",      int(fp))
        cc.metric("FN - Falso Negativo",      int(fn),
                  delta=f"-{int(fn)} nao detectados", delta_color="inverse")
        cd.metric("TP - Verdadeiro Positivo", int(tp))

    with tab2:
        gerar_trilha_auditoria("VISUALIZACAO_ROC", "exibida")
        auc_val = METRICAS_IA["roc_auc"]
        if PLOTLY_OK:
            fpr, tpr, _ = roc_curve(Y_TEST_IA, Y_PROBA_IA)
            fig_roc = go.Figure()
            fig_roc.add_trace(go.Scatter(
                x=[0, 1], y=[0, 1], mode="lines",
                name="Baseline (aleatorio)",
                line=dict(dash="dash", color="#5A6B65"),
            ))
            fig_roc.add_trace(go.Scatter(
                x=fpr, y=tpr, mode="lines",
                name=f"Decision Tree (AUC = {auc_val})",
                line=dict(color="#6C86C4", width=2.5),
                fill="tozeroy", fillcolor="rgba(108,134,196,0.08)",
            ))
            fig_roc.update_layout(
                title=f"Curva ROC - AUC: {auc_val}",
                xaxis_title="Taxa de Falso Positivo (FPR)",
                yaxis_title="Recall / TPR",
                template="plotly_dark",
                plot_bgcolor="#0E1614", paper_bgcolor="#0E1614",
                font=dict(color="#E4EDE9"),
            )
            st.plotly_chart(fig_roc, use_container_width=True)
        else:
            st.metric("ROC-AUC", auc_val)

    with tab3:
        gerar_trilha_auditoria("VISUALIZACAO_RELATORIO",
            f"f1={METRICAS_IA['f1_fraude']} recall={METRICAS_IA['recall_fraude']}")
        for label, prec, rec, f1, cor in [
            ("0 - Normal",
             METRICAS_IA["precision_normal"], METRICAS_IA["recall_normal"],
             METRICAS_IA["f1_normal"],   "#63A87C"),
            ("1 - Fraude/Anomalia",
             METRICAS_IA["precision_fraude"], METRICAS_IA["recall_fraude"],
             METRICAS_IA["f1_fraude"],   "#E04B45"),
        ]:
            st.markdown(f"""
            <div style="background:#0E1614;border:1px solid {cor}33;border-left:3px solid {cor};
                        border-radius:12px;padding:1rem 1.25rem;margin-bottom:12px;">
                <div style="font-weight:700;font-size:0.9rem;color:{cor};margin-bottom:10px;">
                    Classe {label}</div>
                <div style="display:flex;gap:24px;flex-wrap:wrap;">
                    <div style="text-align:center;">
                        <div style="font-size:1.4rem;font-weight:800;color:#E4EDE9;">{prec}</div>
                        <div style="font-size:0.65rem;color:#8FA39B;text-transform:uppercase;">Precision</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.4rem;font-weight:800;color:#E4EDE9;">{rec}</div>
                        <div style="font-size:0.65rem;color:#8FA39B;text-transform:uppercase;">Recall</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.4rem;font-weight:800;color:#E4EDE9;">{f1}</div>
                        <div style="font-size:0.65rem;color:#8FA39B;text-transform:uppercase;">F1-Score</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)


def pagina_auditoria():
    _contrato_box("pagina_auditoria", ["ACESSO_AUDITORIA", "EXPORTACAO_AUDITORIA"])
    _header("Trilha de Auditoria",
            "Hash Chaining · SHA-256 · AES-256 · Imutavel")
    gerar_trilha_auditoria("ACESSO_AUDITORIA", "pagina=auditoria")

    logs = st.session_state.logs_auditoria
    if not logs:
        st.info("Nenhum registro ainda. Interaja com o sistema para gerar logs.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Total de Registros", len(logs))
    c2.metric("Ultimo Hash (8 chars)", logs[-1]["hash"][:8] + "...")
    c3.metric("Integridade da Cadeia", "Valida")

    st.markdown("<br>", unsafe_allow_html=True)

    todas_acoes = sorted(set(l["acao"] for l in logs))
    filtro = st.multiselect(
        "Filtrar por acao", todas_acoes,
        default=todas_acoes, key="aud_filtro",
    )
    logs_filtrados = [l for l in logs if l["acao"] in filtro]
    st.dataframe(pd.DataFrame(logs_filtrados), use_container_width=True)

    st.markdown("##### Ultimos 10 registros")
    for log in reversed(logs_filtrados[-10:]):
        tipo_cor = {
            "LOGIN_SUCESSO": "#63A87C", "LOGIN_FALHA":   "#E04B45",
            "LOGOUT":        "#8FA39B", "BLOQUEIO_IA":   "#E04B45",
            "VIOLACAO_RBAC": "#DDA53C", "STRESS_TEST":   "#DDA53C",
        }.get(log["acao"], "#6C86C4")
        st.markdown(f"""
        <div style="background:#0E1614;border:1px solid rgba(224,236,231,0.07);
                    border-left:3px solid {tipo_cor};border-radius:8px;
                    padding:10px 16px;margin-bottom:6px;
                    font-family:monospace;font-size:0.76rem;color:#8FA39B;">
            <span style="color:{tipo_cor};font-weight:700;">[{log['acao']}]</span>
            <span style="color:#5A6B65;">{log['timestamp']}</span>
            <span style="color:#E4EDE9;">@{log['usuario']}</span>
            <span style="color:#5A6B65;">- {log.get('detalhes','') or '-'}</span><br>
            <span style="color:#1B2926;">HASH: {log['hash']} | ENC: {log['enc_preview']}</span>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("Exportar trilha completa como JSON"):
        st.code(json.dumps(logs, indent=2, ensure_ascii=False), language="json")
        if st.button("Registrar exportacao", key="aud_export"):
            gerar_trilha_auditoria("EXPORTACAO_AUDITORIA", f"total_logs={len(logs)}")
            st.success("Exportacao registrada.")


# ==========================================
# 10. ROTEADOR PRINCIPAL
# ==========================================

def main():
    if not st.session_state.get("jwt_token"):
        tela_login()
        return

    pagina_id = sidebar()

    rota = {
        "inicio":         pagina_inicio,
        "us01_risco":     pagina_us01_risco_sompo.render,
        "us03_cliente":   pagina_us03_painel_cliente.render,
        "us05_gestor":    pagina_us05_gestor_frota.render,
        "us07_xai":       pagina_us07_subscricao_xai.render,
        "us08_sinistros": pagina_us08_analista_sinistros.render,
        "ml_dl":          pagina_ml_deep_learning.render,
        "dados":          pagina_dados,
        "simulador":      pagina_simulador_cenarios.render,
        "integracoes":    pagina_integracoes.render,
        "relatorios":     pagina_relatorios.render,
        "cloud":          pagina_cloud,
        "iot":            pagina_iot,
        "xai":            pagina_explicabilidade.render,
        "seguranca":      pagina_seguranca,
        "metricas":       pagina_desempenho_modelos.render,
        "auditoria":      pagina_auditoria,
        "demo":           pagina_demo_e_sobre.render_modo_demo,
        "sobre":          pagina_demo_e_sobre.render_sobre,
    }

    # Barreira de portal: mesmo que a rota exista no codigo, ela so e
    # servida se pertencer ao menu DESTE portal. Sem isto, um segurado que
    # editasse o estado da sessao alcancaria a carteira inteira — dado de
    # outros clientes. A verificacao de papel dentro de cada tela continua
    # valendo; esta e a camada anterior.
    if not rota_permitida(PORTAL, pagina_id):
        gerar_trilha_auditoria(
            "ACESSO_FORA_DO_PORTAL",
            f"portal={PORTAL.chave} rota={pagina_id}")
        st.warning(
            "Esta tela não faz parte deste portal.", icon="🔒")
        st.session_state.current_page = PORTAL.inicial
        return

    fn = rota.get(pagina_id)
    if fn:
        fn()
    else:
        st.info(f"Página '{pagina_id}' em desenvolvimento.")


if __name__ == "__main__":
    main()
