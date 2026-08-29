# Sompo Predict

Plataforma de prevenção de risco em seguro rural. Telemetria embarcada em
equipamento agrícola, combinada com o histórico da apólice, para antecipar
sinistro em vez de indenizá-lo.

O produtor recebe um sinalizador em campo; a seguradora recebe a carteira
ordenada por exposição. **O sistema alerta — a decisão de interromper a
operação permanece com o operador.**

Projeto acadêmico desenvolvido para o desafio Sompo Seguros · FIAP.

---

## Como executar

### Requisitos

- Python 3.10 ou superior
- Para o dispositivo: Arduino IDE com suporte a ESP32

### Instalação

```bash
git clone <url-do-repositorio>
cd sompo-predict
pip install -r requirements.txt
```

### Executando os dois portais

A plataforma serve dois públicos com o mesmo código. Para subir os dois de
uma vez:

```bash
python iniciar_portais.py
```

| Portal | Endereço | Público |
|---|---|---|
| Sompo Predict | http://localhost:8501 | Subscritor, analista, gestor |
| Minha Máquina | http://localhost:8502 | Produtor rural, operador |

Contas de demonstração:

| Usuário | Senha | Perfil |
|---|---|---|
| `admin` | `Admin@2024!` | Admin — acesso completo |
| `produtor` | `Produtor@2024!` | Segurado — apenas o próprio equipamento |

> As senhas acima são de um ambiente de demonstração, sem dado real de
> cliente. Podem ser sobrescritas pelas variáveis `SOMPO_SENHA_ADMIN` e
> `SOMPO_SENHA_PRODUTOR`.

### Executando um portal isolado

```bash
# Portal da seguradora (padrão)
streamlit run app.py

# Portal do segurado
# Linux/macOS
SOMPO_PERFIL=cliente streamlit run app.py --server.port 8502
# Windows PowerShell
$env:SOMPO_PERFIL = "cliente"; streamlit run app.py --server.port 8502
```

### Serviço de ingestão de telemetria

O serviço que recebe as leituras do dispositivo roda separado do painel:

```bash
python iniciar_local.py
```

Ele gera a chave de assinatura, imprime o endereço para configurar no
dispositivo e sobe o serviço. Para apontar o painel para ele:

```bash
# Linux/macOS
export SOMPO_API_BASE="http://<endereco>:5000"
# Windows PowerShell
$env:SOMPO_API_BASE = "http://<endereco>:5000"
```

Publicação em nuvem: ver [`deploy/README_AWS.md`](deploy/README_AWS.md).

---

## Estrutura do repositório

```
├── app.py                      Aplicação principal (painel, os dois portais)
├── api_telemetria.py           Serviço de ingestão — recebe e valida leituras
├── wsgi.py                     Ponto de entrada de produção (gunicorn)
├── iniciar_portais.py          Sobe os dois portais simultaneamente
├── iniciar_local.py            Sobe o serviço de ingestão em rede local
│
├── core_fusao.py               Motor de cálculo de risco (duas camadas)
├── core_perfis.py              Definição dos dois portais e suas telas
├── core_app.py                 Controle de acesso (RBAC/JWT) e componentes
├── core_audit.py               Trilha de auditoria encadeada (SHA-256 + AES)
├── core_procedencia.py         Registro de origem dos dados exibidos
├── core_relatorio.py           Análise de tendência sobre séries de telemetria
├── core_integracao.py          Carga de artefatos externos, com validação
├── motor_simulacao.py          Geração de telemetria para demonstração
├── pagina_*.py                 Uma tela por arquivo
│
├── firmware/                   Código do dispositivo (ESP32)
│   ├── sompo_predict_esp32.ino
│   └── config_exemplo.h        Modelo — copiar para config.h e preencher
│
├── docs/
│   └── CONTRATO_TELEMETRIA_v1.md   Formato de dados entre dispositivo e nuvem
│
├── deploy/                     Publicação em nuvem (AWS EC2)
│   ├── README_AWS.md
│   ├── bootstrap_ec2.sh        Instalação automatizada
│   ├── verificar.sh            Teste de aceite (9 verificações)
│   ├── sompo-api.service       Serviço systemd
│   └── sompo-api.env.exemplo   Modelo de configuração — sem chave real
│
├── scripts/
│   ├── auditoria_procedencia.py    Verifica dado simulado sem identificação
│   ├── avaliacao_modelo.py         Validação cruzada com baseline
│   └── avaliar_modelo_rafael.py    Reproduz o pipeline de ML e exporta métricas
│
├── data/
│   ├── base_sompo_limpa.csv    Base de apólices (SUSEP, 149 registros)
│   └── LEIAME.md               Onde colocar artefatos externos
│
└── data_science/notebooks/     Análise exploratória e modelagem
```

---

## Arquitetura

```
Sensores → ESP32 → HMAC-SHA256 → Serviço de ingestão → Painel
                                        │
                                   core_fusao
                                (cálculo de risco)
```

**Decisão local.** A classificação de risco acontece no próprio
equipamento, a 10 Hz, sem depender de conexão. Sem rede, as leituras ficam
retidas e são reenviadas quando a conexão volta — o alerta ao operador
nunca depende do enlace.

**Score em duas camadas.** O perfil da apólice (idade da máquina, estado,
cobertura) muda de mês em mês; a exposição do momento (o que o sensor está
medindo) muda a cada segundo. As duas entram juntas: a mesma inclinação de
14° é aceitável numa colheitadeira nova e crítica numa máquina de quinze
anos em região de alta sinistralidade.

**Autenticação do dispositivo.** Cada leitura chega assinada por
HMAC-SHA256 com chave por dispositivo. Payload alterado em trânsito é
recusado com HTTP 401; reenvio da mesma sequência, com 409.

---

## Segurança

- Autenticação de usuário com Argon2id e sessão via JWT
- Controle de acesso por papel (RBAC), com o papel Segurado restrito ao
  próprio equipamento — sem acesso à carteira
- Segunda camada independente: cada rota é conferida contra o menu do
  portal ativo antes de renderizar
- Trilha de auditoria encadeada por SHA-256, com conteúdo cifrado em AES
- Nenhuma chave, senha real ou token neste repositório. O arquivo
  `config.h` do dispositivo e a chave gerada localmente estão no
  `.gitignore`; os modelos versionados (`config_exemplo.h`,
  `sompo-api.env.exemplo`) contêm apenas marcadores.

---

## Limitações declaradas

O projeto documenta o que a base atual permite e o que não permite
concluir:

- A base histórica tem 149 apólices, com 12 casos críticos. Modelos
  estatísticos treinados sobre ela **não superaram a referência aleatória**
  — o cálculo em produção é determinístico, com pesos justificados, e o
  resultado negativo dos modelos está reportado na tela *Desempenho dos
  Modelos*.
- Os pesos da camada de telemetria são limiares de especialista, não
  aprendidos: a base histórica não contém leitura de sensor, então não
  existe par (telemetria, sinistro) para treinar.
- Enquanto o dispositivo não está instalado em frota, parte das telas opera
  sobre dados de demonstração. Toda tela nessa condição exibe aviso
  explícito, e a tela *Fontes de Dados* informa a origem de cada
  informação.

---

## Equipe

Squad T1 — FIAP & Sompo Seguros

| Integrante | Frente |
|---|---|
| Anthony Prado Pereira | IoT e sistemas embarcados |
| Charles Augusto Miranda da Silva | Cybersegurança · Produto e experiência |
| Guilherme Araujo Pinto | Estatística e dados · banco de dados |
| Gustavo Reatti Sela | Computação em nuvem |
| Rafael Gonçalves | Scrum Master · Machine Learning |

## Licença

Ver [LICENSE](LICENSE).
