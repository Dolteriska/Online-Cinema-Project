from sqlalchemy import (
    ForeignKey,
    Integer,
    UniqueConstraint,
    DateTime,
    func)
from datetime import datetime
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship)

from src.database.base import Base
from src.database.models import Movie
from src.database.models.users import UserModel


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True
    )

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="cart"
    )

    cart_items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan"
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "movie_id", name="uq_cart_id_movie_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False
    )

    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False
    )

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    cart: Mapped["Cart"] = relationship(
        "Cart",
        back_populates="cart_items"
    )

    movie: Mapped["Movie"] = relationship(
        "Movie",
        back_populates="in_cart"
    )
