import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from state import ScoreboardState  # noqa: E402


class TimeoutQuotaTest(unittest.TestCase):
    """#48: visual indicators for taken team time-outs, quota per 2:4
    Comment — 3 TOs per match, max 2 per half, none in overtime."""

    def setUp(self):
        self.s = ScoreboardState()

    def test_timeouts_record_period_slot(self):
        self.s.start_timeout_home()                      # 1st Half
        self.s.next_period()
        self.s.start_timeout_home()                      # 2nd Half
        self.s.start_timeout_home()                      # 2nd Half again
        self.assertEqual(self.s.home_timeouts_taken, ["half1", "half2", "half2"])
        q = self.s.to_public_dict()["home_timeouts"]
        self.assertEqual((q["total"], q["half1"], q["half2"]), (3, 1, 2))
        self.assertFalse(q["over_total"])
        self.assertFalse(q["over_half"])

    def test_over_quota_flags(self):
        for _ in range(3):
            self.s.start_timeout_home()
        self.s.start_timeout_home()  # 4th: allowed but flagged
        self.assertTrue(self.s._timeout_quota(self.s.home_timeouts_taken)["over_total"])

    def test_third_timeout_in_one_half_flags_half_quota(self):
        self.s.start_timeout_away()
        self.s.start_timeout_away()
        self.assertFalse(self.s._timeout_quota(self.s.away_timeouts_taken)["over_half"])
        self.s.start_timeout_away()
        self.assertTrue(self.s._timeout_quota(self.s.away_timeouts_taken)["over_half"])

    def test_ot_slot_and_flag(self):
        self.s.next_period()
        self.s.next_period()  # -> "60 Min" counts as overtime slot
        self.assertEqual(self.s._period_slot(), "ot")
        self.s.start_timeout_home()
        self.assertTrue(self.s._timeout_quota(self.s.home_timeouts_taken)["ot_used"])

    def test_public_dict_exposes_quota_view(self):
        self.s.start_timeout_away()
        q = self.s.to_public_dict()["away_timeouts"]
        self.assertEqual(
            q,
            {"total": 1, "max": 3, "half1": 1, "half2": 0, "ot": 0,
             "over_total": False, "over_half": False, "ot_used": False},
        )

    def test_reset_clears_taken(self):
        self.s.start_timeout_home()
        self.s.reset()
        self.assertEqual(self.s.home_timeouts_taken, [])


if __name__ == "__main__":
    unittest.main()
