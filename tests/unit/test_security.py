"""
Unit tests: security utilities.

Covers:
 - src.security.passwords (hash_password / verify_password)
 - src.security.token_manager.JWTAuthManager (create/decode access & refresh tokens)
 - src.security.utils.generate_secure_token

These are pure/self-contained: JWTAuthManager is instantiated directly with
throwaway secrets, so no dependency on the global `settings` object or the DB.
"""
from datetime import timedelta

import pytest
from jose import jwt

from src.security.passwords import hash_password, verify_password
from src.security.utils import generate_secure_token
from src.security.token_manager import JWTAuthManager
from src.exceptions.security import TokenExpiredError, InvalidTokenError

pytestmark = pytest.mark.unit


class TestPasswordHashing:
    def test_hash_password_does_not_return_the_plain_password(self):
        hashed = hash_password("StrongPass1!")
        assert hashed != "StrongPass1!"

    def test_verify_password_succeeds_for_correct_password(self):
        hashed = hash_password("StrongPass1!")
        assert verify_password("StrongPass1!", hashed) is True

    def test_verify_password_fails_for_incorrect_password(self):
        hashed = hash_password("StrongPass1!")
        assert verify_password("WrongPassword1!", hashed) is False

    def test_hashing_the_same_password_twice_yields_different_hashes(self):
        # bcrypt uses a random salt per call
        assert hash_password("StrongPass1!") != hash_password("StrongPass1!")


class TestGenerateSecureToken:
    def test_returns_a_string(self):
        assert isinstance(generate_secure_token(), str)

    def test_two_calls_produce_different_tokens(self):
        assert generate_secure_token() != generate_secure_token()

    def test_length_parameter_influences_token_length(self):
        short_token = generate_secure_token(length=4)
        long_token = generate_secure_token(length=64)
        assert len(long_token) > len(short_token)


@pytest.fixture
def manager():
    return JWTAuthManager(
        secret_key_access="access-secret",
        secret_key_refresh="refresh-secret",
        algorithm="HS256",
    )


class TestJWTAuthManager:
    def test_create_and_decode_access_token_roundtrip(self, manager):
        token = manager.create_access_token({"user_id": 42})
        payload = manager.decode_access_token(token)
        assert payload["user_id"] == 42

    def test_create_and_decode_refresh_token_roundtrip(self, manager):
        token = manager.create_refresh_token({"user_id": 7})
        payload = manager.decode_refresh_token(token)
        assert payload["user_id"] == 7

    def test_access_token_cannot_be_decoded_as_refresh_token(self, manager):
        token = manager.create_access_token({"user_id": 1})
        with pytest.raises(InvalidTokenError):
            manager.decode_refresh_token(token)

    def test_expired_access_token_raises_token_expired_error(self, manager):
        token = manager.create_access_token(
            {"user_id": 1}, expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(TokenExpiredError):
            manager.decode_access_token(token)

    def test_tampered_token_raises_invalid_token_error(self, manager):
        token = manager.create_access_token({"user_id": 1})
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(InvalidTokenError):
            manager.decode_access_token(tampered)

    def test_token_signed_with_wrong_secret_is_rejected(self, manager):
        foreign_token = jwt.encode(
            {"user_id": 1}, "some-other-secret", algorithm="HS256"
        )
        with pytest.raises(InvalidTokenError):
            manager.decode_access_token(foreign_token)

    def test_verify_access_token_or_raise_does_not_raise_for_valid_token(
        self, manager
    ):
        token = manager.create_access_token({"user_id": 1})
        manager.verify_access_token_or_raise(token)  # should not raise

    def test_verify_refresh_token_or_raise_raises_for_expired_token(self, manager):
        token = manager.create_refresh_token(
            {"user_id": 1}, expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(TokenExpiredError):
            manager.verify_refresh_token_or_raise(token)
