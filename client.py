import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import cv2
import numpy as np
import time

UPSTREAM_HOST = "raspberrypi"
UPSTREAM_PORT = 8080
UPSTREAM_PATH = "/stream"

BOUNDARY = b"--frame"


def draw_overlay(img, headers):
    """Draw metadata overlay on image with parameterizable fonts, colors, and sizes."""

    h, w, _ = img.shape

    # ----- Overlay configuration -----
    # Circle (day/night) settings
    circle_radius = 18
    circle_margin = 12
    circle_colors = {"day": (0, 255, 255), "night": (139, 0, 0)}  # BGR
    circle_label_font = cv2.FONT_HERSHEY_SIMPLEX
    circle_label_scale = 0.6
    circle_label_thickness = 1
    circle_label_color = (255, 255, 255)  # white

    # Dark score text settings
    dark_text_font = cv2.FONT_HERSHEY_SIMPLEX
    dark_text_scale = 0.6
    dark_text_thickness = 1
    dark_text_color = (255, 255, 255)

    # HUD (top-left) text settings
    hud_font = cv2.FONT_HERSHEY_SIMPLEX
    hud_scale = 0.6
    hud_thickness = 1
    hud_color_day = (255, 255, 255)
    hud_color_night = (0, 255, 0)
    hud_line_spacing = 30
    hud_start_y = 25
    hud_start_x = 10

    # ----- Parse metadata -----
    frame_id = headers.get("X-Frame-Id", "?")
    dark_score = float(headers.get("X-Dark-Score", 0))
    night = headers.get("X-Night", "0") == "1"
    ts = headers.get("X-Timestamp", "?")

    # ----- Day / Night indicator -----
    center = (w - circle_margin - circle_radius, circle_margin + circle_radius)  # top-right
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

        finally:
            upstream.close()


class MJPEGOverlayProxy(threading.Thread):
    def __init__(self, port=8090):
        super().__init__(daemon=True)
        self.port = port

    def run(self):
        server = HTTPServer(("0.0.0.0", self.port), OverlayProxyHandler)
        print(f"Overlay MJPEG proxy running on http://localhost:{self.port}/stream")
        server.serve_forever()


if __name__ == "__main__":
    MJPEGOverlayProxy().start()
    input("Press Enter to stop\n")
