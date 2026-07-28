import datetime
from typing import Optional

from fastapi import APIRouter, Depends, status, HTTPException, Query, Request
from sqlalchemy import select, func, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from decimal import Decimal


from src.database.models import UserModel
from src.database.models.movies import (Movie,
                                        Certification,
                                        Genre,
                                        Star,
                                        Director,
                                        movie_genres,
                                        movie_directors,
                                        movie_stars)
from src.database.models.orders import OrderItem, Order, StatusEnum
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
from src.schemas.order_schema import OrderResponseSchema, OrderListResponseSchema
from src.schemas.shopping_cart_schema import CartResponseSchema
from src.schemas.users_schema import MessageResponseSchema

router = APIRouter()



@router.post("/checkout/{order_id}")
async def create_checkout_session(
        order_id: int,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.user_id == current_user.id)
        .options(selectinload(Order.items).selectinload(OrderItem.movie))
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUNDT,
                            detail="Order with given ID was not found")

    if not order.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Your order is empty")



