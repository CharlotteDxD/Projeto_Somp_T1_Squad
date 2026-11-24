# Pasta de artefatos externos

Os arquivos abaixo são carregados **automaticamente** quando presentes.
Nenhuma alteração de código é necessária: basta colocar o arquivo aqui e
recarregar a página. A tela **Fontes de Dados** (menu → Plataforma) mostra
o que foi carregado e o que continua pendente.

| Arquivo | Efeito no sistema | Requisito de formato |
|---|---|---|
| `susep_real.xlsx` | Substitui a base de apólices em toda a plataforma | Colunas `UF`, `MODALIDADE_SUSEP`, `QTD_COBERTURAS_CONTRATADAS`, `PREMIO_LIQUIDO_BRL`, `VALOR_INDENIZADO_BRL` |
| `modelo_xgboost.pkl` | Modelo treinado passa a compor o cálculo de risco | Objeto com `predict_proba` (joblib ou pickle) |
| `modelo_lstm.h5` | Habilita detecção de anomalia na série do equipamento | Modelo Keras carregável |
| `frota_real.csv` | Identificadores de operação no lugar de `COL-000…` | Coluna `equip_id` |
| `telemetria_esp32.csv` | Alimenta gráficos quando o serviço ao vivo está fora | Leituras acumuladas |

Arquivo fora do formato exigido é **recusado na carga**, com o motivo
descrito no cartão correspondente da tela Fontes de Dados. Nunca é aceito
em silêncio — um artefato inválido carregado sem aviso reapareceria como
número errado três telas adiante.

## Telemetria ao vivo

Não é arquivo, é endereço de serviço:

    # Windows PowerShell
    $env:SOMPO_API_BASE = "http://<ENDERECO_DO_SERVICO>:80"
    streamlit run app.py

Sem essa variável, o padrão é `http://localhost:5000`.

## Enquanto os artefatos não chegam

O sistema opera normalmente. A base padrão de 150 itens (máquinas agrícolas,
SUSEP R_RURAL/S_RURAL 2021, GO/MS/MT — ver rastreabilidade_secao_6_1.md), o cálculo
determinístico de risco e os identificadores sequenciais cobrem todas as
telas. A tela Fontes de Dados distingue três situações:

- **Conectado** — artefato externo carregado e validado.
- **Padrão** — o artefato não existe, mas há caminho alternativo em
  operação. O sistema funciona.
- **Pendente** — a funcionalidade depende do artefato e está inativa.
