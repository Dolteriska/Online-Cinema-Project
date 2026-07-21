from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.config.dependencies import require_moderator
from src.database.models import UserModel
from src.database.models.movies import (Movie,
                                        Genre,
                                        Star,
                                        Director,
                                        Certification)
from src.database.session import get_db
from src.schemas.admin_movie_schema import (StarCreate,
                                            GenreCreate,
                                            DirectorCreate,
                                            CertificationCreate,
                                            MovieCreateSchema)
from src.schemas.users_schema import MessageResponseSchema
router = APIRouter()



@router.post("/stars/create/", response_model=MessageResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_star(star_data: StarCreate, db: AsyncSession = Depends(get_db),
                      current_moderator: UserModel = Depends(require_moderator)): # noqa
    stmt = select(Star).where(Star.name == star_data.name)
    result = await db.execute(stmt)
    existing_star = result.scalar_one_or_none()

    if existing_star:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Star with given name already exists")

    try:
        new_star = Star(
            name=star_data.name
        )
        db.add(new_star)
        await db.flush()

        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An error occurred during star creation.") from e

    return MessageResponseSchema(message="Star created successfully!")



@router.post("/genres/create/", response_model=MessageResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_genre(genre_data: GenreCreate, db: AsyncSession = Depends(get_db),
                       current_moderator: UserModel = Depends(require_moderator)): # noqa
    stmt = select(Genre).where(Genre.name == genre_data.name)
    result = await db.execute(stmt)
    existing_genre = result.scalar()

    if existing_genre:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Genre with given name already exists.")

    try:
        new_genre = Genre(
            name=genre_data.name
        )
        db.add(new_genre)
        await db.flush()
        await db.commit()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An error occurred during genre creation.") from e

    return MessageResponseSchema(message="Genre created successfully!")


@router.post("/director/create/", response_model=MessageResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_director(director_data: DirectorCreate, db: AsyncSession = Depends(get_db),
                          current_moderator: UserModel = Depends(require_moderator)): # noqa
    stmt = select(Director).where(Director.name == director_data.name)
    result = await db.execute(stmt)
    existing_director = result.scalar_one_or_none()

    if existing_director:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Director with given name already exists.")

    try:
        new_director = Director(
            name=director_data.name
        )
        db.add(new_director)
        await db.flush()
        await db.commit()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An error occurred during director creation.") from e

    return MessageResponseSchema(message="Director created successfully!")



@router.post("/certification/create/", response_model=MessageResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_certification(certification_data: CertificationCreate, db: AsyncSession = Depends(get_db),
                               current_moderator: UserModel = Depends(require_moderator)): # noqa
    stmt = select(Certification).where(Certification.name == certification_data.name)
    result = await db.execute(stmt)
    existing_certification = result.scalar_one_or_none()

    if existing_certification:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Certification with given name already exists.")

    try:
        new_certification = Certification(
            name=certification_data.name
        )
        db.add(new_certification)
        await db.flush()
        await db.commit()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An error occurred during certification creation.") from e

    return MessageResponseSchema(message="Certification created successfully!")

@router.post("/movies/create/", response_model=MessageResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_movie(movie_data: MovieCreateSchema, db: AsyncSession = Depends(get_db),
                       current_moderator: UserModel = Depends(require_moderator) # noqa
                       ):
    data = movie_data.model_dump()

    genre_ids = data.pop("genre_ids", [])
    star_ids = data.pop("star_ids", [])
    director_ids = data.pop("director_ids", [])

    try:
        new_movie = Movie(**data)

        genres_query = await db.execute(select(Genre).where(Genre.id.in_(genre_ids)))
        genres = list(genres_query.scalars().all())
        if len(genres) != len(genre_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more genre IDs do not exist in the database."
            )
        new_movie.genres = genres

        stars_query = await db.execute(select(Star).where(Star.id.in_(star_ids)))
        stars = list(stars_query.scalars().all())
        if len(stars) != len(star_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more star IDs do not exist."
            )
        new_movie.stars = stars

        directors_query = await db.execute(select(Director).where(Director.id.in_(director_ids)))
        directors = list(directors_query.scalars().all())
        if len(directors) != len(director_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more director IDs do not exist."
            )
        new_movie.directors = directors

        db.add(new_movie)
        await db.commit()
        await db.refresh(new_movie)

    except IntegrityError as e:
        await db.rollback()
        if "uq_movie_name_year_time" in str(e.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Movie with a given name, year and time already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity constraint violated (check foreign keys)"
        ) from e
    return MessageResponseSchema(message="Movie created successfully!")
