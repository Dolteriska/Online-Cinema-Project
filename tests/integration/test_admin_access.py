"""
Integration tests: role-based access control (business rule validation).

`require_admin` / `require_moderator` guard the admin endpoints. These tests
confirm that regular users are rejected and that users with the right role
can perform admin actions end-to-end against the DB.
"""
import pytest

from src.database.models.users import UserGroupEnum
from tests.factories import (
    create_user,
    create_certification,
    create_star,
    create_director,
    create_genre,
)

pytestmark = [pytest.mark.functional, pytest.mark.asyncio(loop_scope="session")]


class TestAdminAccessControl:
    async def test_regular_user_cannot_list_admin_users(
        self, client, db_session, make_auth_headers
    ):
        user = await create_user(db_session, email="plain@example.com")

        response = await client.get(
            "/api/v1/admin/accounts/users/",
            headers=make_auth_headers(user.id),
        )
        assert response.status_code == 403

    async def test_admin_can_list_users(self, client, db_session, make_auth_headers):
        admin = await create_user(
            db_session, email="admin@example.com", group=UserGroupEnum.ADMIN
        )
        await create_user(db_session, email="someone@example.com")

        response = await client.get(
            "/api/v1/admin/accounts/users/",
            headers=make_auth_headers(admin.id),
        )
        assert response.status_code == 200
        emails = {u["email"] for u in response.json()["items"]}
        assert "admin@example.com" in emails
        assert "someone@example.com" in emails

    async def test_moderator_can_create_genre_but_regular_user_cannot(
        self, client, db_session, make_auth_headers
    ):
        moderator = await create_user(
            db_session,
            email="moderator@example.com",
            group=UserGroupEnum.MODERATOR,
        )
        regular = await create_user(db_session, email="regular2@example.com")

        forbidden = await client.post(
            "/api/v1/admin/theater/genres/create/",
            json={"name": "Sci-Fi"},
            headers=make_auth_headers(regular.id),
        )
        assert forbidden.status_code == 403

        allowed = await client.post(
            "/api/v1/admin/theater/genres/create/",
            json={"name": "Sci-Fi"},
            headers=make_auth_headers(moderator.id),
        )
        assert allowed.status_code == 201

    async def test_admin_can_also_access_moderator_endpoints(
        self, client, db_session, make_auth_headers
    ):
        admin = await create_user(
            db_session, email="admin2@example.com", group=UserGroupEnum.ADMIN
        )
        response = await client.post(
            "/api/v1/admin/theater/genres/create/",
            json={"name": "Thriller"},
            headers=make_auth_headers(admin.id),
        )
        assert response.status_code == 201

    async def test_admin_endpoints_require_admin(self, client, db_session, make_auth_headers):
        user = await create_user(
            db_session, email="user@example.com", group=UserGroupEnum.USER
        )
        response = await client.get("/api/v1/admin/accounts/users/",
                                    headers=make_auth_headers(user.id))
        assert response.status_code == 403

    async def test_creating_movie_with_unknown_genre_id_returns_400(
        self, client, db_session, make_auth_headers
    ):
        moderator = await create_user(
            db_session,
            email="moderator2@example.com",
            group=UserGroupEnum.MODERATOR,
        )
        cert = await create_certification(db_session, "PG")
        star = await create_star(db_session, "Real Star")
        director = await create_director(db_session, "Real Director")

        payload = {
            "name": "Some New Movie",
            "year": 2023,
            "time": 100,
            "imdb": 7.0,
            "votes": 10,
            "description": "desc",
            "price": "5.00",
            "certification_id": cert.id,
            "genre_ids": [999999],  # does not exist
            "star_ids": [star.id],
            "director_ids": [director.id],
        }
        response = await client.post(
            "/api/v1/admin/theater/movies/create/",
            json=payload,
            headers=make_auth_headers(moderator.id),
        )
        assert response.status_code == 400

    async def test_creating_movie_with_valid_ids_succeeds(
        self, client, db_session, make_auth_headers
    ):
        moderator = await create_user(
            db_session,
            email="moderator3@example.com",
            group=UserGroupEnum.MODERATOR,
        )
        cert = await create_certification(db_session, "PG-13")
        genre = await create_genre(db_session, "Comedy")
        star = await create_star(db_session, "Another Star")
        director = await create_director(db_session, "Another Director")

        payload = {
            "name": "Brand New Movie",
            "year": 2024,
            "time": 95,
            "imdb": 6.5,
            "votes": 5,
            "description": "desc",
            "price": "7.00",
            "certification_id": cert.id,
            "genre_ids": [genre.id],
            "star_ids": [star.id],
            "director_ids": [director.id],
        }
        response = await client.post(
            "/api/v1/admin/theater/movies/create/",
            json=payload,
            headers=make_auth_headers(moderator.id),
        )
        assert response.status_code == 201

        list_response = await client.get(
            "/api/v1/theater/movies/", params={"title": "Brand New Movie"}
        )
        assert list_response.json()["total"] == 1

    async def test_creating_duplicate_genre_name_returns_400(
        self, client, db_session, make_auth_headers
    ):
        moderator = await create_user(
            db_session,
            email="moderator4@example.com",
            group=UserGroupEnum.MODERATOR,
        )
        await client.post(
            "/api/v1/admin/theater/genres/create/",
            json={"name": "Horror"},
            headers=make_auth_headers(moderator.id),
        )
        duplicate = await client.post(
            "/api/v1/admin/theater/genres/create/",
            json={"name": "Horror"},
            headers=make_auth_headers(moderator.id),
        )
        assert duplicate.status_code == 400
