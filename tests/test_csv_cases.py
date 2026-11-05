"""Cases loaded from an external file: pytest_generate_tests.

The data set lives in a CSV instead of the code. A tester can add a row to the
spreadsheet without opening Python, and a new case appears in the report. This
is the same route used when cases live in TestRail or a Google Sheet and are
exported to a file.
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
    """Hook: if a test asks for product_case, feed it every row of the CSV."""
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

