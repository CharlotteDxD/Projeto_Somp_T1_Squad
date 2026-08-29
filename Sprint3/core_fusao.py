"""
core_fusao.py
=============
Motor de score de duas camadas · Sompo Predict · Sprint 3

Owner: Rafael  ·  Reviewers: Charles (consumo), Gustavo (API), Guilherme (dados)

SUBSTITUI core_scoring.py. Motivo da substituicao, documentado para o relatorio:

    core_scoring.py exigia 12 features (freq_sinistros_3y, prox_corpo_dagua_km,
    velocidade_avg_kmh, ...) das quais NENHUMA existe em base_sompo_limpa.csv.
    Como o modulo tratava feature ausente como contribuicao 0.0 sem erro, o peso
    morto era 1.00 e o score_l1 retornava 0.0 para as 149 apolices — a carteira
    inteira classificada como verde, sem caminho possivel para vermelho.
    Verificado em 10/ago/2026.

ARQUITETURA · duas camadas com papeis distintos

    Camada 1 — PERFIL (lenta, atuarial)
        Deriva de colunas que existem de fato na SUSEP: UF, RAMO_SUSEP,
        IDADE_MAQUINA_ANOS, ACESSORIOS_SEGURADOS. Muda de mes em mes.

    Camada 2 — EXPOSICAO (rapida, telemetria)
        Fatores agravantes instantaneos vindos do ESP32. Mudam a cada segundo.

    score_final = clip( score_base * (1 + K * SUM(w_i * a_i)), 0, 100 )

    Mais um OVERRIDE DE SEGURANCA: limiar critico de inclinacao ou obstaculo
    forca faixa vermelha independentemente do score. Regra de seguranca se
    sobrepoe a modelo estatistico — padrao de sistema embarcado critico.

HONESTIDADE METODOLOGICA (vai no capitulo de ML, nao se esconde)

    Os pesos w_i da Camada 2 NAO sao aprendidos. Nao podem ser: a base SUSEP nao
    contem inclinacao, vibracao nem distancia de obstaculo, logo nao existe par
    (telemetria, sinistro) para treinar. Sao juizo de especialista com limiar
    justificado na literatura. Aprende-los e meta declarada da Sprint 4.

    Ja o mapa de risco por UF da Camada 1 E derivado dos dados, via credibilidade
    de Buhlmann-Straub — ver secao 2. Isso corrige um erro concreto do modulo
    anterior, que atribuia peso maximo (1.00) ao MT, estado que tem ZERO casos
    criticos nos 149 registros.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

SCHEMA_V = "1.0"
VERSAO_MOTOR = "2.0.0"

# =========================================================================
# 1. CAMADA 1 · PESOS SOBRE COLUNAS QUE EXISTEM DE FATO
# =========================================================================
# Contrato duro: toda chave aqui TEM que ser uma coluna de base_sompo_limpa.csv.
# validar_contrato_base() falha alto se alguem quebrar isso.

PESOS_PERFIL: dict[str, dict[str, Any]] = {
    "IDADE_MAQUINA_ANOS": {
        "peso": 0.40, "norm": "linear", "cutoff": 15.0,
        "just": "Maquina de 15+ anos e o ponto de obsolescencia usado como "
                "saturacao. Maior peso porque e a unica variavel continua da "
                "base com leitura fisica direta de desgaste.",
    },
    "UF": {
        "peso": 0.25, "norm": "credibilidade",
        "just": "Mapa derivado da taxa de caso critico observada por UF, "
                "suavizada por credibilidade de Buhlmann-Straub (secao 2). "
                "Nao e chumbado.",
    },
    "ACESSORIOS_SEGURADOS": {
        "peso": 0.20, "norm": "inversa", "cutoff": 12.0,
        "just": "Nos 149 registros, apolices deficitarias (indenizado > premio) "
                "tem media 4.7 acessorios contra 5.9 das superavitarias. "
                "Mais cobertura contratada associa-se a perfil melhor. "
                "Correlacao fraca — por isso peso intermediario.",
    },
    "RAMO_SUSEP": {
        "peso": 0.15, "norm": "categorico",
        "mapping": {"0621 - agrícola": 0.85, "0622 - penhor rural": 0.60,
                    "0631 - benfeitorias e produtos agropecuários": 0.55,
                    "0635 - penhor rural - instituição financeira": 0.50},
        "default": 0.60,
        "just": "Agricola concentra exposicao a evento de campo; penhor rural e "
                "predominantemente garantia financeira. Menor peso porque a "
                "base tem poucos niveis e distribuicao desbalanceada.",
    },
}

_SOMA_PERFIL = sum(v["peso"] for v in PESOS_PERFIL.values())
assert abs(_SOMA_PERFIL - 1.0) < 1e-9, (
    f"core_fusao: pesos de perfil somam {_SOMA_PERFIL:.6f}, deveriam somar 1.0"
)

# =========================================================================
# 2. CAMADA 2 · FATORES DE EXPOSICAO (telemetria do contrato v1.0)
# =========================================================================
# Chaves espelham exatamente CONTRATO_TELEMETRIA_v1.md secao 2.1.
# `critico` marca o limiar que dispara override de seguranca.

FATORES_TELEMETRIA: dict[str, dict[str, Any]] = {
    "inclinacao_g": {
        "peso": 0.45, "norm": "linear_offset", "offset": 8.0, "cutoff": 17.0,
        "critico": 25.0, "sentido": "acima",
        "just": "Comeca a pesar a 8 graus (limite de conforto operacional em "
                "encosta) e satura a 25. Limiar critico em 25 por margem sobre "
                "o angulo de tombamento estatico tipico de colheitadeira. "
                "MAIOR PESO: tombamento e o sinistro-alvo do projeto.",
    },
    "dist_obstaculo_cm": {
        "peso": 0.25, "norm": "inversa", "cutoff": 120.0,
        "critico": 35.0, "sentido": "abaixo",
        "just": "Neutro a 120 cm, risco maximo em contato. Critico a 35 cm — "
                "distancia de parada da maquete na velocidade da demo.",
    },
    "vibracao_rms": {
        "peso": 0.15, "norm": "linear_offset", "offset": 0.5, "cutoff": 2.5,
        "critico": None,
        "just": "Proxy de terreno irregular e de folga mecanica. Peso baixo "
                "porque o sinal e ruidoso e o MPU6050 nao e acelerometro "
                "industrial. Nao dispara override sozinho.",
    },
    "umidade_pct": {
        "peso": 0.10, "norm": "linear_offset", "offset": 60.0, "cutoff": 35.0,
        "critico": None,
        "just": "Solo encharcado reduz aderencia e e o fator ambiental exigido "
                "pelo desafio. Sinal indireto (umidade do ar, nao do solo) — "
                "limitacao declarada.",
    },
    "temperatura_c": {
        "peso": 0.05, "norm": "linear_offset", "offset": 35.0, "cutoff": 15.0,
        "critico": None,
        "just": "Ambiente, nao motor. Entra por completude do fator climatico "
                "com o menor peso do conjunto.",
    },
}

_SOMA_TEL = sum(v["peso"] for v in FATORES_TELEMETRIA.values())
assert abs(_SOMA_TEL - 1.0) < 1e-9, (
    f"core_fusao: pesos de telemetria somam {_SOMA_TEL:.6f}, deveriam somar 1.0"
)

# Amplitude maxima do agravamento: telemetria em estresse total multiplica o
# score de perfil por (1 + K).
#
# K=1.5 foi calibrado empiricamente contra os tres cenarios da maquete, com o
# equipamento de demonstracao (score_base ~55) e as faixas nos percentis 60/90:
#     terreno plano seco  -> ~55  VERDE
#     rampa moderada      -> ~69  AMARELO
#     rampa + area umida  -> ~86  VERMELHO
# Com K=2.0 a rampa moderada ja saltava para vermelho e o estado intermediario
# desaparecia da demo. Com K<1.0 a telemetria vira ruido em cima do perfil.
# Este numero e um parametro de projeto declarado, nao um valor aprendido.
K_AGRAVAMENTO = 1.5

FAIXAS = (
    (0.0, 40.0, "verde", "Operação normal."),
    (40.0, 75.0, "amarelo", "Reduza a velocidade e redobre a atenção."),
    (75.0, 100.01, "vermelho", "Risco elevado — avalie interromper a operação."),
)

# Credibilidade: k = numero de observacoes para atribuir peso 50% a experiencia
# propria da UF. k=30 escolhido porque a maior UF da base tem n=29 — nenhuma
# UF recebe credibilidade plena, o que e o comportamento correto com n=149.
CREDIBILIDADE_K = 30.0


# =========================================================================
# 3. NORMALIZADORES PUROS
# =========================================================================
def _arr(x) -> np.ndarray:
    if isinstance(x, pd.Series):
        return x.to_numpy(dtype=float, na_value=np.nan)
    return np.asarray(x, dtype=float)


def _n_linear(x, cutoff: float) -> np.ndarray:
    return np.clip(_arr(x) / cutoff, 0.0, 1.0)


def _n_linear_offset(x, offset: float, cutoff: float) -> np.ndarray:
    return np.clip((_arr(x) - offset) / cutoff, 0.0, 1.0)


def _n_inversa(x, cutoff: float) -> np.ndarray:
    """Proximidade: 0 -> risco maximo, cutoff -> neutro. -1 (sem eco) = neutro."""
    v = _arr(x)
    v = np.where(v < 0, cutoff, v)          # -1 do HC-SR04 = nada a frente
    return np.clip(1.0 - (v / cutoff), 0.0, 1.0)


def _n_categorico(x, mapping: dict, default: float) -> np.ndarray:
    s = pd.Series(x).astype(str).str.strip().str.lower()
    return s.map(mapping).fillna(default).to_numpy(dtype=float)


def mapa_uf_credibilidade(
    df: pd.DataFrame,
    col_uf: str = "UF",
    col_alvo: str = "CLASSIFICACAO_RISCO",
    valor_critico: str = "Crítico",
    k: float = CREDIBILIDADE_K,
) -> dict[str, float]:
    """
    Deriva o risco relativo por UF a partir dos dados, com suavizacao de
    credibilidade de Buhlmann-Straub:

        Z_uf       = n_uf / (n_uf + k)
        taxa_ajust = Z * taxa_observada_uf + (1 - Z) * taxa_global

    Por que isso importa: com 12 casos criticos em 8 estados, a taxa bruta de
    uma UF com n=16 e ruido puro. A suavizacao puxa UFs pequenas na direcao da
    media global e so deixa UFs grandes se afastarem.

    Corrige um erro concreto do motor anterior, que dava peso 1.00 ao MT — o
    estado com ZERO casos criticos na base.

    Retorna dict {uf_minuscula: risco_normalizado_0_1}.
    """
    crit = (df[col_alvo] == valor_critico).astype(int)
    taxa_global = float(crit.mean())

    g = df.groupby(df[col_uf].astype(str).str.strip().str.lower())
    n = g.size().astype(float)
    taxa_obs = crit.groupby(df[col_uf].astype(str).str.strip().str.lower()).mean()

    z = n / (n + k)
    ajustada = z * taxa_obs + (1.0 - z) * taxa_global

    # Normaliza para [0, 1] preservando a ordenacao relativa
    lo, hi = ajustada.min(), ajustada.max()
    if hi - lo < 1e-12:
        return {uf: 0.5 for uf in ajustada.index}
    return {uf: float((v - lo) / (hi - lo)) for uf, v in ajustada.items()}


# =========================================================================
# 4. VALIDACAO DE CONTRATO — falha alto, nunca em silencio
# =========================================================================
class ContratoBaseError(RuntimeError):
    """Base nao tem as colunas que o motor exige."""


def validar_contrato_base(df: pd.DataFrame) -> None:
    """
    Levanta se qualquer coluna de PESOS_PERFIL estiver ausente.

    Existe exatamente para impedir a repeticao da falha de core_scoring.py, que
    devolvia score 0.0 para a carteira inteira sem uma linha de aviso.
    """
    faltando = [c for c in PESOS_PERFIL if c not in df.columns]
    if faltando:
        peso_morto = sum(PESOS_PERFIL[c]["peso"] for c in faltando)
        raise ContratoBaseError(
            f"Colunas ausentes: {faltando}. Peso morto = {peso_morto:.2f}, "
            f"teto do score = {(1 - peso_morto) * 100:.1f} pontos. "
            f"Corrija o nome das colunas ou o mapeamento — NAO calcule assim."
        )


# =========================================================================
# 5. CAMADA 1 · SCORE DE PERFIL
# =========================================================================
def calcular_score_base(
    df: pd.DataFrame,
    mapa_uf: Optional[dict[str, float]] = None,
) -> pd.DataFrame:
    """
    Score 0-100 de perfil do equipamento. Vetorizado.

    Adiciona: score_base, <COLUNA>_contrib (pontos) por feature.
    `mapa_uf` ausente => derivado do proprio df por credibilidade.
    """
    validar_contrato_base(df)
    if mapa_uf is None:
        mapa_uf = mapa_uf_credibilidade(df)

    out = df.copy()
    total = np.zeros(len(df), dtype=float)

    for col, cfg in PESOS_PERFIL.items():
        modo = cfg["norm"]
        if modo == "linear":
            v = _n_linear(df[col], cfg["cutoff"])
        elif modo == "inversa":
            v = _n_inversa(df[col], cfg["cutoff"])
        elif modo == "categorico":
            v = _n_categorico(df[col], cfg["mapping"], cfg["default"])
        elif modo == "credibilidade":
            v = _n_categorico(df[col], mapa_uf, 0.5)
        else:
            raise ValueError(f"normalizador desconhecido: {modo}")

        v = np.nan_to_num(v, nan=0.5)          # NaN vira neutro, nao zero
        pontos = v * cfg["peso"] * 100.0
        out[f"{col}_contrib"] = np.round(pontos, 2)
        total += pontos

    out["score_base"] = np.round(np.clip(total, 0.0, 100.0), 1)
    return out


# =========================================================================
# 6. CAMADA 2 · FATOR DE EXPOSICAO
# =========================================================================
@dataclass(frozen=True)
class ResultadoFusao:
    score_base: float
    score_final: float
    faixa: str
    recomendacao: str
    override_seguranca: bool
    motivo_override: Optional[str]
    agravantes: dict[str, float] = field(default_factory=dict)
    frases: list[str] = field(default_factory=list)
    versao: str = VERSAO_MOTOR

    def to_dict(self) -> dict[str, Any]:
        return {
            "score_base": self.score_base,
            "score_final": self.score_final,
            "faixa": self.faixa,
            "recomendacao": self.recomendacao,
            "override_seguranca": self.override_seguranca,
            "motivo_override": self.motivo_override,
            "agravantes": dict(self.agravantes),
            "frases": list(self.frases),
            "versao_motor": self.versao,
        }


def _normalizar_fator(valor: Optional[float], cfg: dict) -> float:
    """Um campo de telemetria -> [0, 1]. None (sensor falhou) = 0.0, nao penaliza."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return 0.0
    modo = cfg["norm"]
    if modo == "linear":
        return float(_n_linear([valor], cfg["cutoff"])[0])
    if modo == "linear_offset":
        return float(_n_linear_offset([valor], cfg["offset"], cfg["cutoff"])[0])
    if modo == "inversa":
        return float(_n_inversa([valor], cfg["cutoff"])[0])
    raise ValueError(f"normalizador desconhecido: {modo}")


def _checar_override(tel: dict[str, Optional[float]]) -> Optional[str]:
    """
    Regra de seguranca acima do score. Retorna o motivo, ou None.

    Justificativa para o relatorio: sistema de alerta critico nao pode depender
    de um numero continuo cruzar uma faixa. Inclinacao de 26 graus e vermelho
    mesmo que o perfil da maquina seja excelente.
    """
    for campo, cfg in FATORES_TELEMETRIA.items():
        lim = cfg.get("critico")
        if lim is None:
            continue
        v = tel.get(campo)
        if v is None:
            continue
        if cfg["sentido"] == "acima" and v >= lim:
            return f"{campo}>={lim:g}"
        if cfg["sentido"] == "abaixo" and 0 <= v <= lim:
            return f"{campo}<={lim:g}"
    return None


def calibrar_faixas(
    df: pd.DataFrame,
    p_amarelo: float = 0.60,
    p_vermelho: float = 0.90,
) -> tuple[float, float]:
    """
    Deriva os cortes verde/amarelo/vermelho dos percentis empiricos do
    score_base na carteira, e REESCREVE FAIXAS no modulo.

    Por que nao usar 40 e 75 fixos: a soma ponderada nao produz uma escala
    ancorada. Com os pesos atuais a media da carteira SUSEP cai em ~54, o que
    classificaria quase toda a base como amarela e tornaria o farol inutil.

    O SCORE_README.md da Sprint 2 afirmava que 40 e 75 eram "proximos aos
    percentis 60 e 90 da distribuicao empirica" — nao eram, porque o score
    daquele modulo era identicamente zero. Esta funcao torna a afirmacao
    verdadeira: calcula os percentis de fato e devolve os numeros usados.

    Alvo: ~60% verde, ~30% amarelo, ~10% vermelho, coerente com a taxa de caso
    critico observada (8,1%).
    """
    global FAIXAS
    base = calcular_score_base(df)["score_base"]
    c1 = float(np.round(base.quantile(p_amarelo), 1))
    c2 = float(np.round(base.quantile(p_vermelho), 1))
    FAIXAS = (
        (0.0, c1, "verde", "Operação normal."),
        (c1, c2, "amarelo", "Reduza a velocidade e redobre a atenção."),
        (c2, 1e9, "vermelho", "Risco elevado — avalie interromper a operação."),
    )
    return c1, c2


def classificar(score: float) -> tuple[str, str]:
    for lo, hi, faixa, rec in FAIXAS:
        if lo <= score < hi:
            return faixa, rec
    return "vermelho", FAIXAS[-1][3]


def _gerar_frases(
    perfil: dict[str, Any],
    tel: dict[str, Optional[float]],
    agravantes: dict[str, float],
) -> list[str]:
    """
    Traduz os dois maiores agravantes + o perfil em portugues de produtor rural.
    Nada de nome de feature, nada de numero de modelo. Alimenta a tela do Charles
    e a US07 do Rafael.
    """
    frases: list[str] = []
    # Ordena pela CONTRIBUICAO PONDERADA (w_i * a_i), nao pelo valor normalizado.
    # Sem isso, umidade a 65% (a=0.14, w=0.10) apareceria na frente de inclinacao
    # a 14 graus (a=0.35, w=0.45), que e o fator que realmente puxou o score.
    top = sorted(
        ((c, FATORES_TELEMETRIA[c]["peso"] * a) for c, a in agravantes.items()),
        key=lambda kv: kv[1], reverse=True,
    )

    molde = {
        "inclinacao_g": lambda v: f"Inclinação de {v:.0f}° — terreno em declive acentuado.",
        "dist_obstaculo_cm": lambda v: f"Obstáculo a {v:.0f} cm à frente da máquina.",
        "vibracao_rms": lambda v: "Vibração acima do normal — terreno irregular.",
        "umidade_pct": lambda v: f"Umidade em {v:.0f}% — solo encharcado reduz a aderência.",
        "temperatura_c": lambda v: f"Temperatura ambiente de {v:.0f}°C.",
    }
    for campo, contrib in top[:2]:
        if contrib <= 0.02:
            continue
        v = tel.get(campo)
        if v is not None and campo in molde:
            frases.append(molde[campo](v))

    idade = perfil.get("IDADE_MAQUINA_ANOS")
    if idade is not None and float(idade) >= 10:
        frases.append(
            f"Máquina com {float(idade):.0f} anos — faixa etária de maior "
            f"severidade no histórico do setor."
        )

    if not frases:
        frases.append("Nenhum fator de risco relevante detectado neste momento.")
    return frases


def fundir(
    score_base: float,
    telemetria: dict[str, Optional[float]],
    perfil: Optional[dict[str, Any]] = None,
    k: float = K_AGRAVAMENTO,
) -> ResultadoFusao:
    """
    Funcao publica principal. Combina perfil (lento) e telemetria (rapido).

        score_final = clip( score_base * (1 + k * SUM(w_i * a_i)), 0, 100 )

    >>> r = fundir(34.0, {"inclinacao_g": 14.0, "dist_obstaculo_cm": 42.0,
    ...                   "vibracao_rms": 0.9, "umidade_pct": 78.0,
    ...                   "temperatura_c": 31.0},
    ...            perfil={"IDADE_MAQUINA_ANOS": 12})
    >>> r.faixa
    'amarelo'
    >>> fundir(34.0, {"inclinacao_g": 27.0}).faixa
    'vermelho'
    """
    perfil = perfil or {}
    agravantes: dict[str, float] = {}
    soma = 0.0

    for campo, cfg in FATORES_TELEMETRIA.items():
        a = _normalizar_fator(telemetria.get(campo), cfg)
        agravantes[campo] = round(a, 3)
        soma += cfg["peso"] * a

    score_final = float(np.clip(score_base * (1.0 + k * soma), 0.0, 100.0))
    motivo = _checar_override(telemetria)

    if motivo is not None:
        faixa, recomendacao = "vermelho", FAIXAS[-1][3]
        score_final = max(score_final, FAIXAS[2][0])  # coerencia com a faixa calibrada
    else:
        faixa, recomendacao = classificar(score_final)

    return ResultadoFusao(
        score_base=round(float(score_base), 1),
        score_final=round(score_final, 1),
        faixa=faixa,
        recomendacao=recomendacao,
        override_seguranca=motivo is not None,
        motivo_override=motivo,
        agravantes=agravantes,
        frases=_gerar_frases(perfil, telemetria, agravantes),
    )


# =========================================================================
# 7. HISTERESE · evita o farol piscando
# =========================================================================
class AvaliadorEstavel:
    """
    Estabiliza a faixa exigindo persistencia antes de mudar de estado.

    Sem isso, um solavanco isolado faz o farol piscar vermelho e a demo parece
    quebrada. Assimetria deliberada: sobe rapido (2 leituras) e desce devagar
    (5 leituras) — em sistema de seguranca o custo de subir a toa e menor que o
    de descer cedo demais.

    Override de seguranca ignora a histerese: sobe na hora.
    """
    ORDEM = {"verde": 0, "amarelo": 1, "vermelho": 2}

    def __init__(self, n_subir: int = 2, n_descer: int = 5) -> None:
        self.n_subir, self.n_descer = n_subir, n_descer
        self.estado = "verde"
        self._candidato: Optional[str] = None
        self._contagem = 0

    def atualizar(self, res: ResultadoFusao) -> str:
        nova = res.faixa

        if res.override_seguranca:
            self.estado, self._candidato, self._contagem = nova, None, 0
            return self.estado

        if nova == self.estado:
            self._candidato, self._contagem = None, 0
            return self.estado

        if nova != self._candidato:
            self._candidato, self._contagem = nova, 1
        else:
            self._contagem += 1

        subindo = self.ORDEM[nova] > self.ORDEM[self.estado]
        if self._contagem >= (self.n_subir if subindo else self.n_descer):
            self.estado, self._candidato, self._contagem = nova, None, 0
        return self.estado


# =========================================================================
# 8. LOTE — para dashboard e ranking de frota
# =========================================================================
def calcular_lote(
    df: pd.DataFrame,
    telemetria_por_equip: Optional[dict[str, dict]] = None,
) -> pd.DataFrame:
    """
    Score da carteira inteira. Sem telemetria, score_final == score_base.
    `telemetria_por_equip` mapeia indice ou equip_id -> dict de telemetria.
    """
    out = calcular_score_base(df)
    tel_map = telemetria_por_equip or {}

    finais, faixas, overrides = [], [], []
    for idx, linha in out.iterrows():
        chave = linha.get("equip_id", idx)
        tel = tel_map.get(chave, {})
        r = fundir(float(linha["score_base"]), tel, perfil=linha.to_dict())
        finais.append(r.score_final)
        faixas.append(r.faixa)
        overrides.append(r.override_seguranca)

    out["score_final"] = finais
    out["faixa_risco"] = faixas
    out["override_seguranca"] = overrides
    return out


def descrever_pesos() -> pd.DataFrame:
    """Tabela de pesos com justificativa — cola direto no relatorio."""
    linhas = [
        {"camada": "perfil", "fator": k, "peso": v["peso"], "justificativa": v["just"]}
        for k, v in PESOS_PERFIL.items()
    ] + [
        {"camada": "telemetria", "fator": k, "peso": v["peso"], "justificativa": v["just"]}
        for k, v in FATORES_TELEMETRIA.items()
    ]
    return pd.DataFrame(linhas)


__all__ = [
    "PESOS_PERFIL", "FATORES_TELEMETRIA", "FAIXAS", "K_AGRAVAMENTO",
    "ResultadoFusao", "ContratoBaseError", "AvaliadorEstavel",
    "validar_contrato_base", "mapa_uf_credibilidade",
    "calcular_score_base", "fundir", "calcular_lote",
    "classificar", "descrever_pesos",
]


if __name__ == "__main__":
    import sys
    caminho = sys.argv[1] if len(sys.argv) > 1 else "base_sompo_limpa.csv"
    base = pd.read_csv(caminho)

    print("=" * 66)
    print("MAPA DE UF POR CREDIBILIDADE (Buhlmann-Straub, k=30)")
    print("=" * 66)
    for uf, v in sorted(mapa_uf_credibilidade(base).items(),
                        key=lambda kv: -kv[1]):
        print(f"  {uf.upper():<4} risco relativo {v:.3f}")

    c1, c2 = calibrar_faixas(base)
    scored = calcular_score_base(base)
    print("\nscore_base: min=%.1f  max=%.1f  media=%.1f" % (
        scored.score_base.min(), scored.score_base.max(), scored.score_base.mean()))
    print("cortes calibrados (p60/p90): verde <%.1f | amarelo <%.1f | vermelho >=%.1f"
          % (c1, c2, c2))
    dist = scored.score_base.apply(lambda s: classificar(s)[0]).value_counts()
    print("distribuicao da carteira:", dist.to_dict())

    print("\n" + "=" * 66)
    print("FUSAO · mesma maquina, tres cenarios de campo")
    print("=" * 66)
    exemplo = scored.iloc[0]
    cenarios = {
        "campo normal": {"inclinacao_g": 3.0, "dist_obstaculo_cm": 200.0,
                         "vibracao_rms": 0.4, "umidade_pct": 45.0,
                         "temperatura_c": 28.0},
        "terreno irreg.": {"inclinacao_g": 10.0, "dist_obstaculo_cm": 150.0,
                           "vibracao_rms": 0.8, "umidade_pct": 65.0,
                           "temperatura_c": 30.0},
        "encosta umida": {"inclinacao_g": 14.0, "dist_obstaculo_cm": 90.0,
                          "vibracao_rms": 1.4, "umidade_pct": 82.0,
                          "temperatura_c": 33.0},
        "obstaculo": {"inclinacao_g": 16.0, "dist_obstaculo_cm": 28.0,
                      "vibracao_rms": 1.9, "umidade_pct": 82.0,
                      "temperatura_c": 33.0},
    }
    for nome, tel in cenarios.items():
        r = fundir(float(exemplo.score_base), tel, perfil=exemplo.to_dict())
        flag = f"  [OVERRIDE: {r.motivo_override}]" if r.override_seguranca else ""
        print(f"\n  {nome:<14} base {r.score_base:5.1f} -> final {r.score_final:5.1f}"
              f"  {r.faixa.upper()}{flag}")
        for f in r.frases:
            print(f"       · {f}")
