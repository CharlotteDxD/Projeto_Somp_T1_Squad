# Sompo Predict

Plataforma de prevenção de risco em seguro rural, desenvolvida pelo Squad T1
no desafio Sompo Seguros · FIAP. Um ESP32 instalado no equipamento agrícola
mede inclinação, vibração e obstáculo à frente. O serviço cruza essas
leituras com o histórico da apólice e entrega o resultado a dois públicos:
o produtor vê o estado da máquina em tempo real, e a seguradora recebe a
carteira ordenada por exposição.

## Onde está cada coisa

| Pasta | Conteúdo |
|---|---|
| [`Sprint4/`](Sprint4/) | **Versão atual.** Dois portais (seguradora e segurado), sensor integrado em tempo real, firmware, serviço de ingestão, publicação em AWS, avaliação de modelos sobre a base real. Comece pelo [README da Sprint 4](Sprint4/README.md). |
| [`Sprint3/`](Sprint3/) | Entrega da Sprint 3, mantida como histórico. |
| `data_science/notebooks/sprint 2/` | Notebooks de pré-processamento e baseline de ML da Sprint 2. |
| Arquivos na raiz | Painel e páginas das Sprints 1 e 2. Não são mais mantidos; a evolução está em `Sprint3/` e `Sprint4/`. |

## Como executar a versão atual

```bash
cd Sprint4
pip install -r requirements.txt
python iniciar_portais.py
```

Portal da Seguradora em http://localhost:8501 e Portal do Segurado em
http://localhost:8502. Integração com o dispositivo e publicação na nuvem
estão descritas em [`Sprint4/INTEGRACAO.md`](Sprint4/INTEGRACAO.md) e
[`Sprint4/deploy/README_AWS.md`](Sprint4/deploy/README_AWS.md).

## Equipe

* **Rafael:** Scrum Master e ML
* **Gustavo:** nuvem (AWS) e deep learning
* **Anthony:** IoT (C++, ESP32 e sensores)
* **Guilherme:** ciência de dados (base SUSEP e INMET)
* **Charles:** backend e segurança

## Licença

Apache 2.0. Ver [LICENSE](LICENSE).
