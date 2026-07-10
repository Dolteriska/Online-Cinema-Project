from fastapi import FastAPI
from src.routes import auth_router, admin_router
from src.celery_app import celery_app # noqa
app = FastAPI(
    title="Online Cinema Project",
    description="Description of project"
)

api_version_prefix = "/api/v1"

app.include_router(auth_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
app.include_router(admin_router, prefix=f"{api_version_prefix}/admin", tags=["admin"])
