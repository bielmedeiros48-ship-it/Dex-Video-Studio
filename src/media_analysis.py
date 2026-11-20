from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def transcribe(source: Path, model: Path, language: str = "pt", use_gpu: bool = False) -> list[dict]:
    if not source.is_file():
        raise FileNotFoundError(source)
    if not model.is_file():
        raise FileNotFoundError(model)
    filter_graph = (
        "highpass=f=75,lowpass=f=8000,afftdn=nf=-35,"
        f"whisper=model={model.name}:language={language}:"
        f"use_gpu={'true' if use_gpu else 'false'}:destination=-:format=json"
    )
    completed = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(source), "-vn", "-af", filter_graph, "-f", "null", "NUL"],
        cwd=model.parent,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=3600,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "Falha na transcrição local.")
    segments = []
    for line in completed.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if {"start", "end", "text"} <= item.keys():
            segments.append({"start": item["start"] / 1000, "end": item["end"] / 1000, "text": item["text"].strip()})
    if not segments:
        raise RuntimeError("A transcrição terminou sem segmentos reconhecidos.")
    return segments


def seconds_to_timecode(value: float, fps: int) -> str:
    frames = max(0, round(value * fps))
    hours, frames = divmod(frames, fps * 3600)
    minutes, frames = divmod(frames, fps * 60)
    seconds, frames = divmod(frames, fps)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def _srt_time(value: float) -> str:
    milliseconds = max(0, round(value * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def write_clip_srt(segments: list[dict], clip_start: float, clip_end: float, output: Path) -> int:
    records = []
    cursor = 0.0
    for segment in segments:
        start = max(float(segment["start"]), clip_start, clip_start + cursor)
        end = min(float(segment["end"]), clip_end)
        text = str(segment.get("text") or "").strip()
        if end - start < 0.3 or not text:
            continue
        wrapped = text
        records.append(f"{len(records) + 1}\n{_srt_time(start - clip_start)} --> {_srt_time(end - clip_start)}\n{wrapped}\n")
        cursor = end - clip_start
    output.write_text("\n".join(records), encoding="utf-8-sig")
    return len(records)


def _ass_time(value: float) -> str:
    centiseconds = max(0, round(value * 100))
    hours, centiseconds = divmod(centiseconds, 360_000)
    minutes, centiseconds = divmod(centiseconds, 6_000)
    seconds, centiseconds = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def write_clip_ass(segments: list[dict], clip_start: float, clip_end: float, output: Path, words_per_caption: int = 6, title: str | None = None) -> int:
    if words_per_caption < 1:
        raise ValueError("words_per_caption precisa ser positivo.")
    events = []
    for segment in segments:
        start = max(float(segment["start"]), clip_start)
        end = min(float(segment["end"]), clip_end)
        words = str(segment.get("text") or "").strip().split()
        if end - start < 0.3 or not words:
            continue
        chunks = [words[i:i + words_per_caption] for i in range(0, len(words), words_per_caption)]
        duration = (end - start) / len(chunks)
        for index, chunk in enumerate(chunks):
            event_start = start + index * duration - clip_start
            event_end = start + (index + 1) * duration - clip_start
            text = " ".join(chunk).replace("\\", r"\N").replace("{", r"\{").replace("}", r"\}")
            if len(chunk) > 3:
                split = math.ceil(len(chunk) / 2)
                text = " ".join(chunk[:split]) + r"\N" + " ".join(chunk[split:])
            events.append(f"Dialogue: 0,{_ass_time(event_start)},{_ass_time(event_end)},Shorts,,0,0,0,,{text}")
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Shorts,Montserrat Medium,84,&H00FFFFFF,&H0000D7FF,&H00101010,&H70000000,-1,0,0,0,100,100,0,0,1,6,2,2,90,180,510,1
Style: Title,Montserrat Medium,56,&H00FFFFFF,&H0000D7FF,&H00101010,&H70000000,-1,0,0,0,100,100,0,0,1,6,2,7,70,140,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    if title:
        words = title.strip().split()
        split = math.ceil(len(words) / 2)
        title_text = " ".join(words[:split])
        if len(words) > split:
            title_text += r"\N" + " ".join(words[split:])
        events.insert(0, f"Dialogue: 1,0:00:00.20,0:00:03.20,Title,,0,0,0,,{{\\fad(180,320)}}{title_text}")
    output.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    return len(events)


def write_cmx3600(source: Path, clips: list[dict], output: Path, fps: int) -> None:
    reel = "SOURCE"
    record_at = 0.0
    lines = ["TITLE: OLLAMA VIDEO HIGHLIGHTS", "FCM: NON-DROP FRAME", ""]
    for index, clip in enumerate(clips, 1):
        start = float(clip["start"])
        end = float(clip["end"])
        duration = end - start
        lines.append(
            f"{index:03d}  {reel:<8} V     C        {seconds_to_timecode(start, fps)} "
            f"{seconds_to_timecode(end, fps)} {seconds_to_timecode(record_at, fps)} "
            f"{seconds_to_timecode(record_at + duration, fps)}"
        )
        lines.append(f"* FROM CLIP NAME: {source.name}")
        lines.append(f"* COMMENT: {clip.get('title', 'Trecho selecionado')} | {clip.get('reason', '')}")
        lines.append("")
        record_at += duration
    output.write_text("\n".join(lines), encoding="utf-8-sig")


def write_fcpxml(source: Path, clips: list[dict], output: Path, metadata: dict) -> None:
    streams = metadata.get("streams", [])
    video = next(stream for stream in streams if stream.get("codec_type") == "video")
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    numerator, denominator = (int(part) for part in video.get("r_frame_rate", "30/1").split("/"))
    frame_duration = f"{denominator}/{numerator}s"
    ticks = numerator
    source_duration = round(float(metadata["format"]["duration"]) * ticks)
    root = ET.Element("fcpxml", {"version": "1.11"})
    resources = ET.SubElement(root, "resources")
    ET.SubElement(resources, "format", {
        "id": "r1", "name": "FFVideoFormatRateUndefined", "width": str(video["width"]),
        "height": str(video["height"]), "frameDuration": frame_duration, "colorSpace": "1-1-1 (Rec. 709)",
    })
    asset = ET.SubElement(resources, "asset", {
        "id": "r2", "name": source.stem, "start": "0s", "duration": f"{source_duration}/{ticks}s",
        "hasVideo": "1", "hasAudio": "1" if audio else "0", "format": "r1",
        "audioSources": "1" if audio else "0", "audioChannels": str(audio.get("channels", 0)),
    })
    ET.SubElement(asset, "media-rep", {"kind": "original-media", "src": source.as_uri()})
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", {"name": "Ollama Video Highlights"})
    project = ET.SubElement(event, "project", {"name": f"{source.stem} - melhores momentos"})
    sequence_attributes = {"tcStart": "0s", "format": "r1", "tcFormat": "NDF"}
    if audio:
        sequence_attributes.update({"audioLayout": "stereo", "audioRate": f"{float(audio.get('sample_rate', 48000)) / 1000:g}k"})
    spine = ET.SubElement(ET.SubElement(project, "sequence", sequence_attributes), "spine")
    record_tick = 0
    for clip in clips:
        start_tick = round(float(clip["start"]) * ticks)
        duration_tick = round((float(clip["end"]) - float(clip["start"])) * ticks)
        ET.SubElement(spine, "asset-clip", {
            "ref": "r2", "name": str(clip.get("title") or source.stem), "tcFormat": "NDF",
            "offset": f"{record_tick}/{ticks}s", "start": f"{start_tick}/{ticks}s", "duration": f"{duration_tick}/{ticks}s",
        })
        record_tick += duration_tick
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
