from fastapi import APIRouter, Depends, status, HTTPException, Query, Request
from sqlalchemy import select, func, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from decimal import Decimal

from src.database.models import UserModel
from src.database.models.orders import OrderItem, Order, StatusEnum
from src.database.models.movie_interactions import MoviePurchase
from src.database.models.carts import Cart, CartItem
from src.config.dependencies import get_current_user
from src.database.session import get_db
from src.schemas.order_schema import (OrderResponseSchema,
                                      OrderListResponseSchema)
from src.schemas.users_schema import MessageResponseSchema

router = APIRouter()


@router.post("/checkout/",
             response_model=OrderResponseSchema,
             status_code=status.HTTP_201_CREATED)
async def make_order(
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    cart_stmt = (select(Cart).where(Cart.user_id == current_user.id).options(
        selectinload(Cart.cart_items).selectinload(CartItem.movie)
    ))
    result = await db.execute(cart_stmt)
    cart = result.scalar_one_or_none()

    if not cart or not cart.cart_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have no cart or your cart is empty."
                   " Try adding new items to the cart"
        )

    purchased_stmt = (select(MoviePurchase.movie_id)
                      .where(MoviePurchase.user_id == current_user.id))
    purchased_result = await db.execute(purchased_stmt)
    purchased_movie_ids = set(purchased_result.scalars().all())

    pending_stmt = (
        select(OrderItem.movie_id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            Order.user_id == current_user.id,
            Order.status == StatusEnum.PENDING
        )
    )
    pending_result = await db.execute(pending_stmt)
    pending_movie_ids = set(pending_result.scalars().all())

    unavailable_movie_ids = purchased_movie_ids.union(pending_movie_ids)

    valid_items = []
    excluded_items = []

    for cart_item in cart.cart_items:
        if cart_item.movie_id in unavailable_movie_ids:
            excluded_items.append(cart_item.movie.name)
        else:
            valid_items.append(cart_item)

    if not valid_items:
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All your films have already"
                   f" been purchased or are already"
                   f" included in one of your pending"
                   f" orders: {', '.join(excluded_items)}"
        )
    total_amount = Decimal("0.00")
    order_items = []

    for item in valid_items:
        total_amount += item.movie.price
        order_items.append(
            OrderItem(
                movie_id=item.movie_id,
                price_at_order=item.movie.price
            )
        )

    new_order = Order(
        user_id=current_user.id,
        status=StatusEnum.PENDING,
        total_amount=total_amount,
        items=order_items
    )

    try:
        db.add(new_order)
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

        await db.commit()
        order_stmt = (
            select(Order)
            .where(Order.id == new_order.id)
            .options(
                selectinload(Order.items).selectinload(OrderItem.movie)
            )
        )
        res = await db.execute(order_stmt)
        order_from_db = res.scalar_one()

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong during order creation"
        ) from e

    return OrderResponseSchema.model_validate(order_from_db)


@router.get("/", response_model=OrderListResponseSchema)
async def get_orders(request: Request,
                     current_user: UserModel = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db),
                     limit: int = Query(default=20, ge=1, le=100),
                     offset: int = Query(default=0, ge=0)
                     ):
    stmt = (select(Order).where
            (Order.user_id == current_user.id)
            .offset(offset)
            .limit(limit)
            .options(selectinload(Order.items).selectinload(OrderItem.movie)))
    result = await db.execute(stmt)
    orders = result.scalars().all()

    if not orders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have no orders yet"
        )

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(total_stmt)
    total = total_result.scalar_one_or_none() or 0

    if total == 0:
        return OrderListResponseSchema(
            items=[],
            total=total,
            limit=limit,
            offset=offset,
            next=None,
            previous=None,
        )

    next_offset = offset + limit
    previous_offset = max(offset - limit, 0)

    next_url = str(request.url.include_query_params(
        limit=limit,
        offset=next_offset)) if next_offset < total else None
    previous_url = str(request.url.include_query_params(
        limit=limit,
        offset=previous_offset)) if offset > 0 else None

    return OrderListResponseSchema(
        items=[OrderResponseSchema.model_validate(order) for order in orders],
        total=total,
        limit=limit,
        offset=offset,
        next=next_url,
        previous=previous_url,
    )


@router.patch("/{order_id}/cancel/", response_model=MessageResponseSchema)
async def cancel_order(
        order_id: int,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    stmt = select(Order).where(
        Order.id == order_id).where(Order.user_id == current_user.id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order with given ID was not found"
        )

    if order.status == StatusEnum.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can't cancel already paid order"
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

    return MessageResponseSchema(message="Your order"
                                         " was canceled successfully")
