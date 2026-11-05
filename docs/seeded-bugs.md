# Засеянные дефекты

В `app/` намеренно оставлены 11 дефектов. Это не «сломанный код ради сложности» —
каждый баг типичен для реального складского сервиса и находится тестом, а не глазами.

10 из 11 зафиксированы тестами в `tests/test_bugs.py` (маркер `xfail(strict=True)`).
BUG-10 проверяется вручную: нужно остановить базу и посмотреть на `/health`.

| # | Где | Что не так | Как обнаружить | Приоритет |
|---|---|---|---|---|
| BUG-01 | `reserve` | Резерв больше свободного остатка не отклоняется, склад уходит в минус | `test_bug01_available_never_negative` | Critical |
| BUG-02 | `ReserveIn` | Нет ограничения `gt=0`: резерв `-5` увеличивает доступный остаток | `test_bug02_negative_quantity_rejected` | Critical |
| BUG-03 | `cancel_reservation` | Не проверяется `active`: повторная отмена возвращает товар второй раз | `test_bug03_double_cancel_does_not_inflate_stock` | High |
| BUG-04 | `create_order` | Скидка считается от цены единицы, количество не умножается | `test_bug04_order_total_counts_every_unit` | Critical |
| BUG-05 | `list_orders` | `limit + 1` — клиент получает на одну запись больше | `test_bug05_pagination_respects_limit` | Medium |
| BUG-06 | `reserve` | `AttributeError` вместо 404 при неизвестном SKU | `test_bug06_reserve_unknown_sku_returns_404` | High |
| BUG-07 | `create_product` | Регистрозависимая проверка SKU: `ABC` и `abc` — два разных товара | `test_bug07_sku_is_case_insensitive` | High |
| BUG-08 | `ProductIn` | Отрицательная цена принимается | `test_bug08_negative_price_rejected` | High |
| BUG-09 | `models` | `datetime.utcnow()` — наивное время без таймзоны | `test_bug09_created_at_is_timezone_aware` | Medium |
| BUG-10 | `health` | Не проверяется доступность БД: 200 при мёртвой базе | вручную: остановить БД, дёрнуть `/health` | High |
| BUG-11 | `pay_order` | Нет идемпотентности: повторная оплата проходит успешно | `test_bug11_double_payment_rejected` | Critical |

## Правило работы с `xfail`

```python
@pytest.mark.xfail(strict=True, reason="BUG-03: повторная отмена возвращает товар дважды")
```

- баг есть → тест падает → в отчёте **XFAIL** (ожидаемое падение);
- баг починили → тест проходит → **XPASS**, а со `strict=True` это ошибка прогона.

То есть починить баг и не убрать маркер нельзя: CI не пропустит. Это и есть
смысл строгого `xfail` — тест-документация не устаревает молча.

