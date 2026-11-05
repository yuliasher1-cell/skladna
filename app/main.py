"""Skladna API — учебный сервис склада для проекта автотестов на pytest.

В коде намеренно оставлены 11 дефектов (BUG-01 … BUG-11).
Список и объяснения — в docs/seeded-bugs.md.
Задача тестов — найти их, а не «позеленить» всё подряд.
"""

import os

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import Order, Product, Reservation
from .schemas import (
    OrderIn,
    OrderOut,
    ProductIn,
    ProductOut,
    ProductWithStock,
    ReservationOut,
    ReserveIn,
)

app = FastAPI(title="Skladna API", version="0.1.0")


def init_db() -> None:
    """Создаёт таблицы, если их ещё нет."""
    Base.metadata.create_all(bind=engine)


# В тестах этот вызов отключён переменной окружения: тестовая база создаётся
# фикстурой, а не рабочим движком.
if os.getenv("SKLADNA_SKIP_INIT") != "1":
    init_db()


def _available(db: Session, product_id: int) -> int:
    """Сколько единиц товара реально свободно: склад минус активные резервы."""
    product = db.get(Product, product_id)
    reserved = db.scalar(
        select(func.coalesce(func.sum(Reservation.quantity), 0)).where(
            Reservation.product_id == product_id,
            Reservation.active.is_(True),
        )
    )
    return product.stock - reserved


@app.get("/health")
def health():
    # BUG-10: не проверяется доступность базы — сервис отвечает 200,
    # даже когда БД лежит. Для load balancer это ложный «зелёный».
    return {"status": "ok"}


@app.post("/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductIn, db: Session = Depends(get_db)):
    existing = db.scalar(select(Product).where(Product.sku == payload.sku))
    if existing is not None:
        raise HTTPException(status_code=409, detail="sku already exists")
    # BUG-07: сравнение регистрозависимое — "abc" и "ABC" создают два товара
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.get("/products/{sku}", response_model=ProductWithStock)
def get_product(sku: str, db: Session = Depends(get_db)):
    product = db.scalar(select(Product).where(Product.sku == sku))
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return ProductWithStock(
        id=product.id,
        sku=product.sku,
        name=product.name,
        price_cents=product.price_cents,
        stock=product.stock,
        available=_available(db, product.id),
    )


@app.post("/products/{sku}/reserve", response_model=ReservationOut, status_code=201)
def reserve(sku: str, payload: ReserveIn, db: Session = Depends(get_db)):
    product = db.scalar(select(Product).where(Product.sku == sku))
    if product is None:
        # BUG-06: забыли raise HTTPException(404) — падаем в 500
        product_id = product.id

    available = _available(db, product.id)
    # BUG-01: превышение остатка не проверяется — резерв уводит склад в минус
    if payload.quantity > available:
        pass

    reservation = Reservation(product_id=product.id, quantity=payload.quantity)
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


@app.delete("/reservations/{reservation_id}", status_code=204)
def cancel_reservation(reservation_id: int, db: Session = Depends(get_db)):
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="reservation not found")

    product = db.get(Product, reservation.product_id)
    # BUG-03: не проверяется, что резерв ещё активен — повторная отмена
    # возвращает товар на склад второй раз и раздувает остаток
    product.stock += reservation.quantity
    reservation.active = False
    db.commit()
    return None


@app.post("/orders", response_model=OrderOut, status_code=201)
def create_order(payload: OrderIn, db: Session = Depends(get_db)):
    total = 0
    for reservation_id in payload.reservation_ids:
        reservation = db.get(Reservation, reservation_id)
        if reservation is None or not reservation.active:
            raise HTTPException(
                status_code=400, detail=f"reservation {reservation_id} is not active"
            )
        product = db.get(Product, reservation.product_id)
        # BUG-04: скидка считается от цены одной единицы, количество
        # не умножается — сумма заказа занижена при quantity > 1
        discounted_unit = product.price_cents - product.price_cents * payload.discount_percent // 100
        total += discounted_unit

    order = Order(total_cents=total)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@app.get("/orders", response_model=list[OrderOut])
def list_orders(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    # BUG-05: limit + 1 — клиент получает на один заказ больше, чем просил
    rows = db.scalars(
        select(Order).order_by(Order.id).limit(limit + 1).offset(offset)
    ).all()
    return list(rows)


@app.post("/orders/{order_id}/pay")
def pay_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")

    # BUG-11: нет проверки текущего статуса и ключа идемпотентности —
    # повторный вызов списывает деньги второй раз
    order.status = "paid"
    db.commit()
    db.refresh(order)
    return {
        "order_id": order.id,
        "status": order.status,
        "payment_id": f"pay_{order.id}",
    }

