import time, numpy as np
from picamera2 import Picamera2
from metadata import FrameMetadata

class CameraController:
    def __init__(self, cfg, ring):
        self.cfg = cfg
        self.ring = ring
        self.cam = Picamera2()
        self.frame_id = 0
        self.night = False

    def start_video(self):
        cfg = self.cam.create_video_configuration(
            main={"size": (self.cfg["width"], self.cfg["height"]), "format": "RGB888"},
            controls={"FrameRate": self.cfg["framerate"]}
        )
        self.cam.configure(cfg)
        self.cam.start()

    def stop(self):
        self.cam.stop()

    def capture_loop(self):
        while True:
            img = self.cam.capture_array()
            ts = time.time()
            score = float(np.mean(img))
            meta = FrameMetadata(self.frame_id, ts, score, self.night)
            self.ring.append((img, meta))
            self.frame_id += 1
