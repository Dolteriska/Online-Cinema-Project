from fastapi import FastAPI
from src.routes import auth_router, user_admin_router, movies_router, movies_admin_router
from src.celery_app import celery_app # noqa
app = FastAPI(
    title="Online Cinema Project",
    description="Description of project"
)

api_version_prefix = "/api/v1"

app.include_router(auth_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
app.include_router(user_admin_router, prefix=f"{api_version_prefix}/admin/accounts", tags=["user_admin"])
app.include_router(movies_router, prefix=f"{api_version_prefix}/theater", tags=["movies"])
app.include_router(movies_admin_router, prefix=f"{api_version_prefix}/admin/theater", tags=["movie_admin"])



