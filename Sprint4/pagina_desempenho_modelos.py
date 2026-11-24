"""
pagina_desempenho_modelos.py
============================
Desempenho dos modelos preditivos — números de execução, não digitados.

Toda métrica desta tela vem de `metricas_modelo.json`, gerado por
`avaliar_modelo_rafael.py`. Se o modelo mudar e o arquivo não for
regenerado, a tela informa a data da última execução em vez de exibir um
número desatualizado como se fosse atual.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ARQUIVO = Path("metricas_modelo.json")
CLASSES = ["Baixo", "Médio", "Alto", "Crítico"]

_ROTULO = {
    "accuracy": "otimizado por acurácia",
    "f1_macro": "otimizado por F1 macro",
}


@st.cache_data(ttl=300)
def _carregar():
    if not ARQUIVO.exists():
        return None
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cartao(col, valor, rotulo, cor="var(--text)", nota=""):
    extra = (f'<div style="font-size:0.68rem;color:var(--text-3);'
             f'margin-top:4px;">{nota}</div>') if nota else ""
    col.markdown(f"""
    <div class="g-card" style="padding:1rem 1.15rem;">
        <div class="g-num" style="color:{cor};">{valor}</div>
        <div class="g-label">{rotulo}</div>
        {extra}
    </div>
    """, unsafe_allow_html=True)


def render() -> None:
    from core_app import check_permissao, gerar_trilha_auditoria, _contrato_box, _header

    if not check_permissao("view_dashboard"):
        return
    _contrato_box("desempenho", [])
    _header("Desempenho dos Modelos",
            "Resultados de validação, comparados contra referência")
    gerar_trilha_auditoria("ACESSO_DESEMPENHO", "pagina=desempenho_modelos")

    r = _carregar()
    if r is None:
        st.error(
            "Métricas indisponíveis. Execute `python avaliar_modelo_rafael.py` "
            "para gerar `metricas_modelo.json` — esta tela não exibe valores "
            "que não venham de uma execução.", icon="🚨")
        return

    b = r["base"]
    gerado = datetime.fromisoformat(r["gerado_em"])
    st.markdown(
        f"<div class='pill' style='margin-bottom:1.3rem;'>"
        f"<span class='dot' style='background:var(--verde);"
        f"box-shadow:0 0 8px var(--verde);'></span>"
        f"<span style='color:var(--text-2);'>Execução de "
        f"{gerado:%d/%m/%Y às %H:%M} · {b['registros']} registros · "
        f"{b['treino']} treino / {b['teste']} teste</span></div>",
        unsafe_allow_html=True)

    base = r["baseline_ingenuo"]
    acc = r["xgboost"]["accuracy"]
    f1m = r["xgboost"]["f1_macro"]

    # ---------------- Indicadores ----------------
    c1, c2, c3, c4 = st.columns(4)
    _cartao(c1, f"{base:.3f}", "Referência",
            "var(--text-3)", "prever sempre a classe mais comum")
    _cartao(c2, f"{acc['acuracia']:.3f}", "Melhor acurácia",
            "var(--amarelo)",
            f"prevê {len(acc['classes_previstas'])} de 4 classes")
    _cartao(c3, f"{f1m['f1_macro']:.3f}", "Melhor F1 macro",
            "var(--text)", "trata as 4 classes igualmente")
    _cartao(c4, f"{f1m['recall_por_classe']['Crítico']:.0%}",
            "Casos críticos identificados",
            "var(--vermelho)" if f1m["recall_por_classe"]["Crítico"] == 0
            else "var(--verde)")

    st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)

    tab_comp, tab_classe, tab_leitura = st.tabs(
        ["Comparação", "Desempenho por classe", "Leitura do resultado"])

    # =================================================================
    with tab_comp:
        ref = r["referencia_sprint2"]
        linhas = [
            {"Modelo": "Referência (classe mais comum)",
             "Acurácia": base, "F1 macro": None, "Classes previstas": "1 de 4"},
            {"Modelo": "Árvore de decisão",
             "Acurácia": ref["decision_tree"], "F1 macro": None,
             "Classes previstas": "—"},
            {"Modelo": "Rede neural (MLP)",
             "Acurácia": ref["mlp"], "F1 macro": None,
             "Classes previstas": "—"},
        ]
        for met, d in r["xgboost"].items():
            linhas.append({
                "Modelo": f"XGBoost · {_ROTULO[met]}",
                "Acurácia": d["acuracia"],
                "F1 macro": d["f1_macro"],
                "Classes previstas": f"{len(d['classes_previstas'])} de 4",
            })

        st.dataframe(
            pd.DataFrame(linhas),
            column_config={
                "Acurácia": st.column_config.ProgressColumn(
                    "Acurácia", format="%.3f", min_value=0.0, max_value=1.0),
                "F1 macro": st.column_config.NumberColumn(
                    "F1 macro", format="%.3f"),
            },
            hide_index=True, use_container_width=True)

        st.caption(
            "A coluna **Classes previstas** é a que revela o comportamento "
            "real. Um modelo que prevê uma única classe atinge a acurácia da "
            "referência sem distinguir nada.")

        st.markdown("**Parâmetros selecionados**")
        for met, d in r["xgboost"].items():
            with st.expander(f"XGBoost · {_ROTULO[met]}"):
                st.json(d["melhores_parametros"])

    # =================================================================
    with tab_classe:
        st.markdown(
            "Acerto por classe. Em subscrição, **Alto** e **Crítico** são as "
            "que decidem — errar nelas é o que custa.")

        dados = {"Classe": CLASSES}
        for met, d in r["xgboost"].items():
            dados[_ROTULO[met].capitalize()] = [
                d["recall_por_classe"][c] for c in CLASSES]
        df_rec = pd.DataFrame(dados)

        st.dataframe(
            df_rec,
            column_config={
                col: st.column_config.ProgressColumn(
                    col, format="%.2f", min_value=0.0, max_value=1.0)
                for col in df_rec.columns if col != "Classe"
            },
            hide_index=True, use_container_width=True)

        st.markdown("**Distribuição das previsões**")
        cols = st.columns(len(r["xgboost"]))
        for col, (met, d) in zip(cols, r["xgboost"].items()):
            with col:
                st.markdown(f"*{_ROTULO[met].capitalize()}*")
                dist = d["distribuicao_previsoes"]
                total = sum(dist.values())
                for classe in CLASSES:
                    n = dist.get(classe, 0)
                    pct = n / total * 100 if total else 0
                    cor = "var(--text)" if n else "var(--text-3)"
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;"
                        f"font-size:0.82rem;color:{cor};padding:2px 0;'>"
                        f"<span>{classe}</span>"
                        f"<span style='font-family:JetBrains Mono,monospace;'>"
                        f"{n} · {pct:.0f}%</span></div>",
                        unsafe_allow_html=True)

    # =================================================================
    with tab_leitura:
        criticos = f1m["recall_por_classe"]["Crítico"]
        altos = f1m["recall_por_classe"]["Alto"]

        if len(acc["classes_previstas"]) == 1:
            st.warning(
                f"**A maior acurácia é ilusória.** O modelo otimizado por "
                f"acurácia prevê a mesma classe para todas as "
                f"{b['teste']} apólices de teste, atingindo exatamente o valor "
                f"da referência ({base:.3f}) sem distinguir nenhum caso. "
                f"É o exemplo clássico de por que acurácia isolada não "
                f"serve como critério em base desbalanceada.", icon="⚠️")

        if criticos == 0 and altos == 0:
            st.error(
                "**Nenhuma versão identificou um caso Alto ou Crítico.** "
                "São exatamente as classes que orientam decisão de "
                "subscrição. Dois algoritmos distintos chegaram ao mesmo "
                "resultado, o que indica limite de informação na base — não "
                "escolha inadequada de modelo.", icon="🚨")

        st.markdown("""
        #### O que isso significa para a plataforma

        O cálculo de risco em produção **não usa estes modelos**. Opera com
        composição determinística de fatores, cujos pesos são limiares
        justificados e auditáveis, e que produz separação verificável de
        sinistralidade entre as faixas.

        Os modelos estatísticos permanecem em avaliação. Passarão a compor o
        cálculo quando superarem a referência de forma consistente — condição
        que depende de ampliar a base histórica, não de trocar o algoritmo.

        #### Por que este resultado é reportado

        Seria possível publicar apenas a acurácia de """ +
        f"{acc['acuracia']:.3f}" + """ e omitir que ela corresponde a prever
        sempre a mesma classe. A métrica está correta; a conclusão que ela
        sugere, não. Publicar o resultado completo é o que permite confiar
        nos demais números da plataforma.
        """)

        st.markdown("#### Metodologia")
        st.markdown(f"""
        - Divisão 70/30 estratificada, semente fixa &mdash; {b['treino']}
          registros de treino, {b['teste']} de teste
        - Padronização ajustada apenas no treino
        - `VALOR_INDENIZADO_BRL` removido das variáveis de entrada: é o valor
          pago no sinistro, só existe **depois** do evento
        - Busca de hiperparâmetros com validação cruzada de 5 divisões
        - Duas otimizações independentes: acurácia e F1 macro
        """)


if __name__ == "__main__":
    render()
