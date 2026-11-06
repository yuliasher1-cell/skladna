"""Client for the external payment provider.

The provider is a third-party HTTP service: it can be slow, it can decline a
card, and it can be down. All of that is handled here so the endpoint itself
stays readable. Every failure mode has its own exception, which lets the API
translate them into different HTTP statuses.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://payments.local"
CHARGE_PATH = "/v1/charges"
DEFAULT_TIMEOUT = "5"


class PaymentError(Exception):
    """Base class for every payment problem."""


class PaymentDeclined(PaymentError):
    """The provider refused the charge: insufficient funds, blocked card..."""


class PaymentUnavailable(PaymentError):
    """The provider could not be reached or answered with a server error."""


def _decline_reason(response: httpx.Response) -> str:
    """The provider puts the reason in the JSON body, but is not always nice about it."""
    try:
        return response.json().get("reason", "declined")
    except ValueError:
        return response.text or "declined"


def charge(order_id: int, amount_cents: int, currency: str = "CZK") -> dict:
    """Charge the customer for one order. Returns the provider's response body.

    Raises PaymentDeclined when the provider refuses, PaymentUnavailable when it
    cannot be reached or fails on its side.
    """
    base_url = os.getenv("PAYMENT_API_URL", DEFAULT_BASE_URL)
    timeout = float(os.getenv("PAYMENT_TIMEOUT", DEFAULT_TIMEOUT))
    payload = {"order_id": order_id, "amount_cents": amount_cents, "currency": currency}

    logger.info("charging order %s: %s %s", order_id, amount_cents, currency)
    try:
        with httpx.Client(base_url=base_url, timeout=timeout) as client:
            response = client.post(CHARGE_PATH, json=payload)
    except httpx.TimeoutException as exc:
        logger.error("payment provider timed out after %ss, order %s", timeout, order_id)
        raise PaymentUnavailable("payment provider timed out") from exc
    except httpx.HTTPError as exc:
        logger.error("payment provider is unreachable, order %s: %s", order_id, exc)
        raise PaymentUnavailable("payment provider is unreachable") from exc

    if response.status_code == 402:
        reason = _decline_reason(response)
        logger.warning("payment declined, order %s: %s", order_id, reason)
        raise PaymentDeclined(reason)

    if response.status_code >= 500:
        logger.error(
            "payment provider returned %s, order %s", response.status_code, order_id
        )
        raise PaymentUnavailable(f"payment provider returned {response.status_code}")

    if response.status_code >= 400:
        logger.error(
            "unexpected provider response %s, order %s", response.status_code, order_id
        )
        raise PaymentUnavailable(f"unexpected provider response {response.status_code}")

    body = response.json()
    logger.info("order %s charged, provider id %s", order_id, body.get("id"))
    return body

