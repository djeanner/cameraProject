import json, logging
from ring_buffer import RingBuffer
from camera_controller import CameraController
from night_mode import NightModeController
from exporter import Exporter
from trigger_server import TriggerServer

with open("config.json") as f:
    cfg = json.load(f)

logging.basicConfig(level=cfg["logging"]["level"])

ring = RingBuffer(cfg["ring"]["size"])
exporter = Exporter(cfg["export"])

cam = CameraController(cfg["camera"], ring)
cam.start_video()

night = NightModeController(cfg["night"])

def on_trigger(cmd):
    logging.info(f"Trigger: {cmd}")
    frames = ring.get_last_seconds(
        cfg["export"]["save_before_s"], cfg["camera"]["framerate"]
    )
    if cfg["export"]["stack_dark_frames"]:
        exporter.stack_and_save(frames[-cfg["export"]["stack_count"]:])
    else:
        exporter.save(frames)

TriggerServer(cfg["network"]["trigger_port"], on_trigger).start()

cam.capture_loop()
