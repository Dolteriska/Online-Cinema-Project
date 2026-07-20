from pydantic import BaseModel
from src.schemas.movies_schema import MovieResponseSchema


class MovieListResponseSchema(BaseModel):
    items: list[MovieResponseSchema]
    total: int
    limit: int
    offset: int
    next: str | None = None
    previous: str | None = None


class FavoriteMovieListResponseSchema(BaseModel):
    items: list[MovieResponseSchema]
    total: int
    limit: int
    offset: int
    next: str | None = None
    previous: str | None = None
