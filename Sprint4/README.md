# Sompo Predict · Sprint 4

Plataforma de prevenção de risco em seguro rural. Um dispositivo ESP32 no
equipamento agrícola mede inclinação, vibração, obstáculo à frente e
condição ambiente; o serviço cruza essas leituras com o histórico da
apólice e entrega o resultado a dois públicos ao mesmo tempo: o produtor
vê um sinalizador no portal dele, e a seguradora recebe a carteira ordenada
por exposição.

O sistema alerta. A decisão de parar a operação continua com o operador.

Projeto acadêmico do desafio Sompo Seguros · FIAP, Squad T1. A versão desta
pasta foi apresentada no NEXT.

---

## O que mudou desde a Sprint 3

- **Dois portais sobre o mesmo código.** Portal da Seguradora (Sompo Predict,
  16 telas) e Portal do Segurado (Minha Máquina, 4 telas), escolhidos por
  `SOMPO_PERFIL`. Detalhes em [`PORTAIS.md`](PORTAIS.md).
- **Menu e painel do cliente refeitos.** `pagina_us03_painel_cliente.py`
  (situação atual, sinalizador e explicação em linguagem comum) e
  `pagina_meu_equipamento.py` (histórico e tendência de um único
  equipamento, sem carregar a frota inteira).
- **Sensor integrado em tempo real.** O ESP32 transmite leituras assinadas
  com HMAC-SHA256 para `api_telemetria.py`, e o Painel do Segurado
  atualiza a partir delas. Passo a passo em [`INTEGRACAO.md`](INTEGRACAO.md),
  formato de dados em
  [`docs/CONTRATO_TELEMETRIA_v1.md`](docs/CONTRATO_TELEMETRIA_v1.md).
- **Firmware com proteção contra leitura travada do MPU-6050.** Em campo o
  sensor chegou a repetir o mesmo valor de vibração por dezenas de ciclos,
  acima do que o acelerômetro produz fisicamente. O firmware agora descarta
  esse tipo de leitura, reinicia o barramento I2C e limita cada campo à
  faixa aceita pelo servidor antes de assinar o pacote.
- **Publicação em AWS EC2** com script de instalação, serviço systemd e
  teste de aceite (`deploy/`).
- **Base de apólices corrigida.** 150 registros SUSEP rastreáveis, com
  procedência documentada em [`PROCEDENCIA_DADOS.md`](PROCEDENCIA_DADOS.md)
  e [`rastreabilidade_secao_6_1.md`](rastreabilidade_secao_6_1.md).
- **Avaliação de modelos refeita sobre a base real**, sem as variáveis que
  vazavam o alvo. Resultados em
  [`RESULTADOS_MODELO_sprint4.md`](RESULTADOS_MODELO_sprint4.md) e
  [`CHANGELOG_scoragem_sprint4.md`](CHANGELOG_scoragem_sprint4.md).
- **Novas telas e módulos:** Simulador de Cenários, Relatório de Risco,
  Explicabilidade, Desempenho dos Modelos, Fontes de Dados e Infraestrutura.
- **Material comercial:**
  [`SOMPO_PREDICT_apresentacao_comercial.pdf`](SOMPO_PREDICT_apresentacao_comercial.pdf).

---

## Como executar

Requisitos: Python 3.10 ou superior. Para o dispositivo, Arduino IDE com
suporte a ESP32.

```bash
cd Sprint4
pip install -r requirements.txt
```

### Os dois portais juntos

```bash
python iniciar_portais.py
```

| Portal | Endereço | Público |
|---|---|---|
| Sompo Predict | http://localhost:8501 | Subscritor, analista, gestor |
| Minha Máquina | http://localhost:8502 | Produtor rural, operador |

As contas de demonstração estão em [`PORTAIS.md`](PORTAIS.md). São de um
ambiente sem dado real. Em uma instalação que não seja demonstração, defina
`SOMPO_JWT_SECRET` e `SOMPO_KMS_KEY`; sem elas, o painel gera valores novos
a cada início.

### Um portal isolado

```bash
# Seguradora (padrão)
streamlit run app.py

# Segurado, PowerShell
$env:SOMPO_PERFIL = "cliente"; streamlit run app.py --server.port 8502
```

### Serviço de ingestão de telemetria

```bash
# Linux/macOS
export SOMPO_HMAC_T1_CART_01="<chave de 32 bytes>"
PORT=80 python3 api_telemetria.py
```

Para apontar o painel para ele:

```powershell
$env:SOMPO_API_BASE = "http://<endereco>:80"
streamlit run app.py
```

Sem a variável, o painel procura o serviço em `http://localhost:5000`.
Publicação na nuvem: [`deploy/README_AWS.md`](deploy/README_AWS.md).

### Dispositivo

1. Copie `firmware/config_exemplo.h` para `firmware/config.h` e preencha Wi-Fi,
   endereço do serviço, identificador do equipamento e chave de assinatura.
2. Abra `firmware/sompo_predict_esp32.ino` na Arduino IDE e grave no ESP32.

O `config.h` preenchido não deve ser versionado.

---

## Estrutura

```
Sprint4/
├── app.py                    Painel principal (os dois portais)
├── api_telemetria.py         Serviço de ingestão: recebe e valida leituras
├── wsgi.py                   Entrada de produção (gunicorn)
├── iniciar_portais.py        Sobe os dois portais
│
├── core_fusao.py             Cálculo de risco em duas camadas
├── core_perfis.py            Definição dos portais e de suas telas
├── core_app.py               Controle de acesso (RBAC/JWT)
├── core_audit.py             Trilha de auditoria encadeada
├── core_procedencia.py       Origem dos dados exibidos
├── core_integracao.py        Carga de artefatos externos, com validação
├── core_relatorio.py         Tendência sobre séries de telemetria
├── core_ranking.py           Ranking de exposição da carteira
├── core_recomendacoes.py     Recomendações por equipamento
├── core_data_adapter.py      Leitura da base de apólices
├── motor_simulacao.py        Telemetria simulada para demonstração
├── pagina_*.py               Uma tela por arquivo
│
├── avaliacao_modelo.py       Validação cruzada com baseline
├── avaliar_modelo_rafael.py  Pipeline de ML; gera metricas_modelo.json
├── auditoria_procedencia.py  Procura dado simulado sem identificação
├── auditoria_mock.py         Mapa do que ainda é simulado
│
├── firmware/                 ESP32 + modelo de configuração
├── deploy/                   AWS EC2: bootstrap, systemd, verificação
├── docs/                     Contrato de telemetria
├── data/                     Onde entram artefatos externos (LEIAME.md)
├── data_science/notebooks/   Notebooks da Sprint 2
└── base_sompo_limpa.csv      Base de apólices (SUSEP, 150 registros)
```

---

## Arquitetura

```
Sensores → ESP32 → HMAC-SHA256 → Serviço de ingestão → Painéis
                                        │
                                   core_fusao
                                (cálculo de risco)
```

- **Decisão local.** O dispositivo classifica o risco a 10 Hz sem depender
  de rede. Sem conexão, as leituras ficam retidas e são reenviadas depois.
- **Score em duas camadas.** O perfil da apólice (idade da máquina, estado,
  cobertura) muda por mês; a exposição do momento vem do sensor, a cada
  segundo. A mesma inclinação pesa diferente numa máquina nova e numa de
  quinze anos em região de alta sinistralidade.
- **Autenticação do dispositivo.** Leitura com payload alterado recebe
  HTTP 401; reenvio da mesma sequência recebe 409.

## Segurança

- Senhas com Argon2id e sessão via JWT.
- Controle por papel (RBAC). O papel Segurado só alcança o próprio
  equipamento.
- Cada rota é conferida contra o menu do portal ativo antes de renderizar,
  e a tentativa fora do portal fica na trilha de auditoria.
- Trilha de auditoria encadeada por SHA-256, com conteúdo cifrado em AES.
- Nenhuma chave real neste repositório. `config.h` e `.env` estão no
  `.gitignore`; os modelos versionados (`config_exemplo.h`,
  `sompo-api.env.exemplo`) trazem só marcadores.

## Limitações

- A base tem 150 apólices e 14 casos críticos. Com as variáveis disponíveis
  na subscrição, nenhum modelo estatístico superou o baseline aleatório
  (ROC-AUC entre 0,50 e 0,61 contra 0,553). Por isso o score de produção é
  determinístico, com pesos justificados, e o resultado negativo aparece na
  tela Desempenho dos Modelos.
- Os pesos da camada de telemetria são limiares definidos por especialista.
  A base histórica não tem leitura de sensor, então não existe par
  (telemetria, sinistro) para treinar.
- Equipamentos sem dispositivo instalado usam dados de demonstração. Cada
  tela nessa condição avisa, e Fontes de Dados mostra a origem de cada
  informação.

## Equipe

Squad T1 · FIAP e Sompo Seguros. Rafael (Scrum Master e ML), Gustavo
(nuvem), Anthony (IoT), Guilherme (ciência de dados) e Charles (backend e
segurança).
