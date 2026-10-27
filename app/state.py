import json
import os
import time
import redis
from dataclasses import dataclass, asdict, field
from suspension import Suspension
from card import Card

# Redis connection: REDIS_URL (used by compose.yaml) or REDIS_HOST
# (default localhost so `python app/app.py` works outside Docker)
_url = os.environ.get("REDIS_URL")
if _url:
    r = redis.Redis.from_url(_url)
else:
    r = redis.Redis(host=os.environ.get("REDIS_HOST", "localhost"), port=6379, db=0)
REDIS_KEY = "scoreboard_state"


def _player_key(player) -> str:
    """Normalize a player identifier: '#7', ' 7 ' and '7' are the same player."""
    return str(player).strip().lstrip("#")

# Period definitions are per-state (see ScoreboardState.period_definitions);
# the match configuration (#10) decides halves length, overtime and the
# free '60 Min' running-time period. Each definition is
# (name, cap_seconds, swap_ends_on_entry).
# Rule basis: teams change ends for the second half of each period
# (Rule 10 Comment); a NEW coin toss precedes each overtime period, so
# entering overtime and switching OT periods must NOT auto-swap.


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
    home_suspensions: list = field(default_factory=list)
    away_suspensions: list = field(default_factory=list)
    # Cumulative suspensions per player, kept after the suspension expires
    # (16:5: a third suspension of the same player is a disqualification)
    home_suspension_counts: dict = field(default_factory=dict)
    away_suspension_counts: dict = field(default_factory=dict)
    home_disqualified: list = field(default_factory=list)
    away_disqualified: list = field(default_factory=list)

    # Cards
    home_cards: list = field(default_factory=list)
    away_cards: list = field(default_factory=list)

    # Timeouts
    home_timeout_end: float | None = None
    away_timeout_end: float | None = None
    technical_timeout_end: float | None = None
    TIMEOUT_DURATION: int = 60  # seconds

    hide_scorebug: bool = False
    # 2:8a: adding a suspension/DQ stops the clock for the announcement
    auto_stop_on_suspension: bool = True

    # Match configuration (#10)
    match_type: str = "league"      # league | cup | friendly
    half_minutes: int = 30          # 30 senior, 25 (u16), 20 (u12) — 2:1
    overtime_enabled: bool = False  # knockout matches (2:2)

    shootout_active: bool = False
    home_shootout: list = field(default_factory=list)
    away_shootout: list = field(default_factory=list)
    shootout_starting_team: str = "home"
    shootout_confirmed_winner: str | None = None

    buzzer_played: bool = False

    # Break timer (#7): wall-clock end of the current intermission
    break_end: float | None = None

    # Match log / event timeline (#5) — chronological, persisted with state
    match_log: list = field(default_factory=list)

    # Goals per player + last-scorer flash (#4)
    home_goal_scorers: list = field(default_factory=list)
    away_goal_scorers: list = field(default_factory=list)
    last_scorer: dict | None = None
    # Team time-out quota, per 2:4 Comment (#1): entries are period
    # slots ("half1" | "half2" | "ot"); max 3 per match, max 2 per half,
    # none in overtime. Violations are flagged, never blocked (operator
    # drives, app marks).
    home_timeouts_taken: list = field(default_factory=list)
    away_timeouts_taken: list = field(default_factory=list)

    # Passive play (#3, IHF 7:4 + Clarification 4): after the forewarning
    # signal the attacking team may make at most 4 passes before it must
    # shoot.
    PASSIVE_MAX_PASSES = 4
    passive_team: str | None = None
    passive_passes: int | None = None

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
        data.setdefault("home_suspension_counts", {})
        data.setdefault("away_suspension_counts", {})
        data.setdefault("home_disqualified", [])
        data.setdefault("away_disqualified", [])
        data.setdefault("auto_stop_on_suspension", True)
        data.setdefault("match_type", "league")
        data.setdefault("half_minutes", 30)
        data.setdefault("overtime_enabled", False)
        data.setdefault("home_cards", [])
        data.setdefault("away_cards", [])
        data.setdefault("match_log", [])
        data.setdefault("break_end", None)
        data.setdefault("passive_team", None)
        data.setdefault("passive_passes", None)
        data.setdefault("home_goal_scorers", [])
        data.setdefault("away_goal_scorers", [])
        data.setdefault("home_timeouts_taken", [])
        data.setdefault("away_timeouts_taken", [])
        data.setdefault("home_color", "#005eff")
        data.setdefault("away_color", "#ff3b3b")

        if "remaining_seconds" in data and "elapsed_seconds" not in data:
            data["elapsed_seconds"] = data.pop("remaining_seconds")

        # Rehydrate suspensions
        def make_susp_list(lst):
            out = []
            for s in lst:
                if isinstance(s, dict):
                    if "remaining" in s:
                        remaining = int(s.get("remaining") or 0)
                    else:
                        # Legacy wall-clock format: convert once on load.
                        start = s.get("start_time") or 0
                        duration = s.get("duration") or 0
                        remaining = max(0, int(duration - (time.time() - start)))
                    out.append(Suspension(player=_player_key(s.get("player") or "??"), remaining=remaining))
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

    # ----- Match log (#5) -----

    MAX_LOG_ENTRIES = 1000

    def log_event(self, type_: str, side: str | None = None,
                  player: str | None = None, detail: str | None = None):
        """Append one event to the chronological match log."""
        self.match_log.append({
            "at": int(time.time()),
            "clock": self.format_time(self.elapsed_seconds),
            "period": self.period_name,
            "type": type_,
            "side": side,
            "player": player,
            "detail": detail,
        })
        if len(self.match_log) > self.MAX_LOG_ENTRIES:
            del self.match_log[0]

    def log_delete_last(self):
        """Escape hatch for mis-clicked events."""
        if self.match_log:
            self.match_log.pop()

    # ----- Score / scorers (#4) -----

    def goal(self, side: str, scorer: str | None = None):
        """Increment score; optionally record scorer number (#4)."""
        key = _player_key(scorer) if scorer else None
        if side == "away":
            self.away_score += 1
            self.away_goal_scorers.append(key)
        else:
            self.home_score += 1
            self.home_goal_scorers.append(key)
        self.last_scorer = {"side": side, "player": key, "at": int(time.time())}
        self.clear_passive()  # a shot ends the 7:4 phase
        self.log_event("goal", side=side, player=key)

    def undo_goal(self, side: str):
        """Correct a mis-clicked goal: remove score, scorer and flash."""
        if side == "away":
            self.away_score = max(0, self.away_score - 1)
            if self.away_goal_scorers:
                self.away_goal_scorers.pop()
        else:
            self.home_score = max(0, self.home_score - 1)
            if self.home_goal_scorers:
                self.home_goal_scorers.pop()
        if self.last_scorer and self.last_scorer.get("side") == side:
            self.last_scorer = None
        self.clear_passive()  # goal or correction: new situation, 7:4 reset

    # ----- Passive play (#3) -----

    def set_passive(self, team: str | None):
        """Arm/disarm the forewarning indicator. Same team again = off
        (signal lifted, e.g. after a clear attack phase or free throw)."""
        if team not in ("home", "away") or team == self.passive_team:
            if self.passive_team:
                self.log_event("passive_off", side=self.passive_team)
            self.passive_team = None
            self.passive_passes = None
            return
        self.passive_team = team
        self.passive_passes = self.PASSIVE_MAX_PASSES
        self.log_event("passive_on", side=team)

    def passive_pass(self):
        """One completed pass by the flagged team (Clarification 4 count)."""
        if self.passive_team is None or self.passive_passes is None:
            return
        if self.passive_passes == 0:
            return  # already expired; whistle is the operator's call
        self.passive_passes -= 1
        if self.passive_passes == 0:
            self.log_event("passive_expired", side=self.passive_team)

    def clear_passive(self):
        """Any goal, clock stoppage or period change ends the phase."""
        if self.passive_team:
            self.log_event("passive_off", side=self.passive_team)
        self.passive_team = None
        self.passive_passes = None

    # ----- Time -----

    def period_definitions(self) -> list[tuple[str, int, bool, int]]:
        """(name, cap_seconds, swap_ends_on_entry, break_before_seconds)
        for the current config (#7). Break durations per 2:2/2:3:
        10-min half-time, 5 min before each overtime period, 1 min
        between the halves of an overtime period."""
        hm = self.half_minutes if self.half_minutes in (20, 25, 30) else 30
        defs = [("1st Half", hm * 60, False, 0), ("2nd Half", hm * 60, True, 10 * 60)]
        if self.overtime_enabled:
            defs += [
                ("OT1 1st Half", 5 * 60, False, 5 * 60),   # new coin toss: no auto-swap
                ("OT1 2nd Half", 5 * 60, True, 60),
                ("OT2 1st Half", 5 * 60, False, 5 * 60),   # new coin toss again
                ("OT2 2nd Half", 5 * 60, True, 60),
            ]
        defs.append(("60 Min", 60 * 60, False, 0))
        return defs

    def set_match_configuration(self, match_type=None, half_minutes=None,
                                overtime_enabled=None):
        if match_type in ("league", "cup", "friendly"):
            self.match_type = match_type
        if half_minutes is not None:
            try:
                hm = int(half_minutes)
            except (TypeError, ValueError):
                hm = None
            if hm in (20, 25, 30):
                self.half_minutes = hm
        if overtime_enabled is not None:
            self.overtime_enabled = bool(overtime_enabled)

    @property
    def period_name(self) -> str:
        return self.period_definitions()[self.period_index][0]

    def _period_slot(self) -> str:
        """Rule slot of the current period for the TO quota (2:4 Comment)."""
        name = self.period_name
        if name == "1st Half":
            return "half1"
        if name == "2nd Half":
            return "half2"
        return "ot"

    @staticmethod
    def _timeout_quota(taken: list) -> dict:
        """Quota view of a team's taken time-outs: max 3 per match, max 2
        per regular half, none in overtime (2:4 Comment). Flags only."""
        h1, h2, ot = taken.count("half1"), taken.count("half2"), taken.count("ot")
        return {
            "total": len(taken), "max": 3,
            "half1": h1, "half2": h2, "ot": ot,
            "over_total": len(taken) > 3,
            "over_half": h1 > 2 or h2 > 2,
            "ot_used": ot > 0,
        }

    def update_time(self):
        if self.running and self.start_time is not None:
            now = time.time()
            elapsed = now - self.start_time

            if elapsed >= 1:
                period_cap = self.period_definitions()[self.period_index][1]
                # Never run the game clock past the period cap; suspension
                # time is served on the game clock (2:8), so it advances by
                # exactly the same amount and freezes whenever we don't run.
                advance = min(int(elapsed), max(0, period_cap - self.elapsed_seconds))
                self.elapsed_seconds += advance
                self.start_time = now

                for susp in (*self.home_suspensions, *self.away_suspensions):
                    if isinstance(susp, Suspension):
                        susp.tick(advance)

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

    def referee_whistle(self):
        """Referee whistle models the mandatory time-out (2:8): stops a
        running clock, a second whistle resumes play."""
        if self.running:
            self.stop_timer()
            self.clear_passive()  # whistle = stoppage, 7:4 phase over
        else:
            self.start_timer()

    # ----- Periods -----
    def next_period(self):
        self.stop_timer()
        defs = self.period_definitions()
        idx = min(len(defs) - 1, self.period_index + 1)
        self.period_index = idx
        self.elapsed_seconds = 0
        self.buzzer_played = False   # reset for next period
        if defs[idx][2]:             # swap ends only where the rules say so
            self.side_change()
        self.clear_passive()
        self.log_event("period", detail=self.period_name)
        if defs[idx][3] > 0:         # #7: start the prescribed break
            self.break_end = time.time() + defs[idx][3]
            self.log_event("break_start", detail=f"{defs[idx][3] // 60} min before {defs[idx][0]}")

    def set_period_index(self, index: int):
        defs = self.period_definitions()
        index = max(0, min(len(defs) - 1, index))
        changed = index != self.period_index
        self.stop_timer()
        self.period_index = index
        self.elapsed_seconds = 0
        self.buzzer_played = False
        self.clear_passive()
        if changed:
            self.log_event("period", detail=self.period_name)
            if defs[index][3] > 0:
                self.break_end = time.time() + defs[index][3]
                self.log_event("break_start", detail=f"{defs[index][3] // 60} min before {defs[index][0]}")

    # ----- Suspensions -----

    def cleanup_suspensions(self):
        def still_active(s):
            # Suspensions are measured on the game clock; load() already
            # rehydrates legacy wall-clock entries, anything else is stale.
            return isinstance(s, Suspension) and s.remaining > 0

        self.home_suspensions = [s for s in self.home_suspensions if still_active(s)]
        self.away_suspensions = [s for s in self.away_suspensions if still_active(s)]

    def _register_suspension(self, counts: dict, disqualified: list, key: str):
        counts[key] = counts.get(key, 0) + 1
        if counts[key] >= 3 and key not in disqualified:
            disqualified.append(key)  # 16:5/16:6d: third suspension = disqualification

    def _revoke_suspension(self, counts: dict, disqualified: list, key: str):
        # Undo of a mis-click: roll the progression back with it
        if counts.get(key):
            counts[key] -= 1
            if counts[key] < 3 and key in disqualified:
                disqualified.remove(key)

    def add_suspension_home(self, player: str, duration: int = 120):
        key = _player_key(player)
        self.home_suspensions.append(Suspension(key, duration))
        self._register_suspension(self.home_suspension_counts, self.home_disqualified, key)
        self.clear_passive()
        self._announcement_timeout()
        self.log_event("suspension", side="home", player=key)
        if self.home_suspension_counts.get(key) == 3:
            self.log_event("disqualification", side="home", player=key)

    def add_suspension_away(self, player: str, duration: int = 120):
        key = _player_key(player)
        self.away_suspensions.append(Suspension(key, duration))
        self._register_suspension(self.away_suspension_counts, self.away_disqualified, key)
        self.clear_passive()
        self._announcement_timeout()
        self.log_event("suspension", side="away", player=key)
        if self.away_suspension_counts.get(key) == 3:
            self.log_event("disqualification", side="away", player=key)

    def _announcement_timeout(self):
        """2:8a: mandatory clock stop for the suspension announcement."""
        if self.auto_stop_on_suspension:
            self.stop_timer()

    def delete_suspension_home(self, index: int):
        if 0 <= index < len(self.home_suspensions):
            s = self.home_suspensions.pop(index)
            if isinstance(s, Suspension):
                self._revoke_suspension(self.home_suspension_counts, self.home_disqualified, _player_key(s.player))

    def delete_suspension_away(self, index: int):
        if 0 <= index < len(self.away_suspensions):
            s = self.away_suspensions.pop(index)
            if isinstance(s, Suspension):
                self._revoke_suspension(self.away_suspension_counts, self.away_disqualified, _player_key(s.player))


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
        key = _player_key(player)
        color = color if color in ("yellow", "red") else "yellow"
        self.home_cards.append(Card(key, time.time(), duration, color))
        self.log_event("card", side="home", player=key, detail=color)

    def add_card_away(self, player: str, color: str = "yellow", duration: int = 10):
        key = _player_key(player)
        color = color if color in ("yellow", "red") else "yellow"
        self.away_cards.append(Card(key, time.time(), duration, color))
        self.log_event("card", side="away", player=key, detail=color)

    def delete_card_home(self, index: int):
        if 0 <= index < len(self.home_cards):
            del self.home_cards[index]

    def delete_card_away(self, index: int):
        if 0 <= index < len(self.away_cards):
            del self.away_cards[index]

    # ----- Timeouts -----

    def start_timeout_home(self):
        self.home_timeout_end = time.time() + self.TIMEOUT_DURATION
        self.home_timeouts_taken.append(self._period_slot())
        self.stop_timer()
        self.clear_passive()
        self.log_event("timeout", side="home")

    def start_timeout_away(self):
        self.away_timeout_end = time.time() + self.TIMEOUT_DURATION
        self.away_timeouts_taken.append(self._period_slot())
        self.stop_timer()
        self.clear_passive()
        self.log_event("timeout", side="away")

    def start_technical_timeout(self):
        """2:8c-type interruption (injury, floor cleaning, referee decision):
        neutral time-out, game clock stopped, separate countdown (#6)."""
        self.technical_timeout_end = time.time() + self.TIMEOUT_DURATION
        self.stop_timer()
        self.clear_passive()
        self.log_event("technical_timeout")

    def skip_break(self):
        """Operator ends the intermission early (teams are ready)."""
        self.break_end = None

    def update_timeouts(self):
        now = time.time()
        if self.home_timeout_end and now >= self.home_timeout_end:
            self.home_timeout_end = None
        if self.away_timeout_end and now >= self.away_timeout_end:
            self.away_timeout_end = None
        if self.technical_timeout_end and now >= self.technical_timeout_end:
            self.technical_timeout_end = None
        if self.break_end and now >= self.break_end:
            self.break_end = None

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
        self.home_suspension_counts = {}
        self.away_suspension_counts = {}
        self.home_disqualified = []
        self.away_disqualified = []
        self.home_cards = []
        self.away_cards = []
        self.home_timeout_end = None
        self.away_timeout_end = None
        self.technical_timeout_end = None
        self.buzzer_played = False
        self.home_shootout = []
        self.away_shootout = []
        self.shootout_active = False
        self.shootout_starting_team = "home"
        self.shootout_confirmed_winner = None
        self.hide_scorebug = False
        self.match_log = []
        self.passive_team = None
        self.passive_passes = None
        self.break_end = None
        self.home_goal_scorers = []
        self.away_goal_scorers = []
        self.last_scorer = None
        self.home_timeouts_taken = []
        self.away_timeouts_taken = []

    # ----- Shootout -----

    def start_shootout(self, starting_team: str = "home"):
        self.shootout_active = True
        self.shootout_starting_team = starting_team if starting_team in ("home", "away") else "home"
        self.shootout_confirmed_winner = None
        self.home_shootout = []
        self.away_shootout = []

    def stop_shootout(self):
        self.shootout_active = False

    def add_shootout_attempt(self, is_home: bool, success: bool):
        if self.shootout_confirmed_winner:
            return  # result confirmed: input locked until un-confirm
        if is_home:
            self.home_shootout.append(success)
        else:
            self.away_shootout.append(success)
        self.log_event("7m", side="home" if is_home else "away",
                       detail="goal" if success else "miss")

    def undo_shootout(self, is_home: bool):
        if self.shootout_confirmed_winner:
            return  # undo requires un-confirm first
        if is_home and self.home_shootout:
            self.home_shootout.pop()
        if not is_home and self.away_shootout:
            self.away_shootout.pop()

    # ----- Shootout protocol (IHF 2:2 Comment) -----

    def suggested_shootout_winner(self) -> str | None:
        """Winner forced by the rules, computed (never declared) — #15.

        A goal difference counts only after BOTH teams had the same number
        of throws: not before each has thrown five in the first phase, and
        in continuation rounds at any equal count >= 6.
        """
        if not self.shootout_active or self.shootout_confirmed_winner:
            return None
        nh, na = len(self.home_shootout), len(self.away_shootout)
        if nh == na and nh >= 5:
            gh, ga = sum(self.home_shootout), sum(self.away_shootout)
            if gh > ga:
                return "home"
            if ga > gh:
                return "away"
        return None

    def next_shootout_team(self) -> str | None:
        """Expected next thrower (warning-only hint; alternation assumed)."""
        if not self.shootout_active or self.shootout_confirmed_winner:
            return None
        total = len(self.home_shootout) + len(self.away_shootout)
        if total % 2 == 0:
            return self.shootout_starting_team
        return "away" if self.shootout_starting_team == "home" else "home"

    def confirm_shootout_winner(self, team: str | None) -> None:
        """Operator confirms a rule-forced suggestion — the only path to a
        declared winner."""
        if self.suggested_shootout_winner() == team:
            self.shootout_confirmed_winner = team

    def unconfirm_shootout_winner(self) -> None:
        self.shootout_confirmed_winner = None

    def side_change(self):
        tmp_team = self.home_team
        tmp_color = self.home_color
        tmp_score = self.home_score

        self.home_team = self.away_team
        self.home_color = self.away_color
        self.home_score = self.away_score

        self.away_team = tmp_team
        self.away_color = tmp_color
        self.away_score = tmp_score

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
            "home_suspension_counts": self.home_suspension_counts,
            "away_suspension_counts": self.away_suspension_counts,
            "home_disqualified": self.home_disqualified,
            "away_disqualified": self.away_disqualified,
            # On-court players: 7 minus players currently serving suspensions
            "home_players_on_court": max(0, 7 - len(self.home_suspensions)),
            "away_players_on_court": max(0, 7 - len(self.away_suspensions)),
            "home_cards": [s.to_dict() for s in self.home_cards],
            "away_cards": [s.to_dict() for s in self.away_cards],
            "home_timeout_active": self.home_timeout_end is not None,
            "away_timeout_active": self.away_timeout_end is not None,
            "home_timeout_remaining": max(0, int(self.home_timeout_end - time.time())) if self.home_timeout_end else 0,
            "away_timeout_remaining": max(0, int(self.away_timeout_end - time.time())) if self.away_timeout_end else 0,
            "technical_timeout_active": self.technical_timeout_end is not None,
            "technical_timeout_remaining": max(0, int(self.technical_timeout_end - time.time())) if self.technical_timeout_end else 0,
            "hide_scorebug": self.hide_scorebug,
            "auto_stop_on_suspension": self.auto_stop_on_suspension,
            "at_period_cap": self.elapsed_seconds >= self.period_definitions()[self.period_index][1],
            "match_type": self.match_type,
            "half_minutes": self.half_minutes,
            "overtime_enabled": self.overtime_enabled,
            "period_names": [d[0] for d in self.period_definitions()],
            "shootout_active": self.shootout_active,
            "home_shootout": self.home_shootout,
            "away_shootout": self.away_shootout,
            "shootout_starting_team": self.shootout_starting_team,
            "shootout_suggested_winner": self.suggested_shootout_winner(),
            "shootout_confirmed_winner": self.shootout_confirmed_winner,
            "shootout_next_team": self.next_shootout_team(),
            "match_log": self.match_log,
            "break_active": self.break_end is not None,
            "break_remaining": max(0, int(self.break_end - time.time())) if self.break_end else 0,
            "passive_team": self.passive_team,
            "passive_passes": self.passive_passes,
            "passive_expired": self.passive_team is not None and self.passive_passes == 0,
            "home_goal_scorers": self.home_goal_scorers,
            "away_goal_scorers": self.away_goal_scorers,
            "last_scorer": self.last_scorer,
            "home_timeouts": self._timeout_quota(self.home_timeouts_taken),
            "away_timeouts": self._timeout_quota(self.away_timeouts_taken),
        }
