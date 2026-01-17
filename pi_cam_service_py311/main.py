import json, logging
from ring_buffer import RingBuffer
from camera_controller import CameraController
from night_mode import NightModeController
from exporter import Exporter
from trigger_server import TriggerServer

with open("config.json") as f:
    cfg: dict = json.load(f)

logging.basicConfig(level=cfg["logging"]["level"])

ring = RingBuffer(cfg["ring"]["size"])
exporter = Exporter(cfg["export"])
cam = CameraController(cfg["camera"], ring)
cam.start_video()

night = NightModeController(cfg["night"])
last_dark_score = 0.0

def on_trigger(cmd: str) -> str | None:
    if cmd == "save":
        frames = ring.get_last_seconds(cfg["export"]["save_before_s"], cfg["camera"]["framerate"])
        saved_files: list[str] = []
        if cfg["export"]["stack_dark_frames"]:
            saved_files = exporter.stack_and_save(frames[-cfg["export"]["stack_count"]:])
        else:
            saved_files = exporter.save(frames)
        return "SAVED:" + ",".join(saved_files)

    elif cmd == "night_level":
        if not ring.buffer:
            return "NO DATA"
        meta = ring.buffer[-1][1]
        thr = cfg["night"]["dark_threshold"]
        status = "NIGHT" if meta.dark_score < thr else "DAY"
        return f"LEVEL={meta.dark_score:.1f} THRESH={thr} STATUS={status}"

    return None

TriggerServer(cfg["network"]["trigger_port"], on_trigger).start()

cam.capture_loop()
