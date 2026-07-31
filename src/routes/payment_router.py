from os import environ
import stripe
from fastapi import APIRouter, Depends, status, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv


from src.config.settings import settings
from src.database.models import UserModel, Movie
from src.stripe.stripe_service import StripeService
from src.database.models.orders import OrderItem, Order, StatusEnum
from src.database.models.payment import Payment, PaymentStatusEnum, PaymentItem
from src.database.models.movie_interactions import MoviePurchase
from src.config.dependencies import get_current_user
from src.database.session import get_db
from src.tasks.tasks import send_payment_confirmation_email
from src.schemas.payment_schema import (PaymentListResponseSchema,
                                        PaymentResponseSchema)


load_dotenv()

STRIPE_WEBHOOK_SECRET = environ.get("STRIPE_WEBHOOK_SECRET")


router = APIRouter()


@router.post("/checkout/{order_id}/")
async def create_checkout(
    order_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.user_id == current_user.id)
        .options(selectinload(Order.items).selectinload(OrderItem.movie))
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order with given ID was not found"
        )

    if not order.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your order is empty"
        )

    movie_ids = [item.movie_id for item in order.items if item.movie_id]

    stmt_purchased = select(MoviePurchase.movie_id).where(
        MoviePurchase.user_id == current_user.id,
        MoviePurchase.movie_id.in_(movie_ids)
    )
    already_purchased_ids = (await db.execute(stmt_purchased)).scalars().all()

    if already_purchased_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You already own one or more movies in this order"
                   f" (IDs: {already_purchased_ids})"
        )

    calculated_total = sum(
        (item.price_at_order for item in order.items),
        Decimal("0.00")
    )
    calculated_total = calculated_total.quantize(Decimal("0.01"),
                                                 rounding=ROUND_HALF_UP)

    if calculated_total <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Price of order should be greater than 0"
        )

    if order.total_amount != calculated_total:
        order.total_amount = calculated_total
        await db.commit()

    base_url = getattr(settings, "BASE_URL", "http://127.0.0.1:8000")
    api_prefix = getattr(settings, "API_V1_STR", "/api/v1")

    success_url = (f"{base_url}"
                   f"{api_prefix}"
                   f"/payments/success?session_id={{CHECKOUT_SESSION_ID}}")
    cancel_url = f"{base_url}{api_prefix}/payments/cancel"

    try:
        checkout_url = await StripeService.create_checkout_session(
            order_id=order.id,
            order_items=order.items,
            success_url=success_url,
            cancel_url=cancel_url
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment service error: {str(e)}"
        )

    return {
        "order_id": order.id,
        "amount": order.total_amount,
        "checkout_url": checkout_url
    }


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = getattr(session, "metadata", None)
        payment_intent_id = getattr(session, "payment_intent", None)

        order_id = None
        if metadata:
            try:
                order_id = metadata["order_id"]
            except (KeyError, TypeError):
                order_id = None
        if order_id is not None:
            try:
                order_id = int(order_id)
            except (TypeError, ValueError):
                order_id = None

        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.user),
            )
        )
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()

        if order and order.status != StatusEnum.PAID:
            payment = Payment(
                user_id=order.user_id,
                order_id=order.id,
                amount=order.total_amount,
                status=PaymentStatusEnum.SUCCESSFUL,
                external_payment_id=payment_intent_id
            )
            db.add(payment)
            await db.flush()

            order.status = StatusEnum.PAID

            for item in order.items:
                payment_item = PaymentItem(
                    payment_id=payment.id,
                    order_item_id=item.id,
                    price_at_payment=item.price_at_order
                )
                db.add(payment_item)

                stmt_check = select(MoviePurchase).where(
                    MoviePurchase.user_id == order.user_id,
                    MoviePurchase.movie_id == item.movie_id
                )
                existing_purchase = ((await db.execute(stmt_check))
                                     .scalar_one_or_none())

                if not existing_purchase:
                    movie_purchase = MoviePurchase(
                        user_id=order.user_id,
                        movie_id=item.movie_id,
                        order_id=order.id
                    )
                    db.add(movie_purchase)

            await db.commit()

            print(f"[DEBUG] Sending email to {order.user.email}")
            send_payment_confirmation_email.delay(
                order.user.email,
                f"{settings.BASE_URL}{settings.API_V1_STR}/orders/")
            print("[DEBUG] Task queued")

    elif (event["type"]
          in ["payment_intent.payment_failed", "checkout.session.expired"]):
        session = event["data"]["object"]
        metadata = getattr(session, "metadata", None)
        order_id = None

        if metadata:
            try:
                order_id = metadata["order_id"]

            except (KeyError, TypeError):
                order_id = None

        if order_id is not None:
            try:
                order_id = int(order_id)
            except (TypeError, ValueError):
                order_id = None

        if order_id:
            order_id = int(order_id)
            stmt = select(Order).where(Order.id == order_id)
            result = await db.execute(stmt)
            order = result.scalar_one_or_none()

            if order and order.status != StatusEnum.PAID:
                payment = Payment(
                    user_id=order.user_id,
                    order_id=order.id,
                    amount=order.total_amount,
                    status=PaymentStatusEnum.CANCELED
                )
                db.add(payment)
                await db.commit()

    return {"status": "success"}


@router.get("/me/", response_model=PaymentListResponseSchema)
async def get_payments(
        request: Request,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0)
):
    total_stmt = (
        select(func.count())
        .select_from(Payment)
        .where(Payment.user_id == current_user.id)
    )
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    if total == 0:
        return PaymentListResponseSchema(
            items=[],
            total=0,
            limit=limit,
            offset=offset,
            next=None,
            previous=None,
        )

    stmt = (
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .options(
            selectinload(Payment.items)
            .selectinload(PaymentItem.order_item)
            .selectinload(OrderItem.movie)
            .selectinload(Movie.genres)
        )
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)

    payments = result.scalars().unique().all()

    next_offset = offset + limit
    previous_offset = max(offset - limit, 0)

    next_url = str(request.url.include_query_params(
        limit=limit,
        offset=next_offset)) if next_offset < total else None
    previous_url = str(request.url.include_query_params(
        limit=limit,
        offset=previous_offset)) if offset > 0 else None

    return PaymentListResponseSchema(
        items=[PaymentResponseSchema.model_validate(payment)
               for payment in payments],
        total=total,
        limit=limit,
        offset=offset,
        next=next_url,
        previous=previous_url,
    )


@router.get("/success")
async def payment_success(
    session_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        session = await stripe.checkout.Session.retrieve_async(session_id)
    except stripe.error.InvalidRequestError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id"
        )

    metadata = getattr(session, "metadata", None)
    order_id = None
    if metadata:
        try:
            order_id = int(metadata["order_id"])
        except (KeyError, TypeError, ValueError):
            order_id = None

    if not order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order not found for this session"
        )

    stmt = select(Order).where(Order.id == order_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Order not found"
                            )

    stripe_confirmed = getattr(session, "payment_status", None) == "paid"

    if order.status == StatusEnum.PAID:
        return {"status": "success",
                "order_id": order.id,
                "amount": order.total_amount}

    if stripe_confirmed:
        return {"status": "processing",
                "order_id": order.id,
                "message": "Payment confirmed, finalizing shortly"}

    return {"status": "pending",
            "order_id": order.id,
            "message": "Payment not completed yet"}


@router.get("/cancel")
async def payment_cancel(
    session_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    decline_reason = None
    order_id = None

    if session_id:
        try:
            session = await stripe.checkout.Session.retrieve_async(
                session_id,
                expand=["payment_intent"]
            )
        except stripe.error.InvalidRequestError:
            session = None

        if session:
            metadata = getattr(session, "metadata", None)
            if metadata:
                try:
                    order_id = int(metadata["order_id"])
                except (KeyError, TypeError, ValueError):
                    order_id = None

            payment_intent = getattr(session, "payment_intent", None)
            if payment_intent is not None:
                last_error = getattr(payment_intent,
                                     "last_payment_error",
                                     None)
                if last_error is not None:
                    decline_reason = getattr(last_error, "message", None)

    order = None
    if order_id:
        stmt = select(Order).where(Order.id == order_id)
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()

    if decline_reason:
        message = (
            f"Your payment was declined: {decline_reason}. "
            "Please try a different payment method or contact your bank."
        )
    else:
        message = (
            "Your payment was not completed. "
            "You can try again with the same or a different payment method."
        )

    return {
        "status": "canceled",
        "order_id": order.id if order else order_id,
        "message": message
    }
