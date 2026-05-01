"""
core_auth.py
============
Autenticacao, autorizacao (RBAC) e emissao de JWT.

Importavel por qualquer pagina via:
    from core_auth import inicializar_sessao, tela_login_registro, check_permissao, fazer_logout

Owner: Charles
"""
import re
import time
import hashlib
import secrets
import streamlit as st
import jwt
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet

from core_audit import gerar_trilha_auditoria


# Matriz de Controle de Acesso (RBAC)
RBAC_MATRIX = {
    "Admin": ["all"],
    "Cientista": ["view_dashboard", "train_models", "extract_data"],
    "Operador": ["view_dashboard", "input_telemetry"],
}


def inicializar_sessao() -> None:
    """Inicializa o session_state com chaves de seguranca + estado base."""
    if st.session_state.get("init"):
        return

    st.session_state.init = True

    # Chaves de cripto (geradas a cada boot — em prod viriam do KMS/Vault)
    st.session_state.kms_key = Fernet.generate_key()
    st.session_state.cipher_suite = Fernet(st.session_state.kms_key)
    st.session_state.jwt_secret = secrets.token_hex(32)

    # Cadeia de auditoria (genesis block)
    st.session_state.ultimo_hash = "GENESIS_BLOCK_000"
    st.session_state.logs_auditoria = []

    # Rate limiting
    st.session_state.tentativas_falhas = 0
    st.session_state.bloqueio_tempo = 0.0

    # Sessao do usuario
    st.session_state.jwt_token = None
    st.session_state.usuario_logado = None
    st.session_state.role_logado = None

    # Mock BD de usuarios — admin/admin123 default pro pitch
    st.session_state.mock_users = {
        "admin": {
            "senha_hash": hashlib.sha256("admin123".encode()).hexdigest(),
            "role": "Admin",
        }
    }


def _sanitizar_input(entrada: str) -> bool:
    """WAF basico: aceita apenas alphanum + underscore, 3-20 chars."""
    return bool(re.match(r"^[a-zA-Z0-9_]{3,20}$", entrada))


def _emitir_jwt(usuario: str, role: str) -> str:
    """Gera o token JWT com expiracao de 1h."""
    payload = {
        "user": usuario,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, st.session_state.jwt_secret, algorithm="HS256")


def check_permissao(acao_requerida: str) -> bool:
    """
    Middleware de autorizacao. Valida JWT + RBAC.

    Args:
        acao_requerida: nome da permissao (ex: "view_dashboard", "all").

    Returns:
        True se autorizado, False caso contrario (ja exibe st.error).
    """
    token = st.session_state.get("jwt_token")
    if not token:
        st.error("⛔ Acesso negado: token ausente.")
        return False

    try:
        payload = jwt.decode(
            token, st.session_state.jwt_secret, algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError:
        st.error("⛔ Sessao expirada. Faca login novamente.")
        gerar_trilha_auditoria("TOKEN_EXPIRADO", "Token expirado durante request")
        st.session_state.jwt_token = None
        return False
    except jwt.InvalidTokenError:
        st.error("⛔ Token invalido ou adulterado.")
        gerar_trilha_auditoria(
            "TOKEN_INVALIDO", "Tentativa de uso de token adulterado"
        )
        return False

    role = payload.get("role")
    permissoes = RBAC_MATRIX.get(role, [])

    if "all" in permissoes or acao_requerida in permissoes:
        return True

    st.error(
        f"⛔ Acesso negado: perfil '{role}' nao permite '{acao_requerida}'."
    )
    gerar_trilha_auditoria(
        "VIOLACAO_RBAC", f"Role={role} | Acao={acao_requerida}"
    )
    return False


def tela_login_registro() -> None:
    """Renderiza tela de login + cadastro com rate limiting + WAF."""
    st.title("🔐 Sompo Secure Gateway")
    st.caption("Login obrigatorio · JWT + RBAC + Trilha de Auditoria SHA-256")

    # Rate limiting check
    if st.session_state.tentativas_falhas >= 3:
        if time.time() < st.session_state.bloqueio_tempo:
            restante = int(st.session_state.bloqueio_tempo - time.time())
            st.error(
                f"⛔ Multiplas falhas detectadas. Tente novamente em {restante}s."
            )
            return
        else:
            st.session_state.tentativas_falhas = 0

    tab_login, tab_cadastro = st.tabs(["🔓 Fazer Login", "📝 Novo Cadastro"])

    with tab_login:
        with st.form("login_form"):
            user = st.text_input("Usuario", key="login_user")
            pwd = st.text_input("Senha", type="password", key="login_pwd")
            submit = st.form_submit_button("Entrar")

            if submit:
                _processar_login(user, pwd)

    with tab_cadastro:
        with st.form("register_form"):
            n_user = st.text_input("Novo Usuario", key="reg_user")
            n_pwd = st.text_input("Nova Senha", type="password", key="reg_pwd")
            n_role = st.selectbox(
                "Perfil de Acesso",
                ["Operador", "Cientista", "Admin"],
                key="reg_role",
            )
            reg_submit = st.form_submit_button("Cadastrar")

            if reg_submit:
                _processar_cadastro(n_user, n_pwd, n_role)

    # Hint de credenciais default pro pitch
    with st.expander("ℹ️  Credenciais default (demo)"):
        st.code("usuario: admin\nsenha: admin123\nperfil: Admin", language="text")


def _processar_login(user: str, pwd: str) -> None:
    """Logica de processamento do login com WAF + rate limit."""
    if not _sanitizar_input(user):
        st.warning("🛡️  WAF: input rejeitado. Use 3-20 caracteres alfanumericos.")
        st.session_state.tentativas_falhas += 1
        gerar_trilha_auditoria("WAF_BLOQUEIO", f"Input invalido: {user[:10]}")
        return

    user_db = st.session_state.mock_users.get(user)
    pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()

    if user_db and user_db["senha_hash"] == pwd_hash:
        st.session_state.tentativas_falhas = 0
        st.session_state.usuario_logado = user
        st.session_state.role_logado = user_db["role"]
        st.session_state.jwt_token = _emitir_jwt(user, user_db["role"])
        gerar_trilha_auditoria("LOGIN_SUCESSO", f"Role: {user_db['role']}")
        st.rerun()
    else:
        st.session_state.tentativas_falhas += 1
        gerar_trilha_auditoria("LOGIN_FALHA", f"Tentativa para usuario: {user}")
        if st.session_state.tentativas_falhas >= 3:
            st.session_state.bloqueio_tempo = time.time() + 30
            gerar_trilha_auditoria(
                "BLOQUEIO_RATE_LIMIT", "3 falhas consecutivas — bloqueio 30s"
            )
        st.error("Credenciais invalidas.")


def _processar_cadastro(user: str, pwd: str, role: str) -> None:
    """Cadastro de novo usuario com hash SHA-256."""
    if not _sanitizar_input(user):
        st.warning("🛡️  Usuario invalido. Use 3-20 caracteres alfanumericos.")
        return
    if user in st.session_state.mock_users:
        st.error("Usuario ja existe.")
        return
    if len(pwd) < 4:
        st.error("Senha muito curta (minimo 4 caracteres).")
        return

    st.session_state.mock_users[user] = {
        "senha_hash": hashlib.sha256(pwd.encode()).hexdigest(),
        "role": role,
    }
    gerar_trilha_auditoria("NOVO_USUARIO", f"User={user} | Role={role}")
    st.success(
        f"✅ Usuario '{user}' cadastrado com perfil '{role}'. Va para a aba de login."
    )


def fazer_logout() -> None:
    """Encerra a sessao atual e limpa o JWT."""
    gerar_trilha_auditoria(
        "LOGOUT", f"User={st.session_state.usuario_logado}"
    )
    st.session_state.jwt_token = None
    st.session_state.usuario_logado = None
    st.session_state.role_logado = None
    st.rerun()
