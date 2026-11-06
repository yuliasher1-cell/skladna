"""Shared fixtures for the whole suite.

Three things live here, and without them the tests become brittle:
  1. an isolated database per test (in-memory SQLite);
  2. an override of the get_db dependency so the app talks to that database;
  3. factories — helpers that create data instead of copy-pasted JSON.
"""

import os
import sys
from pathlib import Path

# Disable creation of the production database before the app is imported.
os.environ["SKLADNA_SKIP_INIT"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Make `import app` work no matter which directory pytest is started from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def engine():
    """A fresh in-memory database per test: tests never see each other's data."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one and the same connection for every request
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(engine):
    """Direct database access — for assertions made around the API."""
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine):
    """HTTP client wired to the test database."""
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def client_raw(engine):
    """A second client that does not re-raise server exceptions.

    The regular TestClient propagates an exception from inside the endpoint
    straight into the test — handy for debugging, but it hides the real 500
    response. This one behaves like a real client and shows what a user sees.
    """
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def payment_env(monkeypatch):
    """Point the payment client at a fake host for every test.

    No test may reach the real provider: an unmocked call would fail fast on DNS
    instead of hanging, and the address is the same in every test file.
    """
    monkeypatch.setenv("PAYMENT_API_URL", "http://payments.test")
    monkeypatch.setenv("PAYMENT_TIMEOUT", "2")


@pytest.fixture()
def make_product(client):
    """Product factory: sensible defaults plus the ability to override any field."""

    def _make(sku: str = "SKU-001", name: str = "Laptop", price_cents: int = 100_000, stock: int = 10):
        response = client.post(
            "/products",
            json={"sku": sku, "name": name, "price_cents": price_cents, "stock": stock},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture()
def make_reservation(client):
    """Reservation factory, addressed by SKU."""

    def _make(sku: str, quantity: int = 1):
        response = client.post(f"/products/{sku}/reserve", json={"quantity": quantity})
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture()
def make_order(client):
    """Order factory built from existing reservations."""

    def _make(reservation_ids: list[int], discount_percent: int = 0):
        response = client.post(
            "/orders",
            json={"reservation_ids": reservation_ids, "discount_percent": discount_percent},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make


