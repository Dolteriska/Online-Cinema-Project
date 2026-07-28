import stripe
from decimal import Decimal
from typing import Optional
from os import environ

stripe.api_key = environ.get("STRIPE_SECRET_KEY")


class StripeService:
    @staticmethod
    async def create_checkout_session(
            payment_id: int,
            order_items: list,
            success_url: str,
            cancel_url: str
    ) -> str:
        line_items = []

        for item in order_items:
            unit_amount = int(item.price_at_order * 100)

            line_items.append({
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": item.movie.name,
                    },
                    "unit_amount": unit_amount,
                },
                "quantity": 1,
            })

        session = await stripe.checkout.Session.create_async(
            payment_method_types=["card"],
            line_items=line_items, 
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"payment_id": str(payment_id)}
        )

        return session.url
