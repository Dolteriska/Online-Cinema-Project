from fastapi import APIRouter, Depends, status, HTTPException, Query, Request, Path
from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional
from decimal import Decimal
from src.config.dependencies import get_current_user
from src.database.models.movie_interactions import (FavoriteMovie,
                                                    ReactionEnum,
                                                    MovieReaction,
                                                    MovieRating)
from src.database.models.users import UserModel
from src.database.models.movies import (Movie,
                                        movie_genres,
                                        movie_directors,
                                        movie_stars)
from src.database.models.movie_interactions import MoviePurchase
from src.database.session import get_db
from src.schemas.movie_and_user_interaction_schema import FavoriteMovieListResponseSchema
from src.schemas.users_schema import MessageResponseSchema
from src.schemas.movies_schema import MovieResponseSchema, MovieSortBy
router = APIRouter()


#FAVORITE

@router.get("/favorites/movies/", response_model=FavoriteMovieListResponseSchema)
async def get_favorite_movies(
    request: Request,
    db: AsyncSession = Depends(get_db),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    min_imdb: Optional[float] = Query(None),
    max_imdb: Optional[float] = Query(None),
    min_price: Optional[Decimal] = Query(None),
    max_price: Optional[Decimal] = Query(None),
    certification_id: Optional[int] = Query(None),
    title: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    genre_ids: Optional[list[int]] = Query(None),
    star_ids: Optional[list[int]] = Query(None),
    director_ids: Optional[list[int]] = Query(None),
    sort: Optional[MovieSortBy] = Query(None),
    current_user: UserModel = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    base_stmt = (
        select(Movie)
        .join(FavoriteMovie, FavoriteMovie.movie_id == Movie.id)
        .where(FavoriteMovie.user_id == current_user.id)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.certification),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
        )
    )
    if title:
        title = title.strip()
        base_stmt = base_stmt.filter(Movie.name.ilike(f"%{title}%"))
    if description:
        description = description.strip()
        base_stmt = base_stmt.filter(Movie.description.ilike(f"%{description}%"))
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
                            detail="Movies with such query parameters were not found or you didn't favorite any movie yet")
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
            stmt = stmt.group_by(Movie.id, purchases_sub.c.p_count, favorites_sub.c.f_count)

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


    return FavoriteMovieListResponseSchema(
        items=[MovieResponseSchema.model_validate(movie) for movie in movies],
        total=total,
        limit=limit,
        offset=offset,
        next=next_url,
        previous=previous_url,
    )



@router.post("/movies/{movie_id}/favorite/", response_model=MessageResponseSchema, status_code=status.HTTP_201_CREATED)
async def add_movie_to_favorites(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(get_current_user)
):
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Can't add movie to favorites since movie with such id does not exist"
        )
    favorite_movie = FavoriteMovie(
        user_id=current_user.id,
        movie_id=movie_id
    )

    try:
        db.add(favorite_movie)
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if "uq_favorite_movie_user_movie" in str(e.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Movie is already in favorites"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity constraint violated"
        ) from e
    return MessageResponseSchema(message="Movie added to favorites successfully")


@router.delete("/movies/{movie_id}/favorite/", response_model=MessageResponseSchema)
async def delete_movie_from_favorites(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    stmt = select(FavoriteMovie).where(
        FavoriteMovie.user_id == current_user.id,
        FavoriteMovie.movie_id == movie_id
    )
    result = await db.execute(stmt)
    favorite_record = result.scalar_one_or_none()

    if not favorite_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie was not found in favorites"
        )

    try:
        await db.delete(favorite_record)
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Please try again later"
        ) from e

    return MessageResponseSchema(message="Movie removed from favorites successfully")


#LIKE AND DISLIKE


@router.post("/movies/{movie_id}/{reaction}/", response_model=MessageResponseSchema)
async def add_movie_reaction(
        movie_id: int,
        reaction: ReactionEnum,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(get_current_user)
):
    movie = await db.scalar(select(Movie).where(Movie.id == movie_id))
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with given ID was not found"
        )

    try:

        existing_reaction_stmt = select(MovieReaction).where(
            MovieReaction.user_id == current_user.id,
            MovieReaction.movie_id == movie_id
        )
        result = await db.execute(existing_reaction_stmt)
        existing_reaction = result.scalar_one_or_none()

        if existing_reaction:

            if existing_reaction.reaction == reaction:
                await db.delete(existing_reaction)
                await db.commit()
                return MessageResponseSchema(
                    message=f"Reaction {reaction.value} removed from movie {movie.name}"
                )


            existing_reaction.reaction = reaction
            msg = f"Reaction changed to {reaction.value} for movie {movie.name}"

        else:

            new_reaction = MovieReaction(
                user_id=current_user.id,
                movie_id=movie_id,
                reaction=reaction
            )
            db.add(new_reaction)
            msg = f"Reaction {reaction.value} successfully added to movie {movie.name}"

        await db.commit()
        return MessageResponseSchema(message=msg)

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong"
        ) from e



@router.post("/movies/{movie_id}/rate_movie/{user_rating}/", response_model=MessageResponseSchema)
async def rate_movie(
        movie_id: int,
        user_rating: int = Path(..., ge=1, le=10, description="Rating of movie from 1 to 10"),
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(get_current_user)
):
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with given ID was not found"
        )

    try:
        existing_rating_stmt = select(MovieRating).where(
            MovieRating.movie_id == movie.id,
            MovieRating.user_id == current_user.id
        )
        result = await db.execute(existing_rating_stmt)
        existing_rating = result.scalar_one_or_none()

        if existing_rating:

            if existing_rating.rating == user_rating:
                await db.delete(existing_rating)
                await db.commit()
                return MessageResponseSchema(
                    message=f"Rating {user_rating} removed from movie {movie.name}")

            existing_rating.rating = user_rating
            msg = f"Rating changed to {user_rating} for movie {movie.name}"

        else:

            new_rating = MovieRating(
                movie_id=movie.id,
                user_id=current_user.id,
                rating=user_rating
            )
            db.add(new_rating)
            msg = f"Rating {user_rating} successfully added to movie {movie.name}"

        await db.commit()
        return MessageResponseSchema(message=msg)

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong"
        ) from e








