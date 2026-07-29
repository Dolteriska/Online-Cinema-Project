from typing import Optional

from pydantic import BaseModel
from datetime import datetime
from src.database.models.orders import StatusEnum
from decimal import Decimal

from src.schemas.payment_schema import PaymentResponseSchema
from src.schemas.users_schema import UserShortResponseSchema

class AdminPaymentResponseSchema(PaymentResponseSchema):
    user: UserShortResponseSchema


class AdminPaymentListResponseSchema(BaseModel):
    items: list[AdminPaymentResponseSchema]
    total: int
    limit: int
    offset: int
    next: Optional[str] = None
    previous: Optional[str] = None

    model_config = {"from_attributes": True}
