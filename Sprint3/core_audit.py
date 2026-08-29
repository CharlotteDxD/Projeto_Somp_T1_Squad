"""
==============================================================================
core_audit.py — trilha de auditoria imutavel
==============================================================================
Registro encadeado por SHA-256 com o conteudo cifrado em AES (Fernet).
Cada entrada carrega o hash da anterior, de modo que alterar um registro
antigo invalida toda a cadeia a partir dele.

Este modulo e a FONTE UNICA de gerar_trilha_auditoria. O core_app.py
re-exporta a funcao para as paginas que a importam de la.

    core_audit  (define)  <--  core_app  (re-exporta)  <--  paginas

NUNCA importe core_app aqui: core_app ja importa deste modulo, e a
importacao nos dois sentidos gera ImportError de import circular.

NUNCA chame st.* no top-level — este modulo e importado antes de
st.set_page_config() em alguns fluxos.
==============================================================================
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st


def gerar_trilha_auditoria(acao: str, detalhes: str = "") -> str:
    """
    Registra uma acao na trilha imutavel e devolve o hash gerado.

    Encadeamento: cada registro inclui o hash do anterior antes de ser
    hasheado, o que torna a sequencia verificavel de ponta a ponta.
    O conteudo completo e cifrado em AES (Fernet) antes de ser guardado.

    Args:
        acao: identificador do evento (ex.: "ACESSO_US01", "LOGOUT").
        detalhes: contexto livre, truncado em 80 caracteres na exibicao.

    Returns:
        Hash SHA-256 do registro. Retorna string vazia se a sessao ainda
        nao estiver inicializada (chamada antes do boot do app).
    """
    if "ultimo_hash" not in st.session_state:
        return ""

    usuario = st.session_state.get("usuario_logado") or "SISTEMA"
    registro = {
        "acao":      acao,
        "detalhes":  detalhes,
        "prev_hash": st.session_state.ultimo_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "usuario":   usuario,
    }

    canonico = json.dumps(registro, sort_keys=True, separators=(",", ":"))
    hash_novo = hashlib.sha256(canonico.encode()).hexdigest()
    registro["hash_atual"] = hash_novo
    st.session_state.ultimo_hash = hash_novo

    try:
        cifrado = st.session_state.cipher_suite.encrypt(
            json.dumps(registro).encode()
        ).decode()
    except Exception:
        cifrado = ""

    st.session_state.setdefault("logs_auditoria", []).append({
        "timestamp":   datetime.now().strftime("%H:%M:%S"),
        "usuario":     usuario,
        "acao":        acao,
        "detalhes":    detalhes[:80] + ("..." if len(detalhes) > 80 else ""),
        "hash":        hash_novo[:16] + "...",
        "enc_preview": (cifrado[:36] + "...") if cifrado else "—",
    })
    return hash_novo


def renderizar_trilha(
    limite: int = 50,
    filtro_acao: Optional[str] = None,
) -> pd.DataFrame:
    """
    Devolve as ultimas entradas da trilha como DataFrame, prontas para
    st.dataframe. Nao renderiza direto — quem chama decide como exibir.

    Args:
        limite: quantas entradas mais recentes retornar.
        filtro_acao: se fornecido, filtra por substring no campo 'acao'.

    Returns:
        DataFrame com as colunas da trilha, mais recente primeiro, ou
        DataFrame vazio se ainda nao houver registro na sessao.
    """
    colunas = ["timestamp", "usuario", "acao", "detalhes", "hash", "enc_preview"]
    log = st.session_state.get("logs_auditoria", [])
    if not log:
        return pd.DataFrame(columns=colunas)

    df = pd.DataFrame(log)
    if filtro_acao and "acao" in df.columns:
        df = df[df["acao"].astype(str).str.contains(
            filtro_acao, case=False, na=False)]
    return df.iloc[::-1].head(limite).reset_index(drop=True)


__all__ = ["gerar_trilha_auditoria", "renderizar_trilha"]
