from typing import Optional, List

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


class GenreUpdateSchema(BaseModel):
    name: Optional[str] = None


class StarUpdateSchema(BaseModel):
    name: Optional[str] = None


class DirectorUpdateSchema(BaseModel):
    name: Optional[str] = None


class CertificationUpdateSchema(BaseModel):
    name: Optional[str] = None


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = None
    year: Optional[int] = None
    time: Optional[int] = None
    imdb: Optional[float] = None
    votes: Optional[int] = None
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    certification_id: Optional[int] = None


    genre_ids: Optional[List[int]] = None
    star_ids: Optional[List[int]] = None
    director_ids: Optional[List[int]] = None
