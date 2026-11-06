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
| Tests collected | 67 |
| Passing | 54 |
| Documented defects (`xfail`) | 13 |
| Coverage of `app/` | 95 % |
| Full run time | ~1.2 s |
| CI matrix | Python 3.11 / 3.12 / 3.13 |

## What is covered

- **Products** — creation, retrieval by SKU, stock and availability
- **Reservations** — reserving against stock, cancellation, available-stock maths
- **Orders** — building an order from reservations, discounts, pagination
- **Payments** — charging an order through an external provider, with every
  failure mode mocked: decline, timeout, 5xx, unreachable host, malformed body
- **Negative paths** — validation errors, unknown SKUs, conflicting data
- **Known defects** — one test per bug, pinned with `xfail(strict=True)`

## Stack

`Python` · `pytest` · `FastAPI` · `SQLAlchemy 2` · `Pydantic 2` · `httpx` · `respx` · `GitHub Actions`

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
54 passed, 13 xfailed in 1.23s
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
│   ├── payments.py      client for the external payment provider
│   └── main.py          endpoints + seeded defects
├── tests/
│   ├── conftest.py                    fixtures: engine, client, client_raw, factories
│   ├── test_smoke.py                  5 fast tests, always green
│   ├── test_bugs.py                   11 defect tests, xfail(strict=True)
│   ├── test_products_parametrized.py  parametrization, indirect fixtures, validation
│   ├── test_csv_cases.py              data-driven cases via pytest_generate_tests
│   ├── test_payments_mocked.py        external provider mocked with respx
│   ├── test_time_and_logs.py          monkeypatch, caplog, capfd
│   ├── test_isolation.py              proof that tests share no state
│   └── data/products.csv              the data set for those cases
├── scripts/
│   ├── measure.ps1      serial vs parallel timing on this machine
│   └── flaky_check.ps1  N runs in random order, stops at the first difference
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
| Third-party HTTP mocked with `respx` | `tests/test_payments_mocked.py` |
| Frozen clock with `monkeypatch` | `tests/test_time_and_logs.py` → `naive_utc_now` |
| Assertions on log records with `caplog` | `tests/test_time_and_logs.py` |
| Capturing stdout with `capfd` | `tests/test_time_and_logs.py` |
| Proof of isolation between tests | `tests/test_isolation.py` |
| Parallel run and randomised order | `scripts/measure.ps1`, `scripts/flaky_check.ps1` |
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

## Parallelism and order independence

The suite is designed so that every test can run on its own: each one gets a fresh
in-memory database, a fresh client, and a patched environment. That is what makes
`-n` and random order possible at all, and `tests/test_isolation.py` checks it
directly instead of trusting the fixture code.

```bash
# parallel
.venv\Scripts\python.exe -m pytest -n 4

# random order, reproducible seed
.venv\Scripts\python.exe -m pytest --random-order --random-order-seed=12345
```

### Measured, not assumed

| What was measured | Result |
|---|---|
| Full suite, one process | ~1.9 s |
| 10 runs, random order, random seeds | identical outcome every time: `54 passed, 13 xfailed` |
| Slowest and fastest random run | 1.82 s / 2.09 s |
| Cores on the measuring machine | 16 |

**On whether parallel is worth it here.** For a suite that finishes in two seconds,
usually not: worker start-up costs more than the parallel gain, and a slower run is
the honest result. On a single-core machine the same suite measured 1.29 s serial
against 1.91 s with `-n 2`. `-n` is therefore deliberately **not** in `addopts` — it
is available, and CI runs it, but the default stays serial so the numbers mean
something.

Measure on the target machine rather than trusting a rule of thumb:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\measure.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\measure.ps1 -Workers 8
```

The script prints both wall times, the speed-up, and a verdict — if the speed-up is
under 1.2x it says so and tells you to leave `-n` out of `addopts`.

**On flaky tests.** A flaky test is worse than a failing one: it teaches the team to
ignore red. `scripts/flaky_check.ps1` repeats the suite in random order and stops at
the first run whose result differs, printing the seed needed to reproduce it. It
compares outcomes, not timings:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\flaky_check.ps1 -Runs 20
```

## CI

Two jobs run on every push to `main` and every pull request:

1. **`pytest`** — the reference run: Python 3.11, 3.12 and 3.13, smoke tests first,
   then the full run with coverage. The JUnit report is uploaded as a build artifact.
2. **`order-independence`** — the same suite five times in random order, then once on
   four workers. A green reference run says the code works; these say the *tests* can
   be trusted, because nothing depends on the order or on another test's leftovers.

## Testing a third party without touching it

The payment provider is a separate service and a test must never call it: it is slow,
unreliable, and it charges real cards. The HTTP layer is intercepted with `respx`, so
every failure mode is reproducible in a millisecond:

| Provider answers | What the API does | Why |
|---|---|---|
| `200` with a charge id | `200`, order becomes `paid` | happy path |
| `402` declined | `402`, order stays `created` | the customer's problem |
| timeout | `502` | the provider's problem |
| `500` | `502` | the provider's problem |
| connection refused | `502` | the provider's problem |

A decline and an outage are deliberately different statuses: retrying a declined card
is pointless, retrying a timeout is not.

## Roadmap

- [x] Fixtures, database isolation, factories
- [x] Parametrization and data-driven cases from CSV
- [x] CI with a version matrix
- [x] External payment API mocked with `respx`, `monkeypatch` for time and config
- [x] Log assertions with `caplog`
- [x] Isolation tests, parallel run with `pytest-xdist`, flaky check with `--random-order`
- [ ] Allure report

## Running against PostgreSQL

```bash
DATABASE_URL=postgresql+psycopg://skladna:skladna@localhost:5432/skladna pytest
```

`docker-compose.yml` brings up PostgreSQL, Redis and the API for a local stand when
Docker is available.

