from fastapi import APIRouter, Depends, status, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload


from src.database.models.movies import (Movie,
                                        Certification,
                                        Genre,
                                        Star,
                                        Director)
from src.schemas.movies_schema import (MovieResponseSchema,
                                       MovieListResponseSchema,
                                       GenreResponse,
                                       StarResponse,
                                       MovieShortResponseSchema,
                                       StarWithMoviesResponse)

from src.config.settings import settings
from src.database.session import get_db
router = APIRouter()



@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_movie_list(request: Request,
                         db: AsyncSession = Depends(get_db),
                         limit: int = Query(default=20, ge=1, le=100),
                         offset: int = Query(default=0, ge=0)
                         ):
    total_stmt = select(func.count()).select_from(Movie)
    total_result = await db.execute(total_stmt)
    total = total_result.scalar_one_or_none()

    if not total:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No movies found")


    stmt = (
        select(Movie)
        .options(
            selectinload(Movie.certification),
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
        )
        .order_by(Movie.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    movies = result.scalars().all()

    next_offset = offset + limit
    previous_offset = max(offset - limit, 0)

    next_url = None
    if next_offset < total:
        next_url = str(
            request.url.include_query_params(
                limit=limit,
                offset=next_offset
            )
        )
    previous_url = None
    if offset > 0:
        previous_url = str(
            request.url.include_query_params(
                limit=limit,
                offset=previous_offset,
            )
        )

    return MovieListResponseSchema(
        items=[MovieResponseSchema.model_validate(movie) for movie in movies],
        total=total,
        limit=limit,
        offset=offset,
        next=next_url,
        previous=previous_url,
    )


@router.get("/movies/{movie_id}/", response_model=MovieResponseSchema)
async def get_movie_by_id(movie_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Movie)
        .options(
            selectinload(Movie.certification),
            selectinload(Movie.genres)
        )
    )
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with given id was not found"
        )
    return MovieResponseSchema(
        id=movie.id,
        name=movie.name,
        year=movie.year,
        time=movie.time,
        imdb=movie.imdb,
        votes=movie.votes,
        meta_score=movie.meta_score,
        gross=movie.gross,
        description=movie.description,
        price=movie.price,
        certification=movie.certification,
        genres=movie.genres
    )


@router.get("/genres/", response_model=list[GenreResponse], status_code=status.HTTP_200_OK)
async def get_genre_list(db: AsyncSession = Depends(get_db)):
    stmt = select(Genre)
    result = await db.execute(stmt)

    genres = result.scalars().all()

    if not genres:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No genres were found")

    return genres


@router.get("/stars/", response_model=list[StarResponse], status_code=status.HTTP_200_OK)
async def get_star_list(db: AsyncSession = Depends(get_db)):
    stmt = select(Star).options(selectinload(Star.movies))
    result = await db.execute(stmt)

    stars = result.scalars().all()

    if not stars:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No stars were found")

    return stars


@router.get("/stars/{star_id}/", response_model=StarWithMoviesResponse, status_code=status.HTTP_200_OK)
async def get_star_with_movies(star_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Star)
        .where(Star.id == star_id)
        .options(selectinload(Star.movies))
    )
    result = await db.execute(stmt)
    star = result.scalar_one_or_none()

    if not star:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Star with given ID was not found")

    return star





