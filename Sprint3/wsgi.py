"""
wsgi.py
=======
Ponto de entrada de producao do servico de ingestao.

    gunicorn --workers 1 --threads 8 --bind 0.0.0.0:80 wsgi:app

POR QUE UM UNICO WORKER

    O servico mantem estado em memoria: ultima leitura por equipamento,
    serie recente, ultimo numero de sequencia (anti-reenvio) e o avaliador
    de estabilidade do sinalizador.

    Com varios workers, cada processo tem a sua propria copia desse estado.
    O resultado seria: a mesma consulta devolvendo respostas diferentes
    conforme o worker sorteado, o controle de reenvio deixando passar
    duplicatas e o sinalizador oscilando. O sintoma aparece como
    "instabilidade da rede" e leva horas para ser diagnosticado.

    Um worker com varias threads atende o volume desta aplicacao com folga
    — sao leituras de poucos dispositivos por segundo, e o trabalho por
    requisicao e curto. Se um dia o volume exigir mais processos, o estado
    precisa sair para um armazenamento compartilhado (Redis ou banco)
    ANTES de aumentar o numero de workers.

RECUPERACAO APOS REINICIO

    O estado em memoria e perdido a cada reinicio do servico. Como as
    leituras sao persistidas em disco a cada requisicao, este modulo
    recarrega as ultimas linhas na subida — assim uma manutencao nao zera
    o painel nem reabre a janela de reenvio.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Log estruturado para o journal do systemd (stdout) — sem arquivo proprio,
# a rotacao fica a cargo do journald.
logging.basicConfig(
    level=os.environ.get("SOMPO_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("sompo.wsgi")

from api_telemetria import (        # noqa: E402
    ARQUIVO_CSV, JANELA_SERIE, criar_app, _serie, _ultimo, _ultima_seq,
)


def _recuperar_estado() -> None:
    """
    Recarrega as ultimas leituras persistidas para a memoria.

    Sem isto, apos um reinicio o painel mostra "nenhum dispositivo
    transmitindo" ate a proxima leitura chegar, e o controle de reenvio
    aceita numeros de sequencia ja usados.
    """
    if not ARQUIVO_CSV.exists():
        log.info("sem historico em %s — iniciando com estado vazio", ARQUIVO_CSV)
        return

    try:
        import pandas as pd
        df = pd.read_csv(ARQUIVO_CSV).tail(JANELA_SERIE)
        if df.empty:
            return

        for equip_id, grupo in df.groupby("equip_id"):
            registros = grupo.to_dict("records")
            _serie[equip_id].extend(registros)
            _ultimo[equip_id] = {**registros[-1], "frases": [],
                                 "recomendacao": ""}

        for device_id, grupo in df.groupby("device_id"):
            _ultima_seq[device_id] = int(grupo["seq"].max())

        log.info("estado recuperado: %d leituras · %d equipamento(s) · "
                 "%d dispositivo(s)", len(df), len(_ultimo), len(_ultima_seq))
    except Exception as e:
        # Falha na recuperacao nao impede o servico de subir: perder o
        # historico e aceitavel, nao subir nao e.
        log.warning("nao foi possivel recuperar o estado: %s", e)


app = criar_app()
_recuperar_estado()

log.info("servico pronto · persistencia em %s", Path(ARQUIVO_CSV).resolve())
