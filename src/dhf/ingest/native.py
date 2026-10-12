"""Pure native-ADO normalization. Fixture-only metadata never determines product facts."""

import re
from html import unescape
from xml.etree import ElementTree as ET


# The optional synthetic marker is the only permitted fixture metadata input.
def synthetic_marker(text: str, tags: list[str], mapping: dict) -> bool:
    return mapping["tags"]["synthetic"] in tags or bool(
        re.search(r'DHF-META:\s*\{\s*"synthetic"\s*:\s*true\s*\}', text)
    )


def plain_body(text: str) -> str:
    return re.sub(r"\nDHF-META:.*$", "", text, flags=re.S).rstrip()


def workitem_kind(fields: dict, mapping: dict) -> str | None:
    tags = [t.strip() for t in fields.get(mapping["fields"]["tags"], "").split(";")]
    kind = mapping["work_item_types"].get(fields["System.WorkItemType"])
    return next((kind[t] for t in tags if t in kind), None) if isinstance(kind, dict) else kind


def normalize_workitem(
    item: dict, history: list[dict], mapping: dict, retrieved: str
) -> dict | None:
    fields = item["fields"]
    names = mapping["fields"]
    kind = workitem_kind(fields, mapping)
    if kind is None:
        return None
    tags = [t.strip() for t in fields.get(names["tags"], "").split(";")]
    id = next(
        (
            t[len(mapping["id_tag_prefix"]) :]
            for t in tags
            if t.startswith(mapping["id_tag_prefix"])
        ),
        f"ADO-{item['id']}",
    )
    description = fields.get(names["body"], "")
    attrs = {
        "synthetic": synthetic_marker(description, tags, mapping),
        "changed_at": fields[names["changed_at"]],
        "state": fields[names["state"]],
    }
    area = fields.get(names["area"], "")
    if area in mapping["area_components"]:
        attrs["component"] = mapping["area_components"][area]
    severity = fields.get(names["severity"])
    if severity is not None:
        attrs["severity"] = mapping["severity_values"].get(
            str(severity), int(severity) if str(severity).isdigit() else None
        )
    if kind == "software_req":
        attrs["acceptance_criteria"] = fields.get(names["acceptance_criteria"], "")
        attrs["risk_control"] = mapping["tags"]["risk_requirement"] in tags
        attrs["requirement_history"] = [
            {"revision": v["rev"], "changed_at": v["fields"][names["changed_at"]]} for v in history
        ]
    if kind == "test_case":
        attrs["level"] = "unit" if "Unit-Test" in tags else "system"
        attrs["steps"] = parse_steps(fields.get(names["steps"], ""))
    if kind == "defect":
        attrs["residual_listed"] = mapping["tags"]["residual_anomaly"] in tags
    return {
        "id": id,
        "type": kind,
        "title": fields[names["title"]],
        "body": plain_body(description),
        "attributes": attrs,
        "source": {
            "system": "ado",
            "url": item["_links"]["html"]["href"],
            "native_id": str(item["id"]),
            "revision": str(item["rev"]),
            "retrieved_at": retrieved,
        },
    }


def parse_steps(text: str) -> list[dict]:
    if not text:
        return []
    root = ET.fromstring(text)
    return [
        {
            "action": unescape("".join(step.find("parameterizedString").itertext())),
            "expected": unescape("".join(step.findall("parameterizedString")[1].itertext())),
        }
        for step in root.findall("step")
    ]


def normalize_run(run: dict, mapping: dict, retrieved: str, base: str) -> dict:
    release_match = re.search(mapping["release_pattern"], run["name"])
    attrs = {
        "synthetic": (
            synthetic_marker(run.get("comment", ""), [], mapping)
            or run.get("comment", "").startswith("Synthetic fixture evidence only.")
        ),
        "release": release_match[1] if release_match else "",
        "completed_at": run.get("completedDate", ""),
        "environment": run.get("buildConfiguration", {}).get("platform", ""),
        "is_retest": "retest" in run["name"].lower(),
    }
    return native_record(
        f"RUN-{run['id']}",
        "test_run",
        run["name"],
        plain_body(run.get("comment", run["name"])),
        attrs,
        base + f"/_apis/test/runs/{run['id']}",
        str(run["id"]),
        retrieved,
    )


def normalize_result(result: dict, run: dict, native_ids: dict, retrieved: str, base: str) -> dict:
    tc = native_ids[str(result["testCase"]["id"])]
    run_id = str(result["testRun"]["id"])
    attrs = {
        "synthetic": run["attributes"]["synthetic"],
        "release": run["attributes"]["release"],
        "completed_at": result["completedDate"],
        "test_case": tc,
        "outcome": result["outcome"],
        "run": f"RUN-{run_id}",
    }
    return native_record(
        f"RES-{run_id}-{int(result['id']):03}",
        "test_result",
        result["testCaseTitle"],
        plain_body(result.get("comment", result["testCaseTitle"])),
        attrs,
        base + f"/_apis/test/runs/{run_id}/results/{result['id']}",
        str(result["id"]),
        retrieved,
    )


def native_record(
    id: str, kind: str, title: str, body: str, attrs: dict, url: str, native: str, retrieved: str
) -> dict:
    return {
        "id": id,
        "type": kind,
        "title": title,
        "body": body,
        "attributes": attrs,
        "source": {
            "system": "ado",
            "url": url,
            "native_id": native,
            "revision": "1",
            "retrieved_at": retrieved,
        },
    }


def fixture_item(artifact: dict, native: int, mapping: dict) -> dict:
    """File adapter maps declared fixture values to the native fields it represents."""
    kind = artifact["type"]
    attrs = artifact["attributes"]
    names = mapping["fields"]
    type_entry = next(
        (
            typ
            for typ, value in mapping["work_item_types"].items()
            if value == kind or isinstance(value, dict) and kind in value.values()
        ),
        None,
    )
    tag = (
        next(
            (tag for tag, value in mapping["work_item_types"][type_entry].items() if value == kind),
            "",
        )
        if isinstance(mapping["work_item_types"][type_entry], dict)
        else ""
    )
    tags = [tag, "DHF:" + artifact["id"]]
    if attrs.get("synthetic"):
        tags.append(mapping["tags"]["synthetic"])
    if attrs.get("risk_control"):
        tags.append(mapping["tags"]["risk_requirement"])
    if attrs.get("residual_listed"):
        tags.append(mapping["tags"]["residual_anomaly"])
    if attrs.get("level") == "unit":
        tags.append("Unit-Test")
    fields = {
        "System.Id": native,
        "System.WorkItemType": type_entry,
        names["title"]: artifact["title"],
        names["body"]: artifact["body"],
        names["tags"]: "; ".join(tags),
        names["state"]: attrs.get("state", "Active"),
        names["changed_at"]: attrs.get("changed_at", "2026-09-20T12:00:00Z"),
    }
    if attrs.get("component") in mapping["components"]:
        fields[names["area"]] = next(
            area for area, id in mapping["area_components"].items() if id == attrs["component"]
        )
    if "severity" in attrs:
        fields[names["severity"]] = next(
            value
            for value, severity in mapping["severity_values"].items()
            if severity == attrs["severity"]
        )
    if "acceptance_criteria" in attrs:
        fields[names["acceptance_criteria"]] = attrs["acceptance_criteria"]
    if kind == "test_case":
        steps = ET.Element("steps", {"id": "0", "last": "1"})
        step = ET.SubElement(steps, "step", {"id": "1", "type": "ActionStep"})
        ET.SubElement(step, "parameterizedString", {"isformatted": "true"}).text = attrs.get(
            "steps", ""
        )
        ET.SubElement(step, "parameterizedString", {"isformatted": "true"}).text = attrs.get(
            "expected_result", ""
        )
        fields[names["steps"]] = ET.tostring(steps, encoding="unicode")
    return {
        "id": native,
        "rev": attrs.get("revision", 1),
        "fields": fields,
        "relations": [],
        "_links": {"html": {"href": f"fixture://{artifact['id']}"}},
    }
