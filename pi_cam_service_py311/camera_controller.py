import time
import cv2
import numpy as np
from picamera2 import Picamera2
from metadata import FrameMetadata

class CameraController:
    def __init__(self, cfg: dict, ring) -> None:
        self.cfg = cfg          # live reference to full config
        self.ring = ring
        self.cam = Picamera2()
        self.frame_id = 0
        self.mode = None
        self.night_cfg = None

    # Universal getter for any parameter
    def get_param(self, key_path: str):
        """
        Access any nested parameter using dot notation, e.g.,
        get_param("camera.framerate") or get_param("night.exposure_us")
        """
        keys = key_path.split(".")
        sub = self.cfg
        for k in keys:
            sub = sub[k]
        return sub

    # Start video mode
    def start_video(self):
        if self.mode == "video":
            return
        self.cam.stop()

        cfg = self.cam.create_video_configuration(
            main={
                "size": (self.get_param("camera.width"), self.get_param("camera.height")),
                "format": "RGB888"
            },
            controls={"FrameRate": self.get_param("camera.framerate")}
        )
        self.cam.configure(cfg)
        self.cam.start()
        self.mode = "video"
        self.night_cfg = None

    # Start still/night mode
    def start_still(self, night_cfg: dict):
        if self.mode == "still":
            return
        self.cam.stop()
        self.night_cfg = night_cfg

        cfg = self.cam.create_still_configuration(
            main={
                "size": (self.get_param("camera.width"), self.get_param("camera.height")),
                "format": "RGB888"
            },
            controls={
                "ExposureTime": self.night_cfg["exposure_us"],
                "AnalogueGain": self.night_cfg["gain"]
            }
        )
        self.cam.configure(cfg)
        self.cam.start()
        self.mode = "still"

    # Capture a frame for the ring buffer
    def capture_once(self):
        img = self.cam.capture_array()

        # Downscale for ring buffer if enabled
        downscale = self.get_param("ring.downscale.enable") if self.get_param("ring.downscale") else True
        if downscale:
            w = self.get_param("ring.downscale.width")
            h = self.get_param("ring.downscale.height")
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

    def capture_fullres(self):
        return self.cam.capture_array()

    # Apply live changes from cfg
    def update_settings(self):
        try:
            if self.mode == "video":
                self.cam.set_controls({"FrameRate": self.get_param("camera.framerate")})
            elif self.mode == "still" and self.night_cfg:
                self.cam.set_controls({
                    "ExposureTime": self.night_cfg["exposure_us"],
                    "AnalogueGain": self.night_cfg["gain"]
                })
        except Exception as e:
            import logging
            logging.warning("Failed to update camera settings live: %s", e)

    def describe_mode(self):
        if self.mode == "video":
            return {
                "mode": "video",
                "resolution": f'{self.get_param("camera.width")}x{self.get_param("camera.height")}',
                "framerate": self.get_param("camera.framerate"),
                "exposure_us": "auto",
                "gain": "auto"
            }
        if self.mode == "still":
            return {
                "mode": "still",
                "resolution": f'{self.get_param("camera.width")}x{self.get_param("camera.height")}',
                "framerate": None,
                "exposure_us": self.night_cfg["exposure_us"] if self.night_cfg else None,
                "gain": self.night_cfg["gain"] if self.night_cfg else None
            }
        return {"mode": "unknown"}
