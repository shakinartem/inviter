from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CapacityFrontierRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str = Field(default="telegram", min_length=1, max_length=32)
    stage: Literal["engagement", "business"] = "business"
    event_type: str = Field(default="payment_received", min_length=1, max_length=64)
    horizon_hours: int = Field(default=168, ge=1, le=2160)
    objective: Literal["incremental_outcomes", "incremental_business_value"] = "incremental_business_value"
    value_unit: str | None = Field(default="RUB", min_length=1, max_length=16)
    value_aggregation: Literal["sum", "max"] | None = "sum"
    allocation_mode: Literal["decision_grade", "coverage_expansion"] = "decision_grade"
    capacities: list[int] = Field(default_factory=lambda: [100, 250, 500, 1000, 2000, 5000], min_length=1, max_length=12)
    cost_per_action: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_request(self) -> "CapacityFrontierRequest":
        normalized = sorted(set(int(value) for value in self.capacities))
        if any(value < 1 or value > 50000 for value in normalized):
            raise ValueError("capacities must be between 1 and 50000")
        self.capacities = normalized
        if self.objective == "incremental_business_value":
            if self.stage != "business":
                raise ValueError("business-value frontier requires stage=business")
            if not self.value_unit:
                raise ValueError("value_unit is required for business-value frontier")
            self.value_unit = self.value_unit.strip().upper()
            self.value_aggregation = self.value_aggregation or "sum"
        else:
            if self.value_unit is not None or self.value_aggregation is not None:
                self.value_unit = None
                self.value_aggregation = None
            if self.cost_per_action is not None:
                raise ValueError("cost_per_action is only meaningful for business-value frontier")
        return self


class CapacityFrontierPoint(BaseModel):
    requested_capacity: int
    allocated_count: int
    cumulative_expected: float
    cumulative_conservative: float
    cumulative_upside: float
    marginal_count: int
    marginal_expected: float
    marginal_conservative: float
    marginal_upside: float
    marginal_conservative_per_action: float | None
    cumulative_cost: float | None
    cumulative_conservative_net: float | None
    marginal_cost: float | None
    marginal_conservative_net: float | None


class CapacityFrontierResponse(BaseModel):
    objective: str
    value_unit: str | None
    event_type: str
    horizon_hours: int
    allocation_mode: str
    global_prior_status: str
    global_prior_i_squared: float
    unique_positive_candidates: int
    overlap_removed: int
    candidate_pool_capped: bool
    cost_per_action: float | None
    recommended_capacity: int | None
    recommendation_reason: str
    warnings: list[str]
    points: list[CapacityFrontierPoint]
