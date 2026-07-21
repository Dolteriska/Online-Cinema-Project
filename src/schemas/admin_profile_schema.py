from pydantic import BaseModel
from src.schemas.users_profile_schema import UserProfileResponse


class AdminUserProfileListResponseSchema(BaseModel):
    items: list[UserProfileResponse]
    total: int
    limit: int
    offset: int
    next: str | None
    previous: str | None

