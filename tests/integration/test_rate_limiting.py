"""
Rate limiting tests: Tests how rate limiting works.
Base rate limiter is defined in main.py file with default set to 100 request per minute
"""
import pytest
from src.config.limiter import limiter


pytestmark = [pytest.mark.functional, pytest.mark.asyncio(loop_scope="session")]


@pytest.fixture(autouse=True)
def reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


class TestRateLimit:
    async def test_exceeds_default_limit_movies(self, client):
        print(limiter._storage)
        for _ in range(100):
            response = await client.get("/api/v1/theater/movies/")
        response = await client.get("/api/v1/theater/movies/")
        assert response.status_code == 429
