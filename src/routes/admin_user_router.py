from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


from src.config.dependencies import require_moderator, require_admin
from src.database.models.users import UserModel, UserGroupModel
from src.schemas.admin_user import (AdminUserResponseSchema,
                                    AdminUserListResponseSchema,
                                    AdminUserGroupChangeSchema,
                                    MessageResponseSchema)
from src.database.session import get_db
router = APIRouter()




@router.get("/users/", response_model=AdminUserListResponseSchema)
async def get_user_list(request: Request,
                        db: AsyncSession = Depends(get_db),
                        current_admin: UserModel = Depends(require_admin), # noqa
                        limit: int = Query(default=20, ge=1, le=100),
                        offset: int = Query(default=0, ge=0)
                        ):
    total_stmt = select(func.count()).select_from(UserModel)
    total_result = await db.execute(total_stmt)
    total = total_result.scalar_one()

    stmt = (
        select(
            UserModel.id,
            UserModel.email,
            UserModel.is_active,
            UserGroupModel.name.label("group"),
            UserModel.created_at,
            UserModel.updated_at,
        )
        .join(UserGroupModel, UserModel.group_id == UserGroupModel.id)
        .order_by(UserModel.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    users = result.mappings().all()

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

    return AdminUserListResponseSchema(
        items=[AdminUserResponseSchema.model_validate(user) for user in users],
        total=total,
        limit=limit,
        offset=offset,
        next=next_url,
        previous=previous_url,
    )



@router.get("/users/{user_id}/", response_model=AdminUserResponseSchema)
async def get_user_by_id(user_id: int, db: AsyncSession = Depends(get_db),
                         current_admin: UserModel = Depends(require_admin)): # noqa
    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_BAD_REQUEST,
            detail="User with given id was not found"
        )
    return AdminUserResponseSchema(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        group=user.group.name,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


@router.patch("/users/{user_id}/activate/", response_model=MessageResponseSchema)
async def force_activate_account(user_id: int, db: AsyncSession = Depends(get_db),
                                 current_admin: UserModel = Depends(require_admin)):
    stmt = select(UserModel).options(joinedload(UserModel.activation_token)).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with given id was not found"
        )
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active."
        )


    user.is_active = True

    if user.activation_token:
        await db.delete(user.activation_token)

    await db.commit()

    return MessageResponseSchema(message="User account activated successfully.")



@router.patch("/users/{user_id}/change-group", response_model=MessageResponseSchema)
async def change_user_group(new_role: AdminUserGroupChangeSchema,
                            user_id: int, db: AsyncSession = Depends(get_db),
                            current_user: UserModel = Depends(require_admin),
                            ):
    stmt = (select(UserModel)
            .options(joinedload(UserModel.group))
            .where(UserModel.id == user_id))
    result = await db.execute(stmt)

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="User with given id was not found")

    if user.group.name == new_role.group.name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"This user is already {new_role.group.value}")

    group_stmt = select(UserGroupModel).where(UserGroupModel.name == new_role.group)
    group_result = await db.execute(group_stmt)
    target_group = group_result.scalar_one_or_none()

    if not target_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Target user group was not found")

    user.group = target_group

    await db.commit()
    return MessageResponseSchema(message="User role has been changed successfully")


