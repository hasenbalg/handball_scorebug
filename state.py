import json
import time
import redis
from dataclasses import dataclass, asdict

# Redis connection
r = redis.Redis(host="localhost", port=6379, db=0)
REDIS_KEY = "scoreboard_state"

# Periods: (name, duration in seconds)
PERIODS = [
    ("1st Half", 30 * 60),
    ("2nd Half", 30 * 60),
    ("Overtime 1", 5 * 60),
    ("Overtime 2", 5 * 60),
]


@dataclass
class ScoreboardState:
    home_team: str = "Home"
    away_team: str = "Away"
    home_score: int = 0
    away_score: int = 0

    period_index: int = 0
    elapsed_seconds: int = 0  # counts UP within the current period
    running: bool = False
    start_time: float | None = None

    # Colors
    home_color: str = "#005eff"
    away_color: str = "#ff3b3b"

    # Suspensions
    home_suspensions: list | None = None
    away_suspensions: list | None = None

    # Timeouts
    home_timeout_end: float | None = None
    away_timeout_end: float | None = None
    TIMEOUT_DURATION: int = 60  # seconds

    hide_scorebug: bool = False

    shootout_active: bool = False
    home_shootout: list | None = None
    away_shootout: list | None = None

    def __post_init__(self):
        if self.home_suspensions is None:
            self.home_suspensions = []
        if self.away_suspensions is None:
            self.away_suspensions = []
        if self.home_shootout is None:
            self.home_shootout = []
        if self.away_shootout is None:
            self.away_shootout = []

    # ----- Persistence -----

    @classmethod
    def load(cls) -> "ScoreboardState":
        raw = r.get(REDIS_KEY)
        if raw is None:
            return cls()

        data = json.loads(raw)

        # Backward compatibility for prior keys
        data.setdefault("home_suspensions", [])
        data.setdefault("away_suspensions", [])
        data.setdefault("home_color", "#005eff")
        data.setdefault("away_color", "#ff3b3b")

        # Migrate old countdown field to elapsed
        if "remaining_seconds" in data and "elapsed_seconds" not in data:
            data["elapsed_seconds"] = data.pop("remaining_seconds")

        return cls(**data)

    def save(self):
        self.update_time()
        self.update_timeouts()
        r.set(REDIS_KEY, json.dumps(asdict(self)))

    # ----- Time -----

    @property
    def period_name(self) -> str:
        return PERIODS[self.period_index][0]

    def update_time(self):
        if self.running and self.start_time is not None:
            now = time.time()
            elapsed = now - self.start_time

            if elapsed >= 1:
                self.elapsed_seconds += int(elapsed)  # count up
                self.start_time = now

                # Optional cap at period duration (stop automatically)
                period_cap = PERIODS[self.period_index][1]
                if self.elapsed_seconds >= period_cap:
                    self.elapsed_seconds = period_cap
                    self.running = False
                    self.start_time = None

    def compute_time(self):
        self.update_time()
        return self.format_time(self.elapsed_seconds)

    @staticmethod
    def format_time(seconds: int) -> str:
        m = seconds // 60
        s = seconds % 60
        return f"{m:02d}:{s:02d}"

    def set_time(self, timestr: str):
        try:
            m, s = timestr.split(":")
            self.elapsed_seconds = int(m) * 60 + int(s)
        except Exception:
            return
        self.running = False
        self.start_time = None

    def start_timer(self):
        if not self.running:
            self.running = True
            self.start_time = time.time()

    def stop_timer(self):
        self.update_time()
        self.running = False
        self.start_time = None

    # ----- Periods -----

    def next_period(self):
        self.stop_timer()
        self.period_index = min(len(PERIODS) - 1, self.period_index + 1)
        self.elapsed_seconds = 0

    def set_period_index(self, index: int):
        index = max(0, min(len(PERIODS) - 1, index))
        self.stop_timer()
        self.period_index = index
        self.elapsed_seconds = 0

    # ----- Suspensions -----

    def suspension_remaining(self, susp: dict) -> int:
        elapsed = int(time.time() - susp["start_time"])
        return max(0, susp["duration"] - elapsed)

    def cleanup_suspensions(self):
        self.home_suspensions = [
            s for s in self.home_suspensions if self.suspension_remaining(s) > 0
        ]
        self.away_suspensions = [
            s for s in self.away_suspensions if self.suspension_remaining(s) > 0
        ]

    def add_suspension_home(self, player: str, duration: int = 120):
        self.home_suspensions.append({
            "player": player,
            "start_time": time.time(),
            "duration": duration,
        })

    def add_suspension_away(self, player: str, duration: int = 120):
        self.away_suspensions.append({
            "player": player,
            "start_time": time.time(),
            "duration": duration,
        })

    def delete_suspension_home(self, index: int):
        if 0 <= index < len(self.home_suspensions):
            del self.home_suspensions[index]

    def delete_suspension_away(self, index: int):
        if 0 <= index < len(self.away_suspensions):
            del self.away_suspensions[index]

    # ----- Timeouts -----

    def in_first_half(self):
        return self.period_index == 0

    def in_second_half(self):
        return self.period_index == 1

    def start_timeout_home(self):
        self.home_timeout_end = time.time() + self.TIMEOUT_DURATION
        self.stop_timer()

    def start_timeout_away(self):
        self.away_timeout_end = time.time() + self.TIMEOUT_DURATION
        self.stop_timer()

    def update_timeouts(self):
        now = time.time()

        if self.home_timeout_end and now >= self.home_timeout_end:
            self.home_timeout_end = None

        if self.away_timeout_end and now >= self.away_timeout_end:
            self.away_timeout_end = None

    # ----- Reset -----

    def reset(self):
        self.home_score = 0
        self.away_score = 0
        self.period_index = 0
        self.elapsed_seconds = 0
        self.running = False
        self.start_time = None
        self.home_suspensions = []
        self.away_suspensions = []
        self.home_timeout_end = None
        self.away_timeout_end = None

    # ----- 7M Shootout -----

    def start_shootout(self):
        self.shootout_active = True
        self.home_shootout = []
        self.away_shootout = []

    def stop_shootout(self):
        self.shootout_active = False

    def add_shootout_attempt(self, is_home: bool, success: bool):
        if is_home:
            self.home_shootout.append(success)
        else:
            self.away_shootout.append(success)

    def undo_shootout(self, is_home: bool):
        if is_home and self.home_shootout:
            self.home_shootout.pop()
        if not is_home and self.away_shootout:
            self.away_shootout.pop()

    # ----- Public dict -----

    def to_public_dict(self) -> dict:
        self.update_time()
        self.update_timeouts()
        self.cleanup_suspensions()

        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "period_index": self.period_index,
            "period_name": self.period_name,
            "time": self.compute_time(),
            "running": self.running,
            "home_color": self.home_color,
            "away_color": self.away_color,

            "home_suspensions": [
                {"player": s["player"], "remaining": self.suspension_remaining(s)}
                for s in self.home_suspensions
            ],
            "away_suspensions": [
                {"player": s["player"], "remaining": self.suspension_remaining(s)}
                for s in self.away_suspensions
            ],

            # Timeouts
            "home_timeout_active": self.home_timeout_end is not None,
            "away_timeout_active": self.away_timeout_end is not None,
            "home_timeout_remaining": max(0, int(self.home_timeout_end - time.time())) if self.home_timeout_end else 0,
            "away_timeout_remaining": max(0, int(self.away_timeout_end - time.time())) if self.away_timeout_end else 0,
            "hide_scorebug": self.hide_scorebug,
            "shootout_active": self.shootout_active,
            "home_shootout": self.home_shootout,
            "away_shootout": self.away_shootout,
        }
