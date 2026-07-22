from fastapi import FastAPI
from src.routes import (auth_router,
                        user_admin_router,
                        movies_router,
                        movies_admin_router,
                        movie_and_user_interaction_router,
                        user_profile_router,
                        user_profile_admin_router)
from fastapi.staticfiles import StaticFiles
from src.celery_app import celery_app # noqa

app = FastAPI(
    title="Online Cinema Project",
    description="Description of project"
)

api_version_prefix = "/api/v1"

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth_router, prefix=f"{api_version_prefix}/accounts", tags=["Accounts"])
app.include_router(user_admin_router, prefix=f"{api_version_prefix}/admin/accounts", tags=["Accounts admin"])
app.include_router(user_profile_router, prefix=f"{api_version_prefix}/profile", tags=["Profiles"])
app.include_router(user_profile_admin_router, prefix=f"{api_version_prefix}/admin/profile", tags=["Profiles admin"])
app.include_router(movies_router, prefix=f"{api_version_prefix}/theater", tags=["Movies"])
app.include_router(movies_admin_router, prefix=f"{api_version_prefix}/admin/theater", tags=["Movies admin"])
app.include_router(movie_and_user_interaction_router, prefix=f"{api_version_prefix}/theater", tags=["User interaction with movies"])


