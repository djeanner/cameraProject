import os, cv2, numpy as np
from datetime import datetime

class Exporter:
    def __init__(self, cfg):
        self.cfg = cfg
        os.makedirs(cfg["base_dir"], exist_ok=True)

    def save(self, frames):
        for img, meta in frames:
            ts = datetime.fromtimestamp(meta.timestamp).strftime("%Y%m%d_%H%M%S")
            base = f"{ts}_f{meta.frame_id}"
            if "jpg" in self.cfg["formats"]:
                cv2.imwrite(os.path.join(self.cfg["base_dir"], base + ".jpg"), img)
            if "png" in self.cfg["formats"]:
                cv2.imwrite(os.path.join(self.cfg["base_dir"], base + ".png"), img)
            if "npy" in self.cfg["formats"]:
                np.save(os.path.join(self.cfg["base_dir"], base + ".npy"), img)

    def stack_and_save(self, frames):
        imgs = [f[0].astype("float32") for f in frames]
        stacked = sum(imgs) / len(imgs)
        stacked = stacked.clip(0,255).astype("uint8")
        self.save([(stacked, frames[-1][1])])
