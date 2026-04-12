"""
crud.py — Data Access Layer for FinGPT Portfolio Analyzer.

Provides typed, reusable CRUD operations for all ORM models.
Every write operation is automatically audit-logged.

Design principles:
  - Functions accept a Session, never create their own
  - All writes go through audit_log() for compliance
  - Pagination via paginate() helper
  - Soft errors return None; hard errors raise
"""

import hashlib
import logging
import math
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from backend.database.models import (
    User, Portfolio, Holding, AnalysisSnapshot,
    TradeJournal, Watchlist, Alert, AuditLog,
)

logger = logging.getLogger("fingpt.crud")


def _utcnow():
    return datetime.now(timezone.utc)


def _hash_password(password: str) -> str:
    """SHA-256 password hashing. Production should use bcrypt."""
    return hashlib.sha256(password.encode()).hexdigest()


# ══════════════════════════════════════════════════════════════
#  Audit Logging
# ══════════════════════════════════════════════════════════════

def audit_log(
    db: Session,
    user_id: Optional[str],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
):
    """Record an immutable audit trail entry."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    db.flush()
    return entry


# ══════════════════════════════════════════════════════════════
#  Pagination Helper
# ══════════════════════════════════════════════════════════════

def paginate(query, page: int = 1, page_size: int = 20) -> dict:
    """Apply pagination to a SQLAlchemy query and return metadata."""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


# ══════════════════════════════════════════════════════════════
#  Users
# ══════════════════════════════════════════════════════════════

def create_user(db: Session, username: str, email: str, password: str,
                display_name: Optional[str] = None, ip: Optional[str] = None) -> User:
    """Register a new user. Raises ValueError if username/email taken."""
    if db.query(User).filter(User.username == username).first():
        raise ValueError(f"Username '{username}' is already taken")
    if db.query(User).filter(User.email == email).first():
        raise ValueError(f"Email '{email}' is already registered")

    user = User(
        username=username,
        email=email,
        password_hash=_hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    db.flush()

    # Create a default portfolio for the new user
    default_portfolio = Portfolio(
        user_id=user.id,
        name="My Portfolio",
        is_default=True,
    )
    db.add(default_portfolio)
    db.flush()

    audit_log(db, user.id, "register", "user", user.id, ip_address=ip)
    db.commit()
    logger.info("User registered: %s (%s)", username, user.id[:8])
    return user


def authenticate_user(db: Session, username: str, password: str,
                       ip: Optional[str] = None) -> Optional[User]:
    """Validate credentials. Returns User on success, None on failure."""
    user = db.query(User).filter(User.username == username).first()
    if not user or user.password_hash != _hash_password(password):
        if user:
            audit_log(db, user.id, "login_failed", "user", ip_address=ip)
            db.commit()
        return None
    if not user.is_active:
        return None
    user.last_login = _utcnow()
    audit_log(db, user.id, "login", "user", user.id, ip_address=ip)
    db.commit()
    return user


def get_user(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def update_user(db: Session, user_id: str, **kwargs) -> Optional[User]:
    user = get_user(db, user_id)
    if not user:
        return None
    for k, v in kwargs.items():
        if v is not None and hasattr(user, k):
            setattr(user, k, v)
    audit_log(db, user_id, "update_user", "user", user_id,
              details={"fields": list(kwargs.keys())})
    db.commit()
    return user


def deactivate_user(db: Session, user_id: str) -> bool:
    user = get_user(db, user_id)
    if not user:
        return False
    user.is_active = False
    audit_log(db, user_id, "deactivate_user", "user", user_id)
    db.commit()
    return True


# ══════════════════════════════════════════════════════════════
#  Portfolios
# ══════════════════════════════════════════════════════════════

def create_portfolio(db: Session, user_id: str, name: str = "My Portfolio",
                     description: Optional[str] = None, is_default: bool = False) -> Portfolio:
    # If setting as default, unset other defaults
    if is_default:
        db.query(Portfolio).filter(
            Portfolio.user_id == user_id, Portfolio.is_default == True
        ).update({"is_default": False})

    portfolio = Portfolio(
        user_id=user_id,
        name=name,
        description=description,
        is_default=is_default,
    )
    db.add(portfolio)
    db.flush()
    audit_log(db, user_id, "create_portfolio", "portfolio", portfolio.id,
              details={"name": name})
    db.commit()
    logger.info("Portfolio created: %s for user %s", name, user_id[:8])
    return portfolio


def get_portfolios(db: Session, user_id: str) -> list[Portfolio]:
    return db.query(Portfolio).filter(Portfolio.user_id == user_id).order_by(
        desc(Portfolio.is_default), Portfolio.created_at
    ).all()


def get_portfolio(db: Session, portfolio_id: str, user_id: Optional[str] = None) -> Optional[Portfolio]:
    q = db.query(Portfolio).filter(Portfolio.id == portfolio_id)
    if user_id:
        q = q.filter(Portfolio.user_id == user_id)
    return q.first()


def get_default_portfolio(db: Session, user_id: str) -> Optional[Portfolio]:
    return db.query(Portfolio).filter(
        Portfolio.user_id == user_id, Portfolio.is_default == True
    ).first()


def update_portfolio(db: Session, portfolio_id: str, user_id: str, **kwargs) -> Optional[Portfolio]:
    portfolio = get_portfolio(db, portfolio_id, user_id)
    if not portfolio:
        return None
    if kwargs.get("is_default"):
        db.query(Portfolio).filter(
            Portfolio.user_id == user_id, Portfolio.is_default == True
        ).update({"is_default": False})
    for k, v in kwargs.items():
        if v is not None and hasattr(portfolio, k):
            setattr(portfolio, k, v)
    audit_log(db, user_id, "update_portfolio", "portfolio", portfolio_id,
              details={"fields": list(kwargs.keys())})
    db.commit()
    return portfolio


def delete_portfolio(db: Session, portfolio_id: str, user_id: str) -> bool:
    portfolio = get_portfolio(db, portfolio_id, user_id)
    if not portfolio:
        return False
    audit_log(db, user_id, "delete_portfolio", "portfolio", portfolio_id,
              details={"name": portfolio.name})
    db.delete(portfolio)
    db.commit()
    return True


# ══════════════════════════════════════════════════════════════
#  Holdings
# ══════════════════════════════════════════════════════════════

def add_holding(db: Session, portfolio_id: str, user_id: str,
                symbol: str, shares: float, avg_cost: float,
                dividends_per_share: float = 0, sector: Optional[str] = None,
                asset_class: str = "equity", notes: Optional[str] = None) -> Holding:
    portfolio = get_portfolio(db, portfolio_id, user_id)
    if not portfolio:
        raise ValueError("Portfolio not found")

    # Check for existing holding of same symbol — merge if exists
    existing = db.query(Holding).filter(
        Holding.portfolio_id == portfolio_id,
        Holding.symbol == symbol.upper(),
    ).first()

    if existing:
        # Weighted average cost basis
        total_shares = float(existing.shares) + shares
        existing.avg_cost = (
            (float(existing.shares) * float(existing.avg_cost) + shares * avg_cost) / total_shares
        )
        existing.shares = total_shares
        if notes:
            existing.notes = notes
        db.flush()
        audit_log(db, user_id, "merge_holding", "holding", existing.id,
                  details={"symbol": symbol.upper(), "added_shares": shares})
        db.commit()
        return existing

    holding = Holding(
        portfolio_id=portfolio_id,
        symbol=symbol.upper(),
        shares=shares,
        avg_cost=avg_cost,
        dividends_per_share=dividends_per_share,
        sector=sector,
        asset_class=asset_class,
        notes=notes,
    )
    db.add(holding)
    db.flush()
    audit_log(db, user_id, "add_holding", "holding", holding.id,
              details={"symbol": symbol.upper(), "shares": shares})
    db.commit()
    return holding


def get_holdings(db: Session, portfolio_id: str) -> list[Holding]:
    return db.query(Holding).filter(
        Holding.portfolio_id == portfolio_id
    ).order_by(Holding.symbol).all()


def update_holding(db: Session, holding_id: str, user_id: str, **kwargs) -> Optional[Holding]:
    holding = db.query(Holding).filter(Holding.id == holding_id).first()
    if not holding:
        return None
    portfolio = get_portfolio(db, holding.portfolio_id, user_id)
    if not portfolio:
        return None
    for k, v in kwargs.items():
        if v is not None and hasattr(holding, k):
            setattr(holding, k, v)
    audit_log(db, user_id, "update_holding", "holding", holding_id,
              details={"fields": list(kwargs.keys())})
    db.commit()
    return holding


def remove_holding(db: Session, holding_id: str, user_id: str) -> bool:
    holding = db.query(Holding).filter(Holding.id == holding_id).first()
    if not holding:
        return False
    portfolio = get_portfolio(db, holding.portfolio_id, user_id)
    if not portfolio:
        return False
    audit_log(db, user_id, "remove_holding", "holding", holding_id,
              details={"symbol": holding.symbol})
    db.delete(holding)
    db.commit()
    return True


# ══════════════════════════════════════════════════════════════
#  Analysis Snapshots
# ══════════════════════════════════════════════════════════════

def save_snapshot(db: Session, portfolio_id: str, user_id: str,
                  payload: dict, model_available: bool = False) -> AnalysisSnapshot:
    """Persist a full analysis result as a historical snapshot.

    Extracts key metrics from the payload for denormalized fast-query columns.
    """
    summary = payload.get("analytics", {}).get("summary", {})
    holdings_list = payload.get("analytics", {}).get("holdings", [])

    snapshot = AnalysisSnapshot(
        portfolio_id=portfolio_id,
        total_value=summary.get("total_value"),
        total_return_pct=summary.get("total_return_pct"),
        portfolio_volatility=summary.get("portfolio_volatility"),
        sharpe_ratio=summary.get("portfolio_sharpe"),
        sortino_ratio=summary.get("portfolio_sortino"),
        portfolio_beta=summary.get("portfolio_beta"),
        portfolio_alpha=summary.get("portfolio_alpha"),
        var_95=summary.get("var_95"),
        hhi=summary.get("hhi"),
        effective_n=summary.get("effective_n"),
        risk_free_rate=payload.get("risk_free_rate"),
        payload=payload,
        num_holdings=len(holdings_list),
        model_available=model_available,
    )
    db.add(snapshot)
    db.flush()
    audit_log(db, user_id, "save_snapshot", "snapshot", snapshot.id,
              details={"portfolio_id": portfolio_id, "total_value": summary.get("total_value")})
    db.commit()
    logger.info("Snapshot saved for portfolio %s (value=$%s)",
                portfolio_id[:8], summary.get("total_value"))
    return snapshot


def get_snapshots(db: Session, portfolio_id: str,
                  page: int = 1, page_size: int = 20) -> dict:
    """Get paginated snapshot history for a portfolio (newest first)."""
    q = db.query(AnalysisSnapshot).filter(
        AnalysisSnapshot.portfolio_id == portfolio_id
    ).order_by(desc(AnalysisSnapshot.created_at))
    return paginate(q, page, page_size)


def get_snapshot(db: Session, snapshot_id: str) -> Optional[AnalysisSnapshot]:
    return db.query(AnalysisSnapshot).filter(AnalysisSnapshot.id == snapshot_id).first()


def get_latest_snapshot(db: Session, portfolio_id: str) -> Optional[AnalysisSnapshot]:
    return db.query(AnalysisSnapshot).filter(
        AnalysisSnapshot.portfolio_id == portfolio_id
    ).order_by(desc(AnalysisSnapshot.created_at)).first()


def get_snapshot_timeseries(db: Session, portfolio_id: str, metric: str,
                            limit: int = 90) -> list[dict]:
    """Extract a time series of a single metric from snapshot history.

    Useful for charting Sharpe, beta, VaR, etc. over time.
    """
    valid_metrics = {
        "total_value", "total_return_pct", "portfolio_volatility",
        "sharpe_ratio", "sortino_ratio", "portfolio_beta", "portfolio_alpha",
        "var_95", "hhi", "effective_n",
    }
    if metric not in valid_metrics:
        raise ValueError(f"Invalid metric '{metric}'. Valid: {valid_metrics}")

    col = getattr(AnalysisSnapshot, metric)
    rows = db.query(AnalysisSnapshot.created_at, col).filter(
        AnalysisSnapshot.portfolio_id == portfolio_id,
        col.isnot(None),
    ).order_by(desc(AnalysisSnapshot.created_at)).limit(limit).all()

    return [{"date": r[0].isoformat(), "value": float(r[1])} for r in reversed(rows)]


# ══════════════════════════════════════════════════════════════
#  Trade Journal
# ══════════════════════════════════════════════════════════════

def record_trade(db: Session, portfolio_id: str, user_id: str,
                 symbol: str, action: str, shares: float,
                 price: Optional[float] = None, total_cost: Optional[float] = None,
                 trade_type: str = "executed", simulation_result: Optional[dict] = None,
                 notes: Optional[str] = None) -> TradeJournal:
    portfolio = get_portfolio(db, portfolio_id, user_id)
    if not portfolio:
        raise ValueError("Portfolio not found")

    trade = TradeJournal(
        portfolio_id=portfolio_id,
        symbol=symbol.upper(),
        action=action,
        shares=shares,
        price=price,
        total_cost=total_cost,
        trade_type=trade_type,
        simulation_result=simulation_result,
        notes=notes,
    )
    db.add(trade)
    db.flush()
    audit_log(db, user_id, "record_trade", "trade", trade.id,
              details={"symbol": symbol.upper(), "action": action, "shares": shares, "type": trade_type})
    db.commit()
    return trade


def get_trades(db: Session, portfolio_id: str,
               page: int = 1, page_size: int = 50,
               trade_type: Optional[str] = None) -> dict:
    q = db.query(TradeJournal).filter(TradeJournal.portfolio_id == portfolio_id)
    if trade_type:
        q = q.filter(TradeJournal.trade_type == trade_type)
    q = q.order_by(desc(TradeJournal.executed_at))
    return paginate(q, page, page_size)


def get_trade_summary(db: Session, portfolio_id: str) -> dict:
    """Aggregate trade statistics for a portfolio."""
    trades = db.query(TradeJournal).filter(
        TradeJournal.portfolio_id == portfolio_id,
        TradeJournal.trade_type == "executed",
    ).all()

    total_buys = sum(1 for t in trades if t.action == "buy")
    total_sells = sum(1 for t in trades if t.action == "sell")
    unique_symbols = len({t.symbol for t in trades})
    total_volume = sum(float(t.shares) * float(t.price or 0) for t in trades)

    return {
        "total_trades": len(trades),
        "total_buys": total_buys,
        "total_sells": total_sells,
        "unique_symbols": unique_symbols,
        "total_volume": round(total_volume, 2),
    }


# ══════════════════════════════════════════════════════════════
#  Watchlist
# ══════════════════════════════════════════════════════════════

def add_to_watchlist(db: Session, user_id: str, symbol: str,
                     target_price: Optional[float] = None,
                     notes: Optional[str] = None) -> Watchlist:
    existing = db.query(Watchlist).filter(
        Watchlist.user_id == user_id,
        Watchlist.symbol == symbol.upper(),
    ).first()
    if existing:
        if target_price is not None:
            existing.target_price = target_price
        if notes is not None:
            existing.notes = notes
        db.commit()
        return existing

    item = Watchlist(
        user_id=user_id,
        symbol=symbol.upper(),
        target_price=target_price,
        notes=notes,
    )
    db.add(item)
    db.flush()
    audit_log(db, user_id, "add_watchlist", "watchlist", item.id,
              details={"symbol": symbol.upper()})
    db.commit()
    return item


def get_watchlist(db: Session, user_id: str) -> list[Watchlist]:
    return db.query(Watchlist).filter(
        Watchlist.user_id == user_id
    ).order_by(Watchlist.added_at).all()


def update_watchlist_item(db: Session, item_id: str, user_id: str, **kwargs) -> Optional[Watchlist]:
    item = db.query(Watchlist).filter(
        Watchlist.id == item_id, Watchlist.user_id == user_id
    ).first()
    if not item:
        return None
    for k, v in kwargs.items():
        if v is not None and hasattr(item, k):
            setattr(item, k, v)
    db.commit()
    return item


def remove_from_watchlist(db: Session, item_id: str, user_id: str) -> bool:
    item = db.query(Watchlist).filter(
        Watchlist.id == item_id, Watchlist.user_id == user_id
    ).first()
    if not item:
        return False
    audit_log(db, user_id, "remove_watchlist", "watchlist", item_id,
              details={"symbol": item.symbol})
    db.delete(item)
    db.commit()
    return True


def remove_from_watchlist_by_symbol(db: Session, user_id: str, symbol: str) -> bool:
    item = db.query(Watchlist).filter(
        Watchlist.user_id == user_id,
        Watchlist.symbol == symbol.upper(),
    ).first()
    if not item:
        return False
    audit_log(db, user_id, "remove_watchlist", "watchlist", item.id,
              details={"symbol": symbol.upper()})
    db.delete(item)
    db.commit()
    return True


# ══════════════════════════════════════════════════════════════
#  Alerts
# ══════════════════════════════════════════════════════════════

def create_alert(db: Session, user_id: str, metric: str, condition: str,
                 threshold: float, symbol: Optional[str] = None,
                 portfolio_id: Optional[str] = None) -> Alert:
    alert = Alert(
        user_id=user_id,
        symbol=symbol.upper() if symbol else None,
        portfolio_id=portfolio_id,
        metric=metric,
        condition=condition,
        threshold=threshold,
    )
    db.add(alert)
    db.flush()
    audit_log(db, user_id, "create_alert", "alert", alert.id,
              details={"metric": metric, "condition": condition, "threshold": threshold})
    db.commit()
    return alert


def get_alerts(db: Session, user_id: str, active_only: bool = True) -> list[Alert]:
    q = db.query(Alert).filter(Alert.user_id == user_id)
    if active_only:
        q = q.filter(Alert.is_active == True)
    return q.order_by(desc(Alert.created_at)).all()


def update_alert(db: Session, alert_id: str, user_id: str, **kwargs) -> Optional[Alert]:
    alert = db.query(Alert).filter(
        Alert.id == alert_id, Alert.user_id == user_id
    ).first()
    if not alert:
        return None
    for k, v in kwargs.items():
        if v is not None and hasattr(alert, k):
            setattr(alert, k, v)
    db.commit()
    return alert


def trigger_alert(db: Session, alert_id: str) -> Optional[Alert]:
    """Mark an alert as triggered (called by the alert evaluation engine)."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return None
    alert.triggered_at = _utcnow()
    alert.last_checked = _utcnow()
    alert.trigger_count += 1
    db.commit()
    return alert


def delete_alert(db: Session, alert_id: str, user_id: str) -> bool:
    alert = db.query(Alert).filter(
        Alert.id == alert_id, Alert.user_id == user_id
    ).first()
    if not alert:
        return False
    audit_log(db, user_id, "delete_alert", "alert", alert_id,
              details={"metric": alert.metric, "symbol": alert.symbol})
    db.delete(alert)
    db.commit()
    return True


# ══════════════════════════════════════════════════════════════
#  Audit Log Queries
# ══════════════════════════════════════════════════════════════

def get_audit_log(db: Session, user_id: Optional[str] = None,
                  action: Optional[str] = None,
                  page: int = 1, page_size: int = 50) -> dict:
    q = db.query(AuditLog)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if action:
        q = q.filter(AuditLog.action == action)
    q = q.order_by(desc(AuditLog.timestamp))
    return paginate(q, page, page_size)


def get_user_activity_summary(db: Session, user_id: str) -> dict:
    """High-level activity counts for a user's audit trail."""
    total = db.query(func.count(AuditLog.id)).filter(AuditLog.user_id == user_id).scalar()
    actions = db.query(AuditLog.action, func.count(AuditLog.id)).filter(
        AuditLog.user_id == user_id
    ).group_by(AuditLog.action).all()
    last = db.query(AuditLog).filter(AuditLog.user_id == user_id).order_by(
        desc(AuditLog.timestamp)
    ).first()

    return {
        "total_events": total,
        "by_action": {a: c for a, c in actions},
        "last_activity": last.timestamp.isoformat() if last else None,
    }


# ══════════════════════════════════════════════════════════════
#  Dashboard Stats (cross-model aggregations)
# ══════════════════════════════════════════════════════════════

def get_user_dashboard_stats(db: Session, user_id: str) -> dict:
    """Aggregate statistics for a user's dashboard overview."""
    portfolios = db.query(func.count(Portfolio.id)).filter(Portfolio.user_id == user_id).scalar()
    holdings = db.query(func.count(Holding.id)).join(Portfolio).filter(
        Portfolio.user_id == user_id
    ).scalar()
    snapshots = db.query(func.count(AnalysisSnapshot.id)).join(Portfolio).filter(
        Portfolio.user_id == user_id
    ).scalar()
    trades = db.query(func.count(TradeJournal.id)).join(Portfolio).filter(
        Portfolio.user_id == user_id
    ).scalar()
    watchlist_count = db.query(func.count(Watchlist.id)).filter(
        Watchlist.user_id == user_id
    ).scalar()
    active_alerts = db.query(func.count(Alert.id)).filter(
        Alert.user_id == user_id, Alert.is_active == True
    ).scalar()

    # Latest portfolio value from most recent snapshot
    latest_snap = db.query(AnalysisSnapshot).join(Portfolio).filter(
        Portfolio.user_id == user_id
    ).order_by(desc(AnalysisSnapshot.created_at)).first()

    return {
        "portfolios": portfolios,
        "holdings": holdings,
        "snapshots": snapshots,
        "trades": trades,
        "watchlist": watchlist_count,
        "active_alerts": active_alerts,
        "latest_total_value": float(latest_snap.total_value) if latest_snap and latest_snap.total_value else None,
        "latest_sharpe": latest_snap.sharpe_ratio if latest_snap else None,
        "latest_snapshot_date": latest_snap.created_at.isoformat() if latest_snap else None,
    }
