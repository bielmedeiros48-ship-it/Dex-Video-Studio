from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


def _largest_face_center(frame: np.ndarray, detector) -> float | None:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = detector.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5, minSize=(32, 32))
    if not len(faces):
        return None
    x, _y, width, _height = max(faces, key=lambda item: item[2] * item[3])
    return float(x + width / 2) / frame.shape[1]


def _contact_sheet(frames: list[tuple[float, np.ndarray]], output: Path) -> None:
    columns = 3
    tile_width, tile_height = 480, 286
    rows = (len(frames) + columns - 1) // columns
    sheet = np.full((rows * tile_height, columns * tile_width, 3), 18, dtype=np.uint8)
    for index, (timestamp, frame) in enumerate(frames):
        scale = min(tile_width / frame.shape[1], (tile_height - 28) / frame.shape[0])
        resized = cv2.resize(frame, (max(1, round(frame.shape[1] * scale)), max(1, round(frame.shape[0] * scale))))
        row, column = divmod(index, columns)
        x = column * tile_width + (tile_width - resized.shape[1]) // 2
        y = row * tile_height + 26 + (tile_height - 28 - resized.shape[0]) // 2
        sheet[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
        cv2.putText(sheet, f"{timestamp:.1f}s", (column * tile_width + 10, row * tile_height + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 245, 255), 1, cv2.LINE_AA)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90]):
        raise RuntimeError(f"Não foi possível criar a folha de revisão: {output}")


def review_video(source: Path, output_dir: Path, sample_count: int = 12) -> dict:
    """Gera métricas determinísticas e quadros para revisão visual humana/agentiva."""
    if not source.is_file():
        raise FileNotFoundError(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Não foi possível abrir o vídeo: {source}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if fps > 0 else 0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if duration <= 0 or width <= 0 or height <= 0:
        capture.release()
        raise RuntimeError("O vídeo não forneceu duração ou resolução válidas.")

    review_times = np.linspace(min(0.5, duration / 4), max(0.5, duration - 0.5), min(sample_count, max(1, frame_count))).tolist()
    frames: list[tuple[float, np.ndarray]] = []
    frame_paths: list[str] = []
    for index, timestamp in enumerate(review_times, start=1):
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, frame = capture.read()
        if not ok:
            continue
        path = output_dir / f"quadro-{index:02d}-{timestamp:.1f}s.jpg"
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        frames.append((timestamp, frame))
        frame_paths.append(str(path))

    cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
    interval = max(0.35, duration / 600)
    previous_gray = None
    previous_face = None
    samples = black_samples = soft_samples = hard_changes = face_samples = off_center = framing_jumps = 0
    brightness_total = sharpness_total = 0.0
    timestamp = 0.0
    while timestamp < duration:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, frame = capture.read()
        if not ok:
            break
        small_width = min(480, width)
        scale = small_width / width
        small = cv2.resize(frame, (small_width, max(1, round(height * scale))))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness_total += brightness
        sharpness_total += sharpness
        black_samples += int(brightness < 12)
        soft_samples += int(sharpness < 35)
        face = _largest_face_center(small, cascade)
        if face is not None:
            face_samples += 1
            off_center += int(abs(face - 0.5) > 0.22)
        if previous_gray is not None:
            difference = float(cv2.absdiff(gray, previous_gray).mean())
            hard_changes += int(difference > 46)
            if face is not None and previous_face is not None and difference < 30 and abs(face - previous_face) > 0.28:
                framing_jumps += 1
        previous_gray = gray
        previous_face = face
        samples += 1
        timestamp += interval
    capture.release()

    sheet = output_dir / "folha-de-revisao.jpg"
    if frames:
        _contact_sheet(frames, sheet)
    metrics = {
        "duration_seconds": round(duration, 3),
        "resolution": {"width": width, "height": height},
        "fps": round(fps, 3),
        "analysis_interval_seconds": round(interval, 3),
        "analysis_samples": samples,
        "hard_visual_changes": hard_changes,
        "hard_changes_per_minute": round(hard_changes / max(duration / 60, 1 / 60), 2),
        "black_sample_ratio": round(black_samples / max(samples, 1), 4),
        "soft_sample_ratio": round(soft_samples / max(samples, 1), 4),
        "average_brightness": round(brightness_total / max(samples, 1), 2),
        "average_sharpness": round(sharpness_total / max(samples, 1), 2),
        "face_detection_ratio": round(face_samples / max(samples, 1), 4),
        "off_center_face_ratio": round(off_center / max(face_samples, 1), 4),
        "possible_abrupt_framing_jumps": framing_jumps,
    }
    report = {
        "source": str(source),
        "metrics": metrics,
        "contact_sheet": str(sheet) if sheet.is_file() else None,
        "frames": frame_paths,
        "interpretation_limits": [
            "Métricas automáticas não julgam se a história ou a estética são boas.",
            "A folha de revisão deve ser inspecionada por uma pessoa ou por um modelo com visão.",
            "Detecção facial pode falhar em anime, perfis, máscaras ou baixa iluminação.",
        ],
        "visual_review_questions": [
            "O assunto principal permanece enquadrado sem movimentos secos de câmera?",
            "Legendas, rostos e elementos importantes respeitam as áreas seguras?",
            "Os cortes parecem intencionais e o ritmo combina com o conteúdo?",
            "Há quadros vazios, borrados, estourados ou escuros demais?",
            "A composição visual e as transições parecem humanas e consistentes?",
        ],
    }
    report_path = output_dir / "revisao-visual.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report"] = str(report_path)
    return report
