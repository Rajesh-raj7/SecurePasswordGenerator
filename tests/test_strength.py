"""Tests for strength.py -- entropy calculation and strength rating."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from strength import analyze_password, calculate_entropy, rate_strength, estimate_crack_time


class TestEntropy(unittest.TestCase):
    def test_empty_password_zero_entropy(self) -> None:
        self.assertEqual(calculate_entropy(""), 0.0)

    def test_longer_password_has_more_entropy(self) -> None:
        short = calculate_entropy("Ab3!")
        long = calculate_entropy("Ab3!Ab3!Ab3!Ab3!")
        self.assertGreater(long, short)

    def test_more_character_classes_more_entropy(self) -> None:
        simple = calculate_entropy("aaaaaaaa")
        complex_ = calculate_entropy("aB3!cD4@")
        self.assertGreater(complex_, simple)


class TestRating(unittest.TestCase):
    def test_weak_rating(self) -> None:
        rating, score = rate_strength(10)
        self.assertEqual(rating, "Weak")

    def test_very_strong_rating(self) -> None:
        rating, score = rate_strength(100)
        self.assertEqual(rating, "Very Strong")
        self.assertGreaterEqual(score, 75)

    def test_score_monotonic_with_entropy(self) -> None:
        _, s1 = rate_strength(20)
        _, s2 = rate_strength(50)
        _, s3 = rate_strength(90)
        self.assertLess(s1, s2)
        self.assertLess(s2, s3)


class TestCrackTime(unittest.TestCase):
    def test_zero_entropy_instant(self) -> None:
        self.assertEqual(estimate_crack_time(0, 1e10), "instantly")

    def test_high_entropy_takes_long(self) -> None:
        result = estimate_crack_time(128, 1e10)
        self.assertNotEqual(result, "instantly")


class TestAnalyzePassword(unittest.TestCase):
    def test_full_analysis_shape(self) -> None:
        result = analyze_password("Tr0ub4dor&3")
        self.assertTrue(hasattr(result, "entropy_bits"))
        self.assertTrue(hasattr(result, "rating"))
        self.assertIn(result.rating, ("Weak", "Medium", "Strong", "Very Strong"))
        self.assertGreaterEqual(result.score_percent, 0)
        self.assertLessEqual(result.score_percent, 100)


if __name__ == "__main__":
    unittest.main()
