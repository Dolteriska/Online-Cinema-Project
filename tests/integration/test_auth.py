"""
Integration tests: auth API endpoints + database interaction + JWT workflow.

Covers registration, activation, login, refresh, logout, password reset, and
change-password — including error handling for invalid input.
"""
import pytest
from sqlalchemy import select

from src.database.models.users import (
    UserModel,
    ActivationTokenModel,
    RefreshTokenModel,
    PasswordResetTokenModel,
)
from tests.factories import create_user

pytestmark = [pytest.mark.functional, pytest.mark.asyncio(loop_scope="session")]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
class TestRegister:
    async def test_register_creates_inactive_user_and_activation_token(
        self, client, db_session
    ):
        response = await client.post(
            "/api/v1/accounts/register/",
            json={"email": "newuser@example.com", "password": "StrongPass1!"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "newuser@example.com"
        assert "id" in body

        result = await db_session.execute(
            select(UserModel).where(UserModel.email == "newuser@example.com")
        )
        user = result.scalars().one()
        assert user.is_active is False

        token_result = await db_session.execute(
            select(ActivationTokenModel).where(
                ActivationTokenModel.user_id == user.id
            )
        )
        assert token_result.scalars().first() is not None

    async def test_register_rejects_duplicate_email(self, client, db_session):
        await create_user(db_session, email="dup@example.com")

        response = await client.post(
            "/api/v1/accounts/register/",
            json={"email": "dup@example.com", "password": "StrongPass1!"},
        )

        assert response.status_code == 409

    async def test_register_rejects_invalid_email(self, client):
        response = await client.post(
            "/api/v1/accounts/register/",
            json={"email": "not-an-email", "password": "StrongPass1!"},
        )
        assert response.status_code == 422

    async def test_register_rejects_weak_password(self, client):
        response = await client.post(
            "/api/v1/accounts/register/",
            json={"email": "weakpass@example.com", "password": "weak"},
        )
        assert response.status_code == 422

    async def test_register_rejects_missing_fields(self, client):
        response = await client.post("/api/v1/accounts/register/", json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------
class TestActivate:
    async def test_activate_with_valid_token_activates_user(self, client, db_session):
        user = await create_user(
            db_session, email="toactivate@example.com", is_active=False
        )
        token = ActivationTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()
        await db_session.refresh(token)

        response = await client.post(
            "/api/v1/accounts/activate/",
            json={"email": user.email, "token": token.token},
        )

        assert response.status_code == 200
        await db_session.refresh(user)
        assert user.is_active is True

    async def test_activate_with_invalid_token_returns_400(self, client, db_session):
        user = await create_user(
            db_session, email="badtoken@example.com", is_active=False
        )

        response = await client.post(
            "/api/v1/accounts/activate/",
            json={"email": user.email, "token": "does-not-exist"},
        )

        assert response.status_code == 400

    async def test_activate_already_active_user_returns_400(self, client, db_session):
        user = await create_user(
            db_session, email="alreadyactive@example.com", is_active=True
        )
        token = ActivationTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()
        await db_session.refresh(token)

        response = await client.post(
            "/api/v1/accounts/activate/",
            json={"email": user.email, "token": token.token},
        )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class TestLogin:
    async def test_login_with_correct_credentials_returns_tokens(
        self, client, db_session
    ):
        await create_user(
            db_session,
            email="login@example.com",
            password="StrongPass1!",
            is_active=True,
        )

        response = await client.post(
            "/api/v1/accounts/login/",
            json={"email": "login@example.com", "password": "StrongPass1!"},
        )

        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    async def test_login_persists_refresh_token_in_db(self, client, db_session):
        await create_user(
            db_session,
            email="persist@example.com",
            password="StrongPass1!",
            is_active=True,
        )
        response = await client.post(
            "/api/v1/accounts/login/",
            json={"email": "persist@example.com", "password": "StrongPass1!"},
        )
        refresh_token = response.json()["refresh_token"]

        result = await db_session.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.token == refresh_token
            )
        )
        assert result.scalars().first() is not None

    async def test_login_with_wrong_password_returns_401(self, client, db_session):
        await create_user(
            db_session,
            email="wrongpass@example.com",
            password="StrongPass1!",
            is_active=True,
        )

        response = await client.post(
            "/api/v1/accounts/login/",
            json={"email": "wrongpass@example.com", "password": "WrongPass1!"},
        )

        assert response.status_code == 401

    async def test_login_with_unknown_email_returns_401(self, client):
        response = await client.post(
            "/api/v1/accounts/login/",
            json={"email": "ghost@example.com", "password": "StrongPass1!"},
        )
        assert response.status_code == 401

    async def test_login_with_inactive_account_returns_403(self, client, db_session):
        await create_user(
            db_session,
            email="inactive@example.com",
            password="StrongPass1!",
            is_active=False,
        )

        response = await client.post(
            "/api/v1/accounts/login/",
            json={"email": "inactive@example.com", "password": "StrongPass1!"},
        )

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------
class TestRefreshToken:
    async def test_refresh_with_valid_token_returns_new_access_token(
        self, client, db_session
    ):
        await create_user(
            db_session,
            email="refresh@example.com",
            password="StrongPass1!",
            is_active=True,
        )
        login_response = await client.post(
            "/api/v1/accounts/login/",
            json={"email": "refresh@example.com", "password": "StrongPass1!"},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = await client.post(
            "/api/v1/accounts/refresh/", json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_refresh_with_garbage_token_returns_400(self, client):
        response = await client.post(
            "/api/v1/accounts/refresh/", json={"refresh_token": "not-a-jwt"}
        )
        assert response.status_code == 400

    async def test_refresh_with_unknown_but_well_formed_token_returns_401(
        self, client, jwt_manager
    ):
        # Well-formed JWT, valid signature, but never stored in DB
        fake_token = jwt_manager.create_refresh_token({"user_id": 999})
        response = await client.post(
            "/api/v1/accounts/refresh/", json={"refresh_token": fake_token}
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
class TestLogout:
    async def test_logout_deletes_refresh_token(self, client, db_session):
        await create_user(
            db_session,
            email="logout@example.com",
            password="StrongPass1!",
            is_active=True,
        )
        login_response = await client.post(
            "/api/v1/accounts/login/",
            json={"email": "logout@example.com", "password": "StrongPass1!"},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = await client.post(
            "/api/v1/accounts/logout/", json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        result = await db_session.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.token == refresh_token
            )
        )
        assert result.scalars().first() is None

    async def test_logout_with_unknown_token_returns_400(self, client):
        response = await client.post(
            "/api/v1/accounts/logout/", json={"refresh_token": "unknown-token"}
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------
class TestPasswordReset:
    async def test_password_reset_request_creates_token_for_active_user(
        self, client, db_session
    ):
        user = await create_user(
            db_session, email="reset@example.com", is_active=True
        )

        response = await client.post(
            "/api/v1/accounts/password-reset/request/",
            json={"email": user.email},
        )

        assert response.status_code == 200
        result = await db_session.execute(
            select(PasswordResetTokenModel).where(
                PasswordResetTokenModel.user_id == user.id
            )
        )
        assert result.scalars().first() is not None

    async def test_password_reset_request_for_unknown_email_does_not_leak(
        self, client
    ):
        # Should return 200 with a generic message, not reveal whether the
        # email exists in the system.
        response = await client.post(
            "/api/v1/accounts/password-reset/request/",
            json={"email": "ghost@example.com"},
        )
        assert response.status_code == 200

    async def test_password_reset_confirm_changes_password(self, client, db_session):
        user = await create_user(
            db_session,
            email="confirmreset@example.com",
            password="OldPass1!",
            is_active=True,
        )
        token = PasswordResetTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()
        await db_session.refresh(token)

        response = await client.post(
            "/api/v1/accounts/password-reset/confirm/",
            json={"token": token.token, "new_password": "NewPass1!"},
        )
        assert response.status_code == 200

        # Old password no longer works, new one does.
        login_old = await client.post(
            "/api/v1/accounts/login/",
            json={"email": user.email, "password": "OldPass1!"},
        )
        assert login_old.status_code == 401

        login_new = await client.post(
            "/api/v1/accounts/login/",
            json={"email": user.email, "password": "NewPass1!"},
        )
        assert login_new.status_code == 200

    async def test_password_reset_confirm_with_invalid_token_returns_400(
        self, client
    ):
        response = await client.post(
            "/api/v1/accounts/password-reset/confirm/",
            json={"token": "does-not-exist", "new_password": "NewPass1!"},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Change password (authenticated)
# ---------------------------------------------------------------------------
class TestChangePassword:
    async def test_change_password_with_correct_old_password_succeeds(
        self, client, db_session, make_auth_headers
    ):
        user = await create_user(
            db_session,
            email="changepw@example.com",
            password="OldPass1!",
            is_active=True,
        )

        response = await client.post(
            "/api/v1/accounts/change-password/",
            json={"old_password": "OldPass1!", "new_password": "NewPass1!"},
            headers=make_auth_headers(user.id),
        )

        assert response.status_code == 200

    async def test_change_password_with_wrong_old_password_returns_400(
        self, client, db_session, make_auth_headers
    ):
        user = await create_user(
            db_session,
            email="changepwwrong@example.com",
            password="OldPass1!",
            is_active=True,
        )

        response = await client.post(
            "/api/v1/accounts/change-password/",
            json={"old_password": "WrongOld1!", "new_password": "NewPass1!"},
            headers=make_auth_headers(user.id),
        )

        assert response.status_code == 400

    async def test_change_password_without_auth_header_returns_403(self, client):
        response = await client.post(
            "/api/v1/accounts/change-password/",
            json={"old_password": "OldPass1!", "new_password": "NewPass1!"},
        )
        # No Authorization header at all -> HTTPBearer rejects with 401
        assert response.status_code == 401

    async def test_change_password_with_invalid_token_returns_401(self, client):
        response = await client.post(
            "/api/v1/accounts/change-password/",
            json={"old_password": "OldPass1!", "new_password": "NewPass1!"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Protected-endpoint / JWT workflow edge cases (business-rule validation)
# ---------------------------------------------------------------------------
class TestJWTProtectedAccess:
    async def test_inactive_user_is_forbidden_even_with_valid_token(
        self, client, db_session, make_auth_headers
    ):
        user = await create_user(
            db_session, email="deactivated@example.com", is_active=False
        )

        response = await client.post(
            "/api/v1/accounts/change-password/",
            json={"old_password": "StrongPass1!", "new_password": "NewPass1!"},
            headers=make_auth_headers(user.id),
        )

        assert response.status_code == 403

    async def test_token_for_nonexistent_user_returns_401(
        self, client, make_auth_headers
    ):
        response = await client.post(
            "/api/v1/accounts/change-password/",
            json={"old_password": "StrongPass1!", "new_password": "NewPass1!"},
            headers=make_auth_headers(999999),
        )
        assert response.status_code == 401
