"""Тесты на известные дефекты сервиса.

Каждый помечен xfail(strict=True): пока баг есть — тест «падает ожидаемо»
и в отчёте это XFAIL. Как только баг починят, тест станет XPASS, а с
strict=True это уже ошибка прогона — сигнал убрать маркер.

Так дефект становится зафиксированным в репозитории, а не «известным всем по памяти».
Номер бага совпадает с docs/seeded-bugs.md и с issue в трекере.
"""

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.bug]


@pytest.mark.xfail(strict=True, reason="BUG-01: превышение остатка не отклоняется")
def test_bug01_reserve_more_than_available(client, make_product):
    """BUG-01: резерв больше остатка должен возвращать 409, а не уводить склад в минус."""
    make_product(sku="SKU-B01", stock=2)

    response = client.post("/products/SKU-B01/reserve", json={"quantity": 5})
    # Ожидаем конфликт: свободных единиц всего две
    assert response.status_code in (409, 422), response.text


@pytest.mark.xfail(strict=True, reason="BUG-01: остаток уходит в минус")
def test_bug01_available_never_negative(client, make_product):
    make_product(sku="SKU-B01B", stock=2)

    client.post("/products/SKU-B01B/reserve", json={"quantity": 5})
    available = client.get("/products/SKU-B01B").json()["available"]

    assert available >= 0, f"доступный остаток отрицательный: {available}"


@pytest.mark.xfail(strict=True, reason="BUG-02: отрицательный резерв не отклоняется")
def test_bug02_negative_quantity_rejected(client, make_product):
    make_product(sku="SKU-B02", stock=10)

    response = client.post("/products/SKU-B02/reserve", json={"quantity": -5})

    assert response.status_code == 422, "отрицательное количество должно быть отклонено схемой"


@pytest.mark.xfail(strict=True, reason="BUG-03: повторная отмена возвращает товар дважды")
def test_bug03_double_cancel_does_not_inflate_stock(client, make_product, make_reservation):
    make_product(sku="SKU-B03", stock=10)
    reservation = make_reservation("SKU-B03", quantity=4)

    client.delete(f"/reservations/{reservation['id']}")
    client.delete(f"/reservations/{reservation['id']}")

    stock = client.get("/products/SKU-B03").json()["stock"]
    assert stock == 10, f"остаток раздулся до {stock}"


@pytest.mark.xfail(strict=True, reason="BUG-04: скидка не умножается на количество")
def test_bug04_order_total_counts_every_unit(client, make_product, make_reservation, make_order):
    make_product(sku="SKU-B04", price_cents=10_000, stock=10)
    reservation = make_reservation("SKU-B04", quantity=3)

    order = make_order([reservation["id"]])

    assert order["total_cents"] == 30_000, f"сумма заказа {order['total_cents']} вместо 30000"


@pytest.mark.xfail(strict=True, reason="BUG-05: пагинация отдаёт limit + 1 записей")
def test_bug05_pagination_respects_limit(client, make_product, make_reservation, make_order):
    make_product(sku="SKU-B05", price_cents=1_000, stock=100)
    for _ in range(3):
        reservation = make_reservation("SKU-B05", quantity=1)
        make_order([reservation["id"]])

    response = client.get("/orders", params={"limit": 2})

    assert len(response.json()) == 2, f"пришло {len(response.json())} записей при limit=2"


@pytest.mark.xfail(strict=True, reason="BUG-06: несуществующий SKU даёт 500 вместо 404")
def test_bug06_reserve_unknown_sku_returns_404(client_raw):
    """BUG-06: несуществующий SKU даёт 500 вместо 404 (AttributeError)."""
    response = client_raw.post("/products/NOPE-B06/reserve", json={"quantity": 1})

    assert response.status_code == 404, f"получили {response.status_code}, ожидали 404"


@pytest.mark.xfail(strict=True, reason="BUG-07: SKU регистрозависим, создаются дубли")
def test_bug07_sku_is_case_insensitive(client, make_product):
    make_product(sku="ABC-777")
    response = client.post(
        "/products",
        json={"sku": "abc-777", "name": "Дубль", "price_cents": 100, "stock": 1},
    )

    assert response.status_code == 409, "тот же товар в другом регистре не должен создаваться"


@pytest.mark.xfail(strict=True, reason="BUG-08: отрицательная цена принимается")
def test_bug08_negative_price_rejected(client):
    response = client.post(
        "/products",
        json={"sku": "SKU-B08", "name": "Брак", "price_cents": -500, "stock": 1},
    )

    assert response.status_code == 422, "отрицательная цена должна отклоняться валидацией"


@pytest.mark.xfail(strict=True, reason="BUG-09: created_at без часового пояса")
def test_bug09_created_at_is_timezone_aware(client, make_product, make_reservation):
    make_product(sku="SKU-B09")
    reservation = make_reservation("SKU-B09")

    created_at = reservation["created_at"]

    assert created_at.endswith("Z") or "+" in created_at[10:], (
        f"время без таймзоны: {created_at}"
    )


@pytest.mark.xfail(strict=True, reason="BUG-11: повторная оплата проходит без ошибки")
def test_bug11_double_payment_rejected(client, make_product, make_reservation, make_order):
    make_product(sku="SKU-B11", price_cents=5_000, stock=5)
    reservation = make_reservation("SKU-B11", quantity=1)
    order = make_order([reservation["id"]])

    first = client.post(f"/orders/{order['id']}/pay")
    second = client.post(f"/orders/{order['id']}/pay")

    assert first.status_code == 200
    assert second.status_code == 409, "заказ уже оплачен — повторное списание недопустимо"



