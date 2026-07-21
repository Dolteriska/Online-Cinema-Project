import os
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.database.session import get_db
from src.config.dependencies import get_current_user, require_admin
from src.database.models.users import UserProfileModel
from src.schemas.users_profile_schema import UserProfileCreate, UserProfileResponse, UserProfileUpdateSchema
from src.schemas.admin_profile_schema import AdminUserProfileListResponseSchema
from src.database.models.users import UserModel

router = APIRouter()

UPLOAD_DIR = "static/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)




@router.get("/all/", response_model=AdminUserProfileListResponseSchema, status_code=status.HTTP_200_OK)
async def get_all_profiles(
        request: Request,
        current_admin: UserModel = Depends(require_admin),
        db: AsyncSession = Depends(get_db),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0)
):
    total_stmt = select(func.count()).select_from(UserProfileModel)
    total_result = await db.execute(total_stmt)
    total = total_result.scalar_one()

    stmt = (
        select(
            UserProfileModel.id,
            UserProfileModel.user_id,
            UserProfileModel.first_name,
            UserProfileModel.last_name,
            UserProfileModel.gender,
            UserProfileModel.date_of_birth,
            UserProfileModel.avatar
        )
        .order_by(UserProfileModel.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    profiles = result.mappings().all()

    next_offset = offset + limit
    previous_offset = max(offset - limit, 0)

    next_url = None
    if next_offset < total:
        next_url = str(
            request.url.include_query_params(
                limit=limit,
                offset=next_offset
            )
        )
    previous_url = None
    if offset > 0:
        previous_url = str(
            request.url.include_query_params(
                limit=limit,
                offset=previous_offset,
            )
        )

    return AdminUserProfileListResponseSchema(
        items=[UserProfileResponse.model_validate(profile) for profile in profiles],
        total=total,
        limit=limit,
        offset=offset,
        next=next_url,
        previous=previous_url,
    )



