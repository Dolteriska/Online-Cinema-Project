from typing import Optional

from fastapi import APIRouter, Depends, status, HTTPException, Query, Request
from sqlalchemy import select, func
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
from src.schemas.shopping_cart_schema import CartResponseSchema
from src.schemas.users_schema import MessageResponseSchema
router = APIRouter()




@router.get("/items/{user_id}/", response_model=CartResponseSchema)
async def get_user_cart(
        user_id: int,
        current_admin: UserModel = Depends(require_admin),
        db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(
            selectinload(Cart.cart_items)
            .selectinload(CartItem.movie)
            .selectinload(Movie.genres)
        )
    )
    result = await db.execute(stmt)
    user_cart = result.scalar_one_or_none()

    if not user_cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cart for user with id {user_id} was not found"
        )

    movie_list = [
        MovieInShoppingCartResponseSchema.model_validate(item.movie)
        for item in reversed(user_cart.cart_items)
    ]

    return CartResponseSchema(movies=movie_list)


