import os, zipfile, textwrap, json

# Use current directory for portability
base = os.path.join(os.getcwd(), "pi_cam_service_py311")
os.makedirs(base, exist_ok=True)

files = {}

# Modernized JSON config
files["config.json"] = json.dumps({
    "camera": {
        "width": 1024,
        "height": 768,
        "framerate": 10,
        "codec": "rgb",
        "video_mode": "stream"
    },
    "ring": {"size": 300},
    "night": {
        "enable": True,
        "dark_threshold": 35,
        "bright_threshold": 55,
        "min_dark_frames": 20,
        "mode": "still",
        "exposure_us": 2000000,
        "gain": 6.0
    },
    "export": {
        "base_dir": "./captures",
        "formats": ["jpg", "png"],
        "save_before_s": 5,
        "save_after_s": 3,
        "stack_dark_frames": True,
        "stack_count": 4,
        "auto_save_interval_s": 3600
    },
    "network": {"trigger_port": 9999},
    "logging": {"level": "INFO"}
}, indent=2)

# Ring buffer
files["ring_buffer.py"] = textwrap.dedent("""
from collections import deque
import threading
from typing import Tuple, List
import numpy as np
from metadata import FrameMetadata

class RingBuffer:
    def __init__(self, size: int) -> None:
        self.buffer: deque[Tuple[np.ndarray, FrameMetadata]] = deque(maxlen=size)
        self.lock = threading.Lock()

    def append(self, item: Tuple[np.ndarray, FrameMetadata]) -> None:
        with self.lock:
            self.buffer.append(item)

    def get_last(self, n: int) -> List[Tuple[np.ndarray, FrameMetadata]]:
        with self.lock:
            return list(self.buffer)[-n:]

    def get_last_seconds(self, seconds: int, fps: int) -> List[Tuple[np.ndarray, FrameMetadata]]:
        return self.get_last(int(seconds * fps))
""")

# Metadata
files["metadata.py"] = textwrap.dedent("""
from dataclasses import dataclass

@dataclass(kw_only=True)
class FrameMetadata:
    frame_id: int
    timestamp: float
    dark_score: float
    night_mode: bool
""")

# Night mode controller
files["night_mode.py"] = textwrap.dedent("""
class NightModeController:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.dark_count = 0
        self.active = False

    def update(self, score: float) -> str | None:
        if score < self.cfg["dark_threshold"]:
            self.dark_count += 1
        else:
            self.dark_count = 0

        match (self.active, self.dark_count >= self.cfg["min_dark_frames"]):
            case (False, True):
                self.active = True
                return "ENTER"
            case (True, False) if score > self.cfg["bright_threshold"]:
                self.active = False
                return "EXIT"
            case _:
                return None
""")

# Exporter
files["exporter.py"] = textwrap.dedent("""
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
""")

# Trigger server
files["trigger_server.py"] = textwrap.dedent("""
import socket
import threading
from typing import Callable

class TriggerServer(threading.Thread):
    def __init__(self, port: int, callback: Callable[[str], str]) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.callback = callback

    def run(self) -> None:
        s = socket.socket()
        s.bind(("", self.port))
        s.listen(5)
        while True:
            conn, _ = s.accept()
            cmd = conn.recv(1024).decode().strip()
            response = self.callback(cmd)
            conn.sendall((response + "\n").encode())
            conn.close()
""")

# Main application with hourly autosave
files["main.py"] = textwrap.dedent("""
import json
import logging
import time
from ring_buffer import RingBuffer
from camera_controller import CameraController
from exporter import Exporter
from trigger_server import TriggerServer

with open("config.json") as f:
    cfg: dict = json.load(f)

logging.basicConfig(level=cfg["logging"]["level"])

ring = RingBuffer(cfg["ring"]["size"])
exporter = Exporter(cfg["export"])

cam = CameraController(cfg["camera"], ring)
cam.start_video()

last_auto_save = 0.0


def on_trigger(cmd: str) -> str:
    cmd = cmd.strip()
    if cmd.startswith("save"):
        parts = cmd.split()
        formats = parts[1:] if len(parts) > 1 else None
        frames = ring.get_last_seconds(cfg["export"]["save_before_s"], cfg["camera"]["framerate"])
        if not frames:
            return "NO_FRAMES"
        if cfg["export"]["stack_dark_frames"]:
            used = frames[-cfg["export"]["stack_count"]:]
            saved = exporter.stack_and_save(used) if formats is None else exporter.save([(used[-1][0], used[-1][1])], formats)
        else:
            saved = exporter.save(frames, formats)
        return "SAVED:" + ",".join(saved) if saved else "NOT_SAVED"

    if cmd == "night_level":
        if not ring.buffer:
            return "NO_DATA"
        meta = ring.buffer[-1][1]
        thr = cfg["night"]["dark_threshold"]
        status = "NIGHT" if meta.dark_score < thr else "DAY"
        return f"LEVEL={meta.dark_score:.1f} THRESH={thr} STATUS={status}"

    return "UNKNOWN_COMMAND"

TriggerServer(cfg["network"]["trigger_port"], on_trigger).start()

while True:
    cam.capture_once()

    now = time.time()
    interval = cfg["export"].get("auto_save_interval_s", 0)
    if interval > 0 and now - last_auto_save >= interval:
        frames = ring.get_last(1)
        if frames:
            saved = exporter.save(frames)
            logging.info(f"Hourly auto-save: {saved}")
            last_auto_save = now
""")

# Write files and zip
for name, content in files.items():
    with open(os.path.join(base, name), "w") as f:
        f.write(content)

zip_path = os.path.join(base, "pi_cam_service_py311.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for name in files:
        z.write(os.path.join(base, name), arcname=name)

zip_path
import os, zipfile, textwrap, json

# Use current directory for portability
base = os.path.join(os.getcwd(), "pi_cam_service_py311")
os.makedirs(base, exist_ok=True)

files = {}

# Modernized JSON config
files["config.json"] = json.dumps({
    "camera": {
        "width": 1024,
        "height": 768,
        "framerate": 10,
        "codec": "rgb",
        "video_mode": "stream"
    },
    "ring": {"size": 300},
    "night": {
        "enable": True,
        "dark_threshold": 35,
        "bright_threshold": 55,
        "min_dark_frames": 20,
        "mode": "still",
        "exposure_us": 2000000,
        "gain": 6.0
    },
    "export": {
        "base_dir": "./captures",
        "formats": ["jpg", "png"],
        "save_before_s": 5,
        "save_after_s": 3,
        "stack_dark_frames": True,
        "stack_count": 4,
        "auto_save_interval_s": 3600
    },
    "network": {"trigger_port": 9999},
    "logging": {"level": "INFO"}
}, indent=2)

# Ring buffer
files["ring_buffer.py"] = textwrap.dedent("""
from collections import deque
import threading
from typing import Tuple, List
import numpy as np
from metadata import FrameMetadata

class RingBuffer:
    def __init__(self, size: int) -> None:
        self.buffer: deque[Tuple[np.ndarray, FrameMetadata]] = deque(maxlen=size)
        self.lock = threading.Lock()

    def append(self, item: Tuple[np.ndarray, FrameMetadata]) -> None:
        with self.lock:
            self.buffer.append(item)

    def get_last(self, n: int) -> List[Tuple[np.ndarray, FrameMetadata]]:
        with self.lock:
            return list(self.buffer)[-n:]

    def get_last_seconds(self, seconds: int, fps: int) -> List[Tuple[np.ndarray, FrameMetadata]]:
        return self.get_last(int(seconds * fps))
""")

# Metadata
files["metadata.py"] = textwrap.dedent("""
from dataclasses import dataclass

@dataclass(kw_only=True)
class FrameMetadata:
    frame_id: int
    timestamp: float
    dark_score: float
    night_mode: bool
""")

# Night mode controller
files["night_mode.py"] = textwrap.dedent("""
class NightModeController:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.dark_count = 0
        self.active = False

    def update(self, score: float) -> str | None:
        if score < self.cfg["dark_threshold"]:
            self.dark_count += 1
        else:
            self.dark_count = 0

        match (self.active, self.dark_count >= self.cfg["min_dark_frames"]):
            case (False, True):
                self.active = True
                return "ENTER"
            case (True, False) if score > self.cfg["bright_threshold"]:
                self.active = False
                return "EXIT"
            case _:
                return None
""")

# Exporter
files["exporter.py"] = textwrap.dedent("""
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
""")

# Trigger server
files["trigger_server.py"] = textwrap.dedent("""
import socket
import threading
from typing import Callable

class TriggerServer(threading.Thread):
    def __init__(self, port: int, callback: Callable[[str], str]) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.callback = callback

    def run(self) -> None:
        s = socket.socket()
        s.bind(("", self.port))
        s.listen(5)
        while True:
            conn, _ = s.accept()
            cmd = conn.recv(1024).decode().strip()
            response = self.callback(cmd)
            conn.sendall((response + "\n").encode())
            conn.close()
""")

# Main application with hourly autosave
files["main.py"] = textwrap.dedent("""
import json
import logging
import time
from ring_buffer import RingBuffer
from camera_controller import CameraController
from exporter import Exporter
from trigger_server import TriggerServer

with open("config.json") as f:
    cfg: dict = json.load(f)

logging.basicConfig(level=cfg["logging"]["level"])

ring = RingBuffer(cfg["ring"]["size"])
exporter = Exporter(cfg["export"])

cam = CameraController(cfg["camera"], ring)
cam.start_video()

last_auto_save = 0.0


def on_trigger(cmd: str) -> str:
    cmd = cmd.strip()
    if cmd.startswith("save"):
        parts = cmd.split()
        formats = parts[1:] if len(parts) > 1 else None
        frames = ring.get_last_seconds(cfg["export"]["save_before_s"], cfg["camera"]["framerate"])
        if not frames:
            return "NO_FRAMES"
        if cfg["export"]["stack_dark_frames"]:
            used = frames[-cfg["export"]["stack_count"]:]
            saved = exporter.stack_and_save(used) if formats is None else exporter.save([(used[-1][0], used[-1][1])], formats)
        else:
            saved = exporter.save(frames, formats)
        return "SAVED:" + ",".join(saved) if saved else "NOT_SAVED"

    if cmd == "night_level":
        if not ring.buffer:
            return "NO_DATA"
        meta = ring.buffer[-1][1]
        thr = cfg["night"]["dark_threshold"]
        status = "NIGHT" if meta.dark_score < thr else "DAY"
        return f"LEVEL={meta.dark_score:.1f} THRESH={thr} STATUS={status}"

    return "UNKNOWN_COMMAND"

TriggerServer(cfg["network"]["trigger_port"], on_trigger).start()

while True:
    cam.capture_once()

    now = time.time()
    interval = cfg["export"].get("auto_save_interval_s", 0)
    if interval > 0 and now - last_auto_save >= interval:
        frames = ring.get_last(1)
        if frames:
            saved = exporter.save(frames)
            logging.info(f"Hourly auto-save: {saved}")
            last_auto_save = now
""")

# Write files and zip
for name, content in files.items():
    with open(os.path.join(base, name), "w") as f:
        f.write(content)

zip_path = os.path.join(base, "pi_cam_service_py311.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for name in files:
        z.write(os.path.join(base, name), arcname=name)

zip_path

