from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from pydantic import BaseModel
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
                                            MovieCreateSchema,
                                            GenreUpdateSchema,
                                            StarUpdateSchema,
                                            DirectorUpdateSchema, CertificationUpdateSchema, MovieUpdateSchema,
                                            )
from src.schemas.movies_schema import CertificationResponse, DirectorResponse, StarResponse, GenreResponse, \
    MovieResponseSchema
from src.schemas.users_schema import MessageResponseSchema
from src.tasks.tasks import notify_users_about_new_release

router = APIRouter()

#CREATE

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


@router.post("/directors/create/", response_model=MessageResponseSchema, status_code=status.HTTP_201_CREATED)
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



@router.post("/certifications/create/", response_model=MessageResponseSchema, status_code=status.HTTP_201_CREATED)
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

    notify_users_about_new_release.delay(new_movie.id, new_movie.name)
    return MessageResponseSchema(message="Movie created successfully!")

#UPDATE


async def update_simple_entity(model, entity_id: int, update_data: BaseModel, db: AsyncSession, entity_name: str) -> dict:
    stmt = select(model).where(model.id == entity_id)
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()

    if not obj:
        raise HTTPException(status_code=404, detail=f"{entity_name} not found")

    data = update_data.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(obj, key, value)

    await db.commit()
    return {"message": f"{entity_name} successfully updated"}


@router.patch(
    "/genres/{genre_id}",
    response_model=GenreResponse,
    summary="Update Genre"
)
async def update_genre(
        genre_id: int,
        payload: GenreUpdateSchema,
        db: AsyncSession = Depends(get_db),
        current_moderator: UserModel = Depends(require_moderator) # noqa
):
    return await update_simple_entity(Genre, genre_id, payload, db, "Genre")


@router.patch(
    "/stars/{star_id}",
    response_model=StarResponse,
    summary="Update Star"
)
async def update_star(
        star_id: int,
        payload: StarUpdateSchema,
        db: AsyncSession = Depends(get_db),
        current_moderator: UserModel = Depends(require_moderator) # noqa
):
    return await update_simple_entity(Star, star_id, payload, db, "Star")


@router.patch(
    "/directors/{director_id}",
    response_model=DirectorResponse,
    summary="Update Director"
)
async def update_director(
        director_id: int,
        payload: DirectorUpdateSchema,
        db: AsyncSession = Depends(get_db),
        current_moderator: UserModel = Depends(require_moderator) # noqa
):
    return await update_simple_entity(Director, director_id, payload, db, "Director")


@router.patch(
    "/certifications/{certification_id}",
    response_model=CertificationResponse,
    summary="Update Certification"
)
async def update_certification(
        certification_id: int,
        payload: CertificationUpdateSchema,
        db: AsyncSession = Depends(get_db),
        current_moderator: UserModel = Depends(require_moderator) # noqa
):
    return await update_simple_entity(
        Certification, certification_id, payload, db, "Certification"
    )

@router.patch(
    "/movies/{movie_id}",
    response_model=MovieResponseSchema,
    summary="Update Movie"
)
async def update_movie(
        movie_id: int,
        payload: MovieUpdateSchema,
        db: AsyncSession = Depends(get_db),
        current_moderator: UserModel = Depends(require_moderator) # noqa
):

    stmt = (
        select(Movie)
        .where(Movie.id == movie_id)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
            selectinload(Movie.certification),
        )
    )
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )


    update_data = payload.model_dump(exclude_unset=True)


    if "genre_ids" in update_data:
        genre_ids = update_data.pop("genre_ids")
        if genre_ids:
            genres_res = await db.execute(select(Genre).where(Genre.id.in_(genre_ids)))
            movie.genres = list(genres_res.scalars().all())
        else:
            movie.genres = []

    if "star_ids" in update_data:
        star_ids = update_data.pop("star_ids")
        if star_ids:
            stars_res = await db.execute(select(Star).where(Star.id.in_(star_ids)))
            movie.stars = list(stars_res.scalars().all())
        else:
            movie.stars = []

    if "director_ids" in update_data:
        director_ids = update_data.pop("director_ids")
        if director_ids:
            directors_res = await db.execute(select(Director).where(Director.id.in_(director_ids)))
            movie.directors = list(directors_res.scalars().all())
        else:
            movie.directors = []


    for field, value in update_data.items():
        setattr(movie, field, value)


    await db.commit()


    await db.refresh(movie)


    await db.execute(
        select(Movie)
        .where(Movie.id == movie.id)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
            selectinload(Movie.certification),
        )
    )

    return movie



#DELETE

async def delete_simple_entity(model, entity_id: int, db: AsyncSession, entity_name: str) -> dict:
    stmt = select(model).where(model.id == entity_id)
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()

    if not obj:
        raise HTTPException(status_code=404, detail=f"{entity_name} not found")

    await db.delete(obj)
    await db.commit()

    return {"message": f"{entity_name} successfully deleted"}


@router.delete("/genres/{genre_id}", response_model=MessageResponseSchema)
async def delete_genre(genre_id: int, db: AsyncSession = Depends(get_db),
                       current_moderator: UserModel = Depends(require_moderator)):
    return await delete_simple_entity(Genre, genre_id, db, "Genre")

@router.delete("/stars/{star_id}", response_model=MessageResponseSchema)
async def delete_star(star_id: int, db: AsyncSession = Depends(get_db),
                      current_moderator: UserModel = Depends(require_moderator)):
    return await delete_simple_entity(Star, star_id, db, "Star")

@router.delete("/directors/{director_id}", response_model=MessageResponseSchema)
async def delete_director(director_id: int, db: AsyncSession = Depends(get_db),
                          current_moderator: UserModel = Depends(require_moderator)):
    return await delete_simple_entity(Director, director_id, db, "Director")

@router.delete("/certifications/{certification_id}", response_model=MessageResponseSchema)
async def delete_certification(certification_id: int, db: AsyncSession = Depends(get_db),
                               current_moderator: UserModel = Depends(require_moderator)):
    return await delete_simple_entity(Certification, certification_id, db, "Certification")

@router.delete("/movies/{movie_id}", response_model=MessageResponseSchema)
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db),
                       current_moderator: UserModel = Depends(require_moderator)):
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    await db.delete(movie)
    await db.commit()
    return MessageResponseSchema(message="Movie successfully deleted")
