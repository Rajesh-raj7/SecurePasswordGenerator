"""Tests for generator.py -- password, passphrase, PIN, and related generators."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator import PasswordGenerator, PasswordOptions, GeneratorError


class TestPasswordGeneration(unittest.TestCase):
    def setUp(self) -> None:
        self.gen = PasswordGenerator()

    def test_default_length(self) -> None:
        pw = self.gen.generate_password(PasswordOptions(length=16))
        self.assertEqual(len(pw), 16)

    def test_length_bounds(self) -> None:
        for length in (4, 32, 128):
            pw = self.gen.generate_password(PasswordOptions(length=length))
            self.assertEqual(len(pw), length)

    def test_length_too_short_raises(self) -> None:
        with self.assertRaises(GeneratorError):
            self.gen.generate_password(PasswordOptions(length=3))

    def test_length_too_long_raises(self) -> None:
        with self.assertRaises(GeneratorError):
            self.gen.generate_password(PasswordOptions(length=129))

    def test_no_character_type_selected_raises(self) -> None:
        with self.assertRaises(GeneratorError):
            self.gen.generate_password(PasswordOptions(
                length=8, use_upper=False, use_lower=False,
                use_digits=False, use_symbols=False,
            ))

    def test_only_lowercase(self) -> None:
        pw = self.gen.generate_password(PasswordOptions(
            length=20, use_upper=False, use_lower=True,
            use_digits=False, use_symbols=False,
        ))
        self.assertTrue(all(c.islower() for c in pw))

    def test_category_coverage_when_length_allows(self) -> None:
        pw = self.gen.generate_password(PasswordOptions(length=12))
        self.assertTrue(any(c.isupper() for c in pw))
        self.assertTrue(any(c.islower() for c in pw))
        self.assertTrue(any(c.isdigit() for c in pw))

    def test_exclude_similar_characters(self) -> None:
        for _ in range(20):
            pw = self.gen.generate_password(PasswordOptions(
                length=40, exclude_similar=True,
            ))
            for ch in "O0Il1":
                self.assertNotIn(ch, pw)

    def test_exclude_ambiguous_symbols(self) -> None:
        pw = self.gen.generate_password(PasswordOptions(
            length=40, exclude_ambiguous=True,
        ))
        for ch in "{}[]()/\\'\"`~,;:.<>|":
            self.assertNotIn(ch, pw)

    def test_no_repeat_characters(self) -> None:
        pw = self.gen.generate_password(PasswordOptions(length=10, no_repeat=True))
        self.assertEqual(len(pw), len(set(pw)))

    def test_no_repeat_too_long_raises(self) -> None:
        with self.assertRaises(GeneratorError):
            self.gen.generate_password(PasswordOptions(
                length=15, no_repeat=True,
                use_upper=False, use_lower=False, use_symbols=False,
                use_digits=True,  # only 10 unique digits available
            ))

    def test_generate_many_count(self) -> None:
        passwords = self.gen.generate_many(PasswordOptions(length=12, count=5))
        self.assertEqual(len(passwords), 5)
        self.assertEqual(len(set(passwords)), 5, "passwords should be unique")

    def test_generate_many_invalid_count_raises(self) -> None:
        with self.assertRaises(GeneratorError):
            self.gen.generate_many(PasswordOptions(length=12, count=0))
        with self.assertRaises(GeneratorError):
            self.gen.generate_many(PasswordOptions(length=12, count=21))

    def test_randomness_not_identical(self) -> None:
        pw1 = self.gen.generate_password(PasswordOptions(length=32))
        pw2 = self.gen.generate_password(PasswordOptions(length=32))
        self.assertNotEqual(pw1, pw2)


class TestPassphrase(unittest.TestCase):
    def setUp(self) -> None:
        self.gen = PasswordGenerator()

    def test_word_count(self) -> None:
        phrase = self.gen.generate_passphrase(word_count=5, include_number=False)
        self.assertEqual(len(phrase.split("-")), 5)

    def test_invalid_word_count_raises(self) -> None:
        with self.assertRaises(GeneratorError):
            self.gen.generate_passphrase(word_count=2)
        with self.assertRaises(GeneratorError):
            self.gen.generate_passphrase(word_count=11)


class TestPin(unittest.TestCase):
    def setUp(self) -> None:
        self.gen = PasswordGenerator()

    def test_pin_length_and_digits(self) -> None:
        pin = self.gen.generate_pin(length=6)
        self.assertEqual(len(pin), 6)
        self.assertTrue(pin.isdigit())

    def test_invalid_pin_length_raises(self) -> None:
        with self.assertRaises(GeneratorError):
            self.gen.generate_pin(length=2)
        with self.assertRaises(GeneratorError):
            self.gen.generate_pin(length=13)


class TestMiscGenerators(unittest.TestCase):
    def setUp(self) -> None:
        self.gen = PasswordGenerator()

    def test_username_format(self) -> None:
        username = self.gen.generate_username()
        self.assertRegex(username, r"^[A-Za-z]+[A-Za-z]+\d{3}$")

    def test_wifi_password_length(self) -> None:
        pw = self.gen.generate_wifi_password(length=20)
        self.assertEqual(len(pw), 20)

    def test_pronounceable_length(self) -> None:
        pw = self.gen.generate_pronounceable(length=10, trailing_number=False)
        self.assertEqual(len(pw), 10)


if __name__ == "__main__":
    unittest.main()
