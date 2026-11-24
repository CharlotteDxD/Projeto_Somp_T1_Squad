"""
auditoria_procedencia.py
========================
Auditoria de procedência de dados — apoio à revisão final (R11).

DIFERENÇA PARA O auditoria_mock.py

    O scanner anterior contava ocorrências de geração artificial. Útil, mas
    trata igual dois casos muito diferentes:

        · um gráfico ilustrativo, com selo de demonstração na tela;
        · uma tabela de sinistros gerada, exibida sem aviso nenhum.

    O primeiro é uma escolha de produto. O segundo é o erro que derruba a
    credibilidade da apresentação inteira. Este script separa os dois.

CLASSIFICAÇÃO

    CRÍTICO   dado gerado exibido SEM identificação na tela.
              O espectador não tem como saber que é fictício.

    DECLARADO dado gerado, mas com selo de procedência visível.
              Aceitável — é decisão de escopo, não engano.

    SEM_MARCA gerador presente no código sem declaração @sintetico.
              Não necessariamente exibido, mas invisível para a revisão.

    REAL      função que lê fonte verificável, declarada com @real.

USO
    python3 auditoria_procedencia.py .
    python3 auditoria_procedencia.py . --md PROCEDENCIA_DADOS.md
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

IGNORAR = {".git", "__pycache__", "node_modules", ".venv", "venv", "data"}

# Chamadas que indicam geração artificial
PADRAO_GERACAO = re.compile(
    r"\b(np\.random\.\w+|rng\.\w+|random\.\w+|"
    r"np\.random\.default_rng|make_classification|make_blobs|Faker)\s*\(")

# Sinais de que a tela identifica a procedência
PADRAO_SELO = re.compile(
    r"(procedencia\.selo|selo\s*\(|status_dados\s*\(|"
    r"Dados de demonstração|MODO DEMONSTRAÇÃO|modo demonstração|"
    r"FONTE: DADO SIMULADO|dados de demonstração|_badge_fonte)", re.I)


@dataclass
class Achado:
    classe: str
    arquivo: str
    funcao: str
    linha: int
    detalhe: str
    acao: str


def _funcoes_com_geracao(caminho: Path) -> list[tuple[str, int, int, bool]]:
    """
    Retorna [(nome_funcao, linha_ini, n_chamadas_geracao, tem_decorador)].
    Usa AST: nome de função não é critério, chamada de gerador é.
    """
    try:
        src = caminho.read_text(encoding="utf-8", errors="ignore")
        arvore = ast.parse(src)
    except Exception:
        return []

    linhas = src.split("\n")
    resultado = []

    for no in ast.walk(arvore):
        if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        ini = no.lineno
        fim = getattr(no, "end_lineno", ini)
        corpo = "\n".join(linhas[ini - 1:fim])
        n_ger = len(PADRAO_GERACAO.findall(corpo))
        if n_ger == 0:
            continue
        decorado = any(
            (isinstance(d, ast.Call) and getattr(d.func, "id", "") in
             ("sintetico", "real"))
            or getattr(d, "id", "") in ("sintetico", "real")
            or (isinstance(d, ast.Attribute) and d.attr in ("sintetico", "real"))
            for d in no.decorator_list)
        resultado.append((no.name, ini, n_ger, decorado))
    return resultado


def _tela_identifica(caminho: Path) -> bool:
    """A tela exibe alguma identificação de procedência?"""
    try:
        src = caminho.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return bool(PADRAO_SELO.search(src))


def _eh_tela(caminho: Path) -> bool:
    """Arquivo que renderiza interface (exibe dado para alguém)."""
    try:
        src = caminho.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return "streamlit" in src and ("def render" in src or "def pagina_" in src)


def auditar(raiz: Path) -> list[Achado]:
    achados: list[Achado] = []

    for arq in sorted(raiz.rglob("*.py")):
        if any(p in IGNORAR for p in arq.parts):
            continue
        if arq.name in ("auditoria_procedencia.py", "auditoria_mock.py",
                        "avaliacao_modelo.py", "core_procedencia.py"):
            continue

        geradores = _funcoes_com_geracao(arq)
        if not geradores:
            continue

        rel = str(arq.relative_to(raiz))
        tela = _eh_tela(arq)
        identifica = _tela_identifica(arq)

        for nome, linha, n_ger, decorado in geradores:
            if decorado:
                achados.append(Achado(
                    "DECLARADO", rel, nome, linha,
                    f"{n_ger} chamada(s) de geração, com declaração explícita",
                    "nenhuma — procedência declarada no código"))
            elif tela and not identifica:
                achados.append(Achado(
                    "CRITICO", rel, nome, linha,
                    f"{n_ger} chamada(s) de geração numa tela que NÃO "
                    f"identifica a procedência",
                    "decorar com @sintetico e chamar procedencia.selo() "
                    "no topo da tela"))
            elif tela and identifica:
                achados.append(Achado(
                    "SEM_MARCA", rel, nome, linha,
                    f"{n_ger} chamada(s) de geração; a tela identifica a "
                    f"procedência, mas a função não está declarada",
                    "decorar com @sintetico para aparecer no inventário"))
            else:
                achados.append(Achado(
                    "SEM_MARCA", rel, nome, linha,
                    f"{n_ger} chamada(s) de geração fora de tela",
                    "decorar com @sintetico, ou remover se não for usada"))

    ordem = {"CRITICO": 0, "SEM_MARCA": 1, "DECLARADO": 2, "REAL": 3}
    return sorted(achados, key=lambda a: (ordem[a.classe], a.arquivo, a.linha))


def relatorio_md(achados: list[Achado], raiz: Path) -> str:
    cont = {c: sum(1 for a in achados if a.classe == c)
            for c in ("CRITICO", "SEM_MARCA", "DECLARADO")}

    L = ["# Procedência dos dados — apoio à revisão final",
         "",
         "Gerado por `auditoria_procedencia.py`. Cada entrada é uma função "
         "que produz dados artificialmente, classificada pelo risco que "
         "representa numa apresentação.",
         "",
         "| Classificação | Ocorrências | Significado |",
         "|---|---|---|",
         f"| Crítico | {cont['CRITICO']} | Dado gerado exibido **sem "
         f"identificação** — o espectador não tem como saber que é fictício |",
         f"| Sem marca | {cont['SEM_MARCA']} | Gerador não declarado no "
         f"código; invisível para a revisão |",
         f"| Declarado | {cont['DECLARADO']} | Gerado, porém com procedência "
         f"explícita — aceitável |",
         "",
         "**Critério de aceite da revisão:** zero ocorrências em Crítico. "
         "Entradas em Declarado podem permanecer, desde que a justificativa "
         "esteja preenchida.",
         ""]

    rotulos = {"CRITICO": "Crítico — exibido sem identificação",
               "SEM_MARCA": "Sem marca — não declarado no código",
               "DECLARADO": "Declarado — procedência explícita"}

    for classe in ("CRITICO", "SEM_MARCA", "DECLARADO"):
        deste = [a for a in achados if a.classe == classe]
        if not deste:
            continue
        L += [f"## {rotulos[classe]} · {len(deste)}", ""]
        arquivo_atual = None
        for a in deste:
            if a.arquivo != arquivo_atual:
                arquivo_atual = a.arquivo
                L += ["", f"### `{a.arquivo}`", ""]
            L += [f"- **`{a.funcao}()`** — linha {a.linha}",
                  f"  - {a.detalhe}",
                  f"  - *Ação:* {a.acao}"]
        L.append("")

    L += ["## Como declarar procedência", "",
          "```python",
          "from core_procedencia import sintetico, real, selo",
          "",
          '@sintetico("frota de demonstração",',
          '           motivo="cadastro real ainda não disponível",',
          '           substituir_por="data/frota_real.csv")',
          "def _frota_demo():",
          "    ...",
          "",
          "# no topo da tela que exibe:",
          "selo(_frota_demo._origem)",
          "```",
          "",
          "A função decorada entra no inventário automaticamente e a tela "
          "passa a exibir o aviso sem depender de o autor lembrar.",
          ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Auditoria de procedência")
    ap.add_argument("raiz", nargs="?", default=".")
    ap.add_argument("--md", default="PROCEDENCIA_DADOS.md")
    args = ap.parse_args()

    raiz = Path(args.raiz).resolve()
    achados = auditar(raiz)

    cont = {c: sum(1 for a in achados if a.classe == c)
            for c in ("CRITICO", "SEM_MARCA", "DECLARADO")}

    print("=" * 68)
    print("  PROCEDÊNCIA DOS DADOS — revisão final")
    print("=" * 68)
    print(f"  {len(achados)} função(ões) que geram dados artificialmente\n")
    print(f"    CRÍTICO    {cont['CRITICO']:>3}   exibido sem identificação")
    print(f"    SEM MARCA  {cont['SEM_MARCA']:>3}   não declarado no código")
    print(f"    DECLARADO  {cont['DECLARADO']:>3}   procedência explícita")

    if cont["CRITICO"]:
        print("\n  Exibição sem identificação — prioridade da revisão:\n")
        for a in achados:
            if a.classe != "CRITICO":
                continue
            print(f"    {a.arquivo}:{a.linha}")
            print(f"      {a.funcao}() — {a.detalhe}")

    Path(args.md).write_text(relatorio_md(achados, raiz), encoding="utf-8")
    print(f"\n  Relatório: {args.md}")

    return 2 if cont["CRITICO"] else 0


if __name__ == "__main__":
    sys.exit(main())
