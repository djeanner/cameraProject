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
        self.mode = None
        self.night_cfg = None

    def start_video(self) -> None:
        if self.mode == "video":
            return
        self.cam.stop()
        cfg = self.cam.create_video_configuration(
            main={"size": (self.cfg["width"], self.cfg["height"]), "format": "RGB888"},
            controls={"FrameRate": self.cfg["framerate"]}
        )
        self.cam.configure(cfg)
        self.cam.start()
        self.mode = "video"

    def start_still(self, night_cfg: dict) -> None:
        if self.mode == "still":
            return
        self.cam.stop()
        cfg = self.cam.create_still_configuration(
            main={"size": (self.cfg["width"], self.cfg["height"]), "format": "RGB888"},
            controls={
                "ExposureTime": night_cfg["exposure_us"],
                "AnalogueGain": night_cfg["gain"]
            }
        )
        self.cam.configure(cfg)
        self.cam.start()
        self.mode = "still"
        self.night_cfg = night_cfg

    def capture_once(self) -> None:
        img = self.cam.capture_array()
        ts = time.time()
        score = float(img.mean())
        meta = FrameMetadata(
            frame_id=self.frame_id,
            timestamp=ts,
            dark_score=score,
            night_mode=self.mode == "still"
        )
        self.ring.append((img, meta))
        self.frame_id += 1

    def describe_mode(self) -> dict:
        if self.mode == "video":
            return {
                "mode": "video",
                "resolution": f'{self.cfg["width"]}x{self.cfg["height"]}',
                "framerate": self.cfg["framerate"],
                "exposure_us": "auto",
                "gain": "auto"
            }

        if self.mode == "still":
            return {
                "mode": "still",
                "resolution": f'{self.cfg["width"]}x{self.cfg["height"]}',
                "framerate": None,
                "exposure_us": self.night_cfg["exposure_us"],
                "gain": self.night_cfg["gain"]
            }
