from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess


def _run(command: list[str], timeout: int = 900) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed


def _last_json(text: str) -> dict:
    matches = re.findall(r"\{[\s\S]*?\}", text)
    for candidate in reversed(matches):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise RuntimeError("O FFmpeg não retornou as medições de volume esperadas.")


def probe(path: Path) -> dict:
    result = _run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,duration",
        "-of", "json", str(path),
    ], timeout=120)
    return json.loads(result.stdout)


def loudness(path: Path, profile: dict) -> dict:
    target = profile["loudness"]
    audio = profile["audio"]
    chain = (
        f"highpass=f={audio['highpass_hz']},"
        f"loudnorm=I={target['integrated_lufs']}:TP={target['true_peak_dbtp']}:"
        f"LRA={target['loudness_range_lu']}:print_format=json"
    )
    result = _run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(path), "-vn", "-af", chain, "-f", "null", "NUL"])
    return _last_json(result.stderr)


def master_audio(source: Path, output: Path, profile: dict) -> dict:
    if not source.is_file():
        raise FileNotFoundError(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    measured = loudness(source, profile)
    target = profile["loudness"]
    audio = profile["audio"]
    chain = (
        f"highpass=f={audio['highpass_hz']},"
        f"loudnorm=I={target['integrated_lufs']}:TP={target['true_peak_dbtp']}:"
        f"LRA={target['loudness_range_lu']}:"
        f"measured_I={measured['input_i']}:measured_LRA={measured['input_lra']}:"
        f"measured_TP={measured['input_tp']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true:print_format=json"
    )
    result = _run([
        "ffmpeg", "-nostdin", "-hide_banner", "-y", "-i", str(source), "-vn", "-af", chain,
        "-ar", str(audio["sample_rate_hz"]), "-ac", "2", "-c:a", "pcm_s24le", str(output),
    ])
    return {"before": measured, "after": _last_json(result.stderr), "output": str(output)}


def quality_report(source: Path, quality_profile: dict, audio_profile: dict) -> dict:
    metadata = probe(source)
    streams = metadata.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    checks: list[dict] = []

    expected = quality_profile["video"]
    if video:
        checks.extend([
            {"name": "width", "actual": video.get("width"), "expected": expected["width"], "passed": video.get("width") == expected["width"]},
            {"name": "height", "actual": video.get("height"), "expected": expected["height"], "passed": video.get("height") == expected["height"]},
            {"name": "fps", "actual": video.get("r_frame_rate"), "expected": expected["fps"], "passed": video.get("r_frame_rate") in {str(expected["fps"]), f"{expected['fps']}/1"}},
        ])
    else:
        checks.append({"name": "video_stream", "actual": None, "expected": "present", "passed": False})

    measured = None
    if audio:
        measured = loudness(source, audio_profile)
        integrated = float(measured["input_i"])
        peak = float(measured["input_tp"])
        target = audio_profile["loudness"]
        checks.extend([
            {"name": "integrated_lufs", "actual": integrated, "expected": target["integrated_lufs"], "passed": abs(integrated - target["integrated_lufs"]) <= quality_profile["audio"]["lufs_tolerance"]},
            {"name": "true_peak_dbtp", "actual": peak, "expected_max": quality_profile["audio"]["true_peak_max_dbtp"], "passed": peak <= quality_profile["audio"]["true_peak_max_dbtp"]},
        ])
    else:
        checks.append({"name": "audio_stream", "actual": None, "expected": "present", "passed": False})

    video_duration = float(video.get("duration") or metadata.get("format", {}).get("duration") or 0) if video else 0
    audio_duration = float(audio.get("duration") or metadata.get("format", {}).get("duration") or 0) if audio else 0
    if video and audio:
        difference = abs(video_duration - audio_duration)
        limit = quality_profile["sync"]["max_duration_difference_seconds"]
        checks.append({"name": "av_duration_difference", "actual": round(difference, 3), "expected_max": limit, "passed": difference <= limit})

    return {
        "source": str(source),
        "probe": metadata,
        "loudness": measured,
        "checks": checks,
        "automatic_passed": all(item["passed"] for item in checks),
        "human_review": quality_profile["human_review"],
    }
