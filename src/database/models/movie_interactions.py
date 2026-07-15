import enum
from typing import List, Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
    Enum,
    Text,
    Boolean,
    CheckConstraint

)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from datetime import datetime
from typing import TYPE_CHECKING

from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.users import UserModel
    from src.database.models.movies import Movie


class ReactionEnum(str, enum.Enum):
    LIKE = "LIKE"
    DISLIKE = "DISLIKE"

class NotificationEnum(str, enum.Enum):
    COMMENT_REPLY = "COMMENT_REPLY"
    COMMENT_LIKE = "COMMENT_LIKE"
    NEW_RELEASE = "NEW_RELEASE"




class FavoriteMovie(Base):
    __tablename__ = "favorite_movies"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_favorite_movie_user_movie"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="favorite_movies",
    )
    movie: Mapped["Movie"] = relationship(
        "Movie",
        back_populates="favorite_by_users"
    )



class MovieReaction(Base):
    __tablename__ = "movie_reactions"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_movie_reaction_user_movie"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False
    )
    reaction: Mapped[ReactionEnum] = mapped_column(Enum(ReactionEnum),
                                                   nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="reaction_on_movies",
    )
    movie: Mapped["Movie"] = relationship(
        "Movie",
        back_populates="reacted_by_users"
    )

class MovieComment(Base):
    __tablename__ = "movie_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("movie_comments.id", ondelete="CASCADE"),
        nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="movie_comments",
    )
    movie: Mapped["Movie"] = relationship(
        "Movie",
        back_populates="comments",
    )
    parent: Mapped[Optional["MovieComment"]] = relationship(
        "MovieComment",
        remote_side=[id],
        back_populates="replies",
        foreign_keys=[parent_id]
    )
    replies: Mapped[List["MovieComment"]] = relationship(
        "MovieComment",
        back_populates="parent",
        cascade="all, delete-orphan",
        single_parent=True
    )

    reactions: Mapped[List["MovieCommentReaction"]] = relationship(
        "MovieCommentReaction",
        back_populates="comment",
        cascade="all, delete-orphan"
    )


class MovieRating(Base):
    __tablename__ = "movie_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_movie_rating_user_movie"),
        CheckConstraint("rating >= 1 AND rating <= 10", name="ck_rating_range")
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="movie_ratings",
    )
    movie: Mapped["Movie"] = relationship(
        "Movie",
        back_populates="ratings"
    )


class MovieCommentReaction(Base):
    __tablename__ = "comment_reactions"
    __table_args__ = (
        UniqueConstraint("user_id", "comment_id", name="uq_movie_comment_reaction_user_comment"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("movie_comments.id", ondelete="CASCADE"),
        nullable=False
    )
    reaction: Mapped[ReactionEnum] = mapped_column(Enum(ReactionEnum),
                                                   nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="comment_reactions",
    )
    comment: Mapped["MovieComment"] = relationship(
        "MovieComment",
        back_populates="reactions"
    )


class UserNotification(Base):
    __tablename__ = "user_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    notification_type: Mapped[NotificationEnum] = mapped_column(
        Enum(NotificationEnum),
        nullable=False
    )

    movie_comment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("movie_comments.id", ondelete="CASCADE"),
        nullable=True
    )

    movie_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=True
    )

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="notifications",
    )

    movie_comment: Mapped[Optional["MovieComment"]] = relationship(
        "MovieComment",
        foreign_keys=[movie_comment_id]
    )

    movie: Mapped[Optional["Movie"]] = relationship(
        "Movie",
        foreign_keys=[movie_id]
    )

class MoviePurchase(Base):
    """Model for tracking user movie purchases"""
    __tablename__ = "movie_purchases"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_user_movie_purchase"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="RESTRICT"),
        nullable=False
    )

    purchase_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    expiration_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    user: Mapped["UserModel"] = relationship("UserModel")
    movie: Mapped["Movie"] = relationship("Movie")
