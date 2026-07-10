from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.config.settings import settings
from src.database.session import get_db
from src.exceptions.security import BaseSecurityError
from src.database.models.users import UserModel
from src.security.interfaces import JWTAuthManagerInterface
from src.security.token_manager import JWTAuthManager
from src.database.models.users import UserGroupEnum

def get_jwt_auth_manager() -> JWTAuthManagerInterface:
    """
    Create and return a JWT authentication manager instance.

    This function uses the provided application settings to instantiate a JWTAuthManager, which implements
    the JWTAuthManagerInterface. The manager is configured with secret keys for access and refresh tokens
    as well as the JWT signing algorithm specified in the settings.

    Returns:
        JWTAuthManagerInterface: An instance of JWTAuthManager configured with
        the appropriate secret keys and algorithm.
    """
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM
    )


bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserModel:
    token = credentials.credentials

    try:
        payload = jwt_manager.decode_access_token(token)

    except BaseSecurityError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == user_id)
    )

    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active.",
        )

    return user


def require_roles(*allowed_roles: UserGroupEnum):
    async def role_checker(
        current_user: UserModel = Depends(get_current_user),
    ) -> UserModel:
        if current_user.group is None or current_user.group.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_checker


require_admin = require_roles(UserGroupEnum.ADMIN)

require_moderator = require_roles(
    UserGroupEnum.MODERATOR,
    UserGroupEnum.ADMIN,
)
