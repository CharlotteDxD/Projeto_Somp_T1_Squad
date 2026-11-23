"""
avaliacao_modelo.py
===================
Harness de avaliacao honesta · Sompo Predict · Sprint 4

Owner: Rafael  ·  Auditoria dos numeros: Guilherme

CORRECAO DE SPRINT 4 (rodada sobre a base real reconstruida)

    Ate a Sprint 3 este script rodava sobre uma base de 149 registros nao
    rastreavel ate o SUSEP (ver core_fusao.py e rastreabilidade_secao_6_1.md
    para o contexto completo da correcao). A base foi reconstruida do zero
    a partir de R_RURAL_2021.csv + S_RURAL_2021.csv (150 registros reais,
    ID_BEM=60, GO/MS/MT). O preparo de features (preparar()) foi corrigido
    para: (1) nao assumir nomes fixos de coluna categorica — a base nova tem
    MODALIDADE_SUSEP no lugar de RAMO_SUSEP — e (2) descartar CAUSA_SINISTRO
    como vazamento, coluna nova que nao existia na base antiga.

O QUE ESTE SCRIPT RESOLVE

    A Sprint 2 registrou "Decision Tree 26,7%" e "MLP 42,2%" sem dizer qual
    metrica, com qual particao, nem contra qual baseline. Com 12 casos criticos
    em 149 registros, um holdout simples deixa 2 ou 3 positivos no teste — a
    diferenca entre 26,7% e 42,2% e indistinguivel do sorteio da particao.

    Este script produz, de uma vez so, tudo que os capitulos de ML, Redes
    Neurais e Estatistica precisam:

      1. Auditoria da base       — suporte por UF, loss ratio, taxa de critico
      2. Comparacao de modelos   — CV repetida, media +- desvio, com baseline
      3. Auditoria SHAP x EDA    — a importancia de UF acompanha risco ou n?
      4. Tabelas markdown        — prontas pra colar no documento mestre

    Nenhum numero deste script deve ser transcrito a mao. Rode, copie a tabela.

DECISOES METODOLOGICAS (defenda estas, nao esconda)

    Alvo binario, nao 4 classes.
        Com 149 linhas, multiclasse com 12 casos na menor classe nao sustenta
        particao. "Critico vs nao-critico" tambem e a decisao de negocio real:
        subscrever com atencao ou nao.

    RepeatedStratifiedKFold 5x10, nao train_test_split.
        50 particoes estratificadas. O desvio entre elas E o resultado: se ele
        for maior que a diferenca entre dois modelos, os modelos empatam.

    DummyClassifier obrigatorio na tabela.
        Modelo que nao bate o aleatorio com folga fora do desvio nao aprendeu
        nada. Sem essa linha, qualquer numero parece bom.

    ROC-AUC e balanced accuracy, nunca accuracy pura.
        Com 8,1% de positivos, chutar "nao-critico" sempre da 91,9% de acuracia
        e zero utilidade.

RODAR
    python3 avaliacao_modelo.py base_sompo_limpa.csv
    python3 avaliacao_modelo.py base_sompo_limpa.csv --sem-shap
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RepeatedStratifiedKFold, cross_validate
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from sklearn.neural_network import MLPClassifier

SEMENTE = 42
N_SPLITS, N_REPEATS = 5, 10
COL_ALVO = "CLASSIFICACAO_RISCO"
VALOR_CRITICO = "Crítico"


# =========================================================================
# 1. AUDITORIA DA BASE
# =========================================================================
def auditar_base(df: pd.DataFrame) -> pd.DataFrame:
    """
    Responde a pergunta que sustenta ou derruba o Ato 4 do pitch:
    a importancia regional vem de RISCO ou de VOLUME?

    Tres medidas lado a lado por UF:
        n          — quantos registros (o volume)
        LR%        — indenizado / premio (a sinistralidade de verdade)
        crit%      — taxa de caso critico dentro da propria UF
    """
    crit = (df[COL_ALVO] == VALOR_CRITICO)
    g = df.groupby("UF")

    t = pd.DataFrame({
        "n": g.size(),
        "pct_base": (g.size() / len(df) * 100).round(1),
        "indeniz": g["VALOR_INDENIZADO_BRL"].sum(),
        "premio": g["PREMIO_LIQUIDO_BRL"].sum(),
        "criticos": crit.groupby(df["UF"]).sum(),
    })
    t["LR_pct"] = (t.indeniz / t.premio * 100).round(1)
    t["crit_pct"] = (t.criticos / t.n * 100).round(1)

    lr_global = df.VALOR_INDENIZADO_BRL.sum() / df.PREMIO_LIQUIDO_BRL.sum() * 100
    t["vs_global"] = np.where(t.LR_pct > lr_global, "acima", "abaixo")

    return t[["n", "pct_base", "LR_pct", "vs_global", "criticos", "crit_pct"]] \
        .sort_values("LR_pct", ascending=False)


def imprimir_auditoria(df: pd.DataFrame) -> pd.DataFrame:
    print("=" * 74)
    print(" 1 · AUDITORIA DA BASE")
    print("=" * 74)
    print(f"  n = {len(df)} registros · {df.UF.nunique()} UFs")

    dist = df[COL_ALVO].value_counts()
    print(f"  alvo: {dict(dist)}")
    taxa = (df[COL_ALVO] == VALOR_CRITICO).mean()
    print(f"  taxa base de caso critico = {taxa*100:.1f}%")

    lr_global = df.VALOR_INDENIZADO_BRL.sum() / df.PREMIO_LIQUIDO_BRL.sum() * 100
    print(f"  loss ratio global = {lr_global:.1f}%\n")

    t = auditar_base(df)
    print(t.to_string())

    lider_vol = t.n.idxmax()
    lider_lr = t.LR_pct.idxmax()
    print()
    print(f"  Maior VOLUME:        {lider_vol} (n={t.n.max()}, "
          f"{t.loc[lider_vol,'pct_base']}% da base)")
    print(f"  Maior SINISTRALIDADE: {lider_lr} (LR={t.LR_pct.max()}%)")
    if lider_vol != lider_lr:
        print(f"  >> {lider_vol} lidera em volume mas NAO em sinistralidade "
              f"(LR={t.loc[lider_vol,'LR_pct']}% vs global {lr_global:.1f}%).")
        print("     Qualquer afirmacao de 'concentracao de risco' baseada em "
              "contagem\n     absoluta esta medindo tamanho de amostra, nao risco.")
    return t


# =========================================================================
# 2. PREPARO
# =========================================================================
def preparar(df: pd.DataFrame, alvo: str = "critico"):
    """
    Monta X e y. Regra dura: nada que derive do alvo entra em X.

    alvo='critico'    -> CLASSIFICACAO_RISCO == 'Crítico'
    alvo='deficitaria'-> indenizado > premio (alternativa atuarialmente util)
    """
    # CAUSA_SINISTRO e vazamento em qualquer alvo: e "Sem sinistro" quando
    # nao houve sinistro e o nome do evento quando houve, entao ela por si
    # so quase entrega CLASSIFICACAO_RISCO=="Baixo". Nao existia na base
    # antiga (Sprint 3); entrou na reconstrucao da Sprint 4 e precisa do
    # mesmo tratamento dado a INTENSIDADE_SINISTRO.
    if alvo == "critico":
        y = (df[COL_ALVO] == VALOR_CRITICO).astype(int)
        descartar = [COL_ALVO, "INTENSIDADE_SINISTRO", "CAUSA_SINISTRO"]
    elif alvo == "subscricao":
        # Mesmo alvo de 'critico', mas SEM as variaveis de desfecho.
        # Premio e valor indenizado existem no historico e nao existem no
        # momento em que o subscritor decide aceitar o risco. Manter as duas
        # produz um modelo que reconhece sinistro ja ocorrido, nao que preve.
        y = (df[COL_ALVO] == VALOR_CRITICO).astype(int)
        descartar = [COL_ALVO, "INTENSIDADE_SINISTRO", "CAUSA_SINISTRO",
                     "PREMIO_LIQUIDO_BRL", "VALOR_INDENIZADO_BRL"]
    elif alvo == "deficitaria":
        y = (df.VALOR_INDENIZADO_BRL > df.PREMIO_LIQUIDO_BRL).astype(int)
        # premio e indenizado DEFINEM o alvo — mante-los seria vazamento
        descartar = [COL_ALVO, "INTENSIDADE_SINISTRO", "CAUSA_SINISTRO",
                     "PREMIO_LIQUIDO_BRL", "VALOR_INDENIZADO_BRL"]
    else:
        raise ValueError(alvo)

    # Deteccao generica de colunas categoricas, em vez de hardcoded
    # ("UF", "RAMO_SUSEP") — a base da Sprint 4 trocou RAMO_SUSEP por
    # MODALIDADE_SUSEP e introduziu CAUSA_SINISTRO. Hardcoded quebrava
    # silenciosamente (astype float em string) a cada mudanca de schema.
    restante = df.drop(columns=[c for c in descartar if c in df.columns])
    # select_dtypes(exclude="number"), nao "== object": pandas >= 2.x pode
    # ler coluna de texto como dtype "str"/StringDtype em vez de "object",
    # dependendo da versao — comparar contra object perdia essas colunas
    # silenciosamente e o restante seguia pro modelo como string crua.
    cat_cols = list(restante.select_dtypes(exclude="number").columns)
    X = pd.get_dummies(restante, columns=cat_cols)
    return X, y


def catalogo_modelos(y: pd.Series) -> dict:
    n_neg, n_pos = int((y == 0).sum()), int((y == 1).sum())
    razao = n_neg / max(n_pos, 1)

    mods = {
        "Dummy (baseline)": DummyClassifier(strategy="stratified",
                                            random_state=SEMENTE),
        "Decision Tree d=3": DecisionTreeClassifier(
            max_depth=3, class_weight="balanced", random_state=SEMENTE),
        "LogReg L2 balanced": make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=2000,
                               random_state=SEMENTE)),
        "Random Forest d=3": RandomForestClassifier(
            max_depth=3, n_estimators=300, class_weight="balanced",
            random_state=SEMENTE),
        "MLP (32,16)": make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=1500,
                          random_state=SEMENTE)),
    }
    try:
        from xgboost import XGBClassifier
        mods["XGBoost d=3"] = XGBClassifier(
            max_depth=3, n_estimators=200, learning_rate=0.05,
            scale_pos_weight=razao, eval_metric="logloss",
            random_state=SEMENTE, verbosity=0)
    except ImportError:
        print("  [aviso] xgboost nao instalado — linha omitida da tabela")
    return mods


# =========================================================================
# 3. COMPARACAO
# =========================================================================
def comparar(X: pd.DataFrame, y: pd.Series, rotulo: str) -> pd.DataFrame:
    """CV repetida em todos os modelos, tres metricas, mesmas particoes."""
    cv = RepeatedStratifiedKFold(n_splits=N_SPLITS, n_repeats=N_REPEATS,
                                 random_state=SEMENTE)
    metricas = ["roc_auc", "f1_macro", "balanced_accuracy"]

    print("\n" + "=" * 74)
    print(f" 2 · COMPARACAO DE MODELOS · alvo: {rotulo}")
    print("=" * 74)
    print(f"  X = {X.shape} · positivos = {int(y.sum())} ({y.mean()*100:.1f}%)")
    print(f"  {N_SPLITS}-fold estratificado x {N_REPEATS} repeticoes "
          f"= {N_SPLITS*N_REPEATS} particoes\n")

    linhas, brutos = [], {}
    for nome, modelo in catalogo_modelos(y).items():
        r = cross_validate(modelo, X, y, cv=cv, scoring=metricas, n_jobs=-1)
        brutos[nome] = r["test_roc_auc"]
        linhas.append({
            "modelo": nome,
            "ROC-AUC": f"{r['test_roc_auc'].mean():.3f} ± {r['test_roc_auc'].std():.3f}",
            "F1-macro": f"{r['test_f1_macro'].mean():.3f} ± {r['test_f1_macro'].std():.3f}",
            "Bal.Acc": f"{r['test_balanced_accuracy'].mean():.3f} ± {r['test_balanced_accuracy'].std():.3f}",
            "_auc": r["test_roc_auc"].mean(),
            "_dp": r["test_roc_auc"].std(),
        })

    tab = pd.DataFrame(linhas)
    print(tab[["modelo", "ROC-AUC", "F1-macro", "Bal.Acc"]].to_string(index=False))
    veredito(tab, brutos)
    return tab


def veredito(tab: pd.DataFrame, brutos: dict) -> None:
    """
    Compara cada modelo com o baseline usando o desvio das particoes.

    Criterio explicito: um modelo so e considerado melhor se a media dele
    superar a media do dummy por mais de um desvio-padrao do dummy. E um
    criterio conservador, e com n=149 e o unico honesto.
    """
    base = tab[tab.modelo.str.startswith("Dummy")].iloc[0]
    auc_b, dp_b = base["_auc"], base["_dp"]

    print(f"\n  Baseline: ROC-AUC {auc_b:.3f} ± {dp_b:.3f}")
    print(f"  Criterio: superar {auc_b + dp_b:.3f} (media + 1 dp do baseline)\n")

    vencedores = []
    for _, r in tab.iterrows():
        if r.modelo.startswith("Dummy"):
            continue
        delta = r["_auc"] - auc_b
        passou = r["_auc"] > auc_b + dp_b
        marca = "SUPERA" if passou else "empata/perde"
        print(f"    {r.modelo:<22} {r['_auc']:.3f}  ({delta:+.3f})  {marca}")
        if passou:
            vencedores.append(r.modelo)

    print()
    if vencedores:
        print(f"  >> Modelos que superam o baseline: {', '.join(vencedores)}")
        print("     Reporte estes com o desvio junto. Nunca a media sozinha.")
    else:
        print("  >> NENHUM modelo supera o baseline aleatorio.")
        print("     Leitura correta: as features disponiveis nao carregam sinal")
        print("     sobre este alvo com n=149. Isso NAO invalida o produto — o")
        print("     score deterministico (core_fusao, Camada 1) continua de pe")
        print("     porque nao depende de aprendizado. O que fica documentado e")
        print("     que volume de dados e o limite duro, e a meta da Sprint 4.")
        print("     Resultado negativo com metodologia correta > metrica inflada.")


# =========================================================================
# 4. SHAP x SUPORTE
# =========================================================================
def auditar_importancia(X, y, aud: pd.DataFrame, usar_shap: bool = True):
    """
    A pergunta: as dummies de UF aparecem no topo por RISCO ou por FREQUENCIA?

    Correlaciona a importancia de cada dummy UF_xx com (a) o n daquela UF e
    (b) o loss ratio daquela UF. Se a correlacao com n for alta e com LR for
    baixa, a "convergencia SHAP x EDA" e artefato de suporte, nao achado.
    """
    print("\n" + "=" * 74)
    print(" 3 · AUDITORIA DE IMPORTANCIA · a UF pesa por risco ou por volume?")
    print("=" * 74)

    modelo = RandomForestClassifier(max_depth=3, n_estimators=400,
                                    class_weight="balanced",
                                    random_state=SEMENTE).fit(X, y)

    imp, fonte = None, ""
    if usar_shap:
        try:
            import shap
            vals = shap.TreeExplainer(modelo).shap_values(X)
            if isinstance(vals, list):
                vals = vals[1]
            if getattr(vals, "ndim", 2) == 3:
                vals = vals[:, :, 1]
            imp = pd.Series(np.abs(vals).mean(axis=0), index=X.columns)
            fonte = "SHAP (|valor| medio)"
        except Exception as e:
            print(f"  [shap indisponivel: {e}] usando importancia do modelo")

    if imp is None:
        imp = pd.Series(modelo.feature_importances_, index=X.columns)
        fonte = "feature_importances_ (Gini)"

    print(f"  fonte da importancia: {fonte}\n")
    print("  Top 8 features:")
    for f, v in imp.sort_values(ascending=False).head(8).items():
        print(f"    {f:<34} {v:.4f}")

    ufs = [c for c in X.columns if c.startswith("UF_")]
    if len(ufs) < 3:
        return

    comp = pd.DataFrame({
        "importancia": [imp[c] for c in ufs],
        "n": [aud.loc[c[3:], "n"] if c[3:] in aud.index else np.nan for c in ufs],
        "LR_pct": [aud.loc[c[3:], "LR_pct"] if c[3:] in aud.index else np.nan
                   for c in ufs],
        "crit_pct": [aud.loc[c[3:], "crit_pct"] if c[3:] in aud.index else np.nan
                     for c in ufs],
    }, index=[c[3:] for c in ufs]).dropna()

    print("\n  Importancia da dummy de UF x caracteristicas reais da UF:")
    print(comp.sort_values("importancia", ascending=False).round(4).to_string())

    r_n = comp.importancia.corr(comp.n)
    r_lr = comp.importancia.corr(comp.LR_pct)
    r_cr = comp.importancia.corr(comp.crit_pct)
    k = len(comp)

    print(f"\n  correlacao(importancia, n)        = {r_n:+.3f}")
    print(f"  correlacao(importancia, LR)       = {r_lr:+.3f}")
    print(f"  correlacao(importancia, crit_pct) = {r_cr:+.3f}")

    # Com k UFs, |r| precisa passar deste valor pra ser distinguivel de ruido
    # (aproximacao de Pearson bicaudal, alfa=0.05).
    limiar = {5: .878, 6: .811, 7: .754, 8: .707, 9: .666, 10: .632}.get(k, .6)
    print(f"  (com {k} UFs, |r| precisa passar de ~{limiar:.2f} "
          f"para ser significante a 5%)\n")

    # Checagem decisiva, independente de correlacao: a UF mais importante para
    # o modelo tem quantos casos positivos de fato?
    top_uf = comp.importancia.idxmax()
    crit_top = comp.loc[top_uf, "crit_pct"]

    if max(abs(r_n), abs(r_lr), abs(r_cr)) < limiar:
        print(f"  >> NENHUMA das correlacoes e significante com {k} UFs. A "
              f"importancia\n     regional nao pode ser atribuida nem a risco "
              f"nem a volume — nao ha\n     evidencia suficiente para nenhuma "
              f"das duas leituras.")
    elif abs(r_n) > max(abs(r_lr), abs(r_cr)):
        print("  >> A importancia acompanha o TAMANHO DA AMOSTRA mais que a")
        print("     sinistralidade: a UF no topo esta la por ter mais linhas.")
    else:
        print("  >> A importancia acompanha a sinistralidade mais que o volume.")

    if crit_top == 0:
        print(f"\n  >> ALERTA: {top_uf} e a UF de MAIOR importancia para o "
              f"modelo e tem\n     ZERO casos criticos na base. O modelo esta "
              f"usando essa dummy para\n     separar negativos, nao para "
              f"identificar risco. Apresentar isso\n     como 'fator de risco "
              f"regional' e leitura errada do SHAP.")

    if abs(r_cr) < limiar or r_cr < 0:
        print(f"\n  >> A correlacao com a taxa real de caso critico e "
              f"{r_cr:+.3f}.\n     Isto e o que derruba a frase 'a EDA e o "
              f"SHAP convergiram de forma\n     independente': as duas leem os "
              f"mesmos {len(X)} registros, e a importancia\n     do modelo nao "
              f"acompanha a taxa de evento observada. Reescreva como\n     "
              f"consistencia interna, nunca como validacao independente.")

    # Features de desfecho: existem no historico mas NAO na hora de subscrever
    desfecho = [c for c in ("VALOR_INDENIZADO_BRL", "PREMIO_LIQUIDO_BRL")
                if c in imp.index]
    if desfecho:
        top5 = list(imp.sort_values(ascending=False).head(5).index)
        no_topo = [c for c in desfecho if c in top5]
        if no_topo:
            print(f"\n  >> ATENCAO A VAZAMENTO DE CONTEXTO: {', '.join(no_topo)} "
                  f"esta(o)\n     entre as 5 features mais importantes. Sao "
                  f"variaveis de DESFECHO —\n     o valor indenizado so existe "
                  f"depois do sinistro. Um modelo de\n     subscricao nao tem "
                  f"acesso a elas no momento da decisao. Para uso\n     "
                  f"preditivo real, retreine sem essas colunas e reporte a "
                  f"queda.")


# =========================================================================
# 5. EXPORTACAO
# =========================================================================
def exportar_markdown(aud: pd.DataFrame, tabs: dict, destino: Path) -> None:
    """Gera o trecho pronto pro documento mestre. Zero digitacao manual."""
    L = ["# Avaliação de modelos · Sompo Predict · Sprint 4", "",
         f"Gerado por `avaliacao_modelo.py` · {N_SPLITS}-fold estratificado × "
         f"{N_REPEATS} repetições ({N_SPLITS*N_REPEATS} partições) · semente {SEMENTE}.",
         "", "## Auditoria da base por UF", "",
         aud.to_markdown(), "",
         "`n` é o número de registros, `LR_pct` a sinistralidade "
         "(indenizado ÷ prêmio) e `crit_pct` a taxa de caso crítico dentro da "
         "própria UF. Ordenado por sinistralidade, não por contagem.", ""]

    for rotulo, tab in tabs.items():
        L += [f"## Comparação de modelos · alvo: {rotulo}", "",
              tab[["modelo", "ROC-AUC", "F1-macro", "Bal.Acc"]].to_markdown(index=False),
              "",
              "Todos os valores são média ± desvio-padrão entre as partições. "
              "O `Dummy (baseline)` é obrigatório na leitura: um modelo cuja "
              "média não supera a do baseline por mais de um desvio não "
              "demonstrou aprendizado.", ""]

    n_total = int(aud["n"].sum())
    n_crit = int(aud["criticos"].sum())
    L += ["## Limitações declaradas", "",
          f"- **n = {n_total}** com {n_crit} casos críticos "
          f"({n_crit/n_total*100:.1f}%). Cada partição de teste contém poucos "
          f"positivos, o que produz desvios largos entre partições.",
          "- **Ausência de série temporal por máquina.** A base é transversal, "
          "sem coluna de data por apólice, o que impede tanto modelagem "
          "recorrente quanto validação temporal.",
          "- **Nenhuma variável de telemetria na base.** Inclinação, vibração e "
          "distância de obstáculo não existem nos registros da SUSEP, portanto "
          "a relação telemetria → sinistro não pode ser aprendida. É por isso "
          "que a Camada 2 do `core_fusao.py` é determinística e calibrada por "
          "limiar, não treinada.",
          "- **Ampliar o volume de dados é a meta explícita da Sprint 4.**", ""]

    destino.write_text("\n".join(L), encoding="utf-8")
    print(f"\n[ok] markdown para o documento mestre: {destino}")


# =========================================================================
def main() -> int:
    ap = argparse.ArgumentParser(description="Avaliacao honesta · Sompo Predict")
    ap.add_argument("base", nargs="?", default="base_sompo_limpa.csv")
    ap.add_argument("--sem-shap", action="store_true")
    ap.add_argument("--saida", default="RESULTADOS_MODELO.md")
    args = ap.parse_args()

    caminho = Path(args.base)
    if not caminho.exists():
        print(f"[erro] base nao encontrada: {caminho}")
        return 1

    df = pd.read_csv(caminho)
    aud = imprimir_auditoria(df)

    tabs = {}
    for alvo, rotulo in [
        ("critico", "caso crítico · todas as colunas"),
        ("subscricao", "caso crítico · apenas variáveis disponíveis na subscrição"),
        ("deficitaria", "apólice deficitária (indenizado > prêmio)"),
    ]:
        X, y = preparar(df, alvo)
        tabs[rotulo] = comparar(X, y, rotulo)

    X, y = preparar(df, "critico")
    auditar_importancia(X, y, aud, usar_shap=not args.sem_shap)

    exportar_markdown(aud, tabs, Path(args.saida))

    print("\n" + "=" * 74)
    print(" O QUE FAZER COM ISTO")
    print("=" * 74)
    print("  · A tabela de comparacao vai inteira no capitulo de ML, com o")
    print("    baseline visivel. Nao publique linha isolada.")
    print("  · A auditoria de UF corrige o Ato 4 do pitch antes do ensaio.")
    print("  · As limitacoes ja estao escritas no markdown — nao as reescreva")
    print("    mais suaves na hora de montar o documento.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
