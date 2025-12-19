import time
from dataclasses import dataclass


@dataclass
class Suspension:
    player: str
    start_time: float
    duration: int

    def remaining(self) -> int:
        elapsed = int(time.time() - self.start_time)
        return max(0, self.duration - elapsed)

    def to_dict(self) -> dict:
        return {
            "player": self.player,
            "remaining": self.remaining()
        }
