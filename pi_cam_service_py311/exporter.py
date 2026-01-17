
import os
import cv2
import numpy as np
from datetime import datetime
from typing import List, Tuple
from metadata import FrameMetadata

class Exporter:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.base_dir = os.path.abspath(cfg["base_dir"])
        os.makedirs(self.base_dir, exist_ok=True)

    def save(self, frames: List[Tuple[np.ndarray, FrameMetadata]], formats: list[str] | None = None) -> list[str]:
        saved: list[str] = []
        use_formats = formats if formats is not None else self.cfg["formats"]
        for img, meta in frames:
            ts = datetime.fromtimestamp(meta.timestamp).strftime("%Y%m%d_%H%M%S")
            base = f"{ts}_f{meta.frame_id}"
            if "jpg" in use_formats:
                fn = os.path.join(self.base_dir, base + ".jpg")
                cv2.imwrite(fn, img)
                saved.append(fn)
            if "png" in use_formats:
                fn = os.path.join(self.base_dir, base + ".png")
                cv2.imwrite(fn, img)
                saved.append(fn)
            if "npy" in use_formats:
                fn = os.path.join(self.base_dir, base + ".npy")
                np.save(fn, img)
                saved.append(fn)
        return saved

    def stack_and_save(self, frames: List[Tuple[np.ndarray, FrameMetadata]], formats: list[str] | None = None) -> list[str]:
        if not frames:
            return []
        imgs = [f[0].astype("float32") for f in frames]
        stacked = sum(imgs) / len(imgs)
        stacked = stacked.clip(0, 255).astype("uint8")
        return self.save([(stacked, frames[-1][1])], formats)
