sompo-predict-v15/
│
├── docs/                       # Documentação do Projeto (Rafael e Charles)
│   ├── arquitetura_uml.png     # Diagramas de Implantação, Classes e Casos de Uso
│   ├── pitch_sompo.pdf         # Apresentação executiva
│   └── user_stories.md         # Detalhamento das 8 User Stories do projeto
│
├── edge_iot/                   # Código Embarcado / Hardware (Anthony)
│   ├── src/                    # Scripts em C/C++ para o ESP32
│   │   ├── main.cpp            # Lógica principal de controle
│   │   ├── mpu6050_sensor.cpp  # Leitura dos eixos X, Y, Z (Acelerômetro/Giroscópio)
│   │   └── mqtt_client.cpp     # Envio seguro dos dados via MQTT
│   └── platformio.ini          # Configurações de build e bibliotecas do ESP32
│
├── data_science/               # IA e Engenharia de Dados (Guilherme e Rafael)
│   ├── notebooks/              # Jupyter Notebooks (.ipynb)
│   │   ├── 01_eda_susep.ipynb  # Análise Exploratória da base real da SUSEP
│   │   ├── 02_inmet_clima.ipynb# Integração e Feature Engineering com clima
│   │   └── 03_xgboost_shap.ipynb # Treinamento do modelo de risco e explicabilidade
│   └── models/                 # Modelos exportados (.pkl, .tflite para o Edge)
│
├── backend_api/                # Nuvem AWS, API e Segurança (Gustavo e Charles)
│   ├── app/
│   │   ├── main.py             # Rotas da API (Flask ou FastAPI)
│   │   ├── auth.py             # Controle de acesso com tokens JWT
│   │   └── audit_log.py        # Caixa-preta: Geração de Hashes SHA-256 para logs
│   ├── Dockerfile              # Containerização para deploy na AWS EC2
│   └── requirements.txt        # Dependências Python (Pandas, XGBoost, SHAP, Flask)
│
├── .gitignore                  # Arquivos ignorados pelo Git (MUITO IMPORTANTE)
└── README.md                   # A porta de entrada do projeto
