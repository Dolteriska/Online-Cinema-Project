from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from src.database.models import UserModel
from src.schemas.users_profile_schema import UserProfileShortResponse
from src.database.models.movie_interactions import ReactionEnum


class CommentCreateSchema(BaseModel):
    text: str

class BaseCommentSchema(BaseModel):
    id: int
    text: str
    created_at: datetime
    is_deleted: bool
    user: UserProfileShortResponse

    model_config = {"from_attributes": True}

    @field_validator("user", mode="before")
    @classmethod
    def extract_profile_from_user(cls, value):
        if hasattr(value, "profile") and value.profile is not None:
            return value.profile
        return value

class CommentReplyReadSchema(BaseCommentSchema):
    likes_count: int = 0
    dislikes_count: int = 0
    my_reaction: Optional[ReactionEnum] = None


class CommentReadSchema(BaseCommentSchema):
    likes_count: int = 0
    dislikes_count: int = 0
    my_reaction: Optional[ReactionEnum] = None

    replies: List[CommentReplyReadSchema] = Field(default_factory=list)




