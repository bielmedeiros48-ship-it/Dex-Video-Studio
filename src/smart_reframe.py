from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def smooth_camera_path(samples: list[dict], max_x: int, crop_width: int, command_hz: int = 30) -> list[tuple[float, int]]:
    if not samples:
        return [(0.0, max_x // 2)]
    dt = 1 / command_hz
    max_speed = max(120.0, crop_width)
    max_acceleration = max_speed * 3
    deadzone = max(6.0, crop_width * 0.02)
    current = float(samples[0]["x"])
    velocity = 0.0
    segment = 0
    commands = []
    steps = max(1, round(float(samples[-1]["time"]) * command_hz) + 1)
    for step in range(steps):
        time = step * dt
        while segment + 1 < len(samples) and time >= float(samples[segment + 1]["time"]) - dt / 2:
            segment += 1
        left = samples[segment]
        right = samples[min(segment + 1, len(samples) - 1)]
        if right["scene_change"] or right["time"] <= left["time"]:
            desired = float(left["x"])
        else:
            progress = min(1.0, max(0.0, (time - left["time"]) / (right["time"] - left["time"])))
            eased = progress * progress * (3 - 2 * progress)
            desired = float(left["x"]) + (float(right["x"]) - float(left["x"])) * eased
        distance = desired - current
        desired_velocity = 0.0 if abs(distance) <= deadzone else max(-max_speed, min(max_speed, distance * 3.2))
        velocity += max(-max_acceleration * dt, min(max_acceleration * dt, desired_velocity - velocity))
        current = min(float(max_x), max(0.0, current + velocity * dt))
        commands.append((round(time, 3), int(round(current))))
    return commands


def write_focus_commands(source: Path, clip_start: float, clip_end: float, output: Path, sample_seconds: float = 0.35) -> dict:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Não foi possível analisar o enquadramento: {source}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    crop_width = min(width, int(height * 9 / 16) // 2 * 2)
    max_x = max(0, width - crop_width)
    yunet_path = Path(__file__).resolve().parents[1] / "models" / "face_detection_yunet_2023mar.onnx"
    yunet = cv2.FaceDetectorYN.create(str(yunet_path), "", (320, 320), 0.72, 0.3, 5000) if yunet_path.is_file() else None
    cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
    detections = []
    previous = None
    last_target = width / 2
    face_samples = 0
    motion_samples = 0
    time = clip_start
    while time < clip_end + 0.001:
        capture.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
        ok, frame = capture.read()
        if not ok:
            break
        small_width = min(640, width)
        scale = small_width / width
        small = cv2.resize(frame, (small_width, max(1, round(height * scale))))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = []
        if yunet is not None:
            yunet.setInputSize((small.shape[1], small.shape[0]))
            _, detected = yunet.detect(small)
            if detected is not None:
                faces = [tuple(row[:4]) for row in detected]
        if not faces:
            faces = cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5, minSize=(32, 32))
        if len(faces):
            weights = np.array([w * h for _, _, w, h in faces], dtype=float)
            centers = np.array([x + w / 2 for x, _, w, _ in faces], dtype=float)
            target = float(np.average(centers, weights=weights)) / scale
            face_samples += 1
        elif previous is not None:
            delta = cv2.absdiff(gray, previous)
            _, mask = cv2.threshold(delta, 24, 255, cv2.THRESH_BINARY)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            moments = cv2.moments(mask)
            if moments["m00"] > mask.size * 255 * 0.008:
                target = (moments["m10"] / moments["m00"]) / scale
                motion_samples += 1
            else:
                target = last_target
        else:
            target = last_target
        scene_change = previous is not None and float(cv2.absdiff(gray, previous).mean()) > 46
        last_target = target
        x = int(round(min(max(target - crop_width / 2, 0), max_x)))
        detections.append({"time": round(time - clip_start, 3), "x": x, "scene_change": scene_change})
        previous = gray
        time += sample_seconds
    capture.release()
    if not detections:
        detections = [{"time": 0.0, "x": max_x // 2, "scene_change": False}]
    commands = smooth_camera_path(detections, max_x, crop_width)
    output.write_text("\n".join(f"{time:.3f} crop@focus x {x};" for time, x in commands) + "\n", encoding="ascii")
    return {
        "samples": len(commands), "detection_samples": len(detections),
        "scene_changes": sum(1 for item in detections if item["scene_change"]),
        "face_samples": face_samples, "motion_samples": motion_samples,
        "crop_width": crop_width, "source_width": width, "source_height": height,
        "face_detector": "yunet" if yunet is not None else "haar", "camera_motion": "continuous-eased-pan-30fps",
    }
