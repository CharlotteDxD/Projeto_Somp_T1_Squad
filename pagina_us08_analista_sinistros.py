"""
==============================================================================
SOMPO PREDICT v15 - US08: ANALISTA DE SINISTROS
==============================================================================
Owner:     Charles (placeholder funcional ate Guilherme entregar dados SUSEP)
Tipo:      Pagina do MENU - visao do Analista de Sinistros
Prioridade: ALTA

User Story:
    "Como Analista de Sinistros, quero auditar avisos de sinistro com
     deteccao de fraude e padroes anomalos para acelerar pagamento de
     casos legitimos e investigar casos suspeitos."

Acceptance Criteria atendidos:
    [x] Lista de sinistros pendentes com score de fraude
    [x] Deteccao de anomalias via Z-Score sobre base SUSEP
    [x] Cluster de casos similares historicos
    [x] Decisao auditada (aceitar / glosar / investigar)
    [x] Relatorio de glosas evitadas
==============================================================================
"""
import time
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

from core_data_adapter import carregar_dataset, status_dados


# ==========================================================================
# DATASETS MOCK
# ==========================================================================

def _historico_sinistros_mock() -> pd.DataFrame:
    """Base SUSEP historica - 200 sinistros pagos nos ultimos 12 meses."""
    np.random.seed(91)
    n = 200
    causas = ["Tombamento", "Atolamento", "Falha mecanica",
              "Colisao", "Furto", "Incendio", "Granizo"]
    regioes = ["Sul", "Centro-Oeste", "Sudeste", "Norte", "Nordeste"]
    tipos   = ["Colheitadeira", "Trator", "Pulverizador", "Plantadeira"]

    df = pd.DataFrame({
        "ID":              [f"SIN-{2024000 + i}" for i in range(n)],
        "Causa":           np.random.choice(causas, n),
        "Tipo":            np.random.choice(tipos, n),
        "Regiao":          np.random.choice(regioes, n),
        "Valor_Indenizado": np.random.lognormal(11, 0.7, n).astype(int),
        "Valor_Apolice":    np.random.lognormal(13, 0.5, n).astype(int),
        "Dias_Apos_Apolice": np.random.randint(30, 720, n),
        "Score_Risco_Pre":  np.round(np.random.uniform(15, 90, n), 1),
        "Status":           np.random.choice(["Pago", "Glosado", "Investigado"],
                                             n, p=[0.85, 0.10, 0.05]),
    })
    return df


def _sinistros_pendentes_mock() -> pd.DataFrame:
    """Sinistros aguardando analise pelo analista."""
    np.random.seed(11)
    nomes = [
        "Joao Almeida", "Maria Carvalho", "Pedro Santos", "Ana Pereira",
        "Carlos Souza", "Luiza Costa", "Roberto Lima", "Patricia Rocha",
        "Marcos Silva", "Beatriz Mendes", "Fernando Dias", "Camila Reis",
    ]
    causas = ["Tombamento", "Atolamento", "Falha mecanica",
              "Colisao", "Furto", "Incendio", "Granizo"]

    pendentes = []
    for i, nome in enumerate(nomes):
        causa = np.random.choice(causas)
        valor_indenizacao = np.random.randint(80_000, 1_500_000)
        valor_apolice     = valor_indenizacao * np.random.uniform(1.2, 4.0)
        dias_apolice      = np.random.randint(15, 600)
        # Score de fraude: combinacao de fatores suspeitos
        razao_indeniz = valor_indenizacao / valor_apolice
        proximidade   = max(0, (60 - dias_apolice) / 60)
        score_fraude  = round(min(
            razao_indeniz * 50 + proximidade * 40 + np.random.uniform(0, 20), 100
        ), 1)

        pendentes.append({
            "ID":               f"AVIS-{2026100 + i}",
            "Cliente":          nome,
            "Causa_Declarada":  causa,
            "Valor_Solicitado": valor_indenizacao,
            "Valor_Apolice":    int(valor_apolice),
            "Dias_Apos_Apolice": dias_apolice,
            "Tem_Telemetria":   np.random.choice([True, False], p=[0.7, 0.3]),
            "Tem_Boletim":      np.random.choice([True, False], p=[0.85, 0.15]),
            "Tem_Foto":         np.random.choice([True, False], p=[0.9, 0.1]),
            "Score_Fraude":     score_fraude,
            "Dias_Aguardando":  np.random.randint(2, 25),
        })
    return pd.DataFrame(pendentes)


def _z_score_anomalias(df: pd.DataFrame, coluna: str, threshold: float = 2.0):
    """Detecta anomalias via Z-Score em uma coluna numerica."""
    mu, sigma = df[coluna].mean(), df[coluna].std()
    z = ((df[coluna] - mu) / sigma).round(3)
    df = df.copy()
    df[f"Z_{coluna}"] = z
    df[f"Anomalia_{coluna}"] = z.abs() > threshold
    return df


def _categoria_fraude(score: float) -> tuple:
    if score >= 70:
        return ("ALTO_RISCO_FRAUDE", "#FF4D6A",
                "Padrao suspeito - investigar antes do pagamento")
    elif score >= 45:
        return ("ATENCAO", "#F5A623",
                "Verificar documentacao adicional")
    elif score >= 25:
        return ("NORMAL_REVISAR", "#FFD93D",
                "Revisao padrao - prosseguir")
    else:
        return ("PAGAMENTO_RAPIDO", "#22D48A",
                "Padrao normal - elegivel para pagamento expresso")


# ==========================================================================
# RENDER PRINCIPAL
# ==========================================================================

def render():
    from app import check_permissao, gerar_trilha_auditoria, _header, _contrato_box

    if not check_permissao("view_dashboard"):
        return

    _contrato_box(
        "pagina_us08_analista_sinistros",
        ["ACESSO_US08_SINISTROS", "ANALISE_SINISTRO",
         "DECISAO_PAGAMENTO", "DETECCAO_ANOMALIA_FRAUDE"]
    )
    _header(
        "Analista de Sinistros",
        "Guilherme",
        "US08 · Sinistros · Z-Score · Deteccao de Fraude · Auditoria SHA-256"
    )
    gerar_trilha_auditoria("ACESSO_US08_SINISTROS", "pagina=us08_analista_sinistros")

    # Status do arquivo SUSEP real
    status_dados("susep_real",
                 label="Base SUSEP rural com sinistros historicos (aguardando)")

    # Carrega datasets (real ou mock)
    df_hist, _    = carregar_dataset("data/susep_real.xlsx",
                                     _historico_sinistros_mock)
    df_pend, _    = carregar_dataset("data/sinistros_pendentes.csv",
                                     _sinistros_pendentes_mock)

    # ── KPIs ──
    n_pend       = len(df_pend)
    n_alto_risco = sum(1 for _, r in df_pend.iterrows()
                       if _categoria_fraude(r["Score_Fraude"])[0] == "ALTO_RISCO_FRAUDE")
    valor_pend   = df_pend["Valor_Solicitado"].sum()
    glosa_estim  = sum(r["Valor_Solicitado"] for _, r in df_pend.iterrows()
                       if _categoria_fraude(r["Score_Fraude"])[0] in
                       ("ALTO_RISCO_FRAUDE", "ATENCAO")) * 0.4

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Avisos Pendentes",   n_pend)
    c2.metric("Alto Risco Fraude",  n_alto_risco, delta_color="inverse",
              delta=f"+{n_alto_risco}" if n_alto_risco else "0")
    c3.metric("Valor Pendente",     f"R$ {valor_pend/1e6:.2f}M")
    c4.metric("Glosa Estimada",     f"R$ {glosa_estim/1e3:.0f}K",
              delta=f"-{glosa_estim/valor_pend*100:.0f}%",
              delta_color="off")
    c5.metric("Historico SUSEP",    f"{len(df_hist)} casos")

    # ── TABS ──
    tab1, tab2, tab3, tab4 = st.tabs([
        "Fila de Avisos",
        "Analise Individual",
        "Anomalias Z-Score (SUSEP)",
        "Padroes Historicos",
    ])

    # ── TAB 1: FILA DE AVISOS ───────────────────────────────────────────
    with tab1:
        st.markdown("##### Avisos de sinistro aguardando analise - ordenados por urgencia")
        st.caption(
            "Score alto + dias aguardando = topo. "
            "Sistema marca casos suspeitos com base em padroes historicos da SUSEP."
        )

        df_fila = df_pend.copy()
        df_fila["urgencia"] = (
            df_fila["Score_Fraude"] * 0.4 + df_fila["Dias_Aguardando"] * 4
        )
        df_fila = df_fila.sort_values("urgencia", ascending=False)

        for _, row in df_fila.head(10).iterrows():
            cat, cor, msg = _categoria_fraude(row["Score_Fraude"])
            docs = []
            if row["Tem_Telemetria"]: docs.append("telemetria")
            if row["Tem_Boletim"]:    docs.append("boletim")
            if row["Tem_Foto"]:       docs.append("foto")
            docs_str = ", ".join(docs) if docs else "sem documentos!"
            cor_docs = "#22D48A" if len(docs) >= 2 else "#FF4D6A"

            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid {cor}33;
                        border-left:3px solid {cor};border-radius:10px;
                        padding:14px 18px;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;
                            align-items:flex-start;gap:1rem;">
                    <div style="flex:1;">
                        <div style="display:flex;gap:10px;align-items:center;
                                    margin-bottom:6px;flex-wrap:wrap;">
                            <span style="font-size:0.65rem;color:{cor};
                                         background:{cor}20;padding:3px 10px;
                                         border-radius:5px;font-weight:700;">
                                {cat.replace('_', ' ')}</span>
                            <span style="font-weight:700;color:#EEF0F8;
                                         font-size:0.95rem;">{row['ID']}</span>
                            <span style="font-size:0.78rem;color:#8B8FA8;">
                                {row['Cliente']}</span>
                        </div>
                        <div style="font-size:0.78rem;color:#8B8FA8;
                                    line-height:1.6;">
                            Causa: <strong style="color:#EEF0F8;">
                                {row['Causa_Declarada']}</strong> ·
                            R$ {row['Valor_Solicitado']/1e3:.0f}K solicitados ·
                            apolice de R$ {row['Valor_Apolice']/1e3:.0f}K ·
                            sinistro a {row['Dias_Apos_Apolice']}d da contratacao<br>
                            <span style="color:{cor_docs};">
                                Documentos: {docs_str}</span> ·
                            <span style="color:#4A4D62;">
                                aguardando ha {row['Dias_Aguardando']}d</span>
                        </div>
                        <div style="font-size:0.75rem;color:{cor};margin-top:6px;
                                    line-height:1.5;">{msg}</div>
                    </div>
                    <div style="text-align:right;min-width:120px;">
                        <div style="font-size:1.6rem;font-weight:800;color:{cor};
                                    line-height:1;">{row['Score_Fraude']:.0f}</div>
                        <div style="font-size:0.65rem;color:#8B8FA8;">
                            SCORE FRAUDE</div>
                        <div style="margin-top:8px;padding-top:8px;
                                    border-top:1px solid rgba(255,255,255,0.07);
                                    font-size:0.7rem;color:#8B8FA8;">
                            Razao indeniz/apolice:<br>
                            <strong style="color:#EEF0F8;">
                                {row['Valor_Solicitado']/row['Valor_Apolice']*100:.0f}%
                            </strong>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── TAB 2: ANALISE INDIVIDUAL ───────────────────────────────────────
    with tab2:
        st.markdown("##### Selecione um aviso para analise completa")

        avis_id = st.selectbox(
            "Aviso",
            df_pend["ID"].tolist(),
            format_func=lambda x: f"{x} - {df_pend[df_pend['ID']==x]['Cliente'].iloc[0]}",
            key="us08_avis",
        )

        avis = df_pend[df_pend["ID"] == avis_id].iloc[0]
        cat, cor, msg = _categoria_fraude(avis["Score_Fraude"])

        col_a, col_b = st.columns([1, 2])

        with col_a:
            st.markdown(f"""
            <div style="background:#131520;border:1px solid {cor}44;
                        border-radius:14px;padding:1.5rem;text-align:center;">
                <div style="font-size:0.7rem;color:#8B8FA8;text-transform:uppercase;
                            letter-spacing:0.1em;margin-bottom:8px;">
                    Score de Fraude</div>
                <div style="font-size:3.5rem;font-weight:800;color:{cor};
                            line-height:1;">
                    {avis['Score_Fraude']:.0f}</div>
                <div style="font-size:0.85rem;color:#8B8FA8;margin-top:4px;">
                    / 100</div>
                <div style="margin-top:14px;padding:6px 14px;background:{cor}18;
                            border:1px solid {cor};border-radius:6px;
                            display:inline-block;color:{cor};
                            font-weight:700;font-size:0.8rem;">
                    {cat.replace('_', ' ')}</div>
            </div>
            """, unsafe_allow_html=True)

        with col_b:
            st.markdown("##### Indicadores de risco")

            # Indicador 1: razao indenizacao/apolice
            razao = avis["Valor_Solicitado"] / avis["Valor_Apolice"]
            cor_r = "#FF4D6A" if razao > 0.7 else "#F5A623" if razao > 0.4 else "#22D48A"
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid {cor_r}33;
                        border-left:3px solid {cor_r};border-radius:8px;
                        padding:10px 14px;margin-bottom:6px;">
                <div style="display:flex;justify-content:space-between;
                            align-items:center;">
                    <span style="font-size:0.85rem;color:#EEF0F8;">
                        Indenizacao / Valor da Apolice</span>
                    <span style="font-weight:700;color:{cor_r};">
                        {razao*100:.0f}%</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Indicador 2: dias apos contratacao
            dias = avis["Dias_Apos_Apolice"]
            cor_d = ("#FF4D6A" if dias < 60 else
                     "#F5A623" if dias < 180 else "#22D48A")
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid {cor_d}33;
                        border-left:3px solid {cor_d};border-radius:8px;
                        padding:10px 14px;margin-bottom:6px;">
                <div style="display:flex;justify-content:space-between;
                            align-items:center;">
                    <span style="font-size:0.85rem;color:#EEF0F8;">
                        Dias entre apolice e sinistro</span>
                    <span style="font-weight:700;color:{cor_d};">
                        {dias} dias</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Indicador 3: documentacao
            docs_n = sum([avis["Tem_Telemetria"], avis["Tem_Boletim"], avis["Tem_Foto"]])
            cor_doc = "#22D48A" if docs_n == 3 else "#F5A623" if docs_n >= 2 else "#FF4D6A"
            st.markdown(f"""
            <div style="background:#0D0F18;border:1px solid {cor_doc}33;
                        border-left:3px solid {cor_doc};border-radius:8px;
                        padding:10px 14px;margin-bottom:6px;">
                <div style="display:flex;justify-content:space-between;
                            align-items:center;">
                    <span style="font-size:0.85rem;color:#EEF0F8;">
                        Documentacao apresentada</span>
                    <span style="font-weight:700;color:{cor_doc};">
                        {docs_n}/3</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Casos similares na base historica
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Casos similares na base SUSEP historica")
        similares = df_hist[df_hist["Causa"] == avis["Causa_Declarada"]].head(5)
        if len(similares) > 0:
            sim_view = similares[["ID", "Causa", "Tipo", "Regiao",
                                  "Valor_Indenizado", "Status"]].copy()
            sim_view["Valor_Indenizado"] = sim_view["Valor_Indenizado"].apply(
                lambda x: f"R$ {x/1e3:.0f}K"
            )
            st.dataframe(sim_view, use_container_width=True, hide_index=True)

        # Painel de decisao
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Decisao do analista")

        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            if st.button("Aprovar pagamento", type="primary",
                         use_container_width=True,
                         key=f"us08_pag_{avis_id}"):
                gerar_trilha_auditoria(
                    "DECISAO_PAGAMENTO",
                    f"avis={avis_id} acao=APROVAR valor={avis['Valor_Solicitado']:.0f}"
                )
                st.success(f"Pagamento de {avis_id} aprovado e auditado.")

        with col_d2:
            if st.button("Investigar", use_container_width=True,
                         key=f"us08_inv_{avis_id}"):
                gerar_trilha_auditoria(
                    "DECISAO_PAGAMENTO",
                    f"avis={avis_id} acao=INVESTIGAR score_fraude={avis['Score_Fraude']}"
                )
                st.info(f"Caso {avis_id} encaminhado para investigacao.")

        with col_d3:
            if st.button("Glosar", use_container_width=True,
                         key=f"us08_glo_{avis_id}"):
                gerar_trilha_auditoria(
                    "DECISAO_PAGAMENTO",
                    f"avis={avis_id} acao=GLOSAR motivo=indicios_fraude"
                )
                st.error(f"Aviso {avis_id} glosado e auditado.")

    # ── TAB 3: ANOMALIAS Z-SCORE ────────────────────────────────────────
    with tab3:
        st.markdown("##### Deteccao de outliers na base SUSEP via Z-Score")
        st.caption(
            "Z-Score > 2 indica caso atipico. Sao candidatos a auditoria de fraude. "
            "Algoritmo: (valor - media) / desvio_padrao"
        )

        threshold = st.slider(
            "Threshold Z-Score", 1.5, 3.5, 2.0, step=0.1, key="us08_thr"
        )

        df_anom = _z_score_anomalias(df_hist, "Valor_Indenizado", threshold)
        anomalias = df_anom[df_anom["Anomalia_Valor_Indenizado"]]

        col1, col2, col3 = st.columns(3)
        col1.metric("Total de casos",  len(df_anom))
        col2.metric("Anomalias",       len(anomalias),
                    delta=f"{len(anomalias)/len(df_anom)*100:.1f}%",
                    delta_color="inverse")
        col3.metric("Threshold |Z| >", threshold)

        if PLOTLY_OK:
            df_plot = df_anom.copy()
            df_plot["Cor"] = df_plot["Anomalia_Valor_Indenizado"].map({
                True: "Anomalia", False: "Normal"
            })
            fig = px.scatter(
                df_plot, x="Dias_Apos_Apolice", y="Valor_Indenizado",
                color="Cor",
                hover_data=["ID", "Causa", "Tipo"],
                title=f"Distribuicao de sinistros (anomalias |Z|>{threshold})",
                template="plotly_dark",
                color_discrete_map={"Anomalia": "#FF4D6A", "Normal": "#5B7FFF"},
            )
            fig.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
                              font=dict(color="#EEF0F8"), height=400)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("##### Anomalias detectadas")
        anom_view = anomalias[["ID", "Causa", "Tipo", "Regiao",
                               "Valor_Indenizado", "Z_Valor_Indenizado",
                               "Status"]].copy()
        anom_view["Valor_Indenizado"] = anom_view["Valor_Indenizado"].apply(
            lambda x: f"R$ {x/1e3:.0f}K"
        )
        st.dataframe(anom_view, use_container_width=True, hide_index=True)

        if st.button("Registrar deteccao", key="us08_anom_log"):
            gerar_trilha_auditoria(
                "DETECCAO_ANOMALIA_FRAUDE",
                f"threshold={threshold} anomalias={len(anomalias)} "
                f"total={len(df_anom)} algoritmo=ZScore"
            )
            st.success("Deteccao registrada na trilha de auditoria.")

    # ── TAB 4: PADROES HISTORICOS ───────────────────────────────────────
    with tab4:
        st.markdown("##### Distribuicao de sinistros na base SUSEP")

        if PLOTLY_OK:
            col_v1, col_v2 = st.columns(2)

            with col_v1:
                causa_counts = df_hist["Causa"].value_counts().reset_index()
                causa_counts.columns = ["Causa", "Quantidade"]
                fig1 = px.bar(causa_counts, x="Causa", y="Quantidade",
                              title="Sinistros por causa",
                              template="plotly_dark",
                              color="Quantidade",
                              color_continuous_scale="Reds")
                fig1.update_layout(plot_bgcolor="#0D0F18",
                                   paper_bgcolor="#0D0F18",
                                   font=dict(color="#EEF0F8"), height=320)
                st.plotly_chart(fig1, use_container_width=True)

            with col_v2:
                status_counts = df_hist["Status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Quantidade"]
                fig2 = px.pie(status_counts, names="Status", values="Quantidade",
                              title="Distribuicao de status",
                              template="plotly_dark",
                              color_discrete_sequence=["#22D48A", "#F5A623", "#FF4D6A"])
                fig2.update_layout(plot_bgcolor="#0D0F18",
                                   paper_bgcolor="#0D0F18",
                                   font=dict(color="#EEF0F8"), height=320)
                st.plotly_chart(fig2, use_container_width=True)

            # Heatmap regiao x causa
            cross = df_hist.groupby(["Regiao", "Causa"]).size().reset_index(name="N")
            cross_p = cross.pivot(index="Regiao", columns="Causa",
                                  values="N").fillna(0)
            fig3 = px.imshow(
                cross_p, text_auto=True, aspect="auto",
                title="Frequencia de sinistros: Regiao x Causa",
                color_continuous_scale="Blues",
                template="plotly_dark",
            )
            fig3.update_layout(plot_bgcolor="#0D0F18", paper_bgcolor="#0D0F18",
                               font=dict(color="#EEF0F8"), height=320)
            st.plotly_chart(fig3, use_container_width=True)

    # Footer
    st.markdown("---")
    st.markdown(f"""
    <div style="background:rgba(245,166,35,0.04);
                border:1px solid rgba(245,166,35,0.2);
                border-left:3px solid #F5A623;border-radius:10px;
                padding:12px 18px;font-size:0.78rem;color:#8B8FA8;line-height:1.7;">
        <strong style="color:#EEF0F8;">Status de integracao US08:</strong><br>
        <span style="color:#22D48A;">x</span> Pagina criada e funcional ·
        <span style="color:#22D48A;">x</span> Z-Score sobre base SUSEP ·
        <span style="color:#22D48A;">x</span> Decisao auditada ·
        <span style="color:#22D48A;">x</span> Cluster de casos similares ·
        <span style="color:#F5A623;">~</span> Aguardando base SUSEP real (Guilherme)
    </div>
    """, unsafe_allow_html=True)
