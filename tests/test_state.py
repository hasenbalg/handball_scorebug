import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from state import ScoreboardState  # noqa: E402


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
