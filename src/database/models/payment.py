import enum
from typing import List, Optional
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
from src.database.models import Movie
from src.database.models.users import UserModel
from src.database.models.orders import Order, OrderItem
class PaymentStatusEnum(str, enum.Enum):
    SUCCESSFUL = "successful"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    status: Mapped[PaymentStatusEnum] = mapped_column(
        Enum(
            PaymentStatusEnum,
            name="paymentstatusenum",
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=PaymentStatusEnum.SUCCESSFUL
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    external_payment_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="payments"
    )

    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="payments"
    )

    items: Mapped[List["PaymentItem"]] = relationship(
        "PaymentItem",
        back_populates="payment",
        cascade="all, delete-orphan"
    )




class PaymentItem(Base):
    __tablename__ = "payment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"),
                                         nullable=False)

    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id", ondelete="CASCADE"),
                                               nullable=False)

    price_at_payment: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="items"
    )

    order_item: Mapped["OrderItem"] = relationship(
        "OrderItem",
        back_populates="payment_items"
    )

