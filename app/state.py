import json
import time
import redis
from dataclasses import dataclass, asdict
from suspension import Suspension
from card import Card

# Redis connection
r = redis.Redis(host="redis", port=6379, db=0)
REDIS_KEY = "scoreboard_state"

# Periods: (name, duration in seconds)
PERIODS = [
    ("1st Half", 30 * 60),
    ("2nd Half", 30 * 60),
    ("60 Min", 60 * 60),
]


@dataclass
class ScoreboardState:
    home_team: str = "Home"
    away_team: str = "Away"
    home_score: int = 0
    away_score: int = 0

    period_index: int = 0
    elapsed_seconds: int = 0  # counts UP
    running: bool = False
    start_time: float | None = None

    # Colors
    home_color: str = "#005eff"
    away_color: str = "#ff3b3b"

    # Suspensions
    home_suspensions: list | None = None
    away_suspensions: list | None = None

    # Cards
    home_cards: list | None = None
    away_cards: list | None = None

    # Timeouts
    home_timeout_end: float | None = None
    away_timeout_end: float | None = None
    TIMEOUT_DURATION: int = 60  # seconds

    hide_scorebug: bool = False

    shootout_active: bool = False
    home_shootout: list | None = None
    away_shootout: list | None = None

    buzzer_played: bool = False

    def __post_init__(self):
        if self.home_suspensions is None:
            self.home_suspensions = []
        if self.away_suspensions is None:
            self.away_suspensions = []
        if self.home_cards is None:
            self.home_cards = []
        if self.away_cards is None:
            self.away_cards = []
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

        # Backward compatibility defaults
        data.setdefault("home_suspensions", [])
        data.setdefault("away_suspensions", [])
        data.setdefault("home_cards", [])
        data.setdefault("away_cards", [])
        data.setdefault("home_color", "#005eff")
        data.setdefault("away_color", "#ff3b3b")

        if "remaining_seconds" in data and "elapsed_seconds" not in data:
            data["elapsed_seconds"] = data.pop("remaining_seconds")

        # Rehydrate suspensions
        def make_susp_list(lst):
            out = []
            for s in lst:
                if isinstance(s, dict):
                    out.append(Suspension(
                        player=s.get("player"),
                        start_time=s.get("start_time"),
                        duration=s.get("duration"),
                    ))
                else:
                    out.append(s)
            return out

        data["home_suspensions"] = make_susp_list(data["home_suspensions"])
        data["away_suspensions"] = make_susp_list(data["away_suspensions"])

        # Rehydrate cards
        def make_cards_list(lst):
            out = []
            for c in lst:
                if isinstance(c, dict):
                    out.append(Card(
                        player=c.get("player"),
                        start_time=c.get("start_time"),
                        duration=c.get("duration"),
                        color=c.get("color")
                    ))
                else:
                    out.append(c)
            return out

        data["home_cards"] = make_cards_list(data["home_cards"])
        data["away_cards"] = make_cards_list(data["away_cards"])

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
                self.elapsed_seconds += int(elapsed)
                self.start_time = now

                period_cap = PERIODS[self.period_index][1]
                if self.elapsed_seconds >= period_cap:
                    self.elapsed_seconds = period_cap
                    self.running = False
                    self.start_time = None

                    # 🔔 Only emit once
                    if not self.buzzer_played:
                        from app import socketio
                        socketio.emit("time_over")
                        self.buzzer_played = True

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
        self.buzzer_played = False   # reset for next period

    def set_period_index(self, index: int):
        index = max(0, min(len(PERIODS) - 1, index))
        self.stop_timer()
        self.period_index = index
        self.elapsed_seconds = 0
        self.buzzer_played = False

    # ----- Suspensions -----

    def cleanup_suspensions(self):
        def still_active(s):
            if hasattr(s, "remaining"):
                return s.remaining() > 0
            elif isinstance(s, dict):
                # compute remaining manually
                start = s.get("start_time", 0)
                duration = s.get("duration", 0)
                return (start + duration) > time.time()
            return False

        self.home_suspensions = [s for s in self.home_suspensions if still_active(s)]
        self.away_suspensions = [s for s in self.away_suspensions if still_active(s)]

    def add_suspension_home(self, player: str, duration: int = 120):
        self.home_suspensions.append(Suspension(player, time.time(), duration))

    def add_suspension_away(self, player: str, duration: int = 120):
        self.away_suspensions.append(Suspension(player, time.time(), duration))

    def delete_suspension_home(self, index: int):
        if 0 <= index < len(self.home_suspensions):
            del self.home_suspensions[index]

    def delete_suspension_away(self, index: int):
        if 0 <= index < len(self.away_suspensions):
            del self.away_suspensions[index]


    # ----- Cards -----

    def cleanup_cards(self):
        def still_active(c):
            if hasattr(c, "remaining"):
                return c.remaining() > 0
            elif isinstance(c, dict):
                # compute remaining manually
                start = c.get("start_time", 0)
                duration = c.get("duration", 0)
                return (start + duration) > time.time()
            return False

        self.home_cards = [c for c in self.home_cards if still_active(c)]
        self.away_cards = [c for c in self.away_cards if still_active(c)]

    def add_card_home(self, player: str, color: str = "yellow", duration: int = 10):
        self.home_cards.append(Card(player, time.time(), duration, color))

    def add_card_away(self, player: str, color: str = "yellow", duration: int = 10):
        self.away_cards.append(Card(player, time.time(), duration, color))

    def delete_card_home(self, index: int):
        if 0 <= index < len(self.home_cards):
            del self.home_cards[index]

    def delete_card_away(self, index: int):
        if 0 <= index < len(self.away_cards):
            del self.away_cards[index]

    # ----- Timeouts -----

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
        self.home_cards = []
        self.away_cards = []
        self.home_timeout_end = None
        self.away_timeout_end = None
        self.buzzer_played = False

    # ----- Shootout -----

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
        self.cleanup_cards()

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
            "home_suspensions": [s.to_dict() for s in self.home_suspensions],
            "away_suspensions": [s.to_dict() for s in self.away_suspensions],
            "home_cards": [s.to_dict() for s in self.home_cards],
            "away_cards": [s.to_dict() for s in self.away_cards],
            "home_timeout_active": self.home_timeout_end is not None,
            "away_timeout_active": self.away_timeout_end is not None,
            "home_timeout_remaining": max(0, int(self.home_timeout_end - time.time())) if self.home_timeout_end else 0,
            "away_timeout_remaining": max(0, int(self.away_timeout_end - time.time())) if self.away_timeout_end else 0,
            "hide_scorebug": self.hide_scorebug,
            "shootout_active": self.shootout_active,
            "home_shootout": self.home_shootout,
            "away_shootout": self.away_shootout,
        }
