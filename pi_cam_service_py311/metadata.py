from dataclasses import dataclass

@dataclass
class FrameMetadata:
    frame_id: int
    timestamp: float
    dark_score: float
    night_mode: bool
