from typing import Optional, List

from pydantic import BaseModel, computed_field
from datetime import datetime
from decimal import Decimal
from src.database.models.payment import PaymentStatusEnum
from src.schemas.movies_schema import MovieInShoppingCartResponseSchema


class OrderItemInPaymentSchema(BaseModel):
    movie: MovieInShoppingCartResponseSchema

    model_config = {"from_attributes": True}


class PaymentItemResponseSchema(BaseModel):
    id: int
    price_at_payment: Decimal
    order_item: OrderItemInPaymentSchema

    @computed_field
    def movie(self) -> MovieInShoppingCartResponseSchema:
        return self.order_item.movie

    model_config = {"from_attributes": True}


class PaymentResponseSchema(BaseModel):
    id: int
    created_at: datetime
    amount: Decimal
    items: List[PaymentItemResponseSchema]
    status: PaymentStatusEnum
    external_payment_id: Optional[str] = None

    model_config = {"from_attributes": True}


class PaymentListResponseSchema(BaseModel):
    items: list[PaymentResponseSchema]
    total: int
    limit: int
    offset: int
    next: str | None = None
    previous: str | None = None
