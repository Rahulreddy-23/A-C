from datetime import UTC, datetime
from pathlib import Path

import yaml

from dhf.ingest.code import PythonExtractor
from dhf.models.evidence import validate_graph


def ingest_fixtures(root: Path = Path("data/synthetic")) -> dict:
    raw = yaml.safe_load((root / "evidence.yaml").read_text())
    retrieved = datetime.now(UTC).isoformat()
    files = {
        str(p.relative_to(root / "code")): p.read_text()
        for p in (root / "code").rglob("*")
        if p.is_file() and p.suffix in (".py", ".txt")
    }
    files["architecture.yaml"] = yaml.safe_dump(
        [a for a in raw["artifacts"] if a["type"] in ("component", "adr")]
    )
    extracted = PythonExtractor().extract(files, "fixture://kestrel-device-sw", retrieved)
    extracted_ids = {a["id"] for a in extracted["artifacts"]}
    for a in raw["artifacts"]:
        if a["id"] not in extracted_ids:
            extracted["artifacts"].append(
                {
                    **a,
                    "source": {
                        "system": "ado",
                        "url": f"fixture://{a['id']}",
                        "native_id": a["id"],
                        "revision": str(a["attributes"].get("revision", 1)),
                        "retrieved_at": retrieved,
                    },
                }
            )
    by_edge = {(e["src"], e["dst"], e["type"]): e for e in raw["links"]}
    for e in extracted["links"]:
        by_edge[(e["src"], e["dst"], e["type"])] = e
    extracted["links"] = list(by_edge.values())
    return validate_graph(extracted)
