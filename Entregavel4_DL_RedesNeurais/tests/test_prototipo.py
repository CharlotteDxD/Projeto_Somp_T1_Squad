import prototipo_telemetria as pt


def test_prototipo_pega_o_que_a_regra_nao_ve():
    _, _, _, r, _ = pt.executar()
    assert r["eventos"]["superaquecimento"]["detectados_pela_rede"] >= 0.9
    assert r["eventos"]["superaquecimento"]["disparados_pela_regra"] == 0.0
    assert r["alarme_falso_sequencia_normal"] <= 0.1
    assert r["roc_auc_sequencia"] > 0.9


def test_rede_avisa_antes_da_regra_na_rampa():
    _, _, _, r, _ = pt.executar()
    assert r["eventos"]["rampa"]["antecedencia_media_amostras"] > 5


def test_mesma_semente_mesmo_resultado():
    a = pt.executar()[3]
    b = pt.executar()[3]
    assert a == b
