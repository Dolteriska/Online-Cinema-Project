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
                                               CommentCreateSchema)
from src.schemas.users_profile_schema import UserProfileShortResponse

router = APIRouter()


@router.get("/movies/{movie_id}/comments/", response_model=List[CommentReadSchema])
async def get_movie_comments_tree(
        movie_id: int,
        db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(MovieComment)
        .where(MovieComment.movie_id == movie_id)
        .options(
            joinedload(MovieComment.user).joinedload(UserModel.profile)
        )
        .order_by(MovieComment.created_at.asc())
    )

    result = await db.execute(stmt)
    all_comments = result.scalars().unique().all()

    if not all_comments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The movie with given ID has no comments yet or does not exist"
        )

    nodes_map: dict[int, CommentReadSchema] = {}
    root_comments: list[CommentReadSchema] = []

    for comment in all_comments:
        comment_dict = {
            "id": comment.id,
            "text": comment.text,
            "created_at": comment.created_at,
            "is_deleted": comment.is_deleted,
            "user": UserProfileShortResponse(id=comment.user_id,
                                             first_name=comment.user.profile.first_name,
                                             last_name=comment.user.profile.last_name,
                                             avatar=comment.user.profile.avatar),
            "likes_count": getattr(comment, "likes_count", 0),
            "dislikes_count": getattr(comment, "dislikes_count", 0),
            "my_reaction": getattr(comment, "my_reaction", None),
            "replies": []
        }

        node = CommentReadSchema.model_validate(comment_dict)
        nodes_map[comment.id] = node

    for comment in all_comments:
        node = nodes_map[comment.id]
        if comment.parent_id is None:
            root_comments.append(node)
        else:
            parent_node = nodes_map.get(comment.parent_id)
            if parent_node:
                parent_node.replies.append(node)

    root_comments.reverse()

    return root_comments


@router.post("/movies/{movie_id}/comments/", response_model=CommentReadSchema, status_code=status.HTTP_201_CREATED)
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
            joinedload(MovieComment.user)
            .joinedload(UserModel.profile),
            selectinload(MovieComment.replies)
        )
        .where(MovieComment.id == new_comment.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()

@router.post("/comments/{comment_id}/replies/", response_model=CommentReadSchema, status_code=status.HTTP_201_CREATED)
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
            joinedload(MovieComment.user).joinedload(UserModel.profile),
            selectinload(MovieComment.replies)
        )
        .where(MovieComment.id == new_reply.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()
