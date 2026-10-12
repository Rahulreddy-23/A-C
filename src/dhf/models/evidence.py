import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dhf.llm import canonical

ArtifactType = Literal[
    "user_need",
    "system_req",
    "software_req",
    "hazard",
    "risk_control",
    "component",
    "software_unit",
    "soup",
    "adr",
    "code_change",
    "test_case",
    "test_run",
    "test_result",
    "defect",
    "review",
    "action_item",
    "document_section",
]


class Source(BaseModel):
    system: Literal["ado", "git", "file", "derived"]
    url: str = Field(min_length=1)
    native_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    retrieved_at: str = Field(min_length=1)


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    type: ArtifactType
    title: str
    body: str
    attributes: dict[str, Any]
    source: Source
    content_hash: str = ""

    @model_validator(mode="after")
    def hash_content(self) -> "Artifact":
        digest = hashlib.sha256(
            canonical({"body": self.body, "attributes": self.attributes}).encode()
        ).hexdigest()
        if self.content_hash and self.content_hash != digest:
            raise ValueError("Artifact content hash mismatch")
        self.content_hash = digest
        return self


class TraceLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    src: str
    dst: str
    type: Literal[
        "derives_from",
        "allocated_to",
        "implements",
        "verifies",
        "mitigates",
        "detects",
        "executes",
        "reports_defect",
        "changes",
        "reviews",
    ]
    origin: Literal["explicit", "ai_inferred", "human_confirmed"]
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: str

    @model_validator(mode="after")
    def inferred_confidence(self) -> "TraceLink":
        if self.origin == "ai_inferred" and self.confidence is None:
            raise ValueError("Inferred links require confidence")
        return self


def validate_graph(data: dict) -> dict:
    artifacts = [Artifact.model_validate(a).model_dump(mode="json") for a in data["artifacts"]]
    links = [TraceLink.model_validate(e).model_dump(mode="json") for e in data["links"]]
    ids = {a["id"] for a in artifacts}
    if len(ids) != len(artifacts):
        raise ValueError("Duplicate artifact IDs")
    if any(e["src"] not in ids or e["dst"] not in ids for e in links):
        raise ValueError("Trace link target missing")
    return {
        "artifacts": sorted(artifacts, key=lambda a: a["id"]),
        "links": sorted(links, key=lambda e: (e["src"], e["dst"], e["type"])),
    }
