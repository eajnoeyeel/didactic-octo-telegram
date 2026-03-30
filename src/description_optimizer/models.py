"""Data models for the Description Optimizer pipeline."""

from enum import StrEnum
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

GEO_DIMENSIONS = frozenset(
    {"clarity", "disambiguation", "parameter_coverage", "fluency", "stats", "precision"}
)


class OptimizationStatus(StrEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    GATE_REJECTED = "gate_rejected"


class DimensionScore(BaseModel):
    """Score for a single GEO dimension (0.0 to 1.0)."""

    dimension: Literal[
        "clarity", "disambiguation", "parameter_coverage", "fluency", "stats", "precision"
    ]
    score: float = Field(ge=0.0, le=1.0)
    explanation: str

    @field_validator("dimension")
    @classmethod
    def validate_dimension(cls, v: str) -> str:
        if v not in GEO_DIMENSIONS:
            raise ValueError(f"Invalid dimension '{v}'. Must be one of {GEO_DIMENSIONS}")
        return v


class AnalysisReport(BaseModel):
    """GEO Score analysis report for a single tool description."""

    tool_id: str
    original_description: str
    dimension_scores: list[DimensionScore]

    @model_validator(mode="after")
    def validate_all_dimensions(self) -> "AnalysisReport":
        dims = {s.dimension for s in self.dimension_scores}
        if dims != GEO_DIMENSIONS:
            missing = GEO_DIMENSIONS - dims
            raise ValueError(f"Missing dimensions: {missing}. All 6 dimensions required.")
        return self

    @computed_field
    @property
    def geo_score(self) -> float:
        """Compute GEO score as equal-weight average of all dimensions."""
        return sum(s.score for s in self.dimension_scores) / len(self.dimension_scores)

    def weak_dimensions(self, threshold: float = 0.5) -> list[str]:
        """Return dimension names that score below the threshold."""
        return [s.dimension for s in self.dimension_scores if s.score < threshold]


class OptimizedDescription(BaseModel):
    """Result of the description optimization pipeline."""

    tool_id: str
    original_description: str
    optimized_description: str
    retrieval_description: str = Field(
        description="Embedding-optimized description for vector search",
        validation_alias=AliasChoices("retrieval_description", "search_description"),
        serialization_alias="retrieval_description",
    )
    geo_score_before: float = Field(ge=0.0, le=1.0)
    geo_score_after: float = Field(ge=0.0, le=1.0)
    status: OptimizationStatus
    skip_reason: str | None = None

    @property
    def search_description(self) -> str:
        """Backward-compatible alias for legacy code/tests."""
        return self.retrieval_description

    @computed_field
    @property
    def improvement(self) -> float:
        """GEO score improvement (after - before)."""
        return self.geo_score_after - self.geo_score_before


class OptimizationContext(BaseModel):
    """Context for grounded description optimization.

    Carries real tool data (input_schema, sibling tools) so the LLM
    can produce factually accurate descriptions without hallucination.
    """

    tool_id: str
    original_description: str
    input_schema: dict | None = None
    sibling_tools: list[dict] = Field(default_factory=list)

    @computed_field
    @property
    def parameter_names(self) -> list[str]:
        if not self.input_schema:
            return []
        props = self.input_schema.get("properties", {})
        return list(props.keys())
