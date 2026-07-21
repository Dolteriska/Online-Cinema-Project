import os
import uuid
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database.session import get_db
from src.config.dependencies import get_current_user
from src.database.models.users import UserProfileModel, GenderEnum
from src.schemas.users_profile_schema import UserProfileCreate, UserProfileResponse, UserProfileUpdateSchema
from src.database.models.users import UserModel
from src.schemas.users_schema import MessageResponseSchema

router = APIRouter()

UPLOAD_DIR = "static/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)

#PROFILES


@router.post("/create/", response_model=MessageResponseSchema, status_code=status.HTTP_201_CREATED)
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

    if avatar:
        if not avatar.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        file_ext = avatar.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        content = await avatar.read()
        with open(file_path, "wb") as f:
            f.write(content)

        avatar_path = f"/{UPLOAD_DIR}/{file_name}"

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong during profile creation. Please try again later"
        ) from e

    return MessageResponseSchema(message="Profile created successfully!")



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

    if avatar:
        if not avatar.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        if profile.avatar:
            old_avatar_path = profile.avatar.lstrip("/")
            if os.path.exists(old_avatar_path):
                os.remove(old_avatar_path)

        file_ext = avatar.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        content = await avatar.read()
        with open(file_path, "wb") as f:
            f.write(content)

        profile.avatar = f"/{UPLOAD_DIR}/{file_name}"

    try:
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Try again later"
        ) from e

    return profile





