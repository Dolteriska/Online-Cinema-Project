from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import UserModel
from src.database.models.movies import Movie
from src.schemas.movies_schema import MovieInShoppingCartResponseSchema
from src.database.models.movie_interactions import MoviePurchase
from src.database.models.carts import Cart, CartItem
from src.config.dependencies import get_current_user
from src.database.session import get_db
from src.schemas.shopping_cart_schema import CartResponseSchema
from src.schemas.users_schema import MessageResponseSchema
router = APIRouter()


async def get_or_create_cart(user_id: int, db: AsyncSession) -> Cart:
    stmt = (
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(
            selectinload(Cart.cart_items)
            .selectinload(CartItem.movie)
            .selectinload(Movie.genres)
        )
        .execution_options(populate_existing=True)
    )
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()

    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.commit()
        result = await db.execute(stmt)
        cart = result.scalar_one()

    return cart


@router.get("/items/", response_model=CartResponseSchema)
async def get_user_cart(
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    cart = await get_or_create_cart(current_user.id, db)

    movie_list = [
        MovieInShoppingCartResponseSchema.model_validate(item.movie)
        for item in reversed(cart.cart_items)
    ]

    return CartResponseSchema(movies=movie_list)


@router.post("/items/",
             response_model=MessageResponseSchema,
             status_code=status.HTTP_201_CREATED)
async def add_movie_to_cart(
        movie_id: int,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    cart = await get_or_create_cart(current_user.id, db)

    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with given ID was not found"
        )

    stmt_purchase = select(MoviePurchase).where(
        MoviePurchase.user_id == current_user.id,
        MoviePurchase.movie_id == movie_id
    )
    result_purchase = await db.execute(stmt_purchase)
    already_purchased = result_purchase.scalar_one_or_none()

    if already_purchased:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already purchased this movie"
        )

    stmt_item = select(CartItem).where(
        CartItem.cart_id == cart.id,
        CartItem.movie_id == movie_id
    )
    result_item = await db.execute(stmt_item)
    existing_item = result_item.scalar_one_or_none()

    if existing_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie is already in your cart"
        )
    new_cart_item = CartItem(
        cart_id=cart.id,
        movie_id=movie.id
    )
    try:
        db.add(new_cart_item)
        await db.commit()

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong, try again later"
        ) from e

    return MessageResponseSchema(message="Movie added to cart successfully")


@router.delete("/items/", response_model=MessageResponseSchema)
async def delete_movie_from_cart(
        movie_id: int,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    cart = await get_or_create_cart(current_user.id, db)

    stmt_item = select(CartItem).where(
        CartItem.cart_id == cart.id,
        CartItem.movie_id == movie_id
    )
    result_item = await db.execute(stmt_item)
    existing_item = result_item.scalar_one_or_none()

    if not existing_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with given ID was not found in your cart"
        )

    try:
        await db.delete(existing_item)
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Please try again later"
        ) from e

    return MessageResponseSchema(message="Movie was successfully"
                                         " removed from your cart")


@router.delete("/items/clear/", response_model=MessageResponseSchema)
async def clear_cart(
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    cart = await get_or_create_cart(current_user.id, db)

    try:
        stmt = delete(CartItem).where(CartItem.cart_id == cart.id)
        await db.execute(stmt)
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Please try again later"
        ) from e

    return MessageResponseSchema(message="You have successfully"
                                         " cleared you shopping cart")
