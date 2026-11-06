"""The external payment provider, mocked with respx.

The provider is a third-party service. A test must never call it: that would be
slow, unreliable and could charge a real card. Instead the HTTP layer is
intercepted — and every failure mode the provider can produce is reproduced on
demand: success, a declined card, a timeout, a server error.

The distinction that matters in these tests: a decline is the customer's
problem (402, the order stays unpaid), while a provider outage is ours (502).
"""

import json

import httpx
import pytest
import respx

from app import payments
from app.models import Order

pytestmark = pytest.mark.regression

CHARGE_URL = "http://payments.test/v1/charges"


@pytest.fixture()
def order(client, make_product, make_reservation, make_order):
    """An order ready to be paid: one reservation of one unit."""
    make_product(sku="PAY-1", price_cents=10_000, stock=5)
    reservation = make_reservation("PAY-1", quantity=1)
    return make_order([reservation["id"]])


# --- 1. Happy path ----------------------------------------------------------

@respx.mock
def test_successful_payment_marks_order_paid(client, order):
    route = respx.post(CHARGE_URL).mock(
        return_value=httpx.Response(200, json={"id": "ch_123", "status": "succeeded"})
    )

    response = client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "paid"
    assert body["payment_id"] == "ch_123"
    assert route.call_count == 1


# --- 2. What we actually send to the provider -------------------------------

@respx.mock
def test_payment_payload_sent_to_provider(client, order):
    route = respx.post(CHARGE_URL).mock(
        return_value=httpx.Response(200, json={"id": "ch_124"})
    )

    client.post(f"/orders/{order['id']}/pay")

    payload = json.loads(route.calls[0].request.content)
    assert payload["order_id"] == order["id"]
    assert payload["amount_cents"] == 10_000
    assert payload["currency"] == "CZK"


# --- 3. Declined: the customer's problem, the order stays unpaid ------------

@respx.mock
def test_declined_payment_returns_402_and_keeps_order_unpaid(
    client, order, db_session
):
    respx.post(CHARGE_URL).mock(
        return_value=httpx.Response(402, json={"reason": "insufficient_funds"})
    )

    response = client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 402
    assert "insufficient_funds" in response.json()["detail"]
    # Checked straight in the database: the API has no endpoint for a single order.
    assert db_session.get(Order, order["id"]).status == "created"


# --- 4. Provider timeout: our problem, 502 ----------------------------------

@respx.mock
def test_provider_timeout_returns_502(client, order):
    respx.post(CHARGE_URL).mock(side_effect=httpx.ReadTimeout("timed out"))

    response = client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 502
    assert "timed out" in response.json()["detail"]


# --- 5. Provider server error ----------------------------------------------

@respx.mock
def test_provider_500_returns_502(client, order):
    respx.post(CHARGE_URL).mock(return_value=httpx.Response(500, text="boom"))

    response = client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 502
    assert "500" in response.json()["detail"]


# --- 6. Provider unreachable -----------------------------------------------

@respx.mock
def test_provider_unreachable_returns_502(client, order):
    respx.post(CHARGE_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    response = client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 502
    assert "unreachable" in response.json()["detail"]


# --- 7. Malformed provider response ----------------------------------------

@respx.mock
def test_provider_decline_without_json_body_still_reports_402(client, order):
    respx.post(CHARGE_URL).mock(return_value=httpx.Response(402, text="card blocked"))

    response = client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 402
    assert "card blocked" in response.json()["detail"]


# --- 8. A gap worth knowing about: no retry on a server error --------------

@pytest.mark.xfail(
    strict=True,
    reason="BUG-12: a 500 from the provider is not retried, the customer sees 502",
)
@respx.mock
def test_server_error_is_retried_once(client, order):
    """A single 5xx is usually transient; a charge call is safe to retry once."""
    route = respx.post(CHARGE_URL).mock(
        side_effect=[
            httpx.Response(500, text="boom"),
            httpx.Response(200, json={"id": "ch_retry"}),
        ]
    )

    response = client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 200
    assert route.call_count == 2, f"provider was called {route.call_count} time(s)"


# --- 9. Idempotency key: absent, and that is deliberate --------------------

@pytest.mark.xfail(
    strict=True,
    reason="BUG-11: no Idempotency-Key header, a retry can charge twice",
)
@respx.mock
def test_charge_sends_idempotency_key(client, order):
    route = respx.post(CHARGE_URL).mock(
        return_value=httpx.Response(200, json={"id": "ch_125"})
    )

    client.post(f"/orders/{order['id']}/pay")

    assert "idempotency-key" in {k.lower() for k in route.calls[0].request.headers}


# --- 10. The client itself, without HTTP -----------------------------------

def test_charge_raises_on_decline(monkeypatch):
    """Unit-level check of the client: no FastAPI, no respx, just the function."""

    def fake_post(*args, **kwargs):
        return httpx.Response(402, json={"reason": "expired_card"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with pytest.raises(payments.PaymentDeclined, match="expired_card"):
        payments.charge(order_id=7, amount_cents=100)

