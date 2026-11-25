# Roteiro do vídeo

Texto falado em cada slide, com o tempo de cada trecho. Para gravar com a própria voz, leia cada bloco olhando para o slide correspondente (as imagens estão em video/png/).

## Slide 1: O problema (0:00 a 0:27)

Oi, eu sou o Rafael, do grupo T1. Neste vídeo mostro onde usamos redes neurais no Sompo Predict, a solução que montamos para a Sompo. O problema é o de sempre em seguro: a Sompo só fica sabendo que um equipamento agrícola corria risco quando o aviso de sinistro chega. Os dados que temos para ensinar uma rede são poucos, 150 apólices reais da SUSEP, e foi com elas que trabalhamos.

## Slide 2: O que foi desenvolvido (0:28 a 1:06)

Na Sprint 1 propusemos uma rede híbrida, um MLP para o perfil da apólice e uma LSTM para a telemetria. A LSTM ficou no papel, porque a base não tem série temporal por máquina. O MLP foi treinado de verdade. Na Sprint 2 ele nasceu em Keras, com duas camadas escondidas, de 32 e 16 neurônios, e dropout. Na Sprint 3 testamos regularização, parada antecipada e peso por classe. Na Sprint 4, com a base refeita direto da fonte da SUSEP, ele entrou numa validação cruzada junto com mais cinco modelos.

## Slide 3: Onde o modelo foi usado (1:07 a 1:42)

Na solução, a rede fica ao lado do sistema e não decide nada. O score que o produtor e a seguradora enxergam vem de um motor de regras em duas camadas. Por cima dele há uma regra de segurança: inclinação acima de 25 graus, ou obstáculo a menos de 35 centímetros, força o vermelho. O MLP roda como experimento e aparece no aplicativo só para comparação. Foi uma escolha nossa. O motor de regras dá para auditar, e a rede ainda não provou que merece decidir.

## Slide 4: Resultado e contribuição (1:43 a 2:21)

O resultado, em cinquenta partições de validação cruzada: o MLP fez ROC-AUC de 0,61 e o sorteio, 0,55. A diferença é menor que um desvio-padrão, então não dá para afirmar que a rede aprendeu um padrão. A árvore, a floresta e o XGBoost ficaram no mesmo teto. A contribuição da rede neural foi ajudar a mostrar que o limite está no dado: são 14 casos críticos, pouco para qualquer rede. Para a Sompo isso aponta o investimento certo, mais apólices e telemetria acumulada, em vez de outro algoritmo.

## Slide 5: Como a rede pode evoluir (2:22 a 3:07)

Vejo três caminhos. O primeiro é a telemetria. O ESP32 já manda inclinação, vibração, obstáculo, temperatura e umidade. Com histórico, uma LSTM ou um autoencoder aprende como é uma operação normal e avisa quando a máquina foge disso, antes de qualquer limite da regra ser cruzado. O segundo é usar esses mesmos pares de leitura e sinistro para aprender os pesos da camada de exposição do score, que hoje vêm de julgamento de especialista. O terceiro são imagens de drone ou de satélite, com uma CNN pré-treinada, em transfer learning, para enxergar água, erosão e declive do terreno antes de a máquina chegar lá.

## Slide 6: Demonstração (3:08 a 3:56)

Para mostrar a ideia sem prometer o que ainda não temos, fiz uma prova de conceito. Atenção: os dados são simulados, porque não existe histórico de telemetria. Treinei um autoencoder só com janelas de operação normal. Na rampa, o erro da rede passa do limite na amostra 37, e a regra só dispara na 55. Em média, a rede avisa 18 amostras antes. No superaquecimento, com vibração e temperatura subindo juntas, a regra de segurança não olha para isso, e a rede pegou todos os casos simulados. No obstáculo ela deixou passar 28 por cento, que a regra pega por ser um limite fixo. Por isso a ideia é somar a rede à regra.

## Slide 7: Fechamento (3:56 a 4:12)

Resumindo: usamos um MLP de verdade, mantivemos o MLP fora do score e mostramos com número que o gargalo é o dado. O próximo passo é juntar telemetria suficiente para treinar a LSTM. Obrigado.
