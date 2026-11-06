"""Skladna API — a small warehouse service used as the system under test.

The code deliberately contains 11 defects (BUG-01 … BUG-11).
The list and the explanations live in docs/seeded-bugs.md.
The point of the test suite is to find them, not to turn every check green.
"""

import os

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import payments
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
    """Create the tables if they do not exist yet."""
    Base.metadata.create_all(bind=engine)


# Tests switch this off through an environment variable: the test database is
# created by a fixture, not by the application engine.
if os.getenv("SKLADNA_SKIP_INIT") != "1":
    init_db()


def _available(db: Session, product_id: int) -> int:
    """Units actually free to reserve: stock minus active reservations."""
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
    # BUG-10: database connectivity is not checked — the service answers 200
    # even when the database is down. For a load balancer that is a false green.
    return {"status": "ok"}


@app.post("/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductIn, db: Session = Depends(get_db)):
    existing = db.scalar(select(Product).where(Product.sku == payload.sku))
    if existing is not None:
        raise HTTPException(status_code=409, detail="sku already exists")
    # BUG-07: case-sensitive comparison — "abc" and "ABC" create two products
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
        # BUG-06: the raise HTTPException(404) is missing — this crashes with 500
        product_id = product.id

    available = _available(db, product.id)
    # BUG-01: exceeding the available stock is not rejected — stock goes negative
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
    # BUG-03: the active flag is not checked — cancelling twice puts the goods
    # back on the shelf twice and inflates the stock
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
        # BUG-04: the discount is applied to a single unit price — the quantity
        # is never multiplied, so the order total is too low when quantity > 1
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
    # BUG-05: limit + 1 — the client receives one record more than it asked for
    rows = db.scalars(
        select(Order).order_by(Order.id).limit(limit + 1).offset(offset)
    ).all()
    return list(rows)


@app.post("/orders/{order_id}/pay")
def pay_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")

    # BUG-11: neither the current status nor an idempotency key is checked —
    # a repeated call charges the customer twice
    try:
        payment = payments.charge(order.id, order.total_cents)
    except payments.PaymentDeclined as exc:
        raise HTTPException(status_code=402, detail=f"payment declined: {exc}")
    except payments.PaymentUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    order.status = "paid"
    db.commit()
    db.refresh(order)
    return {
        "order_id": order.id,
        "status": order.status,
        "payment_id": payment.get("id"),
    }



