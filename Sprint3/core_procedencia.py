"""
core_procedencia.py
===================
Fonte única de verdade sobre a origem de cada dado exibido.

PROBLEMA QUE ESTE MÓDULO RESOLVE

    Hoje não é possível saber, olhando a tela, se um número veio da base
    real ou foi gerado. Algumas telas exibem um selo discreto, outras não
    exibem nada. Numa revisão de código isso é pior ainda: a única pista é
    o nome da função conter "mock", o que depende de convenção e não de
    contrato.

    Aqui a procedência vira declaração explícita, verificável por script:

        @sintetico("frota de demonstração",
                   motivo="cadastro real ainda não disponível",
                   substituir_por="data/frota_real.csv")
        def _frota_demo():
            ...

    Com isso:
      · o revisor encontra todo dado sintético com uma busca por @sintetico;
      · a tela exibe o selo automaticamente, sem depender de o autor lembrar;
      · o relatório de procedência é gerado por leitura do registro, não
        por heurística de nome de função.

REGRA DO PROJETO

    Dado gerado nunca aparece ao lado de dado real sem distinção visual.
    Um número inventado ao lado de um resultado verdadeiro derruba a
    credibilidade dos dois.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# =========================================================================
# 1. REGISTRO
# =========================================================================
@dataclass
class Origem:
    """Descreve a procedência de um conjunto de dados."""
    rotulo: str                       # o que é, em linguagem de negócio
    real: bool                        # veio de fonte verificável?
    fonte: str = ""                   # arquivo, serviço ou base de origem
    motivo: str = ""                  # por que é sintético (se for)
    substituir_por: str = ""          # o que precisa chegar para virar real
    funcao: str = ""                  # onde está no código
    modulo: str = ""

    @property
    def situacao(self) -> str:
        return "Real" if self.real else "Demonstração"

    @property
    def cor(self) -> str:
        return "var(--verde)" if self.real else "var(--amarelo)"


REGISTRO: list[Origem] = []


def _registrar(o: Origem) -> None:
    chave = (o.modulo, o.funcao)
    for i, existente in enumerate(REGISTRO):
        if (existente.modulo, existente.funcao) == chave:
            REGISTRO[i] = o
            return
    REGISTRO.append(o)


# =========================================================================
# 2. DECORADORES
# =========================================================================
def sintetico(
    rotulo: str,
    motivo: str = "",
    substituir_por: str = "",
) -> Callable:
    """
    Marca uma função que PRODUZ dado gerado artificialmente.

    Args:
        rotulo: o que o dado representa, em linguagem de negócio.
        motivo: por que ainda é sintético — a justificativa que vai para a
            revisão. "ainda não temos" é resposta; "esqueci" não é.
        substituir_por: o artefato concreto que torna este dado real.
            Preenchido, vira item de backlog rastreável.

    A função decorada ganha o atributo `_origem`, lido pelo scanner e pela
    interface. O comportamento da função não muda.
    """
    def decorador(fn: Callable) -> Callable:
        origem = Origem(
            rotulo=rotulo, real=False, motivo=motivo,
            substituir_por=substituir_por,
            funcao=fn.__name__, modulo=fn.__module__,
        )
        _registrar(origem)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        wrapper._origem = origem          # type: ignore[attr-defined]
        return wrapper
    return decorador


def real(rotulo: str, fonte: str) -> Callable:
    """
    Marca uma função que LÊ dado de fonte verificável.

    Args:
        rotulo: o que o dado representa.
        fonte: arquivo, serviço ou base de origem — precisa ser citável
            em documento.
    """
    def decorador(fn: Callable) -> Callable:
        origem = Origem(
            rotulo=rotulo, real=True, fonte=fonte,
            funcao=fn.__name__, modulo=fn.__module__,
        )
        _registrar(origem)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        wrapper._origem = origem          # type: ignore[attr-defined]
        return wrapper
    return decorador


# =========================================================================
# 3. SELO VISUAL
# =========================================================================
def selo(origem: Origem | str, detalhe: str = "") -> None:
    """
    Renderiza o selo de procedência. Chamar no topo de toda tela que
    exibe dados.

        selo(_frota_demo._origem)
        selo("real", "Base SUSEP · 149 apólices")

    O selo de demonstração é deliberadamente visível: dado gerado
    apresentado como se fosse real é o erro mais caro que este projeto
    pode cometer numa apresentação.
    """
    import streamlit as st

    if isinstance(origem, str):
        eh_real = origem.lower() in ("real", "verdadeiro")
        origem = Origem(rotulo=detalhe or "", real=eh_real, fonte=detalhe)

    if origem.real:
        texto = origem.fonte or origem.rotulo
        st.markdown(f"""
        <div class="pill" style="margin-bottom:1.2rem;border-color:#3FCF8E55;">
            <span class="dot" style="background:var(--verde);
                  box-shadow:0 0 8px var(--verde);"></span>
            <span style="color:var(--text-2);">Dado real · {texto}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        complemento = f" — {origem.motivo}" if origem.motivo else ""
        st.markdown(f"""
        <div style="background:rgba(245,178,61,0.07);
              border:1px solid rgba(245,178,61,0.35);
              border-left:3px solid var(--amarelo);border-radius:10px;
              padding:11px 15px;margin-bottom:1.2rem;">
            <div style="display:flex;align-items:center;gap:9px;">
                <span style="width:7px;height:7px;border-radius:50%;
                      background:var(--amarelo);
                      box-shadow:0 0 8px var(--amarelo);flex:none;"></span>
                <span style="color:var(--amarelo);font-weight:600;
                      font-size:0.82rem;">Dados de demonstração</span>
            </div>
            <div style="font-size:0.78rem;color:var(--text-2);margin-top:5px;
                  line-height:1.55;">
                {origem.rotulo}{complemento}. Os valores ilustram o
                funcionamento da tela e não representam a carteira.
            </div>
        </div>
        """, unsafe_allow_html=True)


# =========================================================================
# 4. RELATÓRIO
# =========================================================================
def inventario() -> list[Origem]:
    """Tudo que foi declarado, ordenado: sintético primeiro."""
    return sorted(REGISTRO, key=lambda o: (o.real, o.modulo, o.funcao))


def resumo() -> tuple[int, int]:
    """(reais, sintéticos)."""
    r = sum(1 for o in REGISTRO if o.real)
    return r, len(REGISTRO) - r


def pendencias() -> list[Origem]:
    """Sintéticos que declararam o que precisa chegar para virarem reais."""
    return [o for o in REGISTRO if not o.real and o.substituir_por]


def origem_por_funcao(modulo: str, funcao: str) -> Origem | None:
    """
    Busca no registro central em vez de ler o atributo `_origem` direto da
    função decorada. Funções também decoradas por st.cache_resource (ou
    qualquer outro decorador empilhado por cima) dependem de o wrapper
    externo propagar atributos customizados — o que costuma funcionar via
    functools.wraps, mas é detalhe de implementação de terceiros, não
    contrato. Buscar pelo nome no registro não depende disso.
    """
    for o in REGISTRO:
        if o.modulo == modulo and o.funcao == funcao:
            return o
    return None


def selo_multiplo(origens: list[Origem], titulo: str = "Dados de demonstração") -> None:
    """
    Selo único para uma tela com MAIS DE UMA fonte sintética. Chamar selo()
    uma vez por função empilharia N caixas amarelas idênticas — aqui os
    motivos entram como lista dentro de um único aviso.
    """
    import streamlit as st

    origens = [o for o in origens if o and not o.real]
    if not origens:
        return

    itens = "".join(
        f'<div style="margin-top:6px;">'
        f'<strong style="color:var(--text);">{o.rotulo}</strong>'
        f'<div style="color:var(--text-2);">{o.motivo}</div></div>'
        for o in origens
    )
    st.markdown(f"""
    <div style="background:rgba(245,178,61,0.07);
          border:1px solid rgba(245,178,61,0.35);
          border-left:3px solid var(--amarelo);border-radius:10px;
          padding:11px 15px;margin-bottom:1.2rem;">
        <div style="display:flex;align-items:center;gap:9px;">
            <span style="width:7px;height:7px;border-radius:50%;
                  background:var(--amarelo);box-shadow:0 0 8px var(--amarelo);
                  flex:none;"></span>
            <span style="color:var(--amarelo);font-weight:600;
                  font-size:0.82rem;">{titulo}</span>
        </div>
        <div style="font-size:0.78rem;line-height:1.55;margin-top:4px;">
            {itens}
        </div>
    </div>
    """, unsafe_allow_html=True)


__all__ = ["Origem", "REGISTRO", "sintetico", "real", "selo", "selo_multiplo",
           "origem_por_funcao", "inventario", "resumo", "pendencias"]
