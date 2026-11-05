# Skladna — фреймворк автотестов на pytest

Учебный складской сервис (FastAPI + SQLAlchemy) и слой автотестов к нему.
Сервис содержит 11 намеренных дефектов, тесты их документируют и находят.

## Что уже работает

- API: товары, резервы, заказы, оплата, пагинация
- 42 теста: **31 passed, 11 xfailed**, прогон ~1 секунда
- Параметризация с `ids`, `indirect=True`, кейсы из CSV через `pytest_generate_tests`
- Изолированная in-memory база на каждый тест — тесты не зависят от порядка запуска
- Фабрики (`make_product`, `make_reservation`, `make_order`) вместо копипасты JSON
- CI в GitHub Actions: матрица Python 3.11 / 3.12 / 3.13, smoke-прогон, отчёт в artifacts

## Запуск

```bash
py -m venv .venv                 # Windows; на macOS/Linux: python3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest
```

Ожидаемый результат:

```
31 passed, 11 xfailed in 1.14s
```

Запустить только smoke-тесты (то, что гоняется в CI на каждый коммит):

```bash
.venv\Scripts\python.exe -m pytest -m smoke
```

Запустить один параметризованный кейс по его id:

```bash
.venv\Scripts\python.exe -m pytest "tests/test_products_parametrized.py::test_created_product_has_expected_available[out-of-stock]"
```

Поднять сам сервис и посмотреть документацию:

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Документация Swagger: http://localhost:8000/docs

## Структура

```
skladna/
├── app/
│   ├── db.py            подключение к БД, зависимость get_db
│   ├── models.py        таблицы: products, reservations, orders
│   ├── schemas.py       Pydantic-схемы запросов и ответов
│   └── main.py          эндпоинты + 11 засеянных дефектов
├── tests/
│   ├── conftest.py                    фикстуры: engine, client, client_raw, фабрики
│   ├── test_smoke.py                  5 быстрых тестов, всегда зелёные
│   ├── test_bugs.py                   11 тестов на дефекты, xfail(strict=True)
│   ├── test_products_parametrized.py  параметризация, indirect, валидация
│   ├── test_csv_cases.py              кейсы из CSV через pytest_generate_tests
│   └── data/products.csv              данные для параметризации
├── docs/
│   └── seeded-bugs.md   таблица дефектов: где, что, как поймать, приоритет
├── .github/workflows/tests.yml        CI: матрица версий Python
├── pytest.ini           маркеры, строгий режим, фильтры предупреждений
├── requirements.txt
├── docker-compose.yml   Postgres + Redis + API для стенда (нужен Docker)
└── Dockerfile
```

## База данных

По умолчанию — SQLite-файл `skladna.db`, ничего устанавливать не надо.
Для PostgreSQL достаточно переменной окружения:

```bash
DATABASE_URL=postgresql+psycopg://skladna:skladna@localhost:5432/skladna pytest
```

## Что добавлено сверх базового pytest

| Приём | Где смотреть |
|---|---|
| Каскад фикстур и изоляция БД на тест | `tests/conftest.py` → `engine`, `client` |
| Подмена зависимости через `dependency_overrides` | `tests/conftest.py` → `client` |
| Два клиента: с пробросом исключений и без | `client` и `client_raw` |
| Фабрики с значениями по умолчанию | `make_product`, `make_reservation`, `make_order` |
| Параметризация с осмысленными `ids` | `tests/test_products_parametrized.py` |
| `indirect=True` — параметр уходит в фикстуру | `stocked_product` в том же файле |
| Кейсы из внешнего CSV | `tests/test_csv_cases.py` → `pytest_generate_tests` |
| Свои маркеры + `--strict-markers` | `pytest.ini`, `pytestmark` в тестах |
| `xfail(strict=True)` как документация дефекта | `tests/test_bugs.py` |
| Понятный вывод при прогоне | `addopts = -ra` в `pytest.ini` |
| CI с матрицей версий и artifacts | `.github/workflows/tests.yml` |

## Про параметризацию коротко

```bash
# все кейсы одного теста
pytest tests/test_products_parametrized.py -v

# один конкретный кейс по id
pytest "tests/test_products_parametrized.py::test_created_product_has_expected_available[out-of-stock]"
```

`ids` в `pytest.param(...)` — это не украшение. Без них упавший кейс называется
`test_created_product_has_expected_available[payload2-0]`, и приходится лезть в код,
чтобы понять, что там за данные. С `id="out-of-stock"` всё видно в отчёте сразу.



