from typing import Optional

from fastapi import APIRouter, Depends, status, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from decimal import Decimal


from src.database.models.movies import (Movie,
                                        Certification,
                                        Genre,
                                        Star,
                                        Director,
                                        movie_genres,
                                        movie_directors,
                                        movie_stars)
from src.schemas.movies_schema import (MovieResponseSchema,
                                       MovieListResponseSchema,
                                       GenreResponse,
                                       StarResponse,
                                       MovieShortResponseSchema,
                                       StarWithMoviesResponse,
                                       MovieDetailResponseSchema,
                                       DirectorResponse,
                                       GenreWithCountResponse,
                                       GenreWithMoviesResponse,
                                       MovieSortBy
                                       )
from src.database.models.movie_interactions import (MoviePurchase,
                                                    FavoriteMovie
                                                    )

from src.database.session import get_db
router = APIRouter()


@router.get("/")
async def get_movies():
    # TODO: GET EVERYTHING DONE
    return {"message": "Coming soon"}

@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_movie_list(request: Request,
                         db: AsyncSession = Depends(get_db),
                         min_year: Optional[int] = Query(None),
                         max_year: Optional[int] = Query(None),
                         min_imdb: Optional[float] = Query(None),
                         max_imdb: Optional[float] = Query(None),
                         genre_ids: Optional[list[int]] = Query(None),
                         min_price: Optional[Decimal] = Query(None),
                         max_price: Optional[Decimal] = Query(None),
                         certification_id: Optional[int] = Query(None),
                         title: Optional[str] = Query(None),
                         star_ids: Optional[list[int]] = Query(None),
                         director_ids: Optional[list[int]] = Query(None),
                         sort: Optional[MovieSortBy] = Query(None),
                         limit: int = Query(default=20, ge=1, le=100),
                         offset: int = Query(default=0, ge=0),
                         ):
    base_stmt = select(Movie)

    if title:
        title = title.strip()
        base_stmt = base_stmt.filter(Movie.name.ilike(f"%{title}%"))
    if min_year:
        base_stmt = base_stmt.filter(Movie.year >= min_year)
    if max_year:
        base_stmt = base_stmt.filter(Movie.year <= max_year)
    if min_imdb:
        base_stmt = base_stmt.filter(Movie.imdb >= min_imdb)
    if max_imdb:
        base_stmt = base_stmt.filter(Movie.imdb <= max_imdb)
    if min_price:
        base_stmt = base_stmt.filter(Movie.price >= min_price)
    if max_price:
        base_stmt = base_stmt.filter(Movie.price <= max_price)
    if certification_id:
        base_stmt = base_stmt.filter(Movie.certification_id == certification_id)

    if genre_ids:
        base_stmt = (
            base_stmt.join(movie_genres)
            .filter(movie_genres.c.genre_id.in_(genre_ids))
            .group_by(Movie.id)
            .having(func.count(movie_genres.c.genre_id) == len(genre_ids))
        )
    if star_ids:
        base_stmt = (
            base_stmt.join(movie_stars)
            .filter(movie_stars.c.star_id.in_(star_ids))
            .group_by(Movie.id)
            .having(func.count(movie_stars.c.star_id) == len(star_ids))
        )
    if director_ids:
        base_stmt = (
            base_stmt.join(movie_directors)
            .filter(movie_directors.c.director_id.in_(director_ids))
            .group_by(Movie.id)
            .having(func.count(movie_directors.c.director_id) == len(director_ids))
        )

    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(total_stmt)
    total = total_result.scalar_one_or_none() or 0

    if total == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Movies with such query parameters were not found or the database is emtpy")
    stmt = base_stmt.options(
        selectinload(Movie.certification),
        selectinload(Movie.genres),
        selectinload(Movie.stars),
        selectinload(Movie.directors),
    )

    if sort == MovieSortBy.popularity:
        purchases_sub = (
            select(MoviePurchase.movie_id, func.count(MoviePurchase.id).label("p_count"))
            .group_by(MoviePurchase.movie_id)
            .subquery()
        )

        favorites_sub = (
            select(FavoriteMovie.movie_id, func.count(FavoriteMovie.id).label("f_count"))
            .group_by(FavoriteMovie.movie_id)
            .subquery()
        )

        stmt = (
            stmt
            .outerjoin(purchases_sub, Movie.id == purchases_sub.c.movie_id)
            .outerjoin(favorites_sub, Movie.id == favorites_sub.c.movie_id)
        )
        popularity_score = (
                (func.coalesce(purchases_sub.c.p_count, 0) * 100) +
                (func.coalesce(favorites_sub.c.f_count, 0) * 30) +
                (Movie.votes * 0.001)
        )

        if genre_ids or star_ids or director_ids:
            stmt = stmt.group_by(purchases_sub.c.p_count, favorites_sub.c.f_count)

        stmt = stmt.order_by(popularity_score.desc())

    elif sort == MovieSortBy.price_asc:
        stmt = stmt.order_by(Movie.price.asc())
    elif sort == MovieSortBy.price_desc:
        stmt = stmt.order_by(Movie.price.desc())
    elif sort == MovieSortBy.year_desc:
        stmt = stmt.order_by(Movie.year.desc())
    else:
        stmt = stmt.order_by(Movie.id.desc())

    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    movies = result.scalars().all()

    next_offset = offset + limit
    previous_offset = max(offset - limit, 0)

    next_url = str(request.url.include_query_params(limit=limit, offset=next_offset)) if next_offset < total else None
    previous_url = str(request.url.include_query_params(limit=limit, offset=previous_offset)) if offset > 0 else None

    return MovieListResponseSchema(
        items=[MovieResponseSchema.model_validate(movie) for movie in movies],
        total=total,
        limit=limit,
        offset=offset,
        next=next_url,
        previous=previous_url,
    )


@router.get("/movies/{movie_id}/", response_model=MovieDetailResponseSchema)
async def get_movie_by_id(movie_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Movie).where(Movie.id == movie_id)
        .options(
            selectinload(Movie.certification),
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
            selectinload(Movie.favorite_by_users),
            selectinload(Movie.ratings),
            selectinload(Movie.reacted_by_users)
        )
    )
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with given id was not found"
        )
    return movie


@router.get("/genres/", response_model=list[GenreWithCountResponse], status_code=status.HTTP_200_OK)
async def get_genre_list(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Genre.id,
               Genre.name,
               func.count(movie_genres.c.movie_id).label("movies_count")
               )
        .outerjoin(movie_genres, Genre.id == movie_genres.c.genre_id)
        .group_by(Genre.id, Genre.name)
        .order_by(Genre.id.desc())
    )

    result = await db.execute(stmt)
    genres = result.all()

    if not genres:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No genres were found"
        )

    return genres

@router.get("/genres/{genre_id}/", response_model=GenreWithMoviesResponse, status_code=status.HTTP_200_OK)
async def get_genre_detail(genre_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Genre)
        .where(Genre.id == genre_id)
        .options(selectinload(Genre.movies))
    )
    result = await db.execute(stmt)
    genre = result.scalar_one_or_none()

    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No genre was found"
        )
    return genre

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


@router.get("/directors/", response_model=list[DirectorResponse], status_code=status.HTTP_200_OK)
async def get_director_list(db: AsyncSession = Depends(get_db)):
    stmt = select(Director).options(selectinload(Director.movies))
    result = await db.execute(stmt)

    directors = result.scalars().all()

    if not directors:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No directors were found")

    return directors


