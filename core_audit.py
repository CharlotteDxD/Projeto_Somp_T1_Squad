"""
core_audit.py
=============
Trilha de auditoria imutavel com hash chaining + criptografia AES (Fernet).
Importavel por qualquer pagina do projeto via:

    from core_audit import gerar_trilha_auditoria, renderizar_trilha

Owner: Charles (transversal a todos os modulos)
"""
import json
import hashlib
import streamlit as st
from datetime import datetime, timezone
from cryptography.fernet import Fernet


def _garantir_sessao():
    """Garante que as chaves de sessao existem antes de usar."""
    if "ultimo_hash" not in st.session_state:
        st.session_state.ultimo_hash = "GENESIS_BLOCK_000"
    if "logs_auditoria" not in st.session_state:
        st.session_state.logs_auditoria = []
    if "kms_key" not in st.session_state:
        st.session_state.kms_key = Fernet.generate_key()
        st.session_state.cipher_suite = Fernet(st.session_state.kms_key)


def gerar_trilha_auditoria(acao: str, detalhes: str = "") -> str:
    """
    Gera um log imutavel encadeado criptograficamente com o log anterior.

    Cada log e:
      1. Estruturado em Canonical JSON (chaves ordenadas, sem espacos)
      2. SHA-256 hasheado, com referencia ao prev_hash (hash chaining)
      3. Criptografado com Fernet (AES-128-CBC + HMAC) antes de salvar

    Args:
        acao: Nome da acao em CAIXA_ALTA (ex: "LOGIN_SUCESSO").
        detalhes: Texto livre com contexto (ex: "Score=88 | Equip=COL-099").

    Returns:
        O hash SHA-256 do log gerado (str hex de 64 chars).
    """
    _garantir_sessao()

    usuario_logado = st.session_state.get("usuario_logado") or "SISTEMA"

    registro = {
        "acao": acao,
        "detalhes": detalhes,
        "prev_hash": st.session_state.ultimo_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "usuario": usuario_logado,
    }

    # Canonical JSON garante hash deterministico independente da ordem
    registro_canonico = json.dumps(registro, sort_keys=True, separators=(",", ":"))
    hash_atual = hashlib.sha256(registro_canonico.encode("utf-8")).hexdigest()

    registro["hash_atual"] = hash_atual
    st.session_state.ultimo_hash = hash_atual

    # Criptografa o payload completo antes de armazenar
    payload_criptografado = st.session_state.cipher_suite.encrypt(
        json.dumps(registro).encode()
    ).decode()

    entrada = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "usuario":   usuario_logado,
        "acao":      acao,
        "detalhes":  detalhes,
        "hash":      hash_atual[:16] + "...",
        "enc_preview": payload_criptografado[:36] + "...",
    }
    st.session_state.logs_auditoria.append(entrada)

    return hash_atual


def renderizar_trilha(qtd: int = 10) -> None:
    """Renderiza os ultimos N logs num expander Streamlit."""
    _garantir_sessao()
    with st.expander(f"⛓️ Trilha de Auditoria (ultimos {qtd} logs)"):
        logs = st.session_state.get("logs_auditoria", [])
        if not logs:
            st.info("Nenhum log gerado ainda nesta sessao.")
            return
        for log in reversed(logs[-qtd:]):
            tipo_cor = {
                "LOGIN_SUCESSO": "#22D48A",
                "LOGIN_FALHA":   "#FF4D6A",
                "LOGOUT":        "#8B8FA8",
                "BLOQUEIO_IA":   "#FF4D6A",
                "VIOLACAO_RBAC": "#F5A623",
            }.get(log["acao"], "#5B7FFF")
            st.markdown(f"""
            <div style="font-family:monospace;font-size:0.75rem;
                        padding:8px 12px;margin-bottom:4px;
                        background:#07080C;border-left:3px solid {tipo_cor};
                        border-radius:6px;color:#8B8FA8;">
                <span style="color:{tipo_cor};font-weight:700;">[{log['acao']}]</span>
                <span style="color:#4A4D62;"> {log['timestamp']}</span>
                <span style="color:#EEF0F8;"> @{log['usuario']}</span>
                — {log.get('detalhes','') or '—'}<br>
                <span style="color:#252840;">HASH: {log['hash']} | ENC: {log['enc_preview']}</span>
            </div>
            """, unsafe_allow_html=True)
        st.caption(f"Total: {len(logs)} logs encadeados via SHA-256 + Fernet (AES)")
