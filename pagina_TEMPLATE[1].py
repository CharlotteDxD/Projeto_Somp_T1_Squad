"""
pagina_TEMPLATE.py
==================
TEMPLATE pra Anthony, Guilherme, Gustavo e Rafael.

Copie esse arquivo, renomeie pra `pagina_SEUNOME.py` e implemente o `render()`.

============================================================
REGRAS DO CONTRATO (LEIA ANTES DE CODAR)
============================================================
1. Funcao obrigatoria: `def render():` — sem argumentos, sem retorno.
2. NAO faca login na sua pagina. Quando ela rodar, o usuario JA esta logado.
3. NAO use `st.set_page_config` — apenas o `app.py` faz isso.
4. Toda acao relevante chama `gerar_trilha_auditoria("ACAO_CAIXA_ALTA", "detalhes")`.
5. Use `key=` em TODOS os widgets, prefixado com seu nome.
   Ex: `key="anthony_slider1"`, `key="guil_btn_load"`.
6. Imports pesados (shap, tensorflow, torch) ficam DENTRO de `render()`,
   nao no topo do arquivo (sao lazy — so carregam quando alguem clica na pagina).
7. Nao escreva no `st.session_state` em chaves nao prefixadas com seu nome.
   (Pra nao quebrar a sessao do Charles.)
8. Deadline: SEXTA 01/05 as 20h, no GitHub do projeto.
============================================================
"""
import streamlit as st
from core_audit import gerar_trilha_auditoria


def render():
    """Funcao unica que o app.py vai chamar quando o usuario navegar pra ca."""

    st.title("📌 Minha Pagina")
    st.markdown("Descricao do que essa secao faz no fluxo do produto Sompo.")

    # === SEU CODIGO COMECA AQUI ===

    valor = st.slider(
        "Exemplo de input",
        min_value=0,
        max_value=100,
        value=50,
        key="meunome_slider1",  # ← prefixe com seu nome!
    )

    if st.button("Calcular", key="meunome_btn1"):
        # Sua logica de negocio
        resultado = valor * 2

        st.success(f"Resultado: {resultado}")

        # === HOOK DE AUDITORIA OBRIGATORIO ===
        # Toda acao significativa precisa virar um log encadeado.
        # Charles vai conferir isso no review da integracao (sabado 02/05).
        gerar_trilha_auditoria(
            acao="MINHA_ACAO_RELEVANTE",        # CAIXA_ALTA, descritivo
            detalhes=f"Valor={valor} | Resultado={resultado}",  # contexto
        )

    # === EXEMPLO: lazy import de lib pesada ===
    # if st.button("Rodar SHAP", key="meunome_btn_shap"):
    #     import shap   # ← DENTRO da funcao, nao no topo
    #     # ... codigo SHAP aqui
