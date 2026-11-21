from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from media_analysis import write_clip_ass
from smart_reframe import write_focus_commands
from ollama_video import _normalize_media_queries, isolated_subprocess_environment, load_editorial_profile
from craft_tools import _environment as craft_environment


class ShortRenderingTests(unittest.TestCase):
    def test_editorial_profile_is_loaded_and_validated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profile.json"
            path.write_text(json.dumps({"schema": "dex-editorial-profile.v1", "id": "test"}), encoding="utf-8")
            self.assertEqual(load_editorial_profile(path)["id"], "test")
            path.write_text(json.dumps({"schema": "wrong", "id": "test"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_editorial_profile(path)

    def test_media_queries_reject_urls_and_require_every_scene(self):
        result = _normalize_media_queries({"items": [
            {"order": 1, "queries": ["  mapa   do Brasil  ", "https://example.com", "mapa do Brasil"]},
            {"order": 2, "queries": ["global technology news"]},
        ]}, {1, 2})
        self.assertEqual(result["1"], ["mapa do Brasil"])
        self.assertEqual(result["2"], ["global technology news"])
        with self.assertRaises(RuntimeError):
            _normalize_media_queries({"items": [{"order": 1, "queries": ["mapa"]}]}, {1, 2})

    def test_external_helper_environment_drops_credentials(self):
        environment = isolated_subprocess_environment(
            Path("safe-home"),
            {"PATH": "tools", "SYSTEMROOT": "windows", "GITHUB_TOKEN": "secret", "OPENAI_API_KEY": "secret"},
        )
        self.assertEqual(environment["PATH"], "tools")
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertNotIn("OPENAI_API_KEY", environment)

    def test_craft_environment_drops_credentials(self):
        previous = os.environ.get("GITHUB_TOKEN")
        os.environ["GITHUB_TOKEN"] = "secret"
        try:
            environment = craft_environment(Path("safe-home"))
        finally:
            if previous is None:
                os.environ.pop("GITHUB_TOKEN", None)
            else:
                os.environ["GITHUB_TOKEN"] = previous
        self.assertNotIn("GITHUB_TOKEN", environment)

    def test_ass_uses_short_chunks_and_safe_area(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "captions.ass"
            count = write_clip_ass(
                [{"start": 10.0, "end": 14.0, "text": "uma duas três quatro cinco seis sete oito"}],
                10.0,
                14.0,
                output,
                title="Título de teste",
            )
            text = output.read_text(encoding="utf-8-sig")
            self.assertEqual(count, 3)
            self.assertIn("Montserrat Medium,84", text)
            self.assertIn(",510,1", text)
            self.assertNotIn("BorderStyle=3", text)
            self.assertIn(r"\fad(180,320)", text)
            self.assertIn("Título", text)
            self.assertIn(r"de\Nteste", text)

    def test_focus_commands_follow_horizontal_motion(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "moving.mp4"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (640, 360))
            for frame_number in range(30):
                frame = np.zeros((360, 640, 3), dtype=np.uint8)
                x = 50 + frame_number * 15
                cv2.rectangle(frame, (x, 100), (x + 90, 280), (255, 255, 255), -1)
                writer.write(frame)
            writer.release()
            commands = Path(folder) / "focus.txt"
            report = write_focus_commands(video, 0.0, 2.9, commands, sample_seconds=0.3)
            positions = [int(line.rsplit(" ", 1)[-1].rstrip(";")) for line in commands.read_text().splitlines()]
            self.assertGreater(report["motion_samples"], 0)
            self.assertGreater(report["samples"], report["detection_samples"])
            self.assertGreater(max(positions) - min(positions), 40)
            self.assertLessEqual(max(abs(b - a) for a, b in zip(positions, positions[1:])), 15)

    def test_scene_change_never_teleports_camera(self):
        from smart_reframe import smooth_camera_path
        positions = [x for _, x in smooth_camera_path([
            {"time": 0.0, "x": 0, "scene_change": False},
            {"time": 1.0, "x": 800, "scene_change": True},
            {"time": 2.0, "x": 800, "scene_change": False},
        ], 876, 404)]
        self.assertLessEqual(max(abs(b - a) for a, b in zip(positions, positions[1:])), 45)


if __name__ == "__main__":
    unittest.main()

