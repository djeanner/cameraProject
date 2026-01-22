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
    """Draw metadata overlay on image"""
    h, w, _ = img.shape

    frame_id = headers.get("X-Frame-Id", "?")
    dark = headers.get("X-Dark-Score", "?")
    night = headers.get("X-Night", "0")
    ts = headers.get("X-Timestamp", "?")

    lines = [
        f"Frame: {frame_id}",
        f"Dark score: {dark}",
        f"Night: {'YES' if night == '1' else 'NO'}",
        f"Timestamp: {ts}",
    ]

    y = 25
    for line in lines:
        cv2.putText(
            img,
            line,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0) if night == "1" else (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        y += 30

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
