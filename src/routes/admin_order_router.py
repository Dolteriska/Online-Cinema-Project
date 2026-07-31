from datetime import datetime
from typing import Optional
from fastapi import (APIRouter,
                     Depends,
                     status,
                     HTTPException,
                     Query,
                     Request)
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import UserModel
from src.database.models.orders import (OrderItem,
                                        Order,
                                        StatusEnum)
from src.schemas.admin_order_schema import (AdminOrderListResponseSchema,
                                            AdminOrderResponseSchema)
from src.config.dependencies import require_admin
from src.database.session import get_db
from src.schemas.users_schema import MessageResponseSchema

router = APIRouter()


@router.get("/list/", response_model=AdminOrderListResponseSchema)
async def get_all_orders(
        request: Request,
        current_admin: UserModel = Depends(require_admin),
        db: AsyncSession = Depends(get_db),
        user_id: Optional[int] = Query(None),
        created_at: Optional[datetime] = Query(None),
        order_status: Optional[StatusEnum] = Query(None),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0)
):
    base_stmt = select(Order).options(selectinload(Order.user),
                                      selectinload(Order.items).
                                      selectinload(OrderItem.movie))

    if user_id:
        base_stmt = base_stmt.filter(Order.user_id == user_id)
    if created_at:
        base_stmt = base_stmt.filter(Order.created_at == created_at)
    if order_status:
        base_stmt = base_stmt.filter(Order.status == order_status)

    result = await db.execute(base_stmt)
    orders = result.scalars().all()

    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(total_stmt)
    total = total_result.scalar_one_or_none() or 0

    if total == 0:
        return AdminOrderListResponseSchema(
            items=[],
            total=total,
            limit=limit,
            offset=offset,
            next=None,
            previous=None,
        )
    paginated_stmt = (
        base_stmt.order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(paginated_stmt)
    orders = result.scalars().all()

    next_offset = offset + limit
    previous_offset = max(offset - limit, 0)

    next_url = str(request.url.include_query_params(
        limit=limit,
        offset=next_offset)) if next_offset < total else None
    previous_url = str(request.url.include_query_params(
        limit=limit,
        offset=previous_offset)) if offset > 0 else None

    return AdminOrderListResponseSchema(
        items=[AdminOrderResponseSchema.model_validate(order)
               for order in orders],
        total=total,
        limit=limit,
        offset=offset,
        next=next_url,
        previous=previous_url,
    )


@router.patch("/{order_id}/cancel/", response_model=MessageResponseSchema)
async def cancel_order_with_id(
        order_id: int,
        current_admin: UserModel = Depends(require_admin),
        db: AsyncSession = Depends(get_db)
):
    stmt = select(Order).where(Order.id == order_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order with given ID was not found"
        )

    try:
        order.status = StatusEnum.CANCELED
        await db.commit()

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Please try again later"
        ) from e

    return MessageResponseSchema(message="Order was canceled successfully")
