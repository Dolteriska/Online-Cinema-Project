"""
Functional tests: end-to-end user scenarios that stitch together several
endpoints the way a real client would, exactly as called out in the ТЗ:
"registration, login, movie filtering, and order placement".
"""
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.database.models.users import ActivationTokenModel, UserModel
from tests.factories import create_movie, create_genre, create_certification

pytestmark = [pytest.mark.functional, pytest.mark.asyncio(loop_scope="session")]


class TestFullUserJourney:
    async def test_register_activate_login_browse_cart_checkout_cancel(
        self, client, db_session
    ):
        # --- Arrange: seed a small catalogue ---
        action = await create_genre(db_session, "Action")
        cert = await create_certification(db_session, "PG-13")
        movie = await create_movie(
            db_session,
            name="The Great Adventure",
            year=2023,
            imdb=8.2,
            price="12.99",
            certification=cert,
            genres=[action],
        )
        await create_movie(
            db_session,
            name="Boring Documentary",
            year=2010,
            imdb=5.0,
            price="3.99",
        )

        # --- 1. Register ---
        register_response = await client.post(
            "/api/v1/accounts/register/",
            json={"email": "journey@example.com", "password": "JourneyPass1!"},
        )
        assert register_response.status_code == 200

        # --- 2. Activate the account using the token created in the DB ---
        result = await db_session.execute(
            select(UserModel).where(UserModel.email == "journey@example.com")
        )
        user = result.scalars().one()
        token_result = await db_session.execute(
            select(ActivationTokenModel).where(
                ActivationTokenModel.user_id == user.id
            )
        )
        activation_token = token_result.scalars().one()

        activate_response = await client.get(
            "/api/v1/accounts/activate/",
            params={"token": activation_token.token},
        )
        assert activate_response.status_code == 200

        # --- 3. Login ---
        login_response = await client.post(
            "/api/v1/accounts/login/",
            json={"email": "journey@example.com", "password": "JourneyPass1!"},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # --- 4. Browse / filter movies ---
        catalogue_response = await client.get(
            "/api/v1/theater/movies/",
            params={"min_imdb": 7, "genre_ids": [action.id]},
        )
        assert catalogue_response.status_code == 200
        catalogue = catalogue_response.json()
        assert catalogue["total"] == 1
        assert catalogue["items"][0]["name"] == "The Great Adventure"

        # --- 5. Add the chosen movie to cart ---
        add_to_cart_response = await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=auth_headers,
        )
        assert add_to_cart_response.status_code == 201

        cart_response = await client.get(
            "/api/v1/theater/cart/items/", headers=auth_headers
        )
        assert len(cart_response.json()["movies"]) == 1

        # --- 6. Checkout / place order ---
        checkout_response = await client.post(
            "/api/v1/orders/checkout/", headers=auth_headers
        )
        assert checkout_response.status_code == 201
        order = checkout_response.json()
        assert order["status"] == "pending"
        assert Decimal(str(order["total_amount"])) == Decimal("12.99")

        # --- 7. Cart is now empty, order shows up in order history ---
        empty_cart_response = await client.get(
            "/api/v1/theater/cart/items/", headers=auth_headers
        )
        assert empty_cart_response.json()["movies"] == []

        orders_response = await client.get(
            "/api/v1/orders/", headers=auth_headers
        )
        assert orders_response.json()["total"] == 1

        # --- 8. User changes their mind and cancels the order ---
        cancel_response = await client.patch(
            f"/api/v1/orders/{order['id']}/cancel/", headers=auth_headers
        )
        assert cancel_response.status_code == 200

        final_orders_response = await client.get(
            "/api/v1/orders/", headers=auth_headers
        )
        assert final_orders_response.json()["items"][0]["status"] == "canceled"

        # --- 9. Logout ---
        logout_response = await client.post(
            "/api/v1/accounts/logout/",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert logout_response.status_code == 200

    async def test_cannot_login_before_activation(self, client, db_session):
        await client.post(
            "/api/v1/accounts/register/",
            json={"email": "notyetactive@example.com", "password": "JourneyPass1!"},
        )

        login_response = await client.post(
            "/api/v1/accounts/login/",
            json={
                "email": "notyetactive@example.com",
                "password": "JourneyPass1!",
            },
        )
        assert login_response.status_code == 403

    async def test_password_reset_journey(self, client, db_session):
        # Register + activate directly through the API for a realistic flow.
        await client.post(
            "/api/v1/accounts/register/",
            json={"email": "forgetful@example.com", "password": "OldJourney1!"},
        )
        result = await db_session.execute(
            select(UserModel).where(UserModel.email == "forgetful@example.com")
        )
        user = result.scalars().one()
        token_result = await db_session.execute(
            select(ActivationTokenModel).where(
                ActivationTokenModel.user_id == user.id
            )
        )
        activation_token = token_result.scalars().one()
        await client.post(
            "/api/v1/accounts/activate/",
            json={"email": user.email, "token": activation_token.token},
        )

        # User forgot their password -> requests a reset link.
        reset_request_response = await client.post(
            "/api/v1/accounts/password-reset/request/",
            json={"email": user.email},
        )
        assert reset_request_response.status_code == 200

        from src.database.models.users import PasswordResetTokenModel

        reset_token_result = await db_session.execute(
            select(PasswordResetTokenModel).where(
                PasswordResetTokenModel.user_id == user.id
            )
        )
        reset_token = reset_token_result.scalars().one()

        confirm_response = await client.post(
            "/api/v1/accounts/password-reset/confirm/",
            json={"token": reset_token.token, "new_password": "NewJourney1!"},
        )
        assert confirm_response.status_code == 200

        # Old password rejected, new password logs in successfully.
        old_login = await client.post(
            "/api/v1/accounts/login/",
            json={"email": user.email, "password": "OldJourney1!"},
        )
        assert old_login.status_code == 401

        new_login = await client.post(
            "/api/v1/accounts/login/",
            json={"email": user.email, "password": "NewJourney1!"},
        )
        assert new_login.status_code == 200
