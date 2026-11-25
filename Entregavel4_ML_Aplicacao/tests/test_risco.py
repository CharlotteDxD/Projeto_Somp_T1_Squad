import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import modelo_exp  # noqa: E402
import risco  # noqa: E402

PERFIL = dict(UF="MT", MODALIDADE_SUSEP="Penhor Rural (financiamento)",
              PREMIO_LIQUIDO_BRL=6500.0, QTD_COBERTURAS_CONTRATADAS=2)


def test_cenarios_da_maquete():
    esperado = {
        "Terreno plano e seco": (55.3, "Baixo"),
        "Rampa moderada": (69.0, "Médio"),
        "Rampa com área úmida": (85.8, "Alto"),
        "Obstáculo muito próximo": (82.7, "Alto"),
    }
    for nome, (score, nivel) in esperado.items():
        a = risco.avaliar(PERFIL, risco.CENARIOS[nome])
        assert a.score_final == pytest.approx(score, abs=0.1), nome
        assert a.nivel == nivel, nome


@pytest.mark.parametrize("cenario", list(risco.CENARIOS))
@pytest.mark.parametrize("modalidade", risco.opcoes()["modalidade"])
def test_fatores_somam_o_score(cenario, modalidade):
    a = risco.avaliar(dict(PERFIL, MODALIDADE_SUSEP=modalidade),
                      risco.CENARIOS[cenario])
    assert sum(f.pontos for f in a.fatores) == pytest.approx(a.score_final, abs=0.3)


def test_regra_de_seguranca_sobrepoe_score_baixo():
    perfil = dict(PERFIL, UF="MS", PREMIO_LIQUIDO_BRL=300.0,
                  QTD_COBERTURAS_CONTRATADAS=6)
    tel = dict(risco.CENARIOS["Terreno plano e seco"], inclinacao_g=27.0)
    a = risco.avaliar(perfil, tel)
    assert a.override and a.nivel == "Alto"
    assert any(f.chave == "regra" for f in a.fatores)


def test_sensor_ausente_nao_penaliza():
    a = risco.avaliar(PERFIL, {})
    assert a.score_final == a.score_base


@pytest.mark.parametrize("troca", [
    {"UF": "SP"},
    {"MODALIDADE_SUSEP": "outra"},
    {"PREMIO_LIQUIDO_BRL": -5.0},
    {"PREMIO_LIQUIDO_BRL": 5e9},
    {"QTD_COBERTURAS_CONTRATADAS": 0},
])
def test_perfil_invalido(troca):
    with pytest.raises(risco.EntradaInvalida):
        risco.avaliar(dict(PERFIL, **troca), {})


def test_telemetria_fora_da_faixa():
    with pytest.raises(risco.EntradaInvalida):
        risco.avaliar(PERFIL, {"inclinacao_g": 120.0})
    with pytest.raises(risco.EntradaInvalida):
        risco.avaliar(PERFIL, {"umidade_pct": -3.0})


def test_frases_produtor_so_falam_de_terreno():
    a = risco.avaliar(PERFIL, risco.CENARIOS["Rampa com área úmida"])
    texto = " ".join(risco.frases_produtor(a, PERFIL, risco.CENARIOS["Rampa com área úmida"]))
    assert "Prêmio" not in texto and "Modalidade" not in texto


def test_modelo_experimental_nao_supera_baseline():
    p = modelo_exp.prever("MT", PERFIL["MODALIDADE_SUSEP"], 2)
    assert 0.0 <= p["probabilidade"] <= 1.0
    t = modelo_exp.validar().set_index("Modelo")
    base = t.loc["Baseline (sorteio estratificado)"]
    lr = t.loc["Regressão logística L2"]
    assert base["ROC-AUC"] == pytest.approx(0.553, abs=0.005)
    assert lr["ROC-AUC"] - base["ROC-AUC"] < lr["Desvio"]


def test_textos_sem_travessao():
    for nome, t in risco.CENARIOS.items():
        a = risco.avaliar(PERFIL, t)
        blob = " ".join([a.recomendacao, *a.frases,
                         *risco.frases_produtor(a, PERFIL, t)])
        assert "—" not in blob and "–" not in blob
