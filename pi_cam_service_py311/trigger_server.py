import socket, threading

class TriggerServer(threading.Thread):
    def __init__(self, port, callback):
        super().__init__(daemon=True)
        self.port = port
        self.callback = callback

    def run(self):
        s = socket.socket()
        s.bind(("", self.port))
        s.listen(5)
        while True:
            c,_ = s.accept()
            cmd = c.recv(1024).decode().strip()
            self.callback(cmd)
            c.close()
