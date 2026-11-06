"""Fast smoke checks: the service is up and the main flows still work.

These five run on every commit. They must always be green; if one fails,
there is no point looking further.
"""

import allure
import pytest

pytestmark = pytest.mark.smoke


@allure.story("Health")
@allure.title("Health endpoint answers 200")
@allure.severity(allure.severity_level.CRITICAL)
def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@allure.story("Create")
@allure.title("A product is created and returned with its fields")
@allure.severity(allure.severity_level.CRITICAL)
def test_create_product_returns_created(make_product):
    product = make_product(sku="SKU-100", name="Monitor", price_cents=25_000, stock=5)

    assert product["sku"] == "SKU-100"
    assert product["price_cents"] == 25_000
    assert product["stock"] == 5


@allure.story("Read")
@allure.title("A product is found by SKU together with its availability")
@allure.severity(allure.severity_level.NORMAL)
def test_get_product_by_sku(client, make_product):
    make_product(sku="SKU-101", stock=7)

    response = client.get("/products/SKU-101")

    assert response.status_code == 200
    body = response.json()
    assert body["sku"] == "SKU-101"
    assert body["stock"] == 7
    assert body["available"] == 7


@allure.story("Read")
@allure.title("An unknown SKU answers 404")
@allure.severity(allure.severity_level.NORMAL)
def test_get_unknown_product_returns_404(client):
    response = client.get("/products/NOPE-404")

    assert response.status_code == 404


@allure.story("Availability")
@allure.title("A reservation lowers the available stock")
@allure.severity(allure.severity_level.CRITICAL)
def test_reservation_reduces_available_stock(client, make_product):
    make_product(sku="SKU-102", stock=10)

    reserve = client.post("/products/SKU-102/reserve", json={"quantity": 3})
    assert reserve.status_code == 201

    available = client.get("/products/SKU-102").json()["available"]
    assert available == 7

