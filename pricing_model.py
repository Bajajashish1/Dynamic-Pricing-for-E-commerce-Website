from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PricingInput:
    base_price: float
    stock: int
    max_stock: int
    recent_views: int
    recent_cart_adds: int
    recent_purchases: int
    user_loyalty_score: float


@dataclass(frozen=True)
class PricingResult:
    price: float
    demand_score: float
    stock_pressure: float
    behavior_score: float
    adjustment: float
    explanation: str


class DynamicPricingModel:
    """Small, dependency-free pricing model with ML-style weighted features.

    The weights act like a trained linear model. In a production system, these
    would be updated by a scheduled training job from conversion and margin data.
    """

    def __init__(self) -> None:
        self.weights = {
            "bias": 0.0,
            "demand": 0.18,
            "stock": 0.14,
            "behavior": 0.10,
            "loyalty": -0.05,
        }

    def predict(self, data: PricingInput) -> PricingResult:
        max_stock = max(data.max_stock, 1)
        demand_score = min(
            1.0,
            (data.recent_views * 0.015)
            + (data.recent_cart_adds * 0.075)
            + (data.recent_purchases * 0.18),
        )
        stock_pressure = max(0.0, 1.0 - (data.stock / max_stock))
        behavior_score = min(1.0, (data.recent_cart_adds + data.recent_purchases * 2) / 12)
        loyalty_score = min(max(data.user_loyalty_score, 0.0), 1.0)

        adjustment = (
            self.weights["bias"]
            + self.weights["demand"] * demand_score
            + self.weights["stock"] * stock_pressure
            + self.weights["behavior"] * behavior_score
            + self.weights["loyalty"] * loyalty_score
        )

        bounded_adjustment = min(0.28, max(-0.12, adjustment))
        price = round(data.base_price * (1 + bounded_adjustment), 2)

        explanation_parts = []
        if demand_score > 0.55:
            explanation_parts.append("high demand")
        if stock_pressure > 0.65:
            explanation_parts.append("limited stock")
        if loyalty_score > 0.6:
            explanation_parts.append("loyalty discount")
        if not explanation_parts:
            explanation_parts.append("stable market signals")

        return PricingResult(
            price=price,
            demand_score=round(demand_score, 3),
            stock_pressure=round(stock_pressure, 3),
            behavior_score=round(behavior_score, 3),
            adjustment=round(bounded_adjustment, 3),
            explanation=", ".join(explanation_parts),
        )
