"""
core_ranking.py
===============
Componente de Ranking de Risco · Reutilizavel · Sompo Predict · Sprint 3

Owner: Charles · Consumidores: US01 (Charles), US05 (Gustavo), US07 (Rafael)

MIGRACAO Sprint 3 (substitui a versao que importava core_scoring):

    core_scoring.py exigia 12 colunas que nao existem em base_sompo_limpa.csv.
    Como calcular_score_lote tratava coluna ausente como contribuicao 0.0, o
    ranking inteiro produzia score_risco=0 para a carteira, sem erro visivel.

    Este modulo agora consome core_fusao, que valida contrato de colunas em
    tempo de execucao (ContratoBaseError) em vez de degradar em silencio.

    Mudanca de vocabulario, mantida deliberadamente visivel em vez de
    escondida atras de alias:
        score_risco  -> score_base   (perfil da apolice, sem telemetria)
        score_l1/l2  -> nao existem mais (motor nao e mais hibrido L1+L2)
        peso_l1      -> parametro removido (nao ha mais dois modelos a pesar)

    Quando telemetria de um equipamento estiver disponivel (dict opcional
    `telemetria_por_equip`), o ranking mostra score_final (perfil + telemetria)
    em vez de score_base. Sem telemetria, os dois coincidem.

Objetivo:
    Centralizar a apresentacao de "ranking de risco da frota" em UM
    componente que qualquer pagina Streamlit possa importar.

Dependencias:
    - core_fusao (motor de score canonico, substitui core_scoring)
    - core_audit (trilha LGPD opcional)
"""
from __future__ import annotations

from typing import Callable, Optional

import pandas as pd
import streamlit as st

import core_fusao as cf

try:
    from core_audit import gerar_trilha_auditoria
except ImportError:
    def gerar_trilha_auditoria(*_a, **_kw):  # fallback no-op
        return None


# =========================================================================
# 1. FORMATADORES PUROS · usados via .apply/lambda
# =========================================================================
_EMOJI_FAIXA = {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴"}


def _fmt_faixa_visual(faixa: str) -> str:
    return f"{_EMOJI_FAIXA.get(faixa, '⚪')} {faixa.capitalize()}"


def _fmt_score(score: float) -> str:
    return f"{score:.1f} / 100"


def _fmt_brl(valor: float) -> str:
    if pd.isna(valor):
        return "—"
    return f"R$ {valor:,.0f}".replace(",", ".")


def _fmt_recomendacao_curta(faixa: str) -> str:
    return {
        "verde":    "Operacao normal",
        "amarelo":  "Reduzir velocidade",
        "vermelho": "Parar e inspecionar",
    }.get(faixa, "Revisar manualmente")


# =========================================================================
# 2. PREPARACAO DO DATAFRAME PARA EXIBICAO
# =========================================================================
def preparar_para_exibicao(
    df_scored: pd.DataFrame,
    coluna_id: str = "equip_id",
    top_n: Optional[int] = None,
    apenas_faixas: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Recebe o output de core_fusao (calcular_score_base ou calcular_lote) e
    transforma em DataFrame pronto pra apresentar.

    Aceita tanto 'score_final' (com telemetria) quanto 'score_base' (sem).
    Usa o que estiver disponivel, preferindo score_final.
    """
    col_score = "score_final" if "score_final" in df_scored.columns else "score_base"
    if col_score not in df_scored.columns:
        raise ValueError(
            "DataFrame precisa ter 'score_base' ou 'score_final' — chame "
            "core_fusao.calcular_score_base() ou calcular_lote() antes."
        )

    df = df_scored.copy()
    if "faixa_risco" not in df.columns:
        df["faixa_risco"] = df[col_score].apply(lambda s: cf.classificar(s)[0])

    if apenas_faixas:
        df = df[df["faixa_risco"].isin(apenas_faixas)]

    df = df.sort_values(col_score, ascending=False, kind="mergesort"
                        ).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)

    df["_col_score"] = col_score       # lembra qual coluna virou 'score exibido'
    df["faixa_visual"] = df["faixa_risco"].apply(_fmt_faixa_visual)
    df["acao"] = df["faixa_risco"].apply(_fmt_recomendacao_curta)
    df["score_fmt"] = df[col_score].apply(_fmt_score)

    if "valor_segurado_brl" in df.columns:
        df["valor_segurado_fmt"] = df["valor_segurado_brl"].apply(_fmt_brl)

    if top_n is not None and top_n > 0:
        df = df.head(top_n)

    return df


def top_n_risco(
    df_scored: pd.DataFrame,
    n: int = 10,
    coluna_id: str = "equip_id",
) -> pd.DataFrame:
    """Versao headless do ranking — API /score?top=10, Lambda, exportacao PDF."""
    col_score = "score_final" if "score_final" in df_scored.columns else "score_base"
    cols_essenciais = [
        c for c in [coluna_id, "UF", "RAMO_SUSEP", "IDADE_MAQUINA_ANOS",
                    col_score, "faixa_risco"]
        if c in df_scored.columns
    ]
    return (
        df_scored.sort_values(col_score, ascending=False)
                 .head(n)
                 .reset_index(drop=True)[cols_essenciais]
    )


# =========================================================================
# 3. CACHE DO SCORE
# =========================================================================
@st.cache_data(show_spinner="Calculando score da carteira...", ttl=900)
def calcular_e_rankear(
    df_features: pd.DataFrame,
    telemetria_por_equip: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Pipeline completo: features SUSEP -> score de perfil (+ telemetria, se
    houver) -> df ordenado.

    `telemetria_por_equip` substitui o antigo `peso_l1`: nao ha mais dois
    modelos pra ponderar, ha perfil (sempre) e telemetria (quando existir).
    """
    if telemetria_por_equip:
        df_scored = cf.calcular_lote(df_features, telemetria_por_equip)
    else:
        df_scored = cf.calcular_score_base(df_features)
    return preparar_para_exibicao(df_scored)


# =========================================================================
# 4. RENDER STREAMLIT
# =========================================================================
def render_ranking(
    df_features: pd.DataFrame,
    titulo: str = "🏁 Ranking de Risco da Frota",
    coluna_id: str = "equip_id",
    telemetria_por_equip: Optional[dict] = None,
    altura_tabela: int = 420,
    mostrar_filtros: bool = True,
    mostrar_kpis: bool = True,
    key_prefix: str = "rank",
    callback_selecao: Optional[Callable[[str], None]] = None,
    log_evento: str = "RANKING_VISUALIZADO",
) -> Optional[str]:
    """
    Renderiza o ranking completo no Streamlit. Componente canonico
    chamado por US01, US05 e US07.

    Args:
        df_features:     df bruto (colunas de core_fusao.PESOS_PERFIL) OU
                         df ja com score_base/score_final. Detecta automatico.
        coluna_id:       coluna chave. 'equip_id' no contrato novo — se o
                         df nao tiver essa coluna, cai no indice.
        telemetria_por_equip: dict opcional {equip_id: {campo: valor}} vindo
                         de api_telemetria — quando presente, mostra
                         score_final em vez de score_base.
    """
    st.markdown(f"### {titulo}")

    if coluna_id not in df_features.columns:
        df_features = df_features.copy()
        df_features[coluna_id] = [f"COL-{i:03d}" for i in df_features.index]

    if "score_base" in df_features.columns or "score_final" in df_features.columns:
        df_scored = preparar_para_exibicao(df_features, coluna_id=coluna_id)
    else:
        df_scored = calcular_e_rankear(df_features, telemetria_por_equip)

    col_score = df_scored["_col_score"].iloc[0] if len(df_scored) else "score_base"
    modo_telemetria = col_score == "score_final"

    if mostrar_kpis:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Frota", len(df_scored))
        c2.metric("Score médio", f"{df_scored[col_score].mean():.1f}")
        c3.metric(
            "🔴 Críticos",
            int((df_scored["faixa_risco"] == "vermelho").sum()),
            help="Faixa calibrada nos percentis 60/90 da carteira",
        )
        c4.metric(
            "🟡 Atenção",
            int((df_scored["faixa_risco"] == "amarelo").sum()),
        )
        if not modo_telemetria:
            st.caption(
                "ℹ️ Mostrando **score de perfil** (sem telemetria em tempo "
                "real). Equipamentos com telemetria ativa mostram score "
                "combinado."
            )

    df_view = df_scored.copy()

    if mostrar_filtros:
        with st.expander("🎛️  Filtros", expanded=False):
            cf1, cf2, cf3 = st.columns(3)

            faixas_disponiveis = sorted(df_scored["faixa_risco"].unique().tolist())
            faixas_sel = cf1.multiselect(
                "Faixa de risco", faixas_disponiveis,
                default=faixas_disponiveis, key=f"{key_prefix}_faixas",
            )
            if faixas_sel:
                df_view = df_view[df_view["faixa_risco"].isin(faixas_sel)]

            if "RAMO_SUSEP" in df_scored.columns:
                tipos = sorted(df_scored["RAMO_SUSEP"].unique().tolist())
                tipos_sel = cf2.multiselect(
                    "Ramo SUSEP", tipos, default=tipos,
                    key=f"{key_prefix}_tipos",
                )
                if tipos_sel:
                    df_view = df_view[df_view["RAMO_SUSEP"].isin(tipos_sel)]

            if "UF" in df_scored.columns:
                ufs = sorted(df_scored["UF"].unique().tolist())
                ufs_sel = cf3.multiselect(
                    "UF", ufs, default=ufs, key=f"{key_prefix}_ufs",
                )
                if ufs_sel:
                    df_view = df_view[df_view["UF"].isin(ufs_sel)]

            df_view = df_view.sort_values(
                col_score, ascending=False, kind="mergesort"
            ).reset_index(drop=True)
            df_view["rank"] = df_view.index + 1

    colunas_exibir = ["rank", coluna_id]
    for c in ["RAMO_SUSEP", "UF"]:
        if c in df_view.columns:
            colunas_exibir.append(c)
    colunas_exibir += ["score_fmt", "faixa_visual", "acao"]

    config = {
        "rank": st.column_config.NumberColumn(
            "#", help="Posição no ranking", width="small", format="%d",
        ),
        coluna_id: st.column_config.TextColumn(
            "ID", help="Identificador do equipamento",
        ),
        "score_fmt": st.column_config.TextColumn(
            "Score", help="Score de perfil, combinado com telemetria quando disponível",
        ),
        "faixa_visual": st.column_config.TextColumn(
            "Faixa", help="Verde / Amarelo / Vermelho — cortes calibrados por percentil",
        ),
        "acao": st.column_config.TextColumn(
            "Ação recomendada", help="Diretriz operacional auto-gerada",
        ),
    }

    df_view_show = df_view[colunas_exibir + [col_score]].copy()
    config[col_score] = st.column_config.ProgressColumn(
        "Risco", help="Score 0-100",
        format="%.1f", min_value=0, max_value=100,
    )

    st.dataframe(
        df_view_show, column_config=config,
        hide_index=True, use_container_width=True,
        height=altura_tabela, key=f"{key_prefix}_table",
    )

    equip_selecionado: Optional[str] = None
    if len(df_view) > 0:
        col_sel, col_dl = st.columns([3, 1])

        equip_selecionado = col_sel.selectbox(
            "🔎 Selecionar equipamento para drill-down",
            options=df_view[coluna_id].tolist(),
            key=f"{key_prefix}_select",
            help="Escolha um equipamento para ver a explicação (US07)",
        )

        col_dl.download_button(
            "📥 CSV",
            data=df_view[colunas_exibir].to_csv(index=False).encode("utf-8"),
            file_name="ranking_risco_sompo.csv",
            mime="text/csv",
            key=f"{key_prefix}_dl",
            use_container_width=True,
        )

        if callback_selecao is not None and equip_selecionado:
            callback_selecao(equip_selecionado)

    gerar_trilha_auditoria(
        log_evento,
        f"linhas={len(df_view)} | top_score={df_view[col_score].iloc[0]:.1f}"
        if len(df_view) > 0 else "linhas=0",
    )

    return equip_selecionado


# =========================================================================
# 5. RENDER COMPACTO
# =========================================================================
def render_top5_compacto(
    df_features: pd.DataFrame,
    coluna_id: str = "equip_id",
    titulo: str = "🚨 Top 5 críticos",
) -> None:
    if "score_base" not in df_features.columns and "score_final" not in df_features.columns:
        df_scored = calcular_e_rankear(df_features)
    else:
        df_scored = preparar_para_exibicao(df_features, coluna_id=coluna_id)

    col_score = df_scored["_col_score"].iloc[0] if len(df_scored) else "score_base"
    top = top_n_risco(df_scored, n=5, coluna_id=coluna_id)

    st.markdown(f"##### {titulo}")
    for _, r in top.iterrows():
        emoji = _EMOJI_FAIXA.get(r["faixa_risco"], "⚪")
        st.markdown(f"{emoji} **{r[coluna_id]}** — score `{r[col_score]:.1f}`")


__all__ = [
    "render_ranking", "render_top5_compacto",
    "preparar_para_exibicao", "top_n_risco", "calcular_e_rankear",
]
