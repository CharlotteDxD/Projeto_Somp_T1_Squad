"""
api_telemetria.py
=================
Endpoint de ingestao de telemetria do ESP32 · Sompo Predict · Sprint 3

Owner: Gustavo (transporte/infra)  ·  Consumidor: Charles (menu e dashboard)
Produtor: Anthony (ESP32)          ·  Score: Rafael (core_fusao)

Implementa CONTRATO_TELEMETRIA_v1.md. Roda standalone ou como Blueprint
registrado dentro de api_dados.py.

RODAR (bancada):
    export SOMPO_HMAC_T1_CART_01="chave-de-32-bytes-no-minimo-troque-isto"
    python3 api_telemetria.py

RODAR (EC2, porta 80 — ver contrato secao 1.2):
    sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))
    PORT=80 nohup python3 api_telemetria.py > api.log 2>&1 &

INTEGRAR no api_dados.py do Gustavo:
    from api_telemetria import bp_telemetria
    app.register_blueprint(bp_telemetria)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from flask import Blueprint, Flask, jsonify, request

import core_fusao as cf

SCHEMA_V = "1.0"
JANELA_SERIE = 5000           # amostras em memoria por equipamento
ARQUIVO_CSV = Path(os.environ.get("SOMPO_TELEMETRIA_CSV", "telemetria_ingerida.csv"))
CAMINHO_BASE = Path(os.environ.get("SOMPO_BASE_PATH", "base_sompo_limpa.csv"))
EXIGIR_HMAC = os.environ.get("SOMPO_EXIGIR_HMAC", "1") == "1"

bp_telemetria = Blueprint("telemetria", __name__)

# =========================================================================
# ESTADO EM MEMORIA
# =========================================================================
_lock = threading.Lock()
_serie: dict[str, deque] = defaultdict(lambda: deque(maxlen=JANELA_SERIE))
_ultimo: dict[str, dict] = {}
_ultima_seq: dict[str, int] = {}
_perfis: dict[str, dict] = {}          # equip_id -> linha da SUSEP + score_base
_avaliadores: dict[str, cf.AvaliadorEstavel] = {}
_stats = {"aceitos": 0, "rejeitados": 0, "perdas_seq": 0, "inicio": None}


def _chave_do_dispositivo(device_id: str) -> Optional[bytes]:
    """
    Chave HMAC por dispositivo, via variavel de ambiente.
    T1-CART-01 -> SOMPO_HMAC_T1_CART_01

    Nunca em arquivo commitado. No EC2 vai no /etc/environment ou no
    systemd unit; na bancada do Anthony, no .env local (gitignored).
    """
    var = "SOMPO_HMAC_" + device_id.replace("-", "_").upper()
    v = os.environ.get(var)
    return v.encode("utf-8") if v else None


CAMPOS_ASSINADOS = ("inclinacao_g", "vibracao_rms", "dist_obstaculo_cm",
                    "temperatura_c", "umidade_pct")


def _fmt(v: Optional[float]) -> str:
    """Formatacao canonica: 2 casas decimais, ou 'null'. Espelha %.2f do C."""
    return "null" if v is None else f"{float(v):.2f}"


def mensagem_canonica(corpo: dict) -> str:
    """
    String assinada. Contrato secao 3:

        device_id|seq|incl|vib|dist|temp|umid|estado

    NAO se assina o JSON serializado. Motivo, e vale registrar no capitulo de
    Cyber: Python e o ArduinoJson formatam float de forma diferente (14.2 vs
    14.20), entao um HMAC sobre a serializacao JSON falharia de maneira
    intermitente e praticamente impossivel de depurar em campo. Assinar uma
    concatenacao de valores com formatacao fixa e deterministico nos dois lados.
    """
    tel = corpo.get("tel", {})
    partes = [str(corpo["device_id"]), str(corpo["seq"])]
    partes += [_fmt(tel.get(c)) for c in CAMPOS_ASSINADOS]
    partes.append(str(corpo.get("edge", {}).get("estado", "")))
    return "|".join(partes)


def _hmac_esperado(chave: bytes, corpo: dict) -> str:
    msg = mensagem_canonica(corpo).encode("utf-8")
    return hmac.new(chave, msg, hashlib.sha256).hexdigest()


# =========================================================================
# VALIDACAO DE SCHEMA — contrato secao 2.1
# =========================================================================
FAIXAS_VALIDAS: dict[str, tuple[float, float]] = {
    "inclinacao_g": (0.0, 90.0),
    "vibracao_rms": (0.0, 20.0),
    "dist_obstaculo_cm": (-1.0, 400.0),
    "temperatura_c": (-10.0, 60.0),
    "umidade_pct": (0.0, 100.0),
}
OBRIGATORIOS_TEL = ("inclinacao_g", "vibracao_rms", "dist_obstaculo_cm")
ESTADOS_EDGE = {"VERDE", "AMARELO", "VERMELHO"}


class ErroValidacao(Exception):
    def __init__(self, msg: str, campo: str = "", codigo: int = 400):
        super().__init__(msg)
        self.msg, self.campo, self.codigo = msg, campo, codigo


def validar(corpo: Any) -> dict:
    """Valida estrutura, tipos e faixas. Levanta ErroValidacao com o campo culpado."""
    if not isinstance(corpo, dict):
        raise ErroValidacao("corpo nao e um objeto JSON")

    if corpo.get("schema_v") != SCHEMA_V:
        raise ErroValidacao(
            f"schema incompativel: recebido {corpo.get('schema_v')!r}",
            "schema_v", 422)

    for c in ("device_id", "equip_id", "seq", "tel", "edge"):
        if c not in corpo:
            raise ErroValidacao(f"campo obrigatorio ausente: {c}", c)

    if not isinstance(corpo["seq"], int) or corpo["seq"] < 0:
        raise ErroValidacao("seq deve ser inteiro >= 0", "seq")

    tel = corpo["tel"]
    if not isinstance(tel, dict):
        raise ErroValidacao("tel deve ser objeto", "tel")

    for c in OBRIGATORIOS_TEL:
        if c not in tel:
            raise ErroValidacao(f"tel.{c} obrigatorio", f"tel.{c}")

    for campo, valor in tel.items():
        if valor is None:
            continue                       # sensor falhou — permitido, contrato §2.1
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            raise ErroValidacao(f"tel.{campo} deve ser numero ou null", f"tel.{campo}")
        if campo in FAIXAS_VALIDAS:
            lo, hi = FAIXAS_VALIDAS[campo]
            if not (lo <= float(valor) <= hi):
                raise ErroValidacao(
                    f"tel.{campo}={valor} fora da faixa [{lo}, {hi}]", f"tel.{campo}")

    edge = corpo["edge"]
    if not isinstance(edge, dict) or edge.get("estado") not in ESTADOS_EDGE:
        raise ErroValidacao(
            f"edge.estado deve ser um de {sorted(ESTADOS_EDGE)}", "edge.estado")

    return corpo


# =========================================================================
# PERFIS — liga equip_id ao registro da SUSEP
# =========================================================================
def carregar_perfis() -> None:
    """
    Calcula score_base de cada equipamento uma vez, na subida.

    Perfil e lento (muda de mes em mes); telemetria e rapida (muda por segundo).
    Recalcular a Camada 1 a cada POST seria desperdicio e deixaria a resposta
    lenta demais para o farol.

    Mapeamento COL-000..COL-148 -> linha da base. Na Sprint 4, quando existir
    cadastro real, isso vira consulta ao Oracle do Guilherme.
    """
    if not CAMINHO_BASE.exists():
        print(f"[AVISO] base nao encontrada em {CAMINHO_BASE} — score_base=50 fixo")
        return

    base = pd.read_csv(CAMINHO_BASE)
    c1, c2 = cf.calibrar_faixas(base)
    print(f"[ok] faixas calibradas nos percentis 60/90: "
          f"verde <{c1} | amarelo <{c2} | vermelho >={c2}")

    scored = cf.calcular_score_base(base)
    for i, linha in scored.iterrows():
        _perfis[f"COL-{i:03d}"] = linha.to_dict()
    print(f"[ok] {len(_perfis)} perfis carregados de {CAMINHO_BASE}")


def _perfil_de(equip_id: str) -> dict:
    return _perfis.get(equip_id, {"score_base": 50.0})


# =========================================================================
# ROTA PRINCIPAL — INGESTAO
# =========================================================================
@bp_telemetria.route("/telemetria/v1/ingest", methods=["POST"])
def ingest():
    agora = datetime.now(timezone.utc)
    corpo = request.get_json(silent=True)

    try:
        corpo = validar(corpo)
    except ErroValidacao as e:
        _stats["rejeitados"] += 1
        return jsonify({"erro": e.msg, "campo": e.campo}), e.codigo

    device_id = corpo["device_id"]
    equip_id = corpo["equip_id"]
    seq = corpo["seq"]

    # ---- autenticacao ----
    if EXIGIR_HMAC:
        chave = _chave_do_dispositivo(device_id)
        if chave is None:
            _stats["rejeitados"] += 1
            return jsonify({"erro": "dispositivo_desconhecido",
                            "device_id": device_id}), 401
        recebido = str(corpo.get("hmac", ""))
        esperado = _hmac_esperado(chave, corpo)
        if not hmac.compare_digest(recebido, esperado):
            # compare_digest e nao-timing-safe-naive: evita side channel
            _stats["rejeitados"] += 1
            return jsonify({"erro": "assinatura_invalida"}), 401

    with _lock:
        # ---- anti-replay + deteccao de perda ----
        anterior = _ultima_seq.get(device_id)
        perdidas = 0
        if anterior is not None:
            if seq <= anterior and seq != 0:      # seq=0 => dispositivo rebootou
                _stats["rejeitados"] += 1
                return jsonify({"erro": "seq_duplicado", "ultima_vista": anterior}), 409
            perdidas = max(0, seq - anterior - 1)
            _stats["perdas_seq"] += perdidas
        _ultima_seq[device_id] = seq

        # ---- score: Camada 1 (cache) x Camada 2 (agora) ----
        perfil = _perfil_de(equip_id)
        res = cf.fundir(
            score_base=float(perfil.get("score_base", 50.0)),
            telemetria=corpo["tel"],
            perfil=perfil,
        )

        # ---- histerese: o farol da tela nao pode piscar ----
        av = _avaliadores.setdefault(equip_id, cf.AvaliadorEstavel())
        faixa_estavel = av.atualizar(res)

        registro = {
            "ts_servidor": agora.isoformat(),
            "device_id": device_id,
            "equip_id": equip_id,
            "seq": seq,
            "uptime_ms": corpo.get("uptime_ms"),
            **{f"tel_{k}": v for k, v in corpo["tel"].items()},
            "edge_estado": corpo["edge"].get("estado"),
            "edge_regra": corpo["edge"].get("regra", "—"),
            "score_base": res.score_base,
            "score_final": res.score_final,
            "faixa_instantanea": res.faixa,
            "faixa_estavel": faixa_estavel,
            "override_seguranca": res.override_seguranca,
        }
        _serie[equip_id].append(registro)
        _ultimo[equip_id] = {**registro, "frases": res.frases,
                             "recomendacao": res.recomendacao}
        _stats["aceitos"] += 1

    _persistir(registro)

    return jsonify({
        "aceito": True,
        "ts_servidor": agora.isoformat(),
        "score_base": res.score_base,
        "score_final": res.score_final,
        "faixa": faixa_estavel,
        "faixa_instantanea": res.faixa,
        "override_seguranca": res.override_seguranca,
        "motivo_override": res.motivo_override,
        "frases": res.frases,
        "recomendacao": res.recomendacao,
        "seq_perdidas": perdidas,
    }), 202


def _persistir(registro: dict) -> None:
    """
    Append em CSV. Simples de proposito: a demo nao pode depender do Oracle
    estar no ar. Quando o banco do Guilherme estiver estavel, este arquivo vira
    o INSERT — o registro ja esta achatado no formato de uma linha de tabela.
    """
    try:
        novo = not ARQUIVO_CSV.exists()
        with open(ARQUIVO_CSV, "a", encoding="utf-8") as f:
            if novo:
                f.write(",".join(registro.keys()) + "\n")
            f.write(",".join("" if v is None else str(v)
                             for v in registro.values()) + "\n")
    except Exception as e:                     # nunca derruba a ingestao
        print(f"[AVISO] falha ao persistir: {e}")


# =========================================================================
# ROTAS DE LEITURA — consumo do menu (US03) e da dashboard (US05)
# =========================================================================
@bp_telemetria.route("/telemetria/v1/ultimo/<equip_id>", methods=["GET"])
def ultimo(equip_id: str):
    """Menu do cliente. Polling de 2s. Farol + frases em portugues."""
    with _lock:
        r = _ultimo.get(equip_id)
    if r is None:
        return jsonify({"erro": "sem_telemetria", "equip_id": equip_id}), 404
    return jsonify(r)


@bp_telemetria.route("/telemetria/v1/serie/<equip_id>", methods=["GET"])
def serie(equip_id: str):
    """
    Serie temporal. Alimenta o grafico do dashboard e — mais importante — e o
    dataset real de serie temporal para o GRU do Rafael. 20 minutos de carrinho
    rodando a 1 Hz geram ~1200 amostras rotuladas por estado.
    """
    n = min(int(request.args.get("n", 200)), JANELA_SERIE)
    with _lock:
        dados = list(_serie.get(equip_id, []))[-n:]
    return jsonify({"equip_id": equip_id, "n": len(dados), "amostras": dados})


@bp_telemetria.route("/telemetria/v1/frota", methods=["GET"])
def frota():
    """Dashboard Sompo. Todos os equipamentos com telemetria, do pior pro melhor."""
    with _lock:
        itens = [
            {"equip_id": k, "score_final": v["score_final"],
             "faixa": v["faixa_estavel"], "ts_servidor": v["ts_servidor"],
             "override": v["override_seguranca"]}
            for k, v in _ultimo.items()
        ]
    itens.sort(key=lambda d: d["score_final"], reverse=True)
    return jsonify({"n": len(itens), "equipamentos": itens})


@bp_telemetria.route("/whoami", methods=["GET"])
def whoami():
    """
    Endereco em que a API realmente subiu. Contrato secao 1.3 — serve pra
    confirmar o alvo do ESP32 antes de sair procurando erro no firmware.
    """
    return jsonify({
        "host_visto_pelo_cliente": request.host,
        "ip_do_cliente": request.remote_addr,
        "hostname_servidor": socket.gethostname(),
        "porta": int(os.environ.get("PORT", 5000)),
        "schema_v": SCHEMA_V,
        "hmac_exigido": EXIGIR_HMAC,
        "versao_motor_score": cf.VERSAO_MOTOR,
    })


@bp_telemetria.route("/telemetria/v1/health", methods=["GET"])
def health():
    with _lock:
        return jsonify({
            "status": "ok",
            "schema_v": SCHEMA_V,
            "perfis_carregados": len(_perfis),
            "equipamentos_ativos": len(_ultimo),
            "aceitos": _stats["aceitos"],
            "rejeitados": _stats["rejeitados"],
            "perdas_seq": _stats["perdas_seq"],
            "faixas_calibradas": [f[0] for f in cf.FAIXAS],
        })


# =========================================================================
# STANDALONE
# =========================================================================
def criar_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.register_blueprint(bp_telemetria)
    carregar_perfis()
    _stats["inicio"] = datetime.now(timezone.utc).isoformat()
    return app


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    app = criar_app()
    ip_local = socket.gethostbyname(socket.gethostname())
    print("=" * 62)
    print("  SOMPO PREDICT · INGESTAO DE TELEMETRIA v" + SCHEMA_V)
    print("=" * 62)
    print(f"  Anthony, use este endereco no config.h:")
    print(f"     API_HOST  \"{ip_local}\"   (rede local)")
    print(f"     API_PORT  {porta}")
    print(f"     API_PATH  \"/telemetria/v1/ingest\"")
    print(f"  Confirme com:  curl http://{ip_local}:{porta}/whoami")
    print(f"  HMAC exigido: {EXIGIR_HMAC}"
          + ("" if EXIGIR_HMAC else "   <-- SO PARA BANCADA"))
    print("=" * 62)
    # debug=False sempre: debug=True no Werkzeug expoe console de execucao remota
    app.run(host="0.0.0.0", port=porta, debug=False, threaded=True)
