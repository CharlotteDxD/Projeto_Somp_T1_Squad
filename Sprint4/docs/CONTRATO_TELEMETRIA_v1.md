# Contrato de Telemetria · Sompo Predict · v1.0

**Status:** congelado em 10/ago/2026 · Squad T1
**Donos:** Anthony (produtor) · Gustavo (transporte/infra) · Charles (consumidor) · Rafael (schema)

> Este documento é a **única fonte de verdade** do formato de dados entre o ESP32 e a nuvem.
> Mudança de campo, unidade ou frequência exige aviso no grupo e bump de `schema_v`.
> Nenhum dos quatro pode alterar sozinho.

---

## 1. Endereço da API — o problema do IP

O ESP32 precisa de um endereço fixo. Três cenários, nesta ordem de preferência:

| Cenário | `API_HOST` | Quando usar |
|---|---|---|
| **Produção (EC2)** | Elastic IP da instância | Padrão. Ver §1.1 |
| **Plano B (notebook + hotspot)** | IP local do notebook do Gustavo | Wi-Fi da FIAP bloqueando saída |
| **Bancada** | IP local na rede de casa | Desenvolvimento do Anthony |

### 1.1 Elastic IP — obrigatório antes do checkpoint

O IP público de uma EC2 **muda a cada stop/start**. Se o Gustavo desligar a instância pra
economizar free tier e ligar de novo no dia do pitch, o ESP32 aponta pro vazio e a demo morre
em silêncio. Elastic IP é gratuito enquanto associado a uma instância **em execução**.

```bash
# Gustavo · uma vez só, antes de qualquer coisa
aws ec2 allocate-address --domain vpc
aws ec2 associate-address --instance-id <i-xxxx> --allocation-id <eipalloc-xxxx>
```

Anota o IP resultante no grupo. É esse valor que entra no `config.h` do Anthony.

### 1.2 Porta 80, não 5000

Rede de faculdade costuma bloquear saída em portas altas. O ESP32 fazendo POST na 5000 é
exatamente o cenário que falha na hora do checkpoint e ninguém entende por quê.
**Rode a API na porta 80.** O security group libera TCP 80 de `0.0.0.0/0`; a saída do ESP32
vira tráfego HTTP comum, que nenhuma rede bloqueia.

```bash
# EC2 · autoriza porta baixa sem rodar como root
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))
PORT=80 python3 api_telemetria.py
```

### 1.3 Descoberta em runtime

A API expõe `GET /whoami`, que devolve o endereço em que ela realmente se amarrou. Serve
pra confirmar antes de sair procurando erro no firmware.

```bash
curl http://<ELASTIC_IP>/whoami
# {"host_visto_pelo_cliente":"...","porta":80,"schema_v":"1.0","hmac_exigido":true}
```

---

## 2. Payload — POST `/telemetria/v1/ingest`

`Content-Type: application/json` · corpo **exatamente** nesta forma:

```json
{
  "schema_v": "1.0",
  "device_id": "T1-CART-01",
  "equip_id": "COL-099",
  "seq": 1487,
  "uptime_ms": 894312,
  "tel": {
    "inclinacao_g": 14.2,
    "vibracao_rms": 0.87,
    "dist_obstaculo_cm": 42.0,
    "temperatura_c": 31.4,
    "umidade_pct": 78.0
  },
  "edge": {
    "estado": "AMARELO",
    "regra": "INCLINACAO>12",
    "fw": "2.0.0"
  },
  "hmac": "9f2c8ab1..."
}
```

### 2.1 Dicionário de campos

| Campo | Tipo | Unidade | Faixa válida | Sensor | Obrig. |
|---|---|---|---|---|---|
| `schema_v` | string | — | `"1.0"` | — | sim |
| `device_id` | string | — | `T1-CART-\d\d` | — | sim |
| `equip_id` | string | — | id do equipamento simulado | — | sim |
| `seq` | int | — | monotônico ≥ 0 | — | sim |
| `uptime_ms` | int | ms | `millis()` desde boot | — | sim |
| `tel.inclinacao_g` | float | **graus** | 0.0 – 90.0 | MPU6050 | sim |
| `tel.vibracao_rms` | float | **m/s²** | 0.0 – 20.0 | MPU6050 | sim |
| `tel.dist_obstaculo_cm` | float | **cm** | 2.0 – 400.0 · `-1` = sem eco | HC-SR04 | sim |
| `tel.temperatura_c` | float | **°C** | -10.0 – 60.0 · `null` se falhou | DHT22 | não |
| `tel.umidade_pct` | float | **%** | 0.0 – 100.0 · `null` se falhou | DHT22 | não |
| `edge.estado` | string | — | `VERDE` \| `AMARELO` \| `VERMELHO` | — | sim |
| `edge.regra` | string | — | regra que disparou, ou `"—"` | — | sim |
| `edge.fw` | string | — | semver do firmware | — | sim |
| `hmac` | string hex | — | 64 chars · SHA-256 | — | sim |

**Regras que não se negocia:**

1. **Unidade vai no nome do campo.** `_cm`, `_pct`, `_c`, `_g`, `_ms`. Nunca um campo sem sufixo.
2. **`inclinacao_g` é ângulo em graus**, não aceleração. O nome antigo `Inclinacao` era ambíguo.
3. **Sensor que falhou manda `null`**, nunca `0`. Zero é uma leitura válida de umidade; `null` é
   ausência. Trocar os dois contamina a estatística do Guilherme.
4. **`-1` em `dist_obstaculo_cm`** significa "sem eco" (nada à frente dentro do alcance) — o
   HC-SR04 não distingue "longe" de "sem retorno", então o firmware normaliza.
5. **O ESP32 não manda timestamp.** Não tem RTC e o relógio do `millis()` reseta. O carimbo de
   tempo autoritativo é o do servidor, em UTC. `uptime_ms` + `seq` bastam pra ordenar.
6. **`edge.estado` é a decisão do dispositivo**, o score da nuvem é outra coisa. O servidor
   guarda os dois e **nunca sobrescreve** o `edge`. É essa distinção que permite ao Charles
   mostrar "o que o sensor achou" ao lado de "o que o modelo achou" na tela de detalhe.

### 2.2 Frequências

| O quê | Período | Por quê |
|---|---|---|
| Loop de decisão local (farol/buzzer) | **100 ms** | Latência do alerta não depende da rede |
| Leitura MPU6050 + HC-SR04 | 100 ms | Barato, e média móvel de 5 amostras filtra ruído |
| Leitura DHT22 | **5 s** | Limite físico do sensor é 0,5 Hz — ler mais rápido devolve lixo |
| POST de heartbeat | **1 s** | Regime normal |
| POST de evento | **imediato** | Sempre que `edge.estado` muda. É o que faz o alerta parecer instantâneo na demo |
| Timeout HTTP | 3 s, 1 retry | Depois disso vai pro buffer circular (20 amostras) |

Duas justificativas que vão direto pro capítulo de Sensores: o DHT22 a 0,2 Hz é restrição
física do componente, não escolha; e a arquitetura **event-driven sobre heartbeat** existe
porque numa máquina real em LoRaWAN o custo é por mensagem — mandar 1 Hz o dia inteiro é
inviável, mandar só quando o estado muda é o padrão de telemetria industrial.

---

## 3. Autenticação — HMAC-SHA256

O ESP32 não tem como guardar credencial de forma segura, e TLS num ESP32 custa RAM e falha em
handshake com frequência. O padrão para dispositivo restrito é **assinar o payload**, não
criptografá-lo: o dado de telemetria não é sigiloso, mas precisa ser **autêntico**.

```
mensagem = device_id | seq | inclinacao_g | vibracao_rms | dist_obstaculo_cm
           | temperatura_c | umidade_pct | edge.estado

float  -> "%.2f"   ·   sensor ausente -> "null"   ·   separador -> "|"

exemplo: T1-CART-01|1487|14.20|0.87|42.00|31.40|78.00|AMARELO
hmac    = HEX( HMAC-SHA256( chave_do_dispositivo, mensagem ) )
```

**Assina-se a concatenação de valores, não o JSON serializado.** Python (`14.2`) e
ArduinoJson (`14.20`) formatam float de maneira diferente, então um HMAC sobre o JSON
falharia de forma intermitente e praticamente impossível de depurar em campo. Com
formatação fixa de 2 casas, os dois lados produzem byte a byte a mesma string —
verificado.

- Chave de 32 bytes, **uma por dispositivo**, nunca commitada — `config.h` está no `.gitignore`.
- Servidor rejeita com `401` se o HMAC não confere, e com `409` se `seq` já foi visto
  (proteção contra replay).
- Demonstração de 20 segundos pro capítulo de Cyber: altera um byte do payload no Postman,
  o servidor recusa. Isso é evidência, não descrição.

Isso **não substitui** TLS na rota do navegador — o dashboard continua atrás de HTTPS. É a
camada do dispositivo, e a justificativa da escolha é conteúdo do capítulo do Charles.

---

## 4. Respostas

| Código | Quando | Corpo |
|---|---|---|
| `202` | Aceito e processado | score, faixa, frases, `override_seguranca` |
| `400` | Campo ausente, tipo errado ou fora de faixa | `{"erro": "...", "campo": "..."}` |
| `401` | HMAC inválido ou `device_id` desconhecido | `{"erro":"assinatura_invalida"}` |
| `409` | `seq` repetido (replay) | `{"erro":"seq_duplicado"}` |
| `422` | `schema_v` incompatível | `{"erro":"schema_incompativel","esperado":"1.0"}` |

Resposta `202` (é isto que o firmware usa pro farol e o menu do Charles consome):

```json
{
  "aceito": true,
  "ts_servidor": "2026-08-12T14:32:05.123Z",
  "score_base": 34.2,
  "score_final": 81.7,
  "faixa": "vermelho",
  "override_seguranca": true,
  "motivo_override": "obstaculo_critico",
  "frases": [
    "Obstáculo a 42 cm à frente da máquina.",
    "Inclinação de 14° em terreno irregular.",
    "Colheitadeira de 12 anos — faixa etária de maior severidade histórica."
  ],
  "recomendacao": "Reduza a velocidade e avalie parar a operação.",
  "seq_perdidas": 0
}
```

---

## 5. Rotas de leitura (consumo do menu e da dashboard)

| Rota | Uso |
|---|---|
| `GET /telemetria/v1/ultimo/<equip_id>` | Menu do cliente (US03) — farol + frases |
| `GET /telemetria/v1/serie/<equip_id>?n=200` | Gráfico do dashboard e treino do GRU do Rafael |
| `GET /telemetria/v1/frota` | Dashboard Sompo (US05) — todos os equipamentos ordenados por score |
| `GET /whoami` · `GET /health` | Diagnóstico e entregável de Cloud |

O menu do Charles faz *polling* de 2 s em `/ultimo/<equip_id>`. Não precisa de WebSocket para
seis equipamentos numa demo — e polling não quebra quando a rede oscila.

---

## 6. Mapa de responsabilidade

| Etapa | Dono | Entregável de aceite |
|---|---|---|
| Produzir o JSON conforme §2 | Anthony | 20 min de POST sem travar, `seq` sem buraco |
| Receber, validar, persistir | Gustavo | `202` no Postman + CSV crescendo em disco |
| Calcular score e frases | Rafael | `core_fusao.py` com testes passando |
| Consumir no menu e na dashboard | Charles | Farol muda de cor em ≤ 3 s do evento físico |
| Modelar a tabela no Oracle | Guilherme | DDL espelhando §2.1, uma coluna por campo |

**Teste de aceite conjunto (o checkpoint da semana de 17/ago):** Anthony inclina a protoboard,
o farol físico vira vermelho em menos de 200 ms, e a tela do Charles vira vermelha em menos de
3 s. Se os dois acontecem, o caminho do dado está fechado.
