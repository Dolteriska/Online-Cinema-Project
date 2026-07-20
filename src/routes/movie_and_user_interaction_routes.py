from fastapi import APIRouter, Depends, status, HTTPException, Query, Request, Path
from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config.dependencies import get_current_user
from src.database.models.movie_interactions import (FavoriteMovie,
                                                    ReactionEnum,
                                                    MovieReaction,
                                                    MovieRating)
from src.database.models.users import UserModel
from src.database.models.movies import (Movie,
                                        Certification,
                                        Genre,
                                        Star,
                                        Director,
                                        movie_genres)
from src.database.session import get_db
from src.schemas.movie_and_user_interaction_schema import FavoriteMovieListResponseSchema
from src.schemas.users_schema import MessageResponseSchema
from src.schemas.movies_schema import MovieResponseSchema

router = APIRouter()


#FAVORITE

@router.get("/favorites/movies/", response_model=FavoriteMovieListResponseSchema)
async def get_favorite_movies(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    total_stmt = (
        select(func.count())
        .select_from(FavoriteMovie)
        .where(FavoriteMovie.user_id == current_user.id)
    )
    total_result = await db.execute(total_stmt)
    total = total_result.scalar_one()

    stmt = (
        select(Movie)
        .join(FavoriteMovie, FavoriteMovie.movie_id == Movie.id)
        .where(FavoriteMovie.user_id == current_user.id)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.certification),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
        )
        .order_by(FavoriteMovie.created_at.desc())
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
                offset=next_offset,
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








