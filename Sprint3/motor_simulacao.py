"""
motor_simulacao.py
==================
Ambiente de demonstração — geração de telemetria de frota.

O QUE É SIMULADO, E O QUE NÃO É

    Simulado:     as leituras dos sensores. Uma frota operando ao longo de
                  uma safra, com terrenos, clima e desgaste distintos.

    NÃO simulado: o cálculo de risco. As leituras geradas aqui passam pelo
                  mesmo `core_fusao` que roda no dispositivo em campo e no
                  serviço de ingestão. Nenhum resultado é escrito à mão.

    Essa separação é o que torna a demonstração defensável: o que se vê é
    o motor real reagindo a uma frota fictícia — não um relatório com
    conclusões inventadas.

FUNDAMENTO FÍSICO DA SIMULAÇÃO

    Cada equipamento recebe um perfil operacional que determina como suas
    leituras se comportam:

      · terreno       distribuição de inclinação ao longo da jornada
      · densidade     frequência de obstáculos na área de trabalho
      · clima         faixa de umidade da região e do período
      · conservação   quanto a vibração cresce com as horas acumuladas

    O desgaste é progressivo: a vibração média sobe ao longo das semanas em
    função do estado de conservação. É esse crescimento que produz, nos
    dados, a tendência que o relatório depois identifica — a tendência não
    é plantada no relatório, ela emerge da física da simulação e é
    encontrada pela análise.

USO
    from motor_simulacao import simular_frota
    df = simular_frota(n_equipamentos=12, dias=90)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

SEMENTE_PADRAO = 20260824

# ---------------------------------------------------------------------------
# Perfis operacionais — o que diferencia um equipamento de outro em campo
# ---------------------------------------------------------------------------
# Calibração dos perfis
# ---------------------
# O motor entra em atenção por volta de 12° de inclinação e em risco por
# volta de 18°, com as demais grandezas em condição normal. Uma frota cuja
# inclinação média já fosse 14° operaria permanentemente em alerta — o
# alerta perderia sentido, e ninguém acreditaria na demonstração.
#
# Os valores abaixo produzem uma frota realista: a maioria das leituras em
# operação normal, uma parcela em atenção, e episódios de risco
# concentrados nos equipamentos de pior perfil. É esse contraste que torna
# o relatório legível — se tudo é crítico, nada é.
TERRENOS = {
    "plano":     {"incl_media": 2.5, "incl_desvio": 1.8},
    "ondulado":  {"incl_media": 4.5, "incl_desvio": 2.4},
    "encosta":   {"incl_media": 7.5, "incl_desvio": 3.2},
}

DENSIDADE_OBSTACULO = {
    "limpa":      0.006,   # probabilidade de obstáculo próximo por leitura
    "media":      0.009,
    "com_pedras": 0.022,
}

CLIMAS = {
    "seco":   {"umid_media": 38.0, "umid_desvio": 10.0},
    "misto":  {"umid_media": 52.0, "umid_desvio": 12.0},
    "umido":  {"umid_media": 60.0, "umid_desvio": 10.0},
}

CONSERVACAO = {
    "boa":       {"vib_base": 0.25, "vib_crescimento": 0.0006},
    "regular":   {"vib_base": 0.40, "vib_crescimento": 0.0018},
    "ruim":      {"vib_base": 0.52, "vib_crescimento": 0.0034},
}


@dataclass
class PerfilOperacional:
    equip_id: str
    terreno: str
    densidade: str
    clima: str
    conservacao: str
    horas_por_dia: float

    def descricao(self) -> str:
        return (f"terreno {self.terreno} · área {self.densidade} · "
                f"clima {self.clima} · conservação {self.conservacao}")


def _sortear_perfis(n: int, rng: np.random.Generator) -> list[PerfilOperacional]:
    """
    Distribui perfis pela frota. A proporção não é uniforme: a maior parte
    de uma frota real opera em condição intermediária, e os extremos são
    minoria. Uma distribuição uniforme produziria uma frota irreal, onde um
    terço dos equipamentos está sempre em situação crítica.
    """
    perfis = []
    for i in range(n):
        perfis.append(PerfilOperacional(
            equip_id=f"COL-{i:03d}",
            terreno=rng.choice(list(TERRENOS), p=[0.45, 0.35, 0.20]),
            densidade=rng.choice(list(DENSIDADE_OBSTACULO), p=[0.40, 0.42, 0.18]),
            clima=rng.choice(list(CLIMAS), p=[0.30, 0.45, 0.25]),
            conservacao=rng.choice(list(CONSERVACAO), p=[0.40, 0.42, 0.18]),
            horas_por_dia=float(np.clip(rng.normal(8.5, 2.0), 4.0, 14.0)),
        ))
    return perfis


def _leituras_do_dia(
    perfil: PerfilOperacional,
    dia: int,
    data: datetime,
    leituras_por_dia: int,
    rng: np.random.Generator,
) -> list[dict]:
    """
    Gera as leituras de uma jornada. Cada grandeza tem comportamento próprio,
    não é ruído aleatório uniforme.
    """
    t = TERRENOS[perfil.terreno]
    c = CLIMAS[perfil.clima]
    cons = CONSERVACAO[perfil.conservacao]
    p_obst = DENSIDADE_OBSTACULO[perfil.densidade]

    horas_acumuladas = perfil.horas_por_dia * dia

    # Desgaste: a vibração de base cresce com as horas acumuladas. É daqui
    # que sai a deterioração que o relatório vai encontrar depois.
    vib_media = cons["vib_base"] + cons["vib_crescimento"] * horas_acumuladas

    # Umidade tem componente sazonal — não é sorteio independente por dia
    sazonal = 8.0 * np.sin(2 * np.pi * dia / 45.0)
    umid_dia = float(np.clip(
        rng.normal(c["umid_media"] + sazonal, c["umid_desvio"]), 5, 98))

    # Temperatura anticorrelacionada com umidade, como no campo
    temp_dia = float(np.clip(rng.normal(34.0 - 0.12 * umid_dia, 3.0), 8, 45))

    registros = []
    for k in range(leituras_por_dia):
        # Inclinação: meia-normal — terreno tem piso plano e cauda de declive
        incl = float(np.clip(
            abs(rng.normal(t["incl_media"], t["incl_desvio"])), 0.0, 42.0))

        # Vibração cresce com a inclinação: terreno acidentado treme mais
        vib = float(np.clip(
            rng.normal(vib_media + 0.022 * incl, 0.16), 0.0, 12.0))

        # Obstáculo: evento discreto, não leitura contínua
        if rng.random() < p_obst:
            dist = float(np.clip(rng.gamma(2.2, 26.0), 8.0, 300.0))
        else:
            dist = -1.0            # sem eco — campo livre, contrato §2.1

        registros.append({
            "equip_id": perfil.equip_id,
            "data": data + timedelta(minutes=int(k * (600 / leituras_por_dia))),
            "dia": dia,
            "inclinacao_g": round(incl, 2),
            "vibracao_rms": round(vib, 2),
            "dist_obstaculo_cm": round(dist, 1),
            "umidade_pct": round(float(np.clip(
                rng.normal(umid_dia, 4.0), 5, 98)), 1),
            "temperatura_c": round(float(np.clip(
                rng.normal(temp_dia, 1.8), 5, 48)), 1),
            "horas_acumuladas": round(horas_acumuladas, 1),
        })
    return registros


def simular_frota(
    n_equipamentos: int = 12,
    dias: int = 90,
    leituras_por_dia: int = 24,
    semente: int = SEMENTE_PADRAO,
    data_inicial: datetime | None = None,
) -> tuple[pd.DataFrame, list[PerfilOperacional]]:
    """
    Gera a telemetria de uma frota ao longo de um período.

    Args:
        n_equipamentos: tamanho da frota.
        dias: duração da simulação — 90 dias cobre uma janela de safra.
        leituras_por_dia: amostras por jornada. 24 equivale a uma leitura
            agregada a cada 25 minutos de operação.
        semente: fixa para que a demonstração seja idêntica a cada execução.
            Uma apresentação que muda de números a cada abertura não é
            apresentável.

    Returns:
        (DataFrame de leituras, lista de perfis operacionais)
    """
    rng = np.random.default_rng(semente)
    data_inicial = data_inicial or (datetime.now() - timedelta(days=dias))
    perfis = _sortear_perfis(n_equipamentos, rng)

    linhas: list[dict] = []
    for dia in range(dias):
        data = data_inicial + timedelta(days=dia)
        if data.weekday() == 6:          # domingo: frota parada
            continue
        for perfil in perfis:
            linhas.extend(
                _leituras_do_dia(perfil, dia, data, leituras_por_dia, rng))

    df = pd.DataFrame(linhas).sort_values(["equip_id", "data"]).reset_index(drop=True)
    return df, perfis


def resumo_perfis(perfis: list[PerfilOperacional]) -> pd.DataFrame:
    """Tabela dos perfis, para exibir junto ao relatório."""
    return pd.DataFrame([{
        "Equipamento": p.equip_id,
        "Terreno": p.terreno,
        "Área": p.densidade.replace("_", " "),
        "Clima": p.clima,
        "Conservação": p.conservacao,
        "Jornada (h/dia)": round(p.horas_por_dia, 1),
    } for p in perfis])


__all__ = ["simular_frota", "resumo_perfis", "PerfilOperacional",
           "TERRENOS", "CLIMAS", "CONSERVACAO", "DENSIDADE_OBSTACULO"]
