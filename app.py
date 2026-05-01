# ==========================================
# SOMPO PREDICT v15 — SECURE GATEWAY
# Streamlit App — Menu Integrado e Estruturado
#
# Instalação:
#   pip install streamlit PyJWT cryptography scikit-learn numpy argon2-cffi pandas plotly
#
# Execução:
#   streamlit run app.py
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
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

# ── Plotly é opcional — usamos só se disponível ───────────────────────
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# ==========================================
# 0. CONFIGURAÇÃO DA PÁGINA
# ==========================================

st.set_page_config(
    page_title="Sompo Predict v15",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS global — dark theme alinhado ao battle-plan
st.markdown("""
<style>
/* ── Reset e variáveis ── */
:root {
    --bg: #07080C;
    --surface: #0D0F18;
    --surface2: #131520;
    --border: rgba(255,255,255,0.07);
    --accent: #5B7FFF;
    --green: #22D48A;
    --amber: #F5A623;
    --red: #FF4D6A;
    --purple: #A855F7;
    --text: #EEF0F8;
    --text2: #8B8FA8;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0D0F18 !important;
    border-right: 1px solid rgba(255,255,255,0.07) !important;
}
section[data-testid="stSidebar"] .block-container { padding: 1.5rem 1rem; }

/* Botões sidebar */
.stRadio > label { color: #8B8FA8 !important; font-size: 0.8rem; letter-spacing: 0.06em; }
div[data-testid="stRadio"] label { color: #EEF0F8 !important; }

/* Cards de métricas */
div[data-testid="metric-container"] {
    background: #131520;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 1rem 1.25rem;
}

/* Expander */
details { border: 1px solid rgba(255,255,255,0.07) !important; border-radius: 10px; }

/* Inputs e selects */
input, select, textarea {
    background: #131520 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: #EEF0F8 !important;
    border-radius: 8px !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #07080C; }
::-webkit-scrollbar-thumb { background: #252840; border-radius: 2px; }

/* Tabelas */
.stDataFrame { border: 1px solid rgba(255,255,255,0.07) !important; border-radius: 10px; }

/* Status badge helper */
.badge-ok   { background: rgba(34,212,138,0.12); color: #22D48A; border: 1px solid rgba(34,212,138,0.3);
              padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; }
.badge-warn { background: rgba(245,166,35,0.12);  color: #F5A623; border: 1px solid rgba(245,166,35,0.3);
              padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; }
.badge-crit { background: rgba(255,77,106,0.12);  color: #FF4D6A; border: 1px solid rgba(255,77,106,0.3);
              padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 1. ESTADO DA SESSÃO — inicialização única
# ==========================================

def _init_session():
    if "init" in st.session_state:
        return

    st.session_state.init = True

    # ─ Fernet (AES-128-CBC + HMAC-SHA256) ─
    _kms_raw = os.getenv("SOMPO_KMS_KEY", "")
    st.session_state.kms_key = _kms_raw.encode() if _kms_raw else Fernet.generate_key()
    st.session_state.cipher_suite = Fernet(st.session_state.kms_key)

    # ─ JWT secret ─
    st.session_state.jwt_secret = os.getenv("SOMPO_JWT_SECRET", secrets.token_hex(32))

    # ─ Hash chaining ─
    st.session_state.ultimo_hash = "GENESIS_BLOCK_000"

    # ─ Rate limiting ─
    st.session_state.tentativas_falhas = 0
    st.session_state.bloqueio_tempo = 0.0

    # ─ Sessão autenticada ─
    st.session_state.jwt_token      = None
    st.session_state.usuario_logado = None
    st.session_state.role_logado    = None

    # ─ Logs de auditoria ─
    st.session_state.logs_auditoria = []

    # ─ Argon2id (OWASP 2024) ─
    st.session_state.ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1)

    # ─ Mock de usuários ─
    _ph = st.session_state.ph
    st.session_state.mock_users = {
        "admin": {"senha_hash": _ph.hash("Admin@2024!"), "role": "Admin"},
    }

    # ─ Dados de telemetria simulada (para dashboard) ─
    st.session_state.telemetria_historico = []


_init_session()

# ==========================================
# 2. CONSTANTES
# ==========================================

RBAC_MATRIX: dict[str, list[str]] = {
    "Admin":     ["all"],
    "Cientista": ["view_dashboard", "train_models", "extract_data", "view_dados"],
    "Operador":  ["view_dashboard", "input_telemetry", "view_iot"],
}

MENU_ITEMS = {
    "🏠  Início":                 "inicio",
    "📊  Dados & Estatística":    "dados",        # Guilherme
    "☁️  Cloud & IA":             "cloud",        # Gustavo
    "📡  IoT & Telemetria":       "iot",          # Anthony
    "🎯  XAI & Gestão":           "xai",          # Rafael
    "🔐  Segurança & Auth":       "seguranca",    # Charles
    "⛓️  Trilha de Auditoria":    "auditoria",
}

MEMBER_COLORS = {
    "Guilherme": "#F5A623",
    "Gustavo":   "#FF4D6A",
    "Anthony":   "#A855F7",
    "Rafael":    "#5B7FFF",
    "Charles":   "#22D48A",
}


# ==========================================
# 3. MOTOR DE RISCO IA (cache)
# ==========================================

@st.cache_resource
def treinar_motor_risco() -> dict:
    """Decision Tree para detecção de anomalias no login. Treinado uma única vez."""
    X, y = make_classification(
        n_samples=2000, n_features=4, n_informative=3,
        n_redundant=1, weights=[0.85, 0.15], random_state=42,
    )
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    clf = DecisionTreeClassifier(max_depth=5, class_weight="balanced", random_state=42)
    clf.fit(X_train, y_train)
    y_pred  = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]
    relatorio = classification_report(y_test, y_pred, output_dict=True)
    return {
        "modelo": clf,
        "metricas": {
            "roc_auc":          round(roc_auc_score(y_test, y_proba), 4),
            "precision_fraude": round(relatorio["1"]["precision"], 4),
            "recall_fraude":    round(relatorio["1"]["recall"],    4),
            "f1_fraude":        round(relatorio["1"]["f1-score"],  4),
            "acuracia":         round(relatorio["accuracy"],       4),
        },
    }


_cache_risco   = treinar_motor_risco()
MOTOR_RISCO_IA = _cache_risco["modelo"]
METRICAS_IA    = _cache_risco["metricas"]


def avaliar_risco_login(falhas: int, hora: int, ip_score: float, latencia: float) -> bool:
    feat = np.array([[falhas, hora, ip_score, latencia]])
    prob = MOTOR_RISCO_IA.predict_proba(feat)[0][1]
    return prob > 0.60


# ==========================================
# 4. TRILHA DE AUDITORIA
# ==========================================

def gerar_trilha_auditoria(acao: str, detalhes: str = "") -> None:
    usuario = st.session_state.get("usuario_logado") or "SISTEMA"
    registro = {
        "acao": acao, "detalhes": detalhes,
        "prev_hash": st.session_state.ultimo_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "usuario": usuario,
    }
    canonico  = json.dumps(registro, sort_keys=True, separators=(",", ":"))
    hash_novo = hashlib.sha256(canonico.encode()).hexdigest()
    registro["hash_atual"] = hash_novo
    st.session_state.ultimo_hash = hash_novo
    cifrado = st.session_state.cipher_suite.encrypt(json.dumps(registro).encode()).decode()
    entrada = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "usuario":   usuario,
        "acao":      acao,
        "hash":      hash_novo[:16] + "...",
        "enc_preview": cifrado[:36] + "...",
    }
    st.session_state.logs_auditoria.append(entrada)


# ==========================================
# 5. RBAC / JWT
# ==========================================

def check_permissao(acao: str) -> bool:
    token = st.session_state.jwt_token
    if not token:
        st.error("⛔ Acesso negado — faça login primeiro.")
        return False
    try:
        payload = jwt.decode(token, st.session_state.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        gerar_trilha_auditoria("TOKEN_EXPIRADO")
        st.error("⏱️ Sessão expirada. Faça login novamente.")
        st.session_state.jwt_token = None
        st.rerun()
        return False
    except jwt.InvalidTokenError:
        gerar_trilha_auditoria("TOKEN_INVALIDO")
        st.error("🚨 Token inválido.")
        return False
    role = payload.get("role", "")
    perms = RBAC_MATRIX.get(role, [])
    if "all" in perms or acao in perms:
        return True
    gerar_trilha_auditoria("VIOLACAO_RBAC", f"Role '{role}' tentou '{acao}'")
    st.warning(f"⛔ Perfil **{role}** não tem acesso a esta funcionalidade.")
    return False


def _verificar_senha(hash_armazenado: str, senha: str) -> bool:
    try:
        return st.session_state.ph.verify(hash_armazenado, senha)
    except (VerifyMismatchError, Exception):
        return False


# ==========================================
# 6. HELPERS VISUAIS
# ==========================================

def _header(titulo: str, membro: str, subtitulo: str = ""):
    cor = MEMBER_COLORS.get(membro, "#5B7FFF")
    st.markdown(f"""
    <div style="border-left: 3px solid {cor}; padding: 6px 0 6px 16px; margin-bottom: 1.5rem;">
        <div style="font-size:0.7rem; color:#8B8FA8; text-transform:uppercase;
                    letter-spacing:0.1em; margin-bottom:4px;">
            Módulo de {membro}
        </div>
        <div style="font-size:1.5rem; font-weight:700; color:#EEF0F8;">{titulo}</div>
        {"<div style='font-size:0.9rem;color:#8B8FA8;margin-top:4px;'>"+subtitulo+"</div>" if subtitulo else ""}
    </div>
    """, unsafe_allow_html=True)


def _score_badge(score: float) -> str:
    if score < 40:
        return f'<span class="badge-ok">🟢 BAIXO ({score:.1f})</span>'
    elif score < 75:
        return f'<span class="badge-warn">🟡 MÉDIO ({score:.1f})</span>'
    else:
        return f'<span class="badge-crit">🔴 CRÍTICO ({score:.1f})</span>'


def _dataset_susep_mock() -> pd.DataFrame:
    """Extrato simulado de dados SUSEP para demo."""
    np.random.seed(42)
    n = 120
    regioes  = ["Sul", "Centro-Oeste", "Sudeste", "Norte", "Nordeste"]
    tipos    = ["Colheitadeira", "Trator", "Pulverizador", "Plantadeira"]
    sinistros = np.random.choice([0,1,2,3], n, p=[0.55,0.25,0.12,0.08])
    return pd.DataFrame({
        "ID_Apolice":      [f"AP-{1000+i}" for i in range(n)],
        "Equipamento":     np.random.choice(tipos, n),
        "Regiao":          np.random.choice(regioes, n),
        "Idade_Anos":      np.random.randint(1, 20, n),
        "Valor_BRL":       np.random.randint(200_000, 2_000_000, n),
        "Sinistros_Ano":   sinistros,
        "Temp_Max_C":      np.round(np.random.uniform(22, 42, n), 1),
        "Umidade_Pct":     np.round(np.random.uniform(30, 95, n), 1),
        "Score_Risco":     np.round(np.clip(
            sinistros * 25 + np.random.uniform(5, 30, n), 0, 100
        ), 1),
    })


# ==========================================
# 7. TELA DE LOGIN / REGISTRO
# ==========================================

def tela_login():
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown("""
        <div style="text-align:center; padding: 2rem 0 1.5rem;">
            <div style="font-size:2.5rem; margin-bottom:0.5rem;">🌾</div>
            <div style="font-size:1.8rem; font-weight:800; color:#EEF0F8;">Sompo Predict</div>
            <div style="font-size:0.85rem; color:#8B8FA8; margin-top:4px;">
                Secure Gateway · Squad T1 · FIAP 2025
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Rate limiting
        if st.session_state.tentativas_falhas >= 3:
            restante = st.session_state.bloqueio_tempo - time.time()
            if restante > 0:
                st.error(f"⛔ Bloqueio temporário: aguarde {int(restante)}s.")
                return
            else:
                st.session_state.tentativas_falhas = 0

        tab_login, tab_reg = st.tabs(["  🔑  Entrar  ", "  ➕  Registrar  "])

        # ── Login ──
        with tab_login:
            with st.form("form_login", clear_on_submit=False):
                usuario = st.text_input("Usuário", placeholder="ex: admin")
                senha   = st.text_input("Senha",   placeholder="••••••••", type="password")
                st.caption("Conta padrão: `admin` / `Admin@2024!`")
                submit  = st.form_submit_button("Entrar →", use_container_width=True)

            if submit:
                if not re.match(r"^[a-zA-Z0-9_]{3,20}$", usuario):
                    st.warning("🛡️ WAF: formato de usuário inválido bloqueado.")
                    st.session_state.tentativas_falhas += 1
                    return

                ip_score = 0.8 if st.session_state.tentativas_falhas > 0 else -0.5
                if avaliar_risco_login(st.session_state.tentativas_falhas, datetime.now().hour, ip_score, 45.0):
                    st.session_state.tentativas_falhas += 3
                    st.session_state.bloqueio_tempo = time.time() + 30
                    gerar_trilha_auditoria("BLOQUEIO_IA", f"Anomalia detectada para '{usuario}'")
                    st.error("🚨 Motor de IA bloqueou acesso anômalo.")
                    st.rerun()
                    return

                db_entry = st.session_state.mock_users.get(usuario)
                hash_alvo = db_entry["senha_hash"] if db_entry else st.session_state.ph.hash("dummy")
                senha_ok  = _verificar_senha(hash_alvo, senha) if db_entry else False

                if not senha_ok:
                    st.session_state.tentativas_falhas += 1
                    gerar_trilha_auditoria("LOGIN_FALHA", f"Tentativa para '{usuario}'")
                    st.error("Credenciais inválidas.")
                    return

                st.session_state.tentativas_falhas  = 0
                st.session_state.usuario_logado     = usuario
                st.session_state.role_logado        = db_entry["role"]
                payload_jwt = {
                    "sub":  usuario,
                    "role": db_entry["role"],
                    "iat":  datetime.now(timezone.utc),
                    "exp":  datetime.now(timezone.utc) + timedelta(hours=2),
                }
                st.session_state.jwt_token = jwt.encode(
                    payload_jwt, st.session_state.jwt_secret, algorithm="HS256"
                )
                gerar_trilha_auditoria("LOGIN_SUCESSO", f"Role: {db_entry['role']}")
                st.rerun()

        # ── Registro ──
        with tab_reg:
            with st.form("form_reg", clear_on_submit=True):
                n_user = st.text_input("Novo Usuário")
                n_pwd  = st.text_input("Nova Senha", type="password")
                n_role = st.selectbox("Perfil de Acesso", ["Operador", "Cientista", "Admin"])
                reg_ok = st.form_submit_button("Registrar →", use_container_width=True)

            if reg_ok:
                if not re.match(r"^[a-zA-Z0-9_]{3,20}$", n_user):
                    st.error("Nome de usuário inválido (3-20 chars, sem espaços).")
                elif n_user in st.session_state.mock_users:
                    st.error("Usuário já existe.")
                elif len(n_pwd) < 8:
                    st.error("Senha deve ter ≥ 8 caracteres.")
                else:
                    st.session_state.mock_users[n_user] = {
                        "senha_hash": st.session_state.ph.hash(n_pwd),
                        "role": n_role,
                    }
                    gerar_trilha_auditoria("NOVO_USUARIO", f"'{n_user}' criado com role '{n_role}'")
                    st.success(f"✅ Usuário `{n_user}` criado! Faça login ao lado.")


# ==========================================
# 8. SIDEBAR + MENU PRINCIPAL
# ==========================================

def sidebar():
    with st.sidebar:
        # Avatar e info do usuário
        cor = MEMBER_COLORS.get(st.session_state.usuario_logado, "#5B7FFF")
        initials = st.session_state.usuario_logado[:2].upper()
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;padding:0.5rem 0 1.5rem;">
            <div style="width:40px;height:40px;border-radius:10px;
                        background:{cor}22;border:1.5px solid {cor};
                        display:flex;align-items:center;justify-content:center;
                        font-weight:700;font-size:1rem;color:{cor};">{initials}</div>
            <div>
                <div style="font-weight:600;color:#EEF0F8;font-size:0.9rem;">
                    {st.session_state.usuario_logado}
                </div>
                <div style="font-size:0.7rem;color:#8B8FA8;">
                    {st.session_state.role_logado}
                </div>
            </div>
        </div>
        <div style="height:1px;background:rgba(255,255,255,0.07);margin-bottom:1rem;"></div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='font-size:0.65rem;color:#4A4D62;text-transform:uppercase;"
                    "letter-spacing:0.1em;margin-bottom:8px;'>Navegação</div>",
                    unsafe_allow_html=True)

        pagina = st.radio(
            label="menu",
            options=list(MENU_ITEMS.keys()),
            label_visibility="collapsed",
        )

        st.markdown("<div style='height:1px;background:rgba(255,255,255,0.07);"
                    "margin:1.5rem 0 1rem;'></div>", unsafe_allow_html=True)

        # Status do sistema
        n_logs = len(st.session_state.logs_auditoria)
        st.markdown(f"""
        <div style="font-size:0.72rem;color:#8B8FA8;line-height:1.8;">
            <div>🔗 Hashes auditados: <strong style="color:#22D48A;">{n_logs}</strong></div>
            <div>👥 Usuários: <strong style="color:#EEF0F8;">
                {len(st.session_state.mock_users)}</strong></div>
            <div>📡 Telemetria: <strong style="color:#EEF0F8;">
                {len(st.session_state.telemetria_historico)}</strong> leituras</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        if st.button("🚪 Encerrar Sessão", use_container_width=True):
            gerar_trilha_auditoria("LOGOUT", "Logout manual do usuário.")
            for k in ["jwt_token", "usuario_logado", "role_logado"]:
                st.session_state[k] = None
            st.rerun()

    return MENU_ITEMS[pagina]


# ==========================================
# 9. PÁGINAS DO MENU
# ==========================================

# ── 9.1 INÍCIO ──────────────────────────────────────────────────────────

def pagina_inicio():
    st.markdown("""
    <div style="padding:2rem 0 1rem;">
        <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                    letter-spacing:0.12em;margin-bottom:8px;">Sprint 1 · Sompo Challenge 2025</div>
        <h1 style="font-size:2.8rem;font-weight:800;color:#EEF0F8;
                   letter-spacing:-0.02em;line-height:1.05;margin:0;">
            Sompo Predict
            <span style="color:#5B7FFF;">v15</span>
        </h1>
        <p style="color:#8B8FA8;margin-top:0.75rem;font-size:1rem;max-width:600px;">
            Ecossistema de prevenção de riscos para equipamentos agrícolas.
            Score preditivo, explicável e auditável — da telemetria no campo até o dashboard da seguradora.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # KPIs
    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        ("8", "User Stories",   "#5B7FFF"),
        ("5", "Membros",        "#22D48A"),
        ("8", "Matérias",       "#F5A623"),
        ("06/05", "Pitch",      "#FF4D6A"),
        ("10/05", "Deadline",   "#A855F7"),
    ]
    for col, (val, lab, cor) in zip([c1,c2,c3,c4,c5], kpis):
        col.markdown(f"""
        <div style="background:#0D0F18;border:1px solid rgba(255,255,255,0.07);
                    border-radius:12px;padding:1rem 1.25rem;text-align:center;">
            <div style="font-size:1.6rem;font-weight:800;color:{cor};line-height:1;">{val}</div>
            <div style="font-size:0.65rem;color:#4A4D62;text-transform:uppercase;
                        letter-spacing:0.08em;margin-top:6px;">{lab}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Pipeline de arquitetura
    st.markdown("#### Arquitetura da Solução")
    steps = [
        ("📡", "IoT / Edge",      "ESP32 + MPU-6050\nDHT22 + GPS",      "Anthony",   "#A855F7"),
        ("📊", "Dados",           "SUSEP + INMET\nEDA + Anomalias",      "Guilherme", "#F5A623"),
        ("☁️", "Cloud & IA",     "AWS EC2 + Flask\nXGBoost + LSTM",     "Gustavo",   "#FF4D6A"),
        ("🎯", "XAI Dashboard",   "SHAP Values\nScore Explicável",       "Rafael",    "#5B7FFF"),
        ("🔐", "Seg. & Auditoria","SHA-256 + RBAC\nAES-256 + JWT",      "Charles",   "#22D48A"),
    ]
    cols = st.columns(5)
    for col, (icon, titulo, desc, membro, cor) in zip(cols, steps):
        col.markdown(f"""
        <div style="background:#0D0F18;border:1px solid {cor}33;
                    border-radius:12px;padding:1rem;text-align:center;
                    border-top:2px solid {cor};">
            <div style="font-size:1.6rem;margin-bottom:6px;">{icon}</div>
            <div style="font-weight:700;font-size:0.85rem;color:#EEF0F8;">{titulo}</div>
            <div style="font-size:0.7rem;color:#8B8FA8;margin:6px 0;line-height:1.5;
                        white-space:pre-line;">{desc}</div>
            <div style="font-size:0.65rem;color:{cor};text-transform:uppercase;
                        letter-spacing:0.08em;">{membro}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Squad T1
    st.markdown("#### Squad T1")
    membros = [
        ("R", "Rafael",    "Scrum Master · XAI · Pitch",   "#5B7FFF"),
        ("C", "Charles",   "Backend · ML · Segurança",     "#22D48A"),
        ("A", "Anthony",   "IoT · ESP32 · Edge Computing", "#A855F7"),
        ("G", "Guilherme", "Data Science · Estatística",   "#F5A623"),
        ("G", "Gustavo",   "Cloud AWS · Flask · LSTM",     "#FF4D6A"),
    ]
    cols = st.columns(5)
    for col, (init, nome, papel, cor) in zip(cols, membros):
        col.markdown(f"""
        <div style="background:#0D0F18;border:1px solid rgba(255,255,255,0.07);
                    border-radius:12px;padding:1rem;text-align:center;">
            <div style="width:44px;height:44px;border-radius:12px;
                        background:{cor}22;border:1.5px solid {cor};
                        display:flex;align-items:center;justify-content:center;
                        font-weight:800;font-size:1.1rem;color:{cor};
                        margin:0 auto 10px;">{init}</div>
            <div style="font-weight:700;font-size:0.9rem;color:#EEF0F8;">{nome}</div>
            <div style="font-size:0.68rem;color:#8B8FA8;margin-top:4px;line-height:1.4;">{papel}</div>
        </div>
        """, unsafe_allow_html=True)


# ── 9.2 DADOS & ESTATÍSTICA (Guilherme) ─────────────────────────────────

def pagina_dados():
    if not check_permissao("view_dados") and not check_permissao("view_dashboard"):
        return
    _header("Dados & Estatística", "Guilherme", "Base SUSEP · Análise Exploratória · Anomalias")

    df = _dataset_susep_mock()

    tab1, tab2, tab3 = st.tabs(["📋 Dataset", "📈 Visualizações", "🔍 Anomalias Z-Score"])

    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Apólices", len(df))
        col2.metric("Sinistros médios/apólice", round(df["Sinistros_Ano"].mean(), 2))
        col3.metric("Valor médio (R$)", f"{df['Valor_BRL'].mean()/1e6:.2f}M")
        col4.metric("Score médio de risco", round(df["Score_Risco"].mean(), 1))

        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(df.head(30), use_container_width=True)
        st.caption("Extrato simulado baseado na estrutura da base SUSEP rural.")

    with tab2:
        if PLOTLY_OK:
            col_a, col_b = st.columns(2)
            with col_a:
                fig1 = px.histogram(
                    df, x="Score_Risco", nbins=20, color="Equipamento",
                    title="Distribuição de Score por Tipo de Equipamento",
                    template="plotly_dark",
                )
                fig1.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18")
                st.plotly_chart(fig1, use_container_width=True)
            with col_b:
                media_reg = df.groupby("Regiao")["Score_Risco"].mean().reset_index()
                fig2 = px.bar(
                    media_reg, x="Regiao", y="Score_Risco",
                    title="Score Médio por Região",
                    color="Score_Risco", color_continuous_scale="RdYlGn_r",
                    template="plotly_dark",
                )
                fig2.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18")
                st.plotly_chart(fig2, use_container_width=True)

            fig3 = px.scatter(
                df, x="Umidade_Pct", y="Score_Risco",
                color="Equipamento", size="Sinistros_Ano",
                title="Umidade vs Score de Risco (tamanho = nº de sinistros)",
                template="plotly_dark",
            )
            fig3.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18")
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Instale `plotly` para ver os gráficos: `pip install plotly`")
            st.bar_chart(df.groupby("Regiao")["Score_Risco"].mean())

    with tab3:
        st.markdown("**Z-Score aplicado na coluna `Score_Risco` — outliers (|Z| > 2) marcados como anomalias.**")
        df_z = df.copy()
        mu, sigma = df_z["Score_Risco"].mean(), df_z["Score_Risco"].std()
        df_z["Z_Score"]  = ((df_z["Score_Risco"] - mu) / sigma).round(3)
        df_z["Anomalia"] = df_z["Z_Score"].abs() > 2

        anomalias = df_z[df_z["Anomalia"]]
        st.info(f"🔍 {len(anomalias)} anomalias detectadas em {len(df_z)} registros "
                f"({100*len(anomalias)/len(df_z):.1f}%)")
        st.dataframe(
            anomalias[["ID_Apolice", "Equipamento", "Regiao", "Score_Risco", "Z_Score"]],
            use_container_width=True,
        )

    gerar_trilha_auditoria("ACESSO_DADOS", "Módulo Guilherme — EDA executada")


# ── 9.3 CLOUD & IA (Gustavo) ────────────────────────────────────────────

def pagina_cloud():
    if not check_permissao("train_models") and not check_permissao("view_dashboard"):
        return
    _header("Cloud & IA", "Gustavo", "AWS EC2 · Flask API · XGBoost · LSTM")

    tab1, tab2, tab3 = st.tabs(["☁️ Infraestrutura AWS", "🧠 Motor de IA", "🔌 API Simulator"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### Arquitetura AWS")
            recursos = [
                ("EC2 t2.micro",     "Instância Free Tier — backend Flask",     "🟢 Online"),
                ("Security Group",   "Portas 22 (SSH) e 5000 (Flask) abertas",  "🟢 Ativo"),
                ("S3 Data Lake",     "Parquet — telemetria e modelos (.pkl)",   "🟢 Conectado"),
                ("SageMaker",        "Endpoint XGBoost + LSTM em produção",      "🟡 Staging"),
                ("CloudWatch",       "Logs de auditoria e métricas",            "🟢 Monitorando"),
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
                    <div style="font-size:0.72rem;color:{cor_s};white-space:nowrap;
                                padding:3px 10px;background:{cor_s}15;border-radius:6px;">
                        {status}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with col2:
            st.markdown("##### Rotas Flask")
            rotas = [
                ("GET",  "/",              "Boas-vindas da API"),
                ("GET",  "/health",        '{"status":"ok","version":"15.0"}'),
                ("GET",  "/echo/<texto>",  "Echo com timestamp"),
                ("POST", "/score",         "Score de risco 0-100 (JSON)"),
                ("GET",  "/fleet",         "Ranking dos 10 equipamentos mais críticos"),
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

    with tab2:
        st.markdown("##### Métricas do Motor de IA (Decision Tree — Detecção de Anomalias)")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("ROC-AUC",   METRICAS_IA["roc_auc"])
        c2.metric("F1-Fraude", METRICAS_IA["f1_fraude"])
        c3.metric("Recall",    METRICAS_IA["recall_fraude"])
        c4.metric("Precision", METRICAS_IA["precision_fraude"])
        c5.metric("Acurácia",  METRICAS_IA["acuracia"])

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Simulador de Score XGBoost (mock)")
        col_sl1, col_sl2 = st.columns(2)
        with col_sl1:
            inclin  = st.slider("Inclinação Eixo Z (graus)", 0, 45, 10)
            umidade = st.slider("Umidade do Solo (%)", 20, 100, 55)
        with col_sl2:
            temp    = st.slider("Temperatura do Motor (°C)", 60, 130, 85)
            idade   = st.slider("Idade do Equipamento (anos)", 1, 25, 5)

        score_calc = round(
            min(inclin, 40)/40 * 40
            + min(umidade, 100)/100 * 20
            + max(0, temp - 90)/40  * 25
            + min(idade, 20)/20     * 15,
            1,
        )
        score_calc = min(score_calc, 100)

        st.markdown(f"""
        <div style="background:#131520;border:1px solid rgba(255,255,255,0.12);
                    border-radius:12px;padding:1.5rem;text-align:center;margin-top:1rem;">
            <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                        letter-spacing:0.1em;margin-bottom:8px;">Score de Risco Calculado</div>
            <div style="font-size:3rem;font-weight:800;
                        color:{'#FF4D6A' if score_calc>=75 else '#F5A623' if score_calc>=40 else '#22D48A'};">
                {score_calc}
            </div>
            <div style="font-size:0.85rem;color:#8B8FA8;margin-top:4px;">/ 100</div>
        </div>
        """, unsafe_allow_html=True)

    with tab3:
        st.markdown("##### Simulador de Chamada à API `/score`")
        exemplo_req = {
            "device_id": "COL-099",
            "features": {
                "inclinacao_z": inclin,
                "umidade_pct":  umidade,
                "temp_motor":   temp,
                "idade_anos":   idade,
            }
        }
        st.code(json.dumps(exemplo_req, indent=2, ensure_ascii=False), language="json")
        if st.button("⚡ Simular POST /score"):
            with st.spinner("Chamando API..."):
                time.sleep(0.6)
            resp = {
                "status": "ok",
                "device_id": "COL-099",
                "score": score_calc,
                "categoria": "CRÍTICO" if score_calc >= 75 else "ATENÇÃO" if score_calc >= 40 else "NORMAL",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            st.code(json.dumps(resp, indent=2, ensure_ascii=False), language="json")
            gerar_trilha_auditoria("API_SCORE_CALL", f"Score simulado: {score_calc}")
            st.success("✅ API respondeu em 142ms")

    gerar_trilha_auditoria("ACESSO_CLOUD", "Módulo Gustavo — Cloud & IA")


# ── 9.4 IoT & TELEMETRIA (Anthony) ──────────────────────────────────────

def pagina_iot():
    if not check_permissao("input_telemetry") and not check_permissao("view_dashboard"):
        return
    _header("IoT & Telemetria", "Anthony", "ESP32 · MPU-6050 · DHT22 · Edge Computing")

    tab1, tab2 = st.tabs(["📡 Leitura de Telemetria", "🗃️ Histórico de Leituras"])

    with tab1:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("##### Parâmetros do Sensor")
            device_id = st.selectbox("ID do Equipamento", ["TRAT-047", "COLH-012", "TRAT-099", "COLH-088"])
            contexto  = st.selectbox("Contexto Operacional", ["Campo", "Transporte em Estrada", "Área Crítica"])
            inc_x     = st.number_input("Inclinação Eixo X (°)", -45.0, 45.0, 5.0, step=0.5)
            inc_z     = st.number_input("Inclinação Eixo Z (°)", -45.0, 45.0, 12.0, step=0.5)
            umidade   = st.number_input("Umidade do Solo (%)", 0.0, 100.0, 58.0, step=1.0)
            temp      = st.number_input("Temperatura Motor (°C)", 40.0, 140.0, 85.0, step=1.0)

        with col2:
            st.markdown("##### Saída do ESP32 (Serial Monitor)")
            multiplicador = 1.4 if contexto == "Área Crítica" else 1.0
            score_edge = round(min(
                abs(inc_z)/45 * 50 + umidade/100 * 30 + max(0, temp-90)/50 * 20,
                100,
            ) * multiplicador, 1)
            score_edge = min(score_edge, 100)

            payload_serial = f"""> SOMPO PREDICT v15 · ESP32
> Device : {device_id}
> Context: {contexto}
> ─────────────────────────────
> [MPU-6050] Eixo X : {inc_x:+.1f}°
> [MPU-6050] Eixo Z : {inc_z:+.1f}°
> [DHT22]   Umidade : {umidade:.1f} %
> [NTC]     Temp    : {temp:.0f} °C
> ─────────────────────────────
> [EDGE AI] Score   : {score_edge} / 100
> [STATUS]  {'⚠️  ALERTA CRÍTICO — PARADA OBRIGATÓRIA' if score_edge >= 75 else '🟡 ATENÇÃO — reduzir velocidade' if score_edge >= 40 else '🟢 OPERAÇÃO SEGURA'}
"""
            st.code(payload_serial, language="text")

            if st.button("📤 Enviar Telemetria para Cloud", use_container_width=True):
                with st.spinner("Transmitindo via MQTT/TLS 1.3..."):
                    time.sleep(0.8)
                entrada = {
                    "timestamp":  datetime.now().strftime("%H:%M:%S"),
                    "device_id":  device_id,
                    "contexto":   contexto,
                    "inc_z":      inc_z,
                    "umidade":    umidade,
                    "temp":       temp,
                    "score_edge": score_edge,
                    "status":     "CRÍTICO" if score_edge >= 75 else "ATENÇÃO" if score_edge >= 40 else "NORMAL",
                }
                st.session_state.telemetria_historico.append(entrada)
                gerar_trilha_auditoria("TELEMETRIA_ENVIADA",
                    f"Device:{device_id} Score:{score_edge}")
                st.success("✅ Payload enviado — latência: 847ms")

    with tab2:
        if not st.session_state.telemetria_historico:
            st.info("Nenhuma leitura enviada ainda. Use a aba '📡 Leitura de Telemetria'.")
        else:
            df_hist = pd.DataFrame(st.session_state.telemetria_historico)
            st.dataframe(df_hist, use_container_width=True)
            if PLOTLY_OK and len(df_hist) > 1:
                fig = px.line(df_hist, x="timestamp", y="score_edge",
                              color="device_id", markers=True,
                              title="Score Edge ao longo do tempo",
                              template="plotly_dark")
                fig.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18")
                st.plotly_chart(fig, use_container_width=True)


# ── 9.5 XAI & GESTÃO (Rafael) ───────────────────────────────────────────

def pagina_xai():
    if not check_permissao("view_dashboard"):
        return
    _header("XAI & Gestão Ágil", "Rafael", "SHAP Values · ROI · Scrum Master · Pitch")

    tab1, tab2, tab3 = st.tabs(["🎯 Explicabilidade SHAP", "💰 Simulador de ROI", "📋 Sprint 1"])

    with tab1:
        st.markdown("##### Explicação SHAP do Score de Risco")
        st.info("SHAP (SHapley Additive exPlanations) — explica o peso de cada feature no score final.")

        col1, col2 = st.columns([1, 1])
        with col1:
            score_base  = st.slider("Score do Equipamento", 0.0, 100.0, 78.0, step=0.5)
            sh_inclin   = st.slider("Contribuição: Inclinação Z", -30.0, 50.0, 28.5, step=0.5)
            sh_umidade  = st.slider("Contribuição: Umidade",     -20.0, 30.0, 18.2, step=0.5)
            sh_temp     = st.slider("Contribuição: Temperatura", -15.0, 25.0, 12.4, step=0.5)
            sh_idade    = st.slider("Contribuição: Idade",       -10.0, 20.0,  8.9, step=0.5)

        with col2:
            st.markdown(f"""
            <div style="background:#131520;border:1px solid rgba(255,255,255,0.1);
                        border-radius:12px;padding:1.25rem;margin-bottom:1rem;">
                <div style="font-size:0.7rem;color:#8B8FA8;letter-spacing:0.08em;margin-bottom:4px;">
                    SCORE EXPLICADO</div>
                <div style="font-size:2.5rem;font-weight:800;
                    color:{'#FF4D6A' if score_base>=75 else '#F5A623' if score_base>=40 else '#22D48A'};">
                    {score_base:.1f}</div>
            </div>
            """, unsafe_allow_html=True)

            # Waterfall manual
            features = [
                ("📊 Base (SHAP expected)", score_base - sh_inclin - sh_umidade - sh_temp - sh_idade, "#5B7FFF"),
                ("📐 Inclinação Z",         sh_inclin,  "#FF4D6A" if sh_inclin > 0 else "#22D48A"),
                ("💧 Umidade solo",         sh_umidade, "#FF4D6A" if sh_umidade > 0 else "#22D48A"),
                ("🌡️ Temperatura motor",    sh_temp,    "#FF4D6A" if sh_temp > 0 else "#22D48A"),
                ("🔧 Idade equipamento",    sh_idade,   "#F5A623" if sh_idade > 0 else "#22D48A"),
            ]
            for label, val, cor in features:
                direcao = "▲" if val > 0 else "▼"
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;align-items:center;
                            padding:8px 12px;background:#07080C;border-radius:8px;margin-bottom:4px;">
                    <span style="font-size:0.82rem;color:#EEF0F8;">{label}</span>
                    <span style="font-size:0.85rem;font-weight:700;color:{cor};">
                        {direcao} {abs(val):.1f}
                    </span>
                </div>
                """, unsafe_allow_html=True)

            explicacao = f""
            top = sorted(features[1:], key=lambda x: abs(x[1]), reverse=True)[0]
            st.markdown(f"""
            <div style="background:rgba(91,127,255,0.08);border-left:2px solid #5B7FFF;
                        border-radius:6px;padding:12px 16px;margin-top:1rem;">
                <div style="font-size:0.78rem;color:#EEF0F8;line-height:1.6;">
                    ✦ Score de <strong>{score_base:.0f}%</strong> de risco.
                    Principal fator: <strong>{top[0]}</strong>
                    contribuindo com <strong>{top[1]:+.1f} pontos</strong>.
                </div>
            </div>
            """, unsafe_allow_html=True)

        gerar_trilha_auditoria("ACESSO_SHAP", f"Score explicado: {score_base}")

    with tab2:
        st.markdown("##### Simulador de ROI Sompo")
        col_a, col_b = st.columns(2)
        with col_a:
            frota        = st.slider("Frota Monitorada", 10, 500, 150)
            ef_preditiva = st.slider("Eficiência Preditiva (%)", 10, 80, 40)
            custo_medio  = st.slider("Custo Médio por Sinistro (R$ mil)", 100, 2000, 450)
        with col_b:
            sinistros_base   = frota * 0.15
            evitados         = int(sinistros_base * ef_preditiva / 100)
            economia         = evitados * custo_medio * 1000
            tco_plataforma   = frota * 2000
            lucro            = economia - tco_plataforma
            roi_pct          = round(lucro / tco_plataforma * 100) if tco_plataforma else 0
            payback_meses    = round(tco_plataforma / (economia / 12)) if economia > 0 else 0

            st.metric("Sinistros Evitados/ano", evitados)
            st.metric("Economia Bruta",  f"R$ {economia/1e6:.2f}M")
            st.metric("TCO Plataforma",  f"R$ {tco_plataforma/1e3:.0f}K")
            st.metric("ROI Estimado",    f"{roi_pct}%", delta=f"Payback: {payback_meses} meses")

    with tab3:
        st.markdown("##### Sprint 1 — Status Atual")
        us_data = [
            ("US01", "Identificação de Risco",  "Charles",   "🟡 Em andamento", 70),
            ("US02", "Governança / Auditoria",  "Rafael",    "🟡 Em andamento", 60),
            ("US03", "Painel Cliente",          "Charles",   "🔵 Planejado",    30),
            ("US04", "Operador de Equipamento", "Anthony",   "🟡 Em andamento", 55),
            ("US05", "Gestor de Frota",         "Gustavo",   "🔵 Planejado",    25),
            ("US06", "Técnico / Anomalias",     "Guilherme", "🟡 Em andamento", 50),
            ("US07", "Subscrição XAI",          "Rafael",    "🟡 Em andamento", 65),
            ("US08", "Analista de Sinistros",   "Guilherme", "🔵 Planejado",    20),
        ]
        for us_id, titulo, dono, status, pct in us_data:
            cor_d = MEMBER_COLORS.get(dono, "#5B7FFF")
            cor_s = "#22D48A" if "Concluído" in status else "#F5A623" if "andamento" in status else "#5B7FFF"
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid rgba(255,255,255,0.07);
                        border-radius:10px;padding:14px 18px;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;align-items:center;
                            margin-bottom:8px;">
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
                    <div style="background:{cor_s};width:{pct}%;height:100%;border-radius:3px;
                                transition:width .3s;"></div>
                </div>
                <div style="font-size:0.65rem;color:#4A4D62;margin-top:4px;text-align:right;">{pct}%</div>
            </div>
            """, unsafe_allow_html=True)


# ── 9.6 SEGURANÇA & AUTH (Charles) ──────────────────────────────────────

def pagina_seguranca():
    if not check_permissao("all") and not check_permissao("view_dashboard"):
        return
    _header("Segurança & Auth", "Charles", "RBAC · JWT · AES-256 · SHA-256 · Argon2id")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["🔐 Stack de Segurança", "👥 RBAC", "🔥 Stress Test", "📊 Métricas do Motor IA"]
    )

    with tab1:
        protos = [
            ("🔐 TLS 1.3",   "Em Trânsito",   "Criptografia end-to-end ESP32 → AWS. Perfect Forward Secrecy habilitado.",   "#29B6F6"),
            ("🔒 AES-256",   "Em Repouso",    "Fernet (AES-128-CBC + HMAC-SHA256) criptografa cada registro de telemetria.", "#00E676"),
            ("🔗 SHA-256",   "Integridade",   "Hash Chaining imutável — cada log carrega hash do registro anterior.",        "#FFA000"),
            ("🪙 JWT HS256", "Autenticação",  "Tokens assinados com 2h de validade. RBAC via claim `role`.",                "#AB47BC"),
            ("🛡️ Argon2id",  "Senhas",        "KDF: time_cost=2, memory_cost=64MiB (OWASP 2024). Resistente a GPU/ASIC.",  "#22D48A"),
        ]
        for icon_label, categoria, desc, cor in protos:
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid {cor}33;border-left:3px solid {cor};
                        border-radius:10px;padding:14px 18px;margin-bottom:8px;display:flex;
                        gap:16px;align-items:flex-start;">
                <div>
                    <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px;">
                        <span style="font-weight:700;font-size:0.9rem;color:{cor};">{icon_label}</span>
                        <span style="font-size:0.65rem;color:#4A4D62;text-transform:uppercase;
                                     letter-spacing:0.08em;">{categoria}</span>
                    </div>
                    <div style="font-size:0.82rem;color:#8B8FA8;line-height:1.55;">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with tab2:
        st.markdown("##### Matriz RBAC")
        rbac_data = []
        acoes = ["view_dashboard", "input_telemetry", "train_models", "extract_data", "view_dados", "all"]
        for role, perms in RBAC_MATRIX.items():
            row = {"Role": role}
            for a in acoes:
                row[a] = "✅" if ("all" in perms or a in perms) else "❌"
            rbac_data.append(row)
        st.dataframe(pd.DataFrame(rbac_data).set_index("Role"), use_container_width=True)

        st.markdown("<br>**Usuários cadastrados:**", unsafe_allow_html=True)
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
        st.markdown("##### Simulação de Ataque — Stress Test")
        if st.button("▶️ Executar Ataque Simulado (5 tentativas)", type="primary"):
            progresso = st.progress(0)
            log_area  = st.empty()
            bloqueado = False
            for i in range(1, 6):
                st.session_state.tentativas_falhas += 1
                gerar_trilha_auditoria("STRESS_TEST", f"Tentativa {i}/5")
                progresso.progress(i / 5)
                log_area.info(f"Tentativa {i}/5 | Falhas acumuladas: {st.session_state.tentativas_falhas}")
                time.sleep(0.35)
                if st.session_state.tentativas_falhas >= 3:
                    b = avaliar_risco_login(st.session_state.tentativas_falhas,
                                            datetime.now().hour, 0.9, 50.0)
                    if b:
                        gerar_trilha_auditoria("BLOQUEIO_IA_STRESS", f"Anomalia na tentativa {i}")
                        st.error(f"🚨 Motor IA detectou anomalia na tentativa {i} — bloqueio ativado!")
                        st.session_state.bloqueio_tempo = time.time() + 30
                        bloqueado = True
                        break
            if not bloqueado:
                st.success("Teste concluído sem bloqueio (score abaixo do threshold).")
            st.session_state.tentativas_falhas = 0

    with tab4:
        st.markdown("##### Desempenho do Motor de Risco (Decision Tree · Scikit-learn)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ROC-AUC",   METRICAS_IA["roc_auc"])
        c2.metric("F1-Fraude", METRICAS_IA["f1_fraude"])
        c3.metric("Recall",    METRICAS_IA["recall_fraude"])
        c4.metric("Precision", METRICAS_IA["precision_fraude"])
        st.caption("Treinado com `make_classification` (2000 amostras, 15% positivos). "
                   "Em produção: substituir pelo dataset real de tentativas de acesso.")
        gerar_trilha_auditoria("ACESSO_METRICAS_IA")


# ── 9.7 TRILHA DE AUDITORIA ─────────────────────────────────────────────

def pagina_auditoria():
    _header("Trilha de Auditoria", "Charles", "Hash Chaining · SHA-256 · AES-256 · Imutável")

    logs = st.session_state.logs_auditoria
    if not logs:
        st.info("Nenhum registro de auditoria ainda. Interaja com o sistema para gerar logs.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Total de Registros", len(logs))
    c2.metric("Último Hash (8 chars)", logs[-1]["hash"][:8] + "...")
    c3.metric("Integridade da Cadeia", "✅ Válida")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("##### Registros mais recentes (decrescente)")

    for log in reversed(logs[-20:]):
        tipo_cor = {
            "LOGIN_SUCESSO":   "#22D48A",
            "LOGIN_FALHA":     "#FF4D6A",
            "LOGOUT":          "#8B8FA8",
            "BLOQUEIO_IA":     "#FF4D6A",
            "VIOLACAO_RBAC":   "#F5A623",
            "STRESS_TEST":     "#F5A623",
        }.get(log["acao"], "#5B7FFF")

        st.markdown(f"""
        <div style="background:#0D0F18;border:1px solid rgba(255,255,255,0.07);
                    border-left:3px solid {tipo_cor};border-radius:8px;
                    padding:10px 16px;margin-bottom:6px;
                    font-family:monospace;font-size:0.76rem;color:#8B8FA8;">
            <span style="color:{tipo_cor};font-weight:700;">[{log['acao']}]</span>&nbsp;
            <span style="color:#4A4D62;">{log['timestamp']}</span>&nbsp;
            <span style="color:#EEF0F8;">@{log['usuario']}</span>&nbsp;
            <span style="color:#4A4D62;">— {log.get('detalhes','') or '—'}</span><br>
            <span style="color:#252840;">HASH: {log['hash']}</span>&nbsp;&nbsp;
            <span style="color:#252840;">ENC: {log['enc_preview']}</span>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("📥 Exportar como JSON"):
        st.code(json.dumps(logs, indent=2, ensure_ascii=False), language="json")


# ==========================================
# 10. ROTEADOR PRINCIPAL
# ==========================================

def main():
    if not st.session_state.jwt_token:
        tela_login()
        return

    pagina_id = sidebar()

    if pagina_id == "inicio":
        pagina_inicio()
    elif pagina_id == "dados":
        pagina_dados()
    elif pagina_id == "cloud":
        pagina_cloud()
    elif pagina_id == "iot":
        pagina_iot()
    elif pagina_id == "xai":
        pagina_xai()
    elif pagina_id == "seguranca":
        pagina_seguranca()
    elif pagina_id == "auditoria":
        pagina_auditoria()


if __name__ == "__main__":
    main()