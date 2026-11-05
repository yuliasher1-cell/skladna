"""Схемы запросов и ответов (валидация на входе и выходе)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductIn(BaseModel):
    sku: str
    name: str
    # BUG-08: нет ограничения ge=1 — отрицательная и нулевая цена проходят
    price_cents: int
    stock: int = 0


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    price_cents: int
    stock: int


class ProductWithStock(ProductOut):
    available: int


class ReserveIn(BaseModel):
    # BUG-02: нет ограничения gt=0 — можно зарезервировать отрицательное число
    quantity: int


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    active: bool
    created_at: datetime


class OrderIn(BaseModel):
    reservation_ids: list[int]
    discount_percent: int = 0


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    total_cents: int
    status: str
    created_at: datetime

