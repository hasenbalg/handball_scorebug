import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import state as state_mod  # noqa: E402
from state import ScoreboardState  # noqa: E402


class SuspensionGameClockTest(unittest.TestCase):
    """Suspensions must be served on the GAME clock (IHF 16:3 with 2:8)."""

    def test_suspension_advances_with_running_game_clock(self):
        s = ScoreboardState()
        s.add_suspension_home("7")  # 120s default
        s.running = True
        s.start_time = time.time() - 10
        s.update_time()
        self.assertEqual(s.elapsed_seconds, 10)
        self.assertEqual(s.home_suspensions[0].remaining, 110)

    def test_suspension_frozen_while_clock_stopped(self):
        s = ScoreboardState()
        s.add_suspension_home("7")
        s.running = True
        s.start_time = time.time() - 5
        s.update_time()
        s.stop_timer()

        # A minute of real time passes while the game clock is stopped
        # (ball out / time-out / half time) — served time must NOT advance.
        s.start_time = time.time() - 60
        s.update_time()
        self.assertEqual(s.home_suspensions[0].remaining, 115)
        self.assertEqual(s.elapsed_seconds, 5)

    def test_suspension_ticks_do_not_pass_period_cap(self):
        s = ScoreboardState()
        s.add_suspension_home("7")
        s.elapsed_seconds = 30 * 60 - 3  # period cap is 1800s
        s.running = True
        s.start_time = time.time() - 30

        # End-of-period emits "time_over" via the app module (pulls in
        # flask); stub it so this test needs no web deps.
        import types
        emitted = []
        stub = types.ModuleType("app")
        setattr(stub, "socketio", types.SimpleNamespace(emit=emitted.append))
        original, sys.modules["app"] = sys.modules.get("app"), stub
        try:
            s.update_time()
        finally:
            if original is None:
                del sys.modules["app"]
            else:
                sys.modules["app"] = original

        self.assertEqual(s.elapsed_seconds, 30 * 60)
        self.assertEqual(s.home_suspensions[0].remaining, 117)
        self.assertFalse(s.running)
        self.assertEqual(emitted, ["time_over"])

    def test_cleanup_drops_expired_suspensions(self):
        s = ScoreboardState()
        s.add_suspension_home("7")
        s.add_suspension_away("11")
        s.home_suspensions[0].remaining = 0
        s.cleanup_suspensions()
        self.assertEqual(s.home_suspensions, [])
        self.assertEqual(len(s.away_suspensions), 1)

    def test_legacy_wallclock_state_migrates_on_load(self):
        blob = json.dumps({
            "home_suspensions": [
                {"player": "9", "start_time": time.time() - 30, "duration": 120},
            ],
        })

        class FakeRedis:
            def get(self, key):
                return blob

        original, state_mod.r = state_mod.r, FakeRedis()
        try:
            s = ScoreboardState.load()
        finally:
            state_mod.r = original

        self.assertEqual(len(s.home_suspensions), 1)
        self.assertIn(s.home_suspensions[0].remaining, (89, 90, 91))


class ResetTest(unittest.TestCase):
    def test_reset_clears_shootout_and_visibility(self):
        s = ScoreboardState()
        s.start_shootout()
        s.add_shootout_attempt(True, True)
        s.add_shootout_attempt(False, False)
        s.hide_scorebug = True

        s.reset()

        self.assertFalse(s.shootout_active)
        self.assertEqual(s.home_shootout, [])
        self.assertEqual(s.away_shootout, [])
        self.assertFalse(s.hide_scorebug)

    def test_reset_still_clears_core_state(self):
        s = ScoreboardState()
        s.home_score = 21
        s.away_score = 20
        s.set_period_index(1)
        s.add_suspension_home("7")
        s.add_card_home("11", "yellow")

        s.reset()

        self.assertEqual(s.home_score, 0)
        self.assertEqual(s.away_score, 0)
        self.assertEqual(s.period_index, 0)
        self.assertEqual(s.elapsed_seconds, 0)
        self.assertFalse(s.running)
        self.assertEqual(s.home_suspensions, [])
        self.assertEqual(s.home_cards, [])


if __name__ == "__main__":
    unittest.main()
