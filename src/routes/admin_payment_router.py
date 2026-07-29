from datetime import datetime
from os import environ
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, status, HTTPException, Query, Request
from sqlalchemy import select, func, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv
from src.config.settings import settings
from src.database.models import UserModel, Movie
from src.stripe.stripe_service import StripeService
from src.database.models.orders import OrderItem, Order, StatusEnum
from src.database.models.payment import Payment, PaymentStatusEnum, PaymentItem
from src.schemas.movies_schema import (MovieResponseSchema,
                                       MovieListResponseSchema,
                                       GenreResponse,
                                       StarResponse,
                                       MovieShortResponseSchema,
                                       StarWithMoviesResponse,
                                       MovieDetailResponseSchema,
                                       DirectorResponse,
                                       GenreWithCountResponse,
                                       GenreWithMoviesResponse,
                                       MovieSortBy,
                                       MovieInShoppingCartResponseSchema
                                       )
from src.database.models.movie_interactions import (MoviePurchase,
                                                    FavoriteMovie
                                                    )
from src.database.models.carts import Cart, CartItem
from src.config.dependencies import get_current_user, require_admin
from src.database.session import get_db
from src.tasks.tasks import send_payment_confirmation_email
from src.schemas.admin_payment_schema import AdminPaymentResponseSchema, AdminPaymentListResponseSchema



router = APIRouter()


@router.get("/list/", response_model=AdminPaymentListResponseSchema)
async def get_all_payments(
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_admin: UserModel = Depends(require_admin),
        user_id: Optional[int] = Query(None),
        created_at: Optional[datetime] = Query(None),
        payment_status: Optional[PaymentStatusEnum] = Query(None),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0)
):
    base_stmt = select(Payment).options(selectinload(Payment.user),
                                        selectinload(Payment.items).selectinload(PaymentItem.order_item)
                                        .selectinload(OrderItem.movie).selectinload(Movie.genres))

    if user_id:
        base_stmt = base_stmt.filter(Payment.user_id == user_id)
    if created_at:
        base_stmt = base_stmt.filter(Payment.created_at == created_at)
    if payment_status:
        base_stmt = base_stmt.filter(Payment.status == payment_status)

    result = await db.execute(base_stmt)
    payments = result.scalars().all()

    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(total_stmt)
    total = total_result.scalar_one_or_none() or 0

    if total == 0:
        return AdminPaymentListResponseSchema(
            items=[],
            total=total,
            limit=limit,
            offset=offset,
            next=None,
            previous=None,
        )
    paginated_stmt = (
        base_stmt.order_by(Payment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(paginated_stmt)
    payments = result.scalars().all()

    next_offset = offset + limit
    previous_offset = max(offset - limit, 0)

    next_url = str(request.url.include_query_params(limit=limit, offset=next_offset)) if next_offset < total else None
    previous_url = str(request.url.include_query_params(limit=limit, offset=previous_offset)) if offset > 0 else None

    return AdminPaymentListResponseSchema(
        items=[AdminPaymentResponseSchema.model_validate(payment) for payment in payments],
        total=total,
        limit=limit,
        offset=offset,
        next=next_url,
        previous=previous_url,
    )
