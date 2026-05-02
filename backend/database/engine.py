"""
engine.py — Database connection, pooling, and session management.

Supports three backends via DATABASE_URL:
  - SQLite:      sqlite:///./data/veris.db         (default, zero config)
  - MySQL:       mysql+pymysql://user:pass@host/db
  - PostgreSQL:  postgresql+asyncpg://user:pass@host/db

Connection pooling is configured for production use:
  - pool_size=10         (10 persistent connections)
  - max_overflow=20      (up to 20 burst connections)
  - pool_recycle=3600    (recycle connections every hour to avoid stale handles)
  - pool_pre_ping=True   (test connection health before checkout)
"""

import os
import logging
from pathlib import Path
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from backend.database.models import Base

logger = logging.getLogger("veris.database")

_engine = None
_SessionLocal = None


def _build_url() -> str:
    """Construct DATABASE_URL from env, with fallback to SQLite."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    # Build from individual env vars (MySQL/PostgreSQL)
    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME", "veris")
    db_port = os.getenv("DB_PORT", "3306")
    db_driver = os.getenv("DB_DRIVER", "mysql+pymysql")

    if db_host and db_user and db_pass:
        return f"{db_driver}://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    # Default: SQLite in project data/ directory
    data_dir = Path(__file__).parent.parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    return f"sqlite:///{data_dir / 'veris.db'}"


def init_db():
    """Initialize the database engine, create tables if they don't exist."""
    global _engine, _SessionLocal

    url = _build_url()
    is_sqlite = url.startswith("sqlite")

    engine_kwargs = {}
    if not is_sqlite:
        engine_kwargs.update({
            "pool_size": 10,
            "max_overflow": 20,
            "pool_recycle": 3600,
            "pool_pre_ping": True,
        })

    _engine = create_engine(
        url,
        echo=os.getenv("DB_ECHO", "").lower() == "true",
        **engine_kwargs,
    )

    # SQLite: enable WAL mode and foreign keys
    if is_sqlite:
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

    # Create all tables
    Base.metadata.create_all(bind=_engine)

    backend = url.split("://")[0].split("+")[0]
    logger.info("Database initialized: %s", backend)
    return _engine


def get_db():
    """FastAPI dependency: yields a database session, auto-closes on exit."""
    if _SessionLocal is None:
        init_db()
    db = _SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_session() -> Session:
    """Context manager for use outside of FastAPI request cycle."""
    if _SessionLocal is None:
        init_db()
    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def close_db():
    """Dispose of the engine and all pooled connections."""
    global _engine, _SessionLocal
    if _engine:
        _engine.dispose()
        logger.info("Database connections closed")
    _engine = None
    _SessionLocal = None
