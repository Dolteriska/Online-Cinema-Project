from typing import Optional

from pydantic import BaseModel, Field, field_validator
from src.database.validators.users import validate_email, validate_password_strength
from datetime import date, datetime
from src.database.models.users import GenderEnum



class UserProfileBase(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    gender: GenderEnum | None = None
    date_of_birth: date | None = None
    info: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def check_not_empty(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("Field can't be empty or blank")
        return value


class UserProfileCreate(UserProfileBase):
    first_name: str = Field(..., min_length=1, description="First name")
    date_of_birth: date = Field(..., description="Date of birth")


class UserProfileResponse(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str | None
    gender: GenderEnum | None
    date_of_birth: date
    avatar: str | None = None

    model_config = {"from_attributes": True}


class UserProfileUpdateSchema(UserProfileBase):
    pass
