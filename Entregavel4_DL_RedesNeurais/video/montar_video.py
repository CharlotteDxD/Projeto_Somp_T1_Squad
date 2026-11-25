"""Monta o vídeo: renderiza os slides (Edge), gera a voz (Windows, voz pt-BR) e junta com o ffmpeg.

    python montar_video.py

Precisa de Edge, ffmpeg no PATH e a voz "Microsoft Maria Desktop". A voz é só um
rascunho: para a entrega, dá para gravar a própria voz lendo o ROTEIRO.md e
trocar os .wav da pasta audio/ (o script usa o .wav que já existir se passar --manter-audio).
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import slides

AQUI = Path(__file__).parent
PNG, AUDIO, CLIPES = AQUI / "png", AQUI / "audio", AQUI / "clipes"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
FINAL = AQUI.parent / "Sompo_Predict_Redes_Neurais.mp4"
LEGENDA = AQUI.parent / "Sompo_Predict_Redes_Neurais.srt"
PAUSA_FINAL = 0.7  # segundos de respiro depois de cada fala

# como o sintetizador deve ler o que ele lê mal
PRONUNCIA = {
    "ROC-AUC": "rók áuc", "MLP": "ême éle pê", "LSTM": "éle esse tê ême",
    "CNN": "cê ene ene", "ESP32": "é esse pê trinta e dois", "SUSEP": "Susépi",
    "XGBoost": "ékis guê bust", "Keras": "Quéras", "Early Stopping": "érli stópin",
    "dropout": "drópaut", "transfer learning": "transfér lérnin",
    "autoencoder": "auto encóder", "Sprint": "Sprínt", "T1": "tê um",
}


def executar(*args, **kw):
    r = subprocess.run(args, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"falhou: {' '.join(map(str, args))[:200]}\n{r.stderr[-600:]}")
    return r


def renderizar_slides():
    PNG.mkdir(exist_ok=True)
    perfil = Path.home() / "AppData" / "Local" / "Temp" / "edge_slides_profile"
    for p in slides.gerar():
        saida = PNG / (p.stem + ".png")
        saida.unlink(missing_ok=True)  # o Edge devolve o controle antes de gravar
        subprocess.run(
            [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--user-data-dir={perfil}", "--window-size=1920,1080",
             f"--screenshot={saida}", p.resolve().as_uri()],
            capture_output=True, timeout=120)
        for _ in range(40):
            if saida.exists() and saida.stat().st_size > 20000:
                time.sleep(0.5)
                break
            time.sleep(0.5)
        else:
            sys.exit(f"slide não renderizou: {p.name}")


def falar(texto, wav):
    for chave, leitura in PRONUNCIA.items():
        texto = texto.replace(chave, leitura)
    txt = wav.with_suffix(".txt")
    txt.write_text(texto, encoding="utf-8")
    ps = ("Add-Type -AssemblyName System.Speech;"
          "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
          "$s.SelectVoice('Microsoft Maria Desktop');$s.Rate=2;"
          f"$s.SetOutputToWaveFile('{wav}');"
          f"$s.Speak((Get-Content -Raw -Encoding UTF8 '{txt}'));$s.Dispose()")
    executar("powershell", "-NoProfile", "-Command", ps)
    txt.unlink()


def duracao(arquivo):
    r = executar("ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(arquivo))
    return float(r.stdout.strip())


def tempo_srt(t):
    h, resto = divmod(t, 3600)
    m, s = divmod(resto, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


def trechos(texto, limite=95):
    frases = re.split(r"(?<=[.:?!])\s+", texto)
    saida = []
    for f in frases:
        partes = re.split(r"(?<=,)\s+", f) if len(f) > limite else [f]
        atual = ""
        for p in partes:
            if atual and len(atual) + len(p) > limite:
                saida.append(atual); atual = p
            else:
                atual = f"{atual} {p}".strip()
        saida.append(atual)
    return [s for s in saida if s]


def escrever_roteiro(roteiro):
    linhas = ["# Roteiro do vídeo", "",
              "Texto falado em cada slide, com o tempo de cada trecho. Para gravar com a própria voz, "
              "leia cada bloco olhando para o slide correspondente (as imagens estão em video/png/).", ""]
    t = 0.0
    for i, b in enumerate(roteiro, 1):
        d = duracao(AUDIO / f"{b['id']}.wav")
        linhas += [f"## Slide {i}: {b['titulo']} ({int(t // 60)}:{int(t % 60):02d} a "
                   f"{int((t + d) // 60)}:{int((t + d) % 60):02d})", "", b["texto"], ""]
        t += d + PAUSA_FINAL
    (AQUI.parent / "ROTEIRO.md").write_text("\n".join(linhas), encoding="utf-8")


def main(manter_audio=False):
    roteiro = json.loads((AQUI / "narracao.json").read_text(encoding="utf-8"))
    AUDIO.mkdir(exist_ok=True); CLIPES.mkdir(exist_ok=True)
    renderizar_slides()
    legendas, t0, lista = [], 0.0, []
    for i, bloco in enumerate(roteiro, 1):
        wav = AUDIO / f"{bloco['id']}.wav"
        if not (manter_audio and wav.exists()):
            falar(bloco["texto"], wav)
        dur = duracao(wav) + PAUSA_FINAL
        clipe = CLIPES / f"{bloco['id']}.mp4"
        executar("ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i",
                 str(PNG / f"slide_{i:02d}.png"), "-i", str(wav),
                 "-af", f"apad=pad_dur={PAUSA_FINAL}", "-t", f"{dur:.3f}",
                 "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
                 str(clipe))
        lista.append(f"file '{clipe.as_posix()}'")
        partes = trechos(bloco["texto"])
        total = sum(len(p) for p in partes)
        t = t0
        for p in partes:
            fim = t + (dur - PAUSA_FINAL) * len(p) / total
            legendas.append((t, fim, p)); t = fim
        t0 += dur
    (CLIPES / "lista.txt").write_text("\n".join(lista), encoding="utf-8")
    LEGENDA.write_text("\n".join(
        f"{n}\n{tempo_srt(a)} --> {tempo_srt(b)}\n{txt}\n"
        for n, (a, b, txt) in enumerate(legendas, 1)), encoding="utf-8")
    bruto = CLIPES / "sem_legenda.mp4"
    executar("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i",
             str(CLIPES / "lista.txt"), "-c", "copy", str(bruto))
    executar("ffmpeg", "-y", "-i", str(bruto), "-i", str(LEGENDA), "-map", "0",
             "-map", "1", "-c", "copy", "-c:s", "mov_text",
             "-metadata:s:s:0", "language=por", "-movflags", "+faststart",
             "-metadata", "title=Redes Neurais no Sompo Predict", str(FINAL))
    escrever_roteiro(roteiro)
    print(f"{FINAL.name}: {duracao(FINAL):.0f} s")


if __name__ == "__main__":
    main("--manter-audio" in sys.argv)
