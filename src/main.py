from fastapi import FastAPI
from src.config.settings import settings
from src.routes import (auth_router,
                        user_admin_router,
                        movies_router,
                        movies_admin_router,
                        movie_and_user_interaction_router,
                        user_profile_router,
                        user_profile_admin_router,
                        commentary_router,
                        shopping_cart_router,
                        shopping_cart_admin_router,
                        order_router,
                        order_admin_router,
                        payment_router,
                        payment_admin_router)
from src.celery_app import celery_app # noqa

app = FastAPI(
    title="Online Cinema Project",
    description="Description of project"
)

@app.get("/health")
def health():
    return {"status": "ok"}

api_version_prefix = settings.API_V1_STR

app.include_router(payment_admin_router, prefix=f"{api_version_prefix}/admin/payments", tags=["Payment admin"])
app.include_router(payment_router, prefix=f"{api_version_prefix}/payments", tags=["Payment"])
app.include_router(order_router, prefix=f"{api_version_prefix}/orders", tags=["Order"])
app.include_router(order_admin_router, prefix=f"{api_version_prefix}/admin/orders", tags=["Order admin"])
app.include_router(shopping_cart_router, prefix=f"{api_version_prefix}/theater/cart", tags=["Cart"])
app.include_router(shopping_cart_admin_router, prefix=f"{api_version_prefix}/admin/theater/cart", tags=["Cart admin"])
app.include_router(commentary_router, prefix=f"{api_version_prefix}/theater", tags=["Commentary"])
app.include_router(auth_router, prefix=f"{api_version_prefix}/accounts", tags=["Accounts"])
app.include_router(user_admin_router, prefix=f"{api_version_prefix}/admin/accounts", tags=["Accounts admin"])
app.include_router(user_profile_router, prefix=f"{api_version_prefix}/profile", tags=["Profiles"])
app.include_router(user_profile_admin_router, prefix=f"{api_version_prefix}/admin/profile", tags=["Profiles admin"])
app.include_router(movies_router, prefix=f"{api_version_prefix}/theater", tags=["Movies"])
app.include_router(movies_admin_router, prefix=f"{api_version_prefix}/admin/theater", tags=["Movies admin"])
app.include_router(movie_and_user_interaction_router, prefix=f"{api_version_prefix}/theater", tags=["User interaction with movies"])


