import time, numpy as np
from picamera2 import Picamera2
from metadata import FrameMetadata
from typing import Tuple

class CameraController:
    def __init__(self, cfg: dict, ring) -> None:
        self.cfg = cfg
        self.ring = ring
        self.cam = Picamera2()
        self.frame_id = 0
        self.night = False

    def start_video(self) -> None:
        cfg = self.cam.create_video_configuration(
            main={"size": (self.cfg["width"], self.cfg["height"]), "format": "RGB888"},
            controls={"FrameRate": self.cfg["framerate"]}
        )
        self.cam.configure(cfg)
        self.cam.start()

    def stop(self) -> None:
        self.cam.stop()

    def capture_loop(self) -> None:
        while True:
            img: np.ndarray = self.cam.capture_array()
            ts = time.time()
            score: float = float(np.mean(img))
            meta = FrameMetadata(frame_id=self.frame_id, timestamp=ts, dark_score=score, night_mode=self.night)
            self.ring.append((img, meta))
            self.frame_id += 1
