import json
import logging
import time
import concurrent.futures

from ring_buffer import RingBuffer
from camera_controller import CameraController
from exporter import Exporter
from trigger_server import TriggerServer

# Load configuration
with open("config.json") as f:
    cfg: dict = json.load(f)

logging.basicConfig(level=cfg["logging"]["level"])

# Initialize components
ring = RingBuffer(cfg["ring"]["size"])
exporter = Exporter(cfg["export"])
cam = CameraController(cfg["camera"], ring)
cam.start_video()

# Auto-save tracking
last_auto_save = 0.0
CAPTURE_TIMEOUT = cfg["camera"].get("capture_timeout_s", 2.0)  # default 2s timeout
executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)


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


# Start the trigger server
TriggerServer(cfg["network"]["trigger_port"], on_trigger).start()
logging.info("Trigger server started")

# Main loop with timeout handling
logging.info("Starting main capture loop")
while True:
    try:
        # Run capture in a separate thread with timeout
        future = executor.submit(cam.capture_once)
        future.result(timeout=CAPTURE_TIMEOUT)
    except concurrent.futures.TimeoutError:
        logging.warning("Camera capture timed out! Skipping this frame.")
        continue
    except Exception as e:
        logging.error(f"Camera capture failed: {e}")
        time.sleep(1)
        continue

    # Auto-save logic
    now = time.time()
    interval = cfg["export"].get("auto_save_interval_s", 0)
    if interval > 0 and now - last_auto_save >= interval:
        frames = ring.get_last(1)
        if frames:
            try:
                saved = exporter.save(frames)
                logging.info(f"Hourly auto-save: {saved}")
            except Exception as e:
                logging.error(f"Auto-save failed: {e}")
        last_auto_save = now
