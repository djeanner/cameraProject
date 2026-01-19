import socket
import threading
from typing import Callable

class TriggerServer(threading.Thread):
    def __init__(self, port: int, callback: Callable[[str, "socket.socket"], str]) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.callback = callback

    def run(self) -> None:
        s = socket.socket()
        s.bind(("", self.port))
        s.listen(5)
        while True:
            conn, _ = s.accept()
            try:
                cmd = conn.recv(1024).decode().strip()
                response = self.callback(cmd, conn)
                # Only send textual response if not already streaming
                if not cmd.startswith("stream"):
                    conn.sendall((response + "\n").encode())
            finally:
                conn.close()
