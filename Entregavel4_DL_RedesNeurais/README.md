# Redes neurais no Sompo Predict: vídeo do 4º entregável

Material do 4º entregável de Redes Neurais & Deep Learning (FIAP, Squad T1). O produto principal é o vídeo `Sompo_Predict_Redes_Neurais.mp4` (4 min 13 s, com legenda em `Sompo_Predict_Redes_Neurais.srt`). O resto da pasta é o que sustenta o que o vídeo mostra.

A pasta foi montada à parte. Nenhum arquivo das sprints anteriores nem do `Entregavel4_ML_Aplicacao` foi alterado. A base em `dados/` é cópia da `base_sompo_limpa.csv` da Sprint 4 (150 apólices da SUSEP, mesmo conteúdo do arquivo original).

## O que o vídeo conta

1. O problema da Sompo e a base disponível.
2. O que o grupo fez com redes neurais: o MLP das Sprints 2 a 4. A LSTM proposta na Sprint 1 não foi implementada, porque a base não tem série temporal por máquina.
3. Onde o MLP entra na solução: como experimento isolado, ao lado do motor de regras que gera o score.
4. Resultado: ROC-AUC de 0,607 ± 0,135 contra 0,553 ± 0,106 do sorteio, dentro de um desvio-padrão. A conclusão é que o gargalo é o volume de dados.
5. Como a rede pode evoluir: LSTM ou autoencoder sobre a telemetria do ESP32, MLP para aprender os pesos da camada de exposição, CNN com transfer learning sobre imagens do terreno.
6. Demonstração de uma prova de conceito com dados simulados.

O texto falado, slide por slide e com os tempos, está em `ROTEIRO.md`.

## Como rodar

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python mlp_base_real.py
.\.venv\Scripts\python prototipo_telemetria.py
.\.venv\Scripts\python gerar_graficos.py
```

Para os testes: `pip install -r requirements-dev.txt` e depois `pytest`.

## Arquivos

```
mlp_base_real.py         refaz a validação cruzada do MLP (32, 16) na base real
prototipo_telemetria.py  autoencoder sobre telemetria simulada do ESP32
gerar_graficos.py        gráficos dos slides, a partir dos resultados dos dois scripts
saida/                   resultados em JSON e gráficos
tests/                   3 testes do protótipo
video/                   slides em HTML, narração, script de montagem e capturas
ROTEIRO.md               texto falado com os tempos
```

Para refazer o vídeo: `python video/montar_video.py` (precisa de Edge, ffmpeg e da voz pt-BR do Windows). Com `--manter-audio` o script reaproveita os `.wav` que já estiverem em `video/audio/`, o que permite trocar a voz sintética por uma gravação própria.

## O que é real e o que é simulado

O MLP e os números do slide 4 vêm da base real, com o mesmo recorte do `avaliacao_modelo.py` da Sprint 4: alvo caso crítico, só variáveis conhecidas na contratação, 5 folds com 10 repetições, semente 42. A Sprint 4 registrou 0,608 ± 0,136 para o MLP. Aqui deu 0,607 ± 0,135; a diferença vem da versão do scikit-learn.

O protótipo do autoencoder usa telemetria simulada. A base da SUSEP não tem leituras de sensor e ainda não existe histórico do carrinho. Os cinco canais seguem o contrato de telemetria v1 e os limites críticos são os do `core_fusao.py` (25 graus e 35 cm), mas os eventos (rampa, obstáculo, superaquecimento) foram desenhados por nós. O script mostra o mecanismo e não mede desempenho em campo. Nada disso entra no score do Sompo Predict.

Resultado da simulação, 40 sequências por tipo de evento: a rede detecta 100% das rampas e dos superaquecimentos e 72% das aproximações de obstáculo. A regra de segurança dispara em 92% das rampas, 100% dos obstáculos e nenhum superaquecimento. Na rampa, a rede alerta em média 18 amostras antes da regra. Em 3% das sequências normais há alarme falso.

## Limites

- A voz do vídeo é sintética (voz do Windows) e a abertura diz "eu sou o Rafael". Para entregar com voz humana, grave a partir do `ROTEIRO.md` e ajuste o nome se outra pessoa apresentar.
- Os números de Sprint 2 e 3 citados nos slides (1.076 parâmetros, experimentos de regularização) vêm da base antiga de 149 registros. Os números do slide 4 vêm da base nova. Os dois conjuntos não são comparáveis entre si.
- O autoencoder usa `MLPRegressor` do scikit-learn, para manter as dependências leves. Em produção a escolha natural seria Keras ou PyTorch, principalmente para uma LSTM.
- As capturas do aplicativo não aparecem no vídeo. A demonstração é a prova de conceito.
