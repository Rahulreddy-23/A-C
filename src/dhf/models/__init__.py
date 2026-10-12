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


def strict_claims_schema() -> dict:
    """Strict provider schema; confidence is required but may be null for sourced claims."""
    import json
    from pathlib import Path

    schema = json.loads(Path("specs/schemas/claims.v1.json").read_text())
    claim = schema["$defs"]["Claim"]
    claim["required"] = list(claim["properties"])
    claim["properties"]["confidence"].pop("default", None)

    def strip_bounds(value: object) -> None:
        if isinstance(value, dict):
            for key in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
                value.pop(key, None)
            for child in value.values():
                strip_bounds(child)
        elif isinstance(value, list):
            for child in value:
                strip_bounds(child)

    strip_bounds(schema)
    return schema
