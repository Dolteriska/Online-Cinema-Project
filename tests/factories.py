"""
Small, explicit factory helpers for building test data directly through the
ORM. Kept deliberately simple (no factory_boy dependency), so the test suite
has the smallest possible list of extra requirements.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.users import UserModel, UserGroupModel, UserGroupEnum
from src.database.models.movies import Movie, Genre, Certification, Star, Director


async def get_group(db: AsyncSession, group_name: UserGroupEnum) -> UserGroupModel:
    result = await db.execute(
        select(UserGroupModel).where(UserGroupModel.name == group_name)
    )
    return result.scalars().one()


async def create_user(
    db: AsyncSession,
    email: str = "user@example.com",
    password: str = "StrongPass1!",
    group: UserGroupEnum = UserGroupEnum.USER,
    is_active: bool = True,
) -> UserModel:
    user_group = await get_group(db, group)
    user = UserModel.create(email=email, raw_password=password, group_id=user_group.id)
    user.is_active = is_active
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_certification(db: AsyncSession, name: str = "R-18") -> Certification:
    result = await db.execute(select(Certification).where(Certification.name == name))
    existing = result.scalars().first()
    if existing:
        return existing
    cert = Certification(name=name)
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return cert


async def create_genre(db: AsyncSession, name: str = "Drama") -> Genre:
    result = await db.execute(select(Genre).where(Genre.name == name))
    existing = result.scalars().first()
    if existing:
        return existing
    genre = Genre(name=name)
    db.add(genre)
    await db.commit()
    await db.refresh(genre)
    return genre


async def create_star(db: AsyncSession, name: str = "Test Star") -> Star:
    result = await db.execute(select(Star).where(Star.name == name))
    existing = result.scalars().first()
    if existing:
        return existing
    star = Star(name=name)
    db.add(star)
    await db.commit()
    await db.refresh(star)
    return star


async def create_director(db: AsyncSession, name: str = "Test Director") -> Director:
    result = await db.execute(select(Director).where(Director.name == name))
    existing = result.scalars().first()
    if existing:
        return existing
    director = Director(name=name)
    db.add(director)
    await db.commit()
    await db.refresh(director)
    return director


async def create_movie(
    db: AsyncSession,
    name: str = "Test Movie",
    year: int = 2020,
    time: int = 120,
    imdb: float = 7.5,
    votes: int = 1000,
    price: str = "9.99",
    description: str = "A movie used for testing.",
    certification: Certification | None = None,
    genres: list[Genre] | None = None,
) -> Movie:
    if certification is None:
        certification = await create_certification(db)
    movie = Movie(
        name=name,
        year=year,
        time=time,
        imdb=imdb,
        votes=votes,
        price=Decimal(price),
        description=description,
        certification_id=certification.id,
    )
    if genres:
        movie.genres = genres
    db.add(movie)
    await db.commit()
    await db.refresh(movie)
    return movie
