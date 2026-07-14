from pydantic import BaseModel, field_validator, model_validator
from src.database.models.movie_interactions import NotificationEnum


class UserNotificationCreateSchema(BaseModel):
    user_id: int
    notification_type: NotificationEnum
    movie_comment_id: int | None = None
    movie_id: int | None = None

    @model_validator(mode='after')
    def validate_notification_consistency(self):
        """Check of a notification type"""

        if self.notification_type in ('COMMENT_REPLY', 'COMMENT_LIKE'):
            if self.movie_comment_id is None:
                raise ValueError(
                    f"type '{self.notification_type}' needs movie_comment_id"
                )
            if self.movie_id is not None:
                raise ValueError(
                    f"type '{self.notification_type}' shouldn't have movie_id"
                )

        elif self.notification_type == 'NEW_RELEASE':
            if self.movie_id is None:
                raise ValueError(
                    "type 'NEW_RELEASE' needs movie_id"
                )
            if self.movie_comment_id is not None:
                raise ValueError(
                    "type 'NEW_RELEASE' shouldn't have movie_comment_id"
                )

        return self
