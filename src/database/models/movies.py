import uuid as uuid_pkg
from typing import List, Optional, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import (
    ForeignKey,
    String,
    Float,
    Integer,
    Text,
    UniqueConstraint,
    Table,
    Column,
    Uuid,
    Numeric,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.movie_interactions import (MovieComment,
                                                        MovieReaction,
                                                        FavoriteMovie,
                                                        MovieRating,
                                                        MoviePurchase)

movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True)
)

movie_stars = Table(
    "movie_stars",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("star_id", ForeignKey("stars.id", ondelete="CASCADE"), primary_key=True)
)

movie_directors = Table(
    "movie_directors",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("director_id", ForeignKey("directors.id", ondelete="CASCADE"), primary_key=True)
)

class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    movies: Mapped[List["Movie"]] = relationship(
        secondary=movie_genres,
        back_populates="genres"
    )


class Star(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    movies: Mapped[List["Movie"]] = relationship(
        secondary=movie_stars,
        back_populates="stars"
    )


class Director(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    movies: Mapped[List["Movie"]] = relationship(
        "Movie",
        secondary=movie_directors,
        back_populates="directors"
    )


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    movies: Mapped[List["Movie"]] = relationship(
        "Movie",
        back_populates="certification"
    )


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="uq_movie_name_year_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(
        Uuid(as_uuid=True),
        default=uuid_pkg.uuid4,
        unique=True,
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    time: Mapped[int] = mapped_column(Integer, nullable=False)
    imdb: Mapped[float] = mapped_column(Float, nullable=False)
    votes: Mapped[int] = mapped_column(Integer, nullable=False)
    meta_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id", ondelete="RESTRICT"),
        nullable=False,
    )
    certification: Mapped["Certification"] = relationship(
        "Certification",
        back_populates="movies"
    )
    stars: Mapped[List["Star"]] = relationship(
        secondary=movie_stars,
        back_populates="movies",
    )

    directors: Mapped[List["Director"]] = relationship(
        secondary=movie_directors,
        back_populates="movies"
    )

    genres: Mapped[List["Genre"]] = relationship(
        secondary=movie_genres,
        back_populates="movies",
    )

    favorite_by_users: Mapped[List["FavoriteMovie"]] = relationship(
        "FavoriteMovie",
        back_populates="movie",
        cascade="all, delete-orphan"
    )

    reacted_by_users: Mapped[List["MovieReaction"]] = relationship(
        "MovieReaction",
        back_populates="movie",
        cascade="all, delete-orphan"
    )

    comments: Mapped[List["MovieComment"]] = relationship(
        "MovieComment",
        back_populates="movie",
        cascade="all, delete-orphan"
    )

    ratings: Mapped[List["MovieRating"]] = relationship(
        "MovieRating",
        back_populates="movie",
        cascade="all, delete-orphan"
    )

    purchases: Mapped[List["MoviePurchase"]] = relationship(
        "MoviePurchase",
        back_populates="movie"
    )

    @property
    def favorite_count(self) -> int:
        """Number of users who added this movie to their favorites"""
        return len(self.favorite_by_users)

    @property
    def average_rating(self) -> float | None:
        """Average rating from users"""
        if not self.ratings:
            return None
        return sum(r.rating for r in self.ratings) / len(self.ratings)

    @property
    def total_likes(self) -> int:
        """Number of likes"""
        return sum(1 for r in self.reacted_by_users if r.reaction.value == "LIKE")









