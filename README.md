# Skladna — pytest test automation framework

A test automation layer for a warehouse/order API, written from scratch with **pytest**.
The service under test is a small FastAPI application that ships with **11 deliberately
seeded defects**; the suite finds them and documents each one as a test.

Built as a portfolio project: fixtures, parametrization, custom markers, strict `xfail`,
data-driven cases from CSV and a CI pipeline across three Python versions.

![tests](https://github.com/yuliasher1-cell/skladna/actions/workflows/tests.yml/badge.svg)

## Test suite at a glance

| Metric | Value |
|---|---|
| Tests collected | 42 |
| Passing | 31 |
| Documented defects (`xfail`) | 11 |
| Full run time | ~1.2 s |
| CI matrix | Python 3.11 / 3.12 / 3.13 |

## What is covered

- **Products** — creation, retrieval by SKU, stock and availability
- **Reservations** — reserving against stock, cancellation, available-stock maths
- **Orders** — building an order from reservations, discounts, pagination
- **Payments** — paying an order
- **Negative paths** — validation errors, unknown SKUs, conflicting data
- **Known defects** — one test per bug, pinned with `xfail(strict=True)`

## Stack

`Python` · `pytest` · `FastAPI` · `SQLAlchemy 2` · `Pydantic 2` · `httpx` · `GitHub Actions`

The database is in-memory SQLite by default, so the suite needs no external services.
Setting `DATABASE_URL` switches it to PostgreSQL without touching a single test.

## Quick start

```bash
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest
```

Expected output:

```
31 passed, 11 xfailed in 1.23s
```

Useful variants:

```bash
# what runs in CI on every commit
.venv\Scripts\python.exe -m pytest -m smoke

# one parametrized case by its id
.venv\Scripts\python.exe -m pytest "tests/test_products_parametrized.py::test_created_product_has_expected_available[out-of-stock]"

# what the suite collects, without running anything
.venv\Scripts\python.exe -m pytest --collect-only -q
```

Run the service itself:

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs

## Structure

```
skladna/
├── app/
│   ├── db.py            engine, session factory, get_db dependency
│   ├── models.py        products, reservations, orders
│   ├── schemas.py       Pydantic request and response models
│   └── main.py          endpoints + 11 seeded defects
├── tests/
│   ├── conftest.py                    fixtures: engine, client, client_raw, factories
│   ├── test_smoke.py                  5 fast tests, always green
│   ├── test_bugs.py                   11 defect tests, xfail(strict=True)
│   ├── test_products_parametrized.py  parametrization, indirect fixtures, validation
│   ├── test_csv_cases.py              data-driven cases via pytest_generate_tests
│   └── data/products.csv              the data set for those cases
├── docs/
│   └── seeded-bugs.md   every defect: where, what, how to catch it, priority
├── .github/workflows/tests.yml        CI across three Python versions
├── pytest.ini           markers, strict mode, warning filters
├── requirements.txt
├── docker-compose.yml   Postgres + Redis + API for a local stand
└── Dockerfile
```

## Techniques demonstrated

| Technique | Where to look |
|---|---|
| Fixture cascade and database isolation per test | `tests/conftest.py` → `engine`, `client` |
| Dependency override of `get_db` | `tests/conftest.py` → `client` |
| Two clients: with and without exception propagation | `client` and `client_raw` |
| Factories with sensible defaults | `make_product`, `make_reservation`, `make_order` |
| Parametrization with meaningful `ids` | `tests/test_products_parametrized.py` |
| `indirect=True` — the parameter goes into the fixture | `stocked_product` in the same file |
| Cases read from an external CSV | `tests/test_csv_cases.py` → `pytest_generate_tests` |
| Custom markers with `--strict-markers` | `pytest.ini`, `pytestmark` in the tests |
| `xfail(strict=True)` as defect documentation | `tests/test_bugs.py` |
| Readable run summary | `addopts = -ra` in `pytest.ini` |
| CI with a version matrix and artifacts | `.github/workflows/tests.yml` |

## Why `xfail(strict=True)`

A defect is not deleted from the suite and not skipped "for now". It is pinned by a
test that fails on purpose:

- the bug is there → the test fails → the report shows **XFAIL**;
- the bug is fixed → the test passes → **XPASS**, which with `strict=True` fails the
  run, forcing the marker to be removed.

The test list therefore stays a live description of the system's known problems.
Details on all 11 defects: [`docs/seeded-bugs.md`](docs/seeded-bugs.md).

## CI

Every push to `main` and every pull request runs the suite on Python 3.11, 3.12 and
3.13: smoke tests first, then the full run with coverage, and the JUnit report is
uploaded as a build artifact.

## Roadmap

- [x] Fixtures, database isolation, factories
- [x] Parametrization and data-driven cases from CSV
- [x] CI with a version matrix
- [ ] External payment API mocked with `respx`, `monkeypatch` for time
- [ ] Parallel run with `pytest-xdist`, flaky-check with `--random-order`
- [ ] Allure report

## Running against PostgreSQL

```bash
DATABASE_URL=postgresql+psycopg://skladna:skladna@localhost:5432/skladna pytest
```

`docker-compose.yml` brings up PostgreSQL, Redis and the API for a local stand when
Docker is available.

