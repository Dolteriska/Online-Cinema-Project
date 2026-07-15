from datetime import datetime

from pydantic import BaseModel, EmailStr

from src.database.models.users import UserGroupEnum


class AdminUserResponseSchema(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    group: UserGroupEnum
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

class AdminUserListResponseSchema(BaseModel):
    items: list[AdminUserResponseSchema]
    total: int
    limit: int
    offset: int
    next: str | None
    previous: str | None


class MessageResponseSchema(BaseModel):
    message: str


class AdminUserGroupChangeSchema(BaseModel):
    group: UserGroupEnum
