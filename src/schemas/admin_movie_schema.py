from typing import Optional

from pydantic import BaseModel, Field
from decimal import Decimal
from src.schemas.movies_schema import GenreBase, StarBase, DirectorBase, CertificationBase

# POST SCHEMAS

class GenreCreate(GenreBase):
    pass


class StarCreate(StarBase):
    pass


class DirectorCreate(DirectorBase):
    pass

class CertificationCreate(CertificationBase):
    pass

class MovieCreateSchema(BaseModel):
    name: str
    year: int
    time: int = Field(..., description="Duration in minutes")
    imdb: float
    votes: int

    meta_score: Optional[float] = Field(None, ge=0, le=100)
    gross: Optional[float] = Field(None, ge=0)
    description: str
    price: Decimal = Field(..., description="Price in dollars", max_digits=10, decimal_places=2)
    certification_id: int

    genre_ids: list[int] = Field(..., min_length=1, description="List of genre IDs")
    star_ids: list[int] = Field(..., min_length=1, description="List of star IDs")
    director_ids: list[int] = Field(..., min_length=1, description="List of director IDs")


#PATCH SCHEMAS


class MovieUpdateSchema(BaseModel):
    name: str | None = None
    year: int | None = None
    time: int | None = None
    imdb: float | None = None
    description: str | None = None
    price: Decimal | None = None
    certification_id: int | None = None
    genre_ids: list[int] | None = None
    star_ids: list[int] | None = None
    director_ids: list[int] | None = None
