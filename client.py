import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import cv2
import numpy as np
import time
import os
from datetime import datetime, timedelta


UPSTREAM_HOST = "raspberrypi"
UPSTREAM_PORT = 8080
UPSTREAM_PATH = "/stream"

BOUNDARY = b"--frame"

# ----- Configurable periodic saver -----
SAVE_PERIODIC = True  
SAVE_DIR = "capturesOverlay"             # base directory
SAVE_INTERVAL_MIN = 5             # save every 5 minutes
SAVE_HOURLY_INTERVAL = 60         # save hourly image
SAVE_5MIN_RETENTION_HOURS = 24    # 5-min images retention
SAVE_HOURLY_RETENTION_DAYS = 28   # hourly images retention

if SAVE_PERIODIC:
    os.makedirs(SAVE_DIR, exist_ok=True)

# Keep track of last save times
_last_5min_save = None
_last_hourly_save = None

def draw_overlay(img, headers):
    """Draw metadata overlay on image with parameterizable fonts, colors, sizes, and GitHub link."""

    h, w, _ = img.shape

    # ----- Overlay configuration -----
    circle_radius = 18
    circle_margin = 12
    circle_colors = {"day": (0, 255, 255), "night": (139, 0, 0)}  # BGR

    circle_label_font = cv2.FONT_HERSHEY_SIMPLEX
    circle_label_scale = 0.6
    circle_label_thickness = 1
    circle_label_color = (255, 255, 255)  # white

    dark_text_font = cv2.FONT_HERSHEY_SIMPLEX
    dark_text_scale = 0.6
    dark_text_thickness = 1
    dark_text_color = (255, 255, 255)

    hud_font = cv2.FONT_HERSHEY_SIMPLEX
    hud_scale = 0.6
    hud_thickness = 1
    hud_color_day = (255, 255, 255)
    hud_color_night = (0, 255, 0)
    hud_line_spacing = 30
    hud_start_y = 25
    hud_start_x = 10

    # GitHub link watermark
    link_font = cv2.FONT_HERSHEY_SIMPLEX
    link_scale = 0.7
    link_thickness = 1
    link_color = (200, 200, 200)
    link_margin = 10
    link_text = "https://github.com/djeanner/cameraProject"

    # ----- Parse metadata -----
    frame_id = headers.get("X-Frame-Id", "?")
    dark_score = float(headers.get("X-Dark-Score", 0))
    night = headers.get("X-Night", "0") == "1"
    ts = headers.get("X-Timestamp", "?")

    # ----- Day / Night indicator -----
    center = (w - circle_margin - circle_radius, circle_margin + circle_radius)
    color = circle_colors["night"] if night else circle_colors["day"]
    label = "NIGHT" if night else "DAY"

    cv2.circle(img, center, circle_radius, color, -1)
    cv2.putText(
        img,
        label,
        (center[0] - 70, center[1] + 8),
        circle_label_font,
        circle_label_scale,
        circle_label_color,
        circle_label_thickness,
        cv2.LINE_AA
    )

    # Dark score
    cv2.putText(
        img,
        f"Brightness {dark_score:.1f}",
        (center[0] - 150, center[1] + 36),
        dark_text_font,
        dark_text_scale,
        dark_text_color,
        dark_text_thickness,
        cv2.LINE_AA
    )

    # ----- HUD (top-left) -----
    lines = [
        f"Frame: {frame_id}",
        f"Timestamp: {ts}",
    ]
    y = hud_start_y
    for line in lines:
        cv2.putText(
            img,
            line,
            (hud_start_x, y),
            hud_font,
            hud_scale,
            hud_color_night if night else hud_color_day,
            hud_thickness,
            cv2.LINE_AA,
        )
        y += hud_line_spacing

    # ----- GitHub link watermark (bottom-left) -----
    cv2.putText(
        img,
        link_text,
        (link_margin, h - link_margin),
        link_font,
        link_scale,
        link_color,
        link_thickness,
        cv2.LINE_AA
    )

    return img

class OverlayProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/stream":
            self.send_error(404)
            return

        upstream = socket.create_connection((UPSTREAM_HOST, UPSTREAM_PORT))
        upstream.sendall(
            f"GET {UPSTREAM_PATH} HTTP/1.1\r\n"
            f"Host: {UPSTREAM_HOST}\r\n\r\n".encode()
        )
        f = upstream.makefile("rb")

        # Skip upstream headers
        while True:
            line = f.readline()
            if not line or line == b"\r\n":
                break

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "multipart/x-mixed-replace; boundary=frame"
        )
        self.end_headers()

        print("Overlay proxy client connected")

        try:
            while True:
                line = f.readline()
                if not line:
                    break

                if not line.startswith(BOUNDARY):
                    continue

                headers = {}

                # Read part headers
                while True:
                    line = f.readline().strip()
                    if not line:
                        break
                    if b":" in line:
                        k, v = line.decode().split(":", 1)
                        headers[k.strip()] = v.strip()

                length = int(headers.get("Content-Length", 0))
                jpeg = f.read(length)

                # Decode JPEG
                img = cv2.imdecode(
                    np.frombuffer(jpeg, np.uint8),
                    cv2.IMREAD_COLOR
                )
                if img is None:
                    continue

                # Overlay
                img = draw_overlay(img, headers)
                save_frame(img, headers)
                # Re-encode JPEG
                ok, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ok:
                    continue

                data = encoded.tobytes()

                # Write downstream frame
                self.wfile.write(BOUNDARY + b"\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(data)}\r\n".encode())
                self.wfile.write(b"\r\n")
                self.wfile.write(data)
                self.wfile.write(b"\r\n")

        except Exception as e:
            print("Overlay proxy disconnected")
            print("Overlay proxy disconnected")

        finally:
            upstream.close()

# Keep track of last save times
_last_5min_save = None
_last_hourly_save = None

def save_frame(img, headers):
    """Save frame periodically according to retention rules."""
    global _last_5min_save, _last_hourly_save

    if not SAVE_PERIODIC:
        return

    now = datetime.now()
    saved_any = False

    # --- Save immediately at start ---
    if _last_5min_save is None:
        fname_5min = os.path.join(SAVE_DIR, f"frame_5min_{now.strftime('%Y%m%d_%H%M')}.jpg")
        cv2.imwrite(fname_5min, img)
        _last_5min_save = now
        saved_any = True

    if _last_hourly_save is None:
        fname_hourly = os.path.join(SAVE_DIR, f"frame_hourly_{now.strftime('%Y%m%d_%H')}.jpg")
        cv2.imwrite(fname_hourly, img)
        _last_hourly_save = now
        saved_any = True

    # --- Save every 5 minutes ---
    if (now - _last_5min_save).total_seconds() >= SAVE_INTERVAL_MIN * 60:
        fname_5min = os.path.join(SAVE_DIR, f"frame_5min_{now.strftime('%Y%m%d_%H%M')}.jpg")
        cv2.imwrite(fname_5min, img)
        _last_5min_save = now
        saved_any = True

    # --- Save hourly ---
    if (now - _last_hourly_save).total_seconds() >= SAVE_HOURLY_INTERVAL * 60:
        fname_hourly = os.path.join(SAVE_DIR, f"frame_hourly_{now.strftime('%Y%m%d_%H')}.jpg")
        cv2.imwrite(fname_hourly, img)
        _last_hourly_save = now
        saved_any = True

    # --- Cleanup old files only when saving ---
    if saved_any:
        for f in os.listdir(SAVE_DIR):
            fpath = os.path.join(SAVE_DIR, f)
            try:
                ts = os.path.getmtime(fpath)
                age = datetime.fromtimestamp(ts)
                if f.startswith("frame_5min_") and (now - age) > timedelta(hours=SAVE_5MIN_RETENTION_HOURS):
                    os.remove(fpath)
                elif f.startswith("frame_hourly_") and (now - age) > timedelta(days=SAVE_HOURLY_RETENTION_DAYS):
                    os.remove(fpath)
            except Exception as e:
                print("Error cleaning old files:", e)

class MJPEGOverlayProxy(threading.Thread):
    def __init__(self, port=8090):
        super().__init__(daemon=True)
        self.port = port

    def run(self):
        server = HTTPServer(("0.0.0.0", self.port), OverlayProxyHandler)
        print(f"Overlay MJPEG proxy running on http://localhost:{self.port}/stream")
        if SAVE_PERIODIC:
            print(f"Save periodic overlay MJPEG images in {SAVE_DIR}")     
        server.serve_forever()


if __name__ == "__main__":
    MJPEGOverlayProxy().start()
    input("Press Enter to stop\n")
