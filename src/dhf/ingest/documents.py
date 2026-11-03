"""Existing DHF documents and ADO CSV exports → evidence graph (local, deterministic).

Extraction is declared in specs/doc_import/*.yaml (file globs, table headers, heading
structure). `extract_document` is a pure function over parsed blocks; only `docx_blocks`
and `import_folder` touch files. Columns listed under `drop` never enter the store."""

import csv
import fnmatch
import hashlib
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml

from dhf.models.evidence import validate_graph

BODY_LIMIT = 6000
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
VERSION = re.compile(r"(?:#|\brev(?:ision)?\.?\s*|_v|\bv)(\d+(?:\.\d+)*)", re.I)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def norm(text: str) -> str:
    """Comparison key for headers and headings."""
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "-", text.strip()).strip("-")


def matches(name: str, pattern: str) -> bool:
    """File globs ignore case on every platform."""
    return fnmatch.fnmatchcase(name.lower(), pattern.lower())


def visible_text(element) -> str:
    """Run text as Word shows it with tracked changes accepted: insertions kept,
    deletions and moved-away text dropped, line breaks kept as newlines."""
    parts: list[str] = []

    def walk(node) -> None:
        for child in node:
            tag = child.tag
            if tag in (W + "del", W + "moveFrom"):
                continue
            if tag == W + "t" and child.text:
                parts.append(child.text)
            elif tag == W + "tab":
                parts.append(" ")
            elif tag in (W + "br", W + "cr"):
                parts.append("\n")
            else:
                walk(child)

    walk(element)
    return "".join(parts)


def docx_blocks(path: Path) -> tuple[list[dict], Counter]:
    """Body order: headings with level, paragraphs, tables as rows of cell text.

    Content controls are entered; cell text keeps one line per paragraph or break."""
    from docx import Document
    from docx.table import Table

    document = Document(str(path))
    styles = {s.style_id: s.name or "" for s in document.styles if s.style_id}
    body = document.element.body
    notes: Counter = Counter()
    if next(body.iter(W + "ins", W + "del"), None) is not None:
        notes["documents with tracked changes (read as accepted)"] += 1

    def children(container):
        for child in container.iterchildren():
            if child.tag == W + "sdt":
                notes["content controls read"] += 1
                content = child.find(W + "sdtContent")
                if content is not None:
                    yield from children(content)
            elif child.tag in (W + "p", W + "tbl"):
                yield child

    def cell_text(tc) -> str:
        lines = (clean(line) for p in tc.iter(W + "p") for line in visible_text(p).split("\n"))
        return "\n".join(line for line in lines if line)

    blocks: list[dict] = []
    for child in children(body):
        if child.tag == W + "p":
            text = clean(visible_text(child))
            style = child.find(f"{W}pPr/{W}pStyle")
            name = styles.get(style.get(W + "val"), "") if style is not None else ""
            level = re.match(r"(?i)heading\s*(\d)", name)
            if text and level:
                blocks.append({"kind": "heading", "level": int(level[1]), "text": text})
            elif text:
                blocks.append({"kind": "para", "text": text})
        else:
            try:
                table = Table(child, document)
                rows = [[cell_text(c._element) for c in r.cells] for r in table.rows]
            except (IndexError, ValueError):  # irregular grids
                blocks.append({"kind": "table", "rows": [], "unreadable": True})
                continue
            blocks.append({"kind": "table", "rows": rows})
    return blocks, notes


def heading_paths(blocks: list[dict]) -> list[str]:
    """Heading path in force at each block (last three levels)."""
    stack: list[tuple[int, str]] = []
    paths = []
    for block in blocks:
        if block["kind"] == "heading":
            stack = [h for h in stack if h[0] < block["level"]] + [(block["level"], block["text"])]
        paths.append(" > ".join(text for _, text in stack[-3:]))
    return paths


def block_text(block: dict) -> str:
    if block["kind"] == "table":
        return "\n".join(
            " | ".join(c.replace("\n", "; ") for c in row if c) for row in block["rows"] if any(row)
        )
    return block["text"]


def header_index(header: list[str], required: list[str], wanted: list[str]) -> dict | None:
    """Column positions for `wanted` names when every `required` header is present."""
    keys = [norm(h) for h in header]
    if not all(norm(n) in keys for n in required):
        return None
    return {n: keys.index(norm(n)) for n in wanted if norm(n) in keys}


def cells(row: list[str], index: dict[str, int]) -> dict[str, str]:
    return {name: row[i] if i < len(row) else "" for name, i in index.items()}


def one_line(text: str) -> str:
    return clean(text.replace("\n", " "))


def artifact(
    kind: str, ident: str, title: str, body: str, attrs: dict, source: dict, anchor: str = ""
) -> dict:
    return {
        "id": ident,
        "type": kind,
        "title": one_line(title) or ident,
        "body": body[:BODY_LIMIT],
        "attributes": {"synthetic": False, "document": source["document"], **attrs},
        "source": {
            "system": "file",
            "url": f"{source['url']}#{slug(anchor or ident)}",
            "native_id": anchor or ident,
            "revision": source["revision"],
            "retrieved_at": source["retrieved_at"],
        },
    }


def extract_document(blocks: list[dict], rule: dict, source: dict) -> dict:
    """One parsed document and its rule → artifacts, unresolved matrix rows and a report."""
    paths = heading_paths(blocks)
    found: list[dict] = []
    pending: list[dict] = []
    report: Counter = Counter()
    report["unreadable tables"] += sum(1 for b in blocks if b.get("unreadable"))
    tables = [(i, b) for i, b in enumerate(blocks) if b["kind"] == "table" and b["rows"]]

    for spec in rule.get("tables", []):
        wanted = [spec["id"], spec["title"], spec["body"], *spec.get("attributes", {}).values()]
        for index, block in tables:
            col = header_index(block["rows"][0], spec["header"], wanted)
            if not col:
                continue
            for row in block["rows"][1:]:
                cell = cells(row, col)
                ident = one_line(cell.get(spec["id"], ""))
                if ident:
                    attrs = {
                        k: one_line(cell.get(v, "")) for k, v in spec.get("attributes", {}).items()
                    }
                    found.append(
                        artifact(
                            spec["type"],
                            ident,
                            cell.get(spec["title"], ""),
                            cell.get(spec["body"], ""),
                            {"section": paths[index], **attrs},
                            source,
                        )
                    )

    for spec in rule.get("records", []):
        header = spec["header"]
        for index, block in tables:
            col = header_index(block["rows"][0], header, header)
            if not col or len(block["rows"]) < 2:
                continue
            cell = {k: one_line(v) for k, v in cells(block["rows"][1], col).items()}
            if not cell[spec["id"]]:
                continue
            title, body = "", []
            for nxt in blocks[index + 1 :]:
                if nxt["kind"] == "heading" or (
                    nxt["kind"] == "table"
                    and nxt["rows"]
                    and header_index(nxt["rows"][0], header, header) is not None
                ):
                    break
                text = block_text(nxt)
                if not title and spec.get("title_prefix") and text.startswith(spec["title_prefix"]):
                    title = text[len(spec["title_prefix"]) :].strip()
                else:
                    for prefix in spec.get("strip_prefixes", []):
                        text = text.removeprefix(prefix).strip()
                    if text:
                        body.append(text)
            attrs = {k: cell.get(v, "") for k, v in spec.get("attributes", {}).items()}
            found.append(
                artifact(
                    spec["type"],
                    cell[spec["id"]],
                    title,
                    "\n".join(body),
                    {"section": paths[index], **attrs},
                    source,
                )
            )

    for spec in rule.get("sections", []):
        for index, block in enumerate(blocks):
            if block["kind"] != "heading" or norm(block["text"]) != norm(spec["parent"]):
                continue
            items: list[tuple[str, list[str]]] = []
            for nxt in blocks[index + 1 :]:
                if nxt["kind"] == "heading" and nxt["level"] <= block["level"]:
                    break
                if nxt["kind"] == "heading" and nxt["level"] == block["level"] + 1:
                    items.append((nxt["text"], []))
                elif items:
                    items[-1][1].append(block_text(nxt))
            found.extend(
                artifact(
                    spec["type"],
                    spec.get("id_prefix", "") + slug(name),
                    name,
                    "\n".join(t for t in body if t),
                    {"section": spec["parent"]},
                    source,
                )
                for name, body in items
            )

    for spec in rule.get("matrices", []):
        for _, block in tables:
            col = header_index(block["rows"][0], spec["header"], [spec["src"], spec["dst"]])
            if not col or len(col) < 2:
                continue
            for row in block["rows"][1:]:
                cell = cells(row, col)
                if one_line(cell[spec["src"]]):
                    pending.append(
                        {
                            "link": spec["link"],
                            "src_id": one_line(cell[spec["src"]]),
                            "names": cell[spec["dst"]],
                            "none_values": spec.get("none_values", []),
                            "document": source["document"],
                        }
                    )

    for spec in rule.get("units", []):
        headings = [(i, b) for i, b in enumerate(blocks) if b["kind"] == "heading"]
        for position, (index, block) in enumerate(headings):
            child = headings[position + 1][1] if position + 1 < len(headings) else None
            if not child or child["level"] != block["level"] + 1:
                continue
            if norm(child["text"]) != norm(spec["marker"]):
                continue
            parent = next(
                (
                    b["text"]
                    for _, b in reversed(headings[:position])
                    if b["level"] < block["level"]
                ),
                "",
            )
            parts: dict[str, list[str]] = {}
            name = None  # text before the first design section belongs to no section
            for nxt in blocks[index + 1 :]:
                if nxt["kind"] == "heading" and nxt["level"] <= block["level"]:
                    break
                if nxt["kind"] == "heading" and nxt["level"] == block["level"] + 1:
                    name = nxt["text"]
                    parts.setdefault(name, [])
                elif nxt["kind"] != "heading" and name is not None:
                    parts[name].append(block_text(nxt))
            words = {k: sum(len(t.split()) for t in v) for k, v in parts.items()}
            missing = [
                s
                for s in spec.get("required_sections", [])
                if not any(norm(k) == norm(s) and n for k, n in words.items())
            ]
            description = next((v for k, v in parts.items() if norm(k) == norm(spec["marker"])), [])
            found.append(
                artifact(
                    spec["type"],
                    spec.get("id_prefix", "")
                    + ".".join(slug(n) for n in (parent, block["text"]) if n),
                    block["text"],
                    "\n".join(description),
                    {
                        "section": paths[index],
                        "software_item": parent,
                        "design_sections": words,
                        "missing_sections": missing,
                    },
                    source,
                )
            )
    return {"artifacts": found, "pending_links": pending, "report": dict(report)}


def name_tokens(name: str) -> tuple[str, ...]:
    """Words of a software-item name; a plural 's' and a trailing 'Service' are folded."""
    words = [
        w[:-1] if len(w) > 3 and w.endswith("s") else w
        for w in re.findall(r"[a-z0-9]+", name.lower())
    ]
    if len(words) > 1 and words[-1] == "service":
        words.pop()
    return tuple(words)


def component_resolver(artifacts: list[dict]):
    """Name → component ID: the same words, else one component whose words contain (or are
    contained in) the name as a run of at least two whole words. Never substrings."""
    components: dict[tuple[str, ...], str] = {}
    for a in artifacts:
        if a["type"] == "component":
            components.setdefault(name_tokens(a["title"]), a["id"])

    def within(outer: tuple[str, ...], inner: tuple[str, ...]) -> bool:
        return any(outer[i : i + len(inner)] == inner for i in range(len(outer) - len(inner) + 1))

    def resolve(name: str) -> str | None:
        key = name_tokens(name)
        if not key:
            return None
        if key in components:
            return components[key]
        near = {
            cid
            for words, cid in components.items()
            if min(len(words), len(key)) >= 2 and (within(words, key) or within(key, words))
        }
        return near.pop() if len(near) == 1 else None

    return resolve


def resolve_links(artifacts: list[dict], pending: list[dict]) -> tuple[list[dict], Counter]:
    """Matrix rows and unit → software-item names become links to imported components."""
    report: Counter = Counter()
    by_id = {a["id"]: a for a in artifacts}
    component = component_resolver(artifacts)
    links = []
    for row in pending:
        source = by_id.get(row["src_id"])
        if source is None:
            report["matrix rows for unknown requirements"] += 1
            continue
        names = [n.strip() for n in re.split(r"[,;\n]", row["names"]) if n.strip()]
        if not names:  # an empty cell states no allocation; it is not an explicit N/A
            report["matrix rows without software items"] += 1
            continue
        none = {v.strip().upper() for v in row["none_values"]}
        if all(n.rstrip(".").strip().upper() in none for n in names):
            source["attributes"]["allocation"] = "N/A"
            report["requirements allocated N/A"] += 1
            continue
        for name in names:
            target = component(name)
            if target is None:
                source["attributes"].setdefault("unresolved_allocations", []).append(name)
                report["unresolved allocation names"] += 1
            else:
                links.append(edge(source["id"], target, row["link"], row["document"]))
    for unit in (a for a in artifacts if a["type"] == "software_unit"):
        target = component(unit["attributes"].get("software_item", ""))
        if target is None:
            report["units without a matching software item"] += 1
            continue
        unit["attributes"]["component"] = target
        links.append(edge(unit["id"], target, "allocated_to", unit["attributes"]["document"]))
    return links, report


def edge(src: str, dst: str, kind: str, document: str) -> dict:
    return {
        "src": src,
        "dst": dst,
        "type": kind,
        "origin": "explicit",
        "evidence": f"Document trace: {document}",
    }


def version_key(name: str) -> tuple[tuple[int, ...], ...]:
    """Issue markers in a file name ('#11', 'v1.10', '_v06', 'Rev 9') as comparable numbers."""
    found = VERSION.findall(name)
    return tuple(tuple(int(p) for p in v.split(".")) for v in found) or ((0,),)


def csv_artifacts(rows: list[dict], spec: dict, source: dict) -> list[dict]:
    """ADO query export rows → artifacts; dropped columns are never read."""
    found = []
    for row in rows:
        native = (row.get(spec["id"]) or "").strip()
        if not native:
            continue
        attrs: dict = {k: (row.get(v) or "").strip() for k, v in spec.get("attributes", {}).items()}
        for key in spec.get("list_attributes", []):
            attrs[key] = [t.strip() for t in attrs.get(key, "").split(";") if t.strip()]
        if spec["type"] == "test_case":
            attrs.setdefault("level", "system")
        found.append(
            artifact(
                spec["type"],
                spec.get("id_format", "{}").format(native),
                row.get(spec["title"], ""),
                "",
                attrs,
                source,
                anchor="row-" + native,
            )
        )
    return found


def import_folder(folder: Path, profile: Path) -> tuple[dict, dict]:
    """Every matching document in `folder` → validated graph plus an import report."""
    rules = yaml.safe_load(profile.read_text())
    retrieved = datetime.now(UTC).isoformat()
    files = sorted(p for p in folder.iterdir() if p.is_file())
    patterns = rules.get("exclude", [])
    excluded = {p for p in files if any(matches(p.name, g) for g in patterns)}
    report: Counter = Counter()
    artifacts: list[dict] = []
    pending: list[dict] = []
    used: list[str] = []

    def source(path: Path) -> dict:
        return {
            "url": f"file:{path.name}",
            "revision": hashlib.sha256(path.read_bytes()).hexdigest()[:12],
            "retrieved_at": retrieved,
            "document": path.name,
        }

    for rule in rules.get("documents", []):
        found = [p for p in files if matches(p.name, rule["glob"]) and p not in excluded]
        if rule.get("pick", "all") == "latest" and len(found) > 1:
            found.sort(key=lambda p: version_key(p.name))
            report[f"{rule['name']}: older issues skipped"] += len(found) - 1
            if version_key(found[-1].name) == version_key(found[-2].name):
                report[f"{rule['name']}: latest issue ambiguous (took the last by name)"] += 1
            found = found[-1:]
        for path in found:
            try:
                blocks, notes = docx_blocks(path)
            except Exception:  # encrypted or not a Word package
                report["unreadable documents"] += 1
                continue
            result = extract_document(blocks, rule, source(path))
            report.update(notes)
            report.update(result["report"])
            artifacts.extend(result["artifacts"])
            pending.extend(result["pending_links"])
            used.append(path.name)
    for spec in rules.get("csv", []):
        for path in (p for p in files if matches(p.name, spec["glob"]) and p not in excluded):
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            dropped = set(spec.get("drop", []))
            rows = [{k: v for k, v in row.items() if k not in dropped} for row in rows]
            report["personal columns dropped"] += len(dropped)
            artifacts.extend(csv_artifacts(rows, spec, source(path)))
            used.append(path.name)

    # Documents carry only the link classes the profile extracts; rules that need other
    # links (ADO Tested By, Parent/Child) are not assessable for these artifacts.
    provides = list(rules.get("provides_links", []))
    unique: dict[str, dict] = {}
    duplicates = []
    for a in artifacts:
        a["attributes"]["link_classes"] = provides
        if a["id"] in unique:
            duplicates.append(f"{a['id']} ({a['attributes']['document']})")
        else:
            unique[a["id"]] = a
    links, link_report = resolve_links(list(unique.values()), pending)
    report.update(link_report)
    graph = validate_graph({"artifacts": list(unique.values()), "links": links})
    summary = {
        "imported_files": used,
        "excluded_files": sorted(p.name for p in excluded),
        "unused_files": [p.name for p in files if p.name not in used and p not in excluded],
        "artifact_counts": dict(sorted(Counter(a["type"] for a in graph["artifacts"]).items())),
        "link_counts": dict(sorted(Counter(e["type"] for e in graph["links"]).items())),
        "notes": {k: v for k, v in sorted(report.items()) if v},
        "duplicates_ignored": duplicates,
    }
    return graph, summary
