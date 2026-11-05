"""Настройки подключения к базе данных.

По умолчанию — SQLite-файл рядом с проектом: ничего устанавливать не нужно.
В CI или на стенде подставляется DATABASE_URL на PostgreSQL.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./skladna.db")

# SQLite требует отдельный флаг, если к нему обращаются из разных потоков
# (FastAPI делает именно так). Для PostgreSQL этот аргумент не нужен.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Базовый класс для всех таблиц."""


def get_db():
    """FastAPI-зависимость: одна сессия на один запрос, закрывается после ответа."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

