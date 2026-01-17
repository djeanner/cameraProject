import socket, threading
from typing import Callable

class TriggerServer(threading.Thread):
    def __init__(self, port: int, callback: Callable[[str], str | None]) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.callback = callback

    def run(self) -> None:
        s = socket.socket()
        s.bind(("", self.port))
        s.listen(5)
        while True:
            conn, _ = s.accept()
            cmd = conn.recv(1024).decode().strip()
            response = self.callback(cmd)
            if response is not None:
                conn.sendall(response.encode())
            conn.close()
