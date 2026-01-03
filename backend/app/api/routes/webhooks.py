"""
Webhook Routes for Telegram and Payment Processors
"""

import hashlib
import hmac
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.config import get_settings

settings = get_settings()
router = APIRouter()


@router.post("/telegram")
async def telegram_webhook(request: Request) -> dict[str, str]:
    """
    Webhook endpoint for Telegram Bot updates.

    This is called by Telegram when the bot receives messages.
    The actual processing is done by aiogram's dispatcher.
    """
    # Verify the request comes from Telegram
    # Telegram sends updates via POST with JSON body

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    # The actual update processing is handled by aiogram
    # This endpoint is just for receiving and forwarding
    # In production, this would be integrated with aiogram's webhook handler

    # For now, just acknowledge receipt
    return {"status": "ok"}


@router.post("/stripe")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """
    Webhook endpoint for Stripe payment events.
    """
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhooks not configured",
        )

    # Get the webhook signature
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature",
        )

    body = await request.body()

    # Verify webhook signature
    try:
        import stripe

        event = stripe.Webhook.construct_event(
            body,
            signature,
            settings.stripe_webhook_secret,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    # Handle the event
    event_type = event["type"]

    if event_type == "checkout.session.completed":
        # Payment successful
        session = event["data"]["object"]
        await _handle_payment_completed(session)

    elif event_type == "customer.subscription.updated":
        # Subscription updated
        subscription = event["data"]["object"]
        await _handle_subscription_updated(subscription)

    elif event_type == "customer.subscription.deleted":
        # Subscription cancelled
        subscription = event["data"]["object"]
        await _handle_subscription_cancelled(subscription)

    elif event_type == "invoice.payment_failed":
        # Payment failed
        invoice = event["data"]["object"]
        await _handle_payment_failed(invoice)

    return {"status": "ok"}


async def _handle_payment_completed(session: dict[str, Any]) -> None:
    """Handle successful payment."""
    # TODO: Implement payment completion logic
    # 1. Find user by customer ID
    # 2. Update subscription status
    # 3. Record payment
    # 4. Send notification
    pass


async def _handle_subscription_updated(subscription: dict[str, Any]) -> None:
    """Handle subscription update."""
    # TODO: Implement subscription update logic
    pass


async def _handle_subscription_cancelled(subscription: dict[str, Any]) -> None:
    """Handle subscription cancellation."""
    # TODO: Implement subscription cancellation logic
    pass


async def _handle_payment_failed(invoice: dict[str, Any]) -> None:
    """Handle failed payment."""
    # TODO: Implement payment failure logic
    # 1. Find user
    # 2. Send notification
    # 3. Mark subscription as past due
    pass


@router.get("/health")
async def webhook_health() -> dict[str, str]:
    """Health check for webhook endpoint."""
    return {"status": "healthy", "service": "webhooks"}
