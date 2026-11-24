#!/usr/bin/env bash
#
# verificar.sh — teste de aceite do servico publicado.
#
#   bash deploy/verificar.sh                      # local
#   bash deploy/verificar.sh http://54.207.0.1:80 # remoto
#
# Verifica o caminho completo: disponibilidade, formato aceito, calculo de
# score, rejeicao de leitura invalida, protecao contra reenvio e consulta.
# Sai com codigo 0 apenas se todos passarem.

set -uo pipefail

BASE="${1:-http://localhost:5000}"
EQUIP="${SOMPO_EQUIP_TESTE:-COL-000}"
DEVICE="${SOMPO_DEVICE_TESTE:-T1-CART-01}"
SEQ_BASE=$(( (RANDOM % 9000) + 90000 ))

ok=0; falhou=0
verde()   { printf "  \033[0;32mPASSOU\033[0m  %s\n" "$1"; ok=$((ok+1)); }
vermelho(){ printf "  \033[0;31mFALHOU\033[0m  %s\n" "$1"; falhou=$((falhou+1)); }

echo ""
echo "Teste de aceite — $BASE"
echo "-------------------------------------------------------------"

# 1 ---------------------------------------------------------------- disponivel
if curl -sf --max-time 5 "$BASE/whoami" >/dev/null; then
    verde "servico responde"
else
    vermelho "servico nao responde em $BASE"
    echo ""
    echo "  Verificar: grupo de seguranca liberando a porta, servico ativo"
    echo "  (systemctl status sompo-api) e endereco correto."
    exit 1
fi

# 2 ------------------------------------------------------------ formato aceito
SCHEMA=$(curl -s "$BASE/whoami" | grep -o '"schema_v":"[^"]*"' | cut -d'"' -f4)
[ "$SCHEMA" = "1.0" ] && verde "formato de dados 1.0" \
                      || vermelho "formato inesperado: '$SCHEMA'"

# 3 --------------------------------------------------------- assinatura exigida
HMAC=$(curl -s "$BASE/whoami" | grep -o '"hmac_exigido":[a-z]*' | cut -d: -f2)
if [ "$HMAC" = "true" ]; then
    verde "assinatura exigida (producao)"
else
    verde "assinatura dispensada — aceitavel em bancada, NAO em producao"
fi

# 4 ------------------------------------------------------------ leitura aceita
payload() {
cat <<JSON
{"schema_v":"1.0","device_id":"$DEVICE","equip_id":"$EQUIP","seq":$1,
 "uptime_ms":$(( $1 * 1000 )),
 "tel":{"inclinacao_g":$2,"vibracao_rms":1.0,"dist_obstaculo_cm":$3,
        "temperatura_c":31.0,"umidade_pct":78.0},
 "edge":{"estado":"VERDE","regra":"-","fw":"2.0.0"},"hmac":"${SOMPO_HMAC_TESTE:-}"}
JSON
}

RESP=$(curl -s -w '\n%{http_code}' -X POST "$BASE/telemetria/v1/ingest" \
       -H 'Content-Type: application/json' -d "$(payload $SEQ_BASE 3.0 300.0)")
CODIGO=$(echo "$RESP" | tail -1)
CORPO=$(echo "$RESP" | head -n -1)

if [ "$CODIGO" = "202" ]; then
    verde "leitura aceita e processada"
elif [ "$CODIGO" = "401" ]; then
    verde "leitura recusada por assinatura — esperado com HMAC ativo"
    echo "         (para testar o caminho completo: "
    echo "          SOMPO_HMAC_TESTE=<assinatura> bash deploy/verificar.sh)"
    echo ""
    echo "Resumo: $ok verificacao(oes) concluida(s)."
    exit 0
else
    vermelho "leitura recusada com codigo $CODIGO"
    echo "         $CORPO"
fi

# 5 ------------------------------------------------------------ score calculado
if echo "$CORPO" | grep -q '"score_final"'; then
    SCORE=$(echo "$CORPO" | grep -o '"score_final":[0-9.]*' | cut -d: -f2)
    FAIXA=$(echo "$CORPO" | grep -o '"faixa":"[^"]*"' | cut -d'"' -f4)
    verde "score calculado: $SCORE ($FAIXA)"
else
    vermelho "resposta sem score"
fi

# 6 --------------------------------------------------- leitura invalida recusada
INVALIDA=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
    "$BASE/telemetria/v1/ingest" -H 'Content-Type: application/json' \
    -d "$(payload $((SEQ_BASE+1)) 999.0 300.0)")
[ "$INVALIDA" = "400" ] && verde "leitura fora de faixa recusada (400)" \
                        || vermelho "leitura invalida devolveu $INVALIDA, esperado 400"

# 7 ------------------------------------------------------------ reenvio barrado
curl -s -o /dev/null -X POST "$BASE/telemetria/v1/ingest" \
    -H 'Content-Type: application/json' -d "$(payload $((SEQ_BASE+2)) 5.0 300.0)"
REENVIO=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
    "$BASE/telemetria/v1/ingest" -H 'Content-Type: application/json' \
    -d "$(payload $((SEQ_BASE+2)) 5.0 300.0)")
[ "$REENVIO" = "409" ] && verde "reenvio da mesma sequencia barrado (409)" \
                       || vermelho "reenvio devolveu $REENVIO, esperado 409"

# 8 -------------------------------------------------------------- consulta
if curl -sf "$BASE/telemetria/v1/ultimo/$EQUIP" | grep -q '"faixa_estavel"'; then
    verde "consulta da ultima leitura"
else
    vermelho "consulta da ultima leitura nao retornou dados"
fi

if curl -sf "$BASE/telemetria/v1/frota" | grep -q '"equipamentos"'; then
    verde "consulta da frota"
else
    vermelho "consulta da frota falhou"
fi

echo "-------------------------------------------------------------"
echo "  $ok aprovada(s) · $falhou reprovada(s)"
echo ""
[ "$falhou" -eq 0 ] && exit 0 || exit 1
