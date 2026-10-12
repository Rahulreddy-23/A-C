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
