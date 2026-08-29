"""
core_recomendacoes.py
=====================
Catalogo canonico de recomendacoes acionaveis · Sompo Predict · Sprint 3

Owner: Charles · Reviewers: Rafael (XAI), Gustavo (API)

MIGRACAO Sprint 3:

    Este modulo nao importava core_scoring diretamente (so citava em
    comentario), entao nao quebrava em runtime. Mas duas coisas precisavam
    de ajuste pra nao divergir do core_fusao:

    1. FAIXAS_ACIONAVEIS tinha cutoffs fixos (40/75) copiados do
       core_scoring antigo. O core_fusao CALIBRA os cortes nos percentis
       60/90 da carteira real (tipicamente ~58/~72, nao 40/75). Sem ajuste,
       o texto de recomendacao podia dizer "Alerta Critico" pra um score
       que o farol da tela mostra como amarelo.
       Resolvido com `faixa_de(score)`, que usa core_fusao.classificar()
       como fonte de verdade, com os cutoffs fixos so como fallback se
       core_fusao nao estiver importavel (uso standalone/teste).

    2. RECOMENDACOES_CONTEXTUAIS estava indexado pelas 12 features antigas
       (prox_corpo_dagua_km, velocidade_avg_kmh, etc) que nao existem em
       nenhuma base real do projeto — logo NUNCA disparavam em producao.
       Reindexado pelas chaves reais: IDADE_MAQUINA_ANOS, UF,
       ACESSORIOS_SEGURADOS (perfil) e inclinacao_g, dist_obstaculo_cm,
       vibracao_rms, umidade_pct, temperatura_c (telemetria, contrato v1.0).

Este modulo e a UNICA fonte de verdade para gerar texto acionavel a partir
de um score de risco. Todos os consumidores (US01, US03, US05, US07, API
Flask, simulador de cenarios) DEVEM importar daqui.

Contrato publico:
    - gerar_recomendacao(score, fator_dominante=None) -> Recomendacao
    - recomendacoes_por_faixa(score) -> list[str]
    - faixa_de(score) -> dict            [NOVO — fonte de verdade da faixa]
    - FAIXAS_ACIONAVEIS, RECOMENDACOES_CONTEXTUAIS  (constantes)

Referencias:
    - core_fusao.FAIXAS (cortes calibrados, fonte de verdade em runtime)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    import core_fusao as _cf
except ImportError:
    _cf = None


# =========================================================================
# 1. ENUM DE NIVEIS DE URGENCIA (alinhado com core_fusao.FAIXAS)
# =========================================================================
NIVEL_VERDE    = "verde"
NIVEL_AMARELO  = "amarelo"
NIVEL_VERMELHO = "vermelho"


# =========================================================================
# 2. RECOMENDACAO BASE POR FAIXA DE SCORE
# =========================================================================
# Os cutoffs abaixo (0-40 / 40-75 / 75-100) sao FALLBACK apenas — usados
# somente se core_fusao nao puder ser importado. Em runtime normal,
# `faixa_de()` usa core_fusao.classificar(), que aplica os cortes
# calibrados por percentil da carteira real.
FAIXAS_ACIONAVEIS: dict[tuple[float, float], dict[str, str]] = {
    (0.0, 40.0): {
        "nivel":          NIVEL_VERDE,
        "titulo":         "Operacao Segura",
        "acao_principal": "Manter operacao normal. Telemetria dentro dos parametros.",
        "prazo_acao":     "Revisao programada conforme cronograma padrao (90 dias).",
        "cor":            "#22D48A",
        "icone":          "✅",
        "prioridade_sla": "P4 · Baixa",
    },
    (40.0, 75.0): {
        "nivel":          NIVEL_AMARELO,
        "titulo":         "Atencao Operacional",
        "acao_principal": "Reduzir velocidade media e revisar planejamento da jornada.",
        "prazo_acao":     "Inspecao tecnica em ate 48 horas. Notificar gestor de frota.",
        "cor":            "#F5A623",
        "icone":          "⚠️",
        "prioridade_sla": "P2 · Media",
    },
    (75.0, 100.01): {
        "nivel":          NIVEL_VERMELHO,
        "titulo":         "Alerta Critico",
        "acao_principal": "PARAR operacao imediatamente. Acionar tecnico em campo.",
        "prazo_acao":     "Intervencao em ate 2 horas. Bloqueio automatico de cobertura.",
        "cor":            "#FF4D6A",
        "icone":          "🛑",
        "prioridade_sla": "P1 · Critica",
    },
}

_CFG_POR_NIVEL = {cfg["nivel"]: cfg for cfg in FAIXAS_ACIONAVEIS.values()}


def faixa_de(score: float) -> dict[str, str]:
    """
    Resolve a config de faixa pro score, usando core_fusao como fonte de
    verdade quando disponivel (cortes calibrados por percentil), com
    fallback pros cutoffs fixos 40/75 se core_fusao nao existir.
    """
    if _cf is not None:
        nivel, _ = _cf.classificar(float(score))
        return _CFG_POR_NIVEL.get(nivel, _CFG_POR_NIVEL[NIVEL_VERMELHO])
    return _faixa_de_score_legado(score)[1]


def _faixa_de_score_legado(score: float) -> tuple[tuple[float, float], dict[str, str]]:
    """Fallback: cutoffs fixos, usado so se core_fusao nao importar."""
    s = float(score)
    for (low, high), cfg in FAIXAS_ACIONAVEIS.items():
        if low <= s < high:
            return (low, high), cfg
    return (75.0, 100.01), FAIXAS_ACIONAVEIS[(75.0, 100.01)]


# =========================================================================
# 3. RECOMENDACOES CONTEXTUAIS · chaves do contrato atual (Sprint 3)
# =========================================================================
RECOMENDACOES_CONTEXTUAIS: dict[str, dict[str, str]] = {
    # ---- Perfil (Camada 1 — core_fusao.PESOS_PERFIL) ----
    "IDADE_MAQUINA_ANOS": {
        NIVEL_VERDE:
            "Equipamento dentro da vida útil ótima (<8 anos).",
        NIVEL_AMARELO:
            "Equipamento em fase de envelhecimento (8–15 anos). "
            "Intensificar manutenção preventiva e atualizar laudo técnico.",
        NIVEL_VERMELHO:
            "Equipamento com vida útil esgotada (>15 anos). Recomendar "
            "renovação da frota ou aceitar agravamento de prêmio.",
    },
    "UF": {
        NIVEL_VERDE:
            "UF de baixo risco relativo segundo credibilidade Bühlmann-Straub "
            "sobre a base SUSEP.",
        NIVEL_AMARELO:
            "UF com sinistralidade intermediária. Reforçar prevenção "
            "climática conforme calendário regional.",
        NIVEL_VERMELHO:
            "UF de alta sinistralidade relativa. Recomendar monitoramento "
            "climático contínuo e gatilhos automáticos de alerta no app.",
    },
    "ACESSORIOS_SEGURADOS": {
        NIVEL_VERDE:
            "Cobertura de acessórios compatível com o perfil observado.",
        NIVEL_AMARELO:
            "Poucos acessórios segurados frente ao perfil da apólice. "
            "Revisar cobertura na próxima renovação.",
        NIVEL_VERMELHO:
            "Cobertura de acessórios muito abaixo do perfil típico. "
            "Sinalizar ao subscritor para revisão de apólice.",
    },
    # ---- Exposição (Camada 2 — core_fusao.FATORES_TELEMETRIA) ----
    "inclinacao_g": {
        NIVEL_VERDE:
            "Inclinação estável. Operação em conformidade.",
        NIVEL_AMARELO:
            "Inclinação elevada detectada (>8°). Reduzir velocidade e "
            "verificar nivelamento do equipamento.",
        NIVEL_VERMELHO:
            "INCLINAÇÃO CRÍTICA (≥25°). Risco iminente de capotamento. "
            "Parar operação e não reiniciar sem inspeção presencial.",
    },
    "dist_obstaculo_cm": {
        NIVEL_VERDE:
            "Sem obstáculo relevante à frente.",
        NIVEL_AMARELO:
            "Obstáculo em distância de atenção. Reduzir velocidade.",
        NIVEL_VERMELHO:
            "OBSTÁCULO CRÍTICO (≤35 cm). Parar imediatamente.",
    },
    "vibracao_rms": {
        NIVEL_VERDE:
            "Vibração dentro do padrão — terreno regular.",
        NIVEL_AMARELO:
            "Vibração acima do normal — possível terreno irregular. "
            "Inspecionar fixação de componentes em 48h.",
        NIVEL_VERMELHO:
            "Vibração muito elevada. Risco de dano estrutural — parar e "
            "inspecionar antes de continuar.",
    },
    "umidade_pct": {
        NIVEL_VERDE:
            "Solo com umidade normal — boa aderência.",
        NIVEL_AMARELO:
            "Solo úmido — aderência reduzida. Reduzir velocidade em curvas.",
        NIVEL_VERMELHO:
            "Solo encharcado — risco elevado de atolamento e derrapagem. "
            "Reavaliar rota.",
    },
    "temperatura_c": {
        NIVEL_VERDE:
            "Temperatura ambiente dentro do esperado.",
        NIVEL_AMARELO:
            "Temperatura elevada — atenção à fadiga do operador.",
        NIVEL_VERMELHO:
            "Temperatura extrema — considerar pausa e hidratação do operador.",
    },
}


# =========================================================================
# 4. DTO PUBLICO
# =========================================================================
@dataclass(frozen=True)
class Recomendacao:
    """Resultado imutavel da geracao de recomendacao."""
    nivel: str
    titulo: str
    acao_principal: str
    acao_contextual: Optional[str]
    prazo_acao: str
    prioridade_sla: str
    cor: str
    icone: str

    def to_dict(self) -> dict:
        return {
            "nivel":           self.nivel,
            "titulo":          self.titulo,
            "acao_principal":  self.acao_principal,
            "acao_contextual": self.acao_contextual,
            "prazo_acao":      self.prazo_acao,
            "prioridade_sla":  self.prioridade_sla,
            "cor":             self.cor,
            "icone":           self.icone,
        }

    @property
    def texto_completo(self) -> str:
        partes = [self.acao_principal]
        if self.acao_contextual:
            partes.append(self.acao_contextual)
        partes.append(f"Prazo: {self.prazo_acao}")
        return " · ".join(partes)


# =========================================================================
# 5. FUNCAO PRINCIPAL (lookup canonico)
# =========================================================================
def gerar_recomendacao(
    score: float,
    fator_dominante: Optional[str] = None,
) -> Recomendacao:
    """
    Gera recomendacao acionavel para um score de risco.

    Args:
        score: valor 0-100 do score de risco (saida de core_fusao.fundir
               ou calcular_score_base).
        fator_dominante: nome do campo que mais contribuiu no score.
            Aceita chaves de perfil (IDADE_MAQUINA_ANOS, UF,
            ACESSORIOS_SEGURADOS) ou de telemetria (inclinacao_g,
            dist_obstaculo_cm, vibracao_rms, umidade_pct, temperatura_c).

    Exemplos:
        >>> r = gerar_recomendacao(85, fator_dominante="inclinacao_g")
        >>> r.nivel
        'vermelho'

        >>> r = gerar_recomendacao(25)
        >>> r.nivel
        'verde'
        >>> r.acao_contextual is None
        True
    """
    cfg = faixa_de(score)

    contextual = None
    if fator_dominante and fator_dominante in RECOMENDACOES_CONTEXTUAIS:
        contextual = RECOMENDACOES_CONTEXTUAIS[fator_dominante].get(cfg["nivel"])

    return Recomendacao(
        nivel=cfg["nivel"],
        titulo=cfg["titulo"],
        acao_principal=cfg["acao_principal"],
        acao_contextual=contextual,
        prazo_acao=cfg["prazo_acao"],
        prioridade_sla=cfg["prioridade_sla"],
        cor=cfg["cor"],
        icone=cfg["icone"],
    )


def recomendacoes_por_faixa(score: float) -> list[str]:
    """
    Versao multi-acao: retorna lista de strings prontas para checklist UI.
    Util para US05 (Gestor de Frota) que mostra varias acoes em sequencia.

    Exemplo:
        >>> lst = recomendacoes_por_faixa(85)
        >>> len(lst) >= 3
        True
    """
    cfg = faixa_de(score)
    return [
        f"{cfg['icone']} {cfg['titulo']}",
        cfg["acao_principal"],
        cfg["prazo_acao"],
        f"Prioridade do ticket: {cfg['prioridade_sla']}",
    ]


# =========================================================================
# 6. INTROSPECAO
# =========================================================================
def listar_features_contextuais() -> list[str]:
    """Lista as features que possuem recomendacao contextual cadastrada."""
    return sorted(RECOMENDACOES_CONTEXTUAIS.keys())


# =========================================================================
# 7. METADADOS publicos
# =========================================================================
__all__ = [
    "FAIXAS_ACIONAVEIS",
    "RECOMENDACOES_CONTEXTUAIS",
    "NIVEL_VERDE", "NIVEL_AMARELO", "NIVEL_VERMELHO",
    "Recomendacao",
    "gerar_recomendacao", "recomendacoes_por_faixa",
    "faixa_de", "listar_features_contextuais",
]
