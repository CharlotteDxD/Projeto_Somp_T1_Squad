"""
pagina_us03_painel_cliente.py
==============================
Painel do Segurado (US03) — visão simplificada para o cliente final (o
produtor rural / operador de campo).

Owner: Charles · Reviewers: Rafael (score), Gustavo (API)

RECONSTRUÇÃO Sprint 4 — leia antes de mexer

    O arquivo anterior desta tela (`dashboard_cliente[1].py`) não estava
    ligado ao app.py (o roteador importa `pagina_us03_painel_cliente`, que
    não existia) e calculava o score com uma fórmula própria, solta, que
    ignorava core_fusao e o contrato de telemetria — sliders manuais de
    "inclinação eixo Z" e "umidade do solo", sem nenhuma leitura real do
    ESP32, e uma métrica fixa ("3 sinistros evitados") sem selo de dado
    sintético. Reescrita do zero, consumindo:

        GET /telemetria/v1/ultimo/<equip_id>   — leitura ao vivo (contrato
            v1.0, seção 5). Traz score_final, faixa_estavel, frases e
            recomendação já prontos — nada é recalculado aqui.

    Três estados possíveis, sempre rotulados na tela (regra do projeto:
    dado sintético nunca aparece como se fosse real — core_procedencia.py):

        1. TELEMETRIA AO VIVO   — API respondeu para este equip_id.
        2. HISTÓRICO ACUMULADO  — API fora do ar, mas há leitura anterior
           salva em data/telemetria_esp32.csv.
        3. SÓ PERFIL (sem sensor) — nenhuma leitura, ao vivo ou histórica.
           Mostra apenas o score_base (Camada 1, perfil da apólice) e diz
           isso claramente — nunca inventa uma leitura de sensor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st

import core_fusao as cf
import core_integracao as ci
import core_recomendacoes as cr

EQUIP_PADRAO = "COL-099"   # mesmo equipamento de exemplo do contrato de telemetria
TIMEOUT_S = 2.0

_HEX = {"verde": "#3FCF8E", "amarelo": "#F5B23D", "vermelho": "#F2555A"}
_ROTULO_FAIXA = {
    "verde": "Operação segura", "amarelo": "Atenção", "vermelho": "Alerta crítico",
}


# =========================================================================
# 1. SELETOR DE EQUIPAMENTO
# =========================================================================
def _opcoes_equipamento() -> list[str]:
    """
    Lista de equipamentos para o seletor. Usa o cadastro real de frota
    quando presente (data/frota_real.csv); senão cai nos identificadores
    sequenciais que a base de apólices sustenta (COL-000..COL-{n-1}) — o
    mesmo esquema usado por api_telemetria.carregar_perfis().
    """
    frota, integ = ci.carregar_frota()
    if integ.conectado and frota is not None and "equip_id" in frota.columns:
        return sorted(frota["equip_id"].astype(str).unique().tolist())

    apolices, _ = ci.carregar_apolices()
    n = len(apolices) if apolices is not None else 150
    return [f"COL-{i:03d}" for i in range(n)]


# =========================================================================
# 2. LEITURA — três fontes, nesta ordem de prioridade
# =========================================================================
def _leitura_ao_vivo(equip_id: str) -> Optional[dict]:
    """GET /telemetria/v1/ultimo/<equip_id>. None se indisponível ou 404."""
    try:
        import requests
        r = requests.get(f"{ci.API_BASE}/telemetria/v1/ultimo/{equip_id}",
                         timeout=TIMEOUT_S)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _leitura_historica(equip_id: str) -> Optional[dict]:
    """Última linha de data/telemetria_esp32.csv para este equipamento."""
    df, integ = ci.telemetria_historica()
    if not integ.conectado or df is None or "equip_id" not in df.columns:
        return None
    linhas = df[df["equip_id"].astype(str) == str(equip_id)]
    if linhas.empty:
        return None
    return linhas.iloc[-1].to_dict()


def _score_so_perfil(equip_id: str) -> Optional[dict]:
    """
    Sem telemetria de espécie nenhuma: mostra só o score de perfil
    (Camada 1) da linha correspondente da base de apólices. Nunca inventa
    inclinação, vibração ou distância — essas ficam em branco na tela.
    """
    df, integ = ci.carregar_apolices()
    if df is None:
        return None
    try:
        idx = int(equip_id.split("-")[-1])
    except (ValueError, IndexError):
        idx = 0
    if idx >= len(df):
        return None
    cf.calibrar_faixas(df)
    linha = cf.calcular_score_base(df).iloc[idx]
    faixa, recomendacao = cf.classificar(float(linha["score_base"]))
    return {
        "score_base": float(linha["score_base"]),
        "score_final": float(linha["score_base"]),
        "faixa_estavel": faixa,
        "recomendacao": recomendacao,
        "frases": [],
        "perfil": linha.to_dict(),
    }


def obter_estado(equip_id: str) -> tuple[str, dict]:
    """Retorna (fonte, dados) — fonte em {'ao_vivo','historico','perfil'}."""
    ao_vivo = _leitura_ao_vivo(equip_id)
    if ao_vivo is not None:
        return "ao_vivo", ao_vivo

    historico = _leitura_historica(equip_id)
    if historico is not None:
        return "historico", historico

    perfil = _score_so_perfil(equip_id)
    if perfil is not None:
        return "perfil", perfil

    return "indisponivel", {}


# =========================================================================
# 3. RENDER
# =========================================================================
def render() -> None:
    from core_app import (check_permissao_silenciosa, gerar_trilha_auditoria,
                          _contrato_box, _header)

    # Esta é a única tela que os dois portais compartilham: quem administra
    # a carteira (view_dashboard) e o próprio segurado (view_proprio_equipamento,
    # papel "Segurado" — é a tela inicial do portal "Minha Máquina", ver
    # core_perfis.PORTAL_SEGURADO.inicial). check_permissao (não-silenciosa)
    # imprimiria "acesso negado" na primeira tentativa mesmo quando a segunda
    # seria aprovada — por isso as duas checagens usam a variante silenciosa.
    if not (check_permissao_silenciosa("view_dashboard")
            or check_permissao_silenciosa("view_proprio_equipamento")):
        st.error("Acesso negado a esta tela.")
        return

    _contrato_box("painel_cliente", [])
    _header("Painel do Segurado",
            "Farol de risco do seu equipamento, em tempo real")

    equipamentos = _opcoes_equipamento()
    padrao = EQUIP_PADRAO if EQUIP_PADRAO in equipamentos else (
        equipamentos[0] if equipamentos else EQUIP_PADRAO)
    c_sel, c_ref = st.columns([3, 1])
    equip_id = c_sel.selectbox("Equipamento", equipamentos,
                               index=equipamentos.index(padrao) if padrao in equipamentos else 0,
                               key="cliente_equip_sel")
    auto = c_ref.toggle("Atualizar a cada 2s", value=False, key="cliente_auto")

    fonte, dados = obter_estado(equip_id)
    gerar_trilha_auditoria(
        "VISUALIZACAO_PAINEL_CLIENTE", f"equip_id={equip_id} fonte={fonte}")

    if fonte == "indisponivel":
        st.warning(
            "Sem leitura de telemetria (ao vivo ou histórica) e sem base de "
            "apólices carregada para este equipamento. Verifique se o "
            "serviço de ingestão está no ar (menu → Infraestrutura) ou se "
            "`base_sompo_limpa.csv` está na pasta do projeto.", icon="⚠️")
        return

    faixa = dados.get("faixa_estavel") or dados.get("faixa") or "verde"
    cor = _HEX.get(faixa, _HEX["verde"])
    score = dados.get("score_final", dados.get("score_base", 0.0))

    # ---------- Selo de procedência da leitura ----------
    _SELOS = {
        "ao_vivo":  ("Conectado", "var(--verde)",
                     f"Telemetria ao vivo · {ci.API_BASE}"),
        "historico": ("Padrão", "var(--amarelo)",
                      "Serviço ao vivo fora do ar — mostrando última leitura "
                      "salva em data/telemetria_esp32.csv"),
        "perfil":   ("Padrão", "var(--text-3)",
                     "Sem telemetria (ao vivo ou histórica) — mostrando "
                     "apenas o score de perfil da apólice, sem dado de "
                     "sensor"),
    }
    sit, cor_selo, txt_selo = _SELOS[fonte]
    st.markdown(f"""
    <div class="pill" style="margin-bottom:1.2rem;">
        <span class="dot" style="background:{cor_selo};box-shadow:0 0 8px {cor_selo};"></span>
        <span style="color:var(--text-2);">{txt_selo}</span>
    </div>""", unsafe_allow_html=True)

    # ---------- Farol principal ----------
    st.markdown(f"""
    <div class="g-card" style="padding:1.6rem 1.8rem;border-color:{cor}55;">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:20px;">
            <div>
                <div style="font-size:0.78rem;color:var(--text-3);
                      text-transform:uppercase;letter-spacing:0.08em;">
                    {equip_id}</div>
                <div style="font-family:'Manrope',sans-serif;font-weight:800;
                      font-size:1.6rem;color:{cor};margin-top:4px;">
                    {_ROTULO_FAIXA.get(faixa, faixa.title())}</div>
            </div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:2.2rem;
                  font-weight:700;color:{cor};">{score:.0f}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    if dados.get("override_seguranca"):
        st.error(
            f"⚠️ Override de segurança acionado — {dados.get('motivo_override', '')}. "
            f"Recomendação de segurança tem prioridade sobre o score.",
            icon="🛑")

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

    # ---------- Frases explicativas + recomendação ----------
    frases = dados.get("frases") or []
    recomendacao = dados.get("recomendacao")
    if not recomendacao:
        recomendacao = cr.gerar_recomendacao(score).acao_principal

    if frases:
        st.markdown("#### O que está pesando agora")
        for f in frases:
            st.markdown(f"- {f}")
    st.info(f"**Recomendação:** {recomendacao}")

    # ---------- Leituras brutas do sensor (só quando há telemetria) ----------
    if fonte in ("ao_vivo", "historico"):
        st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
        st.markdown("#### Leituras do sensor")
        campos = [
            ("Inclinação", dados.get("tel_inclinacao_g"), "°"),
            ("Vibração (RMS)", dados.get("tel_vibracao_rms"), " m/s²"),
            ("Distância a obstáculo", dados.get("tel_dist_obstaculo_cm"), " cm"),
            ("Temperatura", dados.get("tel_temperatura_c"), "°C"),
            ("Umidade", dados.get("tel_umidade_pct"), "%"),
        ]
        cols = st.columns(len(campos))
        for col, (rotulo, valor, unidade) in zip(cols, campos):
            texto = "—" if valor is None else f"{float(valor):.1f}{unidade}"
            col.metric(rotulo, texto)

        ts = dados.get("ts_servidor")
        if ts:
            st.caption(f"Última leitura: {ts}")

    st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
    with st.expander("Como este número é calculado"):
        st.markdown(
            "O score combina duas camadas: **perfil** (histórico da "
            "apólice — modalidade, prêmio, UF, coberturas — atualizado "
            "mensalmente) e **exposição** (leitura do sensor no "
            "equipamento agora, quando disponível). Um limiar crítico de "
            "inclinação ou obstáculo força alerta vermelho independente "
            "do score. Ver **Explicabilidade** no menu para o detalhe dos "
            "pesos.")

    # ---------- Auto-atualização (polling de 2s, contrato seção 5) ----------
    if auto and fonte == "ao_vivo":
        import time
        time.sleep(2)
        st.rerun()
    elif auto:
        st.caption(
            "Atualização automática pausada — só se aplica com telemetria "
            "ao vivo.")


if __name__ == "__main__":
    render()
