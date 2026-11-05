"""Кейсы из внешнего файла: pytest_generate_tests.

Набор данных живёт в CSV, а не в коде. QA может дописать строку в таблицу,
не открывая Python, — и в отчёте появится новый кейс. Так же поступают, когда
тест-кейсы ведут в TestRail или в Google Sheet и выгружают их в файл.
"""

import csv
from pathlib import Path

import pytest

pytestmark = pytest.mark.regression

DATA_FILE = Path(__file__).parent / "data" / "products.csv"


def _load_cases() -> list[dict]:
    with DATA_FILE.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "sku": row["sku"],
            "name": row["name"],
            "price_cents": int(row["price_cents"]),
            "stock": int(row["stock"]),
        }
        for row in rows
    ]


def pytest_generate_tests(metafunc):
    """Хук: если тесту нужна фикстура product_case — подставляем все строки CSV."""
    if "product_case" in metafunc.fixturenames:
        cases = _load_cases()
        metafunc.parametrize(
            "product_case",
            cases,
            ids=[case["sku"] for case in cases],
        )


def test_products_from_csv_roundtrip(client, product_case):
    created = client.post("/products", json=product_case)
    assert created.status_code == 201, created.text

    fetched = client.get(f"/products/{product_case['sku']}")

    assert fetched.status_code == 200
    body = fetched.json()
    assert body["name"] == product_case["name"]
    assert body["price_cents"] == product_case["price_cents"]
    assert body["available"] == product_case["stock"]

