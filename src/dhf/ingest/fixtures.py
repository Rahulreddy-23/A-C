from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import yaml

from dhf.ingest.code import PythonExtractor
from dhf.ingest.native import fixture_item, normalize_workitem
from dhf.models.evidence import validate_graph


def ingest_fixtures(root: Path = Path("data/synthetic")) -> dict:
    raw = yaml.safe_load((root / "evidence.yaml").read_text(encoding="utf-8"))
    mapping = yaml.safe_load(Path("specs/ado_mapping.yaml").read_text(encoding="utf-8"))
    retrieved = datetime.now(UTC).isoformat()
    files = {
        p.relative_to(root / "code").as_posix(): p.read_text(encoding="utf-8")
        for p in (root / "code").rglob("*")
        if p.is_file() and p.suffix in (".py", ".txt")
    }
    files["architecture.yaml"] = yaml.safe_dump(
        [a for a in raw["artifacts"] if a["type"] in ("component", "adr")]
    )
    extracted = PythonExtractor().extract(files, "fixture://kestrel-device-sw", retrieved)
    extracted_ids = {a["id"] for a in extracted["artifacts"]}
    native_types = {
        "user_need",
        "system_req",
        "software_req",
        "risk_control",
        "hazard",
        "defect",
        "test_case",
        "review",
        "action_item",
    }
    for i, a in enumerate(raw["artifacts"], 1):
        if a["id"] in extracted_ids:
            continue
        if a["type"] in native_types:
            item = fixture_item(a, i, mapping)
            history = []
            for rev in a["attributes"].get(
                "requirement_history",
                [{"revision": item["rev"], "changed_at": item["fields"]["System.ChangedDate"]}],
            ):
                prior = deepcopy(item)
                prior["rev"] = rev["revision"]
                prior["fields"]["System.ChangedDate"] = rev["changed_at"]
                history.append(prior)
            extracted["artifacts"].append(normalize_workitem(item, history, mapping, retrieved))
        else:
            copy = deepcopy(a)
            if a["type"] == "test_run" and a["attributes"]["is_retest"]:
                copy["title"] += " retest"
            extracted["artifacts"].append(
                {
                    **copy,
                    "source": {
                        "system": "ado",
                        "url": f"fixture://{a['id']}",
                        "native_id": a["id"],
                        "revision": "1",
                        "retrieved_at": retrieved,
                    },
                }
            )
    by_edge = {(e["src"], e["dst"], e["type"]): e for e in raw["links"]}
    for e in extracted["links"]:
        by_edge[(e["src"], e["dst"], e["type"])] = e
    extracted["links"] = list(by_edge.values())
    return validate_graph(extracted)
