from typing import Optional

from pydantic import BaseModel
from datetime import datetime
from src.database.models.orders import StatusEnum
from decimal import Decimal

from src.schemas.movies_schema import MovieShortResponseSchema
from src.schemas.order_schema import OrderResponseSchema
from src.schemas.users_schema import UserShortResponseSchema

class AdminOrderResponseSchema(OrderResponseSchema):
    user: UserShortResponseSchema


class AdminOrderListResponseSchema(BaseModel):
    items: list[AdminOrderResponseSchema]
    total: int
    limit: int
    offset: int
    next: Optional[str] = None
    previous: Optional[str] = None

    model_config = {"from_attributes": True}
