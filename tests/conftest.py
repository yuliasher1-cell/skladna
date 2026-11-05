"""Общие фикстуры для всех тестов.

Здесь живут три вещи, без которых тесты становятся хрупкими:
  1. изолированная база на каждый тест (in-memory SQLite);
  2. подмена зависимости get_db, чтобы приложение работало с этой базой;
  3. фабрики — помощники, создающие данные, а не копипаста JSON в каждом тесте.
"""

import os
import sys
from pathlib import Path

# Отключаем автосоздание рабочей базы до импорта приложения.
os.environ["SKLADNA_SKIP_INIT"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Чтобы `import app` работал при запуске pytest из любой папки.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def engine():
    """Свежая in-memory база на каждый тест: тесты не видят данных друг друга."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # один и тот же коннект на все запросы
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(engine):
    """Прямой доступ к базе — для проверок в обход API."""
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine):
    """HTTP-клиент к приложению, подключённый к тестовой базе."""
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
    """Второй клиент: не пробрасывает исключения сервера наружу.

    Обычный TestClient при ошибке внутри эндпоинта поднимает исключение прямо
    в тесте — удобно для отладки, но прячет реальный ответ 500. Этот клиент
    ведёт себя как настоящий клиент и показывает, что увидел бы пользователь.
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


@pytest.fixture()
def make_product(client):
    """Фабрика товара: значения по умолчанию + возможность переопределить любое поле."""

    def _make(sku: str = "SKU-001", name: str = "Ноутбук", price_cents: int = 100_000, stock: int = 10):
        response = client.post(
            "/products",
            json={"sku": sku, "name": name, "price_cents": price_cents, "stock": stock},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture()
def make_reservation(client):
    """Фабрика резерва по SKU."""

    def _make(sku: str, quantity: int = 1):
        response = client.post(f"/products/{sku}/reserve", json={"quantity": quantity})
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture()
def make_order(client):
    """Фабрика заказа из готовых резервов."""

    def _make(reservation_ids: list[int], discount_percent: int = 0):
        response = client.post(
            "/orders",
            json={"reservation_ids": reservation_ids, "discount_percent": discount_percent},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make


