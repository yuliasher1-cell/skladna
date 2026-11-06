"""Parametrization: one check, many data sets.

The point of parametrization is not "fewer lines". It turns a data set into
data: it shows up in the report, it is easy to extend, and a failing case is
named by its id instead of "test number 47 failed".
"""

import allure
import pytest

pytestmark = pytest.mark.regression


# --- 1. Plain parametrize: input -> expected output --------------------------

@pytest.mark.parametrize(
    "payload, expected_available",
    [
        pytest.param(
            {"sku": "P-001", "name": "Laptop", "price_cents": 100_000, "stock": 10},
            10,
            id="stock-10",
        ),
        pytest.param(
            {"sku": "P-002", "name": "Mouse", "price_cents": 2_500, "stock": 0},
            0,
            id="out-of-stock",
        ),
        pytest.param(
            {"sku": "P-003", "name": "Monitor", "price_cents": 45_000, "stock": 1},
            1,
            id="last-unit",
        ),
        pytest.param(
            {"sku": "P-004", "name": "Cable", "price_cents": 150, "stock": 9_999},
            9_999,
            id="large-stock",
        ),
    ],
)
@allure.story("Availability")
@allure.title("A created product exposes the expected availability")
@allure.severity(allure.severity_level.NORMAL)
def test_created_product_has_expected_available(client, payload, expected_available):
    created = client.post("/products", json=payload)
    assert created.status_code == 201, created.text

    fetched = client.get(f"/products/{payload['sku']}")

    assert fetched.status_code == 200
    assert fetched.json()["available"] == expected_available


# --- 2. Parametrize on quantity: available drops by the total reserved -------

@pytest.mark.parametrize("quantities, expected", [
    pytest.param([1], 9, id="one"),
    pytest.param([1, 2], 7, id="two-reservations"),
    pytest.param([3, 3, 3], 1, id="three-reservations"),
], )
@allure.story("Availability")
@allure.title("Available stock is the sum of all active reservations")
@allure.severity(allure.severity_level.NORMAL)
def test_available_is_sum_of_reservations(client, make_product, quantities, expected):
    make_product(sku="P-100", stock=10)

    for quantity in quantities:
        response = client.post("/products/P-100/reserve", json={"quantity": quantity})
        assert response.status_code == 201

    assert client.get("/products/P-100").json()["available"] == expected


# --- 3. Invalid payloads: one test, six reasons to reject -------------------

@pytest.mark.parametrize(
    "payload, reason",
    [
        pytest.param({"name": "No SKU", "price_cents": 100}, "sku field missing", id="missing-sku"),
        pytest.param({"sku": "P-200", "price_cents": 100}, "name field missing", id="missing-name"),
        pytest.param({"sku": "P-201", "name": "No price"}, "price field missing", id="missing-price"),
        pytest.param(
            {"sku": "P-202", "name": "String instead of a number", "price_cents": "expensive"},
            "price_cents is not a number",
            id="wrong-type",
        ),
        pytest.param(
            {"sku": "P-203", "name": "Fractional stock", "price_cents": 100, "stock": "plenty"},
            "stock is not a number",
            id="wrong-stock-type",
        ),
        pytest.param({"sku": 123, "name": "SKU as int", "price_cents": 100}, "sku is not a string", id="sku-as-int"),
    ],
)
@allure.story("Validation")
@allure.title("An invalid product payload is rejected with 422")
@allure.severity(allure.severity_level.NORMAL)
def test_invalid_product_payload_rejected(client, payload, reason):
    response = client.post("/products", json=payload)

    assert response.status_code == 422, f"{reason}: got {response.status_code}"


# --- 4. Unknown SKUs: assert on the code and on the message -----------------

@pytest.mark.parametrize("sku", ["NOPE-1", "nope-2", "NONE-3", "0"])
@allure.story("Validation")
@allure.title("An unknown SKU returns 404 with a readable detail")
@allure.severity(allure.severity_level.MINOR)
def test_unknown_sku_returns_404_with_detail(client, sku):
    response = client.get(f"/products/{sku}")

    assert response.status_code == 404
    assert response.json()["detail"] == "product not found"


# --- 5. indirect=True: parametrize the fixture, not the test -----------------

@pytest.fixture()
def stocked_product(client, make_product, request):
    """A fixture whose parameter is the stock level.

    With indirect=True the value from parametrize goes into the fixture, not
    into the test. That way the setup is described by the parameter while the
    test itself stays short.
    """
    return make_product(sku=f"IND-{request.param}", stock=request.param)


@pytest.mark.parametrize("stocked_product", [0, 1, 5, 50], indirect=True)
@allure.story("Availability")
@allure.title("Stock and availability are equal before any reservation")
@allure.severity(allure.severity_level.NORMAL)
def test_product_with_various_stock_levels(client, stocked_product):
    sku = stocked_product["sku"]

    body = client.get(f"/products/{sku}").json()

    assert body["stock"] == stocked_product["stock"]
    assert body["available"] == stocked_product["stock"]

