"""
Unit tests: data-validation logic.

Covers src.database.validators.users (validate_password_strength, validate_email)
in complete isolation — no DB, no HTTP, no app import required beyond the
pure functions themselves.
"""
import pytest

from src.database.validators.users import (
    validate_password_strength,
    validate_email,
)

pytestmark = pytest.mark.unit


class TestValidatePasswordStrength:
    def test_valid_password_is_returned_unchanged(self):
        password = "StrongPass1!"
        assert validate_password_strength(password) == password

    def test_rejects_password_shorter_than_8_chars(self):
        with pytest.raises(ValueError, match="at least 8 characters"):
            validate_password_strength("Sh0rt!")

    def test_rejects_password_without_uppercase(self):
        with pytest.raises(ValueError, match="uppercase letter"):
            validate_password_strength("weakpass1!")

    def test_rejects_password_without_lowercase(self):
        with pytest.raises(ValueError, match="lower letter"):
            validate_password_strength("WEAKPASS1!")

    def test_rejects_password_without_digit(self):
        with pytest.raises(ValueError, match="one digit"):
            validate_password_strength("WeakPassword!")

    def test_rejects_password_without_special_character(self):
        with pytest.raises(ValueError, match="special character"):
            validate_password_strength("WeakPass123")

    @pytest.mark.parametrize("special_char", list("@$!%*?&#"))
    def test_accepts_every_documented_special_character(self, special_char):
        password = f"WeakPass1{special_char}"
        assert validate_password_strength(password) == password

    def test_errors_are_reported_in_priority_order(self):
        # too short AND missing everything else -> length error wins first
        with pytest.raises(ValueError, match="at least 8 characters"):
            validate_password_strength("a")


class TestValidateEmail:
    def test_valid_email_is_normalized_and_returned(self):
        assert validate_email("user@example.com") == "user@example.com"

    def test_rejects_email_without_at_symbol(self):
        with pytest.raises(ValueError):
            validate_email("not-an-email")

    def test_rejects_email_with_missing_domain(self):
        with pytest.raises(ValueError):
            validate_email("user@")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError):
            validate_email("")
