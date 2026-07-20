from pydantic import BaseModel
from decimal import Decimal
from enum import Enum

#BASE SCHEMAS

class GenreBase(BaseModel):
    name: str

class StarBase(BaseModel):
    name: str

class DirectorBase(BaseModel):
    name: str

class CertificationBase(BaseModel):
    name: str

class MovieBase(BaseModel):
    name: str



#ENUM SCHEMAS FOR QUERY PARAMS AND SORTING

class MovieSortBy(str, Enum):
    price_asc = "price_asc"
    price_desc = "price_desc"
    year_desc = "year_desc"
    popularity = "popularity"



#RESPONSE SCHEMAS (GET)

class GenreResponse(GenreBase):
    id: int

    model_config = {"from_attributes": True}



class GenreWithMoviesResponse(GenreBase):
    id: int
    movies: list[MovieBase]

    model_config = {"from_attributes": True}


class GenreWithCountResponse(GenreBase):
    id: int
    movies_count: int

class StarResponse(StarBase):
    id: int

    model_config = {"from_attributes": True}


class DirectorResponse(DirectorBase):
    id: int

    model_config = {"from_attributes": True}


class CertificationResponse(CertificationBase):
    id: int

    model_config = {"from_attributes": True}

class MovieShortResponseSchema(BaseModel):
    id: int
    name: str
    year: int

class StarWithMoviesResponse(BaseModel):
    id: int
    name: str
    movies: list[MovieShortResponseSchema]

    model_config = {
        "from_attributes": True
    }

class MovieResponseSchema(BaseModel):
    id: int
    name: str
    year: int
    imdb: float
    price: Decimal
    genres: list[GenreResponse]

    model_config = {"from_attributes": True}

class MovieDetailResponseSchema(BaseModel):
    id: int
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float | None = None
    gross: float | None = None
    description: str
    price: Decimal
    certification: CertificationResponse
    genres: list[GenreResponse]
    stars: list[StarResponse]
    directors: list[DirectorResponse]
    favorite_count: int
    average_rating: float | None = None
    total_likes: int

    model_config = {"from_attributes": True}


class MovieListResponseSchema(BaseModel):
    items: list[MovieResponseSchema]
    total: int
    limit: int
    offset: int
    next: str | None = None
    previous: str | None = None
