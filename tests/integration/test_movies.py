"""
Integration tests: movie catalogue endpoints — filtering, sorting, pagination
and error handling, exercised against the real DB layer (in-memory SQLite).
"""
from decimal import Decimal

import pytest
import pytest_asyncio

from tests.factories import create_movie, create_genre, create_certification

pytestmark = [pytest.mark.functional, pytest.mark.asyncio(loop_scope="session")]


@pytest_asyncio.fixture
async def three_movies(db_session):
    action = await create_genre(db_session, "Action")
    drama = await create_genre(db_session, "Drama")
    cert = await create_certification(db_session, "PG-13")

    cheap_old = await create_movie(
        db_session,
        name="Cheap Old Movie",
        year=1999,
        imdb=6.0,
        price="4.99",
        description="A cheap old classic",
        certification=cert,
        genres=[drama],
    )
    mid_new = await create_movie(
        db_session,
        name="Mid New Movie",
        year=2020,
        imdb=7.5,
        price="9.99",
        description="A modern hit",
        certification=cert,
        genres=[action],
    )
    expensive_new = await create_movie(
        db_session,
        name="Expensive New Movie",
        year=2022,
        imdb=8.5,
        price="19.99",
        description="A blockbuster",
        certification=cert,
        genres=[action, drama],
    )
    return {
        "cheap_old": cheap_old,
        "mid_new": mid_new,
        "expensive_new": expensive_new,
        "action": action,
        "drama": drama,
    }


class TestMovieList:
    async def test_returns_all_movies_by_default(self, client, three_movies):
        response = await client.get("/api/v1/theater/movies/")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3

    async def test_filters_by_title_substring_case_insensitive(
        self, client, three_movies
    ):
        response = await client.get(
            "/api/v1/theater/movies/", params={"title": "cheap"}
        )
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Cheap Old Movie"

    async def test_filters_by_year_range(self, client, three_movies):
        response = await client.get(
            "/api/v1/theater/movies/", params={"min_year": 2010, "max_year": 2021}
        )
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Mid New Movie"

    async def test_filters_by_price_range(self, client, three_movies):
        response = await client.get(
            "/api/v1/theater/movies/",
            params={"min_price": 5, "max_price": 15},
        )
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Mid New Movie"

    async def test_filters_by_min_imdb(self, client, three_movies):
        response = await client.get(
            "/api/v1/theater/movies/", params={"min_imdb": 8.0}
        )
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Expensive New Movie"

    async def test_filters_by_single_genre(self, client, three_movies):
        drama_id = three_movies["drama"].id
        response = await client.get(
            "/api/v1/theater/movies/", params={"genre_ids": [drama_id]}
        )
        body = response.json()
        names = {item["name"] for item in body["items"]}
        assert names == {"Cheap Old Movie", "Expensive New Movie"}

    async def test_filters_requiring_all_given_genres_at_once(
        self, client, three_movies
    ):
        # "Expensive New Movie" is the only one tagged with BOTH genres
        action_id = three_movies["action"].id
        drama_id = three_movies["drama"].id
        response = await client.get(
            "/api/v1/theater/movies/",
            params={"genre_ids": [action_id, drama_id]},
        )
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Expensive New Movie"

    async def test_sort_by_price_ascending(self, client, three_movies):
        response = await client.get(
            "/api/v1/theater/movies/", params={"sort": "price_asc"}
        )
        prices = [Decimal(item["price"]) for item in response.json()["items"]]
        assert prices == sorted(prices)

    async def test_sort_by_price_descending(self, client, three_movies):
        response = await client.get(
            "/api/v1/theater/movies/", params={"sort": "price_desc"}
        )
        prices = [Decimal(item["price"]) for item in response.json()["items"]]
        assert prices == sorted(prices, reverse=True)

    async def test_sort_by_year_ascending_and_descending(self, client, three_movies):
        asc = await client.get(
            "/api/v1/theater/movies/", params={"sort": "year_asc"}
        )
        years_asc = [item["year"] for item in asc.json()["items"]]
        assert years_asc == sorted(years_asc)

        desc = await client.get(
            "/api/v1/theater/movies/", params={"sort": "year_desc"}
        )
        years_desc = [item["year"] for item in desc.json()["items"]]
        assert years_desc == sorted(years_desc, reverse=True)

    async def test_pagination_limit_and_offset(self, client, three_movies):
        response = await client.get(
            "/api/v1/theater/movies/", params={"limit": 1, "offset": 1}
        )
        body = response.json()
        assert len(body["items"]) == 1
        assert body["limit"] == 1
        assert body["offset"] == 1
        assert body["total"] == 3

    async def test_empty_result_when_no_movie_matches_filter(
        self, client, three_movies
    ):
        response = await client.get(
            "/api/v1/theater/movies/", params={"title": "does-not-exist-at-all"}
        )
        body = response.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_min_year_greater_than_max_year_returns_400(
        self, client, three_movies
    ):
        response = await client.get(
            "/api/v1/theater/movies/",
            params={"min_year": 2020, "max_year": 2000},
        )
        assert response.status_code == 400

    async def test_invalid_year_below_1888_is_rejected_with_422(self, client):
        response = await client.get(
            "/api/v1/theater/movies/", params={"min_year": 1800}
        )
        assert response.status_code == 422

    async def test_invalid_imdb_above_10_is_rejected_with_422(self, client):
        response = await client.get(
            "/api/v1/theater/movies/", params={"min_imdb": 11}
        )
        assert response.status_code == 422

    async def test_limit_above_100_is_rejected_with_422(self, client):
        response = await client.get(
            "/api/v1/theater/movies/", params={"limit": 500}
        )
        assert response.status_code == 422


class TestMovieDetail:
    async def test_get_existing_movie_returns_full_detail(
        self, client, three_movies
    ):
        movie_id = three_movies["mid_new"].id
        response = await client.get(f"/api/v1/theater/movies/{movie_id}/")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Mid New Movie"
        assert "average_rating" in body
        assert "favorite_count" in body

    async def test_get_nonexistent_movie_returns_404(self, client):
        response = await client.get("/api/v1/theater/movies/999999/")
        assert response.status_code == 404


class TestGenresStarsDirectors:
    async def test_genre_list_includes_movie_counts(self, client, three_movies):
        response = await client.get("/api/v1/theater/genres/")
        assert response.status_code == 200
        by_name = {g["name"]: g["movies_count"] for g in response.json()}
        assert by_name["Action"] == 2
        assert by_name["Drama"] == 2

    async def test_genre_detail_returns_404_for_unknown_genre(self, client):
        response = await client.get("/api/v1/theater/genres/999999/")
        assert response.status_code == 404

    async def test_star_list_returns_404_when_no_stars_exist(self, client):
        response = await client.get("/api/v1/theater/stars/")
        assert response.status_code == 404

    async def test_director_list_returns_404_when_no_directors_exist(self, client):
        response = await client.get("/api/v1/theater/directors/")
        assert response.status_code == 404
