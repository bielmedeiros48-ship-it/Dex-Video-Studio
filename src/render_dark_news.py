from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


TITLES = [
    "AS 5 NOTÍCIAS QUE CONECTARAM A SEMANA",
    "1  •  O SEU BOLSO",
    "2  •  O ALERTA COMEÇA ANTES DO NASCIMENTO",
    "3  •  UMA FOTO HISTÓRICA, POUCO RESULTADO",
    "4  •  A CRISE DENTRO DOS HOSPITAIS",
    "5  •  O CUSTO DA GUERRA NO GOLFO",
    "O FIO QUE LIGA TUDO",
]
FACTS = [
    "DINHEIRO  •  SAÚDE  •  PODER  •  GUERRA",
    "DÓLAR R$ 5,93   |   IBOVESPA -0,69%",
    "350 MIL+ SUBSTÂNCIAS E MISTURAS REGISTRADAS",
    "SEM NOVO PLANO CONCRETO DE CONTROLE NUCLEAR",
    "4,7 MILHÕES DE MORTES ASSOCIADAS POR ANO",
    "FLUXO DE PETRÓLEO CERCA DE 20% ABAIXO DE OUTUBRO",
    "DECISÕES DISTANTES, CONSEQUÊNCIAS PRÓXIMAS",
]
SOURCES = [
    "Fontes verificadas em 20/11/2026",
    "Agência Brasil  •  B3",
    "OMS  •  PNUMA",
    "Associated Press  •  Reuters",
    "Organização Mundial da Saúde",
    "Associated Press  •  Al Jazeera",
    "URLs e créditos registrados no projeto",
]
COLORS = ["0x0b132b", "0x101820", "0x10251f", "0x17142b", "0x17221b", "0x241416", "0x101b2d"]
ACCENTS = ["0x38bdf8", "0xfbbf24", "0x34d399", "0xa78bfa", "0xf87171", "0xfb7185", "0x60a5fa"]
BED_FREQUENCIES = [110, 92, 145, 82, 118, 70, 132]
SOURCE_URLS = [
    "https://agenciabrasil.ebc.com.br/economia/noticia/2026-11/dolar-supera-r-593-e-fecha-no-maior-valor-desde-abril-de-2025",
    "https://borainvestir.b3.com.br/noticias/mercado/ibovespa-b3-cai-069-com-cautela-fiscal-dolar-sobe-a-r-593/",
    "https://www.who.int/publications/m/item/9789240126879",
    "https://apnews.com/article/57638eeb4ed3385f1f943910686f1b2b",
    "https://www.who.int/news-room/events/detail/2026/11/18/default-calendar/world-amr-awareness-week-2026",
    "https://apnews.com/article/16c39c487a23b53b73c5eabb7f0fd57a",
]


def run(command: list[str], cwd: Path | None = None) -> None:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Falha no FFmpeg.")


def duration(path: Path) -> float:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        text=True, capture_output=True, check=True,
    )
    return float(completed.stdout.strip())


def ass_time(seconds: float) -> str:
    centis = max(0, round(seconds * 100))
    hours, centis = divmod(centis, 360000)
    minutes, centis = divmod(centis, 6000)
    secs, centis = divmod(centis, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def caption_chunks(text: str, size: int = 6) -> list[str]:
    words = text.split()
    return [" ".join(words[index:index + size]) for index in range(0, len(words), size)]


def escape_ass(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def write_captions(lines: list[str], durations: list[float], output: Path, overlap: float) -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Segoe UI Semibold,54,&H00FFFFFF,&H000000FF,&H0010182A,&H60000000,-1,0,0,0,100,100,0,0,1,3,1,2,180,180,92,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events: list[str] = []
    scene_start = 0.0
    for scene_index, (text, scene_duration) in enumerate(zip(lines, durations)):
        chunks = caption_chunks(text)
        total_words = max(1, sum(len(chunk.split()) for chunk in chunks))
        cursor = scene_start + 0.35
        usable = max(0.5, scene_duration - 0.7)
        for chunk in chunks:
            share = usable * len(chunk.split()) / total_words
            end = min(scene_start + scene_duration - 0.2, cursor + share)
            events.append(
                f"Dialogue: 0,{ass_time(cursor)},{ass_time(end)},Default,,0,0,0,,{escape_ass(chunk)}"
            )
            cursor = end
        scene_start += scene_duration - (overlap if scene_index < len(durations) - 1 else 0)
    output.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")


def render_scene(index: int, audio: Path, output: Path, work: Path) -> float:
    scene_duration = duration(audio)
    title_file = work / f"title-{index + 1:02d}.txt"
    fact_file = work / f"fact-{index + 1:02d}.txt"
    source_file = work / f"source-{index + 1:02d}.txt"
    title_file.write_text(TITLES[index], encoding="utf-8")
    fact_file.write_text(FACTS[index], encoding="utf-8")
    source_file.write_text(SOURCES[index], encoding="utf-8")
    fade_out = max(0, scene_duration - 0.45)
    font = "C\\:/Windows/Fonts/segoeuib.ttf"
    regular = "C\\:/Windows/Fonts/segoeui.ttf"
    accent = ACCENTS[index]
    vf = (
        "format=yuv420p,"
        "drawgrid=width=120:height=120:thickness=1:color=white@0.035,"
        f"drawbox=x='-460+mod(t*90,2380)':y=0:w=460:h=1080:color={accent}@0.055:t=fill,"
        f"drawbox=x=110:y=170:w=14:h=420:color={accent}@0.95:t=fill,"
        "drawbox=x=145:y=165:w=1610:h=430:color=black@0.30:t=fill,"
        f"drawtext=fontfile='{font}':textfile='title-{index + 1:02d}.txt':reload=0:"
        "expansion=none:fontcolor=white:fontsize=60:x=180:y=230:shadowcolor=black@0.8:shadowx=4:shadowy=4,"
        f"drawtext=fontfile='{font}':textfile='fact-{index + 1:02d}.txt':reload=0:"
        f"expansion=none:fontcolor={accent}:fontsize=42:x=180:y=405:shadowcolor=black@0.7:shadowx=3:shadowy=3,"
        f"drawtext=fontfile='{regular}':textfile='source-{index + 1:02d}.txt':reload=0:"
        "expansion=none:fontcolor=white@0.68:fontsize=25:x=180:y=530,"
        f"drawtext=fontfile='{font}':text='DEX NEWS  •  20 NOV 2026':"
        f"fontcolor={accent}:fontsize=26:x=110:y=75,"
        "vignette=PI/5,"
        f"fade=t=in:st=0:d=0.45,fade=t=out:st={fade_out:.3f}:d=0.45[v]"
    )
    af = (
        "[1:a]highpass=f=65,lowpass=f=15000,"
        "acompressor=threshold=-20dB:ratio=2:attack=15:release=180:makeup=1.5dB[voice];"
        f"[2:a]volume=0.012,lowpass=f=900,afade=t=in:st=0:d=1.2,"
        f"afade=t=out:st={max(0, scene_duration - 1.2):.3f}:d=1.2[bed];"
        "[voice][bed]amix=inputs=2:duration=first:weights='1 0.8',alimiter=limit=0.92[a]"
    )
    run([
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c={COLORS[index]}:s=1920x1080:r=30:d={scene_duration:.3f}",
        "-i", str(audio),
        "-f", "lavfi", "-i", f"sine=frequency={BED_FREQUENCIES[index]}:sample_rate=48000:duration={scene_duration:.3f}",
        "-filter_complex", vf + ";" + af,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-t", f"{scene_duration:.3f}", "-movflags", "+faststart", str(output),
    ], cwd=work)
    return duration(output)


def write_fcpxml(scene_files: list[Path], durations: list[float], output: Path) -> None:
    root = ET.Element("fcpxml", {"version": "1.11"})
    resources = ET.SubElement(root, "resources")
    ET.SubElement(resources, "format", {
        "id": "r1", "name": "FFVideoFormat1080p30", "width": "1920", "height": "1080",
        "frameDuration": "1/30s", "colorSpace": "1-1-1 (Rec. 709)",
    })
    for index, (scene, scene_duration) in enumerate(zip(scene_files, durations), 2):
        ticks = round(scene_duration * 30)
        asset = ET.SubElement(resources, "asset", {
            "id": f"r{index}", "name": scene.stem, "start": "0s", "duration": f"{ticks}/30s",
            "hasVideo": "1", "hasAudio": "1", "format": "r1", "audioSources": "1",
            "audioChannels": "2", "audioRate": "48000",
        })
        ET.SubElement(asset, "media-rep", {"kind": "original-media", "src": scene.as_uri()})
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", {"name": "Dex Video Studio"})
    project = ET.SubElement(event, "project", {"name": "Canal Dark - 5 notícias - 20-11-2026"})
    spine = ET.SubElement(ET.SubElement(project, "sequence", {
        "tcStart": "0s", "format": "r1", "tcFormat": "NDF",
        "audioLayout": "stereo", "audioRate": "48k",
    }), "spine")
    offset = 0
    for index, (title, scene_duration) in enumerate(zip(TITLES, durations), 2):
        ticks = round(scene_duration * 30)
        ET.SubElement(spine, "asset-clip", {
            "ref": f"r{index}", "name": title, "offset": f"{offset}/30s",
            "start": "0s", "duration": f"{ticks}/30s", "tcFormat": "NDF",
        })
        offset += ticks
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)


def combine(scene_files: list[Path], durations: list[float], captions: Path, output: Path, overlap: float) -> None:
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    for scene in scene_files:
        command.extend(["-i", str(scene)])
    filters: list[str] = []
    video_label = "0:v"
    audio_label = "0:a"
    elapsed = durations[0]
    for index in range(1, len(scene_files)):
        next_video = f"v{index}"
        next_audio = f"a{index}"
        offset = elapsed - overlap
        filters.append(
            f"[{video_label}][{index}:v]xfade=transition=fade:duration={overlap}:offset={offset:.3f}[{next_video}]"
        )
        filters.append(
            f"[{audio_label}][{index}:a]acrossfade=d={overlap}:c1=tri:c2=tri[{next_audio}]"
        )
        video_label = next_video
        audio_label = next_audio
        elapsed += durations[index] - overlap
    filters.append(f"[{video_label}]ass=filename='{captions.name}'[vcap]")
    filters.append(f"[{audio_label}]loudnorm=I=-14:LRA=7:TP=-2,alimiter=limit=0.78:level=false[aout]")
    command.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[vcap]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(output),
    ])
    run(command, cwd=output.parent)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        assert ass_time(65.43) == "0:01:05.43"
        assert caption_chunks("um dois três quatro cinco seis sete", 6) == [
            "um dois três quatro cinco seis", "sete"
        ]
        print("self-test ok")
        return 0

    project = args.project.resolve()
    voice_dir = project / "03-voz" / "dark-hoje-batch"
    review_dir = project / "06-revisao"
    final_dir = project / "07-final"
    work_dir = project / "04-midia" / "dark-hoje"
    timeline_dir = project / "05-timeline"
    for folder in (review_dir, final_dir, work_dir, timeline_dir):
        folder.mkdir(parents=True, exist_ok=True)

    audio_files = sorted(voice_dir.glob("line_*.wav"))
    if len(audio_files) != 7:
        raise RuntimeError(f"Esperados 7 áudios; encontrados {len(audio_files)} em {voice_dir}.")
    script_lines = [
        line.strip() for line in (project / "03-voz" / "roteiro-dark-hoje-batch.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(script_lines) != 7:
        raise RuntimeError("O roteiro curto precisa ter exatamente sete blocos.")

    scene_files: list[Path] = []
    durations: list[float] = []
    for index, audio in enumerate(audio_files):
        scene = work_dir / f"cena-{index + 1:02d}.mp4"
        durations.append(render_scene(index, audio, scene, work_dir))
        scene_files.append(scene)

    overlap = 0.45
    captions = review_dir / "canal-dark-hoje.ass"
    write_captions(script_lines, durations, captions, overlap)
    preview = review_dir / "canal-dark-5-noticias-2026-11-20.mp4"
    combine(scene_files, durations, captions, preview, overlap)
    fcpxml = timeline_dir / "canal-dark-5-noticias-2026-11-20.fcpxml"
    write_fcpxml(scene_files, durations, fcpxml)
    credits = final_dir / "FONTES-E-CREDITOS-2026-11-20.json"
    credits.write_text(json.dumps({
        "created_at": "2026-11-20",
        "visuals": "Gráficos e animações originais gerados localmente pelo Dex Video Studio.",
        "voice": "Clone local autorizado da voz do proprietário.",
        "sources": SOURCE_URLS,
        "publication_status": "needs_human_review",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    report = review_dir / "canal-dark-5-noticias-2026-11-20.render.json"
    report.write_text(json.dumps({
        "video": str(preview), "timeline": str(fcpxml), "captions": str(captions),
        "credits": str(credits), "duration": duration(preview),
        "status": "needs_human_review",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"video": str(preview), "timeline": str(fcpxml), "report": str(report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


