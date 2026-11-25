"""Camada de avaliação do app: recebe os dados de um equipamento e devolve o
score com a decomposição em pontos por fator.

O cálculo em si é do core_fusao.py (motor do Sprint 4, copiado sem alteração).
Aqui só cuidamos de três coisas: validar a entrada, montar a explicação e
traduzir os fatores para frases.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "motor"))

import core_fusao as cf  # noqa: E402

BASE_CSV = RAIZ / "motor" / "base_sompo_limpa.csv"

NIVEL = {"verde": "Baixo", "amarelo": "Médio", "vermelho": "Alto"}

RECOMENDACAO = {
    "verde": "Operação normal. Siga o trabalho e mantenha a rotina de checagem.",
    "amarelo": "Reduza a velocidade e redobre a atenção no terreno.",
    "vermelho": "Risco elevado. Avalie interromper a operação até a condição melhorar.",
}

ROTULO = {
    "MODALIDADE_SUSEP": "Modalidade da apólice",
    "PREMIO_LIQUIDO_BRL": "Prêmio (valor da máquina)",
    "UF": "Estado",
    "QTD_COBERTURAS_CONTRATADAS": "Coberturas contratadas",
    "inclinacao_g": "Inclinação do terreno",
    "dist_obstaculo_cm": "Obstáculo à frente",
    "vibracao_rms": "Vibração",
    "umidade_pct": "Umidade",
    "temperatura_c": "Temperatura",
    "regra": "Regra de segurança",
    "teto": "Teto de 100 pontos",
}

# Faixas aceitas pelo contrato de telemetria (docs/CONTRATO_TELEMETRIA_v1.md)
LIMITES = {
    "inclinacao_g": (0.0, 90.0),
    "dist_obstaculo_cm": (0.0, 400.0),
    "vibracao_rms": (0.0, 10.0),
    "umidade_pct": (0.0, 100.0),
    "temperatura_c": (-10.0, 60.0),
}

# Cenários da maquete usados na demonstração
CENARIOS = {
    "Terreno plano e seco": dict(inclinacao_g=3.0, dist_obstaculo_cm=200.0,
                                 vibracao_rms=0.4, umidade_pct=45.0,
                                 temperatura_c=28.0),
    "Rampa moderada": dict(inclinacao_g=11.0, dist_obstaculo_cm=100.0,
                           vibracao_rms=1.0, umidade_pct=65.0,
                           temperatura_c=30.0),
    "Rampa com área úmida": dict(inclinacao_g=14.0, dist_obstaculo_cm=80.0,
                                 vibracao_rms=1.4, umidade_pct=85.0,
                                 temperatura_c=33.0),
    "Obstáculo muito próximo": dict(inclinacao_g=6.0, dist_obstaculo_cm=25.0,
                                    vibracao_rms=0.8, umidade_pct=50.0,
                                    temperatura_c=29.0),
}


@dataclass
class Fator:
    chave: str
    nome: str
    grupo: str          # "apólice", "campo" ou "regra"
    pontos: float


@dataclass
class Avaliacao:
    score_base: float
    score_final: float
    faixa: str
    nivel: str
    recomendacao: str
    override: bool
    motivo_override: str | None
    fatores: list[Fator] = field(default_factory=list)
    frases: list[str] = field(default_factory=list)
    percentil_carteira: float = 0.0


class EntradaInvalida(ValueError):
    pass


@lru_cache(maxsize=1)
def carteira() -> pd.DataFrame:
    base = pd.read_csv(BASE_CSV, encoding="utf-8")
    cf.calibrar_faixas(base)          # cortes por percentil, como nos portais
    return base


@lru_cache(maxsize=1)
def _mapa_uf() -> dict[str, float]:
    return cf.mapa_uf_credibilidade(carteira())


@lru_cache(maxsize=1)
def _scores_carteira() -> np.ndarray:
    return cf.calcular_score_base(carteira())["score_base"].to_numpy()


def opcoes() -> dict[str, list]:
    b = carteira()
    return {
        "uf": sorted(b["UF"].unique()),
        "modalidade": sorted(b["MODALIDADE_SUSEP"].unique()),
    }


def cortes() -> tuple[float, float]:
    carteira()
    return cf.FAIXAS[0][1], cf.FAIXAS[1][1]


def _validar(perfil: dict, tel: dict) -> None:
    opc = opcoes()
    if perfil.get("UF") not in opc["uf"]:
        raise EntradaInvalida(f"Estado fora da base: {perfil.get('UF')!r}.")
    if perfil.get("MODALIDADE_SUSEP") not in opc["modalidade"]:
        raise EntradaInvalida("Modalidade não reconhecida.")
    premio = perfil.get("PREMIO_LIQUIDO_BRL")
    if premio is None or not (0 < float(premio) <= 1_000_000):
        raise EntradaInvalida("O prêmio líquido deve ficar entre R$ 1 e R$ 1.000.000.")
    cob = perfil.get("QTD_COBERTURAS_CONTRATADAS")
    if cob is None or not (1 <= int(cob) <= 20):
        raise EntradaInvalida("Informe de 1 a 20 coberturas.")
    for campo, (lo, hi) in LIMITES.items():
        v = tel.get(campo)
        if v is None:
            continue
        if not (lo <= float(v) <= hi):
            raise EntradaInvalida(
                f"{ROTULO[campo]} fora da faixa aceita ({lo:g} a {hi:g}).")


def avaliar(perfil: dict, telemetria: dict) -> Avaliacao:
    _validar(perfil, telemetria)
    base_df = carteira()

    linha = cf.calcular_score_base(pd.DataFrame([perfil]), mapa_uf=_mapa_uf()).iloc[0]
    score_base = float(linha["score_base"])
    res = cf.fundir(score_base, telemetria, perfil=perfil)

    fatores = [
        Fator(col, ROTULO[col], "apólice", float(linha[f"{col}_contrib"]))
        for col in cf.PESOS_PERFIL
    ]
    soma_campo = 0.0
    for campo, cfg in cf.FATORES_TELEMETRIA.items():
        a = res.agravantes.get(campo, 0.0)
        pts = score_base * cf.K_AGRAVAMENTO * cfg["peso"] * a
        soma_campo += pts
        fatores.append(Fator(campo, ROTULO[campo], "campo", pts))

    # O que sobrou entre a soma dos fatores e o score exibido (teto ou regra)
    resto = res.score_final - (score_base + soma_campo)
    if abs(resto) >= 0.05:
        chave = "regra" if res.override_seguranca else "teto"
        fatores.append(Fator(chave, ROTULO[chave], "regra", resto))

    pct = float((_scores_carteira() < score_base).mean() * 100)
    av = Avaliacao(
        score_base=res.score_base,
        score_final=res.score_final,
        faixa=res.faixa,
        nivel=NIVEL[res.faixa],
        recomendacao=RECOMENDACAO[res.faixa],
        override=res.override_seguranca,
        motivo_override=res.motivo_override,
        fatores=fatores,
        percentil_carteira=pct,
    )
    av.frases = _frases(av, perfil, telemetria)
    return av


def _frases_de_campo(tel: dict) -> dict[str, str]:
    """Uma frase por leitura que existe. Sensor sem leitura fica de fora."""
    v = {k: x for k, x in tel.items() if x is not None}
    f = {}
    if "inclinacao_g" in v:
        f["inclinacao_g"] = (f"Inclinação de {v['inclinacao_g']:.0f}°: terreno em "
                             f"declive, risco de tombamento.")
    if "dist_obstaculo_cm" in v:
        f["dist_obstaculo_cm"] = f"Obstáculo a {v['dist_obstaculo_cm']:.0f} cm da máquina."
    if "vibracao_rms" in v:
        f["vibracao_rms"] = "Vibração acima do normal, sinal de terreno irregular."
    if "umidade_pct" in v:
        f["umidade_pct"] = f"Umidade de {v['umidade_pct']:.0f}%: solo úmido reduz a aderência."
    if "temperatura_c" in v:
        f["temperatura_c"] = f"Temperatura de {v['temperatura_c']:.0f}°C."
    return f


def _frases_por_chave(av: Avaliacao, perfil: dict, tel: dict) -> dict[str, str]:
    mod = str(perfil["MODALIDADE_SUSEP"]).split(" (")[0]
    uf = perfil["UF"]
    premio = f"{float(perfil['PREMIO_LIQUIDO_BRL']):,.0f}".replace(",", ".")
    critico_em = "inclinação" if "inclinacao" in (av.motivo_override or "") else "distância do obstáculo"
    textos = {
        "MODALIDADE_SUSEP": (
            f"Modalidade {mod}: na base, 55% das apólices de Benfeitorias e "
            f"45% das de Compreensivo tiveram sinistro, contra 13% no Penhor Rural."
            if mod.lower().startswith(("benf", "comp"))
            else f"Modalidade {mod}: poucos sinistros na base (13% das apólices)."),
        "PREMIO_LIQUIDO_BRL": (
            f"Prêmio de R$ {premio}: serve de proxy para o valor da máquina, "
            f"e sinistro de máquina mais cara custa mais."),
        "UF": (f"{uf} concentra mais casos críticos no histórico da base."
               if _mapa_uf().get(uf.lower(), 0) >= 0.5
               else f"{uf} tem poucos casos críticos no histórico da base."),
        "QTD_COBERTURAS_CONTRATADAS": (
            f"Poucas coberturas contratadas ({int(perfil['QTD_COBERTURAS_CONTRATADAS'])}): "
            f"menos proteção declarada pesa no perfil."),
        "regra": (f"Regra de segurança acionada: {critico_em} passou do limite "
                  f"crítico, e o nível sobe para Alto mesmo que o resto esteja bom."),
    }
    return {**textos, **_frases_de_campo(tel)}


def _frases(av: Avaliacao, perfil: dict, tel: dict) -> list[str]:
    """Até dois fatores de campo e dois da apólice, os que mais pontuam."""
    texto = _frases_por_chave(av, perfil, tel)
    ordem = sorted((f for f in av.fatores if f.pontos > 0.5), key=lambda f: -f.pontos)
    campo = [f.chave for f in ordem if f.grupo == "campo"][:2]
    apolice = [f.chave for f in ordem if f.grupo == "apólice"][:2]
    regra = ["regra"] if any(f.grupo == "regra" for f in ordem) else []
    frases = [texto[c] for c in (*regra, *campo, *apolice)]
    return frases or ["Nenhum fator pesa de forma relevante neste momento."]


def frases_produtor(av: Avaliacao, perfil: dict, tel: dict) -> list[str]:
    """Só o que o produtor vê no terreno, sem jargão de apólice."""
    texto = _frases_por_chave(av, perfil, tel)
    campo = [f for f in sorted(av.fatores, key=lambda f: -f.pontos)
             if f.grupo in ("campo", "regra") and f.pontos > 0.5]
    frases = [texto[f.chave] for f in campo][:3]
    if any(f.chave == "regra" for f in campo):
        frases = [texto["regra"], *[texto[f.chave] for f in campo if f.chave != "regra"][:2]]
    return frases or ["Nada no terreno preocupa agora. O resultado vem do tipo de "
                      "apólice e da região."]


JUSTIFICATIVA = {
    "MODALIDADE_SUSEP": "Taxa de sinistro de 55% em Benfeitorias, 45% em Compreensivo e 13% em Penhor Rural.",
    "PREMIO_LIQUIDO_BRL": "Único valor contínuo com correlação com sinistro na amostra (r = 0,23). Serve de proxy para o valor da máquina. Corte em R$ 8.000.",
    "UF": "Taxa de casos críticos por estado, suavizada por credibilidade de Bühlmann-Straub (k = 30) para que estado pequeno não pese por acaso.",
    "QTD_COBERTURAS_CONTRATADAS": "Correlação fraca (r = 0,08), por isso o peso é baixo. Menos coberturas, mais risco.",
    "inclinacao_g": "Começa a pesar em 8 graus e satura em 25. Tombamento é o sinistro que o projeto quer evitar.",
    "dist_obstaculo_cm": "Neutro a 120 cm, risco máximo em contato. Limite crítico em 35 cm.",
    "vibracao_rms": "Indica terreno irregular. Peso baixo porque o MPU6050 é um sensor ruidoso.",
    "umidade_pct": "Solo úmido reduz a aderência. Sinal indireto: o sensor mede a umidade do ar, não a do solo.",
    "temperatura_c": "Temperatura ambiente, não do motor. Entra por completude, com o menor peso.",
}


def tabela_pesos() -> pd.DataFrame:
    linhas = []
    for camada, tabela in (("Apólice", cf.PESOS_PERFIL), ("Campo", cf.FATORES_TELEMETRIA)):
        for chave, cfg in tabela.items():
            linhas.append({"Fator": ROTULO[chave], "Camada": camada,
                           "Peso": f"{cfg['peso']:.2f}".replace(".", ","),
                           "Justificativa": JUSTIFICATIVA[chave]})
    return pd.DataFrame(linhas).set_index("Fator")
