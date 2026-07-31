import stripe
from os import environ
from dotenv import load_dotenv
from typing import List
from stripe.params.checkout import SessionCreateParamsLineItem

load_dotenv()

stripe.api_key = environ.get("STRIPE_SECRET_KEY")


class StripeService:
    @staticmethod
    async def create_checkout_session(
            order_id: int,
            order_items: list,
            success_url: str,
            cancel_url: str
    ) -> str | None:
        line_items: List[SessionCreateParamsLineItem] = []

        for item in order_items:
            unit_amount = int(item.price_at_order * 100)

            line_item: SessionCreateParamsLineItem = {
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": item.movie.name,
                    },
                    "unit_amount": unit_amount,
                },
                "quantity": 1,
            }
            line_items.append(line_item)

        session = await stripe.checkout.Session.create_async(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"order_id": str(order_id)}
        )

        return session.url
