from src.tasks.tasks import send_activation_email

from datetime import datetime, timezone

from fastapi import Query
from typing import cast

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.config.settings import settings

from src.config.dependencies import get_jwt_auth_manager
from src.database.models.users import (UserModel,
                                       UserGroupModel,
                                       UserGroupEnum,
                                       ActivationTokenModel,
                                       RefreshTokenModel)
from src.database.session import get_db
from src.exceptions.security import BaseSecurityError

from src.schemas.users import (UserRegistrationResponseSchema,
                               UserRegistrationRequestSchema,
                               MessageResponseSchema,
                               UserActivationRequestSchema,
                               TokenRefreshResponseSchema,
                               TokenRefreshRequestSchema,
                               UserLoginRequestSchema,
                               UserLoginResponseSchema,
                               PasswordResetRequestSchema, LogoutRequest)
from src.security.interfaces import JWTAuthManagerInterface

router = APIRouter()



@router.post("/register/",
             response_model=UserRegistrationResponseSchema)
async def register_user(user_data: UserRegistrationRequestSchema,
                        db: AsyncSession = Depends(get_db)):
    stmt = select(UserModel).where(UserModel.email == user_data.email)
    result = await db.execute(stmt)
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="User with given email already exists")
    stmt = select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER)
    result = await db.execute(stmt)
    user_group = result.scalars().first()
    if not user_group:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default user group not found"
        )
    try:
        new_user = UserModel.create(
            email=str(user_data.email),
            raw_password=user_data.password,
            group_id=user_group.id,
        )
        db.add(new_user)
        await db.flush()

        activation_token = ActivationTokenModel(user_id=new_user.id)
        db.add(activation_token)

        await db.commit()
        await db.refresh(activation_token)
        await db.refresh(new_user)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user creation."
        ) from e
    else:
        activation_link = f"{settings.BASE_URL}/api/v1/accounts/activate?token={activation_token.token}"


        send_activation_email.delay(
            new_user.email,
            activation_link
        )

        return UserRegistrationResponseSchema.model_validate(new_user)



@router.post("/activate/",
             response_model=MessageResponseSchema)
async def activate_account(activation_data: UserActivationRequestSchema, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(ActivationTokenModel)
        .options(joinedload(ActivationTokenModel.user))
        .join(UserModel)
        .where(UserModel.email == activation_data.email,
               ActivationTokenModel.token == activation_data.token)
    )
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    now_utc = datetime.now(timezone.utc)
    if not token_record or cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc) < now_utc:
        if token_record:
            await db.delete(token_record)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token."
        )

    user = token_record.user
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active."
        )

    user.is_active = True
    await db.delete(token_record)
    await db.commit()

    return MessageResponseSchema(message="User account activated successfully.")

@router.get("/activate/", response_model=MessageResponseSchema)
async def activate_account_via_link(
        token: str = Query(...),
        db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ActivationTokenModel)
        .options(joinedload(ActivationTokenModel.user))
        .where(ActivationTokenModel.token == token)
    )
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    now_utc = datetime.now(timezone.utc)


    if not token_record or token_record.expires_at.replace(tzinfo=timezone.utc) < now_utc:
        if token_record:
            await db.delete(token_record)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token."
        )

    user = token_record.user
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active."
        )

    user.is_active = True
    await db.delete(token_record)
    await db.commit()

    return MessageResponseSchema(message="User account activated successfully.")


@router.post("/refresh/", response_model=TokenRefreshResponseSchema)
async def refresh_access_token(
        token_data: TokenRefreshRequestSchema,
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> TokenRefreshResponseSchema:
    try:
        decoded_token = jwt_manager.decode_refresh_token(token_data.refresh_token)
    except BaseSecurityError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    stmt = select(RefreshTokenModel).filter_by(token=token_data.refresh_token)
    result = await db.execute(stmt)
    refresh_token_record = result.scalars().first()
    if not refresh_token_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found.")

    if decoded_token.get("user_id") != refresh_token_record.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token user mismatch")

    if refresh_token_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired.")

    stmt = select(UserModel).filter_by(id=refresh_token_record.user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    new_access_token = jwt_manager.create_access_token({"user_id": user.id})

    return TokenRefreshResponseSchema(access_token=new_access_token)


@router.post("/login/", response_model=UserLoginResponseSchema)
async def login_user(
    login_data: UserLoginRequestSchema,
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
):
    stmt = select(UserModel).filter_by(email=login_data.email)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.verify_password(login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated."
        )

    jwt_refresh_token = jwt_manager.create_refresh_token({"user_id": user.id})
    jwt_access_token = jwt_manager.create_access_token({"user_id": user.id})

    try:
        refresh_token = RefreshTokenModel.create(
            user_id=user.id,
            days_valid=settings.REFRESH_TOKEN_EXPIRE_DAYS,
            token=jwt_refresh_token
        )
        db.add(refresh_token)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request"
        )

    return UserLoginResponseSchema(
        access_token=jwt_access_token,
        refresh_token=jwt_refresh_token
    )


@router.post("/logout/", status_code=status.HTTP_200_OK)
async def logout(body: LogoutRequest,
                 db: AsyncSession = Depends(get_db)
                 ):
    stmt = select(RefreshTokenModel).where(RefreshTokenModel.token == body.refresh_token)
    result = await db.execute(stmt)
    db_token = result.scalars().first()
    if not db_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Refresh token not found or already invalidated.")

    try:
        await db.delete(db_token)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An error occurred while processing the request")

    return MessageResponseSchema(message="You have been successfully logged out!")




