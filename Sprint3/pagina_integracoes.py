"""
pagina_integracoes.py
=====================
Status das fontes de dados — o que está conectado e o que está pendente.

Serve a dois propósitos:
    · operacional — saber, antes de uma demonstração, se a telemetria está
      chegando e qual base está em uso;
    · registro — evidência do estado da integração em uma data, exportável.

Nenhuma tela do sistema depende desta: ela apenas lê o status consolidado
por core_integracao.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

import core_integracao as ci


def _cartao(i: ci.Integracao) -> None:
    st.markdown(f"""
    <div class="g-card" style="padding:1rem 1.25rem;margin-bottom:9px;">
        <div style="display:flex;justify-content:space-between;
              align-items:flex-start;gap:16px;">
            <div style="min-width:0;">
                <div style="font-weight:600;font-size:0.95rem;
                      color:var(--text);">{i.rotulo}</div>
                <div style="font-size:0.79rem;color:var(--text-2);
                      margin-top:4px;line-height:1.55;">{i.detalhe}</div>
                <div style="font-family:'JetBrains Mono',monospace;
                      font-size:0.68rem;color:var(--text-3);margin-top:6px;">
                    {i.origem}</div>
            </div>
            <span class="pill" style="border-color:{i.cor}55;flex:none;">
                <span class="dot" style="background:{i.cor};
                      box-shadow:0 0 8px {i.cor};"></span>
                <span style="color:{i.cor};">{i.situacao}</span>
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render() -> None:
    from core_app import check_permissao, gerar_trilha_auditoria, _contrato_box, _header

    if not check_permissao("view_dashboard"):
        return
    _contrato_box("integracoes", [])
    _header("Fontes de Dados",
            "Origem de cada informação exibida na plataforma")
    gerar_trilha_auditoria("ACESSO_INTEGRACOES", "pagina=fontes_de_dados")

    todas = ci.status_integracoes()
    conectadas = sum(1 for i in todas if i.conectado)
    padrao = sum(1 for i in todas if not i.conectado and i.operante)
    pendentes = len(todas) - conectadas - padrao

    c1, c2, c3 = st.columns(3)
    for col, val, lab, cor in [
        (c1, conectadas, "Conectadas", "var(--verde)"),
        (c2, padrao, "Em modo padrão", "var(--amarelo)"),
        (c3, pendentes, "Pendentes", "var(--text-3)"),
    ]:
        col.markdown(f"""
        <div class="g-card" style="padding:1rem 1.15rem;">
            <div class="g-num" style="color:{cor};">{val}</div>
            <div class="g-label">{lab}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)

    st.markdown(
        "**Conectada** — artefato externo carregado e validado. "
        "**Modo padrão** — o artefato não está presente, mas há caminho "
        "alternativo em operação; o sistema funciona normalmente. "
        "**Pendente** — a funcionalidade depende do artefato e está inativa.")

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    for i in todas:
        _cartao(i)

    # ---------- Telemetria: detalhe quando conectada ----------
    dados, i_tel = ci.telemetria_ao_vivo()
    if i_tel.conectado and dados.get("equipamentos"):
        st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
        st.markdown("#### Equipamentos transmitindo")
        eq = pd.DataFrame(dados["equipamentos"])
        st.dataframe(eq, use_container_width=True, hide_index=True)

    # ---------- Onde colocar cada artefato ----------
    st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
    with st.expander("Onde colocar cada artefato"):
        st.markdown("""
        Os arquivos abaixo são lidos automaticamente quando presentes.
        Nenhuma alteração de código é necessária — basta colocar o arquivo
        no caminho indicado e recarregar a página.

        | Artefato | Caminho | Efeito |
        |---|---|---|
        | Base de apólices ampliada | `data/susep_real.xlsx` | Substitui a base padrão em toda a plataforma |
        | Modelo de risco treinado | `data/modelo_xgboost.pkl` | Passa a compor o score, ao lado do cálculo determinístico |
        | Modelo de série temporal | `data/modelo_lstm.h5` | Habilita detecção de anomalia na série do equipamento |
        | Cadastro de frota | `data/frota_real.csv` | Substitui identificadores sequenciais pelos códigos de operação |
        | Telemetria acumulada | `data/telemetria_esp32.csv` | Alimenta gráficos quando o serviço ao vivo está fora |

        O serviço de telemetria ao vivo é configurado pela variável de
        ambiente `SOMPO_API_BASE`. Endereço atual:
        """)
        st.code(ci.API_BASE, language=None)
        st.caption(
            "Requisitos de formato: a base de apólices precisa conter as "
            "colunas UF, RAMO_SUSEP, IDADE_MAQUINA_ANOS, "
            "ACESSORIOS_SEGURADOS, PREMIO_LIQUIDO_BRL e "
            "VALOR_INDENIZADO_BRL. O modelo precisa expor `predict_proba`. "
            "O cadastro de frota precisa da coluna `equip_id`. Arquivos "
            "fora desse formato são recusados na carga, com o motivo "
            "descrito no cartão correspondente.")

    # ---------- Registro do estado ----------
    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    registro = pd.DataFrame([{
        "fonte": i.rotulo, "situacao": i.situacao,
        "origem": i.origem, "detalhe": i.detalhe,
    } for i in todas])
    st.download_button(
        "Exportar status em CSV",
        registro.to_csv(index=False).encode("utf-8"),
        f"status_fontes_{datetime.now():%Y%m%d_%H%M}.csv",
        "text/csv", key="integ_dl")


if __name__ == "__main__":
    render()
