import asyncio
from typing import Optional
from datetime import date
from fastapi import (APIRouter,
                     Depends,
                     File, Form,
                     UploadFile,
                     HTTPException,
                     status)
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database.session import get_db
from src.config.dependencies import get_current_user
from src.database.models.users import UserProfileModel, GenderEnum
from src.schemas.users_profile_schema import (UserProfileCreate,
                                              UserProfileResponse,
                                              UserProfileUpdateSchema,
                                              UserDeleteRequestSchema,
                                              DeleteProfileQuestionEnum)
from src.database.models.users import UserModel
from src.schemas.users_schema import MessageResponseSchema
from src.services.storage import storage_service

router = APIRouter()


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024


def _validate_avatar(avatar: UploadFile, content: bytes) -> None:
    if (not avatar.content_type
            or avatar.content_type not in ALLOWED_CONTENT_TYPES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image (jpeg, png or webp)"
        )
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar file is too large (max 5 MB)"
        )


def _build_profile_response(profile: UserProfileModel,
                            avatar_url: Optional[str]) -> UserProfileResponse:
    response = UserProfileResponse.model_validate(profile)
    response.avatar = avatar_url
    return response


# PROFILES
@router.post("/create/",
             response_model=UserProfileResponse,
             status_code=status.HTTP_201_CREATED)
async def create_user_profile(
        first_name: str = Form(...),
        date_of_birth: date = Form(...),
        current_user: UserModel = Depends(get_current_user),
        last_name: Optional[str] = Form(None),
        gender: Optional[GenderEnum] = Form(None),
        info: Optional[str] = Form(None),
        avatar: Optional[UploadFile] = File(None),
        db: AsyncSession = Depends(get_db),
):
    try:
        profile_data = UserProfileCreate(
            first_name=first_name,
            date_of_birth=date_of_birth,
            last_name=last_name,
            gender=gender,
            info=info,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors()
        )

    stmt = (select(UserProfileModel).
            where(UserProfileModel.user_id == current_user.id))
    result = await db.execute(stmt)
    user_profile = result.scalar_one_or_none()

    if user_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a profile"
        )

    avatar_key: Optional[str] = None

    if avatar:
        content = await avatar.read()
        _validate_avatar(avatar, content)

        content_type = avatar.content_type
        if not content_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file content type"
            )

        avatar_key = await asyncio.to_thread(
            storage_service.upload_avatar, content,
            current_user.id,
            content_type
        )
    try:
        profile = UserProfileModel(
            user_id=current_user.id,
            avatar=avatar_key,
            **profile_data.model_dump()
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    except SQLAlchemyError as e:
        await db.rollback()

        if avatar_key:
            await asyncio.to_thread(storage_service.delete_avatar, avatar_key)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong during profile creation."
                   " Please try again later"
        ) from e

    avatar_url = None
    if profile.avatar:
        avatar_url = await asyncio.to_thread(storage_service.get_avatar_url,
                                             profile.avatar)

    return _build_profile_response(profile, avatar_url)


@router.get("/me/",
            response_model=UserProfileResponse,
            status_code=status.HTTP_200_OK)
async def get_user_profile(
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    stmt = select(UserProfileModel).where(
        UserProfileModel.user_id == current_user.id)
    result = await db.execute(stmt)
    user_profile = result.scalar_one_or_none()

    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_BAD_REQUEST,
            detail="You have no profile yet."
                   " Try creating profile visiting /profile/create/ endpoint"
        )

    avatar_url = None
    if user_profile.avatar:
        avatar_url = await asyncio.to_thread(storage_service.get_avatar_url,
                                             user_profile.avatar)

    return _build_profile_response(user_profile, avatar_url)


@router.patch("/update/",
              response_model=UserProfileResponse,
              status_code=status.HTTP_200_OK)
async def update_user_profile(
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    gender: Optional[GenderEnum] = Form(None),
    date_of_birth: Optional[date] = Form(None),
    info: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (select(UserProfileModel).where
            (UserProfileModel.user_id == current_user.id))
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You don't have a profile yet"
        )

    try:
        update_data = UserProfileUpdateSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors()
        )

    data_dict = update_data.model_dump(exclude_unset=True)
    for key, value in data_dict.items():
        if value is not None:
            setattr(profile, key, value)

    old_avatar_key: Optional[str] = None
    new_avatar_key: Optional[str] = None

    if avatar:
        content = await avatar.read()
        _validate_avatar(avatar, content)

        content_type = avatar.content_type
        if not content_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file content type"
            )

        old_avatar_key = profile.avatar
        new_avatar_key = await asyncio.to_thread(
            storage_service.upload_avatar, content,
            current_user.id,
            content_type
        )
        profile.avatar = new_avatar_key

    try:
        await db.commit()
        await db.refresh(profile)

        if old_avatar_key:
            await asyncio.to_thread(storage_service.delete_avatar,
                                    old_avatar_key)

    except SQLAlchemyError as e:
        await db.rollback()

        if new_avatar_key:
            await asyncio.to_thread(storage_service.delete_avatar,
                                    new_avatar_key)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Try again later"
        ) from e

    avatar_url = None
    if profile.avatar:
        avatar_url = await asyncio.to_thread(storage_service.get_avatar_url,
                                             profile.avatar)

    return _build_profile_response(profile, avatar_url)


@router.delete("/delete/", response_model=MessageResponseSchema)
async def delete_user_profile(
        user_data: UserDeleteRequestSchema,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    if user_data.answer != DeleteProfileQuestionEnum.yes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile deletion was not confirmed"
        )

    if not current_user.verify_password(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password."
        )

    stmt = (select(UserProfileModel).
            where(UserProfileModel.user_id == current_user.id))
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You don't have a profile yet"
        )

    avatar_key = profile.avatar

    try:
        await db.delete(profile)
        await db.commit()

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Please try again later"
        ) from e

    if avatar_key:
        await asyncio.to_thread(storage_service.delete_avatar, avatar_key)

    return MessageResponseSchema(message="Profile successfully deleted")
