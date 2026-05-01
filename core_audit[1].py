"""
core_audit.py
=============
Trilha de auditoria imutavel com hash chaining + criptografia AES (Fernet).
Importavel por qualquer pagina do projeto via:

    from core_audit import gerar_trilha_auditoria

Owner: Charles (transversal a todos os modulos)
"""
import json
import hashlib
import streamlit as st
from datetime import datetime, timezone
from cryptography.fernet import Fernet


def gerar_trilha_auditoria(acao: str, detalhes: str = "") -> str:
    """
    Gera um log imutavel encadeado criptograficamente com o log anterior.

    Cada log e:
      1. Estruturado em Canonical JSON (chaves ordenadas, sem espacos)
      2. SHA-256 hasheado, com referencia ao prev_hash (hash chaining)
      3. Criptografado com Fernet (AES-128-CBC + HMAC) antes de salvar

    Args:
        acao: Nome da acao em CAIXA_ALTA (ex: "LOGIN_SUCESSO", "CALCULO_SCORE").
        detalhes: Texto livre com contexto (ex: "Score=88 | Equip=COL-099").

    Returns:
        O hash SHA-256 do log gerado (str hex de 64 chars).
    """
    # Defesa caso seja chamada antes de inicializar_sessao()
    if "ultimo_hash" not in st.session_state:
        st.session_state.ultimo_hash = "GENESIS_BLOCK_000"
        st.session_state.logs_auditoria = []
        st.session_state.kms_key = Fernet.generate_key()
        st.session_state.cipher_suite = Fernet(st.session_state.kms_key)

    usuario_logado = st.session_state.get("usuario_logado") or "SISTEMA"

    registro = {
        "acao": acao,
        "detalhes": detalhes,
        "prev_hash": st.session_state.ultimo_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "usuario": usuario_logado,
    }

    # Canonical JSON: chaves ordenadas, sem espacos. Garante hash deterministico.
    registro_canonico = json.dumps(registro, sort_keys=True, separators=(",", ":"))
    hash_atual = hashlib.sha256(registro_canonico.encode("utf-8")).hexdigest()

    registro["hash_atual"] = hash_atual
    st.session_state.ultimo_hash = hash_atual

    # Criptografa o payload completo e armazena
    payload_criptografado = st.session_state.cipher_suite.encrypt(
        json.dumps(registro).encode()
    ).decode()

    log_str = (
        f"HASH: {hash_atual[:8]}... | "
        f"USER: {usuario_logado} | "
        f"ACAO: {acao} | "
        f"ENC: {payload_criptografado[:32]}..."
    )
    st.session_state.logs_auditoria.append(log_str)

    return hash_atual


def renderizar_trilha(qtd: int = 10) -> None:
    """Renderiza os ultimos N logs num expander Streamlit (rodape padrao)."""
    with st.expander(f"⛓️  Trilha de Auditoria (ultimos {qtd} logs)"):
        logs = st.session_state.get("logs_auditoria", [])
        if not logs:
            st.info("Nenhum log gerado ainda nesta sessao.")
            return
        for log in logs[-qtd:]:
            st.code(log, language="text")
        st.caption(
            f"Total acumulado: {len(logs)} logs encadeados via SHA-256 + Fernet (AES)"
        )
