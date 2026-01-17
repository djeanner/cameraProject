
from collections import deque
import threading
from typing import Tuple, List
import numpy as np
from metadata import FrameMetadata

class RingBuffer:
    def __init__(self, size: int) -> None:
        self.buffer: deque[Tuple[np.ndarray, FrameMetadata]] = deque(maxlen=size)
        self.lock = threading.Lock()

    def append(self, item: Tuple[np.ndarray, FrameMetadata]) -> None:
        with self.lock:
            self.buffer.append(item)

    def get_last(self, n: int) -> List[Tuple[np.ndarray, FrameMetadata]]:
        with self.lock:
            return list(self.buffer)[-n:]

    def get_last_seconds(self, seconds: int, fps: int) -> List[Tuple[np.ndarray, FrameMetadata]]:
        return self.get_last(int(seconds * fps))
