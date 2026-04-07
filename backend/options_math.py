"""
options_math.py — Black Scholes pricing and Greeks (spec module 7).

Inputs use decimal interest rates (0.0435 not 4.35) and decimal
volatilities (0.20 not 20). Time T is in years.

All formulas follow the spec text in PART 2 MODULE 7. The Greeks are
divided so that the user facing units are intuitive: per one calendar
day for Theta, per one volatility point for Vega, per one rate point
for Rho.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


SQRT_2PI = math.sqrt(2.0 * math.pi)


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _d1_d2(S: float, K: float, r: float, T: float, sigma: float) -> tuple[float, float]:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        raise ValueError("Black Scholes inputs must be positive and T > 0")
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2


def black_scholes_call(S: float, K: float, r: float, T: float, sigma: float) -> float:
    """European call price under Black Scholes."""
    d1, d2 = _d1_d2(S, K, r, T, sigma)
    return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)


def black_scholes_put(S: float, K: float, r: float, T: float, sigma: float) -> float:
    """European put price under Black Scholes."""
    d1, d2 = _d1_d2(S, K, r, T, sigma)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


@dataclass
class Greeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

    def to_dict(self) -> dict:
        return {
            "delta": round(self.delta, 4),
            "gamma": round(self.gamma, 6),
            "theta": round(self.theta, 4),
            "vega": round(self.vega, 4),
            "rho": round(self.rho, 4),
        }


def greeks(S: float, K: float, r: float, T: float, sigma: float, option_type: str = "call") -> Greeks:
    """Greeks for a European option.

    Theta is per one calendar day, Vega is per one volatility point
    (so a 1% move in IV), Rho is per one rate point (so a 1% move in r).
    """
    d1, d2 = _d1_d2(S, K, r, T, sigma)
    pdf_d1 = _norm_pdf(d1)

    gamma_val = pdf_d1 / (S * sigma * math.sqrt(T))
    vega_val = S * pdf_d1 * math.sqrt(T) / 100.0  # per one vol point

    if option_type.lower() == "call":
        delta_val = _norm_cdf(d1)
        theta_val = (
            -S * pdf_d1 * sigma / (2.0 * math.sqrt(T))
            - r * K * math.exp(-r * T) * _norm_cdf(d2)
        ) / 365.0
        rho_val = K * T * math.exp(-r * T) * _norm_cdf(d2) / 100.0
    else:
        delta_val = _norm_cdf(d1) - 1.0
        theta_val = (
            -S * pdf_d1 * sigma / (2.0 * math.sqrt(T))
            + r * K * math.exp(-r * T) * _norm_cdf(-d2)
        ) / 365.0
        rho_val = -K * T * math.exp(-r * T) * _norm_cdf(-d2) / 100.0

    return Greeks(delta_val, gamma_val, theta_val, vega_val, rho_val)


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    r: float,
    T: float,
    option_type: str = "call",
    initial_guess: float = 0.30,
    tol: float = 1e-4,
    max_iter: int = 50,
) -> Optional[float]:
    """Newton Raphson IV solver. Returns None if it fails to converge."""
    if market_price <= 0 or T <= 0:
        return None

    sigma = max(initial_guess, 1e-3)
    for _ in range(max_iter):
        try:
            price = (
                black_scholes_call(S, K, r, T, sigma)
                if option_type.lower() == "call"
                else black_scholes_put(S, K, r, T, sigma)
            )
            d1, _ = _d1_d2(S, K, r, T, sigma)
            vega_raw = S * _norm_pdf(d1) * math.sqrt(T)  # not divided by 100
        except ValueError:
            return None
        diff = price - market_price
        if abs(diff) < tol:
            return sigma
        if vega_raw == 0:
            return None
        sigma -= diff / vega_raw
        if sigma <= 0:
            sigma = 1e-3
    return None


def expected_move_from_atm_iv(iv: float, days_to_expiry: int) -> float:
    """One sigma expected move as a fraction of price."""
    if iv <= 0 or days_to_expiry <= 0:
        return 0.0
    return iv * math.sqrt(days_to_expiry / 365.0)
