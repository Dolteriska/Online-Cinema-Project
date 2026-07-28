from typing import Optional

from pydantic import BaseModel
from datetime import datetime
from src.database.models.orders import StatusEnum
from decimal import Decimal

from src.schemas.movies_schema import MovieShortResponseOrderSchema


class OrderItemResponseSchema(BaseModel):
    id: int
    movie_id: int
    price_at_order: Decimal
    movie: Optional[MovieShortResponseOrderSchema] = None

    model_config = {"from_attributes": True}


class OrderResponseSchema(BaseModel):
    id: int
    created_at: datetime
    items: list[OrderItemResponseSchema]
    total_amount: Decimal
    status: StatusEnum

    model_config = {"from_attributes": True}


class OrderListResponseSchema(BaseModel):
    items: list[OrderResponseSchema]
    total: int
    limit: int
    offset: int
    next: str | None = None
    previous: str | None = None
