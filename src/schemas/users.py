from typing import Any, Self

from pydantic import BaseModel, EmailStr, field_validator
from src.database.validators.users import validate_email, validate_password_strength


class BaseEmailPasswordSchema(BaseModel):
    email: EmailStr
    password: str

    model_config = {
        "from_attributes": True
    }

    @field_validator("email")
    @classmethod
    def _validate_email_field(cls, value):
        return validate_email(value)

    @field_validator("password")
    @classmethod
    def validate_passwords(cls, value):
        return validate_password_strength(value)


class MessageResponseSchema(BaseModel):
    message: str


class UserActivationRequestSchema(BaseModel):
    email: EmailStr
    token: str


class UserRegistrationRequestSchema(BaseEmailPasswordSchema):
    pass


class UserRegistrationResponseSchema(BaseModel):
    id: int
    email: EmailStr

    model_config = {
        "from_attributes": True
    }


class TokenRefreshRequestSchema(BaseModel):
    refresh_token: str


class TokenRefreshResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
