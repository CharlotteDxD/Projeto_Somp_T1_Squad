"""
core_relatorio.py
=================
Motor de análise e relatório sobre séries de telemetria.

O PONTO CENTRAL

    Nenhum achado deste módulo é escrito à mão. Toda conclusão vem de
    aplicar `core_fusao` — o mesmo motor do dispositivo e do serviço de
    ingestão — sobre a série recebida, e depois procurar padrões nos
    resultados.

    Se a série vier de um dispositivo real, os achados são reais. Se vier
    do ambiente de demonstração, os achados descrevem aquela frota
    fictícia. O motor não sabe a diferença, e é isso que torna a
    demonstração honesta: mostra-se o comportamento verdadeiro do sistema
    diante de dados que se sabe serem simulados.

O QUE O RELATÓRIO RESPONDE

    1. Situação    — como está a frota agora
    2. Tendência   — quais equipamentos estão piorando, e quão rápido
    3. Exposição   — quanto tempo cada máquina passou em risco
    4. Antecipação — quantos alertas precederam uma condição crítica
    5. Ação        — o que fazer, por equipamento, em ordem de prioridade
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

import core_fusao as cf

CAMPOS_TELEMETRIA = ["inclinacao_g", "vibracao_rms", "dist_obstaculo_cm",
                     "umidade_pct", "temperatura_c"]


# =========================================================================
# 1. APLICAÇÃO DO MOTOR SOBRE A SÉRIE
# =========================================================================
def pontuar_serie(
    df: pd.DataFrame,
    score_base_por_equip: Optional[dict[str, float]] = None,
    score_base_padrao: float = 55.0,
) -> pd.DataFrame:
    """
    Aplica core_fusao.fundir a cada leitura da série.

    Este é o único lugar onde o score é calculado. As funções de análise
    abaixo consomem o resultado — nenhuma delas reimplementa o cálculo.
    """
    score_base_por_equip = score_base_por_equip or {}
    saida = df.copy()

    finais, faixas, overrides, motivos = [], [], [], []
    for linha in df.itertuples(index=False):
        base = score_base_por_equip.get(
            getattr(linha, "equip_id", ""), score_base_padrao)
        tel = {c: getattr(linha, c, None) for c in CAMPOS_TELEMETRIA}
        r = cf.fundir(base, tel)
        finais.append(r.score_final)
        faixas.append(r.faixa)
        overrides.append(r.override_seguranca)
        motivos.append(r.motivo_override or "")

    saida["score"] = finais
    saida["faixa"] = faixas
    saida["override"] = overrides
    saida["motivo_override"] = motivos
    return saida


# =========================================================================
# 2. SITUAÇÃO ATUAL
# =========================================================================
def situacao_frota(dfp: pd.DataFrame, janela_dias: int = 7) -> pd.DataFrame:
    """Estado de cada equipamento no período mais recente."""
    ultimo_dia = dfp["dia"].max()
    recente = dfp[dfp["dia"] > ultimo_dia - janela_dias]

    linhas = []
    for equip, g in recente.groupby("equip_id"):
        n = len(g)
        linhas.append({
            "Equipamento": equip,
            "Score médio": round(g["score"].mean(), 1),
            "Pico": round(g["score"].max(), 1),
            "% em atenção": round((g["faixa"] == "amarelo").sum() / n * 100, 1),
            "% em risco": round((g["faixa"] == "vermelho").sum() / n * 100, 1),
            "Alertas críticos": int(g["override"].sum()),
        })
    return (pd.DataFrame(linhas)
            .sort_values("Score médio", ascending=False)
            .reset_index(drop=True))


# =========================================================================
# 3. TENDÊNCIA — o componente preditivo
# =========================================================================
@dataclass
class Tendencia:
    equip_id: str
    inclinacao_pontos_por_semana: float
    score_inicial: float
    score_atual: float
    r2: float
    semanas_ate_faixa_critica: Optional[float]
    confiavel: bool
    leitura: str


def analisar_tendencia(
    dfp: pd.DataFrame,
    corte_critico: Optional[float] = None,
    r2_minimo: float = 0.25,
) -> list[Tendencia]:
    """
    Regressão linear do score diário de cada equipamento ao longo do tempo.

    A projeção de quantas semanas faltam para atingir a faixa crítica só é
    emitida quando o ajuste explica parte relevante da variação (R² acima
    do mínimo) E a inclinação é positiva. Projetar sobre uma série que
    apenas oscila produziria número sem significado — e é exatamente o tipo
    de projeção que não sobrevive a uma pergunta.
    """
    if corte_critico is None:
        corte_critico = cf.FAIXAS[2][0]

    resultados: list[Tendencia] = []
    for equip, g in dfp.groupby("equip_id"):
        diario = g.groupby("dia")["score"].mean()
        if len(diario) < 14:
            continue

        x = diario.index.to_numpy(dtype=float)
        y = diario.to_numpy(dtype=float)

        coef = np.polyfit(x, y, 1)
        previsto = np.polyval(coef, x)
        ss_res = float(((y - previsto) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-9 else 0.0

        por_semana = float(coef[0] * 7.0)
        atual = float(y[-7:].mean())
        inicial = float(y[:7].mean())
        confiavel = (r2 >= r2_minimo) and (por_semana > 0.05)

        semanas = None
        if confiavel and atual < corte_critico:
            semanas = round((corte_critico - atual) / por_semana, 1)

        if not confiavel:
            leitura = "sem tendência definida — oscila sem direção clara"
        elif semanas is not None and semanas <= 4:
            leitura = f"atinge a faixa crítica em cerca de {semanas:.0f} semanas"
        elif semanas is not None:
            leitura = f"deterioração lenta — faixa crítica em ~{semanas:.0f} semanas"
        else:
            leitura = "já opera na faixa crítica"

        resultados.append(Tendencia(
            equip_id=equip,
            inclinacao_pontos_por_semana=round(por_semana, 2),
            score_inicial=round(inicial, 1),
            score_atual=round(atual, 1),
            r2=round(r2, 3),
            semanas_ate_faixa_critica=semanas,
            confiavel=confiavel,
            leitura=leitura,
        ))

    return sorted(resultados,
                  key=lambda t: (-t.inclinacao_pontos_por_semana))


# =========================================================================
# 4. EXPOSIÇÃO ACUMULADA
# =========================================================================
def exposicao_acumulada(dfp: pd.DataFrame) -> pd.DataFrame:
    """
    Quanto tempo cada equipamento passou em cada faixa.

    Duas máquinas com o mesmo score médio podem ter históricos muito
    diferentes: uma estável no limite, outra alternando entre tranquila e
    crítica. A segunda exige atenção diferente, e a média esconde isso.
    """
    linhas = []
    for equip, g in dfp.groupby("equip_id"):
        n = len(g)
        linhas.append({
            "Equipamento": equip,
            "Leituras": n,
            "Normal (%)": round((g["faixa"] == "verde").sum() / n * 100, 1),
            "Atenção (%)": round((g["faixa"] == "amarelo").sum() / n * 100, 1),
            "Risco (%)": round((g["faixa"] == "vermelho").sum() / n * 100, 1),
            "Eventos críticos": int(g["override"].sum()),
        })
    return (pd.DataFrame(linhas)
            .sort_values("Risco (%)", ascending=False)
            .reset_index(drop=True))


# =========================================================================
# 5. ANTECIPAÇÃO — a métrica que descreve a prevenção
# =========================================================================
@dataclass
class Antecipacao:
    eventos_criticos: int
    precedidos_por_alerta: int
    janela_leituras: int
    percentual: float
    mediana_leituras_antes: Optional[float]


def medir_antecipacao(dfp: pd.DataFrame, janela: int = 8) -> Antecipacao:
    """
    Dos eventos que atingiram condição crítica, quantos foram precedidos
    por um alerta de atenção dentro da janela anterior?

    É a medida que descreve o valor do produto: não "quantos sinistros
    evitamos" — isso exige campo — mas "quantas vezes o sistema teve a
    chance de avisar antes". A diferença entre as duas afirmações é o que
    separa demonstração de promessa.
    """
    total, precedidos, distancias = 0, 0, []

    for _, g in dfp.groupby("equip_id"):
        g = g.reset_index(drop=True)
        criticos = g.index[g["override"]].tolist()

        anterior = -999
        for i in criticos:
            if i - anterior < janela:      # mesmo episódio, não conta 2x
                continue
            anterior = i
            total += 1

            inicio = max(0, i - janela)
            antes = g.iloc[inicio:i]
            alerta = antes.index[antes["faixa"].isin(["amarelo", "vermelho"])]
            if len(alerta) > 0:
                precedidos += 1
                distancias.append(i - int(alerta[0]))

    return Antecipacao(
        eventos_criticos=total,
        precedidos_por_alerta=precedidos,
        janela_leituras=janela,
        percentual=round(precedidos / total * 100, 1) if total else 0.0,
        mediana_leituras_antes=(round(float(np.median(distancias)), 1)
                                if distancias else None),
    )


# =========================================================================
# 6. RECOMENDAÇÕES
# =========================================================================
@dataclass
class Recomendacao:
    equip_id: str
    prioridade: int          # 1 = mais urgente
    titulo: str
    fundamento: str
    acao: str


def gerar_recomendacoes(
    dfp: pd.DataFrame,
    tendencias: list[Tendencia],
    limite: int = 6,
) -> list[Recomendacao]:
    """
    Deriva ações a partir do que a análise encontrou. Cada recomendação
    carrega o fundamento numérico que a originou — recomendação sem
    fundamento visível é opinião.
    """
    exp = exposicao_acumulada(dfp).set_index("Equipamento")
    por_equip = {t.equip_id: t for t in tendencias}
    recs: list[Recomendacao] = []

    total_leituras = len(dfp) / max(dfp["equip_id"].nunique(), 1)

    for equip in exp.index:
        risco = float(exp.loc[equip, "Risco (%)"])
        eventos = int(exp.loc[equip, "Eventos críticos"])
        t = por_equip.get(equip)

        # Fator dominante: qual grandeza mais empurrou o score deste equipamento
        g = dfp[dfp["equip_id"] == equip]
        medias = {c: float(g[c].mean()) for c in CAMPOS_TELEMETRIA if c in g}

        # Eventos precisam ser lidos como TAXA, não como contagem absoluta.
        # Quinze eventos em 1.800 leituras é ocorrência esporádica; os mesmos
        # quinze em 200 leituras é padrão. Comparar contagens de séries de
        # tamanhos diferentes produz recomendação errada.
        taxa_eventos = eventos / total_leituras * 100 if total_leituras else 0.0

        ja_critico = risco >= 50.0
        deteriorando = (t and t.confiavel
                        and t.semanas_ate_faixa_critica is not None
                        and t.semanas_ate_faixa_critica <= 8)

        if ja_critico:
            # Prioridade máxima: já está na faixa, não é projeção.
            tendencia_txt = (
                f"; score subindo {t.inclinacao_pontos_por_semana:+.2f} "
                f"pontos por semana" if t and t.confiavel else "")
            recs.append(Recomendacao(
                equip_id=equip, prioridade=1,
                titulo="Intervenção imediata — opera em faixa de risco",
                fundamento=(
                    f"{risco:.0f}% das leituras do período em faixa de risco"
                    f"{tendencia_txt}; vibração média "
                    f"{medias.get('vibracao_rms', 0):.2f} m/s², inclinação "
                    f"média {medias.get('inclinacao_g', 0):.1f}°"),
                acao=("Retirar de operação para inspeção antes da próxima "
                      "jornada. A condição é permanente, não episódica."),
            ))
        elif deteriorando:
            recs.append(Recomendacao(
                equip_id=equip, prioridade=1,
                titulo="Inspeção preventiva — deterioração consistente",
                fundamento=(
                    f"score subiu de {t.score_inicial:.0f} para "
                    f"{t.score_atual:.0f} ({t.inclinacao_pontos_por_semana:+.2f} "
                    f"pontos por semana, R²={t.r2:.2f}); vibração média em "
                    f"{medias.get('vibracao_rms', 0):.2f} m/s²"),
                acao=(f"Agendar inspeção em até "
                      f"{max(1, int(t.semanas_ate_faixa_critica) - 1)} semanas. "
                      f"A tendência é consistente, não oscilação."),
            ))
        elif taxa_eventos >= 0.4:
            recs.append(Recomendacao(
                equip_id=equip, prioridade=2,
                titulo="Revisão de rota e condição de operação",
                fundamento=(
                    f"{eventos} eventos críticos em {total_leituras:.0f} "
                    f"leituras ({taxa_eventos:.2f}% do período); inclinação "
                    f"média {medias.get('inclinacao_g', 0):.1f}°, obstáculos "
                    f"em área {'densa' if medias.get('dist_obstaculo_cm', -1) > 0 else 'limpa'}"),
                acao=("Reavaliar o talhão atribuído e o horário de operação. "
                      "A exposição é recorrente, não pontual."),
            ))
        elif risco >= 8.0 or (t and t.confiavel):
            motivo = (f"score em alta ({t.inclinacao_pontos_por_semana:+.2f}/semana)"
                      if t and t.confiavel
                      else f"{risco:.1f}% das leituras em faixa de risco")
            recs.append(Recomendacao(
                equip_id=equip, prioridade=3,
                titulo="Monitoramento reforçado",
                fundamento=f"{motivo}, sem atingir limiar de intervenção",
                acao="Manter acompanhamento e reavaliar na próxima renovação.",
            ))

    recs.sort(key=lambda r: (r.prioridade, r.equip_id))
    return recs[:limite]


# =========================================================================
# 7. RELATÓRIO CONSOLIDADO
# =========================================================================
@dataclass
class Relatorio:
    gerado_em: datetime
    origem: str
    periodo_dias: int
    n_equipamentos: int
    n_leituras: int
    situacao: pd.DataFrame
    exposicao: pd.DataFrame
    tendencias: list[Tendencia] = field(default_factory=list)
    antecipacao: Optional[Antecipacao] = None
    recomendacoes: list[Recomendacao] = field(default_factory=list)

    @property
    def em_deterioracao(self) -> list[Tendencia]:
        return [t for t in self.tendencias if t.confiavel]


def gerar_relatorio(
    dfp: pd.DataFrame,
    origem: str = "ambiente de demonstração",
) -> Relatorio:
    """Monta o relatório completo a partir de uma série já pontuada."""
    tend = analisar_tendencia(dfp)
    return Relatorio(
        gerado_em=datetime.now(),
        origem=origem,
        periodo_dias=int(dfp["dia"].max() - dfp["dia"].min() + 1),
        n_equipamentos=int(dfp["equip_id"].nunique()),
        n_leituras=int(len(dfp)),
        situacao=situacao_frota(dfp),
        exposicao=exposicao_acumulada(dfp),
        tendencias=tend,
        antecipacao=medir_antecipacao(dfp),
        recomendacoes=gerar_recomendacoes(dfp, tend),
    )


__all__ = ["pontuar_serie", "gerar_relatorio", "Relatorio", "Tendencia",
           "Antecipacao", "Recomendacao", "situacao_frota",
           "exposicao_acumulada", "analisar_tendencia", "medir_antecipacao",
           "gerar_recomendacoes"]
