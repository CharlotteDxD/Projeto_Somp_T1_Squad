/* config_exemplo.h — copie para config.h e preencha.
   config.h TEM que estar no .gitignore. Chave commitada = chave vazada. */
#pragma once

#define WIFI_SSID   "SUA_REDE"
#define WIFI_PASS   "SUA_SENHA"

/* Contrato §1.1 — Elastic IP da EC2. Gustavo publica no grupo.
   Bancada: IP local mostrado pelo api_telemetria.py ao subir. */
#define API_HOST    "54.207.000.000"
#define API_PORT    80          /* §1.2 — porta 80, nao 5000 */

#define DEVICE_ID   "T1-CART-01"
#define EQUIP_ID    "COL-000"   /* score_base 55.4 — calibrado pra demo */

/* Mesma string em SOMPO_HMAC_T1_CART_01 no servidor. Minimo 32 bytes. */
#define HMAC_KEY    "troque-esta-chave-32-bytes-minimo"
