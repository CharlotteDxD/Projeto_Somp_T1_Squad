"""Gera os 7 slides em HTML (1920x1080). A renderização em PNG fica no montar_video.py."""
from pathlib import Path

AQUI = Path(__file__).parent
SAIDA = AQUI.parent / "saida"

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:#020617;color:#F8FAFC;
 font-family:'Segoe UI',system-ui,sans-serif}
.slide{position:relative;width:1920px;height:1080px;padding:84px 120px}
.topo{position:absolute;left:120px;top:56px;font-size:24px;color:#94A3B8;letter-spacing:.02em}
.base{position:absolute;left:120px;bottom:44px;right:120px;font-size:22px;color:#94A3B8;
 display:flex;justify-content:space-between}
h1{font-size:92px;line-height:1.04;font-weight:700;letter-spacing:-.02em}
h2{font-size:68px;line-height:1.08;font-weight:700;letter-spacing:-.015em}
.azul{color:#3B82F6}.ambar{color:#FBBF24}.verm{color:#F87171}.verde{color:#34D399}
.cinza{color:#94A3B8}
.linha{display:grid;grid-template-columns:230px 1fr;gap:48px;padding:30px 0;
 border-top:1px solid #1E293B;align-items:baseline}
.linha:last-child{border-bottom:1px solid #1E293B}
.linha .k{font-size:34px;font-weight:700;color:#3B82F6}
.linha .v{font-size:36px;line-height:1.3}
.linha .v small{display:block;font-size:27px;color:#94A3B8;margin-top:6px}
.aviso{display:inline-block;border:2px solid #FBBF24;color:#FBBF24;padding:6px 18px;
 border-radius:4px;font-size:26px;font-weight:600}
"""


def pagina(corpo: str, n: int) -> str:
    return (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
            f"<title>Slide {n}</title><style>{CSS}</style></head><body>{corpo}</body></html>")


def rodape(texto="Challenge FIAP e Sompo, Grupo T1, Redes Neurais & Deep Learning"):
    return f"<div class='base'><span>{texto}</span></div>"


def s1():
    return pagina("""
<div class='slide'>
 <div class='topo'>4º entregável, Redes Neurais</div>
 <div style='position:absolute;left:120px;top:210px;width:1260px'>
  <h1 style='font-size:80px'>Redes neurais no Sompo Predict: o que fizemos, onde entraram e o que vem depois</h1>
  <p style='font-size:38px;line-height:1.35;margin-top:48px;color:#CBD5E1'>
   Hoje a Sompo descobre que uma máquina agrícola estava em risco quando o aviso de sinistro chega.</p>
 </div>
 <div style='position:absolute;right:120px;top:250px;width:380px;text-align:left'>
  <div style='font-size:150px;font-weight:700;line-height:1;color:#3B82F6'>150</div>
  <div style='font-size:30px;color:#CBD5E1;margin-bottom:64px'>apólices reais da SUSEP, Seguro Rural 2021</div>
  <div style='font-size:150px;font-weight:700;line-height:1;color:#F87171'>14</div>
  <div style='font-size:30px;color:#CBD5E1'>casos críticos para a rede aprender</div>
 </div>
""" + rodape() + "</div>", 1)


def s2():
    return pagina("""
<div class='slide'>
 <div class='topo'>O que foi desenvolvido</div>
 <h2 style='margin-top:96px;margin-bottom:56px'>Um MLP de verdade. A LSTM ficou no papel.</h2>
 <div>
  <div class='linha'><div class='k'>Sprint 1</div><div class='v'>Proposta: MLP para o perfil da apólice e LSTM para a telemetria
    <small class='ambar' style='color:#FBBF24'>LSTM não implementada: a base não tem série temporal por máquina</small></div></div>
  <div class='linha'><div class='k'>Sprint 2</div><div class='v'>MLP em Keras, camadas de 32 e 16 neurônios, dropout
    <small>1.076 parâmetros, Early Stopping</small></div></div>
  <div class='linha'><div class='k'>Sprint 3</div><div class='v'>Regularização, parada antecipada e peso por classe
    <small>Único modelo do projeto a acertar um caso crítico, ao custo de perder a classe Alto</small></div></div>
  <div class='linha'><div class='k'>Sprint 4</div><div class='v'>Base refeita da SUSEP; MLP na validação cruzada com outros cinco modelos
    <small>5 folds x 10 repetições, só variáveis conhecidas na contratação</small></div></div>
 </div>
""" + rodape() + "</div>", 2)


def s3():
    svg = """
<svg width='1680' height='560' viewBox='0 0 1680 560' xmlns='http://www.w3.org/2000/svg'
 font-family="Segoe UI, sans-serif">
 <defs><marker id='a' markerWidth='12' markerHeight='12' refX='10' refY='6' orient='auto'>
  <path d='M0,0 L12,6 L0,12 z' fill='#94A3B8'/></marker>
  <marker id='b' markerWidth='12' markerHeight='12' refX='10' refY='6' orient='auto'>
  <path d='M0,0 L12,6 L0,12 z' fill='#FBBF24'/></marker></defs>
 <g fill='none' stroke='#475569' stroke-width='2'>
  <rect x='0' y='40' width='330' height='130' rx='6'/>
  <rect x='0' y='210' width='330' height='130' rx='6'/>
  <rect x='480' y='60' width='450' height='260' rx='6' stroke='#3B82F6' stroke-width='4'/>
  <rect x='1080' y='110' width='260' height='160' rx='6'/>
  <rect x='1470' y='60' width='210' height='120' rx='6'/>
  <rect x='1470' y='210' width='210' height='120' rx='6'/>
 </g>
 <g fill='#F8FAFC' font-size='30'>
  <text x='24' y='94'>Apólice</text><text x='24' y='136' font-size='24' fill='#94A3B8'>base SUSEP</text>
  <text x='24' y='264'>Telemetria</text><text x='24' y='306' font-size='24' fill='#94A3B8'>ESP32, 5 sensores</text>
  <text x='506' y='116' font-size='36' font-weight='700'>Motor de regras</text>
  <text x='506' y='164' font-size='26' fill='#94A3B8'>perfil da apólice (lento)</text>
  <text x='506' y='204' font-size='26' fill='#94A3B8'>x exposição em campo (rápido)</text>
  <text x='506' y='270' font-size='26' fill='#3B82F6'>em produção, auditável</text>
  <text x='1104' y='176' font-size='36' font-weight='700'>Score</text>
  <text x='1104' y='222' font-size='26' fill='#94A3B8'>0 a 100</text>
  <text x='1494' y='112'>Portal da</text><text x='1494' y='150'>seguradora</text>
  <text x='1494' y='262'>Portal do</text><text x='1494' y='300'>produtor</text>
 </g>
 <g stroke='#94A3B8' stroke-width='3' fill='none' marker-end='url(#a)'>
  <path d='M330 105 L480 150'/><path d='M330 275 L480 230'/><path d='M930 190 L1080 190'/>
  <path d='M1340 170 L1470 120'/><path d='M1340 210 L1470 260'/>
 </g>
 <g>
  <rect x='480' y='400' width='450' height='120' rx='6' fill='none' stroke='#FBBF24' stroke-width='3'
   stroke-dasharray='12 8'/>
  <text x='506' y='452' font-size='34' font-weight='700' fill='#FBBF24'>MLP (32, 16)</text>
  <text x='506' y='494' font-size='26' fill='#94A3B8'>experimento isolado, não decide</text>
  <path d='M330 320 C 400 430, 420 450, 480 455' stroke='#FBBF24' stroke-width='3' fill='none'
   stroke-dasharray='10 8' marker-end='url(#b)'/>
  <path d='M930 460 L1150 460' stroke='#FBBF24' stroke-width='3' fill='none' stroke-dasharray='10 8'
   marker-end='url(#b)'/>
  <text x='1170' y='452' font-size='30' fill='#F8FAFC'>aba de comparação no app</text>
  <text x='1170' y='492' font-size='24' fill='#94A3B8'>ao lado do score de regras</text>
 </g>
 <g>
  <text x='1040' y='334' font-size='26' fill='#F87171'>regra de segurança por cima:</text>
  <text x='1040' y='368' font-size='26' fill='#F87171'>inclinação &gt; 25° ou obstáculo &lt; 35 cm</text>
  <text x='1040' y='402' font-size='26' fill='#F87171'>força o vermelho</text>
 </g>
</svg>"""
    return pagina(f"""
<div class='slide'>
 <div class='topo'>Onde o modelo foi usado</div>
 <h2 style='margin-top:96px;margin-bottom:40px'>O MLP roda ao lado do score e não decide nada.</h2>
 <div style='margin-left:-0px'>{svg}</div>
""" + rodape() + "</div>", 3)


def s4():
    return pagina("""
<div class='slide'>
 <div class='topo'>Resultado e contribuição</div>
 <h2 style='margin-top:96px;width:1500px'>O MLP fez <span class='azul'>0,61</span> de ROC-AUC. O sorteio fez <span class='cinza'>0,55</span>.</h2>
 <div style='display:flex;gap:64px;margin-top:40px;align-items:flex-start'>
  <img src='../../saida/grafico_auc.png' style='width:960px;height:auto'>
  <div style='width:700px;font-size:36px;line-height:1.38'>
   <p>A diferença é menor que um desvio-padrão. Árvore, floresta e XGBoost ficaram no mesmo teto.</p>
   <p style='margin-top:28px'>O que a rede mostrou: o limite está no dado. São <b class='verm'>14</b> casos críticos.</p>
   <p style='margin-top:28px' class='cinza'>Investir em apólices e telemetria, não em outro algoritmo.</p>
  </div>
 </div>
""" + rodape("Fonte: mlp_base_real.py, validação cruzada 5 folds x 10 repetições, semente 42, alvo caso crítico") + "</div>", 4)


def s5():
    return pagina("""
<div class='slide'>
 <div class='topo'>Como a rede pode evoluir</div>
 <h2 style='margin-top:96px;margin-bottom:56px'>Três usos, e todos precisam de dado novo.</h2>
 <div>
  <div class='linha'><div class='k'>Telemetria</div><div class='v'>LSTM ou autoencoder sobre as leituras do ESP32: aprende a operação normal e avisa o desvio, antes do limite da regra
    <small>Precisa de: histórico de leituras por máquina</small></div></div>
  <div class='linha'><div class='k'>Pesos</div><div class='v'>MLP que aprende os pesos da camada de exposição do score, hoje definidos por julgamento de especialista
    <small>Precisa de: pares de leitura de campo e sinistro</small></div></div>
  <div class='linha'><div class='k'>Imagens</div><div class='v'>CNN pré-treinada (transfer learning) em imagem de drone ou satélite: água, erosão, declive
    <small>Precisa de: imagens do terreno das propriedades seguradas</small></div></div>
 </div>
""" + rodape() + "</div>", 5)


def s6():
    return pagina("""
<div class='slide'>
 <div class='topo'>Demonstração: prova de conceito com autoencoder</div>
 <div style='position:absolute;right:120px;top:50px'><span class='aviso'>Dados simulados</span></div>
 <h2 style='margin-top:96px;font-size:58px'>Só com operação normal no treino, o erro da rede vira alerta.</h2>
 <div style='display:flex;gap:56px;margin-top:36px;align-items:flex-start'>
  <img src='../../saida/grafico_telemetria.png' style='width:1130px;height:auto'>
  <div style='width:520px'>
   <div class='linha' style='grid-template-columns:1fr;gap:4px;padding:20px 0'>
     <div class='k' style='font-size:30px'>Rampa</div>
     <div class='v' style='font-size:32px'>rede detecta <b class='verde'>100%</b>, regra <b>92%</b></div>
     <div class='v' style='font-size:28px;color:#94A3B8'>rede avisa 18 amostras antes</div></div>
   <div class='linha' style='grid-template-columns:1fr;gap:4px;padding:20px 0'>
     <div class='k' style='font-size:30px'>Superaquecimento</div>
     <div class='v' style='font-size:32px'>rede detecta <b class='verde'>100%</b>, regra <b class='verm'>0%</b></div>
     <div class='v' style='font-size:28px;color:#94A3B8'>a regra de segurança não olha para isso</div></div>
   <div class='linha' style='grid-template-columns:1fr;gap:4px;padding:20px 0'>
     <div class='k' style='font-size:30px'>Obstáculo</div>
     <div class='v' style='font-size:32px'>rede detecta <b class='ambar'>72%</b>, regra <b>100%</b></div>
     <div class='v' style='font-size:28px;color:#94A3B8'>limite fixo é a regra pegando melhor</div></div>
  </div>
 </div>
""" + rodape("Fonte: prototipo_telemetria.py, semente 42. Alarme falso em 3% das sequências normais. Não mede desempenho real") + "</div>", 6)


def s7():
    return pagina("""
<div class='slide'>
 <div class='topo'>Fechamento</div>
 <div style='position:absolute;left:120px;top:240px;width:1500px'>
  <h1 style='font-size:84px'>Usamos um MLP de verdade.</h1>
  <h1 style='font-size:84px;margin-top:20px'>Ele ficou fora do score.</h1>
  <h1 style='font-size:84px;margin-top:20px'>O número mostrou: o gargalo é o <span class='azul'>dado</span>.</h1>
  <p style='font-size:38px;margin-top:64px;color:#CBD5E1;line-height:1.4'>
   Próximo passo: juntar telemetria para treinar a LSTM.</p>
 </div>
""" + rodape("Grupo T1, FIAP e Sompo. Código e dados em Entregavel4_DL_RedesNeurais") + "</div>", 7)


SLIDES = [s1, s2, s3, s4, s5, s6, s7]


def gerar():
    pasta = AQUI / "slides"
    pasta.mkdir(exist_ok=True)
    caminhos = []
    for i, f in enumerate(SLIDES, 1):
        p = pasta / f"slide_{i:02d}.html"
        p.write_text(f(), encoding="utf-8")
        caminhos.append(p)
    return caminhos


if __name__ == "__main__":
    print(len(gerar()), "slides")
