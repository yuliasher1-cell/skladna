"""monkeypatch, caplog and capfd — the three tools for everything you cannot see.

Three things are invisible in a normal test but break real systems:
  * time — "this reservation expires in 15 minutes" cannot be tested by waiting;
  * configuration — the timeout, the provider address, the feature flag;
  * logs — the only trace left when something goes wrong in production.

monkeypatch changes any attribute for the duration of one test and puts it back
afterwards. caplog captures log records. capfd captures what the code writes to
stdout.
"""

import logging
from datetime import datetime

import httpx
import pytest
import respx

from app import models, payments

pytestmark = pytest.mark.regression

CHARGE_URL = "http://payments.test/v1/charges"


# --- 1. Freeze time --------------------------------------------------------

def test_created_at_uses_the_frozen_clock(client, monkeypatch):
    """A test must not depend on the wall clock — otherwise it is flaky by design.

    naive_utc_now() is patched to return a known moment, so the assertion is exact
    instead of "somewhere around now".
    """
    frozen = datetime(2026, 3, 14, 9, 26, 53, 589793)
    monkeypatch.setattr(models, "naive_utc_now", lambda: frozen)

    client.post(
        "/products",
        json={"sku": "CLOCK-1", "name": "Frozen", "price_cents": 100, "stock": 1},
    )
    reservation = client.post("/products/CLOCK-1/reserve", json={"quantity": 1})

    assert reservation.status_code == 201
    assert reservation.json()["created_at"] == "2026-03-14T09:26:53.589793"


def test_created_at_returns_to_real_time_after_the_test(client, monkeypatch):
    """monkeypatch undoes itself: the next test sees the real clock again."""
    assert models.naive_utc_now() != datetime(2026, 3, 14, 9, 26, 53)


def test_two_reservations_share_the_frozen_timestamp(client, monkeypatch):
    monkeypatch.setattr(models, "naive_utc_now", lambda: datetime(2026, 1, 1, 12, 0, 0))

    client.post(
        "/products",
        json={"sku": "CLOCK-2", "name": "Same", "price_cents": 100, "stock": 5},
    )
    first = client.post("/products/CLOCK-2/reserve", json={"quantity": 1}).json()
    second = client.post("/products/CLOCK-2/reserve", json={"quantity": 1}).json()

    assert first["created_at"] == second["created_at"]


# --- 2. Patch configuration, not code -------------------------------------

def test_timeout_is_read_from_the_environment(monkeypatch):
    """The timeout comes from config, so the test checks the config is honoured."""
    captured = {}

    class RecordingClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def post(self, path, json):
            return httpx.Response(200, json={"id": "ch_cfg"}, request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(payments.httpx, "Client", RecordingClient)
    monkeypatch.setenv("PAYMENT_TIMEOUT", "0.25")

    payments.charge(order_id=1, amount_cents=500)

    assert captured["timeout"] == 0.25
    assert captured["base_url"] == "http://payments.test"


def test_provider_url_is_read_from_the_environment(monkeypatch):
    captured = {}

    class RecordingClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def post(self, path, json):
            return httpx.Response(200, json={"id": "ch_url"}, request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(payments.httpx, "Client", RecordingClient)
    monkeypatch.setenv("PAYMENT_API_URL", "https://sandbox.payments.test")

    payments.charge(order_id=2, amount_cents=700)

    assert captured["base_url"] == "https://sandbox.payments.test"


# --- 3. Logs: the only trace production leaves behind ---------------------

@respx.mock
def test_successful_charge_is_logged(caplog):
    caplog.set_level(logging.INFO, logger="app.payments")
    respx.post(CHARGE_URL).mock(return_value=httpx.Response(200, json={"id": "ch_log"}))

    payments.charge(order_id=42, amount_cents=1_500)

    messages = [record.message for record in caplog.records]
    assert any("charging order 42" in message for message in messages), messages
    assert any("ch_log" in message for message in messages), messages


@respx.mock
def test_declined_charge_is_logged_as_warning(caplog):
    caplog.set_level(logging.INFO, logger="app.payments")
    respx.post(CHARGE_URL).mock(
        return_value=httpx.Response(402, json={"reason": "insufficient_funds"})
    )

    with pytest.raises(payments.PaymentDeclined):
        payments.charge(order_id=43, amount_cents=900)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "a declined charge must be logged as a warning"
    assert "insufficient_funds" in warnings[0].getMessage()


@respx.mock
def test_timeout_is_logged_as_error_with_the_timeout_value(caplog):
    caplog.set_level(logging.INFO, logger="app.payments")
    respx.post(CHARGE_URL).mock(side_effect=httpx.ReadTimeout("timed out"))

    with pytest.raises(payments.PaymentUnavailable):
        payments.charge(order_id=44, amount_cents=100)

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert errors, "a provider timeout must be logged as an error"
    assert "2.0s" in errors[0].getMessage(), errors[0].getMessage()


def test_unexpected_status_is_logged(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="app.payments")

    class BadClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def post(self, path, json):
            return httpx.Response(418, text="teapot", request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(payments.httpx, "Client", BadClient)

    with pytest.raises(payments.PaymentUnavailable, match="418"):
        payments.charge(order_id=45, amount_cents=100)

    assert any("418" in r.getMessage() for r in caplog.records)


# --- 4. capfd: when the code prints instead of logging --------------------

def test_stdout_can_be_captured(capfd):
    """Legacy code prints. capfd catches it without touching the source."""
    print("legacy report: 3 orders processed")

    captured = capfd.readouterr()

    assert "3 orders processed" in captured.out


# --- 5. Patching a function instead of the network ------------------------

def test_endpoint_returns_502_when_the_client_raises(client, monkeypatch, make_product, make_reservation, make_order):
    """The narrowest mock there is: replace one function, check the translation.

    No respx, no HTTP: the test is about how the endpoint maps an exception to a
    status code, nothing else.
    """
    make_product(sku="MOCK-1", price_cents=1_000, stock=2)
    reservation = make_reservation("MOCK-1", quantity=1)
    order = make_order([reservation["id"]])

    def raise_timeout(*args, **kwargs):
        raise payments.PaymentUnavailable("payment provider timed out")

    monkeypatch.setattr(payments, "charge", raise_timeout)

    response = client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 502
    assert "timed out" in response.json()["detail"]

