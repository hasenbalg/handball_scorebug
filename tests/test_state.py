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


class ShootoutProtocolTest(unittest.TestCase):
    """Winner may only be forced after equal throw counts (IHF 2:2 Comment)."""

    def seq(self, s, home, away):
        for outcome in home:
            s.add_shootout_attempt(True, outcome)
        for outcome in away:
            s.add_shootout_attempt(False, outcome)

    def setUp(self):
        self.s = ScoreboardState()
        self.s.start_shootout()

    def test_no_winner_before_both_threw_five(self):
        # difference exists but away still has throws left in the first phase
        self.seq(self.s, [True, True, True, True, True],
                        [True, True, False, False])
        self.assertIsNone(self.s.suggested_shootout_winner())  # 5 vs 4
        self.s.add_shootout_attempt(False, False)
        self.assertEqual(self.s.suggested_shootout_winner(), "home")  # 5/5, 4–2

    def test_no_winner_on_early_equal_difference(self):
        self.seq(self.s, [True, True, True, True], [True, True, False, False])
        self.assertIsNone(self.s.suggested_shootout_winner())  # 3–2 at 4/4

    def test_tie_continues_then_decides_at_equal_count(self):
        self.seq(self.s, [True, True, True, False, False],
                        [True, True, True, False, False])
        self.assertIsNone(self.s.suggested_shootout_winner())  # 3–3 at 5/5
        self.s.add_shootout_attempt(True, True)   # 4–3, away still to throw
        self.assertIsNone(self.s.suggested_shootout_winner())
        self.s.add_shootout_attempt(False, False)  # 4–3 at 6/6
        self.assertEqual(self.s.suggested_shootout_winner(), "home")

    def test_confirm_requires_matching_suggestion_then_locks(self):
        self.seq(self.s, [True, True, True, True, True],
                        [True, True, False, False, False])
        self.s.confirm_shootout_winner("away")  # wrong: no-op
        self.assertIsNone(self.s.shootout_confirmed_winner)
        self.s.confirm_shootout_winner("home")
        self.assertEqual(self.s.shootout_confirmed_winner, "home")

        n_home = len(self.s.home_shootout)
        self.s.add_shootout_attempt(True, True)   # locked
        self.s.undo_shootout(True)                # locked
        self.assertEqual(len(self.s.home_shootout), n_home)

        self.s.unconfirm_shootout_winner()
        self.s.undo_shootout(True)                # unlocked
        self.assertEqual(len(self.s.home_shootout), n_home - 1)

    def test_next_team_alternates_by_starting_team(self):
        s = ScoreboardState()
        s.start_shootout(starting_team="away")
        self.assertEqual(s.next_shootout_team(), "away")
        s.add_shootout_attempt(False, True)
        self.assertEqual(s.next_shootout_team(), "home")
        s.add_shootout_attempt(True, True)
        self.assertEqual(s.next_shootout_team(), "away")

    def test_start_shootout_resets_previous_result(self):
        self.seq(self.s, [True] * 5, [False] * 5)
        self.s.confirm_shootout_winner("home")
        self.s.start_shootout("away")
        self.assertIsNone(self.s.shootout_confirmed_winner)
        self.assertEqual(self.s.home_shootout, [])
        self.assertEqual(self.s.shootout_starting_team, "away")

    def test_public_dict_exposes_protocol_fields(self):
        self.seq(self.s, [True] * 5, [False] * 5)
        d = self.s.to_public_dict()
        self.assertEqual(d["shootout_suggested_winner"], "home")
        self.assertIsNone(d["shootout_confirmed_winner"])
        self.assertEqual(d["shootout_next_team"], "home")  # 10 throws: first team again


class PunishmentProgressionTest(unittest.TestCase):
    """16:5/16:6d: the third suspension of a player is a disqualification."""

    def setUp(self):
        self.s = ScoreboardState()

    def test_counts_accumulate_and_dq_on_third(self):
        self.s.add_suspension_home("7")
        self.s.add_suspension_home("#7")   # same player, normalized
        self.s.add_suspension_home("7")
        self.assertEqual(self.s.home_suspension_counts["7"], 3)
        self.assertEqual(self.s.home_disqualified, ["7"])
        self.assertNotIn("11", self.s.away_disqualified)

    def test_counts_survive_suspension_expiry(self):
        self.s.add_suspension_home("9")
        self.s.home_suspensions[0].remaining = 0
        self.s.cleanup_suspensions()
        self.assertEqual(self.s.home_suspensions, [])
        self.assertEqual(self.s.home_suspension_counts["9"], 1)  # kept!

    def test_undo_rolls_back_progression(self):
        for _ in range(3):
            self.s.add_suspension_home("7")
            self.s.delete_suspension_home(0)  # operator undoes each
        self.assertEqual(self.s.home_suspension_counts["7"], 0)
        self.assertEqual(self.s.home_disqualified, [])

    def test_two_players_third_suspension_each(self):
        for p in ("7", "11"):
            for _ in range(3):
                self.s.add_suspension_away(p)
        self.assertEqual(self.s.away_disqualified, ["7", "11"])
        self.assertEqual(self.s.away_suspension_counts, {"7": 3, "11": 3})

    def test_players_on_court_reflects_active_suspensions(self):
        d = self.s.to_public_dict()
        self.assertEqual(d["home_players_on_court"], 7)
        self.s.add_suspension_home("7")
        self.s.add_suspension_home("11")
        d = self.s.to_public_dict()
        self.assertEqual(d["home_players_on_court"], 5)
        self.assertEqual(d["away_players_on_court"], 7)

    def test_reset_clears_progression(self):
        for _ in range(3):
            self.s.add_suspension_home("7")
        self.s.reset()
        self.assertEqual(self.s.home_suspension_counts, {})
        self.assertEqual(self.s.home_disqualified, [])

    def test_legacy_load_gets_progression_defaults(self):
        blob = json.dumps({"home_suspensions": [
            {"player": "#4", "start_time": time.time(), "duration": 120},
        ]})

        class FakeRedis:
            def get(self, key):
                return blob

        original, state_mod.r = state_mod.r, FakeRedis()
        try:
            s = ScoreboardState.load()
        finally:
            state_mod.r = original
        self.assertEqual(s.home_suspensions[0].player, "4")
        self.assertEqual(s.home_suspension_counts, {})
        self.assertEqual(s.home_disqualified, [])


class ClockRulesTest(unittest.TestCase):
    """2:8 mandatory time-outs: whistle stop/resume, suspension announcement."""

    def test_whistle_stops_running_clock_and_resumes(self):
        s = ScoreboardState()
        s.start_timer()
        s.referee_whistle()
        self.assertFalse(s.running)
        s.referee_whistle()
        self.assertTrue(s.running)

    def test_suspension_announcement_stops_clock_by_default(self):
        s = ScoreboardState()
        s.start_timer()
        s.add_suspension_home("7")
        self.assertFalse(s.running)

    def test_auto_stop_can_be_disabled(self):
        s = ScoreboardState()
        s.auto_stop_on_suspension = False
        s.start_timer()
        s.add_suspension_away("11")
        self.assertTrue(s.running)

    def test_public_dict_exposes_clock_rule_fields(self):
        s = ScoreboardState()
        d = s.to_public_dict()
        self.assertTrue(d["auto_stop_on_suspension"])
        self.assertFalse(d["at_period_cap"])
        s.set_time("30:00")
        self.assertTrue(s.to_public_dict()["at_period_cap"])

    def test_legacy_blobs_default_auto_stop_on(self):
        class FakeRedis:
            def get(self, key):
                return json.dumps({"home_score": 3})

        original, state_mod.r = state_mod.r, FakeRedis()
        try:
            s = ScoreboardState.load()
        finally:
            state_mod.r = original
        self.assertTrue(s.auto_stop_on_suspension)


class MatchConfigurationTest(unittest.TestCase):
    """#10: halves length (2:1), overtime structure (2:2), end swaps (R10 Comm)."""

    def test_default_definitions_match_legacy_periods(self):
        defs = ScoreboardState().period_definitions()
        self.assertEqual([d[0] for d in defs], ["1st Half", "2nd Half", "60 Min"])
        self.assertEqual([d[1] for d in defs], [1800, 1800, 3600])
        self.assertEqual([d[2] for d in defs], [False, True, False])

    def test_youth_half_length_sets_caps(self):
        s = ScoreboardState()
        s.set_match_configuration(half_minutes=25)
        self.assertEqual([d[1] for d in s.period_definitions()][:2], [1500, 1500])
        # clock stops at the shortened cap
        s.elapsed_seconds = 1495
        s.running = True
        s.start_time = time.time() - 10
        import types as _types
        stub = _types.ModuleType("app")
        setattr(stub, "socketio", _types.SimpleNamespace(emit=lambda *_: None))
        original, sys.modules["app"] = sys.modules.get("app"), stub
        try:
            s.update_time()
        finally:
            if original is None:
                del sys.modules["app"]
            else:
                sys.modules["app"] = original
        self.assertEqual(s.elapsed_seconds, 25 * 60)
        self.assertFalse(s.running)

    def test_invalid_values_rejected(self):
        s = ScoreboardState()
        s.set_match_configuration(match_type="world-cup", half_minutes=17,
                                  overtime_enabled=None)
        self.assertEqual(s.match_type, "league")
        self.assertEqual(s.half_minutes, 30)

    def test_overtime_definitions_and_swap_flags(self):
        s = ScoreboardState()
        s.set_match_configuration(overtime_enabled=True)
        defs = s.period_definitions()
        self.assertEqual([d[0] for d in defs], [
            "1st Half", "2nd Half",
            "OT1 1st Half", "OT1 2nd Half",
            "OT2 1st Half", "OT2 2nd Half", "60 Min"])
        self.assertEqual([d[1] for d in defs], [1800, 1800, 300, 300, 300, 300, 3600])
        # swap only at half-time of regular time and of each OT period
        self.assertEqual([d[2] for d in defs],
                         [False, True, False, True, False, True, False])

    def test_next_period_swaps_only_where_required(self):
        s = ScoreboardState(home_team="A", away_team="B")
        s.set_match_configuration(overtime_enabled=True)
        s.next_period()                     # HT: swap
        self.assertEqual((s.home_team, s.away_team), ("B", "A"))
        s.next_period()                     # into OT1: coin toss, no swap
        self.assertEqual((s.home_team, s.away_team), ("B", "A"))
        s.next_period()                     # OT half-time: swap
        self.assertEqual((s.home_team, s.away_team), ("A", "B"))
        s.next_period()                     # into OT2: no swap
        self.assertEqual((s.home_team, s.away_team), ("A", "B"))

    def test_disabling_overtime_clamps_period_index(self):
        s = ScoreboardState()
        s.set_match_configuration(overtime_enabled=True)
        s.set_period_index(5)               # OT2 2nd Half
        s.set_match_configuration(overtime_enabled=False)
        s.set_period_index(s.period_index)  # what app.py does after config change
        self.assertEqual(s.period_index, 2)

    def test_config_survives_reset_and_loads_with_defaults(self):
        s = ScoreboardState()
        s.set_match_configuration(match_type="cup", half_minutes=20,
                                  overtime_enabled=True)
        s.reset()
        self.assertEqual((s.match_type, s.half_minutes, s.overtime_enabled),
                         ("cup", 20, True))
        d = s.to_public_dict()
        self.assertEqual(d["match_type"], "cup")
        self.assertEqual(len(d["period_names"]), 7)

        class FakeRedis:
            def get(self, key):
                return json.dumps({"home_score": 1})

        original, state_mod.r = state_mod.r, FakeRedis()
        try:
            s2 = ScoreboardState.load()
        finally:
            state_mod.r = original
        self.assertEqual((s2.match_type, s2.half_minutes, s2.overtime_enabled),
                         ("league", 30, False))


class TechnicalTimeoutTest(unittest.TestCase):
    """#6: neutral interruption (2:8c) — clock stops, 1-minute countdown."""

    def test_technical_timeout_stops_clock_and_counts_down(self):
        s = ScoreboardState()
        s.start_timer()
        s.start_technical_timeout()
        self.assertFalse(s.running)
        d = s.to_public_dict()
        self.assertTrue(d["technical_timeout_active"])
        self.assertIn(d["technical_timeout_remaining"], (59, 60))

    def test_technical_timeout_expires(self):
        s = ScoreboardState()
        s.start_technical_timeout()
        s.technical_timeout_end = time.time() - 1
        s.update_timeouts()
        self.assertIsNone(s.technical_timeout_end)
        self.assertFalse(s.to_public_dict()["technical_timeout_active"])

    def test_reset_clears_technical_timeout(self):
        s = ScoreboardState()
        s.start_technical_timeout()
        s.reset()
        self.assertIsNone(s.technical_timeout_end)

    def test_team_timeouts_unaffected(self):
        s = ScoreboardState()
        s.start_timeout_home()
        s.start_technical_timeout()
        d = s.to_public_dict()
        self.assertTrue(d["home_timeout_active"])
        self.assertTrue(d["technical_timeout_active"])


class MatchLogTest(unittest.TestCase):
    """#5: chronological event log, persisted with state."""

    def setUp(self):
        self.s = ScoreboardState()

    def test_events_are_logged_with_game_time(self):
        self.s.elapsed_seconds = 300
        self.s.log_event("goal", side="home")
        e = self.s.match_log[-1]
        self.assertEqual((e["type"], e["side"], e["clock"]), ("goal", "home", "05:00"))
        self.assertEqual(e["period"], "1st Half")

    def test_suspension_and_dq_logged(self):
        for _ in range(3):
            self.s.add_suspension_home("7")
        types = [(e["type"], e.get("player")) for e in self.s.match_log]
        self.assertEqual(types, [("suspension", "7")] * 3 + [("disqualification", "7")])

    def test_card_normalizes_color_and_logs(self):
        self.s.add_card_home("#3", color=None)
        e = self.s.match_log[-1]
        self.assertEqual((e["type"], e["detail"]), ("card", "yellow"))
        self.assertEqual(self.s.home_cards[0].color, "yellow")
        self.assertEqual(self.s.home_cards[0].player, "3")

    def test_period_changes_logged_only_on_change(self):
        self.s.next_period()
        self.assertEqual(self.s.match_log[-1]["type"], "period")
        self.s.match_log.clear()
        self.s.set_period_index(self.s.period_index)  # no-op clamp
        self.assertEqual(self.s.match_log, [])
        self.s.set_period_index(0)
        self.assertEqual(self.s.match_log[-1]["detail"], "1st Half")

    def test_shootout_and_technical_timeout_logged(self):
        self.s.add_shootout_attempt(True, False)
        self.s.start_technical_timeout()
        types = [(e["type"], e.get("side"), e.get("detail")) for e in self.s.match_log]
        self.assertEqual(types, [("7m", "home", "miss"), ("technical_timeout", None, None)])

    def test_delete_last(self):
        self.s.log_event("goal", side="home")
        self.s.log_event("goal", side="away")
        self.s.log_delete_last()
        self.assertEqual([e["side"] for e in self.s.match_log], ["home"])
        while self.s.match_log:
            self.s.log_delete_last()
        self.s.log_delete_last()  # empty is a no-op

    def test_reset_clears_log(self):
        self.s.log_event("goal", side="home")
        self.s.reset()
        self.assertEqual(self.s.match_log, [])

    def test_log_is_capped(self):
        for i in range(ScoreboardState.MAX_LOG_ENTRIES + 25):
            self.s.log_event("goal", side="home")
        self.assertEqual(len(self.s.match_log), ScoreboardState.MAX_LOG_ENTRIES)
        self.assertEqual(len(self.s.to_public_dict()["match_log"]),
                         ScoreboardState.MAX_LOG_ENTRIES)

    def test_legacy_blob_defaults_empty_log(self):
        blob = json.dumps({"home_score": 3, "away_score": 1})

        class FakeRedis:
            def get(self, key):
                return blob

        original, state_mod.r = state_mod.r, FakeRedis()
        try:
            s = ScoreboardState.load()
        finally:
            state_mod.r = original
        self.assertEqual(s.match_log, [])


class ScorerTest(unittest.TestCase):
    """#4: scorer number recorded per goal, brief overlay flash."""

    def setUp(self):
        self.s = ScoreboardState()

    def test_goal_records_scorer_and_logs(self):
        self.s.goal("home", "#23")
        self.s.goal("home", "23")
        self.s.goal("home")
        self.assertEqual(self.s.home_score, 3)
        self.assertEqual(self.s.home_goal_scorers, ["23", "23", None])
        goals = [e for e in self.s.match_log if e["type"] == "goal"]
        self.assertEqual([e["player"] for e in goals], ["23", "23", None])

    def test_last_scorer_exposed(self):
        self.s.goal("away", "7")
        ls = self.s.to_public_dict()["last_scorer"]
        self.assertEqual((ls["side"], ls["player"]), ("away", "7"))

    def test_undo_goal_pops_scorer_and_clears_flash(self):
        self.s.goal("home", "9")
        self.s.undo_goal("home")
        self.assertEqual(self.s.home_score, 0)
        self.assertEqual(self.s.home_goal_scorers, [])
        self.assertIsNone(self.s.to_public_dict()["last_scorer"])

    def test_undo_other_side_keeps_flash(self):
        self.s.goal("home", "9")
        self.s.undo_goal("away")  # nothing to undo away
        self.assertIsNotNone(self.s.last_scorer)  # home flash untouched

    def test_reset_clears_scorers(self):
        self.s.goal("home", "1")
        self.s.reset()
        self.assertEqual(self.s.home_goal_scorers, [])
        self.assertIsNone(self.s.last_scorer)


if __name__ == "__main__":
    unittest.main()
