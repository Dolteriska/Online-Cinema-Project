from typing import Optional
from fastapi import (APIRouter,
                     Depends,
                     status,
                     Query,
                     Request)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.database.session import get_db
from src.config.dependencies import require_admin
from src.database.models.users import UserProfileModel
from src.schemas.users_profile_schema import UserProfileResponse
from src.schemas.admin_profile_schema import AdminUserProfileListResponseSchema
from src.database.models.users import UserModel
import asyncio
from src.services.storage import storage_service

router = APIRouter()


async def resolve_avatars_bulk(avatar_keys: set[str])\
        -> dict[str, Optional[str]]:
    if not avatar_keys:
        return {}
    urls = await asyncio.gather(*[
        asyncio.to_thread(storage_service.get_avatar_url,
                          key) for key in avatar_keys
    ])
    return dict(zip(avatar_keys, urls))


@router.get("/all/",
            response_model=AdminUserProfileListResponseSchema,
            status_code=status.HTTP_200_OK)
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
            UserProfileModel.avatar,
            UserProfileModel.info
        )
        .order_by(UserProfileModel.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    profiles = result.mappings().all()

    avatar_keys = {p["avatar"] for p in profiles if p["avatar"]}
    avatar_urls_map = await resolve_avatars_bulk(avatar_keys)

    items = []
    for profile in profiles:
        profile_dict = dict(profile)
        if profile_dict["avatar"]:
            profile_dict["avatar"] =\
                avatar_urls_map.get(profile_dict["avatar"])
        items.append(UserProfileResponse.model_validate(profile_dict))

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
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next=next_url,
        previous=previous_url,
    )
