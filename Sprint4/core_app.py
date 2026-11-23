"""
core_app.py
===========
Camada compartilhada do roteador: autorizacao (RBAC via JWT), verificacao de
senha (Argon2id) e os dois componentes visuais usados por TODAS as paginas
do menu (_header e _contrato_box).

Owner: Charles (transversal a todos os modulos)

Importavel por qualquer pagina via:
    from core_app import gerar_trilha_auditoria, check_permissao, _header, _contrato_box

Paleta de referencia (definida em :root pelo app.py, mesmos valores aqui
em hex puro para os componentes que nao podem depender de CSS injetado
por outra chamada de st.markdown):
    bg #080D0C · surface #0E1614 · surface2 #141F1C · bg4 #1B2926
    linha rgba(224,236,231,.08) · texto #E4EDE9 / #8FA39B / #5A6B65
    marca Sompo #E53935 · farol verde #63A87C · amarelo #DDA53C · vermelho #E04B45
    accent (info) #6C86C4
"""
import streamlit as st
import jwt
from argon2.exceptions import VerifyMismatchError

from core_audit import gerar_trilha_auditoria  # noqa: F401  (re-export - fonte unica)

# ==========================================================================
# IDENTIDADE VISUAL POR MEMBRO (fonte unica - app.py importa daqui)
# ==========================================================================

MEMBER_COLORS = {
    "Guilherme": "#DDA53C",
    "Gustavo":   "#E04B45",
    "Anthony":   "#9B79C0",
    "Rafael":    "#6C86C4",
    "Charles":   "#63A87C",
}

# ==========================================================================
# RBAC — mesma matriz usada no login (app.py)
# ==========================================================================

RBAC_MATRIX = {
    "Admin":      ["all"],
    "Subscritor": ["view_dashboard", "view_dados", "decidir_subscricao"],
    "Cientista":  ["view_dashboard", "train_models", "extract_data", "view_dados"],
    "Operador":   ["view_dashboard", "input_telemetry", "view_iot"],
    # Segurado ve APENAS o proprio equipamento. Sem view_dados: a base de
    # apolices contem informacao de outros clientes, e nenhuma tela do
    # portal do segurado precisa dela para funcionar.
    "Segurado":   ["view_proprio_equipamento", "view_iot"],
}


def check_permissao(acao_requerida: str) -> bool:
    """
    Middleware de autorizacao chamado no topo de cada pagina do menu.
    Valida o JWT emitido no login e checa a permissao na RBAC_MATRIX.

    Args:
        acao_requerida: nome da permissao (ex: "view_dashboard", "all").

    Returns:
        True se autorizado. Caso contrario, ja exibe st.error e audita
        a violacao (VIOLACAO_RBAC), e retorna False.
    """
    token = st.session_state.get("jwt_token")
    if not token:
        st.error("Acesso negado: sessao nao autenticada.")
        return False

    try:
        payload = jwt.decode(
            token, st.session_state.jwt_secret, algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError:
        st.error("Sessao expirada. Faca login novamente.")
        gerar_trilha_auditoria("TOKEN_EXPIRADO", "token expirado durante request")
        st.session_state.jwt_token = None
        return False
    except jwt.InvalidTokenError:
        st.error("Token invalido ou adulterado.")
        gerar_trilha_auditoria("TOKEN_INVALIDO", "tentativa de uso de token adulterado")
        return False

    role = payload.get("role")
    permissoes = RBAC_MATRIX.get(role, [])

    if "all" in permissoes or acao_requerida in permissoes:
        return True

    st.error(f"Acesso negado: perfil '{role}' nao tem permissao para '{acao_requerida}'.")
    gerar_trilha_auditoria("VIOLACAO_RBAC", f"role={role} acao={acao_requerida}")
    return False


def check_permissao_silenciosa(acao_requerida: str) -> bool:
    """
    Mesma verificacao de check_permissao, sem exibir erro nem auditar.

    Existe para telas que aceitam MAIS DE UM caminho de autorizacao — por
    exemplo, o painel do equipamento, aberto tanto a quem administra a
    carteira quanto ao proprio segurado. Usar check_permissao nesses casos
    faria a primeira tentativa imprimir "acesso negado" na tela mesmo
    quando a segunda fosse aprovada.

    Quem chama e responsavel por tratar o False.
    """
    token = st.session_state.get("jwt_token")
    if not token:
        return False
    try:
        payload = jwt.decode(token, st.session_state.jwt_secret,
                             algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return False
    permissoes = RBAC_MATRIX.get(payload.get("role"), [])
    return "all" in permissoes or acao_requerida in permissoes


def verificar_senha(hash_alvo: str, senha: str) -> bool:
    """Verifica senha em texto puro contra um hash Argon2id (tempo constante)."""
    ph = st.session_state.ph
    try:
        ph.verify(hash_alvo, senha)
        return True
    except VerifyMismatchError:
        return False


# ==========================================================================
# COMPONENTES VISUAIS COMPARTILHADOS
# ==========================================================================

def _header(titulo: str, subtitulo: str = "", _legado: str = "") -> None:
    """
    Cabecalho padrao de pagina. Assinatura aceita a forma antiga de tres
    argumentos (titulo, membro, subtitulo) para nao quebrar paginas que
    ainda nao foram atualizadas — nesse caso o segundo argumento e
    descartado e o terceiro vira o subtitulo.
    """
    if _legado:                      # chamada antiga: (titulo, membro, subtitulo)
        subtitulo = _legado
    st.markdown(f"""
    <div style="padding:0.2rem 0 1.1rem;border-bottom:1px solid var(--stroke);
                margin-bottom:1.3rem;">
        <h2 style="font-family:'Manrope',sans-serif;font-weight:800;
                   font-size:1.75rem;letter-spacing:-0.03em;
                   color:var(--text);margin:0;">{titulo}</h2>
        <div style="font-size:0.88rem;color:var(--text-2);margin-top:7px;">
            {subtitulo}</div>
    </div>
    """, unsafe_allow_html=True)


def _contrato_box(nome_pagina: str, acoes: list[str]) -> None:
    """
    Aviso de conformidade. Informa ao usuario que a navegacao e registrada,
    sem expor nome de funcao nem identificador interno.
    """
    st.markdown("""
    <div class="contrato-box">
        Acessos e consultas nesta tela sao registrados em trilha imutavel
        (SHA-256), com dados em repouso cifrados em AES-256, conforme a
        politica de tratamento de dados da apolice.
    </div>
    """, unsafe_allow_html=True)
