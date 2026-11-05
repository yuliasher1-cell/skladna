"""Request and response schemas (input and output validation)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductIn(BaseModel):
    sku: str
    name: str
    # BUG-08: no ge=1 constraint — negative and zero prices are accepted
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
    # BUG-02: no gt=0 constraint — a negative quantity can be reserved
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

