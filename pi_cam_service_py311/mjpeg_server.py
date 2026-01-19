import threading
import time
import cv2
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

class MJPEGHandler(BaseHTTPRequestHandler):
    ring = None
    fps = 2

    def do_GET(self):
        if self.path != "/stream":
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "multipart/x-mixed-replace; boundary=frame"
        )
        self.end_headers()

        logging.info("MJPEG client connected")

        try:
            while True:
                frames = self.ring.get_last(1)
                if not frames:
                    time.sleep(0.1)
                    continue

                img, meta = frames[0]
                ok, jpeg = cv2.imencode(".jpg", img)
                if not ok:
                    continue

                data = jpeg.tobytes()

                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(data)}\r\n".encode())
                # conventions metadata headers
                self.wfile.write(f"X-Frame-Id: {meta.frame_id}\r\n".encode()) 
                self.wfile.write(f"X-Timestamp: {meta.timestamp:.3f}\r\n".encode())
                # Custom metadata headers
                self.wfile.write(f"X-Dark-Score: {meta.dark_score:.1f}\r\n".encode())
                self.wfile.write(f"X-Night: {int(meta.night_mode)}\r\n".encode())
                # End of headers
                self.wfile.write(b"\r\n")

                self.wfile.write(data)

                time.sleep(1 / self.fps)

        except Exception as e:
            logging.info("MJPEG client disconnected")

class MJPEGServer(threading.Thread):
    def __init__(self, port, ring, fps=2):
        super().__init__(daemon=True)
        self.port = port
        MJPEGHandler.ring = ring
        MJPEGHandler.fps = fps

    def run(self):
        server = HTTPServer(("", self.port), MJPEGHandler)
        logging.info("MJPEG server listening on port %d", self.port)
        server.serve_forever()
