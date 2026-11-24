# Integração de dispositivos e serviço

Todo o material necessário está acessível pelo próprio sistema, sem
procurar arquivo em pasta.

## Dispositivo em campo

**Menu → Sensores em Campo → Instalação do dispositivo**

A aba reúne, para download:

- **Programa do dispositivo** (`firmware/sompo_predict_esp32.ino`) —
  leitura dos sensores, classificação local de risco, acionamento do
  sinalizador e transmissão assinada.
- **Modelo de configuração** (`firmware/config_exemplo.h`) — preencher com
  o endereço do serviço, o identificador do equipamento e a chave de
  assinatura; salvar como `config.h`. O arquivo preenchido **não deve ser
  versionado**.
- **Especificação do formato de dados**
  (`docs/CONTRATO_TELEMETRIA_v1.md`) — campos, unidades, faixas válidas,
  frequências e regra de assinatura.

O identificador do equipamento no arquivo de configuração precisa
corresponder a um equipamento da carteira. A leitura aparece no Painel do
Segurado assim que a primeira transmissão for aceita.

## Serviço de ingestão

**Menu → Infraestrutura**

Três abas:

- **Estado do serviço** — verificação real contra o endereço configurado,
  com latência medida em cada rota. Não há status declarado em código: o
  que não responde aparece como indisponível.
- **Interface de integração** — rotas expostas, com download da
  especificação e da implementação de referência (`api_telemetria.py`).
- **Publicação** — endereço fixo, publicação em porta 80 e chave por
  dispositivo, com os comandos de cada etapa.

### Executar o serviço

    export SOMPO_HMAC_T1_CART_01="<chave de 32 bytes>"
    PORT=80 python3 api_telemetria.py

Verificação de aceite:

    curl http://<endereco>/whoami

## Apontar a plataforma para o serviço

    # Windows PowerShell
    $env:SOMPO_API_BASE = "http://<ENDERECO>:80"
    streamlit run app.py

Sem a variável, o padrão é `http://localhost:5000`.

## Conferir o estado das integrações

**Menu → Plataforma → Fontes de Dados**

Lista as seis fontes com situação **Conectado**, **Padrão** ou
**Pendente**, e exporta o estado em CSV com data — serve como registro do
que estava ativo em determinado momento.

## Artefatos de dados

Arquivos colocados em `data/` são carregados automaticamente. Ver
`data/LEIAME.md` para a tabela de formatos aceitos.

## Antes de executar

Remova `__pycache__` sempre que substituir arquivos.
