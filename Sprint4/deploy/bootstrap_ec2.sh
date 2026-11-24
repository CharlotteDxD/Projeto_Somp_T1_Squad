#!/usr/bin/env bash
#
# bootstrap_ec2.sh — de uma instancia Ubuntu limpa ao servico no ar.
#
#   scp -r . ubuntu@<endereco>:/tmp/sompo
#   ssh ubuntu@<endereco>
#   sudo bash /tmp/sompo/deploy/bootstrap_ec2.sh
#
# Idempotente: pode rodar de novo para atualizar o codigo sem refazer tudo.

set -euo pipefail

DESTINO=/opt/sompo-predict
ORIGEM="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE=/etc/sompo-predict.env

echo "==> Origem:  $ORIGEM"
echo "==> Destino: $DESTINO"

# --------------------------------------------------------------------------
# 1. Dependencias do sistema
# --------------------------------------------------------------------------
echo "==> Instalando dependencias do sistema"
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip curl

# --------------------------------------------------------------------------
# 2. Codigo
# --------------------------------------------------------------------------
echo "==> Copiando aplicacao"
mkdir -p "$DESTINO"
# Preserva os dados ja gravados na instancia
rsync -a --exclude '__pycache__' --exclude '.venv' \
      --exclude 'telemetria_ingerida.csv' \
      "$ORIGEM"/ "$DESTINO"/
chown -R ubuntu:ubuntu "$DESTINO"

# --------------------------------------------------------------------------
# 3. Ambiente Python isolado
# --------------------------------------------------------------------------
echo "==> Preparando ambiente Python"
sudo -u ubuntu python3 -m venv "$DESTINO/.venv" 2>/dev/null || true
sudo -u ubuntu "$DESTINO/.venv/bin/pip" install --quiet --upgrade pip
sudo -u ubuntu "$DESTINO/.venv/bin/pip" install --quiet \
    flask gunicorn pandas numpy

# --------------------------------------------------------------------------
# 4. Configuracao e chaves
# --------------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    echo "==> Criando $ENV_FILE com chave gerada"
    CHAVE=$(openssl rand -hex 32)
    sed "s|troque-esta-chave-por-32-bytes-aleatorios|$CHAVE|" \
        "$DESTINO/deploy/sompo-api.env.exemplo" > "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    chown root:root "$ENV_FILE"
    echo ""
    echo "    CHAVE DO DISPOSITIVO (anotar — usar no config.h do dispositivo):"
    echo "    $CHAVE"
    echo ""
else
    echo "==> $ENV_FILE ja existe — mantido (chaves preservadas)"
fi

# --------------------------------------------------------------------------
# 5. Servico
# --------------------------------------------------------------------------
echo "==> Registrando servico"
cp "$DESTINO/deploy/sompo-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable sompo-api >/dev/null
systemctl restart sompo-api

# --------------------------------------------------------------------------
# 6. Verificacao
# --------------------------------------------------------------------------
echo "==> Aguardando o servico responder"
PORTA=$(grep -E '^PORT=' "$ENV_FILE" | cut -d= -f2)
for i in $(seq 1 20); do
    if curl -sf "http://localhost:${PORTA}/whoami" >/dev/null 2>&1; then
        echo ""
        echo "    Servico no ar."
        curl -s "http://localhost:${PORTA}/whoami"
        echo ""
        IP_PUB=$(curl -s --max-time 3 \
                 http://169.254.169.254/latest/meta-data/public-ipv4 || echo "<endereco>")
        echo ""
        echo "    Endereco publico: http://${IP_PUB}:${PORTA}"
        echo ""
        echo "    Proximos passos:"
        echo "      · liberar TCP ${PORTA} de 0.0.0.0/0 no grupo de seguranca"
        echo "      · associar um endereco IP fixo (o publico muda a cada reinicio)"
        echo "      · apontar a plataforma:  SOMPO_API_BASE=http://${IP_PUB}:${PORTA}"
        echo "      · gravar o mesmo endereco e chave no config.h do dispositivo"
        exit 0
    fi
    sleep 1
done

echo ""
echo "    O servico nao respondeu em 20s. Diagnostico:"
echo "      systemctl status sompo-api"
echo "      journalctl -u sompo-api -n 50 --no-pager"
exit 1
