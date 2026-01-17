
class NightModeController:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.dark_count = 0
        self.active = False

    def update(self, score: float) -> str | None:
        if score < self.cfg["dark_threshold"]:
            self.dark_count += 1
        else:
            self.dark_count = 0

        match (self.active, self.dark_count >= self.cfg["min_dark_frames"]):
            case (False, True):
                self.active = True
                return "ENTER"
            case (True, False) if score > self.cfg["bright_threshold"]:
                self.active = False
                return "EXIT"
            case _:
                return None
