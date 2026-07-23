from fastapi import APIRouter, Depends, status, HTTPException, Query, Request, Path
from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional, List
from decimal import Decimal
from src.config.dependencies import get_current_user, require_profile
from src.database.models import MovieComment, MovieCommentReaction
from src.database.models.movie_interactions import (FavoriteMovie,
                                                    ReactionEnum,
                                                    MovieReaction,
                                                    MovieRating, NotificationEnum)
from src.database.models.users import UserModel, UserProfileModel, UserGroupEnum
from src.database.models.movies import Movie
from src.database.session import get_db
from src.schemas.admin_user_schema import MessageResponseSchema
from src.schemas.movie_comments_schema import (CommentReadSchema,
                                               CommentCreateSchema)
from src.schemas.users_profile_schema import UserProfileShortResponse
from src.tasks.tasks import create_and_send_notification
router = APIRouter()

async def get_comment_response_dto(
    comment_id: int,
    db: AsyncSession,
    current_user_id: Optional[int] = None
) -> CommentReadSchema:
    stmt = (
        select(MovieComment)
        .options(joinedload(MovieComment.user).joinedload(UserModel.profile))
        .where(MovieComment.id == comment_id)
    )
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )

    reactions_stmt = (
        select(
            MovieCommentReaction.reaction,
            func.count(MovieCommentReaction.id)
        )
        .where(MovieCommentReaction.comment_id == comment_id)
        .group_by(MovieCommentReaction.reaction)
    )
    reactions_res = await db.execute(reactions_stmt)
    reactions_count = {react: count for react, count in reactions_res.all()}

    likes_count = reactions_count.get(ReactionEnum.LIKE, 0)
    dislikes_count = reactions_count.get(ReactionEnum.DISLIKE, 0)

    my_reaction = None
    if current_user_id:
        my_reaction_stmt = select(MovieCommentReaction.reaction).where(
            MovieCommentReaction.comment_id == comment_id,
            MovieCommentReaction.user_id == current_user_id
        )
        my_reaction_res = await db.execute(my_reaction_stmt)
        my_reaction = my_reaction_res.scalar_one_or_none()

    comment_dict = {
        "id": comment.id,
        "text": comment.text,
        "created_at": comment.created_at,
        "is_deleted": comment.is_deleted,
        "user": UserProfileShortResponse(
            id=comment.user_id,
            first_name=comment.user.profile.first_name,
            last_name=comment.user.profile.last_name,
            avatar=comment.user.profile.avatar
        ),
        "likes_count": likes_count,
        "dislikes_count": dislikes_count,
        "my_reaction": my_reaction,
        "replies": []
    }

    return CommentReadSchema.model_validate(comment_dict)

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
        is_deleted = comment.is_deleted

        user_data = None
        if not is_deleted and comment.user and comment.user.profile:
            user_data = UserProfileShortResponse(
                id=comment.user_id,
                first_name=comment.user.profile.first_name,
                last_name=comment.user.profile.last_name,
                avatar=comment.user.profile.avatar
            )
        elif is_deleted:
            user_data = UserProfileShortResponse(
                id=0,
                first_name="Deleted",
                last_name=None,
                avatar=None
            )

        comment_dict = {
            "id": comment.id,
            "text": "[Deleted comment]" if is_deleted else comment.text,
            "created_at": comment.created_at,
            "is_deleted": is_deleted,
            "user": user_data,
            "likes_count": 0 if is_deleted else getattr(comment, "likes_count", 0),
            "dislikes_count": 0 if is_deleted else getattr(comment, "dislikes_count", 0),
            "my_reaction": None if is_deleted else getattr(comment, "my_reaction", None),
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

    if parent_comment.user_id != current_user.id:
        create_and_send_notification.delay(
            user_id=parent_comment.user_id,
            notification_type=NotificationEnum.COMMENT_REPLY.value,
            movie_comment_id=new_reply.id,
            movie_id=parent_comment.movie_id,
            extra_text=new_reply.text
        )

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



@router.post("/comments/{comment_id}/{reaction}/", response_model=CommentReadSchema)
async def toggle_comment_reaction(
        comment_id: int,
        reaction: ReactionEnum,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(require_profile)
):
    stmt = select(MovieComment).where(MovieComment.id == comment_id)
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()

    if not comment or comment.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment with given ID was not found or was deleted"
        )

    existing_reaction_stmt = (
        select
        (MovieCommentReaction)
        .where(MovieCommentReaction.comment_id == comment_id,
               MovieCommentReaction.user_id == current_user.id)
    )
    result = await db.execute(existing_reaction_stmt)
    existing_reaction = result.scalar_one_or_none()

    should_notify = False

    if existing_reaction:
        if existing_reaction.reaction == reaction:
            await db.delete(existing_reaction)
        else:
            existing_reaction.reaction = reaction
            if reaction == ReactionEnum.LIKE:
                should_notify = True
    else:
        new_reaction = MovieCommentReaction(
            user_id=current_user.id,
            comment_id=comment_id,
            reaction=reaction
        )
        db.add(new_reaction)
        if reaction == ReactionEnum.LIKE:
            should_notify = True

    try:
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update reaction"
        ) from e


    if should_notify and comment.user_id != current_user.id:
        first_name = await db.scalar(
            select(UserProfileModel.first_name)
            .where(UserProfileModel.user_id == current_user.id)
        )
        liker_name = first_name or "A user"

        create_and_send_notification.delay(
            user_id=comment.user_id,
            notification_type=NotificationEnum.COMMENT_LIKE.value,
            movie_comment_id=comment.id,
            movie_id=comment.movie_id,
            extra_text=f"{liker_name} liked your comment"
        )

    return await get_comment_response_dto(comment_id, db, current_user.id)


@router.delete("/comments/{comment_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
        comment_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(require_profile)
):
    stmt = select(MovieComment).where(MovieComment.id == comment_id)
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )

    is_admin = current_user.group and current_user.group.name == UserGroupEnum.ADMIN

    is_author = comment.user_id == current_user.id

    if not is_author and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this comment"
        )

    if comment.is_deleted:
        return MessageResponseSchema(message="Comment has been deleted already")

    comment.is_deleted = True
    comment.text = "[Deleted comment]"

    try:
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete comment"
        ) from e
