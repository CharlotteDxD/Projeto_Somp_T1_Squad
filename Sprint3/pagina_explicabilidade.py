"""
pagina_explicabilidade.py
=========================
Explicabilidade — o que pesa no cálculo de risco e o que pesou no modelo
experimental. São duas coisas diferentes, e a distinção é o ponto da tela.

    Camadas do score em produção  ->  o que determina o risco hoje
    Fatores do modelo estatístico ->  o que aquele modelo usou para decidir

Apresentar o segundo como se fosse o primeiro seria o erro mais fácil de
cometer aqui: o modelo experimental não identifica as classes de maior
gravidade, então os fatores que ele prioriza não descrevem causa de risco.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

import core_fusao as cf

ARQUIVO_METRICAS = Path("metricas_modelo.json")

_NOMES = {
    "IDADE_MAQUINA_ANOS":   "Idade da máquina",
    "ACESSORIOS_SEGURADOS": "Acessórios segurados",
    "PREMIO_LIQUIDO_BRL":   "Prêmio líquido",
    "INTENSIDADE_SINISTRO": "Intensidade do sinistro",
    "UF":                   "Estado",
    "RAMO_SUSEP":           "Ramo do seguro",
}


def _rotular(feature: str) -> str:
    if feature in _NOMES:
        return _NOMES[feature]
    if feature.startswith("UF_"):
        return f"Estado · {feature[3:]}"
    if feature.startswith("RAMO_SUSEP_"):
        ramo = feature[len("RAMO_SUSEP_"):]
        return f"Ramo · {ramo.split(' - ')[-1] if ' - ' in ramo else ramo}"
    return feature


@st.cache_data(ttl=300)
def _metricas():
    if not ARQUIVO_METRICAS.exists():
        return None
    try:
        return json.loads(ARQUIVO_METRICAS.read_text(encoding="utf-8"))
    except Exception:
        return None


def render() -> None:
    from core_app import check_permissao, gerar_trilha_auditoria, _contrato_box, _header

    if not check_permissao("view_dashboard"):
        return
    _contrato_box("explicabilidade", [])
    _header("Explicabilidade",
            "O que determina o score e como cada fator é ponderado")
    gerar_trilha_auditoria("ACESSO_EXPLICABILIDADE", "pagina=explicabilidade")

    tab_prod, tab_exp = st.tabs(
        ["Cálculo em produção", "Modelo experimental"])

    # =================================================================
    with tab_prod:
        st.markdown(
            "O score em uso combina duas camadas. Cada fator tem peso fixo e "
            "justificativa registrada &mdash; o cálculo é reproduzível e "
            "auditável linha a linha.")

        df_base = None
        caminho = Path("base_sompo_limpa.csv")
        if caminho.exists():
            df_base = pd.read_csv(caminho)
            cf.calibrar_faixas(df_base)

        c1, c2, c3 = st.columns(3)
        c1.metric("Operação normal", f"abaixo de {cf.FAIXAS[0][1]:.0f}")
        c2.metric("Atenção", f"{cf.FAIXAS[1][0]:.0f} a {cf.FAIXAS[1][1]:.0f}")
        c3.metric("Risco elevado", f"acima de {cf.FAIXAS[2][0]:.0f}")
        st.caption(
            "Cortes calibrados nos percentis 60 e 90 da carteira, "
            "recalculados a cada carga da base.")

        pesos = cf.descrever_pesos()

        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        st.markdown("##### Camada 1 · perfil da apólice")
        st.caption("Histórico do equipamento e da cobertura. Muda de mês em mês.")
        st.dataframe(
            pesos.query("camada == 'perfil'")[["fator", "peso", "justificativa"]],
            column_config={
                "fator": st.column_config.TextColumn("Fator"),
                "peso": st.column_config.ProgressColumn(
                    "Peso", format="%.2f", min_value=0.0, max_value=1.0),
                "justificativa": st.column_config.TextColumn("Justificativa"),
            },
            hide_index=True, use_container_width=True)

        st.markdown("##### Camada 2 · exposição medida pelo sensor")
        st.caption("Condição do momento. Muda a cada segundo.")
        st.dataframe(
            pesos.query("camada == 'telemetria'")[["fator", "peso", "justificativa"]],
            column_config={
                "fator": st.column_config.TextColumn("Fator"),
                "peso": st.column_config.ProgressColumn(
                    "Peso", format="%.2f", min_value=0.0, max_value=1.0),
                "justificativa": st.column_config.TextColumn("Justificativa"),
            },
            hide_index=True, use_container_width=True)

        st.info(
            "Os pesos da Camada 2 são limiares de especialista, não "
            "parâmetros aprendidos: a base histórica não contém leitura de "
            "sensor, então não existe par (telemetria, sinistro) para "
            "treinar. Aprendê-los depende de acumular telemetria rotulada.",
            icon="📌")

        # ---- separação observada, a validação que existe ----
        if df_base is not None:
            st.markdown("##### Separação observada")
            st.caption(
                "O cálculo não é aprendido, mas é verificável: as faixas "
                "separam sinistralidade na carteira analisada.")
            scored = cf.calcular_score_base(df_base)
            faixa = scored["score_base"].apply(lambda s: cf.classificar(s)[0])
            df_base = df_base.assign(_faixa=faixa.values)
            linhas = []
            for nome, chave in [("Operação normal", "verde"),
                                ("Atenção", "amarelo"),
                                ("Risco elevado", "vermelho")]:
                sub = df_base[df_base._faixa == chave]
                if len(sub) == 0:
                    continue
                lr = (sub.VALOR_INDENIZADO_BRL.sum()
                      / sub.PREMIO_LIQUIDO_BRL.sum() * 100)
                linhas.append({"Faixa": nome, "Apólices": len(sub),
                               "Sinistralidade": round(lr, 1)})
            st.dataframe(
                pd.DataFrame(linhas),
                column_config={
                    "Sinistralidade": st.column_config.NumberColumn(
                        "Sinistralidade", format="%.1f%%"),
                },
                hide_index=True, use_container_width=True)

    # =================================================================
    with tab_exp:
        r = _metricas()
        if r is None:
            st.info(
                "Sem resultados de modelo experimental. Execute "
                "`python avaliar_modelo_rafael.py` para gerá-los.", icon="📊")
            return

        f1m = r["xgboost"]["f1_macro"]
        criticos = f1m["recall_por_classe"]["Crítico"]
        altos = f1m["recall_por_classe"]["Alto"]

        st.warning(
            "**Estes fatores descrevem o comportamento de um modelo em "
            "avaliação, não a causa do risco.** O modelo abaixo não "
            "identificou casos de gravidade Alta ou Crítica no conjunto de "
            "teste, então a ordem de importância que ele produz não deve "
            "ser lida como hierarquia de fatores de risco. O cálculo em "
            "produção está na aba anterior.", icon="⚠️")

        st.markdown(
            f"Modelo: **XGBoost otimizado por F1 macro** &mdash; acurácia "
            f"{f1m['acuracia']:.3f}, F1 macro {f1m['f1_macro']:.3f}, "
            f"contra referência de {r['baseline_ingenuo']:.3f}.")

        imp = pd.DataFrame(r["importancias"])
        imp["Fator"] = imp["feature"].apply(_rotular)
        st.markdown("##### Fatores utilizados pelo modelo")
        st.dataframe(
            imp[["Fator", "peso"]].rename(columns={"peso": "Importância"}),
            column_config={
                "Importância": st.column_config.ProgressColumn(
                    "Importância", format="%.3f",
                    min_value=0.0, max_value=float(imp["peso"].max() or 1.0)),
            },
            hide_index=True, use_container_width=True)

        st.markdown("##### Leitura")
        st.markdown("""
        As variáveis contínuas &mdash; prêmio, idade da máquina, acessórios
        &mdash; dominam a importância, enquanto as marcações de estado ficam
        em posições marginais.

        Isso é esperado tecnicamente: um algoritmo de boosting encontra mais
        pontos de corte úteis em uma variável contínua do que em uma marcação
        binária com poucas observações. **Não contradiz o padrão regional
        observado na análise da carteira** &mdash; que permanece válido como
        característica histórica dos dados &mdash; mas indica que, para este
        modelo específico, a região não foi o fator dominante.
        """)

        if criticos == 0 and altos == 0:
            st.error(
                "Recall de 0% nas classes Alta e Crítica. Enquanto isso não "
                "mudar, os fatores acima explicam apenas como o modelo separa "
                "as classes de menor gravidade &mdash; que não são as que "
                "orientam decisão de subscrição.", icon="🚨")


if __name__ == "__main__":
    render()
