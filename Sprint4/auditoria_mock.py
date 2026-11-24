"""
auditoria_mock.py
=================
Varredura de dado ficticio e numero sem procedencia · Sompo Predict · Sprint 3

Owner: Rafael  ·  Executor recorrente: Guilherme (auditoria dos numeros)

POR QUE ESTE SCRIPT EXISTE

    Dois riscos ja registrados no plano da sprint:

      "Dado ficticio nunca ao lado de dado real. Juntos na mesma tela,
       derrubam a credibilidade dos dois."
      "Dado real, nunca gerado — com fonte citada." (regra da materia)

    Conferir isso a mao antes do congelamento de 23/ago nao escala: sao ~10 mil
    linhas de Python. Este script varre o repositorio e devolve um inventario
    classificado por gravidade, com a correcao sugerida para cada ocorrencia.

    Rode antes de cada entrega. Idealmente vira um passo do checklist de
    congelamento.

O QUE ELE PROCURA

    BLOQUEADOR  geracao de dado sintetico (np.random, faker, seed + uniform)
                alimentando tela ou metrica. Viola a regra da materia.
    ALTO        numero de negocio afirmado sem fonte (ROI, %, R$ milhoes)
    MEDIO       constante numerica de frota/carteira divergente da base real
    BAIXO       TODO, FIXME, placeholder declarado

RODAR
    python3 auditoria_mock.py .
    python3 auditoria_mock.py . --base base_sompo_limpa.csv
    python3 auditoria_mock.py . --md INVENTARIO_MOCK.md
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

IGNORAR_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
                "site-packages", ".ipynb_checkpoints"}


@dataclass
class Achado:
    gravidade: str
    arquivo: str
    linha: int
    trecho: str
    motivo: str
    correcao: str


# =========================================================================
# REGRAS
# =========================================================================
REGRAS: list[tuple[str, str, str, str]] = [
    # (gravidade, regex, motivo, correcao)
    ("BLOQUEADOR", r"np\.random\.(uniform|randint|normal|choice|rand)\b",
     "Gera valor artificial em tempo de execucao",
     "Trocar por leitura da base real ou da telemetria ingerida. Se for "
     "estritamente ilustrativo, isolar em modulo de demo e rotular na tela."),

    ("BLOQUEADOR",
     r"\b\w*rng\w*\.(uniform|integers|normal|choice|poisson|gamma|beta|"
     r"exponential|standard_normal|random)\s*\(",
     "Gera valor artificial via API Generator do numpy (np.random.default_rng)",
     "Mesmo problema do np.random.X classico, sintaxe diferente — "
     "np.random.default_rng().poisson(...) etc tambem e geracao sintetica. "
     "Trocar por leitura da base real."),

    ("BLOQUEADOR", r"np\.random\.default_rng\s*\(",
     "Instancia gerador de numeros aleatorios (Generator API) — sinal de "
     "que a funcao provavelmente produz dado sintetico",
     "Confirmar se o resultado alimenta tela/metrica. Se sim, mesma "
     "correcao dos outros bloqueadores de geracao sintetica."),

    ("BLOQUEADOR", r"np\.random\.seed|random\.seed",
     "Semente fixa — indica geracao sintetica reproduzivel, nao dado real",
     "Semente so se justifica em particao de validacao. Em geracao de dado "
     "de tela, remover junto com o gerador."),

    ("BLOQUEADOR", r"\b(faker|Faker|make_classification|make_blobs)\b",
     "Biblioteca de dado sintetico",
     "Remover. A materia proibe dado gerado."),

    ("ALTO", r"\bROI\b.{0,40}?(\d{2,4}\s*%|\d+x\b)",
     "Afirmacao de retorno financeiro sem fonte",
     "Ou citar a premissa de calculo linha a linha, ou trocar por faixa "
     "com a hipotese explicita ('assumindo X, a ordem de grandeza seria Y')."),

    ("ALTO", r"R\$\s?\d+([.,]\d+)?\s*(M|MM|mi|milh|bi|B)\b",
     "Valor monetario de negocio afirmado",
     "Mostrar a conta ou marcar como projecao hipotetica na propria tela."),

    ("ALTO", r"(redu\w*|evitad\w*|preven\w*|antecipa\w*).{0,30}?\d{1,3}\s*%",
     "Percentual de eficacia do produto — nao ha medicao que sustente",
     "O produto nao rodou em campo. Reescrever como objetivo, nao resultado."),

    ("ALTO", r"\bpayback\b.{0,30}?\d",
     "Prazo de retorno afirmado sem modelo de custo",
     "Remover ou apresentar junto da planilha de premissas."),

    ("ALTO", r"(AUC|ROC|acuracia|acurácia|accuracy|F1)\W{0,4}\d?[.,]\d+",
     "Metrica de modelo escrita como constante",
     "Toda metrica vem do RESULTADOS_MODELO.md gerado por avaliacao_modelo.py. "
     "Numero de metrica nunca digitado a mao."),

    ("BAIXO", r"#\s*(TODO|FIXME|HACK|XXX|placeholder|mock)\b",
     "Pendencia declarada no codigo",
     "Fechar ou registrar como limitacao no documento."),
]

# Nomes que sugerem funcao produtora de dado ficticio
PADRAO_FUNCAO_MOCK = re.compile(
    r"def\s+(_?\w*(mock|fake|dummy|sintetic|simulad|exemplo)\w*)\s*\(", re.I)


def _e_comentario(linha: str) -> bool:
    t = linha.strip()
    return t.startswith("#") or t.startswith('"""') or t.startswith("'''")


def varrer_arquivo(caminho: Path, raiz: Path) -> list[Achado]:
    achados: list[Achado] = []
    try:
        linhas = caminho.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return achados

    rel = str(caminho.relative_to(raiz))

    for i, linha in enumerate(linhas, 1):
        if _e_comentario(linha):
            continue

        for gravidade, padrao, motivo, correcao in REGRAS:
            if re.search(padrao, linha, re.I):
                achados.append(Achado(gravidade, rel, i, linha.strip()[:110],
                                      motivo, correcao))
                break     # uma regra por linha, a mais grave que casar

        m = PADRAO_FUNCAO_MOCK.search(linha)
        if m:
            achados.append(Achado(
                "BLOQUEADOR", rel, i, linha.strip()[:110],
                f"Funcao '{m.group(1)}' produz dado ficticio por nome",
                "Se alimenta tela de apresentacao, substituir pela base real. "
                "Se e fixture de teste, mover para tests/ e deixar claro."))
    return achados


def conferir_constantes(raiz: Path, base: Path) -> list[Achado]:
    """
    Procura numeros da carteira escritos como constante que divirjam da base.

    Este e o caso concreto ja apontado no plano da sprint: a tela mostra
    Frota=150 e Criticos=1 enquanto a base real tem 149 e 12.
    """
    if not base.exists():
        return []

    df = pd.read_csv(base)
    n_real = len(df)
    n_crit = int((df["CLASSIFICACAO_RISCO"] == "Crítico").sum()) \
        if "CLASSIFICACAO_RISCO" in df.columns else None

    # Numeros "redondos" perto do real sao o padrao classico do placeholder
    suspeitos = {str(n_real + d) for d in (-1, 1, 51)} | {"100", "150", "200", "500"}
    achados: list[Achado] = []

    for arq in sorted(raiz.rglob("*.py")):
        if any(p in IGNORAR_DIRS for p in arq.parts):
            continue
        try:
            linhas = arq.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        rel = str(arq.relative_to(raiz))

        for i, linha in enumerate(linhas, 1):
            if _e_comentario(linha):
                continue
            if not re.search(r"frota|carteira|apolice|apólice|total|equipament",
                             linha, re.I):
                continue
            for num in re.findall(r"\b(\d{2,4})\b", linha):
                if num in suspeitos and num != str(n_real):
                    achados.append(Achado(
                        "MEDIO", rel, i, linha.strip()[:110],
                        f"Constante {num} em contexto de frota/carteira; "
                        f"a base real tem {n_real} registros"
                        + (f" e {n_crit} criticos" if n_crit is not None else ""),
                        f"Substituir por len(df) lido da base. Numero de "
                        f"carteira nunca literal no codigo."))
                    break
    return achados


# =========================================================================
def relatorio(achados: list[Achado], base_info: str) -> str:
    ordem = {"BLOQUEADOR": 0, "ALTO": 1, "MEDIO": 2, "BAIXO": 3}
    achados = sorted(achados, key=lambda a: (ordem[a.gravidade], a.arquivo, a.linha))

    L = ["# Inventário de dado fictício e número sem procedência", "",
         "Gerado por `auditoria_mock.py`. " + base_info, ""]

    cont = {g: sum(1 for a in achados if a.gravidade == g) for g in ordem}
    L += ["| gravidade | ocorrências |", "|---|---|"]
    L += [f"| {g} | {cont[g]} |" for g in ordem]
    L += ["", "**Regra de corte:** nenhum BLOQUEADOR pode sobreviver ao "
          "congelamento de 23/ago. ALTO só passa se o número tiver a premissa "
          "escrita ao lado, na mesma tela.", ""]

    for g in ordem:
        do_nivel = [a for a in achados if a.gravidade == g]
        if not do_nivel:
            continue
        L += [f"## {g} · {len(do_nivel)} ocorrência(s)", ""]
        arquivo_atual = None
        for a in do_nivel:
            if a.arquivo != arquivo_atual:
                arquivo_atual = a.arquivo
                L += [f"### `{a.arquivo}`", ""]
            L += [f"- **linha {a.linha}** — {a.motivo}",
                  f"  ```python",
                  f"  {a.trecho}",
                  f"  ```",
                  f"  *Correção:* {a.correcao}", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Varredura de mock · Sompo Predict")
    ap.add_argument("raiz", nargs="?", default=".")
    ap.add_argument("--base", default="base_sompo_limpa.csv")
    ap.add_argument("--md", default="INVENTARIO_MOCK.md")
    args = ap.parse_args()

    raiz = Path(args.raiz).resolve()
    if not raiz.exists():
        print(f"[erro] caminho nao encontrado: {raiz}")
        return 1

    achados: list[Achado] = []
    n_arq = 0
    for arq in sorted(raiz.rglob("*.py")):
        if any(p in IGNORAR_DIRS for p in arq.parts):
            continue
        if arq.name in ("auditoria_mock.py", "avaliacao_modelo.py"):
            continue          # o proprio ferramental usa seed legitimamente
        n_arq += 1
        achados += varrer_arquivo(arq, raiz)

    base = Path(args.base)
    achados += conferir_constantes(raiz, base)
    base_info = (f"Base de referência: `{base.name}`." if base.exists()
                 else "Base não encontrada — checagem de constantes pulada.")

    ordem = ["BLOQUEADOR", "ALTO", "MEDIO", "BAIXO"]
    cont = {g: sum(1 for a in achados if a.gravidade == g) for g in ordem}

    print("=" * 72)
    print(" AUDITORIA DE MOCK · Sompo Predict")
    print("=" * 72)
    print(f"  {n_arq} arquivos varridos · {len(achados)} ocorrencias\n")
    for g in ordem:
        print(f"    {g:<12} {cont[g]:>3}")

    print("\n  Top ocorrencias por arquivo:")
    if achados:
        por_arq = pd.Series([a.arquivo for a in achados]).value_counts().head(8)
        for arq, n in por_arq.items():
            print(f"    {n:>3}  {arq}")

    Path(args.md).write_text(relatorio(achados, base_info), encoding="utf-8")
    print(f"\n[ok] inventario detalhado: {args.md}")

    if cont["BLOQUEADOR"]:
        print(f"\n  >> {cont['BLOQUEADOR']} BLOQUEADOR(es). Dado gerado "
              f"artificialmente alimentando\n     tela viola a regra da materia "
              f"de dados. Resolver antes de 23/ago.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
