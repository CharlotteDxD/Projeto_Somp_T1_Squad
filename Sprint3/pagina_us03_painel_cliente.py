"""
==============================================================================
SOMPO PREDICT · Área do Cliente (US03)
==============================================================================
Owner: Charles

A tela que o produtor rural abre. Um farol grande, uma frase, o que fazer.
Nada de score decomposto, nada de nome de variável, nada de gráfico SHAP —
a explicação existe, mas traduzida para português de quem opera a máquina.

Sprint 3 — reconstruída:
    A versão anterior tinha `_calcular_score_cliente()`, com pesos próprios
    e cortes 30/60/80. Era a quarta implementação de score no projeto. Se a
    fórmula daqui divergir da fórmula da API, o farol desta tela e o farol
    físico do equipamento podem discordar na frente da Sompo.
    Agora chama core_fusao.fundir(), a mesma função que api_telemetria.py usa
    para responder ao ESP32.

    Também saiu a métrica "Sinistros potenciais evitados: 3" — não havia
    medição nenhuma por trás desse número.

INTEGRAÇÃO — o que muda quando os outros entregarem:
    Gustavo (nuvem no ar) → trocar SOMPO_API_BASE (variável de ambiente ou
        a constante API_BASE_PADRAO abaixo) pelo Elastic IP.
    Anthony (ESP32 gravado) → nada. Basta o EQUIP_ID do config.h bater com
        o equipamento selecionado aqui.
    A tela detecta sozinha se a API responde e troca de modo demonstração
    para ao vivo.
==============================================================================
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

import core_fusao as cf

# Trocar aqui, ou definir SOMPO_API_BASE no ambiente (não exige editar código)
API_BASE_PADRAO = "http://localhost:5000"
API_BASE = os.environ.get("SOMPO_API_BASE", API_BASE_PADRAO)
TIMEOUT_S = 2.0
CAMINHO_BASE = Path("base_sompo_limpa.csv")

_HEX = {"verde": "#3FCF8E", "amarelo": "#F5B23D", "vermelho": "#F2555A"}
_TITULO = {"verde": "Pode seguir", "amarelo": "Atenção redobrada",
           "vermelho": "Pare e avalie"}


@st.cache_data(ttl=3600, show_spinner=False)
def _perfis():
    """Score de perfil por equipamento, da base real. None se faltar arquivo."""
    if not CAMINHO_BASE.exists():
        return None
    df = pd.read_csv(CAMINHO_BASE)
    cf.calibrar_faixas(df)
    scored = cf.calcular_score_base(df)
    scored["equip_id"] = [f"COL-{i:03d}" for i in range(len(scored))]
    return scored


def _telemetria_ao_vivo(equip_id: str):
    """GET /telemetria/v1/ultimo/<equip_id>. None se a API não responder."""
    if not REQUESTS_OK:
        return None
    try:
        r = requests.get(f"{API_BASE}/telemetria/v1/ultimo/{equip_id}",
                         timeout=TIMEOUT_S)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _farol_grande(faixa: str) -> str:
    return f"""
    <div class="farol-xl">
        <i class="{'lit-r' if faixa == 'vermelho' else ''}"></i>
        <i class="{'lit-y' if faixa == 'amarelo' else ''}"></i>
        <i class="{'lit-g' if faixa == 'verde' else ''}"></i>
    </div>"""


def render() -> None:
    from core_app import (check_permissao_silenciosa, gerar_trilha_auditoria,
                      _contrato_box)

    # Aceita os dois caminhos: quem administra a carteira (view_dashboard) e
    # o proprio segurado (view_proprio_equipamento). Esta e a unica tela que
    # os dois publicos compartilham — e por isso ela nao mostra nada de
    # outro cliente: so o equipamento selecionado.
    if not (check_permissao_silenciosa("view_dashboard")
            or check_permissao_silenciosa("view_proprio_equipamento")):
        st.error("Acesso negado a esta tela.")
        return
    _contrato_box("pagina_us03", ["ACESSO_US03", "VISUALIZACAO_CLIENTE"])

    st.markdown("""
    <div style="padding:0.2rem 0 1.3rem;">
        <h1 style="margin:0;font-size:2.15rem;">Painel do Segurado</h1>
        <p style="color:var(--text-2);margin-top:0.6rem;font-size:0.95rem;
                  max-width:520px;line-height:1.6;">
            Condição operacional do equipamento segurado em tempo real. O
            sistema emite o alerta; a decisão de interromper permanece com o operador.
        </p>
    </div>
    """, unsafe_allow_html=True)

    perfis = _perfis()
    if perfis is None:
        st.error(
            "`base_sompo_limpa.csv` não está na pasta do projeto. "
            "Coloque o arquivo aqui para carregar os equipamentos.",
            icon="🚨")
        return

    col_eq, col_modo = st.columns([2, 1])
    equip_id = col_eq.selectbox("Equipamento", perfis.equip_id.tolist(),
                                key="us03_equip")
    ao_vivo = _telemetria_ao_vivo(equip_id)
    modo_demo = col_modo.toggle(
        "Modo demonstração", value=(ao_vivo is None), key="us03_demo",
        help="Desligue para tentar ler o sensor ao vivo novamente.")

    score_base = float(perfis.loc[perfis.equip_id == equip_id,
                                  "score_base"].iloc[0])

    # =====================================================================
    if ao_vivo is not None and not modo_demo:
        # ---------------- AO VIVO ----------------
        faixa = ao_vivo.get("faixa_estavel", "verde")
        score = ao_vivo.get("score_final", score_base)
        frases = ao_vivo.get("frases", [])
        recomendacao = ao_vivo.get("recomendacao", "")
        st.markdown(f"""
        <div class="pill" style="margin-bottom:1.2rem;border-color:#3FCF8E55;">
            <span class="dot" style="background:var(--verde);
                  box-shadow:0 0 9px var(--verde);"></span>
            <span style="color:var(--text-2);">Sensor ao vivo · última leitura
            {ao_vivo.get('ts_servidor','—')[11:19]}</span>
        </div>
        """, unsafe_allow_html=True)
        tel_mostrar = {
            "Inclinação": f"{ao_vivo.get('tel_inclinacao_g', 0):.0f}°",
            "Obstáculo": (f"{ao_vivo.get('tel_dist_obstaculo_cm', -1):.0f} cm"
                          if ao_vivo.get('tel_dist_obstaculo_cm', -1) >= 0
                          else "livre"),
            "Umidade": f"{ao_vivo.get('tel_umidade_pct', 0):.0f}%",
        }
    else:
        # ---------------- DEMONSTRAÇÃO ----------------
        st.markdown("""
        <div class="pill" style="margin-bottom:1.2rem;border-color:#F2555A55;">
            <span class="dot" style="background:var(--vermelho);
                  box-shadow:0 0 9px var(--vermelho);"></span>
            <span style="color:var(--text-2);">Modo demonstração · valores
            ajustados por você, não lidos de sensor</span>
        </div>
        """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        inclinacao = c1.slider("Inclinação do terreno (°)", 0.0, 30.0, 5.0, 0.5,
                               key="us03_inc")
        dist = c1.slider("Obstáculo à frente (cm)", 10.0, 400.0, 300.0, 5.0,
                         key="us03_dist")
        umidade = c2.slider("Umidade do solo (%)", 0.0, 100.0, 45.0, 1.0,
                            key="us03_umi")
        vibracao = c2.slider("Trepidação", 0.0, 3.0, 0.4, 0.1, key="us03_vib")

        r = cf.fundir(score_base, {
            "inclinacao_g": inclinacao, "dist_obstaculo_cm": dist,
            "vibracao_rms": vibracao, "umidade_pct": umidade,
            "temperatura_c": 28.0,
        })
        faixa, score = r.faixa, r.score_final
        frases, recomendacao = r.frases, r.recomendacao
        tel_mostrar = {
            "Inclinação": f"{inclinacao:.0f}°",
            "Obstáculo": f"{dist:.0f} cm" if dist < 390 else "livre",
            "Umidade": f"{umidade:.0f}%",
        }

    # =====================================================================
    # FAROL — o elemento central da tela
    # =====================================================================
    st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
    hexcor = _HEX[faixa]
    col_farol, col_msg = st.columns([1, 3])

    with col_farol:
        st.markdown(_farol_grande(faixa), unsafe_allow_html=True)

    with col_msg:
        st.markdown(f"""
        <div class="g-card lit" style="height:100%;display:flex;
             flex-direction:column;justify-content:center;padding:1.5rem 1.7rem;">
            <div style="font-family:'Manrope',sans-serif;font-size:2rem;
                  font-weight:800;color:{hexcor};letter-spacing:-0.03em;
                  line-height:1.1;">{_TITULO[faixa]}</div>
            <div style="font-size:1rem;color:var(--text);margin-top:0.7rem;
                  line-height:1.6;">{recomendacao}</div>
            <div style="display:flex;gap:1.6rem;margin-top:1.2rem;
                  padding-top:1.1rem;border-top:1px solid var(--stroke);">
                {''.join(
                    f'<div><div style="font-size:0.65rem;color:var(--text-3);'
                    f'text-transform:uppercase;letter-spacing:0.09em;">{k}</div>'
                    f'<div style="font-family:JetBrains Mono,monospace;'
                    f'font-size:1.05rem;color:var(--text);margin-top:3px;">'
                    f'{v}</div></div>'
                    for k, v in tel_mostrar.items())}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # =====================================================================
    # POR QUÊ — explicabilidade em português
    # =====================================================================
    if frases:
        st.markdown("<div style='height:1.4rem;'></div>", unsafe_allow_html=True)
        st.markdown("#### Por que está assim")
        cols = st.columns(len(frases))
        for col, frase in zip(cols, frases):
            col.markdown(f"""
            <div class="g-card" style="height:100%;">
                <div style="font-size:0.89rem;color:var(--text);
                      line-height:1.6;">{frase}</div>
            </div>
            """, unsafe_allow_html=True)

    # =====================================================================
    st.markdown("<div style='height:1.4rem;'></div>", unsafe_allow_html=True)
    with st.expander("Como este número é calculado"):
        st.markdown(f"""
        O score começa no **perfil da sua apólice** — idade da máquina,
        estado, tipo de cobertura. Para este equipamento, esse ponto de
        partida é **{score_base:.0f}**.

        Sobre isso entra o que o sensor está medindo agora: inclinação,
        obstáculo à frente, umidade do solo, trepidação. O resultado é
        **{score:.0f}**.

        Uma inclinação que é aceitável numa máquina nova pode ser crítica
        numa máquina de quinze anos numa região de alta sinistralidade —
        é por isso que as duas coisas entram juntas.
        """)
        st.caption(
            "O sistema alerta, não intervém. Nenhum comando é enviado ao "
            "maquinário: quem decide parar é o operador.")

    if not REQUESTS_OK:
        st.caption(
            "Biblioteca `requests` não instalada — a leitura ao vivo do "
            "sensor fica indisponível. `pip install requests` para habilitar.")

    gerar_trilha_auditoria(
        "VISUALIZACAO_PAINEL_CLIENTE",
        f"equip={equip_id} | modo={'ao_vivo' if (ao_vivo and not modo_demo) else 'demo'} "
        f"| score={score:.1f} | faixa={faixa}")


if __name__ == "__main__":
    render()
