"""Параметризация: одна проверка — много наборов данных.

Смысл параметризации не в том, чтобы «написать меньше строк», а в том, чтобы
набор данных стал данными: его видно в отчёте, его легко дописать, и упавший
кейс сразу назван по имени (ids), а не «тест номер 47 упал».
"""

import pytest

pytestmark = pytest.mark.regression


# --- 1. Обычный parametrize: вход → ожидаемый выход -------------------------

@pytest.mark.parametrize(
    "payload, expected_available",
    [
        pytest.param(
            {"sku": "P-001", "name": "Ноутбук", "price_cents": 100_000, "stock": 10},
            10,
            id="stock-10",
        ),
        pytest.param(
            {"sku": "P-002", "name": "Мышь", "price_cents": 2_500, "stock": 0},
            0,
            id="out-of-stock",
        ),
        pytest.param(
            {"sku": "P-003", "name": "Монитор", "price_cents": 45_000, "stock": 1},
            1,
            id="last-unit",
        ),
        pytest.param(
            {"sku": "P-004", "name": "Кабель", "price_cents": 150, "stock": 9_999},
            9_999,
            id="large-stock",
        ),
    ],
)
def test_created_product_has_expected_available(client, payload, expected_available):
    created = client.post("/products", json=payload)
    assert created.status_code == 201, created.text

    fetched = client.get(f"/products/{payload['sku']}")

    assert fetched.status_code == 200
    assert fetched.json()["available"] == expected_available


# --- 2. parametrize на количество: свободный остаток уменьшается на сумму ----

@pytest.mark.parametrize("quantities, expected", [
    pytest.param([1], 9, id="one"),
    pytest.param([1, 2], 7, id="two-reservations"),
    pytest.param([3, 3, 3], 1, id="three-reservations"),
], )
def test_available_is_sum_of_reservations(client, make_product, quantities, expected):
    make_product(sku="P-100", stock=10)

    for quantity in quantities:
        response = client.post("/products/P-100/reserve", json={"quantity": quantity})
        assert response.status_code == 201

    assert client.get("/products/P-100").json()["available"] == expected


# --- 3. Невалидные данные: один тест, шесть причин отказа -------------------

@pytest.mark.parametrize(
    "payload, reason",
    [
        pytest.param({"name": "Без SKU", "price_cents": 100}, "нет поля sku", id="missing-sku"),
        pytest.param({"sku": "P-200", "price_cents": 100}, "нет поля name", id="missing-name"),
        pytest.param({"sku": "P-201", "name": "Без цены"}, "нет поля price_cents", id="missing-price"),
        pytest.param(
            {"sku": "P-202", "name": "Строка вместо числа", "price_cents": "дорого"},
            "price_cents не число",
            id="wrong-type",
        ),
        pytest.param(
            {"sku": "P-203", "name": "Дробный остаток", "price_cents": 100, "stock": "много"},
            "stock не число",
            id="wrong-stock-type",
        ),
        pytest.param({"sku": 123, "name": "SKU числом", "price_cents": 100}, "sku не строка", id="sku-as-int"),
    ],
)
def test_invalid_product_payload_rejected(client, payload, reason):
    response = client.post("/products", json=payload)

    assert response.status_code == 422, f"{reason}: получили {response.status_code}"


# --- 4. Несуществующие SKU: проверяем не только код, но и текст ошибки ------

@pytest.mark.parametrize("sku", ["NOPE-1", "nope-2", "НЕТ-3", "0"])
def test_unknown_sku_returns_404_with_detail(client, sku):
    response = client.get(f"/products/{sku}")

    assert response.status_code == 404
    assert response.json()["detail"] == "product not found"


# --- 5. indirect=True: параметризуем не тест, а фикстуру --------------------

@pytest.fixture()
def stocked_product(client, make_product, request):
    """Фикстура, у которой параметр — размер склада.

    С `indirect=True` значение из parametrize уходит в фикстуру, а не в тест.
    Так готовится окружение, а сам тест остаётся коротким.
    """
    return make_product(sku=f"IND-{request.param}", stock=request.param)


@pytest.mark.parametrize("stocked_product", [0, 1, 5, 50], indirect=True)
def test_product_with_various_stock_levels(client, stocked_product):
    sku = stocked_product["sku"]

    body = client.get(f"/products/{sku}").json()

    assert body["stock"] == stocked_product["stock"]
    assert body["available"] == stocked_product["stock"]

