import json
import logging
import time
import concurrent.futures
import psutil
import gc

from ring_buffer import RingBuffer
from camera_controller import CameraController
from exporter import Exporter
from trigger_server import TriggerServer
from night_mode import NightModeController

# Configuration

with open("config.json") as f:
    cfg = json.load(f)

logging.basicConfig(level=cfg["logging"]["level"])

# Initialize components

ring = RingBuffer(cfg["ring"]["size"])
exporter = Exporter(cfg["export"])
cam = CameraController(cfg["camera"], ring)
night_ctrl = NightModeController(cfg["night"])

process = psutil.Process()
last_mem_log = 0
last_auto_save = 0

CAPTURE_TIMEOUT = cfg["camera"].get("capture_timeout_s", 4.0)
MAX_RSS_MB = 350  # hard safety limit for Pi 1B+

# Helper

def log_mode_change(old, new):
    logging.info("Camera configuration updated:")
    for k in new:
        if old is None or old.get(k) != new.get(k):
            logging.info("  %s: %s → %s", k, old.get(k) if old else None, new[k])

def log_memory(prefix=""):
    rss = process.memory_info().rss / (1024*1024)
    swap = psutil.swap_memory().percent
    logging.info("%sRSS=%.1f MiB | SWAP=%.1f%%", prefix, rss, swap)
    return rss, swap

# Start camera

cam.start_video()
log_mode_change(None, cam.describe_mode())

# Trigger handler

def on_trigger(cmd: str) -> str:
    cmd = cmd.strip()

    if cmd.startswith("save"):
        parts = cmd.split()
        formats = parts[1:] if len(parts) > 1 else None

        frames = ring.get_last_seconds(
            cfg["export"]["save_before_s"],
            cfg["camera"]["framerate"]
        )

        if not frames:
            return "NO_FRAMES"

        if cfg["export"]["stack_dark_frames"]:
            used = frames[-cfg["export"]["stack_count"]:]
            saved = exporter.stack_and_save(used, formats)
        else:
            saved = exporter.save(frames, formats)

        return "SAVED:" + ",".join(saved) if saved else "NOT_SAVED"

    if cmd == "night_level":
        if not ring.buffer:
            return "NO_DATA"

        meta = ring.buffer[-1][1]
        status = "NIGHT" if night_ctrl.active else "DAY"
        return (
            f"LEVEL={meta.dark_score:.1f} "
            f"THRESH={cfg['night']['dark_threshold']} "
            f"STATUS={status}"
        )
        
    if cmd == "health":
        rss, swap = log_memory("HEALTH ")
        return f"RSS={rss:.1f}MiB SWAP={swap:.1f}%"
    
    return "UNKNOWN_COMMAND"

# Start trigger server

TriggerServer(cfg["network"]["trigger_port"], on_trigger).start()
logging.info("Trigger server started")

# Main loop with timeout handling
logging.info("Starting main capture loop")
while True:
    try:
        # test health
        rss, swap = log_memory() if time.time() - last_mem_log > 60 else (None, None)
        last_mem_log = time.time()

        if swap is not None:
            if swap > 85:
                logging.error("Critical swap %.1f%% → forcing GC + pause", swap)
                gc.collect()
                time.sleep(3)
                continue

            if swap > 70:
                logging.warning("High swap %.1f%% → slowing capture", swap)
                time.sleep(1.5)

        start = time.time()
        cam.capture_once()
        duration = time.time() - start
        if duration > CAPTURE_TIMEOUT:
            logging.warning("Camera capture slow (%.1fs > %.1fs) at %s", duration, CAPTURE_TIMEOUT, time.strftime("%H:%M:%S"))

        event = None
        if ring.buffer:
            _, meta = ring.buffer[-1]
            # Always evaluate brightness, regardless of camera mode
            event = night_ctrl.update(meta.dark_score)

            if event == "ENTER" and cam.mode != "still":
                logging.info("Night detected")
                before = cam.describe_mode()
                cam.start_still(cfg["night"])
                after = cam.describe_mode()
                log_mode_change(before, after)

            elif event == "EXIT" and cam.mode != "video":
                logging.info("Day detected")
                before = cam.describe_mode()
                cam.start_video()
                after = cam.describe_mode()
                log_mode_change(before, after)

        # Auto-save logic

        now = time.time()
        interval = cfg["export"].get("auto_save_interval_s", 0)
        if interval > 0 and now - last_auto_save >= interval:
            if True:
                # NOT saving image from ring. Take another image
                img = cam.capture_fullres()
                meta = ring.get_last(1)[0][1]
                exporter.save([(img, meta)])
                del img
            else:
                # save image from ring // may require to move the  exept below aboveAuto-save logic 
                frames = ring.get_last(1)
                if frames:
                    try:
                        saved = exporter.save(frames)
                        logging.info(f"Auto-save: {saved}")
                    except Exception as e:
                        logging.error(f"Auto-save failed: {e}")
            last_auto_save = now

        # --- HARD SAFETY EXIT ---
        
        rss = process.memory_info().rss / (1024*1024)
        if rss > MAX_RSS_MB:
            logging.critical(
                "RSS %.1f MiB exceeded limit %d → exiting for restart",
                rss, MAX_RSS_MB
            )
            raise SystemExit(42)
        # Slow down capture in still mode
        if cam.mode == "still":
            time.sleep(2)

    except Exception as e:
        logging.error("Camera loop error: %s", e)
        time.sleep(2)
