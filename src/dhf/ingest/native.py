"""Pure native-ADO normalization. Fixture-only metadata never determines product facts."""

import re
from html import unescape
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

# Attributes the product derives itself; a mapping may never overwrite them.
RESERVED_ATTRIBUTES = {
    "synthetic",
    "changed_at",
    "state",
    "component",
    "severity",
    "acceptance_criteria",
    "risk_control",
    "requirement_history",
    "level",
    "steps",
    "residual_listed",
    "link_classes",
}
HTML_TAG = re.compile(
    r"</?(p|div|br|span|table|tr|td|th|ul|ol|li|b|i|u|strong|em|h[1-6]|font|img|a)\b[^>]*>", re.I
)


class HTMLText(HTMLParser):
    """Readable text from ADO rich-text fields: blocks become lines, table rows 'a | b'.

    Tolerates omitted </td> and </tr>; a nested table is flattened into its outer cell."""

    BLOCKS = {"p", "div", "ul", "ol", "pre", "blockquote", "hr"} | {f"h{n}" for n in range(1, 7)}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.current: list[str] = []
        self.tables: list[dict] = []  # innermost last: {"row": [...] | None, "cell": [...] | None}
        self.bullet = False
        self.skip = 0

    @staticmethod
    def squash(parts: list[str]) -> str:
        return re.sub(r"\s+", " ", "".join(parts)).strip()

    def sink(self, depth: int | None = None) -> list[str]:
        """Innermost open cell (within the first `depth` tables), else the current line."""
        for table in reversed(self.tables[:depth]):
            if table["cell"] is not None:
                return table["cell"]
        return self.current

    def end_line(self) -> None:
        line = self.squash(self.current)
        if line:
            self.lines.append(("- " if self.bullet else "") + line)
            self.bullet = False
        self.current = []

    def close_cell(self) -> None:
        table = self.tables[-1]
        if table["cell"] is not None:
            table["row"] = (table["row"] or []) + [self.squash(table["cell"])]
            table["cell"] = None

    def close_row(self) -> None:
        self.close_cell()
        table = self.tables[-1]
        if table["row"] and any(table["row"]):
            text = " | ".join(table["row"])
            if len(self.tables) > 1:
                self.sink(-1).append(f" {text} ")
            else:
                self.lines.append(text)
        table["row"] = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "table" or (tag in ("tr", "td", "th") and not self.tables):
            if not self.tables:
                self.end_line()
            self.tables.append({"row": None, "cell": None})
            if tag != "table":
                self.handle_starttag(tag, attrs)
        elif tag == "tr":
            self.close_row()
            self.tables[-1]["row"] = []
        elif tag in ("td", "th"):
            self.close_cell()
            self.tables[-1]["cell"] = []
        elif tag in self.BLOCKS or tag in ("br", "li"):
            if self.sink() is not self.current:
                self.sink().append(" ")
            else:
                self.end_line()
                self.bullet = self.bullet or tag == "li"

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif not self.tables:
            if tag in self.BLOCKS or tag == "li":
                self.end_line()
        elif tag in ("td", "th"):
            self.close_cell()
        elif tag == "tr":
            self.close_row()
        elif tag == "table":
            self.close_row()
            self.tables.pop()
        elif tag in self.BLOCKS or tag == "li":
            self.sink().append(" ")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.sink().append(data)

    def finish(self) -> list[str]:
        self.close()
        while self.tables:
            self.close_row()
            self.tables.pop()
        self.end_line()
        return self.lines


def html_text(value: str) -> str:
    """ADO stores descriptions and steps as HTML; plain text passes through unchanged."""
    if not value or not HTML_TAG.search(value):
        return value
    parser = HTMLText()
    parser.feed(value)
    return "\n".join(parser.finish())


# The optional synthetic marker is the only permitted fixture metadata input.
def synthetic_marker(text: str, tags: list[str], mapping: dict) -> bool:
    """Fail closed: a tag counts only when the mapping names one explicitly."""
    marker = mapping.get("tags", {}).get("synthetic")
    return bool(marker and marker in tags) or bool(
        re.search(r'DHF-META:\s*\{\s*"synthetic"\s*:\s*true\s*\}', text)
    )


def plain_body(text: str) -> str:
    return re.sub(r"\nDHF-META:.*$", "", text, flags=re.S).rstrip()


def workitem_kind(fields: dict, mapping: dict) -> str | None:
    tags = [t.strip() for t in (fields.get(mapping["fields"].get("tags", "")) or "").split(";")]
    kind = mapping["work_item_types"].get(fields["System.WorkItemType"])
    if isinstance(kind, dict):
        kind = next((kind[t] for t in tags if t in kind), None)
    return kind or mapping.get("default_work_item_type")


def native_identifier(item: dict, kind: str, tags: list[str], mapping: dict) -> str:
    """DHF identity tag, else a mapped ID field (e.g. a Spec ID), else a per-type format."""
    prefix = mapping.get("id_tag_prefix")
    tagged = next((t[len(prefix) :] for t in tags if prefix and t.startswith(prefix)), None)
    if tagged:
        return tagged
    field = mapping.get("id_fields", {}).get(kind)
    value = str(item["fields"].get(field, "")).strip() if field else ""
    return value or mapping.get("id_formats", {}).get(kind, "ADO-{id}").format(id=item["id"])


def normalize_workitem(
    item: dict, history: list[dict], mapping: dict, retrieved: str
) -> dict | None:
    fields = item["fields"]
    names = mapping["fields"]
    kind = workitem_kind(fields, mapping)
    if kind is None:
        return None
    tags = [t.strip() for t in (fields.get(names.get("tags", "")) or "").split(";")]
    marker_tags = mapping.get("tags", {})
    description = fields.get(names.get("body", "")) or ""
    attrs = {
        "synthetic": synthetic_marker(description, tags, mapping),
        "changed_at": fields[names["changed_at"]],
        "state": fields[names["state"]],
    }
    for semantic, reference in mapping.get("attribute_fields", {}).items():
        if semantic in RESERVED_ATTRIBUTES:  # e.g. `synthetic` gates external LLM providers
            raise ValueError(f"attribute_fields may not set the reserved attribute {semantic!r}")
        if fields.get(reference) not in (None, ""):
            attrs[semantic] = html_text(str(fields[reference]))
    area = fields.get(names.get("area", ""), "")
    if area in mapping.get("area_components", {}):
        attrs["component"] = mapping["area_components"][area]
    severity = fields.get(names.get("severity", ""))
    if severity is not None:
        attrs["severity"] = mapping.get("severity_values", {}).get(
            str(severity), int(severity) if str(severity).isdigit() else None
        )
    if kind == "software_req":
        attrs["acceptance_criteria"] = html_text(fields.get(names.get("acceptance_criteria"), ""))
        attrs["risk_control"] = marker_tags.get("risk_requirement") in tags
        attrs["requirement_history"] = [
            {"revision": v["rev"], "changed_at": v["fields"][names["changed_at"]]} for v in history
        ]
    if kind == "test_case":
        attrs["level"] = "unit" if "Unit-Test" in tags else "system"
        attrs["steps"] = parse_steps(fields.get(names.get("steps", ""), ""))
    if kind == "defect":
        attrs["residual_listed"] = marker_tags.get("residual_anomaly") in tags
    return {
        "id": native_identifier(item, kind, tags, mapping),
        "type": kind,
        "title": fields[names["title"]],
        "body": html_text(plain_body(description)),
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
    """Test steps XML; real ADO nests HTML inside parameterizedString and in shared steps."""
    if not text:
        return []
    steps = []
    for step in ET.fromstring(text).iter("step"):
        # ElementTree already removed the XML layer: HTML is decoded once more, by html_text;
        # only plain text still needs its entities unescaped.
        raw = ["".join(p.itertext()) for p in step.findall("parameterizedString")]
        parts = [html_text(r) if HTML_TAG.search(r) else unescape(r) for r in raw]
        steps.append({"action": (parts + [""])[0], "expected": (parts + ["", ""])[1]})
    return steps


def normalize_run(
    run: dict, mapping: dict, retrieved: str, base: str, default_release: str = ""
) -> dict:
    """A run's release comes from its name, else the scope's release for its test plans."""
    release_match = re.search(mapping["release_pattern"], run["name"])
    attrs = {
        "synthetic": (
            synthetic_marker(run.get("comment", ""), [], mapping)
            or run.get("comment", "").startswith("Synthetic fixture evidence only.")
        ),
        "release": release_match[1] if release_match else default_release,
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
    run_id = str(result.get("testRun", {}).get("id") or run["source"]["native_id"])
    title = result.get("testCaseTitle") or result["testCase"].get("name", "")
    attrs = {
        "synthetic": run["attributes"]["synthetic"],
        "release": run["attributes"]["release"],
        "completed_at": result.get("completedDate", ""),
        "test_case": tc,
        "outcome": result.get("outcome") or "Unspecified",
        "run": f"RUN-{run_id}",
    }
    return native_record(
        f"RES-{run_id}-{int(result['id']):03}",
        "test_result",
        title,
        plain_body(result.get("comment") or title),
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
