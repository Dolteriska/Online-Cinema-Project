from fastapi import APIRouter, Depends, status, HTTPException, Query, Request, Path
from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional, List
from decimal import Decimal
from src.config.dependencies import get_current_user, require_profile
from src.database.models import MovieComment
from src.database.models.movie_interactions import (FavoriteMovie,
                                                    ReactionEnum,
                                                    MovieReaction,
                                                    MovieRating)
from src.database.models.users import UserModel, UserProfileModel
from src.database.models.movies import Movie
from src.database.session import get_db
from src.schemas.movie_comments_schema import (CommentReadSchema,
                                               CommentCreateSchema, CommentReplyReadSchema)

router = APIRouter()


@router.get("/movies/{movie_id}/comments/", response_model=List[CommentReadSchema])
async def get_movie_comments(
        movie_id: int,
        db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(MovieComment)
        .where(
            MovieComment.movie_id == movie_id,
            MovieComment.parent_id.is_(None)
        )
        .options(
            joinedload(MovieComment.user).joinedload(UserModel.profile),
            selectinload(MovieComment.replies)
            .joinedload(MovieComment.user)
            .joinedload(UserModel.profile)
        )
        .order_by(MovieComment.created_at.desc())
    )
    result = await db.execute(stmt)
    comments = result.scalars().unique().all()

    if not comments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The movie with given ID has no comments yet or does not exist"
        )

    return comments


@router.post("/movies/{movie_id}/comments/", response_model=CommentReadSchema)
async def create_movie_comment(
        movie_id: int,
        comment_data: CommentCreateSchema,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(require_profile)
):
    new_comment = MovieComment(
        user_id=current_user.id,
        movie_id=movie_id,
        parent_id=None,
        text=comment_data.text
    )

    try:
        db.add(new_comment)
        await db.commit()
        await db.refresh(new_comment)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong during comment creation"
        ) from e

    stmt = (
        select(MovieComment)
        .options(
            joinedload(MovieComment.user).joinedload(UserModel.profile)
        )
        .where(MovieComment.id == new_comment.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()

@router.post("/comments/{comment_id}/replies/", response_model=CommentReplyReadSchema)
async def create_comment_reply(
    comment_id: int,
    reply_data: CommentCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_profile)
):
    stmt = select(MovieComment).where(MovieComment.id == comment_id)
    result = await db.execute(stmt)
    parent_comment = result.scalar_one_or_none()
    if not parent_comment or parent_comment.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent comment was not found or has been deleted"
        )

    new_reply = MovieComment(
        user_id=current_user.id,
        movie_id=parent_comment.movie_id,
        parent_id=parent_comment.id,
        text=reply_data.text
    )

    try:
        db.add(new_reply)
        await db.commit()
        await db.refresh(new_reply)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong during reply creation"
        ) from e

    stmt = (
        select(MovieComment)
        .options(
            joinedload(MovieComment.user).joinedload(UserModel.profile)
        )
        .where(MovieComment.id == new_reply.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()
