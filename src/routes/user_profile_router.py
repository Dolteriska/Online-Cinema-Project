import asyncio
import os
import uuid
import aiofiles
import aiofiles.os
from pathlib import Path
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.config.settings import settings
from src.database.session import get_db
from src.config.dependencies import get_current_user
from src.database.models.users import UserProfileModel, GenderEnum
from src.schemas.users_profile_schema import UserProfileCreate, UserProfileResponse, UserProfileUpdateSchema, \
    UserDeleteRequestSchema, DeleteProfileQuestionEnum
from src.database.models.users import UserModel
from src.schemas.users_schema import MessageResponseSchema

router = APIRouter()

UPLOAD_DIR = Path("static/avatars").resolve()
os.makedirs(UPLOAD_DIR, exist_ok=True)

#PROFILES


@router.post("/create/", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
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

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == current_user.id)
    result = await db.execute(stmt)
    user_profile = result.scalar_one_or_none()

    if user_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a profile"
        )

    avatar_path: Optional[str] = None
    saved_file_path: Optional[Path] = None

    if avatar:
        if not avatar.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        file_ext = Path(avatar.filename).suffix
        file_name = f"{uuid.uuid4()}{file_ext}"
        saved_file_path = UPLOAD_DIR / file_name

        content = await avatar.read()
        async with aiofiles.open(saved_file_path, "wb") as f:
            await f.write(content)

        avatar_path = f"{settings.BASE_URL}/static/avatars/{file_name}"

    try:
        profile = UserProfileModel(
            user_id=current_user.id,
            avatar=avatar_path,
            **profile_data.model_dump()
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    except SQLAlchemyError as e:
        await db.rollback()

        if saved_file_path and await aiofiles.os.path.exists(saved_file_path):
            await aiofiles.os.remove(saved_file_path)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong during profile creation. Please try again later"
        ) from e

    return profile



@router.get("/me/", response_model=UserProfileResponse, status_code=status.HTTP_200_OK)
async def get_user_profile(
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    stmt = select(UserProfileModel).where(UserProfileModel.user_id == current_user.id)
    result = await db.execute(stmt)
    user_profile = result.scalar_one_or_none()

    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have no profile yet. Try creating profile visiting /profile/create/ endpoint"
        )
    return user_profile


@router.patch("/update/", response_model=UserProfileResponse, status_code=status.HTTP_200_OK)
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
    stmt = select(UserProfileModel).where(UserProfileModel.user_id == current_user.id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You don't have a profile yet"
        )

    old_avatar_path_to_delete: Optional[Path] = None
    if profile.avatar:
        old_avatar_path_to_delete = UPLOAD_DIR / Path(str(profile.avatar)).name

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

    new_file_path: Optional[Path] = None

    if avatar:
        if not avatar.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        file_ext = Path(avatar.filename).suffix
        file_name = f"{uuid.uuid4()}{file_ext}"

        file_path = UPLOAD_DIR / file_name

        content = await avatar.read()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        profile.avatar = f"{settings.BASE_URL}/static/avatars/{file_name}"

    try:
        await db.commit()
        await db.refresh(profile)

        if old_avatar_path_to_delete and await aiofiles.os.path.exists(old_avatar_path_to_delete):
            await aiofiles.os.remove(old_avatar_path_to_delete)

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Try again later"
        ) from e

    return profile


@router.delete("/delete/", response_model=MessageResponseSchema)
async def delete_user_profile(user_data: UserDeleteRequestSchema,
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

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == current_user.id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You don't have a profile yet"
        )

    avatar_value = profile.avatar


    try:
        await db.delete(profile)
        await db.commit()

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Please try again later"
        ) from e

    if avatar_value:
        file_path = (UPLOAD_DIR / Path(avatar_value).name).resolve()

        if UPLOAD_DIR in file_path.parents and file_path.is_file():
            await asyncio.to_thread(file_path.unlink, missing_ok=True)


    return MessageResponseSchema(message="Profile successfully deleted")




