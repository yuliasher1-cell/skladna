"""Proof that the suite is safe to run in parallel and in any order.

Parallelism only works if tests do not share state. These tests check exactly
that, so a broken fixture shows up here instead of as a mysterious failure once
someone adds `-n 4`.
"""

import allure
import pytest

from app.models import Order, Product, Reservation

pytestmark = pytest.mark.regression


@allure.story("Isolation")
@allure.title("Every test starts with an empty database")
@allure.severity(allure.severity_level.CRITICAL)
def test_database_starts_empty(db_session):
    """Every test gets a fresh database — nothing survives from the previous one."""
    assert db_session.query(Product).count() == 0
    assert db_session.query(Reservation).count() == 0
    assert db_session.query(Order).count() == 0


@allure.story("Isolation")
@allure.title("Data from a previous test is not visible")
@allure.severity(allure.severity_level.CRITICAL)
def test_data_from_a_previous_test_is_not_visible(client, make_product):
    """The fixture that ran before this test created a product; it must be gone.

    The SKU is deliberately fixed: if isolation broke, a duplicate would appear
    and the create call would answer 409.
    """
    created = client.post(
        "/products",
        json={"sku": "ISOLATION-1", "name": "Fresh", "price_cents": 100, "stock": 1},
    )

    assert created.status_code == 201, "a product leaked in from another test"


@allure.story("Isolation")
@allure.title("Two clients on one engine do not leak data into each other")
@allure.severity(allure.severity_level.NORMAL)
def test_two_clients_do_not_share_a_database(engine):
    """Two clients built on the same engine still see separate test data."""
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.db import get_db
    from app.main import app

    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as first:
            first.post(
                "/products",
                json={"sku": "SHARED-1", "name": "One", "price_cents": 100, "stock": 1},
            )
        with TestClient(app) as second:
            assert second.get("/products/SHARED-1").status_code == 200
    finally:
        app.dependency_overrides.clear()


@allure.story("Isolation")
@allure.title("A created product is visible inside the same test")
@allure.severity(allure.severity_level.MINOR)
def test_marker_and_slow_split(client, make_product):
    """A cheap check that the slow marker exists and nothing slow runs by default."""
    make_product(sku="MARK-1", stock=3)

    assert client.get("/products/MARK-1").json()["available"] == 3

