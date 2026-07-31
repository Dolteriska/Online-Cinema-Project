"""
Unit / validation tests for Pydantic request schemas — these run the same
validators as the API layer but without going through HTTP, to pin down the
exact business rules (email format + password strength) in isolation.
"""
import pytest
from pydantic import ValidationError

from src.schemas.users_schema import (
    UserRegistrationRequestSchema,
    UserLoginRequestSchema,
    PasswordResetConfirmRequestSchema,
)

pytestmark = pytest.mark.unit


class TestUserRegistrationRequestSchema:
    def test_accepts_valid_email_and_strong_password(self):
        schema = UserRegistrationRequestSchema(
            email="user@example.com", password="StrongPass1!"
        )
        assert schema.email == "user@example.com"

    def test_rejects_invalid_email_format(self):
        with pytest.raises(ValidationError):
            UserRegistrationRequestSchema(email="not-an-email", password="StrongPass1!")

    def test_rejects_weak_password(self):
        with pytest.raises(ValidationError):
            UserRegistrationRequestSchema(email="user@example.com", password="weak")

    @pytest.mark.parametrize(
        "password",
        [
            "short1!",       # < 8 chars
            "alllowercase1!",  # no uppercase
            "ALLUPPERCASE1!",  # no lowercase
            "NoDigitsHere!",  # no digit
            "NoSpecialChar1",  # no special char
        ],
    )
    def test_rejects_each_password_rule_violation(self, password):
        with pytest.raises(ValidationError):
            UserRegistrationRequestSchema(email="user@example.com", password=password)


class TestUserLoginRequestSchema:
    def test_login_schema_also_enforces_password_strength(self):
        # Login uses the same base schema, so the same rules apply.
        with pytest.raises(ValidationError):
            UserLoginRequestSchema(email="user@example.com", password="weak")


class TestPasswordResetConfirmRequestSchema:
    def test_accepts_strong_new_password(self):
        schema = PasswordResetConfirmRequestSchema(
            token="sometoken", new_password="StrongPass1!"
        )
        assert schema.new_password == "StrongPass1!"

    def test_rejects_weak_new_password(self):
        with pytest.raises(ValidationError):
            PasswordResetConfirmRequestSchema(token="sometoken", new_password="weak")
