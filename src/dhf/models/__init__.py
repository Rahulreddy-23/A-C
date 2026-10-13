from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    kind: Literal["sourced", "inferred", "suggested"]
    citations: list[str]
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def uncertain_confidence(self) -> "Claim":
        if self.kind != "sourced" and self.confidence is None:
            raise ValueError("Confidence required for uncertain claims")
        return self


class Claims(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[Claim]


class SupportVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_key: str
    support: Literal["supported", "partial", "unsupported"]
    rationale: Claim


class SupportChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[SupportVerdict]


def output_model(schema_id: str) -> type[BaseModel]:
    return {"claims.v1": Claims, "support.v1": SupportChecks}[schema_id]


def strict_claims_schema() -> dict:
    return strict_output_schema("claims.v1")


def strict_output_schema(schema_id: str) -> dict:
    """Strict provider schema; confidence is required but may be null for sourced claims."""
    import json
    from pathlib import Path

    output_model(schema_id)  # Reject unknown/path-traversal schema names.
    schema = json.loads(Path(f"specs/schemas/{schema_id}.json").read_text())

    def strip_bounds(value: object) -> None:
        if isinstance(value, dict):
            if "properties" in value:
                value["required"] = list(value["properties"])
                for prop in value["properties"].values():
                    prop.pop("default", None)
            for key in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
                value.pop(key, None)
            for child in value.values():
                strip_bounds(child)
        elif isinstance(value, list):
            for child in value:
                strip_bounds(child)

    strip_bounds(schema)
    return schema
