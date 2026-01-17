from collections import deque
import threading

class RingBuffer:
    def __init__(self, size):
        self.buffer = deque(maxlen=size)
        self.lock = threading.Lock()

    def append(self, item):
        with self.lock:
            self.buffer.append(item)

    def get_last(self, n):
        with self.lock:
            return list(self.buffer)[-n:]

    def get_last_seconds(self, seconds, fps):
        return self.get_last(int(seconds * fps))
