"""Tests for the known defects in the service.

Each one is marked xfail(strict=True): while the bug exists the test "fails as
expected" and the report shows XFAIL. The moment the bug is fixed the test
passes, which with strict=True is a failure of the run — the signal to drop the
marker.

This keeps the defect recorded in the repository instead of living in someone's
memory. The bug number matches docs/seeded-bugs.md and the issue in the tracker.
"""

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.bug]


@pytest.mark.xfail(strict=True, reason="BUG-01: over-reserving is not rejected")
def test_bug01_reserve_more_than_available(client, make_product):
    """BUG-01: reserving more than available should return 409, not go negative."""
    make_product(sku="SKU-B01", stock=2)

    response = client.post("/products/SKU-B01/reserve", json={"quantity": 5})
    # Expect a conflict: only two units are free
    assert response.status_code in (409, 422), response.text


@pytest.mark.xfail(strict=True, reason="BUG-01: available stock goes negative")
def test_bug01_available_never_negative(client, make_product):
    make_product(sku="SKU-B01B", stock=2)

    client.post("/products/SKU-B01B/reserve", json={"quantity": 5})
    available = client.get("/products/SKU-B01B").json()["available"]

    assert available >= 0, f"available stock is negative: {available}"


@pytest.mark.xfail(strict=True, reason="BUG-02: a negative reservation is not rejected")
def test_bug02_negative_quantity_rejected(client, make_product):
    make_product(sku="SKU-B02", stock=10)

    response = client.post("/products/SKU-B02/reserve", json={"quantity": -5})

    assert response.status_code == 422, "a negative quantity must be rejected by the schema"


@pytest.mark.xfail(strict=True, reason="BUG-03: a second cancellation restores the goods twice")
def test_bug03_double_cancel_does_not_inflate_stock(client, make_product, make_reservation):
    make_product(sku="SKU-B03", stock=10)
    reservation = make_reservation("SKU-B03", quantity=4)

    client.delete(f"/reservations/{reservation['id']}")
    client.delete(f"/reservations/{reservation['id']}")

    stock = client.get("/products/SKU-B03").json()["stock"]
    assert stock == 10, f"stock was inflated to {stock}"


@pytest.mark.xfail(strict=True, reason="BUG-04: the discount is not multiplied by quantity")
def test_bug04_order_total_counts_every_unit(client, make_product, make_reservation, make_order):
    make_product(sku="SKU-B04", price_cents=10_000, stock=10)
    reservation = make_reservation("SKU-B04", quantity=3)

    order = make_order([reservation["id"]])

    assert order["total_cents"] == 30_000, f"order total is {order['total_cents']}, expected 30000"


@pytest.mark.xfail(strict=True, reason="BUG-05: pagination returns limit + 1 records")
def test_bug05_pagination_respects_limit(client, make_product, make_reservation, make_order):
    make_product(sku="SKU-B05", price_cents=1_000, stock=100)
    for _ in range(3):
        reservation = make_reservation("SKU-B05", quantity=1)
        make_order([reservation["id"]])

    response = client.get("/orders", params={"limit": 2})

    assert len(response.json()) == 2, f"got {len(response.json())} records with limit=2"


@pytest.mark.xfail(strict=True, reason="BUG-06: an unknown SKU returns 500 instead of 404")
def test_bug06_reserve_unknown_sku_returns_404(client_raw):
    """BUG-06: an unknown SKU produces a 500 instead of a 404 (AttributeError)."""
    response = client_raw.post("/products/NOPE-B06/reserve", json={"quantity": 1})

    assert response.status_code == 404, f"got {response.status_code}, expected 404"


@pytest.mark.xfail(strict=True, reason="BUG-07: SKU lookup is case-sensitive, duplicates are created")
def test_bug07_sku_is_case_insensitive(client, make_product):
    make_product(sku="ABC-777")
    response = client.post(
        "/products",
        json={"sku": "abc-777", "name": "Duplicate", "price_cents": 100, "stock": 1},
    )

    assert response.status_code == 409, "the same product in another case must not be created"


@pytest.mark.xfail(strict=True, reason="BUG-08: a negative price is accepted")
def test_bug08_negative_price_rejected(client):
    response = client.post(
        "/products",
        json={"sku": "SKU-B08", "name": "Reject", "price_cents": -500, "stock": 1},
    )

    assert response.status_code == 422, "a negative price must be rejected by validation"


@pytest.mark.xfail(strict=True, reason="BUG-09: created_at has no timezone")
def test_bug09_created_at_is_timezone_aware(client, make_product, make_reservation):
    make_product(sku="SKU-B09")
    reservation = make_reservation("SKU-B09")

    created_at = reservation["created_at"]

    assert created_at.endswith("Z") or "+" in created_at[10:], (
        f"timestamp without a timezone: {created_at}"
    )


@pytest.mark.xfail(strict=True, reason="BUG-11: a second payment succeeds without an error")
def test_bug11_double_payment_rejected(client, make_product, make_reservation, make_order):
    make_product(sku="SKU-B11", price_cents=5_000, stock=5)
    reservation = make_reservation("SKU-B11", quantity=1)
    order = make_order([reservation["id"]])

    first = client.post(f"/orders/{order['id']}/pay")
    second = client.post(f"/orders/{order['id']}/pay")

    assert first.status_code == 200
    assert second.status_code == 409, "the order is already paid — charging again is not allowed"

