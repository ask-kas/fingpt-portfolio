"""
models.py — SQLAlchemy ORM models for FinGPT Portfolio Analyzer.

Schema design:
  - Users own Portfolios, Watchlists, and Alerts
  - Portfolios contain Holdings and generate AnalysisSnapshots
  - TradeJournal records what-if simulations and executed trades
  - AuditLog tracks all state-changing operations for compliance

All monetary values stored as DECIMAL(18,4) for precision.
All timestamps use UTC with timezone awareness.
JSON columns store complex analytics payloads (snapshots, alert configs).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, Index, JSON, Numeric, Enum as SAEnum,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return uuid.uuid4().hex


# ── Users ─────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(256), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(128), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
    watchlist = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"


# ── Portfolios ────────────────────────────────────────────────

class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(String(32), primary_key=True, default=_uuid)
    user_id = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False, default="My Portfolio")
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="portfolios")
    holdings = relationship("Holding", back_populates="portfolio", cascade="all, delete-orphan")
    snapshots = relationship("AnalysisSnapshot", back_populates="portfolio", cascade="all, delete-orphan",
                             order_by="AnalysisSnapshot.created_at.desc()")
    trades = relationship("TradeJournal", back_populates="portfolio", cascade="all, delete-orphan",
                          order_by="TradeJournal.executed_at.desc()")

    __table_args__ = (
        Index("ix_portfolios_user_default", "user_id", "is_default"),
    )

    def __repr__(self):
        return f"<Portfolio {self.name} ({self.id[:8]})>"


# ── Holdings ──────────────────────────────────────────────────

class Holding(Base):
    __tablename__ = "holdings"

    id = Column(String(32), primary_key=True, default=_uuid)
    portfolio_id = Column(String(32), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    shares = Column(Numeric(18, 6), nullable=False)
    avg_cost = Column(Numeric(18, 4), nullable=False)
    dividends_per_share = Column(Numeric(18, 4), default=0, nullable=False)
    sector = Column(String(64), nullable=True)
    asset_class = Column(String(32), default="equity", nullable=False)  # equity, crypto, etf
    added_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="holdings")

    __table_args__ = (
        Index("ix_holdings_portfolio_symbol", "portfolio_id", "symbol"),
    )

    def __repr__(self):
        return f"<Holding {self.symbol} x{self.shares}>"


# ── Analysis Snapshots ────────────────────────────────────────

class AnalysisSnapshot(Base):
    """Stores the full analytics output each time a portfolio is analyzed.

    This creates a time series of portfolio metrics, enabling historical
    tracking of Sharpe, VaR, beta, and all other analytics over time.
    The payload column stores the complete JSON response from /api/portfolio/analyze.
    """
    __tablename__ = "analysis_snapshots"

    id = Column(String(32), primary_key=True, default=_uuid)
    portfolio_id = Column(String(32), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)

    # Denormalized key metrics for fast querying without JSON parsing
    total_value = Column(Numeric(18, 2), nullable=True)
    total_return_pct = Column(Float, nullable=True)
    portfolio_volatility = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    portfolio_beta = Column(Float, nullable=True)
    portfolio_alpha = Column(Float, nullable=True)
    var_95 = Column(Float, nullable=True)
    hhi = Column(Float, nullable=True)
    effective_n = Column(Float, nullable=True)
    risk_free_rate = Column(Float, nullable=True)

    # Full analytics payload
    payload = Column(JSON, nullable=False)
    num_holdings = Column(Integer, nullable=True)
    model_available = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="snapshots")

    __table_args__ = (
        Index("ix_snapshots_portfolio_date", "portfolio_id", "created_at"),
    )

    def __repr__(self):
        return f"<Snapshot {self.portfolio_id[:8]} @ {self.created_at}>"


# ── Trade Journal ─────────────────────────────────────────────

class TradeJournal(Base):
    """Records trades (executed or simulated) for performance tracking.

    trade_type:
      - 'executed'   actual trade the user made
      - 'simulated'  what-if simulation result
      - 'rebalance'  result of applying an efficient frontier suggestion
    """
    __tablename__ = "trade_journal"

    id = Column(String(32), primary_key=True, default=_uuid)
    portfolio_id = Column(String(32), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    action = Column(String(10), nullable=False)  # buy, sell
    shares = Column(Numeric(18, 6), nullable=False)
    price = Column(Numeric(18, 4), nullable=True)
    total_cost = Column(Numeric(18, 2), nullable=True)
    trade_type = Column(String(20), default="executed", nullable=False)

    # What-if simulation results (stored as JSON delta)
    simulation_result = Column(JSON, nullable=True)

    notes = Column(Text, nullable=True)
    executed_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="trades")

    __table_args__ = (
        Index("ix_trades_portfolio_date", "portfolio_id", "executed_at"),
        Index("ix_trades_symbol", "symbol"),
    )

    def __repr__(self):
        return f"<Trade {self.action} {self.shares} {self.symbol}>"


# ── Watchlist ─────────────────────────────────────────────────

class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(String(32), primary_key=True, default=_uuid)
    user_id = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    target_price = Column(Numeric(18, 4), nullable=True)
    notes = Column(Text, nullable=True)
    added_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="watchlist")

    __table_args__ = (
        Index("ix_watchlist_user_symbol", "user_id", "symbol", unique=True),
    )

    def __repr__(self):
        return f"<Watch {self.symbol}>"


# ── Alerts ────────────────────────────────────────────────────

class Alert(Base):
    """Price and metric alerts.

    metric: 'price', 'sharpe', 'beta', 'volatility', 'var_95', 'rsi'
    condition: 'above', 'below', 'crosses_above', 'crosses_below'
    """
    __tablename__ = "alerts"

    id = Column(String(32), primary_key=True, default=_uuid)
    user_id = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=True)  # null = portfolio-level alert
    portfolio_id = Column(String(32), ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True)
    metric = Column(String(32), nullable=False)
    condition = Column(String(20), nullable=False)
    threshold = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_checked = Column(DateTime(timezone=True), nullable=True)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_user_active", "user_id", "is_active"),
    )

    def __repr__(self):
        return f"<Alert {self.symbol or 'portfolio'} {self.metric} {self.condition} {self.threshold}>"


# ── Audit Log ─────────────────────────────────────────────────

class AuditLog(Base):
    """Immutable audit trail of all state-changing operations.

    Every create, update, delete, login, and analysis is logged here
    for compliance and debugging.
    """
    __tablename__ = "audit_log"

    id = Column(String(32), primary_key=True, default=_uuid)
    user_id = Column(String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(64), nullable=False)  # login, create_portfolio, analyze, etc.
    resource_type = Column(String(32), nullable=True)  # portfolio, holding, alert, etc.
    resource_id = Column(String(32), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)  # supports IPv6
    timestamp = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_action_time", "action", "timestamp"),
    )

    def __repr__(self):
        return f"<Audit {self.action} @ {self.timestamp}>"
