"""
schemas.py — Pydantic request/response models for the database API layer.

Separates the API contract from the ORM models.
All response schemas use `model_config = ConfigDict(from_attributes=True)`
so they can be populated directly from SQLAlchemy model instances.
"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, Field, EmailStr


# ── User ─────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., max_length=256)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    display_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None


# ── Portfolio ────────────────────────────────────────────────

class PortfolioCreate(BaseModel):
    name: str = Field("My Portfolio", max_length=128)
    description: Optional[str] = None
    is_default: bool = False


class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    description: Optional[str]
    is_default: bool
    created_at: datetime
    updated_at: datetime
    num_holdings: Optional[int] = None


# ── Holding ──────────────────────────────────────────────────

class HoldingCreate(BaseModel):
    symbol: str = Field(..., max_length=20)
    shares: float = Field(..., gt=0)
    avg_cost: float = Field(..., ge=0)
    dividends_per_share: float = Field(0.0, ge=0)
    sector: Optional[str] = None
    asset_class: str = "equity"
    notes: Optional[str] = None


class HoldingUpdate(BaseModel):
    shares: Optional[float] = None
    avg_cost: Optional[float] = None
    dividends_per_share: Optional[float] = None
    sector: Optional[str] = None
    asset_class: Optional[str] = None
    notes: Optional[str] = None


class HoldingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    portfolio_id: str
    symbol: str
    shares: float
    avg_cost: float
    dividends_per_share: float
    sector: Optional[str]
    asset_class: str
    added_at: datetime
    notes: Optional[str]


# ── Analysis Snapshot ────────────────────────────────────────

class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    portfolio_id: str
    total_value: Optional[float]
    total_return_pct: Optional[float]
    portfolio_volatility: Optional[float]
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    portfolio_beta: Optional[float]
    portfolio_alpha: Optional[float]
    var_95: Optional[float]
    hhi: Optional[float]
    effective_n: Optional[float]
    risk_free_rate: Optional[float]
    num_holdings: Optional[int]
    model_available: bool
    created_at: datetime


class SnapshotDetailResponse(SnapshotResponse):
    """Includes the full JSON payload for detailed view."""
    payload: dict


# ── Trade Journal ────────────────────────────────────────────

class TradeCreate(BaseModel):
    symbol: str = Field(..., max_length=20)
    action: str = Field(..., pattern="^(buy|sell)$")
    shares: float = Field(..., gt=0)
    price: Optional[float] = None
    total_cost: Optional[float] = None
    trade_type: str = Field("executed", pattern="^(executed|simulated|rebalance)$")
    simulation_result: Optional[dict] = None
    notes: Optional[str] = None


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    portfolio_id: str
    symbol: str
    action: str
    shares: float
    price: Optional[float]
    total_cost: Optional[float]
    trade_type: str
    simulation_result: Optional[dict]
    notes: Optional[str]
    executed_at: datetime


# ── Watchlist ────────────────────────────────────────────────

class WatchlistAdd(BaseModel):
    symbol: str = Field(..., max_length=20)
    target_price: Optional[float] = None
    notes: Optional[str] = None


class WatchlistUpdate(BaseModel):
    target_price: Optional[float] = None
    notes: Optional[str] = None


class WatchlistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    symbol: str
    target_price: Optional[float]
    notes: Optional[str]
    added_at: datetime


# ── Alert ────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    symbol: Optional[str] = None
    portfolio_id: Optional[str] = None
    metric: str = Field(..., pattern="^(price|sharpe|beta|volatility|var_95|rsi)$")
    condition: str = Field(..., pattern="^(above|below|crosses_above|crosses_below)$")
    threshold: float


class AlertUpdate(BaseModel):
    threshold: Optional[float] = None
    is_active: Optional[bool] = None


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    symbol: Optional[str]
    portfolio_id: Optional[str]
    metric: str
    condition: str
    threshold: float
    is_active: bool
    last_checked: Optional[datetime]
    triggered_at: Optional[datetime]
    trigger_count: int
    created_at: datetime


# ── Audit Log ────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[dict]
    ip_address: Optional[str]
    timestamp: datetime


# ── Pagination ───────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
