"""
Integration tests: shopping cart <-> order placement, exercising the
interaction between several endpoints and the database (cart -> checkout ->
order list -> cancel).
"""
from decimal import Decimal

import pytest
import pytest_asyncio

from src.database.models.movie_interactions import MoviePurchase
from tests.factories import create_user, create_movie

pytestmark = [pytest.mark.functional, pytest.mark.asyncio(loop_scope="session")]


@pytest_asyncio.fixture
async def logged_in_user(db_session, make_auth_headers):
    user = await create_user(db_session, email="cartuser@example.com")
    return user, make_auth_headers(user.id)


class TestShoppingCart:
    async def test_new_user_has_empty_cart(self, client, logged_in_user):
        _, headers = logged_in_user
        response = await client.get(
            "/api/v1/theater/cart/items/", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["movies"] == []

    async def test_add_movie_to_cart(self, client, db_session, logged_in_user):
        _, headers = logged_in_user
        movie = await create_movie(db_session, name="Cart Movie")

        response = await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )
        assert response.status_code == 201

        cart_response = await client.get(
            "/api/v1/theater/cart/items/", headers=headers
        )
        movies = cart_response.json()["movies"]
        assert len(movies) == 1
        assert movies[0]["name"] == "Cart Movie"

    async def test_add_same_movie_twice_returns_400(
        self, client, db_session, logged_in_user
    ):
        _, headers = logged_in_user
        movie = await create_movie(db_session, name="Duplicate Movie")

        first = await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )
        assert first.status_code == 201

        second = await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )
        assert second.status_code == 400

    async def test_add_nonexistent_movie_returns_404(self, client, logged_in_user):
        _, headers = logged_in_user
        response = await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": 999999},
            headers=headers,
        )
        assert response.status_code == 404

    async def test_add_already_purchased_movie_returns_400(
        self, client, db_session, logged_in_user
    ):
        user, headers = logged_in_user
        movie = await create_movie(db_session, name="Already Purchased Movie")
        db_session.add(MoviePurchase(user_id=user.id, movie_id=movie.id))
        await db_session.commit()

        response = await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )
        assert response.status_code == 400

    async def test_remove_movie_from_cart(self, client, db_session, logged_in_user):
        _, headers = logged_in_user
        movie = await create_movie(db_session, name="Removable Movie")
        await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )

        response = await client.delete(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )
        assert response.status_code == 200

        cart_response = await client.get(
            "/api/v1/theater/cart/items/", headers=headers
        )
        assert cart_response.json()["movies"] == []

    async def test_remove_movie_not_in_cart_returns_404(
        self, client, db_session, logged_in_user
    ):
        _, headers = logged_in_user
        movie = await create_movie(db_session, name="Not In Cart Movie")

        response = await client.request(
            "DELETE",
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )
        assert response.status_code == 404

    async def test_clear_cart_removes_all_items(
        self, client, db_session, logged_in_user
    ):
        _, headers = logged_in_user
        movie_1 = await create_movie(db_session, name="Movie One")
        movie_2 = await create_movie(
            db_session, name="Movie Two", year=2021, price="12.00"
        )
        await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie_1.id},
            headers=headers,
        )
        await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie_2.id},
            headers=headers,
        )

        response = await client.request(
            "DELETE", "/api/v1/theater/cart/items/clear/", headers=headers
        )
        assert response.status_code == 200

        cart_response = await client.get(
            "/api/v1/theater/cart/items/", headers=headers
        )
        assert cart_response.json()["movies"] == []

    async def test_cart_endpoints_require_authentication(self, client):
        response = await client.get("/api/v1/theater/cart/items/")
        assert response.status_code == 401


class TestCheckoutAndOrders:
    async def test_checkout_with_empty_cart_returns_400(self, client, logged_in_user):
        _, headers = logged_in_user
        response = await client.post("/api/v1/orders/checkout/", headers=headers)
        assert response.status_code == 400

    async def test_checkout_creates_order_and_empties_cart(
        self, client, db_session, logged_in_user
    ):
        _, headers = logged_in_user
        movie = await create_movie(
            db_session, name="Checkout Movie", price="14.50"
        )
        await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )

        response = await client.post("/api/v1/orders/checkout/", headers=headers)

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "pending"
        assert Decimal(str(body["total_amount"])) == Decimal("14.50")
        assert len(body["items"]) == 1
        assert body["items"][0]["movie"]["name"] == "Checkout Movie"

        cart_response = await client.get(
            "/api/v1/theater/cart/items/", headers=headers
        )
        assert cart_response.json()["movies"] == []

    async def test_checkout_excludes_already_pending_movie(
        self, client, db_session, logged_in_user
    ):
        _, headers = logged_in_user
        movie = await create_movie(db_session, name="Pending Movie")
        await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )
        # First checkout creates a pending order for this movie.
        first = await client.post("/api/v1/orders/checkout/", headers=headers)
        assert first.status_code == 201

        # Re-adding the same movie and trying to check out again should fail,
        # since it's already part of a pending order.
        await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )
        second = await client.post("/api/v1/orders/checkout/", headers=headers)
        assert second.status_code == 400

    async def test_get_orders_when_none_exist_returns_400(
        self, client, logged_in_user
    ):
        _, headers = logged_in_user
        response = await client.get("/api/v1/orders/", headers=headers)
        assert response.status_code == 400

    async def test_get_orders_lists_previous_orders(
        self, client, db_session, logged_in_user
    ):
        _, headers = logged_in_user
        movie = await create_movie(db_session, name="Listed Order Movie")
        await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )
        await client.post("/api/v1/orders/checkout/", headers=headers)

        response = await client.get("/api/v1/orders/", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["items"][0]["movie"]["name"] == "Listed Order Movie"

    async def test_cancel_pending_order_succeeds(
        self, client, db_session, logged_in_user
    ):
        _, headers = logged_in_user
        movie = await create_movie(db_session, name="Cancelable Movie")
        await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=headers,
        )
        checkout_response = await client.post(
            "/api/v1/orders/checkout/", headers=headers
        )
        order_id = checkout_response.json()["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/cancel/", headers=headers
        )
        assert response.status_code == 200

        orders_response = await client.get("/api/v1/orders/", headers=headers)
        assert orders_response.json()["items"][0]["status"] == "canceled"

    async def test_cancel_nonexistent_order_returns_404(
        self, client, logged_in_user
    ):
        _, headers = logged_in_user
        response = await client.patch(
            "/api/v1/orders/999999/cancel/", headers=headers
        )
        assert response.status_code == 404

    async def test_cannot_cancel_another_users_order(
        self, client, db_session, logged_in_user
    ):
        _, owner_headers = logged_in_user
        movie = await create_movie(db_session, name="Someone Elses Movie")
        await client.post(
            "/api/v1/theater/cart/items/",
            params={"movie_id": movie.id},
            headers=owner_headers,
        )
        checkout_response = await client.post(
            "/api/v1/orders/checkout/", headers=owner_headers
        )
        order_id = checkout_response.json()["id"]

        other_user = await create_user(db_session, email="intruder@example.com")
        from tests.conftest import auth_headers_for_user

        other_headers = auth_headers_for_user(other_user.id)

        response = await client.patch(
            f"/api/v1/orders/{order_id}/cancel/", headers=other_headers
        )
        assert response.status_code == 404

    async def test_checkout_requires_authentication(self, client):
        response = await client.post("/api/v1/orders/checkout/")
        assert response.status_code == 401
