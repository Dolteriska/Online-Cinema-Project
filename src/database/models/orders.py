import enum
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import (
    ForeignKey,
    String,
    Float,
    Integer,
    Enum,
    DateTime,
    func, Numeric,
)
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models import Movie
    from src.database.models.users import UserModel
    from src.database.models.payment import (Payment,
                                             PaymentItem)

class StatusEnum(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    status: Mapped[StatusEnum] = mapped_column(
        Enum(
            StatusEnum,
            name="statusenum",
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=StatusEnum.PENDING
    )
    total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)


    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="orders"
    )

    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="order")




class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False
    )

    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False
    )

    price_at_order: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="items"
    )

    movie: Mapped["Movie"] = relationship(
        "Movie",
        back_populates="order_items"
    )

    payment_items: Mapped[List["PaymentItem"]] = relationship(
        "PaymentItem",
        back_populates="order_item")
