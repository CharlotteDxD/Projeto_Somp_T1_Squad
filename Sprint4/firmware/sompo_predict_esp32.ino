/*
 * ============================================================================
 *  SOMPO PREDICT · Firmware do carrinho · v2.0.0
 *  Squad T1 · Sprint 3 · Owner: Anthony
 * ============================================================================
 *
 *  Implementa CONTRATO_TELEMETRIA_v1.md.
 *
 *  MUDANCAS EM RELACAO AO sketch_anthony.ino (Sprint 2), e por que:
 *
 *   1. Wi-Fi + POST JSON. Antes so imprimia CSV no Serial — o dado morria no
 *      cabo. Este e o objetivo do checkpoint de 17/ago.
 *   2. HC-SR04 (ultrassom) entrou. Obstaculo e o gatilho mais visivel da demo.
 *   3. delay(1000) eliminado. delay() bloqueia: com ele o farol demora ate 1s
 *      pra reagir e o Wi-Fi perde pacote. Agora o loop e nao-bloqueante e a
 *      decisao local roda a 10 Hz.
 *   4. DHT22 lido a cada 5s, nao a cada ciclo. O sensor tem limite fisico de
 *      0,5 Hz — ler mais rapido devolve NaN. Isso vai no capitulo de Sensores.
 *   5. Farol de 3 estados com HISTERESE. Sem ela um solavanco pisca vermelho
 *      e a demo parece quebrada.
 *   6. O carrinho NAO PARA sozinho. Decisao registrada pelo coordenador: o
 *      sistema alerta, quem decide parar e o operador. O motor continua.
 *   7. HMAC-SHA256 por payload. O dispositivo assina; o servidor valida.
 *   8. Buffer circular offline. Wi-Fi de faculdade cai — o dado nao se perde.
 *
 *  BIBLIOTECAS (Library Manager):
 *      Adafruit MPU6050 · Adafruit Unified Sensor · DHT sensor library
 *      ArduinoJson (v7)          — mbedtls ja vem no core do ESP32
 *
 *  ANTES DE GRAVAR: copie config_exemplo.h para config.h, preencha, e confirme
 *  que config.h esta no .gitignore. Chave commitada = chave vazada.
 * ============================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include "mbedtls/md.h"

// ---------------------------------------------------------------------------
// config.h  (NAO COMMITAR)
// ---------------------------------------------------------------------------
//   #define WIFI_SSID   "..."
//   #define WIFI_PASS   "..."
//   #define API_HOST    "54.207.xxx.xxx"   // Elastic IP — contrato §1.1
//   #define API_PORT    80                 // porta 80 — contrato §1.2
//   #define DEVICE_ID   "T1-CART-01"
//   #define EQUIP_ID    "COL-000"
//   #define HMAC_KEY    "chave-de-32-bytes-no-minimo-aqui"
// ---------------------------------------------------------------------------
#include "config.h"

#define API_PATH "/telemetria/v1/ingest"
#define FW_VERSAO "2.0.0"
#define SCHEMA_V "1.0"

// ---------------------------------------------------------------------------
// PINOS
// ---------------------------------------------------------------------------
#define PIN_DHT     15
#define PIN_SDA     21
#define PIN_SCL     22
#define PIN_TRIG    5
#define PIN_ECHO    18
#define PIN_LED_G   25
#define PIN_LED_Y   26
#define PIN_LED_R   27
#define PIN_BUZZER  33

// ---------------------------------------------------------------------------
// LIMIARES · devem espelhar FATORES_TELEMETRIA em core_fusao.py.
// Divergiu aqui, o farol fisico e a tela discordam na frente da Sompo.
// ---------------------------------------------------------------------------
const float INCL_ATENCAO   = 8.0;    // graus
const float INCL_CRITICA   = 25.0;   // graus  -> override de seguranca
const float DIST_ATENCAO   = 120.0;  // cm
const float DIST_CRITICA   = 35.0;   // cm     -> override de seguranca
const float VIB_ATENCAO    = 0.5;    // m/s^2
const float UMID_ATENCAO   = 60.0;   // %

// Histerese: sobe em 2 leituras, desce em 5. Assimetrico de proposito —
// em sistema de alerta, subir a toa custa menos que descer cedo demais.
const uint8_t N_SUBIR  = 2;
const uint8_t N_DESCER = 5;

// Periodos (ms)
const uint32_t P_LOOP      = 100;    // decisao local — 10 Hz
const uint32_t P_DHT       = 5000;   // limite fisico do DHT22
const uint32_t P_HEARTBEAT = 1000;   // envio em regime normal
const uint32_t TIMEOUT_HTTP = 3000;

#define BUF_OFFLINE 20

// ---------------------------------------------------------------------------
// ESTADO
// ---------------------------------------------------------------------------
DHT dht(PIN_DHT, DHT22);
Adafruit_MPU6050 mpu;

enum Estado { VERDE = 0, AMARELO = 1, VERMELHO = 2 };
const char* NOME_ESTADO[] = {"VERDE", "AMARELO", "VERMELHO"};

Estado  estadoAtual = VERDE;
Estado  candidato   = VERDE;
uint8_t contagem    = 0;

struct Amostra {
  float incl, vib, dist, temp, umid;
  bool  temDHT;
  Estado estado;
  char  regra[24];
  uint32_t uptime;
  uint32_t seq;
};

Amostra bufOffline[BUF_OFFLINE];
uint8_t bufIni = 0, bufQtd = 0;

uint32_t seqGlobal = 0;
uint32_t tLoop = 0, tDHT = 0, tHeartbeat = 0;
float ultimaTemp = NAN, ultimaUmid = NAN;
bool  mpuOk = false;

// Media movel de 5 amostras — MPU6050 e ruidoso, e um pico isolado nao pode
// virar alerta. Este filtro e o que faz a demo ser reproduzivel 3x seguidas.
const uint8_t N_MEDIA = 5;
float histIncl[N_MEDIA] = {0}, histVib[N_MEDIA] = {0}, histDist[N_MEDIA] = {0};
uint8_t idxMedia = 0;
bool mediaCheia = false;

// Saude do MPU6050 · detecta leitura travada (I2C glitch) e leitura acima
// do teto fisico do sensor. As duas sao o padrao observado em campo: valor
// repetido byte-a-byte por dezenas de ciclos, acima do que o acelerometro
// em +-8G consegue fisicamente produzir (~126 m/s^2 de magnitude).
// Verificado em log de campo: vib=129.18 repetido de seq=20 a seq=90.
const float VIB_TETO_FISICO = 126.0;      // magnitude maxima plausivel, +-8G
const float VIB_EPSILON_TRAVADO = 0.02;   // leituras "iguais" dentro disto
const uint8_t N_TRAVADO_REINIT = 15;      // ~1,5s a 10Hz antes de reiniciar
float    vibUltimaBruta   = -1.0;
uint8_t  vibContagemIgual = 0;
uint32_t mpuFalhasSeguidas = 0;
uint32_t mpuUltimaReinit   = 0;

// ===========================================================================
// SENSORES
// ===========================================================================

/*
 * Le o MPU6050 com verificacao de plausibilidade.
 *
 * mpu.getEvent() nao tem o retorno checado na biblioteca Adafruit em todas
 * as versoes, e quando o barramento I2C falha (fiacao solta, alimentacao
 * instavel), o sensor pode devolver o ultimo valor cacheado ou lixo, SEM
 * sinalizar erro. O sintoma em campo foi um valor de vibracao identico
 * repetido por dezenas de ciclos, acima do teto fisico do sensor.
 *
 * Esta funcao:
 *   1. Descarta leitura acima do teto fisico (fisicamente impossivel).
 *   2. Detecta leitura "travada" (identica por N_TRAVADO_REINIT ciclos).
 *   3. Reinicia o barramento I2C e o sensor quando travado.
 *   4. Devolve false quando a leitura nao e confiavel — quem chama decide
 *      o valor seguro a usar (nunca propaga o lixo pra frente).
 */
bool lerMPU(float &inclOut, float &vibOut) {
  if (!mpuOk) { inclOut = 0; vibOut = 0; return false; }

  sensors_event_t a, g, t;
  mpu.getEvent(&a, &g, &t);

  float mag = sqrt(sq(a.acceleration.x) + sq(a.acceleration.y) + sq(a.acceleration.z));
  float vibBruto = fabs(mag - 9.81);

  // ---- travado: mesmo valor por muitos ciclos seguidos ----
  if (fabs(vibBruto - vibUltimaBruta) < VIB_EPSILON_TRAVADO) {
    vibContagemIgual++;
  } else {
    vibContagemIgual = 0;
  }
  vibUltimaBruta = vibBruto;

  bool acimaDoTeto = (vibBruto > VIB_TETO_FISICO);
  bool travado = (vibContagemIgual >= N_TRAVADO_REINIT);

  if (travado || acimaDoTeto) {
    mpuFalhasSeguidas++;
    // Reinicia o barramento I2C e o sensor — no maximo a cada 3s, pra nao
    // martelar o barramento se o problema for fisico (fio solto de verdade).
    if (millis() - mpuUltimaReinit > 3000) {
      mpuUltimaReinit = millis();
      Serial.printf("[MPU] leitura invalida (vib=%.2f, travado=%d) — "
                    "reiniciando I2C. Falhas seguidas: %lu\n",
                    vibBruto, travado, (unsigned long)mpuFalhasSeguidas);
      Wire.end();
      delay(50);
      Wire.begin(PIN_SDA, PIN_SCL);
      mpuOk = mpu.begin();
      if (mpuOk) {
        mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
        mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
        Serial.println("[MPU] reinicializado com sucesso");
      } else {
        Serial.println("[MPU] falha ao reinicializar — verifique fiacao "
                       "SDA/SCL e alimentacao do sensor");
      }
      vibContagemIgual = 0;
    }
    inclOut = 0; vibOut = 0;
    return false;
  }

  mpuFalhasSeguidas = 0;
  inclOut = fabs(atan2(a.acceleration.y, a.acceleration.z) * 180.0 / PI);
  vibOut  = vibBruto;
  return true;
}

float lerDistanciaCm() {
  digitalWrite(PIN_TRIG, LOW);  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  // Timeout de 25 ms ~ 4 m. Sem timeout, pulseIn trava o loop inteiro
  // quando nao ha eco — e "nao ha eco" e o caso normal em campo aberto.
  unsigned long dur = pulseIn(PIN_ECHO, HIGH, 25000UL);

  if (dur == 0) return -1.0;                       // sem eco — contrato §2.1
  float cm = dur * 0.0343 / 2.0;
  if (cm < 2.0 || cm > 400.0) return -1.0;         // fora do alcance util
  return cm;
}

float mediaDe(float* v) {
  uint8_t n = mediaCheia ? N_MEDIA : idxMedia;
  if (n == 0) return 0.0;
  float s = 0;
  for (uint8_t i = 0; i < n; i++) s += v[i];
  return s / n;
}

// ===========================================================================
// CLASSIFICACAO LOCAL
// Roda no dispositivo, nao na nuvem. Justificativa para o capitulo de IoT:
// o alerta de seguranca nao pode depender de rede. O ESP32 decide o farol em
// menos de 200 ms; a nuvem refina o score com o historico da apolice depois.
// ===========================================================================
Estado classificar(float incl, float dist, float vib, float umid, char* regraOut) {
  if (incl >= INCL_CRITICA) {
    snprintf(regraOut, 24, "INCL>=%d", (int)INCL_CRITICA); return VERMELHO;
  }
  if (dist > 0 && dist <= DIST_CRITICA) {
    snprintf(regraOut, 24, "DIST<=%d", (int)DIST_CRITICA); return VERMELHO;
  }
  uint8_t pontos = 0;
  if (incl >= INCL_ATENCAO)                pontos++;
  if (dist > 0 && dist <= DIST_ATENCAO)    pontos++;
  if (vib  >= VIB_ATENCAO)                 pontos++;
  if (!isnan(umid) && umid >= UMID_ATENCAO) pontos++;

  if (pontos >= 3) { snprintf(regraOut, 24, "COMBINADO_%d", pontos); return VERMELHO; }
  if (pontos >= 1) { snprintf(regraOut, 24, "ATENCAO_%d", pontos);   return AMARELO;  }
  strncpy(regraOut, "-", 24);
  return VERDE;
}

Estado aplicarHisterese(Estado bruto, bool forcar) {
  if (forcar) { estadoAtual = bruto; contagem = 0; return estadoAtual; }
  if (bruto == estadoAtual) { contagem = 0; return estadoAtual; }
  if (bruto != candidato) { candidato = bruto; contagem = 1; }
  else                    { contagem++; }

  uint8_t alvo = (bruto > estadoAtual) ? N_SUBIR : N_DESCER;
  if (contagem >= alvo) { estadoAtual = bruto; contagem = 0; }
  return estadoAtual;
}

// ===========================================================================
// ATUADORES · O CARRINHO NAO PARA. Ele avisa.
// ===========================================================================
void acionarFarol(Estado e) {
  digitalWrite(PIN_LED_G, e == VERDE);
  digitalWrite(PIN_LED_Y, e == AMARELO);
  digitalWrite(PIN_LED_R, e == VERMELHO);

  static uint32_t tBip = 0;
  static bool bipando = false;
  uint32_t agora = millis();

  if (e == VERMELHO) {                       // intermitente 200/200 ms
    if (agora - tBip >= 200) {
      tBip = agora; bipando = !bipando;
      if (bipando) tone(PIN_BUZZER, 2200); else noTone(PIN_BUZZER);
    }
  } else if (e == AMARELO) {                 // bipe curto a cada 1,5 s
    if (agora - tBip >= 1500) {
      tBip = agora; tone(PIN_BUZZER, 1200, 90);
    }
  } else {
    noTone(PIN_BUZZER);
  }
  // Nenhuma escrita em pino de motor. Deliberado — ver cabecalho, item 6.
}

// ===========================================================================
// HMAC-SHA256 · contrato §3
//   msg = device_id|seq|incl|vib|dist|temp|umid|estado
//   floats com %.2f, ausente = "null"
// ===========================================================================
void fmtFloat(char* dest, size_t n, float v, bool valido) {
  if (!valido || isnan(v)) snprintf(dest, n, "null");
  else                     snprintf(dest, n, "%.2f", v);
}

void calcularHmac(const Amostra& a, char* hexOut) {
  char sIncl[16], sVib[16], sDist[16], sTemp[16], sUmid[16];
  fmtFloat(sIncl, 16, a.incl, true);
  fmtFloat(sVib,  16, a.vib,  true);
  fmtFloat(sDist, 16, a.dist, true);
  fmtFloat(sTemp, 16, a.temp, a.temDHT);
  fmtFloat(sUmid, 16, a.umid, a.temDHT);

  char msg[192];
  snprintf(msg, sizeof(msg), "%s|%lu|%s|%s|%s|%s|%s|%s",
           DEVICE_ID, (unsigned long)a.seq,
           sIncl, sVib, sDist, sTemp, sUmid, NOME_ESTADO[a.estado]);

  byte hmac[32];
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 1);
  mbedtls_md_hmac_starts(&ctx, (const unsigned char*)HMAC_KEY, strlen(HMAC_KEY));
  mbedtls_md_hmac_update(&ctx, (const unsigned char*)msg, strlen(msg));
  mbedtls_md_hmac_finish(&ctx, hmac);
  mbedtls_md_free(&ctx);

  for (int i = 0; i < 32; i++) sprintf(hexOut + i * 2, "%02x", hmac[i]);
  hexOut[64] = '\0';
}

// ===========================================================================
// ENVIO
// ===========================================================================
bool enviar(const Amostra& original) {
  if (WiFi.status() != WL_CONNECTED) return false;

  // Blindagem final: garante que cada campo cabe na faixa aceita pelo
  // servidor (contrato §2.1), mesmo que algo escape da checagem de
  // plausibilidade em lerMPU(). Sem isto, UM campo fora da faixa derruba
  // o pacote inteiro — inclinacao e distancia corretas se perdem junto
  // com a vibracao ruim. E o que aconteceu em campo: dezenas de leituras
  // boas descartadas por causa de um unico campo saturado.
  //
  // IMPORTANTE: clampa numa copia de Amostra e usa essa MESMA copia para
  // assinar e para montar o JSON. calcularHmac() assina os campos de "a" —
  // se o clamp so acontecesse na serializacao, a assinatura seria calculada
  // sobre o valor bruto enquanto o payload levaria o valor clampado, e o
  // servidor recusaria TODA leitura por assinatura invalida.
  Amostra a = original;
  a.incl = constrain(a.incl, 0.0, 90.0);
  a.vib  = constrain(a.vib,  0.0, 20.0);
  a.dist = (a.dist < 0) ? -1.0 : constrain(a.dist, 2.0, 400.0);
  if (a.temDHT) {
    a.temp = constrain(a.temp, -10.0, 60.0);
    a.umid = constrain(a.umid,   0.0, 100.0);
  }

  JsonDocument doc;
  doc["schema_v"]  = SCHEMA_V;
  doc["device_id"] = DEVICE_ID;
  doc["equip_id"]  = EQUIP_ID;
  doc["seq"]       = a.seq;
  doc["uptime_ms"] = a.uptime;

  JsonObject tel = doc["tel"].to<JsonObject>();
  tel["inclinacao_g"]      = round(a.incl * 100) / 100.0;
  tel["vibracao_rms"]      = round(a.vib  * 100) / 100.0;
  tel["dist_obstaculo_cm"] = round(a.dist * 100) / 100.0;
  if (a.temDHT) {
    tel["temperatura_c"] = round(a.temp * 100) / 100.0;
    tel["umidade_pct"]   = round(a.umid * 100) / 100.0;
  } else {
    tel["temperatura_c"] = nullptr;    // null, nunca 0 — contrato §2.1 regra 3
    tel["umidade_pct"]   = nullptr;
  }

  JsonObject edge = doc["edge"].to<JsonObject>();
  edge["estado"] = NOME_ESTADO[a.estado];
  edge["regra"]  = a.regra;
  edge["fw"]     = FW_VERSAO;

  char hmacHex[65];
  calcularHmac(a, hmacHex);      // assina a MESMA copia clampada acima
  doc["hmac"] = hmacHex;

  String corpo;
  serializeJson(doc, corpo);

  char url[96];
  snprintf(url, sizeof(url), "http://%s:%d%s", API_HOST, API_PORT, API_PATH);

  HTTPClient http;
  http.setTimeout(TIMEOUT_HTTP);
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  int codigo = http.POST(corpo);

  if (codigo == 202) {
    http.end();
    return true;
  }
  Serial.printf("[HTTP] seq=%lu codigo=%d %s\n", (unsigned long)a.seq, codigo,
                codigo > 0 ? http.getString().c_str() : "sem resposta");
  http.end();
  return false;
}

void bufferizar(const Amostra& a) {
  uint8_t pos = (bufIni + bufQtd) % BUF_OFFLINE;
  bufOffline[pos] = a;
  if (bufQtd < BUF_OFFLINE) bufQtd++;
  else bufIni = (bufIni + 1) % BUF_OFFLINE;   // descarta a mais antiga
}

void drenarBuffer() {
  // Uma por ciclo: esvaziar tudo de uma vez trava o loop e o farol congela.
  if (bufQtd == 0 || WiFi.status() != WL_CONNECTED) return;
  if (enviar(bufOffline[bufIni])) {
    bufIni = (bufIni + 1) % BUF_OFFLINE;
    bufQtd--;
  }
}

void garantirWifi() {
  static uint32_t tTentativa = 0;
  if (WiFi.status() == WL_CONNECTED) return;
  if (millis() - tTentativa < 5000) return;    // nao bloqueia o loop
  tTentativa = millis();
  Serial.println("[WiFi] reconectando...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

// ===========================================================================
// SETUP
// ===========================================================================
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== SOMPO PREDICT · carrinho v" FW_VERSAO " ===");

  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_LED_Y, OUTPUT);
  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  // Teste de farol na subida: se um LED nao acender aqui, e fiacao, nao codigo.
  for (int p : {PIN_LED_G, PIN_LED_Y, PIN_LED_R}) {
    digitalWrite(p, HIGH); delay(200); digitalWrite(p, LOW);
  }

  Wire.begin(PIN_SDA, PIN_SCL);
  dht.begin();
  mpuOk = mpu.begin();
  Serial.println(mpuOk ? "[ok] MPU6050" : "[FALHA] MPU6050 — verifique SDA/SCL");
  if (mpuOk) {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);   // filtro em hardware
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WiFi] conectando");
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) {
    delay(250); Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[ok] IP local: %s  ->  alvo http://%s:%d%s\n",
                  WiFi.localIP().toString().c_str(), API_HOST, API_PORT, API_PATH);
  } else {
    Serial.println("[AVISO] sem Wi-Fi — rodando offline, farol funciona igual");
  }
}

// ===========================================================================
// LOOP · nao-bloqueante
// ===========================================================================
void loop() {
  uint32_t agora = millis();
  if (agora - tLoop < P_LOOP) return;
  tLoop = agora;

  garantirWifi();

  // ---- leitura rapida (10 Hz) ----
  float incl = 0, vib = 0;
  lerMPU(incl, vib);   // false = leitura descartada, incl/vib ficam em 0 (seguro)
  float dist = lerDistanciaCm();

  histIncl[idxMedia] = incl;
  histVib[idxMedia]  = vib;
  histDist[idxMedia] = (dist < 0) ? 400.0 : dist;    // sem eco = longe, pra media
  idxMedia = (idxMedia + 1) % N_MEDIA;
  if (idxMedia == 0) mediaCheia = true;

  float mIncl = mediaDe(histIncl);
  float mVib  = mediaDe(histVib);
  float mDist = mediaDe(histDist);
  if (mDist >= 399.0) mDist = -1.0;

  // ---- leitura lenta (0,2 Hz) — limite fisico do DHT22 ----
  if (agora - tDHT >= P_DHT) {
    tDHT = agora;
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t) && !isnan(h)) { ultimaTemp = t; ultimaUmid = h; }
  }
  bool temDHT = !isnan(ultimaTemp) && !isnan(ultimaUmid);

  // ---- decisao local ----
  char regra[24];
  Estado bruto = classificar(mIncl, mDist, mVib, temDHT ? ultimaUmid : NAN, regra);
  bool critico = (mIncl >= INCL_CRITICA) || (mDist > 0 && mDist <= DIST_CRITICA);
  Estado anterior = estadoAtual;
  Estado estavel = aplicarHisterese(bruto, critico);

  acionarFarol(estavel);

  // ---- envio: evento na hora, senao heartbeat de 1 Hz ----
  bool mudou = (estavel != anterior);
  if (mudou || (agora - tHeartbeat >= P_HEARTBEAT)) {
    tHeartbeat = agora;

    Amostra am;
    am.incl = mIncl; am.vib = mVib; am.dist = mDist;
    am.temp = ultimaTemp; am.umid = ultimaUmid; am.temDHT = temDHT;
    am.estado = estavel; am.uptime = agora; am.seq = ++seqGlobal;
    strncpy(am.regra, regra, sizeof(am.regra));

    if (!enviar(am)) bufferizar(am);
    else drenarBuffer();

    // Serial continua ligado: no checkpoint, mostrar o dado saindo do sensor
    // vale mais que mostrar so a tela final.
    Serial.printf("seq=%lu incl=%.1f vib=%.2f dist=%.0f umid=%.0f -> %s (%s)%s\n",
                  (unsigned long)am.seq, mIncl, mVib, mDist,
                  temDHT ? ultimaUmid : -1.0, NOME_ESTADO[estavel], regra,
                  mudou ? "  <<< EVENTO" : "");
  }
}
