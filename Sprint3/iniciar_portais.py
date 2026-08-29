#!/usr/bin/env python3
"""
iniciar_portais.py
==================
Sobe os dois portais ao mesmo tempo, em portas diferentes.

    python iniciar_portais.py

    Portal da Seguradora  ->  http://localhost:8501
    Portal do Segurado    ->  http://localhost:8502

É o mesmo código rodando duas vezes, com SOMPO_PERFIL diferente. Não são
dois sistemas: é um sistema servindo dois públicos.

PARA A DEMONSTRAÇÃO

    Abra as duas janelas lado a lado. Incline a máquina na maquete e as
    duas reagem à mesma leitura — o segurado vê o sinalizador mudar de cor,
    a seguradora vê a apólice subir no ranking de exposição. Mostrar isso
    simultaneamente comunica a arquitetura melhor do que qualquer diagrama.

Encerrar: Ctrl+C encerra os dois.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

from core_perfis import PORTAL_SEGURADO, PORTAL_SEGURADORA

PORTAIS = [PORTAL_SEGURADORA, PORTAL_SEGURADO]
processos: list[subprocess.Popen] = []


def _subir(portal, porta: int) -> subprocess.Popen:
    ambiente = {**os.environ, "SOMPO_PERFIL": portal.chave}
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", str(porta),
         "--server.headless", "true"],
        env=ambiente,
    )


def _encerrar(*_):
    print("\n  Encerrando os portais...")
    for p in processos:
        try:
            p.terminate()
        except Exception:
            pass
    for p in processos:
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
    print("  Encerrados.\n")
    sys.exit(0)


def main() -> int:
    signal.signal(signal.SIGINT, _encerrar)
    signal.signal(signal.SIGTERM, _encerrar)

    linha = "=" * 62
    print(f"\n{linha}")
    print("  SOMPO PREDICT — DOIS PORTAIS")
    print(linha)

    for portal in PORTAIS:
        porta = portal.porta_sugerida
        processos.append(_subir(portal, porta))
        print(f"\n  {portal.marca}")
        print(f"    {portal.tagline}")
        print(f"    http://localhost:{porta}")
        print(f"    {len(portal.itens)} telas · papéis: "
              f"{', '.join(portal.papeis_aceitos)}")
        time.sleep(2)

    print(f"\n{linha}")
    print("  Contas de demonstração")
    print(f"{linha}")
    print("    Seguradora:  admin     / Admin@2024!")
    print("    Segurado:    produtor  / Produtor@2024!")
    print()
    print("  O segurado não enxerga a carteira: o papel dele não tem")
    print("  permissão de leitura da base de apólices, e o portal dele")
    print("  não oferece essas telas.")
    print(f"{linha}")
    print("  Ctrl+C encerra os dois.\n")

    try:
        while True:
            time.sleep(1)
            for p in processos:
                if p.poll() is not None:
                    print("  Um dos portais encerrou. Finalizando o outro.")
                    _encerrar()
    except KeyboardInterrupt:
        _encerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
