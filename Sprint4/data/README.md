# Pasta de Dados - Sompo Predict

Esta pasta recebe os arquivos REAIS que substituem os mocks automaticamente.

## Arquivos esperados

| Arquivo                   | Owner     | Descricao                              |
|---------------------------|-----------|----------------------------------------|
| `susep_real.xlsx`         | Guilherme | Base SUSEP rural com 100+ apolices     |
| `telemetria_esp32.csv`    | Anthony   | Leituras do ESP32 via Wokwi            |
| `frota_real.csv`          | Gustavo   | Frota com IDs reais da Sompo           |
| `modelo_xgboost.pkl`      | Guilherme | XGBoost serializado                    |
| `modelo_lstm.h5`          | Gustavo   | LSTM para series temporais             |

## Como funciona

Cada pagina do menu chama `carregar_dataset(caminho, gerador_mock)`.
Se o arquivo existe, usa ele. Se nao, cai no mock automaticamente.
Sem precisar editar codigo Python.
