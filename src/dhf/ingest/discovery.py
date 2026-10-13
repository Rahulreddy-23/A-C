"""Read-only native inventory and a candidate process mapping for human confirmation."""

import copy
from collections import Counter

from dhf.ingest.ado import ADO


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
    types = Counter(item["fields"].get("System.WorkItemType", "unknown") for item in items)
    for typ in sorted(types.keys() - mapping["work_item_types"].keys()):
        unknowns.append(
            {
                "kind": "work_item_type",
                "name": typ,
                "action": "Choose canonical type/tag discriminator; no automatic classification.",
            }
        )
    areas = sorted(
        {
            item["fields"][mapping["fields"]["area"]]
            for item in items
            if mapping["fields"]["area"] in item["fields"]
        }
    )
    for area in areas:
        if area not in mapping["area_components"]:
            unknowns.append(
                {"kind": "area_path", "name": area, "action": "Confirm component allocation."}
            )
    relation_types = sorted(
        {r["referenceName"] for r in links}
        | {r["rel"] for item in items for r in item.get("relations", [])}
    )
    for rel in set(relation_types) - set(mapping["relations"].values()):
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
        for t in item["fields"].get(mapping["fields"]["tags"], "").split(";")
        if t.strip()
    )
    known_tags = set(mapping["tags"].values()) | {"Unit-Test"}
    known_tags.update(
        t for v in mapping["work_item_types"].values() if isinstance(v, dict) for t in v
    )
    for tag in tags:
        if tag not in known_tags and not tag.startswith(mapping["id_tag_prefix"]):
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
            "test_runs": [{k: r.get(k) for k in ("id", "name", "state")} for r in runs],
            "repositories": [{k: r.get(k) for k in ("id", "name", "defaultBranch")} for r in repos],
        },
    }


def discover(ado: ADO) -> dict:
    return discovery_report(
        ado.workitems(),
        ado.request("GET", ado.base + "/_apis/wit/fields")["value"],
        ado.request("GET", ado.base + "/_apis/wit/workitemrelationtypes")["value"],
        ado.collection("/_apis/test/runs"),
        ado.collection("/_apis/git/repositories"),
        ado.mapping,
    )
