from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from video_review import review_video


class VideoReviewTests(unittest.TestCase):
    def test_review_creates_contact_sheet_and_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video = root / "sample.mp4"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 180))
            for index in range(30):
                frame = np.full((180, 320, 3), 30 + index * 3, dtype=np.uint8)
                cv2.circle(frame, (40 + index * 6, 90), 24, (230, 230, 230), -1)
                writer.write(frame)
            writer.release()

            report = review_video(video, root / "review", sample_count=6)

            self.assertTrue(Path(report["contact_sheet"]).is_file())
            self.assertTrue(Path(report["report"]).is_file())
            self.assertEqual(len(report["frames"]), 6)
            self.assertGreater(report["metrics"]["analysis_samples"], 0)
            stored = json.loads(Path(report["report"]).read_text(encoding="utf-8"))
            self.assertEqual(stored["source"], str(video))


if __name__ == "__main__":
    unittest.main()
