"""Database connection settings.

Defaults to a local SQLite file — nothing to install.
On CI or a staging environment DATABASE_URL points at PostgreSQL instead.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./skladna.db")

# SQLite needs this flag when the connection is used from several threads
# (FastAPI does exactly that). PostgreSQL ignores the argument.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class for every table."""


def get_db():
    """FastAPI dependency: one session per request, closed after the response."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

