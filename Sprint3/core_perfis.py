"""
core_perfis.py
==============
Definição dos dois portais que a plataforma serve.

    Portal da Seguradora  — subscritor, analista, gestor de carteira
    Portal do Segurado    — produtor rural, operador de máquina

POR QUE UM CÓDIGO SÓ, E NÃO DOIS PROJETOS

    Os dois portais mostram o MESMO risco calculado da MESMA forma — a
    diferença está em quanto de detalhe cada público precisa ver. Duplicar
    o código faria as duas versões divergirem na primeira correção que
    alguém esquecesse de replicar, e o pior sintoma possível é o farol do
    produtor discordar do score do subscritor.

    Aqui existe um núcleo único. Este módulo apenas descreve, para cada
    portal, quais telas aparecem, com que nomes e sob qual identidade.

COMO EXECUTAR CADA UM

    Seguradora (padrão):
        streamlit run app.py

    Segurado:
        # Windows PowerShell
        $env:SOMPO_PERFIL = "cliente"
        streamlit run app.py --server.port 8502

    Os dois podem rodar ao mesmo tempo, em portas diferentes — é assim que
    se demonstra os dois lados lado a lado.

CONTROLE DE ACESSO

    O perfil define o que o portal OFERECE. O papel do usuário define o que
    ele PODE ver. Um usuário Segurado que entre no portal da seguradora
    continua restrito às telas de segurado: a verificação de papel acontece
    dentro de cada tela, independentemente do portal.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


# =========================================================================
# 1. DESCRITOR DE PORTAL
# =========================================================================
@dataclass(frozen=True)
class Portal:
    """Configuração completa de um portal."""
    chave: str
    nome: str                      # título da aba do navegador
    marca: str                     # nome exibido na barra lateral
    tagline: str                   # subtítulo da tela inicial
    grupos: dict                   # menu: {grupo: {rótulo: id_rota}}
    inicial: str                   # rota de entrada
    papeis_aceitos: tuple          # papéis que este portal atende
    porta_sugerida: int

    @property
    def itens(self) -> dict:
        """Mapa achatado {rótulo: id_rota}."""
        return {rot: pid for g in self.grupos.values() for rot, pid in g.items()}

    @property
    def rotas_permitidas(self) -> set:
        return set(self.itens.values())


# =========================================================================
# 2. PORTAL DA SEGURADORA
# =========================================================================
PORTAL_SEGURADORA = Portal(
    chave="sompo",
    nome="Sompo Predict",
    marca="Sompo Predict",
    tagline="Prevenção de risco em seguro rural",
    inicial="inicio",
    papeis_aceitos=("Admin", "Subscritor", "Analista", "Cientista", "Operador"),
    porta_sugerida=8501,
    grupos={
        "": {
            "Visão Geral":                  "inicio",
        },
        "Monitoramento": {
            "Carteira de Risco":            "us01_risco",
            "Frota Monitorada":             "us05_gestor",
            "Sensores em Campo":            "iot",
        },
        "Subscrição e Sinistros": {
            "Relatório de Risco":           "relatorios",
            "Análise de Sinistros":         "us08_sinistros",
            "Parecer de Subscrição":        "us07_xai",
            "Simulador de Cenários":        "simulador",
            "Base de Apólices":             "dados",
        },
        "Plataforma": {
            "Modelos Preditivos":           "ml_dl",
            "Desempenho dos Modelos":       "metricas",
            "Explicabilidade":              "xai",
            "Infraestrutura":               "cloud",
            "Segurança e Acessos":          "seguranca",
            "Fontes de Dados":              "integracoes",
            "Trilha de Auditoria":          "auditoria",
            "Modo Apresentação":            "demo",
        },
    },
)


# =========================================================================
# 3. PORTAL DO SEGURADO
# =========================================================================
# Deliberadamente curto. O produtor rural abre isto no celular, no meio da
# lavoura, muitas vezes com luva. Cinco itens, sem submenu, sem jargão.
# Cada tela removida daqui foi removida por uma razão:
#   · carteira e ranking      -> informação de outro cliente, não é dele
#   · modelos e explicabilidade -> detalhe técnico que não muda a decisão dele
#   · infraestrutura e auditoria -> operação interna da seguradora
PORTAL_SEGURADO = Portal(
    chave="cliente",
    nome="Minha Máquina",
    marca="Minha Máquina",
    tagline="Acompanhe seu equipamento em tempo real",
    inicial="us03_cliente",
    papeis_aceitos=("Admin", "Segurado", "Operador"),
    porta_sugerida=8502,
    grupos={
        "": {
            "Situação agora":               "us03_cliente",
            "Histórico do equipamento":     "meu_equipamento",
            "Simular condições":            "simulador",
            "Meus dados e privacidade":     "seguranca",
        },
    },
)


PORTAIS = {p.chave: p for p in (PORTAL_SEGURADORA, PORTAL_SEGURADO)}


# =========================================================================
# 4. SELEÇÃO EM TEMPO DE EXECUÇÃO
# =========================================================================
def portal_ativo() -> Portal:
    """
    Portal desta instância, definido por SOMPO_PERFIL. Valor desconhecido
    cai no portal da seguradora — é o padrão seguro, porque o controle de
    papel dentro de cada tela continua valendo de qualquer forma.
    """
    chave = os.environ.get("SOMPO_PERFIL", "sompo").strip().lower()
    return PORTAIS.get(chave, PORTAL_SEGURADORA)


def rota_permitida(portal: Portal, rota: str) -> bool:
    """A rota pertence ao menu deste portal?"""
    return rota in portal.rotas_permitidas


def portal_para_papel(papel: str) -> Portal:
    """
    Portal apropriado a um papel. Usado no login: um Segurado que acesse a
    porta da seguradora é levado às telas dele, não a uma tela de erro.
    """
    if papel == "Segurado":
        return PORTAL_SEGURADO
    return PORTAL_SEGURADORA


__all__ = ["Portal", "PORTAL_SEGURADORA", "PORTAL_SEGURADO", "PORTAIS",
           "portal_ativo", "rota_permitida", "portal_para_papel"]
