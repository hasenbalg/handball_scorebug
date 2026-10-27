from dataclasses import dataclass


@dataclass
class Suspension:
    """A 2-minute suspension measured on the GAME clock (IHF 16:3 with 2:8).

    `remaining` only decreases while the game clock runs (see
    ScoreboardState.update_time) — stopping the clock (ball out, referee
    interruption, team time-out, half time) freezes suspension time too.
    """

    player: str
    remaining: int  # seconds still to serve on the game clock

    def tick(self, seconds: int) -> None:
        """Advance the game clock by `seconds`: reduce remaining time served."""
        if seconds > 0:
            self.remaining = max(0, self.remaining - seconds)

    def to_dict(self) -> dict:
        return {"player": self.player, "remaining": self.remaining}
