class NightModeController:
    def __init__(self, cfg):
        self.cfg = cfg
        self.dark_count = 0
        self.active = False

    def update(self, score):
        if score < self.cfg["dark_threshold"]:
            self.dark_count += 1
        else:
            self.dark_count = 0

        if not self.active and self.dark_count >= self.cfg["min_dark_frames"]:
            self.active = True
            return "ENTER"

        if self.active and score > self.cfg["bright_threshold"]:
            self.active = False
            return "EXIT"

        return None
