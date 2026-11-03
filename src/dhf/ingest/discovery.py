"""Read-only native inventory and a candidate process mapping for human confirmation."""

import copy
import re
from collections import Counter, defaultdict

from dhf.ingest.ado import ADO, RECIPROCAL

DOCUMENT_ID = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+$")


def id_field_candidates(items: list[dict]) -> dict[str, list[str]]:
    """Per work-item type, string fields whose values look like document IDs (SPEC-X-12)."""
    by_type: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_type[item["fields"].get("System.WorkItemType", "unknown")].append(item["fields"])
    return {
        typ: sorted(
            name
            for name in {n for f in rows for n in f}
            if sum(isinstance(f.get(name), str) and bool(DOCUMENT_ID.match(f[name])) for f in rows)
            >= 0.8 * len(rows)
        )
        for typ, rows in sorted(by_type.items())
    }


def discovery_report(
    items: list[dict],
    fields: list[dict],
    links: list[dict],
    runs: list[dict],
    repos: list[dict],
    mapping: dict,
) -> dict:
    candidate = copy.deepcopy(mapping)
    used = {f for item in items for f in item["fields"]}
    available = used | {f["referenceName"] for f in fields}
    unknowns = []
    for semantic, reference in mapping["fields"].items():
        if reference in available:
            continue
        matches = [
            f["referenceName"]
            for f in fields
            if f.get("name", "").replace(" ", "").lower() == reference.rsplit(".", 1)[-1].lower()
        ]
        if len(matches) == 1:
            candidate["fields"][semantic] = matches[0]
        unknowns.append(
            {
                "kind": "field",
                "semantic": semantic,
                "expected": reference,
                "candidates": matches,
                "action": "Confirm semantic meaning and reference name before ingest.",
            }
        )
    names = mapping.get("fields", {})
    area_field, tags_field = names.get("area", "System.AreaPath"), names.get("tags", "System.Tags")
    types = Counter(item["fields"].get("System.WorkItemType", "unknown") for item in items)
    for typ in sorted(types.keys() - mapping.get("work_item_types", {}).keys()):
        unknowns.append(
            {
                "kind": "work_item_type",
                "name": typ,
                "action": "Choose canonical type/tag discriminator; no automatic classification.",
            }
        )
    areas = sorted({item["fields"][area_field] for item in items if area_field in item["fields"]})
    for area in areas:
        if area not in mapping.get("area_components", {}):
            unknowns.append(
                {"kind": "area_path", "name": area, "action": "Confirm component allocation."}
            )
    relation_types = sorted(
        {r["referenceName"] for r in links}
        | {r["rel"] for item in items for r in item.get("relations", [])}
    )
    mapped = set(mapping.get("relations", {}).values())
    for rel in sorted(set(relation_types) - mapped):
        if RECIPROCAL.get(rel) in mapped:
            continue  # ADO shows each link on both ends; the mapped end is enough
        unknowns.append(
            {
                "kind": "relation",
                "name": rel,
                "action": "Confirm link direction and canonical semantics.",
            }
        )
    tags = Counter(
        t.strip()
        for item in items
        for t in item["fields"].get(tags_field, "").split(";")
        if t.strip()
    )
    known_tags = set(mapping.get("tags", {}).values()) | {"Unit-Test"}
    known_tags.update(
        t for v in mapping.get("work_item_types", {}).values() if isinstance(v, dict) for t in v
    )
    prefix = mapping.get("id_tag_prefix")
    for tag in tags:
        if tag not in known_tags and not (prefix and tag.startswith(prefix)):
            unknowns.append(
                {
                    "kind": "tag",
                    "name": tag,
                    "action": "Confirm whether this tag has engineering semantics.",
                }
            )
    return {
        "mapping": candidate,
        "unknowns": unknowns,
        "status": "draft mapping — human confirmation required",
        "inventory": {
            "work_item_types": dict(sorted(types.items())),
            "fields_used": sorted(used),
            "link_types": relation_types,
            "tags": dict(sorted(tags.items())),
            "area_paths": areas,
            "id_field_candidates": id_field_candidates(items),
            "custom_fields": sorted(
                f for f in used if not f.startswith(("System.", "Microsoft.VSTS."))
            ),
            "test_runs": [{k: r.get(k) for k in ("id", "name", "state")} for r in runs],
            "repositories": [{k: r.get(k) for k in ("id", "name", "defaultBranch")} for r in repos],
        },
    }


def discover(ado: ADO) -> dict:
    try:
        repos = ado.collection("/_apis/git/repositories")
    except PermissionError:  # a Work Items + Test Management PAT has no Code (Read) scope
        repos = None
    report = discovery_report(
        ado.workitems(),
        ado.request("GET", ado.base + "/_apis/wit/fields")["value"],
        ado.request("GET", ado.base + "/_apis/wit/workitemrelationtypes")["value"],
        ado.test_runs(),
        repos or [],
        ado.mapping,
    )
    if repos is None:
        report["inventory"]["repositories"] = "not readable with this PAT (needs Code: Read)"
    return report
