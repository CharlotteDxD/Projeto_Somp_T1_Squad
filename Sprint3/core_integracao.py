"""
core_integracao.py
==================
Camada de integracao — carrega de fato os artefatos externos.

PROBLEMA QUE ESTE MODULO RESOLVE

    O core_data_adapter DECLARA quais arquivos o sistema espera
    (modelo_xgboost.pkl, susep_real.xlsx, frota_real.csv, ...) e desenha um
    selo verde quando o arquivo aparece na pasta. Mas nada era CARREGADO:
    colocar o .pkl em data/ acendia o selo e nao mudava uma linha do
    comportamento do sistema.

    Aqui os artefatos sao carregados de verdade, com tres garantias:

      1. Fallback declarado, nunca silencioso. Se o artefato nao existir, o
         sistema usa o caminho padrao e DIZ que esta usando — nunca finge
         que carregou.
      2. Contrato validado na carga. Um .pkl que nao tem predict_proba, ou
         uma base sem as colunas exigidas, e recusado com mensagem clara em
         vez de estourar tres telas adiante.
      3. Um unico ponto de status. `status_integracoes()` responde o que
         esta conectado e o que esta pendente, para a tela de status e para
         o registro de evidencia.

COMO CADA FRENTE PLUGA O TRABALHO DELA

    Base de apolices      -> data/susep_real.xlsx  ou  base_sompo_limpa.csv
    Modelo de risco       -> data/modelo_xgboost.pkl   (joblib ou pickle)
    Modelo de serie       -> data/modelo_lstm.h5
    Cadastro de frota     -> data/frota_real.csv
    Telemetria historica  -> data/telemetria_esp32.csv
    Telemetria ao vivo    -> variavel SOMPO_API_BASE apontando para a API

    Basta colocar o arquivo na pasta. Nenhuma edicao de codigo.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd

DATA_DIR = Path("data")
API_BASE = os.environ.get("SOMPO_API_BASE", "http://localhost:5000")
TIMEOUT_S = 2.0


# =========================================================================
# 1. DESCRITOR DE INTEGRACAO
# =========================================================================
@dataclass
class Integracao:
    """
    Estado de uma fonte externa. Tres situacoes possiveis, e a distincao
    entre as duas ultimas importa:

        Conectado  — o artefato externo foi carregado e validado.
        Padrão     — o artefato nao existe, mas ha caminho alternativo
                     funcionando (base embutida, score deterministico).
                     O sistema opera normalmente.
        Pendente   — a funcionalidade depende do artefato e esta inativa.

    Marcar tudo que falta como "indisponivel" seria alarme falso: a maior
    parte do sistema funciona sem os artefatos externos.
    """
    chave: str
    rotulo: str
    origem: str                    # onde o artefato deve ser colocado
    conectado: bool
    detalhe: str                   # o que foi carregado, ou por que nao
    critico: bool = False          # ha caminho alternativo funcionando?
    operante: bool = False         # opera mesmo sem o artefato externo

    @property
    def situacao(self) -> str:
        if self.conectado:
            return "Conectado"
        return "Padrão" if self.operante else "Pendente"

    @property
    def cor(self) -> str:
        if self.conectado:
            return "var(--verde)"
        return "var(--amarelo)" if self.operante else "var(--text-3)"


# =========================================================================
# 2. BASE DE APOLICES
# =========================================================================
COLUNAS_APOLICE = {"UF", "RAMO_SUSEP", "IDADE_MAQUINA_ANOS",
                   "ACESSORIOS_SEGURADOS", "PREMIO_LIQUIDO_BRL",
                   "VALOR_INDENIZADO_BRL"}


def carregar_apolices() -> tuple[Optional[pd.DataFrame], Integracao]:
    """
    Base de apolices. Prioridade:
        1. data/susep_real.xlsx    (base ampliada, quando existir)
        2. base_sompo_limpa.csv    (base atual, 149 registros)

    Valida as colunas exigidas pelo motor de score antes de aceitar. Uma
    base ampliada com nome de coluna diferente e recusada aqui, com a lista
    do que falta — nao adiante, com o score zerando em silencio.
    """
    ampliada = DATA_DIR / "susep_real.xlsx"
    if ampliada.exists():
        try:
            df = pd.read_excel(ampliada)
            faltando = COLUNAS_APOLICE - set(df.columns)
            if faltando:
                return _fallback_apolices(
                    f"{ampliada.name} recusado: faltam as colunas "
                    f"{sorted(faltando)}")
            return df, Integracao(
                "apolices", "Base de apólices", str(ampliada), True,
                f"{len(df)} apólices carregadas de {ampliada.name}", True)
        except Exception as e:
            return _fallback_apolices(f"falha ao ler {ampliada.name}: {e}")
    return _fallback_apolices("base ampliada ainda não disponível")


def _fallback_apolices(motivo: str):
    padrao = Path("base_sompo_limpa.csv")
    if not padrao.exists():
        return None, Integracao(
            "apolices", "Base de apólices", "data/susep_real.xlsx", False,
            f"nenhuma base encontrada ({motivo})", True)
    df = pd.read_csv(padrao)
    return df, Integracao(
        "apolices", "Base de apólices", "data/susep_real.xlsx", False,
        f"usando base padrão ({len(df)} registros) — {motivo}",
        True, operante=True)


# =========================================================================
# 3. MODELO DE RISCO SERIALIZADO
# =========================================================================
def carregar_modelo_risco() -> tuple[Optional[Any], Integracao]:
    """
    Modelo treinado (.pkl via joblib ou pickle).

    Exige `predict_proba`. Um objeto sem esse metodo nao serve como modelo
    de risco e e recusado na carga — a alternativa seria descobrir isso na
    frente do cliente, no meio de uma consulta.

    Quando ausente, o sistema opera com o score deterministico de
    core_fusao, que nao depende de modelo treinado.
    """
    caminho = DATA_DIR / "modelo_xgboost.pkl"
    if not caminho.exists():
        return None, Integracao(
            "modelo_risco", "Modelo de risco", str(caminho), False,
            "score determinístico em uso (não depende de modelo treinado)",
            operante=True)

    modelo = None
    try:
        import joblib
        modelo = joblib.load(caminho)
    except Exception:
        try:
            import pickle
            with open(caminho, "rb") as f:
                modelo = pickle.load(f)
        except Exception as e:
            return None, Integracao(
                "modelo_risco", "Modelo de risco", str(caminho), False,
                f"arquivo ilegível: {e}")

    if not hasattr(modelo, "predict_proba"):
        return None, Integracao(
            "modelo_risco", "Modelo de risco", str(caminho), False,
            f"objeto sem predict_proba ({type(modelo).__name__}) — recusado")

    nome = type(modelo).__name__
    n_feat = getattr(modelo, "n_features_in_", "?")
    return modelo, Integracao(
        "modelo_risco", "Modelo de risco", str(caminho), True,
        f"{nome} carregado · {n_feat} variáveis de entrada")


def carregar_modelo_serie() -> tuple[Optional[Any], Integracao]:
    """Modelo de série temporal (.h5). Opcional — usado em detecção de anomalia."""
    caminho = DATA_DIR / "modelo_lstm.h5"
    if not caminho.exists():
        return None, Integracao(
            "modelo_serie", "Modelo de série temporal", str(caminho), False,
            "detecção de anomalia em série indisponível")
    try:
        from tensorflow import keras
        modelo = keras.models.load_model(caminho)
        return modelo, Integracao(
            "modelo_serie", "Modelo de série temporal", str(caminho), True,
            f"modelo carregado · entrada {modelo.input_shape}")
    except ImportError:
        return None, Integracao(
            "modelo_serie", "Modelo de série temporal", str(caminho), False,
            "arquivo presente, mas TensorFlow não instalado")
    except Exception as e:
        return None, Integracao(
            "modelo_serie", "Modelo de série temporal", str(caminho), False,
            f"falha ao carregar: {e}")


# =========================================================================
# 4. CADASTRO DE FROTA
# =========================================================================
def carregar_frota() -> tuple[Optional[pd.DataFrame], Integracao]:
    """
    Cadastro de equipamentos com identificador real. Quando presente,
    substitui os identificadores sintéticos (COL-000...) pelos códigos
    usados na operação.
    """
    caminho = DATA_DIR / "frota_real.csv"
    if not caminho.exists():
        return None, Integracao(
            "frota", "Cadastro de frota", str(caminho), False,
            "identificadores sequenciais em uso (COL-000…)",
            operante=True)
    try:
        df = pd.read_csv(caminho)
        if "equip_id" not in df.columns:
            return None, Integracao(
                "frota", "Cadastro de frota", str(caminho), False,
                "recusado: coluna 'equip_id' ausente")
        return df, Integracao(
            "frota", "Cadastro de frota", str(caminho), True,
            f"{len(df)} equipamentos identificados")
    except Exception as e:
        return None, Integracao(
            "frota", "Cadastro de frota", str(caminho), False,
            f"falha ao ler: {e}")


# =========================================================================
# 5. TELEMETRIA
# =========================================================================
def telemetria_ao_vivo() -> tuple[dict, Integracao]:
    """
    Consulta o serviço de ingestão. Devolve o resumo da frota conectada.

    Não levanta exceção: serviço fora do ar é estado normal enquanto o
    dispositivo não está em campo, e a interface precisa continuar de pé.
    """
    try:
        import requests
    except ImportError:
        return {}, Integracao(
            "telemetria", "Telemetria ao vivo", API_BASE, False,
            "biblioteca requests não instalada")

    try:
        r = requests.get(f"{API_BASE}/telemetria/v1/frota", timeout=TIMEOUT_S)
        if r.status_code == 200:
            dados = r.json()
            n = dados.get("n", 0)
            return dados, Integracao(
                "telemetria", "Telemetria ao vivo", API_BASE, True,
                f"{n} equipamento(s) transmitindo" if n
                else "serviço no ar, aguardando primeira leitura")
    except Exception:
        pass
    return {}, Integracao(
        "telemetria", "Telemetria ao vivo", API_BASE, False,
        f"serviço não responde em {API_BASE}")


def serie_telemetria(equip_id: str, n: int = 200) -> Optional[pd.DataFrame]:
    """Série histórica de um equipamento, direto do serviço de ingestão."""
    try:
        import requests
        r = requests.get(f"{API_BASE}/telemetria/v1/serie/{equip_id}",
                         params={"n": n}, timeout=TIMEOUT_S)
        if r.status_code == 200:
            amostras = r.json().get("amostras", [])
            if amostras:
                return pd.DataFrame(amostras)
    except Exception:
        pass
    return None


def telemetria_historica() -> tuple[Optional[pd.DataFrame], Integracao]:
    """Arquivo de leituras acumuladas, usado quando o serviço está fora."""
    for caminho in (DATA_DIR / "telemetria_esp32.csv",
                    Path("telemetria_ingerida.csv"),
                    Path("telemetria_esp32.csv")):
        if caminho.exists():
            try:
                df = pd.read_csv(caminho)
                return df, Integracao(
                    "telemetria_hist", "Telemetria acumulada", str(caminho),
                    True, f"{len(df)} leituras registradas")
            except Exception:
                continue
    return None, Integracao(
        "telemetria_hist", "Telemetria acumulada",
        "data/telemetria_esp32.csv", False, "nenhum registro acumulado")


# =========================================================================
# 6. STATUS CONSOLIDADO
# =========================================================================
def status_integracoes() -> list[Integracao]:
    """
    Estado de todas as fontes externas, em uma chamada.
    Usado pela tela de status e pelo registro de evidência.
    """
    _, i_apo = carregar_apolices()
    _, i_mod = carregar_modelo_risco()
    _, i_ser = carregar_modelo_serie()
    _, i_fro = carregar_frota()
    _, i_tel = telemetria_ao_vivo()
    _, i_his = telemetria_historica()
    return [i_apo, i_tel, i_mod, i_fro, i_ser, i_his]


def resumo_integracoes() -> tuple[int, int]:
    """(conectadas, total) — para indicador compacto."""
    todas = status_integracoes()
    return sum(1 for i in todas if i.conectado), len(todas)


__all__ = [
    "Integracao", "API_BASE",
    "carregar_apolices", "carregar_modelo_risco", "carregar_modelo_serie",
    "carregar_frota", "telemetria_ao_vivo", "serie_telemetria",
    "telemetria_historica", "status_integracoes", "resumo_integracoes",
]
