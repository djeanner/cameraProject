import time
import numpy as np
import cv2
from picamera2 import Picamera2
from metadata import FrameMetadata

class CameraController:
    def __init__(self, cfg: dict, cfgRing: dict, ring) -> None:
        self.cfg = cfg
        self.cfgRing = cfgRing
        self.ring = ring
        self.cam = Picamera2()
        self.frame_id = 0
        self.mode = None
        self.night_cfg = None
        self.downscale_cfg = self.cfgRing.get("downscale", {
            "enable": True,
            "width": 256,
            "height": 192
        })
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

        # Optional downscale for ring buffer
        if self.downscale_cfg.get("enable", True):
            w = self.downscale_cfg["width"]
            h = self.downscale_cfg["height"]
            ring_img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        else:
            ring_img = img

        ts = time.time()
        score = float(ring_img.mean())

        meta = FrameMetadata(
            frame_id=self.frame_id,
            timestamp=ts,
            dark_score=score,
            night_mode=(self.mode == "still")
        )

        self.ring.append((ring_img, meta))
        self.frame_id += 1


    def capture_fullres(self) -> np.ndarray:
        """Capture a full-resolution frame for export"""
        return self.cam.capture_array()

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
