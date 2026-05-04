# ==========================================
# SOMPO PREDICT v15 - SECURE GATEWAY
# app.py - Roteador principal Streamlit
#
# Instalacao:
#   pip install -r requirements.txt
#
# Execucao:
#   streamlit run app.py
#
# Login padrao:
#   usuario: admin
#   senha:   Admin@2024!
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
from sklearn.datasets import make_classification
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

# ── User Stories do Charles (placeholders funcionais) ─────────────────
import pagina_us01_risco_sompo
import pagina_us03_painel_cliente
import pagina_us05_gestor_frota
import pagina_us07_subscricao_xai
import pagina_us08_analista_sinistros
import pagina_demo_e_sobre
import pagina_ml_deep_learning

# ── Adapter pattern (Frente 4) ────────────────────────────────────────
from core_data_adapter import garantir_pasta_data
garantir_pasta_data()

# ==========================================
# 0. CONFIGURACAO DA PAGINA
# ==========================================

st.set_page_config(
    page_title="Sompo Predict v15",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
:root {
    --bg:#07080C; --surface:#0D0F18; --surface2:#131520;
    --border:rgba(255,255,255,0.07); --accent:#5B7FFF;
    --green:#22D48A; --amber:#F5A623; --red:#FF4D6A;
    --purple:#A855F7; --text:#EEF0F8; --text2:#8B8FA8;
}
section[data-testid="stSidebar"] {
    background:#0D0F18 !important;
    border-right:1px solid rgba(255,255,255,0.07) !important;
}
section[data-testid="stSidebar"] .block-container { padding:1.5rem 1rem; }
div[data-testid="metric-container"] {
    background:#131520; border:1px solid rgba(255,255,255,0.07);
    border-radius:12px; padding:1rem 1.25rem;
}
details { border:1px solid rgba(255,255,255,0.07) !important; border-radius:10px; }
::-webkit-scrollbar { width:4px; }
::-webkit-scrollbar-track { background:#07080C; }
::-webkit-scrollbar-thumb { background:#252840; border-radius:2px; }
.stDataFrame { border:1px solid rgba(255,255,255,0.07) !important; border-radius:10px; }
.contrato-box {
    background:rgba(91,127,255,0.06); border:1px solid rgba(91,127,255,0.25);
    border-left:3px solid #5B7FFF; border-radius:10px;
    padding:14px 18px; margin-bottom:1.5rem;
    font-size:0.82rem; color:#8B8FA8; line-height:1.65;
}
.contrato-box strong { color:#EEF0F8; }
.contrato-box code { color:#22D48A; font-size:0.78rem; }
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
    st.session_state.mock_users = {
        "admin": {
            "senha_hash": st.session_state.ph.hash("Admin@2024!"),
            "role": "Admin",
        }
    }


_init_session()

# ==========================================
# 2. CONSTANTES
# ==========================================

RBAC_MATRIX = {
    "Admin":     ["all"],
    "Cientista": ["view_dashboard", "train_models", "extract_data", "view_dados"],
    "Operador":  ["view_dashboard", "input_telemetry", "view_iot"],
}

MENU_ITEMS = {
    "🏠  Inicio":                      "inicio",
    "🛡️  Gestao de Risco (US01)":      "us01_risco",
    "👨‍🌾  Painel do Segurado (US03)":   "us03_cliente",
    "🚜  Gestor de Frota (US05)":      "us05_gestor",
    "🎯  Subscricao XAI (US07)":       "us07_xai",
    "🔍  Analise de Sinistros (US08)": "us08_sinistros",
    "🧠  ML & Deep Learning":          "ml_dl",
    "📊  Dados & Estatistica":         "dados",
    "☁️  Cloud & IA":                  "cloud",
    "📡  IoT & Telemetria":            "iot",
    "🎯  XAI & Gestao":                "xai",
    "🔐  Seguranca & Auth":            "seguranca",
    "📈  Metricas do Modelo":          "metricas",
    "⛓️  Trilha de Auditoria":         "auditoria",
    "▶️  Modo Demo (Pitch)":           "demo",
    "ℹ️  Sobre o Projeto":             "sobre",
}

MEMBER_COLORS = {
    "Guilherme": "#F5A623",
    "Gustavo":   "#FF4D6A",
    "Anthony":   "#A855F7",
    "Rafael":    "#5B7FFF",
    "Charles":   "#22D48A",
}

# ==========================================
# 3. MOTOR DE RISCO IA
# ==========================================

@st.cache_resource
def treinar_motor_risco():
    X, y = make_classification(
        n_samples=2000, n_features=4, n_informative=3,
        n_redundant=1, weights=[0.85, 0.15], random_state=42,
    )
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )
    clf = DecisionTreeClassifier(max_depth=5, class_weight="balanced", random_state=42)
    clf.fit(X_train, y_train)

    y_pred  = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]
    cm_mat  = confusion_matrix(y_test, y_pred)
    rel     = classification_report(y_test, y_pred, output_dict=True)

    return {
        "modelo":  clf,
        "y_test":  y_test,
        "y_proba": y_proba,
        "cm":      cm_mat,
        "metricas": {
            "roc_auc":          round(roc_auc_score(y_test, y_proba), 4),
            "precision_fraude": round(rel["1"]["precision"], 4),
            "recall_fraude":    round(rel["1"]["recall"],    4),
            "f1_fraude":        round(rel["1"]["f1-score"],  4),
            "acuracia":         round(rel["accuracy"],       4),
            "precision_normal": round(rel["0"]["precision"], 4),
            "recall_normal":    round(rel["0"]["recall"],    4),
            "f1_normal":        round(rel["0"]["f1-score"],  4),
        },
    }


_cache         = treinar_motor_risco()
MOTOR_RISCO_IA = _cache["modelo"]
METRICAS_IA    = _cache["metricas"]
CM_IA          = _cache["cm"]
Y_TEST_IA      = _cache["y_test"]
Y_PROBA_IA     = _cache["y_proba"]


def avaliar_risco_login(falhas, hora, ip_score, latencia):
    # CORRIGIDO: 0 falhas = NUNCA bloqueia (antes ele bloqueava no primeiro login)
    if falhas == 0:
        return False
    feat = np.array([[falhas, hora, ip_score, latencia]])
    return MOTOR_RISCO_IA.predict_proba(feat)[0][1] > 0.60


# ==========================================
# 4-6. TRILHA, RBAC, HELPERS - importados do core_app
# ==========================================
# As funcoes gerar_trilha_auditoria, check_permissao, _header, _contrato_box,
# _verificar_senha estao em core_app.py (importado abaixo).
# Single source of truth - mesmas funcoes usadas pelas paginas pagina_*.py
from core_app import (
    gerar_trilha_auditoria,
    check_permissao,
    verificar_senha as _verificar_senha,
    _header,
    _contrato_box,
)


def _dataset_susep_mock():
    np.random.seed(42)
    n = 120
    sinistros = np.random.choice([0, 1, 2, 3], n, p=[0.55, 0.25, 0.12, 0.08])
    return pd.DataFrame({
        "ID_Apolice":    [f"AP-{1000+i}" for i in range(n)],
        "Equipamento":   np.random.choice(
            ["Colheitadeira", "Trator", "Pulverizador", "Plantadeira"], n),
        "Regiao":        np.random.choice(
            ["Sul", "Centro-Oeste", "Sudeste", "Norte", "Nordeste"], n),
        "Idade_Anos":    np.random.randint(1, 20, n),
        "Valor_BRL":     np.random.randint(200_000, 2_000_000, n),
        "Sinistros_Ano": sinistros,
        "Temp_Max_C":    np.round(np.random.uniform(22, 42, n), 1),
        "Umidade_Pct":   np.round(np.random.uniform(30, 95, n), 1),
        "Score_Risco":   np.round(np.clip(
            sinistros * 25 + np.random.uniform(5, 30, n), 0, 100), 1),
    })


# ==========================================
# 7. TELA DE LOGIN / REGISTRO
# ==========================================

def tela_login():
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown("""
        <div style="text-align:center;padding:2rem 0 1.5rem;">
            <div style="font-size:2.5rem;margin-bottom:0.5rem;">🌾</div>
            <div style="font-size:1.8rem;font-weight:800;color:#EEF0F8;">Sompo Predict</div>
            <div style="font-size:0.85rem;color:#8B8FA8;margin-top:4px;">
                Secure Gateway · Squad T1 · FIAP 2026
            </div>
        </div>
        """, unsafe_allow_html=True)

        # CORRIGIDO: reset automatico quando bloqueio expirou
        if st.session_state.tentativas_falhas >= 3:
            restante = st.session_state.bloqueio_tempo - time.time()
            if restante > 0:
                st.error(f"Bloqueio temporario: aguarde {int(restante)}s.")
                return
            st.session_state.tentativas_falhas = 0
            st.session_state.bloqueio_tempo    = 0.0

        tab_login, tab_reg = st.tabs(["  Entrar  ", "  Registrar  "])

        with tab_login:
            with st.form("form_login", clear_on_submit=False):
                usuario = st.text_input("Usuario", placeholder="ex: admin")
                senha   = st.text_input("Senha",   placeholder="••••••••", type="password")
                st.caption("Conta padrao: `admin` / `Admin@2024!`")
                submit  = st.form_submit_button("Entrar", use_container_width=True)

            if submit:
                # 1. WAF - formato do usuario
                if not re.match(r"^[a-zA-Z0-9_]{3,20}$", usuario):
                    st.warning("WAF: formato de usuario invalido (3-20 chars alfanumericos).")
                    st.session_state.tentativas_falhas += 1
                    return

                # 2. Motor de IA - so avalia se ja houve falhas anteriores
                # CORRIGIDO: ip_score negativo na primeira tentativa = nao bloqueia
                ip_score = 0.8 if st.session_state.tentativas_falhas >= 2 else -0.8
                if avaliar_risco_login(
                    st.session_state.tentativas_falhas,
                    datetime.now().hour,
                    ip_score, 45.0,
                ):
                    st.session_state.tentativas_falhas += 3
                    st.session_state.bloqueio_tempo = time.time() + 30
                    gerar_trilha_auditoria("BLOQUEIO_IA", f"usuario={usuario}")
                    st.error("Motor de IA bloqueou acesso anomalo. Aguarde 30s.")
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
    with st.sidebar:
        cor      = MEMBER_COLORS.get(st.session_state.usuario_logado, "#5B7FFF")
        initials = (st.session_state.usuario_logado or "??")[:2].upper()
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;padding:0.5rem 0 1.5rem;">
            <div style="width:40px;height:40px;border-radius:10px;background:{cor}22;
                        border:1.5px solid {cor};display:flex;align-items:center;
                        justify-content:center;font-weight:700;font-size:1rem;color:{cor};">
                {initials}</div>
            <div>
                <div style="font-weight:600;color:#EEF0F8;font-size:0.9rem;">
                    {st.session_state.usuario_logado}</div>
                <div style="font-size:0.7rem;color:#8B8FA8;">
                    {st.session_state.role_logado}</div>
            </div>
        </div>
        <div style="height:1px;background:rgba(255,255,255,0.07);margin-bottom:1rem;"></div>
        """, unsafe_allow_html=True)

        st.markdown(
            "<div style='font-size:0.65rem;color:#4A4D62;text-transform:uppercase;"
            "letter-spacing:0.1em;margin-bottom:8px;'>Navegacao</div>",
            unsafe_allow_html=True,
        )
        pagina = st.radio("menu", list(MENU_ITEMS.keys()), label_visibility="collapsed")

        st.markdown(
            "<div style='height:1px;background:rgba(255,255,255,0.07);"
            "margin:1.5rem 0 1rem;'></div>",
            unsafe_allow_html=True,
        )

        n_logs = len(st.session_state.logs_auditoria)
        n_tele = len(st.session_state.telemetria_historico)
        st.markdown(f"""
        <div style="font-size:0.72rem;color:#8B8FA8;line-height:1.9;">
            <div>Hashes: <strong style="color:#22D48A;">{n_logs}</strong></div>
            <div>Usuarios: <strong style="color:#EEF0F8;">{len(st.session_state.mock_users)}</strong></div>
            <div>Telemetria: <strong style="color:#EEF0F8;">{n_tele}</strong> leituras</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        if st.button("Encerrar Sessao", use_container_width=True):
            gerar_trilha_auditoria("LOGOUT", "logout manual")
            for k in ["jwt_token", "usuario_logado", "role_logado"]:
                st.session_state[k] = None
            st.rerun()

    return MENU_ITEMS[pagina]


# ==========================================
# 9. PAGINAS DO MENU
# ==========================================

def pagina_inicio():
    _contrato_box("pagina_inicio", ["ACESSO_INICIO"])
    gerar_trilha_auditoria("ACESSO_INICIO", "pagina=inicio")

    st.markdown("""
    <div style="padding:2rem 0 1rem;">
        <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                    letter-spacing:0.12em;margin-bottom:8px;">
            Sprint 1 · Sompo Challenge 2026</div>
        <h1 style="font-size:2.8rem;font-weight:800;color:#EEF0F8;
                   letter-spacing:-0.02em;line-height:1.05;margin:0;">
            Sompo Predict <span style="color:#5B7FFF;">v15</span>
        </h1>
        <p style="color:#8B8FA8;margin-top:0.75rem;font-size:1rem;max-width:600px;">
            Score preditivo, explicavel e auditavel - da telemetria no campo
            ate o dashboard da seguradora.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # CTA para o modo demo - destaque para o pitch
    col_cta1, col_cta2 = st.columns([2, 1])
    with col_cta1:
        st.markdown("""
        <div style="background:linear-gradient(135deg,rgba(91,127,255,0.1),
                                                      rgba(34,212,138,0.05));
                    border:1px solid rgba(91,127,255,0.3);
                    border-left:3px solid #5B7FFF;border-radius:10px;
                    padding:14px 18px;">
            <div style="font-size:0.75rem;color:#5B7FFF;text-transform:uppercase;
                        letter-spacing:0.1em;margin-bottom:4px;">
                Pitch 06/05</div>
            <div style="font-size:0.9rem;color:#EEF0F8;line-height:1.6;">
                Use o <strong>Modo Demo</strong> no menu para apresentar o projeto
                com roteiro guiado de 8 etapas (~5 minutos).
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_cta2:
        st.markdown("""
        <div style="background:#0D0F18;border:1px solid rgba(255,255,255,0.07);
                    border-radius:10px;padding:14px 18px;height:100%;
                    display:flex;flex-direction:column;justify-content:center;">
            <div style="font-size:0.7rem;color:#8B8FA8;">Total de paginas</div>
            <div style="font-size:1.5rem;font-weight:800;color:#22D48A;">15</div>
        </div>
        """, unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        ("8",     "User Stories", "#5B7FFF"),
        ("5",     "Membros",      "#22D48A"),
        ("8",     "Materias",     "#F5A623"),
        ("06/05", "Pitch",        "#FF4D6A"),
        ("10/05", "Deadline",     "#A855F7"),
    ]
    for col, (val, lab, cor) in zip([c1, c2, c3, c4, c5], kpis):
        col.markdown(f"""
        <div style="background:#0D0F18;border:1px solid rgba(255,255,255,0.07);
                    border-radius:12px;padding:1rem;text-align:center;">
            <div style="font-size:1.6rem;font-weight:800;color:{cor};line-height:1;">{val}</div>
            <div style="font-size:0.65rem;color:#4A4D62;text-transform:uppercase;
                        letter-spacing:0.08em;margin-top:6px;">{lab}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Pipeline da Solucao")
    steps = [
        ("📡", "IoT / Edge",     "ESP32 + MPU-6050\nDHT22 + GPS",      "Anthony",   "#A855F7"),
        ("📊", "Dados",          "SUSEP + INMET\nEDA + Anomalias",      "Guilherme", "#F5A623"),
        ("☁️", "Cloud & IA",    "AWS EC2 + Flask\nXGBoost + LSTM",     "Gustavo",   "#FF4D6A"),
        ("🎯", "XAI Dashboard",  "SHAP Values\nScore Explicavel",       "Rafael",    "#5B7FFF"),
        ("🔐", "Seg. & Audit.",  "SHA-256 + RBAC\nAES-256 + JWT",      "Charles",   "#22D48A"),
    ]
    cols = st.columns(5)
    for col, (icon, titulo, desc, membro, cor) in zip(cols, steps):
        col.markdown(f"""
        <div style="background:#0D0F18;border:1px solid {cor}33;border-top:2px solid {cor};
                    border-radius:12px;padding:1rem;text-align:center;">
            <div style="font-size:1.6rem;margin-bottom:6px;">{icon}</div>
            <div style="font-weight:700;font-size:0.85rem;color:#EEF0F8;">{titulo}</div>
            <div style="font-size:0.7rem;color:#8B8FA8;margin:6px 0;line-height:1.5;
                        white-space:pre-line;">{desc}</div>
            <div style="font-size:0.65rem;color:{cor};text-transform:uppercase;">{membro}</div>
        </div>
        """, unsafe_allow_html=True)


def pagina_dados():
    if not check_permissao("view_dados") and not check_permissao("view_dashboard"):
        return
    _contrato_box("pagina_dados", ["ACESSO_DADOS", "EXPORTACAO_CSV", "DETECCAO_ANOMALIAS"])
    _header("Dados & Estatistica", "Guilherme", "Base SUSEP · EDA · Anomalias Z-Score")
    gerar_trilha_auditoria("ACESSO_DADOS", "pagina=dados")

    df = _dataset_susep_mock()
    tab1, tab2, tab3 = st.tabs(["Dataset", "Visualizacoes", "Anomalias Z-Score"])

    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Apolices", len(df))
        c2.metric("Sinistros medios", round(df["Sinistros_Ano"].mean(), 2))
        c3.metric("Valor medio (R$)", f"{df['Valor_BRL'].mean()/1e6:.2f}M")
        c4.metric("Score medio", round(df["Score_Risco"].mean(), 1))
        st.dataframe(df.head(30), use_container_width=True)
        if st.button("Simular exportacao CSV", key="dados_export"):
            gerar_trilha_auditoria("EXPORTACAO_CSV",
                f"linhas={len(df)} colunas={len(df.columns)}")
            st.success("Exportacao registrada na trilha.")

    with tab2:
        if PLOTLY_OK:
            ca, cb = st.columns(2)
            with ca:
                fig1 = px.histogram(df, x="Score_Risco", nbins=20, color="Equipamento",
                                    title="Score por Equipamento", template="plotly_dark")
                fig1.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18")
                st.plotly_chart(fig1, use_container_width=True)
            with cb:
                mr = df.groupby("Regiao")["Score_Risco"].mean().reset_index()
                fig2 = px.bar(mr, x="Regiao", y="Score_Risco",
                              title="Score Medio por Regiao",
                              color="Score_Risco", color_continuous_scale="RdYlGn_r",
                              template="plotly_dark")
                fig2.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18")
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Instale plotly para ver os graficos.")
            st.bar_chart(df.groupby("Regiao")["Score_Risco"].mean())

    with tab3:
        df_z = df.copy()
        mu, sigma = df_z["Score_Risco"].mean(), df_z["Score_Risco"].std()
        df_z["Z_Score"]  = ((df_z["Score_Risco"] - mu) / sigma).round(3)
        df_z["Anomalia"] = df_z["Z_Score"].abs() > 2
        anomalias = df_z[df_z["Anomalia"]]
        st.info(f"{len(anomalias)} anomalias em {len(df_z)} registros "
                f"({100*len(anomalias)/len(df_z):.1f}%)")
        st.dataframe(
            anomalias[["ID_Apolice", "Equipamento", "Regiao", "Score_Risco", "Z_Score"]],
            use_container_width=True,
        )
        if st.button("Registrar deteccao na trilha", key="dados_anomalia"):
            gerar_trilha_auditoria("DETECCAO_ANOMALIAS",
                f"anomalias={len(anomalias)} algo=ZScore")
            st.success("Log registrado.")


def pagina_cloud():
    if not check_permissao("train_models") and not check_permissao("view_dashboard"):
        return
    _contrato_box("pagina_cloud", ["ACESSO_CLOUD", "API_SCORE_CALL"])
    _header("Cloud & IA", "Gustavo", "AWS EC2 · Flask API · Score Simulado")
    gerar_trilha_auditoria("ACESSO_CLOUD", "pagina=cloud")

    tab1, tab2 = st.tabs(["Infraestrutura AWS", "Simulador API /score"])

    with tab1:
        recursos = [
            ("EC2 t2.micro",   "Instancia Free Tier - Flask",     "Online"),
            ("Security Group", "Portas 22 e 5000 abertas",        "Ativo"),
            ("S3 Data Lake",   "Parquet - telemetria e modelos",  "Conectado"),
            ("SageMaker",      "Endpoint XGBoost + LSTM",         "Staging"),
            ("CloudWatch",     "Logs e metricas",                 "Monitorando"),
        ]
        for nome, desc, status in recursos:
            cor_s = "#22D48A" if status != "Staging" else "#F5A623"
            st.markdown(f"""
            <div style="background:#131520;border:1px solid rgba(255,255,255,0.07);
                        border-radius:10px;padding:12px 16px;margin-bottom:8px;
                        display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div style="font-weight:600;color:#EEF0F8;font-size:0.88rem;">{nome}</div>
                    <div style="font-size:0.72rem;color:#8B8FA8;">{desc}</div>
                </div>
                <div style="font-size:0.72rem;color:{cor_s};padding:3px 10px;
                            background:{cor_s}15;border-radius:6px;">{status}</div>
            </div>
            """, unsafe_allow_html=True)

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            inclin  = st.slider("Inclinacao Z (graus)", 0, 45, 10, key="cloud_inc")
            umidade = st.slider("Umidade (%)",         20, 100, 55, key="cloud_umi")
        with c2:
            temp  = st.slider("Temp. Motor (C)", 60, 130, 85, key="cloud_temp")
            idade = st.slider("Idade (anos)",     1,  25,  5, key="cloud_idade")

        score = round(min(
            min(inclin, 40)/40*40 + min(umidade, 100)/100*20
            + max(0, temp-90)/40*25 + min(idade, 20)/20*15, 100), 1)
        cor_s = "#FF4D6A" if score >= 75 else "#F5A623" if score >= 40 else "#22D48A"

        st.markdown(f"""
        <div style="background:#131520;border:1px solid rgba(255,255,255,0.12);
                    border-radius:12px;padding:1.5rem;text-align:center;margin-top:1rem;">
            <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                        letter-spacing:0.1em;margin-bottom:8px;">Score XGBoost (mock)</div>
            <div style="font-size:3rem;font-weight:800;color:{cor_s};">{score}</div>
            <div style="font-size:0.85rem;color:#8B8FA8;margin-top:4px;">/ 100</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Simular POST /score", key="cloud_api"):
            resp = {
                "status":    "ok",
                "device_id": "COL-099",
                "score":     score,
                "categoria": "CRITICO" if score >= 75 else "ATENCAO" if score >= 40 else "NORMAL",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            st.code(json.dumps(resp, indent=2), language="json")
            gerar_trilha_auditoria("API_SCORE_CALL",
                f"score={score} inc={inclin} umi={umidade} temp={temp}")
            st.success("Log de inferencia registrado.")


def pagina_iot():
    if not check_permissao("input_telemetry") and not check_permissao("view_dashboard"):
        return
    _contrato_box("pagina_iot", ["ACESSO_IOT", "TELEMETRIA_ENVIADA"])
    _header("IoT & Telemetria", "Anthony", "ESP32 · MPU-6050 · DHT22 · Edge Computing")
    gerar_trilha_auditoria("ACESSO_IOT", "pagina=iot")

    tab1, tab2 = st.tabs(["Leitura de Sensor", "Historico"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            device_id = st.selectbox("ID do Equipamento",
                ["TRAT-047", "COLH-012", "TRAT-099", "COLH-088"], key="iot_dev")
            contexto  = st.selectbox("Contexto Operacional",
                ["Campo", "Transporte em Estrada", "Area Critica"], key="iot_ctx")
            inc_z   = st.number_input("Inclinacao Eixo Z (graus)",
                                      -45.0, 45.0, 12.0, step=0.5, key="iot_z")
            umidade = st.number_input("Umidade (%)",
                                      0.0, 100.0, 58.0, step=1.0, key="iot_umi")
            temp    = st.number_input("Temp. Motor (C)",
                                      40.0, 140.0, 85.0, step=1.0, key="iot_temp")

        with c2:
            mult = 1.4 if contexto == "Area Critica" else 1.0
            s = round(min(
                abs(inc_z)/45*50 + umidade/100*30 + max(0, temp-90)/50*20, 100
            ) * mult, 1)
            status_str = (
                "ALERTA CRITICO" if s >= 75
                else "ATENCAO" if s >= 40
                else "OPERACAO SEGURA"
            )
            payload = (
                f"> SOMPO PREDICT v15 | ESP32\n"
                f"> Device : {device_id}\n"
                f"> Context: {contexto}\n"
                f"> -----------------------------\n"
                f"> [MPU] Eixo Z : {inc_z:+.1f}\n"
                f"> [DHT] Umidade: {umidade:.1f}%\n"
                f"> [NTC] Temp   : {temp:.0f}C\n"
                f"> -----------------------------\n"
                f"> [EDGE AI] Score: {s}/100\n"
                f"> [STATUS]  {status_str}"
            )
            st.code(payload, language="text")

            if st.button("Enviar Telemetria para Cloud",
                         use_container_width=True, key="iot_send"):
                with st.spinner("Transmitindo via MQTT/TLS 1.3..."):
                    time.sleep(0.6)
                entrada = {
                    "timestamp":  datetime.now().strftime("%H:%M:%S"),
                    "device_id":  device_id, "contexto": contexto,
                    "inc_z":      inc_z, "umidade": umidade, "temp": temp,
                    "score_edge": s,
                    "status":     "CRITICO" if s >= 75 else "ATENCAO" if s >= 40 else "NORMAL",
                }
                st.session_state.telemetria_historico.append(entrada)
                gerar_trilha_auditoria("TELEMETRIA_ENVIADA",
                    f"device={device_id} ctx={contexto} score={s}")
                st.success("Payload enviado - log registrado.")

    with tab2:
        if not st.session_state.telemetria_historico:
            st.info("Nenhuma leitura enviada ainda.")
        else:
            st.dataframe(
                pd.DataFrame(st.session_state.telemetria_historico),
                use_container_width=True,
            )


def pagina_xai():
    if not check_permissao("view_dashboard"):
        return
    _contrato_box("pagina_xai", ["ACESSO_XAI", "CONSULTA_SHAP", "CONSULTA_ROI"])
    _header("XAI & Gestao Agil", "Rafael", "SHAP · ROI · Sprint Status")
    gerar_trilha_auditoria("ACESSO_XAI", "pagina=xai")

    tab1, tab2, tab3 = st.tabs(["SHAP", "ROI", "Sprint 1"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            score_b  = st.slider("Score base",   0.0, 100.0, 78.0, step=0.5, key="xai_sb")
            sh_inc   = st.slider("Inclinacao Z", -30.0, 50.0, 28.5, step=0.5, key="xai_si")
            sh_umi   = st.slider("Umidade",      -20.0, 30.0, 18.2, step=0.5, key="xai_su")
            sh_temp  = st.slider("Temperatura",  -15.0, 25.0, 12.4, step=0.5, key="xai_st")
            sh_idade = st.slider("Idade",        -10.0, 20.0,  8.9, step=0.5, key="xai_sa")

        with c2:
            cor_v = "#FF4D6A" if score_b >= 75 else "#F5A623" if score_b >= 40 else "#22D48A"
            st.markdown(f"""
            <div style="background:#131520;border:1px solid rgba(255,255,255,0.1);
                        border-radius:12px;padding:1.25rem;margin-bottom:1rem;text-align:center;">
                <div style="font-size:0.7rem;color:#8B8FA8;">SCORE EXPLICADO</div>
                <div style="font-size:2.5rem;font-weight:800;color:{cor_v};">{score_b:.1f}</div>
            </div>
            """, unsafe_allow_html=True)

            feats = [
                ("Base (E[f(x)])",  score_b - sh_inc - sh_umi - sh_temp - sh_idade, "#5B7FFF"),
                ("Inclinacao Z",    sh_inc,   "#FF4D6A" if sh_inc > 0    else "#22D48A"),
                ("Umidade",         sh_umi,   "#FF4D6A" if sh_umi > 0    else "#22D48A"),
                ("Temperatura",     sh_temp,  "#FF4D6A" if sh_temp > 0   else "#22D48A"),
                ("Idade",           sh_idade, "#F5A623" if sh_idade > 0  else "#22D48A"),
            ]
            for label, val, cor in feats:
                dir_ = "+" if val > 0 else "-"
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;padding:8px 12px;
                            background:#07080C;border-radius:8px;margin-bottom:4px;">
                    <span style="font-size:0.82rem;color:#EEF0F8;">{label}</span>
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
        us_data = [
            ("US01", "Identificacao de Risco",  "Charles",   "Em andamento", 70),
            ("US02", "Governanca / Auditoria",  "Rafael",    "Em andamento", 60),
            ("US03", "Painel Cliente",           "Charles",   "Planejado",    30),
            ("US04", "Operador de Equipamento", "Anthony",   "Em andamento", 55),
            ("US05", "Gestor de Frota",         "Gustavo",   "Planejado",    25),
            ("US06", "Tecnico / Anomalias",     "Guilherme", "Em andamento", 50),
            ("US07", "Subscricao XAI",          "Rafael",    "Em andamento", 65),
            ("US08", "Analista de Sinistros",   "Guilherme", "Planejado",    20),
        ]
        for us_id, titulo, dono, status, pct in us_data:
            cor_d = MEMBER_COLORS.get(dono, "#5B7FFF")
            cor_s = "#22D48A" if "Concluido" in status else "#F5A623" if "andamento" in status else "#5B7FFF"
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid rgba(255,255,255,0.07);
                        border-radius:10px;padding:14px 18px;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
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


def pagina_seguranca():
    if not check_permissao("all") and not check_permissao("view_dashboard"):
        return
    _contrato_box("pagina_seguranca",
                  ["ACESSO_SEGURANCA", "STRESS_TEST", "BLOQUEIO_IA_STRESS"])
    _header("Seguranca & Auth", "Charles", "RBAC · JWT · AES-256 · SHA-256 · Argon2id")
    gerar_trilha_auditoria("ACESSO_SEGURANCA", "pagina=seguranca")

    tab1, tab2, tab3 = st.tabs(["Stack de Seguranca", "RBAC", "Stress Test"])

    with tab1:
        protos = [
            ("TLS 1.3",   "Em Transito", "End-to-end ESP32 -> AWS, Perfect Forward Secrecy.",  "#29B6F6"),
            ("AES-256",   "Em Repouso",  "Fernet (AES-128-CBC + HMAC-SHA256) por registro.",   "#00E676"),
            ("SHA-256",   "Integridade", "Hash Chaining - cada log referencia o anterior.",     "#FFA000"),
            ("JWT HS256", "Auth",        "Tokens 2h, RBAC via claim role.",                     "#AB47BC"),
            ("Argon2id",  "Senhas",      "time_cost=2, memory_cost=64MiB (OWASP 2024).",       "#22D48A"),
        ]
        for icon_label, cat, desc, cor in protos:
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid {cor}33;border-left:3px solid {cor};
                        border-radius:10px;padding:14px 18px;margin-bottom:8px;">
                <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px;">
                    <span style="font-weight:700;font-size:0.9rem;color:{cor};">{icon_label}</span>
                    <span style="font-size:0.65rem;color:#4A4D62;text-transform:uppercase;">{cat}</span>
                </div>
                <div style="font-size:0.82rem;color:#8B8FA8;">{desc}</div>
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
            cor_r = MEMBER_COLORS.get(u, "#8B8FA8")
            st.markdown(f"""
            <div style="background:#131520;border:1px solid rgba(255,255,255,0.07);
                        border-radius:8px;padding:10px 16px;margin-bottom:6px;
                        display:flex;justify-content:space-between;">
                <span style="font-weight:600;color:#EEF0F8;">{u}</span>
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
    _header("Metricas do Modelo", "Gustavo",
            "Decision Tree · Recall · F1-Score · ROC-AUC · Matriz de Confusao")
    gerar_trilha_auditoria("ACESSO_METRICAS", "pagina=metricas")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ROC-AUC",            METRICAS_IA["roc_auc"])
    c2.metric("F1-Score (Fraude)",  METRICAS_IA["f1_fraude"])
    c3.metric("Recall (Fraude)",    METRICAS_IA["recall_fraude"])
    c4.metric("Precision (Fraude)", METRICAS_IA["precision_fraude"])
    c5.metric("Acuracia Geral",     METRICAS_IA["acuracia"])

    st.markdown("""
    <div style="background:rgba(255,77,106,0.06);border:1px solid rgba(255,77,106,0.2);
                border-radius:10px;padding:12px 18px;margin:1rem 0;
                font-size:0.84rem;color:#8B8FA8;">
        <strong style="color:#EEF0F8;">Por que Recall e a metrica mais critica?</strong><br>
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
                plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
                font=dict(color="#EEF0F8"),
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
                line=dict(dash="dash", color="#4A4D62"),
            ))
            fig_roc.add_trace(go.Scatter(
                x=fpr, y=tpr, mode="lines",
                name=f"Decision Tree (AUC = {auc_val})",
                line=dict(color="#5B7FFF", width=2.5),
                fill="tozeroy", fillcolor="rgba(91,127,255,0.08)",
            ))
            fig_roc.update_layout(
                title=f"Curva ROC - AUC: {auc_val}",
                xaxis_title="Taxa de Falso Positivo (FPR)",
                yaxis_title="Recall / TPR",
                template="plotly_dark",
                plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
                font=dict(color="#EEF0F8"),
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
             METRICAS_IA["f1_normal"],   "#22D48A"),
            ("1 - Fraude/Anomalia",
             METRICAS_IA["precision_fraude"], METRICAS_IA["recall_fraude"],
             METRICAS_IA["f1_fraude"],   "#FF4D6A"),
        ]:
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid {cor}33;border-left:3px solid {cor};
                        border-radius:12px;padding:1rem 1.25rem;margin-bottom:12px;">
                <div style="font-weight:700;font-size:0.9rem;color:{cor};margin-bottom:10px;">
                    Classe {label}</div>
                <div style="display:flex;gap:24px;flex-wrap:wrap;">
                    <div style="text-align:center;">
                        <div style="font-size:1.4rem;font-weight:800;color:#EEF0F8;">{prec}</div>
                        <div style="font-size:0.65rem;color:#8B8FA8;text-transform:uppercase;">Precision</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.4rem;font-weight:800;color:#EEF0F8;">{rec}</div>
                        <div style="font-size:0.65rem;color:#8B8FA8;text-transform:uppercase;">Recall</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.4rem;font-weight:800;color:#EEF0F8;">{f1}</div>
                        <div style="font-size:0.65rem;color:#8B8FA8;text-transform:uppercase;">F1-Score</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)


def pagina_auditoria():
    _contrato_box("pagina_auditoria", ["ACESSO_AUDITORIA", "EXPORTACAO_AUDITORIA"])
    _header("Trilha de Auditoria", "Charles",
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
            "LOGIN_SUCESSO": "#22D48A", "LOGIN_FALHA":   "#FF4D6A",
            "LOGOUT":        "#8B8FA8", "BLOQUEIO_IA":   "#FF4D6A",
            "VIOLACAO_RBAC": "#F5A623", "STRESS_TEST":   "#F5A623",
        }.get(log["acao"], "#5B7FFF")
        st.markdown(f"""
        <div style="background:#0D0F18;border:1px solid rgba(255,255,255,0.07);
                    border-left:3px solid {tipo_cor};border-radius:8px;
                    padding:10px 16px;margin-bottom:6px;
                    font-family:monospace;font-size:0.76rem;color:#8B8FA8;">
            <span style="color:{tipo_cor};font-weight:700;">[{log['acao']}]</span>
            <span style="color:#4A4D62;">{log['timestamp']}</span>
            <span style="color:#EEF0F8;">@{log['usuario']}</span>
            <span style="color:#4A4D62;">- {log.get('detalhes','') or '-'}</span><br>
            <span style="color:#252840;">HASH: {log['hash']} | ENC: {log['enc_preview']}</span>
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
        "cloud":          pagina_cloud,
        "iot":            pagina_iot,
        "xai":            pagina_xai,
        "seguranca":      pagina_seguranca,
        "metricas":       pagina_metricas,
        "auditoria":      pagina_auditoria,
        "demo":           pagina_demo_e_sobre.render_modo_demo,
        "sobre":          pagina_demo_e_sobre.render_sobre,
    }

    fn = rota.get(pagina_id)
    if fn:
        fn()
    else:
        st.info(f"Pagina '{pagina_id}' em desenvolvimento.")


if __name__ == "__main__":
    main()
