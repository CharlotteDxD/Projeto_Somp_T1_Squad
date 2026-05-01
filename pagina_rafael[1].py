"""
pagina_rafael.py
================
Modulo XAI + Ranking de Risco da Frota — Rafael/Gon (US07)

STATUS: PLACEHOLDER FUNCIONAL.
Rafael entrega a versao final ate sexta 01/05 as 20h.

Substituir por: SHAP real explicando os top fatores, ranking dinamico
a partir da API do Gustavo + dados do Guilherme.
"""
import streamlit as st
import pandas as pd

from core_audit import gerar_trilha_auditoria


def render():
    """Pagina XAI + Ranking da Frota (visao Subscritor Sompo)."""
    st.title("🎯 XAI + Ranking de Risco da Frota")
    st.warning(
        "⏳ Aguardando entrega final do Rafael (deadline: sex 01/05, 20h). "
        "Esta versao e um placeholder funcional pra testar a integracao."
    )

    st.markdown("""
    **Escopo esperado nesta pagina:**
    - DataFrame com ranking de risco dos ativos da frota
    - **SHAP values** explicando os top 3 fatores que impactam cada score
    - Explicacao textual gerada automaticamente
      (ex: *"88% de risco devido inclinacao eixo Z (+42%)"*)
    - Tabela ordenada + filtro por regiao/equipamento
    - Hooks de auditoria: `gerar_trilha_auditoria("CONSULTA_XAI", ...)`

    > 💡 **Lazy import:** `import shap` deve ficar DENTRO de render(), nao no topo
    > do arquivo (demora ~3s pra carregar — atrasa a app inteira).
    """)

    # === MOCK PROVISORIO ===
    st.markdown("### 🧪 Mock provisorio")

    df = pd.DataFrame({
        "Ativo": ["COL-099", "TRT-102", "PUL-045", "COL-051", "TRT-088"],
        "Tipo": [
            "Colheitadeira", "Trator", "Pulverizador",
            "Colheitadeira", "Trator",
        ],
        "Regiao": ["Sul", "Centro-Oeste", "Sudeste", "Sul", "Norte"],
        "Score_Risco": [88.5, 45.2, 72.1, 65.0, 31.8],
        "Recomendacao": [
            "🔴 Parada Imediata", "🟢 Inspecao Normal", "🟡 Reduzir Velocidade",
            "🟡 Manutencao Preventiva", "🟢 Operacao Segura",
        ],
    }).sort_values("Score_Risco", ascending=False)

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    ativo = st.selectbox(
        "Selecione ativo pra ver explicacao XAI",
        df["Ativo"].tolist(),
        key="rafa_sel",
    )

    if st.button("Gerar explicacao SHAP (mock)", key="rafa_btn"):
        score = df[df["Ativo"] == ativo]["Score_Risco"].iloc[0]
        st.info(f"📊 Top 3 fatores de risco para **{ativo}** (Score: {score}/100):")

        col1, col2, col3 = st.columns(3)
        col1.metric("Inclinacao eixo Z", "+42%", "principal fator")
        col2.metric("Umidade do solo", "+28%", "secundario")
        col3.metric("Idade do equipamento", "+18%", "terciario")

        st.markdown(
            f"> *O ativo **{ativo}** apresenta {score}% de risco principalmente "
            f"devido a inclinacao no eixo Z (+42% de impacto), seguido pela "
            f"umidade do solo (+28%) e idade estrutural (+18%).*"
        )

        gerar_trilha_auditoria(
            "CONSULTA_XAI_MOCK",
            f"Ativo={ativo} | Score={score} | Top fator: inclinacao_z (+42%)",
        )
        st.success("✅ Trilha de auditoria registrada.")
