"""
database — Persistence layer for FinGPT Portfolio Analyzer.

Supports SQLite (local/dev) and MySQL/PostgreSQL (production).
Configure via DATABASE_URL in config/.env.

Sub-modules:
  - models.py   ORM table definitions
  - engine.py   Connection pooling and session management
  - crud.py     Data access layer (all read/write operations)
  - schemas.py  Pydantic request/response contracts
"""

from backend.database.engine import get_db, get_db_session, init_db, close_db
from backend.database.models import (
    User,
    Portfolio,
    Holding,
    AnalysisSnapshot,
    TradeJournal,
    Watchlist,
    Alert,
    AuditLog,
)
from backend.database import crud
from backend.database import schemas

__all__ = [
    "get_db",
    "get_db_session",
    "init_db",
    "close_db",
    "crud",
    "schemas",
    "User",
    "Portfolio",
    "Holding",
    "AnalysisSnapshot",
    "TradeJournal",
    "Watchlist",
    "Alert",
    "AuditLog",
]
