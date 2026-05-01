"""
test_pagina_local.py
====================
Helper pra desenvolvimento local — bypassa o login pra testar uma pagina isolada.

Uso:
    streamlit run test_pagina_local.py

Edite a linha PAGINA_TESTAR (abaixo) pra escolher qual pagina testar.

⚠️  USAR APENAS EM DEV — esse helper bypassa toda a seguranca.
"""
import streamlit as st
from core_auth import inicializar_sessao
from core_audit import renderizar_trilha


# ============== EDITE AQUI ==============
import pagina_anthony as PAGINA_TESTAR
# import pagina_guilherme as PAGINA_TESTAR
# import pagina_gustavo as PAGINA_TESTAR
# import pagina_rafael as PAGINA_TESTAR
# import dashboard_cliente as PAGINA_TESTAR
# ========================================


st.set_page_config(
    page_title="DEV — Test Page",
    page_icon="🧪",
    layout="wide",
)

inicializar_sessao()

# Bypass de login pra desenvolvimento local
st.session_state.jwt_token = "fake_dev_token"
st.session_state.usuario_logado = "dev_local"
st.session_state.role_logado = "Admin"

st.warning(
    "🧪 **MODO DEV** — Login bypassado. NAO USE EM PRODUCAO. "
    "Esse arquivo so serve pra testar paginas isoladas durante o desenvolvimento."
)
st.markdown("---")

# Renderiza a pagina escolhida
PAGINA_TESTAR.render()

# Mostra trilha de auditoria no rodape (mesmo comportamento da app real)
st.markdown("---")
renderizar_trilha(qtd=10)
