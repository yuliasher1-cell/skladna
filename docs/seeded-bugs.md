# Seeded defects

The code in `app/` deliberately contains 11 defects. This is not "broken code for
the sake of difficulty" — each one is typical for a real warehouse service and is
found by a test, not by reading the code.

10 of the 11 are pinned by tests in `tests/test_bugs.py` (`xfail(strict=True)`).
BUG-10 is verified manually: stop the database and call `/health`.

| # | Where | What is wrong | How it is caught | Priority |
|---|---|---|---|---|
| BUG-01 | `reserve` | A reservation above the free stock is not rejected, stock goes negative | `test_bug01_available_never_negative` | Critical |
| BUG-02 | `ReserveIn` | No `gt=0` constraint: a reservation of `-5` increases available stock | `test_bug02_negative_quantity_rejected` | Critical |
| BUG-03 | `cancel_reservation` | `active` is not checked: a second cancellation restores the goods again | `test_bug03_double_cancel_does_not_inflate_stock` | High |
| BUG-04 | `create_order` | The discount is applied to a unit price, the quantity is never multiplied | `test_bug04_order_total_counts_every_unit` | Critical |
| BUG-05 | `list_orders` | `limit + 1` — the client gets one record more than requested | `test_bug05_pagination_respects_limit` | Medium |
| BUG-06 | `reserve` | `AttributeError` instead of a 404 for an unknown SKU | `test_bug06_reserve_unknown_sku_returns_404` | High |
| BUG-07 | `create_product` | Case-sensitive SKU check: `ABC` and `abc` become two products | `test_bug07_sku_is_case_insensitive` | High |
| BUG-08 | `ProductIn` | A negative price is accepted | `test_bug08_negative_price_rejected` | High |
| BUG-09 | `models` | `datetime.utcnow()` — a naive timestamp with no timezone | `test_bug09_created_at_is_timezone_aware` | Medium |
| BUG-10 | `health` | Database connectivity is not checked: 200 while the database is dead | manually: stop the DB, call `/health` | High |
| BUG-11 | `pay_order` | No idempotency: a repeated payment succeeds | `test_bug11_double_payment_rejected` | Critical |

## How `xfail` is meant to be used

```python
@pytest.mark.xfail(strict=True, reason="BUG-03: a second cancellation restores the goods twice")
```

- the bug is there -> the test fails -> the report shows **XFAIL** (expected failure);
- the bug is fixed -> the test passes -> **XPASS**, and with `strict=True` that is
  a failure of the run.

So you cannot fix a bug and leave the marker behind: CI will not let you. That is
the whole point of a strict `xfail` — the test doubles as documentation that cannot
silently go stale.

