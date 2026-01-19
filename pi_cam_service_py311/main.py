import concurrent.futures
import gc
import json
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import numpy as np
import psutil

from camera_controller import CameraController
from exporter import Exporter
from night_mode import NightModeController
from ring_buffer import RingBuffer
from trigger_server import TriggerServer
from metadata import FrameMetadata

def get_frames_for_save(ring: RingBuffer, cfg: dict) -> list[tuple[np.ndarray, FrameMetadata]]:
    """
    Récupère les images à sauvegarder pour la commande 'save'.
    
    - Le point central correspond à 'save_before_s' secondes avant le trigger.
    - Si stack_dark_frames est activé, on empile 'stack_count' images autour.
    """
    fps = cfg["camera"]["framerate"]
    save_before_s = cfg["export"]["save_before_s"]
    stack_count = cfg["export"]["stack_count"]

    # nombre total d'images à récupérer de la fenêtre complète
    total_frames = int(save_before_s * fps)
    frames = ring.get_last(total_frames)

    if not frames:
        return []

    if not cfg["export"]["stack_dark_frames"]:
        # pas d'empilement, on renvoie toute la fenêtre
        return frames

    # index approximatif du point central à -save_before_s secondes
    center_idx = max(0, len(frames) - int(fps * save_before_s))

    # indices autour du centre pour empilement
    half_stack = stack_count // 2
    start_idx = max(0, center_idx - half_stack)
    end_idx = min(len(frames), start_idx + stack_count)

    return frames[start_idx:end_idx]

def setup_logging(cfg: dict) -> None:
    log_level = getattr(logging, cfg["logging"]["level"].upper(), logging.INFO)

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "camera_service.log"

    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Avoid duplicate handlers if restarted
    if logger.handlers:
        return

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(formatter)

    # Rotating file handler
    file = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MiB
        backupCount=3
    )
    file.setLevel(log_level)
    file.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(file)

def adjust_ring_size(cfg: dict) -> int:
    vm = psutil.virtual_memory()

    usable_bytes = int(vm.available * 0.80)

    # Determine ring image resolution
    downscale_cfg = cfg["ring"].get("downscale", {})
    if downscale_cfg.get("enable", False):
        ring_width = downscale_cfg["width"]
        ring_height = downscale_cfg["height"]
        source = "downscaled ring images"
    else:
        ring_width = cfg["camera"]["width"]
        ring_height = cfg["camera"]["height"]
        source = "full-resolution camera images"

    channels = 3  # RGB
    dtype = np.uint8

    bytes_per_pixel = np.dtype(dtype).itemsize * channels
    bytes_per_image = ring_width * ring_height * bytes_per_pixel

    max_images = max(1, usable_bytes // bytes_per_image)

    requested = cfg["ring"]["size"]
    effective = min(requested, max_images)

    # Log adjustment ONLY if needed
    if effective != requested:
        logging.warning(
            "Ring buffer size adjusted: requested=%d → effective=%d",
            requested, effective
        )

    # Always log calculation details (expert traceability)
    logging.info(
        "Ring memory calculation details:\n"
        "  Available RAM       : %.1f MiB\n"
        "  Usable (80%%)        : %.1f MiB\n"
        "  Image format         : RGB uint8\n"
        "  Ring image size      : %dx%d\n"
        "  Bytes per image      : %.1f KiB\n"
        "  Max images possible  : %d\n",
        vm.available / (1024 * 1024),
        usable_bytes / (1024 * 1024),
        ring_width,
        ring_height,
        bytes_per_image / 1024,
        max_images
    )

    return effective
    
# Configuration

with open("config.json") as f:
    cfg = json.load(f)

setup_logging(cfg)

# Initialize components

effective_ring_size = adjust_ring_size(cfg)
ring = RingBuffer(effective_ring_size)
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

        # Capture full-resolution image directly
        img = cam.capture_fullres()
        meta = ring.get_last(1)[0][1]
        saved_files = exporter.save([(img, meta)], formats)
        del img

        age_s = time.time() - meta.timestamp  # time since capture

        if saved_files:
            msg = f"Saved single full-resolution image: {saved_files[0]} (timestamp: {meta.timestamp:.3f}, age: {age_s:.2f}s)"
        else:
            msg = "NOT_SAVED"

        logging.info(msg)
        return msg

    if cmd.startswith("pastStack"):
        parts = cmd.split()
        formats = parts[1:] if len(parts) > 1 else None

        frames_to_save = get_frames_for_save(ring, cfg)
        if not frames_to_save:
            msg = "NO_FRAMES"
            logging.info(msg)
            return msg

        now = time.time()
        first_frame = frames_to_save[0][1]
        last_frame = frames_to_save[-1][1]
        age_first = now - first_frame.timestamp
        age_last = now - last_frame.timestamp

        # Determine whether stacking is applied
        if cfg["export"]["stack_dark_frames"]:
            saved_files = exporter.stack_and_save(frames_to_save, formats)
            if saved_files:
                msg = (
                    f"Saved stacked image: {saved_files[0]} | stack of {len(frames_to_save)} frames | "
                    f"first frame timestamp: {first_frame.timestamp:.3f} (age: {age_first:.2f}s) | "
                    f"last frame timestamp: {last_frame.timestamp:.3f} (age: {age_last:.2f}s)"
                    f"(export.save_before_s: {cfg['export']['save_before_s']:.3f} s)"
                )
            else:
                msg = "NOT_SAVED"
        else:
            saved_files = exporter.save(frames_to_save, formats)
            if saved_files:
                msg = (
                    f"Saved {len(saved_files)} separate images from ring buffer, "
                    f"starting at timestamp: {first_frame.timestamp:.3f} (age: {age_first:.2f}s)"
                    f"(export.save_before_s: {cfg['export']['save_before_s']:.3f} s)"
                )
            else:
                msg = "NOT_SAVED"

        logging.info(msg)
        return msg

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
            if cfg["export"].get("auto_save_use_ring", False):                
                # NOT saving image from ring. Retake another image
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
